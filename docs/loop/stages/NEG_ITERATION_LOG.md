# Negotiation advisor: looks and changes per item set (D-671 item 8, standing order 102)

Append-only, one line per look at an item set and per change tried on it. Earlier looks at the pilot set are in
role N's SESSION_LOG (sessions 18 to 26: the k=1 score D-654, the k=2 re-score D-695). Sets: `pilot-dev` is the
24-item pilot (set 6a8af3c7...), development since D-695. Counts only. Times before 21:02 are the lane's
estimates (within about 15 minutes); from 21:02 they are read from the clock.

| When (+0300) | Set | Look or change | By | What |
|---|---|---|---|---|
| 2026-11-16 20:05 | pilot-dev | look 1 (development) | lane neg-round1 | error analysis of M1 and M4 on the 18 headline items: where each proposal's answer is lost, per arm (NEG_ROUND1.md section 1) |
| 2026-11-16 20:40 | pilot-dev | change 1, kept | lane neg-round1 | the system's Python step (system_python): M1 0.149 to 0.419, M2 0.367 to 0.457, M3 0.0 to 0.916; M1m, M4, M5, M7, M10 unchanged |
| 2026-11-16 20:40 | pilot-dev | change 2, kept, new runs only | lane neg-round1 | advice schema: one entry per proposal (tuple), reasons at most 8; not measurable on saved answers (Lambda L1) |
| 2026-11-16 20:45 | pilot-dev | change 3, rejected | lane neg-round1 | approach from the system's own alignment: M7 precision 0.609 to 0.393, recall 0.700 to 0.267 |
| 2026-11-16 20:45 | pilot-dev | counterfactual, not applied (rule) | lane neg-round1 | proposal ids without the P- prefix read as ids: M1 0.419 to 0.502 (ANSWER-FORM-A forbids it) |
| 2026-11-16 20:50 | pilot-dev | counterfactual, analysis only | lane neg-round1 | stance rules from conflict and constant stances: M4 at most 0.480, M10 at most 0.444; M1 0.637 with full coverage and all no_conflict |
| 2026-11-16 20:55 | pilot-dev | look 2 (development, a re-read of the saved answers) | lane neg-round1 | after the D-711 and D-712 code, before NEG_BAR.md's D-712 section was committed (65b77dbf): the floors and the per-kind report checked on real rows; no change was chosen on it. M1 unchanged at 0.419; every local class floor 0.0 except M4 kept (system 0.018); 64 on-record claims with no position; bar reading refused (no kind declared) |
| 2026-11-16 21:02 | pilot-dev | changes 4 to 6, built, off or not yet measurable | lane neg-round1 | D-711 basis and record kinds, D-712 floors, D-713 methods (reason_first, stepwise), all new runs only (Lambda plan NEG_ROUND1.md section 6) |
| 2026-11-18 20:38 | pilot-dev | changes 7 to 12 declared, none read (D-756) | lead | before any figure: C1 ceiling count (key and mapping, counts only); N1 oppose recall and precision over all positions against the build's validated stances, item-clustered intervals, development figure only, bar unchanged; P3 proposal-level largest-oppose-margin threshold, one value in config, tuned on a split other than the deciding set; P1 stepwise (NR1118_MSTEP_PILOT) read with N1 and C1 declared; P8 trimmed context as a separate arm against full context; N3 choice steps before generated steps, a refused generated step drops only its field |

| 2026-11-18 20:02 | pilot-dev | look 3 (development, a score of the plain run NR1118_MPLAIN_PILOT as run B beside run A, the saved old answers; role N session 38) | role N | line added late on 19 November 14:5x by the records helper, after the look. Score_neg_advisor.report() called directly at k=2 on the 18 headline items (24 rows, 179 proposal pieces, 0 rows dropped on re-read); development only, no opening read or claimed; 0 model calls, 0 USD. Run B against run A: M1 0.629 against 0.419, M10 0.435 against 0.109, M1m 0.455 against 0.129; conflict class floor still 0.0 on both runs (12 rows), M4 kept class 0.982 on run B against 0.018 on run A, changed 0.0; 5 of 179 pieces withheld by the audit on run B; no change was chosen on it |
