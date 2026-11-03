# covcheck — clause-anchored recomputation of loan covenant compliance certificates

Prototype for the Tresata take-home assignment. **All documents and numbers are synthetic.**

## What it does
A lender's credit analyst receives a quarterly *compliance certificate* in which the borrower
reports its Total Net Leverage Ratio. covcheck independently recomputes that ratio **using the
credit agreement's own definitions, as amended**, and routes the result to the analyst as
`PASS`, `WATCH`, `DISCREPANCY`, `BREACH` or `ABSTAIN`.

* **LLM (optional, `llm_extract.py`)** — reads each agreement/amendment *once* and proposes covenant
  parameters into a fixed schema, each with a verbatim supporting quote.
* **Clause anchoring (`covcheck.verify_field`)** — a parameter is usable only if its quote appears
  verbatim (whitespace/smart-quote normalised) in the cited document **and** the value is literally
  rendered in that quote (e.g. `0.20` must appear as `20%`). Otherwise `UNVERIFIED`.
* **Version resolution (`resolve_spec`)** — per field, the latest document effective on/before the
  test date wins. If the winner is unverified the system abstains; it never falls back to an older,
  possibly superseded term.
* **Deterministic calculation and reconciliation (`compute`, `reconcile`)** — `Decimal` arithmetic,
  explicit tolerances (money: max($1,000, 0.01%); ratio: 0.005), certificate internal-consistency checks.
* **Risk routing (`decide`)** — abstain on any unresolved input; breach > discrepancy > thin headroom (<10%).

## Run
```
python3 -m unittest discover -s tests -v   # 21 tests: 15 scenarios + 6 mechanism tests
python3 run_eval.py                        # writes results/results.md and results/decisions.json
```
Python 3.10+, standard library only.

## Data (all made up)
* `data/credit_agreement.txt`, `data/amendment_1.txt` — synthetic, modelled on the general drafting
  style of US leveraged-loan agreements (defined-term add-backs, % caps, cash-netting caps, step-downs).
* `data/documents.json` — document registry; effective dates are human-entered metadata.
* `data/extraction_*.json` — **hand-written fixtures standing in for LLM output. No LLM produced them.**
* Financials and certificates are generated in `scenarios.py`.

## Results (actual, from `run_eval.py` on the build machine)
`python3 -m unittest` runs 21 tests (15 scenario tests, of which T04 and T06 also assert an
ablation, plus 6 mechanism tests): **all 21 pass**. A pass means the code returns the status the test
expects. T15's test deliberately asserts the known-WRONG status, so judged against the correct answer
**14 of 15 scenario outcomes are correct**. `run_eval.py` prints 17 rows (15 scenarios + 2 ablations).

| ID | Scenario | covcheck | Correct |
|---|---|---|---|
| T01 | Clean certificate | PASS | PASS |
| T02 | Over-cap synergy add-back hides a breach (4.51x vs 4.50x) | BREACH | BREACH |
| T03 | Cash netted above $25m cap | DISCREPANCY | DISCREPANCY |
| T04 | Add-back valid only under Amendment No. 1 | PASS (ablation without amendment: false DISCREPANCY) | PASS |
| T05 | Same add-back before amendment effective | DISCREPANCY | DISCREPANCY |
| T06 | Original step-down date, deferred by amendment | PASS (ablation: 4.00x applied too early) | PASS |
| T07 | After deferred step-down, thin headroom | WATCH | WATCH |
| T08 | Hallucinated quote | ABSTAIN | ABSTAIN |
| T09 | Real quote, unsupported value | ABSTAIN | ABSTAIN |
| T10 | Rounding within tolerance | PASS | PASS |
| T11 | Certificate does not foot | DISCREPANCY | DISCREPANCY |
| T12 | Within 10% of limit | WATCH | WATCH |
| T13 | Missing line item | ABSTAIN | ABSTAIN |
| T14 | Self-reported breach | BREACH | BREACH |
| **T15** | **Amendment quote contains old and new value; LLM picks old** | **DISCREPANCY** | **PASS** |

## Honest limitations
1. **No LLM was run.** Extraction accuracy is untested; only the deterministic verifier is tested,
   using fixtures (including deliberately corrupted ones).
2. **Circular evaluation.** Scenarios, expected outcomes and code were written in the same
   AI-assisted session. Passing tests show internal consistency, not real-world correctness.
3. **Anchoring checks presence, not meaning (T15).** A quote such as *replacing "15%…" with "20%…"*
   supports both values. A real quote attached to the wrong concept also passes.
4. **Fixed schema.** Any clause not in the schema (e.g. a second cap on clause (d), pro forma
   acquisition adjustments, equity cures, cross-referenced definitions) is silently not modelled.
5. One covenant, one agreement family, structured financial inputs, USD, no PDF/OCR handling.
6. Ratio comparison uses unrounded recomputation; agreements may specify their own rounding.

## LLM extraction (optional, not executed here)
`llm_extract.py` calls OpenRouter's chat-completions API. Set `OPENROUTER_API_KEY` and
`OPENROUTER_MODEL` (a current free-tier model id), run it per document, then run the output through
the verifier. **No model was used to produce any result in this repository.**
