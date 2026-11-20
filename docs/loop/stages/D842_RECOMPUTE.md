# D-842 recompute: bar (b) at 10 points below the cloud reference

Operator decision D-842 (Seckin, 20 November 2026, 14:12): the closeness-to-cloud condition is "at most
10 points below the cloud model" everywhere (`gate_score.BAR_BELOW_CLOUD` 0.10). It was 5 points until
20 November 2026. Bar (a), at least 10 points above the bare model (B1), is unchanged. Example: ContraDoc
cloud 90.0 gives a floor of 80.0 (85.0 before).

Recomputed from saved, tracked, keyless figures only: docs/loop/DECISIONS.md, docs/RESULTS.md,
docs/loop/stages/GATE_ATTEMPTS.md, docs/loop/stages/GROUPED_RESEAL_GATE.md and
docs/loop/stages/cloud_reference_score/*.json. No answer key, role folder or private record was opened;
`docs/loop/private/GATE_SCOREBOARD.md` is private and outside git, so its rows are taken from the copies
in GROUPED_RESEAL_GATE.md. Arithmetic only: old status passes when the system minus the cloud is at least
-5.0 points, new status when it is at least -10.0. Bar (b) is read on the point difference as coded; the
interval is shown beside it and gates nothing.

## Gate reads (quick subset 0127b080, steering only)

| Read | Benchmark | System | Cloud | System minus cloud | Old (b), 5 points | New (b), 10 points | Changes |
|---|---|---|---|---|---|---|---|
| K1 (DECISIONS 6089) | ContraDoc, n 40 | 60.0 | 90.0 | -30.0 [-45.0, -15.0] | not met, 25.0 short | not met, 20.0 short | no |
| K0 (DECISIONS 6089) | ContraDoc, n 40 | 55.0 | 90.0 | -35.0 | not met, 30.0 short | not met, 25.0 short | no |
| K1 (DECISIONS 6090) | SciTab 3-class, n 78 | 49.3 | 81.7 | -32.4 [-47.4, -15.8] | not met, 27.4 short | not met, 22.4 short | no |
| K0 (DECISIONS 6969) | ContraDoc, n 40 | 55.0 | 90.0 | -35.0 [-52.5, -17.5] | not met, 30.0 short | not met, 25.0 short | no |
| K0 (DECISIONS 6970) | SciTab 3-class, n 78 | 0.0 | 81.7 | -81.7 | not met, 76.7 short | not met, 71.7 short | no |
| K3 (DECISIONS 7047) | ContraDoc, n 40 | 57.5 | 90.0 | -32.5 | not met, 27.5 short | not met, 22.5 short | no |
| K3 (DECISIONS 7048) | SciTab 3-class, n 78 | 59.8 | 81.7 | -21.9 [-33.5, -7.0] | not met, 16.9 short | not met, 11.9 short | no |
| QUICKSCORE2, 426ef44c (GROUPED_RESEAL_GATE 88; RESULTS) | ContraDoc, n 40, void on integrity | 55.0 | 90.0 | -35.0 | not met, 30.0 short | not met, 25.0 short | no |
| QUICKSCORE2 (GROUPED_RESEAL_GATE 90; RESULTS) | SciTab 3-class, n 78, void on integrity | 19.0 | 81.7 | -62.7 | not met, 57.7 short | not met, 52.7 short | no |

No gate read changes status. Every one stays short of bar (b), and every one also fails bar (a), so
line 5 of GATE_ATTEMPTS section 3 (D-596) stays unmet for all of them.

## Development estimates (GATE_ATTEMPTS section 2, 2-class, half A, not gate reads)

These are in-sample development figures against the cloud reference measured on the same half A
(direct / reasoning). They were never gate reads and they decide nothing; they are listed because two of
them cross the line.

| Configuration | Benchmark | System | Cloud (direct / reasoning) | Minus cloud | Old (b) | New (b) | Changes |
|---|---|---|---|---|---|---|---|
| Judge by probabilities, trained mix, half A (in sample) | SciTab 2-class | .837 | .891 / .888 | -5.4 / -5.1 | not met | met | **yes** |
| Judge 2e trained_full, half A (in sample) | SciTab 2-class | .797 | .891 / .888 | -9.4 / -9.1 | not met | met | **yes** |
| Judge with B1 combined, half A (in sample) | SciTab 2-class | .941 to .943 | .891 / .888 | +5.0 or more | met | met | no |
| Cell question by probabilities, base, half A (in sample) | SciTab 2-class | .738 | .891 / .888 | -15.3 / -15.0 | not met | not met | no |
| "Either", or the trained mix, half A (in sample) | ContraDoc | .733 | .900 / .867 | -16.7 / -13.4 | not met | not met | no |
| Judge by probabilities, base, half A (in sample) | ContraDoc | .700 | .900 / .867 | -20.0 / -16.7 | not met | not met | no |

The two that change pass bar (b) only. Both are in sample (half A chose their thresholds), 2-class while
the gate set is 3-class (D-543), and neither meets bar (a) against B1's half A .918. Out of sample (half B)
no cloud figure exists, so there is nothing to recompute there. GATE_ATTEMPTS' estimate of what bar (b)
needs moves from about .82 to .85 to about .77 to .80 on ContraDoc and from about .84 to about .79 on
SciTab 2-class; the best out-of-sample figures (.600 and .756) stay short.

## Negotiation

The negotiation measures carry their own bars (NEG_ADVISOR_PLAN, NEG_BAR.md); the cloud comparison there
(A2, M1 on the cloud subset) is an indicator, and none of its stated bars uses the 5-point cloud margin, so
nothing there is recomputed. For the record: system M1 0.629 against the cloud's 0.648 on its 14-item
subset (different item sets) is within 5 and within 10 points under either reading.

## Not changed

- The TABLE_TOOL_MEASURE_PLAN non-inferiority margin (5 points, on-minus-off for the table tool) is a
  different quantity and that measurement is closed (D-836); it is left as written, though its text
  names GATE-SCORE-A bar (b) as the reason for choosing 5.
- Power figures in GATE_SET.md section 5 at 5 points are kept beside the new ones at 10 points
  (`contradoc_power.py`, MARGIN now .10).
