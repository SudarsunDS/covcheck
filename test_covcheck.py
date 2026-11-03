import sys, unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from covcheck import load_documents, decide, verify_field, resolve_spec, compute, render_candidates
from scenarios import SCENARIOS, DATA, extractions

DOCS = load_documents(DATA)

class ScenarioTests(unittest.TestCase):
    """One test per synthetic scenario (T01-T15) plus ablations."""

for s in SCENARIOS:
    def make(s=s):
        def t(self):
            d = decide(DOCS, s["ext"], s["fin"], s["cert"])
            self.assertEqual(d.status, s["expected"], d.reasons)
            if "ablation" in s:
                a = s["ablation"]
                self.assertEqual(decide(DOCS, a["ext"], s["fin"], s["cert"]).status, a["expected"])
        return t
    setattr(ScenarioTests, f"test_{s['id']}", make())

class MechanismTests(unittest.TestCase):
    def test_quote_whitespace_and_smart_quotes_normalised(self):
        item = {"value": "0.20", "source_doc": "amendment_1",
                "quote": "replacing \u201c15% of Consolidated   EBITDA\u201d with \u201c20% of Consolidated EBITDA\u201d"}
        self.assertEqual(verify_field("synergy_cap_pct", item, DOCS).status, "VERIFIED")

    def test_unknown_document_rejected(self):
        item = {"value": "4.50", "source_doc": "side_letter", "quote": "4.50:1.00"}
        self.assertEqual(verify_field("max_ratio_initial", item, DOCS).status, "UNVERIFIED")

    def test_unverified_winner_does_not_fall_back_to_older_version(self):
        ext = extractions()
        ext["amendment_1"]["synergy_cap_pct"]["quote"] = "not in the document"
        resolved, issues, _ = resolve_spec(DOCS, ext, date(2026, 6, 30))
        self.assertEqual(resolved["synergy_cap_pct"].source_doc, "amendment_1")
        self.assertTrue(any("synergy_cap_pct" in i for i in issues))

    def test_amendment_ignored_before_effective_date(self):
        resolved, _, _ = resolve_spec(DOCS, extractions(), date(2025, 12, 14))
        self.assertEqual(resolved["synergy_cap_pct"].value, Decimal("0.15"))

    def test_post_addback_cap_algebra(self):
        spec = {"synergy_cap_pct": Decimal("0.20"), "synergy_cap_base": "post_addback",
                "cash_netting_cap": Decimal("25000000"), "max_ratio_initial": Decimal("4.5"),
                "max_ratio_stepped": Decimal("4.0"), "step_down_date": date(2027, 9, 30)}
        f = dict(net_income=20e6, interest_expense=12e6, income_tax_expense=6e6,
                 depreciation_amortization=14e6, non_recurring_charges=8e6,
                 run_rate_synergies=50e6, total_debt=300e6, unrestricted_cash=0)
        c = compute(spec, f, date(2026, 6, 30))
        # cap s satisfies s = 0.2 * (60m + s)  ->  s = 15m
        self.assertEqual(c["synergies_allowed"].quantize(Decimal(1)), Decimal("15000000"))

    def test_ratio_surface_forms(self):
        self.assertIn("4.50:1.00", render_candidates("ratio", Decimal("4.5")))

if __name__ == "__main__":
    unittest.main(verbosity=2)
