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
