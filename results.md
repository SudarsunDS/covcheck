| ID | Scenario | Expected (code) | Actual | Match | Recomputed ratio | Correct answer | First reason |
|---|---|---|---|---|---|---|---|
| T01 | Clean certificate, comfortable headroom | PASS | PASS | yes | 3.9286 | PASS | Recomputed ratio 3.9286 within limit 4.50; certificate reconciles |
| T02 | Synergy add-back over cap hides a breach | BREACH | BREACH | yes | 4.5139 | BREACH | Recomputed ratio 4.5139 exceeds limit 4.50; certificate CLAIMS COMPLIANCE |
| T03 | Cash netted above the $25m cap | DISCREPANCY | DISCREPANCY | yes | 3.9286 | DISCREPANCY | recompute: cash_netted reported 30000000 vs expected 25000000 |
| T04 | Add-back valid only under Amendment No. 1 (20% cap) | PASS | PASS | yes | 3.8732 | PASS | Recomputed ratio 3.8732 within limit 4.50; certificate reconciles |
| T04-ablation | Ignoring the amendment produces a false discrepancy | DISCREPANCY | DISCREPANCY | yes | - | (ablation) | recompute: synergies_addback reported 11000000 vs expected 9000000.00 |
| T05 | Same add-back before amendment effective date (15% cap applies) | DISCREPANCY | DISCREPANCY | yes | 3.9855 | DISCREPANCY | recompute: synergies_addback reported 11000000 vs expected 9000000.00 |
| T06 | Original step-down date, but amendment deferred it | PASS | PASS | yes | 3.9855 | PASS | Recomputed ratio 3.9855 within limit 4.50; certificate reconciles |
| T06-ablation | Ignoring the amendment applies the 4.00x limit too early | WATCH | WATCH | yes | - | (ablation) | Compliant but headroom 0.4% < 10% of limit 4.00 |
| T07 | After deferred step-down: 4.00x limit, thin headroom | WATCH | WATCH | yes | 3.9286 | WATCH | Compliant but headroom 1.8% < 10% of limit 4.00 |
| T08 | Extraction quote not present in document (hallucinated clause) | ABSTAIN | ABSTAIN | yes | - | ABSTAIN | Cannot recompute; analyst must resolve: cash_netting_cap: quote not found verbatim in cited document (source credit_agreement) |
| T09 | Real quote, but extracted value not stated in it | ABSTAIN | ABSTAIN | yes | - | ABSTAIN | Cannot recompute; analyst must resolve: synergy_cap_pct: extracted value is not stated in the quoted text (source amendment_1) |
| T10 | Borrower rounding within tolerance | PASS | PASS | yes | 3.9286 | PASS | Recomputed ratio 3.9286 within limit 4.50; certificate reconciles |
| T11 | Certificate arithmetic does not foot | DISCREPANCY | DISCREPANCY | yes | 3.9286 | DISCREPANCY | internal: certificate EBITDA = components + synergy add-back reported 72000000 vs expected 70000000 |
| T12 | Compliant but within 10% of limit | WATCH | WATCH | yes | 4.4000 | WATCH | Compliant but headroom 2.2% < 10% of limit 4.50 |
| T13 | Required financial line item missing | ABSTAIN | ABSTAIN | yes | - | ABSTAIN | Cannot recompute; analyst must resolve: financial inputs missing: depreciation_amortization |
| T14 | Borrower self-reports breach; recomputation agrees | BREACH | BREACH | yes | 4.5714 | BREACH | Recomputed ratio 4.5714 exceeds limit 4.50; certificate also reports breach |
| T15 | KNOWN LIMITATION: amendment quote contains old AND new value | DISCREPANCY | DISCREPANCY | yes | 3.9855 | PASS | recompute: synergies_addback reported 11000000 vs expected 9000000.00 |
