"""
covcheck - clause-anchored covenant recomputation (prototype).

Pipeline (everything in this file is deterministic; the LLM only produces the
extraction JSON that `resolve_spec` consumes):

  extraction JSON (LLM or fixture)
      -> verify_field()   clause anchoring: quote must exist verbatim in the cited
                          document AND the extracted value must be rendered in it
      -> resolve_spec()   version-aware: latest document effective on/before the
                          test date wins; an unverified winner blocks (no fallback)
      -> compute()        Decimal arithmetic for the Total Net Leverage Ratio
      -> reconcile()      certificate internal consistency + vs. recomputation
      -> decide()         ABSTAIN / BREACH / DISCREPANCY / WATCH / PASS

Scope: one maintenance covenant (Total Net Leverage Ratio) with a capped
synergy add-back and a capped cash-netting deduction. See README for limits.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Fixed extraction schema: field name -> value kind.
SCHEMA = {
    "max_ratio_initial": "ratio",
    "step_down_date": "date",
    "max_ratio_stepped": "ratio",
    "synergy_cap_pct": "pct",
    "synergy_cap_base": "cap_base",
    "cash_netting_cap": "money",
}

LINE_ITEMS = [
    "net_income", "interest_expense", "income_tax_expense",
    "depreciation_amortization", "non_recurring_charges",
    "run_rate_synergies", "total_debt", "unrestricted_cash",
]
EBITDA_BASE_ITEMS = LINE_ITEMS[:5]

# Tolerances (explicit, configurable). Money: max(abs floor, relative).
MONEY_ABS_TOL = Decimal("1000")
MONEY_REL_TOL = Decimal("0.0001")
RATIO_ABS_TOL = Decimal("0.005")      # certificate ratios are reported to 2 dp
WATCH_HEADROOM = Decimal("0.10")      # escalate if within 10% of the limit


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------
@dataclass
class Document:
    doc_id: str
    effective_date: date
    text: str


def load_documents(data_dir: Path) -> dict[str, Document]:
    registry = json.loads((data_dir / "documents.json").read_text())
    return {
        r["doc_id"]: Document(
            r["doc_id"], date.fromisoformat(r["effective_date"]),
            (data_dir / r["path"]).read_text(),
        )
        for r in registry
    }


def normalize(text: str) -> str:
    text = (text.replace("\u201c", '"').replace("\u201d", '"')
                .replace("\u2018", "'").replace("\u2019", "'"))
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# Clause anchoring
# --------------------------------------------------------------------------
def parse_value(kind: str, raw):
    if kind in ("ratio", "pct", "money"):
        return Decimal(str(raw))
    if kind == "date":
        return date.fromisoformat(str(raw))
    if kind == "cap_base":
        if raw not in ("pre_addback", "post_addback"):
            raise ValueError(f"unknown cap_base {raw!r}")
        return raw
    raise ValueError(kind)


def render_candidates(kind: str, value) -> list[str]:
    """Surface forms a value may take in contract prose."""
    if kind == "ratio":
        return [f"{value:.2f}:1.00", f"{value:.2f} to 1.00", f"{value:.2f}:1"]
    if kind == "pct":
        p = format((value * 100).normalize(), "f")
        return [f"{p}%", f"{p} percent"]
    if kind == "money":
        return [f"${int(value):,}"]
    if kind == "date":
        return [f"{value.strftime('%B')} {value.day}, {value.year}"]
    if kind == "cap_base":
        return {"pre_addback": ["before giving effect to such add-backs"],
                "post_addback": ["after giving effect to such add-backs"]}[value]
    return []


@dataclass
class FieldCheck:
    name: str
    value: object
    source_doc: str | None
    effective_date: str | None
    quote: str | None
    status: str          # VERIFIED | UNVERIFIED
    reason: str = ""


def verify_field(name: str, item: dict, documents: dict[str, Document]) -> FieldCheck:
    kind = SCHEMA[name]
    doc_id, quote = item.get("source_doc"), item.get("quote")
    doc = documents.get(doc_id)
    eff = doc.effective_date.isoformat() if doc else None

    def fail(reason, value=None):
        return FieldCheck(name, value, doc_id, eff, quote, "UNVERIFIED", reason)

    try:
        value = parse_value(kind, item.get("value"))
    except (InvalidOperation, ValueError, TypeError) as e:
        return fail(f"value not parseable as {kind}: {e}")
    if doc is None:
        return fail(f"unknown source document {doc_id!r}", value)
    if not quote or normalize(quote) not in normalize(doc.text):
        return fail("quote not found verbatim in cited document", value)
    nq = normalize(quote)
    if not any(c in nq for c in render_candidates(kind, value)):
        return fail("extracted value is not stated in the quoted text", value)
    return FieldCheck(name, value, doc_id, eff, quote, "VERIFIED")


def resolve_spec(documents: dict[str, Document], extractions: dict[str, dict],
                 test_date: date):
    """Pick, per field, the latest document effective on/before test_date.

    Returns (resolved: name -> FieldCheck, issues: list[str], history: name -> list).
    An UNVERIFIED winner is an issue: we never fall back to an older version,
    because that would silently apply a superseded term.
    """
    resolved, issues, history = {}, [], {}
    for name in SCHEMA:
        cands = []
        for doc_id, ext in extractions.items():
            doc = documents.get(doc_id)
            if doc is None or name not in ext:
                continue
            if doc.effective_date > test_date:
                continue
            cands.append(verify_field(name, ext[name], documents))
        if not cands:
            issues.append(f"{name}: no source document defines this term")
            continue
        cands.sort(key=lambda c: c.effective_date or "")
        latest = cands[-1].effective_date
        tied = [c for c in cands if c.effective_date == latest]
        history[name] = [asdict(c) for c in cands]
        if len(tied) > 1 and len({str(c.value) for c in tied}) > 1:
            issues.append(f"{name}: conflicting values from documents with the same effective date")
            continue
        winner = tied[-1]
        resolved[name] = winner
        if winner.status != "VERIFIED":
            issues.append(f"{name}: {winner.reason} (source {winner.source_doc})")
    return resolved, issues, history


# --------------------------------------------------------------------------
# Deterministic calculation
# --------------------------------------------------------------------------
def D(x) -> Decimal:
    return Decimal(str(x))


def compute(spec: dict, fin: dict, test_date: date) -> dict:
    base = sum(D(fin[k]) for k in EBITDA_BASE_ITEMS)
    pct = spec["synergy_cap_pct"]
    if spec["synergy_cap_base"] == "pre_addback":
        cap = pct * base
    else:  # cap measured on EBITDA including the add-back: s <= pct*(base+s)
        cap = pct * base / (1 - pct)
    claimed = D(fin["run_rate_synergies"])
    allowed = min(claimed, cap)
    ebitda = base + allowed
    cash = D(fin["unrestricted_cash"])
    cash_netted = min(cash, spec["cash_netting_cap"])
    net_debt = D(fin["total_debt"]) - cash_netted
    threshold = (spec["max_ratio_initial"] if test_date < spec["step_down_date"]
                 else spec["max_ratio_stepped"])
    ratio = net_debt / ebitda if ebitda > 0 else None
    return {
        "ebitda_before_synergies": base, "synergy_cap": cap,
        "synergies_claimed": claimed, "synergies_allowed": allowed,
        "consolidated_ebitda": ebitda, "cash_netted": cash_netted,
        "consolidated_net_debt": net_debt, "total_net_leverage_ratio": ratio,
        "threshold": threshold,
        "threshold_source": "max_ratio_initial" if test_date < spec["step_down_date"] else "max_ratio_stepped",
    }


# --------------------------------------------------------------------------
# Reconciliation
# --------------------------------------------------------------------------
def money_close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= max(MONEY_ABS_TOL, MONEY_REL_TOL * abs(b))


@dataclass
class Check:
    item: str
    reported: str
    expected: str
    ok: bool
    kind: str   # internal | recompute


def reconcile(cert: dict, comp: dict) -> list[Check]:
    r = {k: D(v) for k, v in cert["reported"].items() if k != "compliant"}
    out = []
    # 1. internal consistency of the certificate's own arithmetic
    comp_sum = sum(D(cert["reported_components"][k]) for k in EBITDA_BASE_ITEMS)
    out.append(Check("certificate EBITDA = components + synergy add-back",
                     str(r["consolidated_ebitda"]), str(comp_sum + r["synergies_addback"]),
                     money_close(r["consolidated_ebitda"], comp_sum + r["synergies_addback"]), "internal"))
    implied = r["consolidated_net_debt"] / r["consolidated_ebitda"]
    out.append(Check("certificate ratio = net debt / EBITDA", str(r["total_net_leverage_ratio"]),
                     f"{implied:.4f}", abs(implied - r["total_net_leverage_ratio"]) <= RATIO_ABS_TOL, "internal"))
    # 2. certificate vs. independent recomputation
    for key, ckey in [("synergies_addback", "synergies_allowed"),
                      ("consolidated_ebitda", "consolidated_ebitda"),
                      ("cash_netted", "cash_netted"),
                      ("consolidated_net_debt", "consolidated_net_debt")]:
        out.append(Check(key, str(r[key]), str(comp[ckey]), money_close(r[key], comp[ckey]), "recompute"))
    out.append(Check("total_net_leverage_ratio", str(r["total_net_leverage_ratio"]),
                     f"{comp['total_net_leverage_ratio']:.4f}",
                     abs(r["total_net_leverage_ratio"] - comp["total_net_leverage_ratio"]) <= RATIO_ABS_TOL,
                     "recompute"))
    return out


# --------------------------------------------------------------------------
# Risk-based routing
# --------------------------------------------------------------------------
@dataclass
class Decision:
    status: str      # ABSTAIN | BREACH | DISCREPANCY | WATCH | PASS
    severity: str
    reasons: list = field(default_factory=list)
    computed: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    checks: list = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str, indent=2)


def decide(documents, extractions, fin, cert) -> Decision:
    test_date = date.fromisoformat(cert["test_date"])
    resolved, issues, _ = resolve_spec(documents, extractions, test_date)
    prov = {k: {"value": str(v.value), "source_doc": v.source_doc, "effective": v.effective_date,
                "quote": v.quote, "status": v.status} for k, v in resolved.items()}
    missing = [k for k in LINE_ITEMS if k not in fin]
    if missing:
        issues.append(f"financial inputs missing: {', '.join(missing)}")
    if issues:
        return Decision("ABSTAIN", "high", ["Cannot recompute; analyst must resolve: " + i for i in issues],
                        provenance=prov)
    spec = {k: v.value for k, v in resolved.items()}
    comp = compute(spec, fin, test_date)
    if comp["total_net_leverage_ratio"] is None:
        return Decision("ABSTAIN", "high", ["Consolidated EBITDA <= 0; ratio undefined"], comp, prov)
    checks = reconcile(cert, comp)
    failed = [c for c in checks if not c.ok]
    ratio, thr = comp["total_net_leverage_ratio"], comp["threshold"]
    claimed_ok = bool(cert["reported"]["compliant"])
    reasons = [f"{c.kind}: {c.item} reported {c.reported} vs expected {c.expected}" for c in failed]
    if ratio > thr:
        lead = (f"Recomputed ratio {ratio:.4f} exceeds limit {thr:.2f}")
        lead += "; certificate CLAIMS COMPLIANCE" if claimed_ok else "; certificate also reports breach"
        return Decision("BREACH", "critical", [lead] + reasons, comp, prov, [asdict(c) for c in checks])
    if failed:
        return Decision("DISCREPANCY", "high", reasons, comp, prov, [asdict(c) for c in checks])
    headroom = (thr - ratio) / thr
    if headroom < WATCH_HEADROOM:
        return Decision("WATCH", "medium",
                        [f"Compliant but headroom {headroom:.1%} < {WATCH_HEADROOM:.0%} of limit {thr:.2f}"],
                        comp, prov, [asdict(c) for c in checks])
    return Decision("PASS", "low", [f"Recomputed ratio {ratio:.4f} within limit {thr:.2f}; certificate reconciles"],
                    comp, prov, [asdict(c) for c in checks])
