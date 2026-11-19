# The v1.1 plan

The tasks the operator has moved to v1.1, in order. Each has its GitHub issue (label `v1.1`); none is skipped or
dropped without the operator's own word. Kept by the loop lead; every new v1.1 task is added here the day it is moved.

| # | Task | Issue | Moved by | Notes |
|---|---|---|---|---|
| 1 | Operator-given red lines (the party's mandate), used together with red lines found in the document, each marked with its source; benchmark items that hold given red lines as well as items without; the frozen pilot set unchanged | #278 | D-664, 15 November 2026 | One of v1.1's first tasks. Red lines are already stored with a source field ("from the document") so this adds a second source without rework. |
| 2 | CLadder and Corr2Cause as further benchmarks | to open | Seckin 14:58, 15 November 2026 (D-636) | Moved to v1.15 (Seckin 01:31, 19 November 2026, standing order 111), no pause before it. Time and cost: estimate, see AFTER_V1_PLAN.md. |
| 3 | The full-set final test (half size ContraDoc and SciTab) and the negotiation final test, run beside the old-system, bare-model and cloud re-measurement (A1 below) | #259, #301 | Seckin 08:38, 19 November 2026 | Moved from v1.0: v1.0 ships on development and pilot figures, stated in its limitations. Estimate about 37 USD (32.1 and up to 4.9, V10 plan rows 11 and 12). |
| 4 | SciTab's "not enough info" class for table claims and the cell_claim threshold (the bound below which a table claim stays undecided), chosen and measured inside row 3's full-set measurement | to open | D-778, Seckin 12:46, 19 November 2026 | Option (a) of FOR_SECKIN 12:06: role B's D3 draw stopped by its own rule (the pool of 83 claims held no "not enough info" claim), so no threshold is chosen in v1.0 and nothing is drawn from the held-out pool; D-760's threshold step and D-762's D3 part are closed unused. v1.0's limitations say so (docs/release/drafts/README_LIMITATIONS_DRAFT.md). No separate cost: it rides row 3. |
| 5 | C9: Auto-Ontology fit (its concept classes mapped onto our graph's node types by a declared mapping, not a DELTA), then its measured comparison | #265 | D-765, Seckin 08:37, 19 November 2026 | "Declared mapping, not a DELTA; a v1.1 item, nothing now." The fit check is done on lane/v105-c9-autoonto 566fd6d6 (not merged; docs/loop/private/v105/C9.md, docs/loop/stages/V105_AUTO_ONTOLOGY_FIT.md, checks 590 to 592): conditional GO, about 13.4 USD (21.9 if our arms are not reused), step_cost.py estimate; a loopback serving path beside VLLM-ROUTE-A needs its own decision id. |
| 6 | N2: the TABLE-AUTHORITY change (a Python comparison layer for table claims), its amendment, hard-rule text and measurement | to open | D-764 item 3, Seckin 08:17, 19 November 2026 | Conditional: in v1.05's grouped re-seal only if v1.05 money remains, else here. Draft at 0 USD: docs/loop/stages/V105_N2_TABLE_AUTHORITY_DRAFT.md (merged 313c2ea9); measurement about 3 to 7 USD (estimate, FOR_SECKIN 12:17); above 5 USD goes to Seckin. |

> Two budgets (Seckin 08:40, 19 November 2026): (a) the 400 USD cap covers v1.0 and v1.05 only; (b) v1.1 (full-set final test, negotiation final test, old-system, bare-model and cloud re-measurement, ablations) has its own budget, not set yet, and no paid v1.1 step starts before he sets it.

## After v1.1

| # | Task | Issue | Moved by | Notes |
|---|---|---|---|---|
| A1 | Re-measure the cloud and bare models on the same items as Shimmer, the final test included | #292 | D-671, 15 November 2026 20:04 | Until then no API or bare-model run on any set; comparisons use the figures measured once on the quick subset, labelled as measured on other items. |
| A2 | Apply the same output form to the cloud and bare-model arms when they run again: fixed answer choices and the advice schema (the API's structured output for the cloud arm), the cloud reference arms' label list, and B1's label constraint only by a decision of its own (B1-ARM-A) | #279 | D-672, 15 November 2026 20:07 | Shimmer's own arms get it now (D-672 item 1). |

## Releases and order (standing order 111, Seckin 01:31, 19 November 2026)

No pause between releases. v1.0 as now; v1.05 straight after it (runtime speed, operator-given red lines (#278, row 1 above, now in v1.05), the GNN and ontology work, a first user interface); v1.1 (the ablations and the re-measurement of the old system, the bare model and the cloud model, rows A1 and A2 below, #292 and #279); v1.15 (the table tool, optional, CLadder and Corr2Cause (row 2 above), everything else still open). Each starts at once after its predecessor. Times and costs per item are in the first section of `docs/loop/stages/AFTER_V1_PLAN.md`; a figure there is recorded only where one exists, otherwise it is marked as an estimate.
