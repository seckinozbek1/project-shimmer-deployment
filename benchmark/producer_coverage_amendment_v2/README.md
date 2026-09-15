# Producer coverage amendment V2

Evidence: **training_label_curation_evidence / curation_only**.
Not independent generalization evidence, blind final evaluation or model acceptance.

**PRODUCER_TUNING_COVERAGE_NOT_READY**
**BALANCED_AGENT_ADJUDICATED_TUNING_EXPERIMENT_NOT_READY**
Human PENDING; training unauthorized.

Method/population commit `1c50cff`; label freeze/failure audit `3f5d4f4`.
Exact64 substantive packets:32 TRAIN/32 DEV;192 fresh primaries;180 valid;19 adjudications.
All otherwise-qualified32 TRAIN/28 DEV labels are quarantined because a historical target-reading regression ran before the label freeze. Four DEV packets separately fail frozen heading/completeness parsing. Eligible files are empty; no balanced execution manifest is issued. Prior evidence and auditor46/24 remain unchanged.

Read `docs/fix/PRODUCER_TUNING_COVERAGE_AMENDMENT_V2.md` and `PRE_GOLD_ACCESS_AUDIT.json` before interpreting results. Never use agreement rates as test/model-quality evidence.

The post-label audit verifies its committed freeze before target-reading checks:

```powershell
& 'C:\Users\secki\anaconda3\python.exe' benchmark/producer_coverage_amendment_v2/gate.py
```

For target-reading cohort regressions, use `regression_phase_guard.py --label-commit <full SHA>`. It rejects missing/uncommitted label freezes before launching the harness. Retain packet-only workspaces under output/producer_coverage_amendment_v2 for procedural isolation checks. Do not rerun one-time selection/review/freeze/comparison stages to overwrite historical evidence.
