# Producer coverage amendment V1

**PRODUCER_TUNING_COVERAGE_NOT_READY**
**BALANCED_AGENT_ADJUDICATED_TUNING_EXPERIMENT_NOT_READY**
Human review remains PENDING; training is not authorized.

Method/selection commit `06dfa0f`; pre-gold labels/canonical targets commit `6f12153`.
Fresh review: 80 packets, 240 primaries, 222 valid, 26 adjudications. Eligible subset: 20 TRAIN/16 DEV. The attempted selection incorrectly included 16 easy TRAIN reserves; all are excluded, with the original run preserved as a governance failure. Only 32 substantive TRAIN/32 DEV exist. The corrected selector refuses historical overwrites; do not rerun it here.

Policy/renderer and labels are frozen. Do not retrofit synonyms or rewrite history. V1/V2 and auditors remain unchanged. Read `docs/fix/PRODUCER_TUNING_COVERAGE_AMENDMENT_V1.md` for all limitations and results.

Local audit:

```powershell
& 'C:\Users\secki\anaconda3\python.exe' benchmark/producer_coverage_amendment_v1/gate.py
```

The gate validates preserved failures and correctly returns NOT_READY; audit test success is not experiment readiness. Retained packet-only workspaces under `output/producer_coverage_amendment_v1` support the procedural isolation check. Committed `inputs/` and primary/adjudication evidence bind the actual review inputs and outputs. Do not rerun review agents or one-time freeze/comparison stages.

Only `machine_adjudicated_producer_candidates_v1/` is the separate producer candidate namespace. It contains no admin maps or authored diagnostics. DEV is validation, not optimization data. No balanced execution manifests are issued for this failed readiness attempt.
