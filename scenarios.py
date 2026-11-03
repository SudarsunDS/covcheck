"""
Synthetic evaluation scenarios (all numbers made up, USD).

Each scenario = (financials, compliance certificate, extraction fixtures) and
the status a careful analyst would assign. `known_limitation` scenarios record
where the prototype is WRONG: `expected` is what the code actually returns,
`correct` is what the right answer is.
"""
from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

DATA = Path(__file__).parent / "data"
BASE_EXT = json.loads((DATA / "extraction_credit_agreement.json").read_text())
AMD_EXT = json.loads((DATA / "extraction_amendment_1.json").read_text())


def extractions(base=None, amd=None, include_amendment=True):
    ext = {"credit_agreement": copy.deepcopy(base or BASE_EXT)}
    if include_amendment:
        ext["amendment_1"] = copy.deepcopy(amd or AMD_EXT)
    for e in ext.values():
        e.pop("_provenance", None)
    return ext


def fin(**over):
    f = dict(net_income=20_000_000, interest_expense=12_000_000, income_tax_expense=6_000_000,
             depreciation_amortization=14_000_000, non_recurring_charges=8_000_000,   # base = 60.0m
             run_rate_synergies=10_000_000, total_debt=300_000_000, unrestricted_cash=30_000_000)
    f.update(over)
    return f


def borrower_cert(f, test_date, addback, cash_netted, ebitda_override=None, compliant=True):
    """Certificate as the BORROWER computed it (may embed the borrower's errors)."""
    comps = {k: f[k] for k in ["net_income", "interest_expense", "income_tax_expense",
                                "depreciation_amortization", "non_recurring_charges"]}
    ebitda = ebitda_override if ebitda_override is not None else sum(comps.values()) + addback
    nd = f["total_debt"] - cash_netted
    ratio = (Decimal(nd) / Decimal(ebitda)).quantize(Decimal("0.01"))
    return {"test_date": test_date, "reported_components": comps,
            "reported": {"synergies_addback": addback, "consolidated_ebitda": ebitda,
                         "cash_netted": cash_netted, "consolidated_net_debt": nd,
                         "total_net_leverage_ratio": str(ratio), "compliant": compliant}}


def _amd(field, value=None, quote=None):
    a = copy.deepcopy(AMD_EXT)
    if value is not None:
        a[field]["value"] = value
    if quote is not None:
        a[field]["quote"] = quote
    return a


def _base(field, value=None, quote=None):
    b = copy.deepcopy(BASE_EXT)
    if value is not None:
        b[field]["value"] = value
    if quote is not None:
        b[field]["quote"] = quote
    return b


Q2_26 = "2026-06-30"   # after Amendment No. 1 (cap 20%), before step-down

SCENARIOS = [
    dict(id="T01", name="Clean certificate, comfortable headroom",
         fin=fin(), cert=borrower_cert(fin(), Q2_26, 10_000_000, 25_000_000),
         ext=extractions(), expected="PASS"),
    dict(id="T02", name="Synergy add-back over cap hides a breach",
         fin=fin(run_rate_synergies=18_000_000, total_debt=350_000_000),
         cert=borrower_cert(fin(run_rate_synergies=18_000_000, total_debt=350_000_000), Q2_26, 18_000_000, 25_000_000),
         ext=extractions(), expected="BREACH"),
    dict(id="T03", name="Cash netted above the $25m cap",
         fin=fin(), cert=borrower_cert(fin(), Q2_26, 10_000_000, 30_000_000),
         ext=extractions(), expected="DISCREPANCY"),
    dict(id="T04", name="Add-back valid only under Amendment No. 1 (20% cap)",
         fin=fin(run_rate_synergies=11_000_000),
         cert=borrower_cert(fin(run_rate_synergies=11_000_000), Q2_26, 11_000_000, 25_000_000),
         ext=extractions(), expected="PASS",
         ablation=dict(ext=extractions(include_amendment=False), expected="DISCREPANCY",
                       note="Ignoring the amendment produces a false discrepancy")),
    dict(id="T05", name="Same add-back before amendment effective date (15% cap applies)",
         fin=fin(run_rate_synergies=11_000_000),
         cert=borrower_cert(fin(run_rate_synergies=11_000_000), "2025-09-30", 11_000_000, 25_000_000),
         ext=extractions(), expected="DISCREPANCY"),
    dict(id="T06", name="Original step-down date, but amendment deferred it",
         fin=fin(run_rate_synergies=9_000_000),
         cert=borrower_cert(fin(run_rate_synergies=9_000_000), "2027-03-31", 9_000_000, 25_000_000),
         ext=extractions(), expected="PASS",
         ablation=dict(ext=extractions(include_amendment=False), expected="WATCH",
                       note="Ignoring the amendment applies the 4.00x limit too early")),
    dict(id="T07", name="After deferred step-down: 4.00x limit, thin headroom",
         fin=fin(), cert=borrower_cert(fin(), "2027-09-30", 10_000_000, 25_000_000),
         ext=extractions(), expected="WATCH"),
    dict(id="T08", name="Extraction quote not present in document (hallucinated clause)",
         fin=fin(), cert=borrower_cert(fin(), Q2_26, 10_000_000, 25_000_000),
         ext=extractions(base=_base("cash_netting_cap", "50000000",
                                     "unrestricted cash so netted shall not exceed $50,000,000")),
         expected="ABSTAIN"),
    dict(id="T09", name="Real quote, but extracted value not stated in it",
         fin=fin(), cert=borrower_cert(fin(), Q2_26, 10_000_000, 25_000_000),
         ext=extractions(amd=_amd("synergy_cap_pct", "0.25")), expected="ABSTAIN"),
    dict(id="T10", name="Borrower rounding within tolerance",
         fin=fin(), cert=borrower_cert(fin(), Q2_26, 10_000_000, 25_000_000, ebitda_override=70_000_400),
         ext=extractions(), expected="PASS"),
    dict(id="T11", name="Certificate arithmetic does not foot",
         fin=fin(), cert=borrower_cert(fin(), Q2_26, 10_000_000, 25_000_000, ebitda_override=72_000_000),
         ext=extractions(), expected="DISCREPANCY"),
    dict(id="T12", name="Compliant but within 10% of limit",
         fin=fin(total_debt=333_000_000), cert=borrower_cert(fin(total_debt=333_000_000), Q2_26, 10_000_000, 25_000_000),
         ext=extractions(), expected="WATCH"),
    dict(id="T13", name="Required financial line item missing",
         fin={k: v for k, v in fin().items() if k != "depreciation_amortization"},
         cert=borrower_cert(fin(), Q2_26, 10_000_000, 25_000_000),
         ext=extractions(), expected="ABSTAIN"),
    dict(id="T14", name="Borrower self-reports breach; recomputation agrees",
         fin=fin(total_debt=345_000_000),
         cert=borrower_cert(fin(total_debt=345_000_000), Q2_26, 10_000_000, 25_000_000, compliant=False),
         ext=extractions(), expected="BREACH"),
    dict(id="T15", name="KNOWN LIMITATION: amendment quote contains old AND new value",
         fin=fin(run_rate_synergies=11_000_000),
         cert=borrower_cert(fin(run_rate_synergies=11_000_000), Q2_26, 11_000_000, 25_000_000),
         ext=extractions(amd=_amd("synergy_cap_pct", "0.15")),
         expected="DISCREPANCY", correct="PASS", known_limitation=True),
]
