# The plan to 12 November (D-S79 item 1)

> **Superseded in part (9 November 2026, D-371).** D-S92 makes the fresh read conditional on a pre-read gate (the whole system at least 10 points above B1 and at most 5 below the cloud reference, on held-out development items, in each paper's own metric, D-S99). The fresh read on 10 and 11 November happens only if that gate is passed. If not, the 12 November package states where the system stands against both bars and the work goes on. The hour-by-hour plan to the gate is in the return brief.

Written 9 November 2026, 11:05 +0300, by the lead, from the measured progress of the three running trainings and the run times recorded in `TIME_BUDGET.md`. Planned backwards from 12 November. Every time is local (+0300). A step moves only when the step before it is done, and the lead records each move in `DECISIONS.md`.

## The critical path

The fresh-set read is the last measurement, and it needs every model-backed part trained if training helps, and calibrated (D-S70, D-322). So the critical path runs: trainings, their reads, calibration, the system configuration frozen, the fresh read, the report.

| When | Step | Depends on | Measured basis |
|---|---|---|---|
| 9 Nov, about 12:30 | Auditor training (AUD_TRAIN5) ends | running | 737 updates at 9.4 to 9.8 s, then 5 passes of 789 decisions |
| 9 Nov, about 13:30 | Producer training (P3_TRAIN_B) ends | running | 352 of 704 replies at 10:57, 3.5 a minute |
| 9 Nov, about 15:30 to 16:30 | Judge 2e training (T2E_TRAIN_F) ends | running | 710 updates; 293 to 357 minutes expected from 09:38 |
| 9 Nov, as each ends | Each read under its committed rule. The auditor's and the producer's tuning parts come first, then their held-out row is committed, then the held-out read (D-330). The judge's success is in-sample. | that run | the scorers run locally, minutes |
| 9 Nov evening | The bound wrapper's fastest-order fix merged (lane/wrapper-rule), and the case-manifest check fix (lane/cases-2) | the trainings ended | the controller gate, about 30 minutes |
| 9 Nov evening | Calibration: the judge's decision threshold measured on development rows and written to `config/semantic_thresholds.json` as a recorded decision; each trained part's checkpoint chosen by its rule | the reads | local, no model |
| 10 Nov morning | The system configuration frozen for the read: which checkpoints, which thresholds, the passage pair form | calibration | recorded decision |
| 10 Nov | Step 5: the worked cases again on the product as it stands (by 11 Nov 12:00) | the frozen configuration | the cases batch took 135 minutes |
| 10 Nov | The timing entry (one development document) on the frozen configuration, to forecast the fresh read | the frozen configuration | about 45 minutes |
| 10 Nov evening | The fresh read sealed: 100 ContraDoc documents, B3 and B1, in batches across several machines (D-S79 item 2), after a records check | the timing entry, the wrapper fix | B3 on ContraDoc: median 5.2 to 7.4 minutes a document on the A10 |
| 11 Nov | The fresh read runs, then the read-once scoring (`system_test.py`: the marker committed before any figure) | the seal | 100 documents across 4 to 8 machines, a few hours |
| 11 Nov to 12 Nov | The report (`docs/TECHNICAL_REPORT.md`) and the package, every figure from a named run, under the comparability rule | the read | writing |

## Beside the critical path, in parallel

- **The causal-readiness probe (D-S78)** on CLadder and Corr2Cause, measurement only. The plan, the engine and the role B request are built (lane/causal), and a checker is reading them now. Role B stages the items today. The seal and launch follow on 10 November: about 180 minutes on two A10s, about 10 USD.
- **PUBHEALTH (D-S77, D-S85):** the adapter, the overlap check and the role B request are being built (lane/other-domains). Its run follows on 10 November if the overlap check passes.
- **The cloud reference (D-S35):** prices from Anthropic's page, then one paid run of 15 USD at most, on 10 November.
- **The auditor's VERIFIER attempt:** a plan from the L-6 evidence is being written. It runs only if its run and held-out read fit before the configuration is frozen on 10 November.
- **D-S82's factor record and D-S66's live view** are being built, and are used from the fresh read on.

## What may not fit, and why

- **The VERIFIER attempt.** If its plan needs a training run, that run plus its held-out read may not end before the configuration freezes on the morning of 10 November. Then the read uses the shipped VERIFIER, and the attempt is reported as not run.
- **The fastest machines.** Every launch so far ran on the A10, because the sealed launch wrapper admits only A10-first lists (D-352). The fix merges tonight; from the fresh read on, D-S79 item 2 applies.
- **The time targets (D-S80).** These are measured and reported, not met: ContraDoc reviews take 5 to 7 minutes against a 2.5-minute target (`TIME_BUDGET.md`). Under D-S81, time is never a condition of success in this loop.

## Budget

Spent 125.28 USD at 11:00, with three runs open (caps 18.32, 19.33 and 11.32). Ahead, all forecasts: the cases about 5, the timing entry about 1, the fresh read about 30 to 60 across several machines, the causal probe about 10, PUBHEALTH about 5, and the cloud reference at most 15. Together they stay under the 299 hard stop and above the 60 floor. The 250 warning is given when spend nears it.
