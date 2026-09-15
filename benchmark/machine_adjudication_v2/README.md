# Machine agent review V2

Status: **AGENT_ADJUDICATED_TUNING_EXPERIMENT_READY** under registered M01?M07 and the pre-review pool definition. Human review remains PENDING; training is not authorized.

- Method registration: `9b0086e4a463cc40e90507d65f041385fee43fa1`.
- Committed pre-gold labels: `b22c8566a16e0930a3ccb8cf941e3b0fc689cb8d`.
- 576 fresh primaries; 576 valid; zero repairs; 56 fresh adjudications.
- Separate eligible namespace: `machine_adjudicated_training_access_v2/` (58 TRAIN, 24 DEV). DEV is validation, not optimization data. Evaluation/admin records outside this folder remain inaccessible to future tuning.
- The pool has 12 producer TRAIN but no producer DEV; this readiness does not authorize or establish suitability of a producer tuning experiment.
- Authored diagnostics retain 36 excluded TRAIN/DEV disputes; no post-gold changes to frozen atoms or projection.

Run local validation from repository root:

```powershell
& 'C:\Users\secki\anaconda3\python.exe' benchmark/machine_adjudication_v2/gate.py
```

The audit gate requires the retained `output/machine_review_v2/reviewer_A/B/C/packets` workspaces to check exact original inputs and procedural isolation. Their packet hashes and the source export hash are preserved in `blind_evidence/isolation_manifest.json`; active cohort exports remain maintained separately. The committed primary/adjudication evidence is authoritative. Do not rerun reviewers or overwrite their files to reproduce diagnostics. `pipeline.py collect/freeze` and `compare.py` are one-time stages with exclusive evidence writes, not update commands.

Read `docs/fix/AGENT_ADJUDICATED_TUNING_REVIEW_V2.md` for results, limitations, chronology and next steps. V1 files remain immutable.
