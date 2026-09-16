# Second tuning experiment implementation

`SECOND_TUNING_EXPERIMENT_DESIGN_READY`

This is a local design/dry-run release. Training remains unauthorized and has not run. See [the quantitative audit](SECOND_TUNING_DATA_AND_FAILURE_AUDIT.md) for exact counts, failure taxonomy, token proportions and limitations.

## Files and responsibilities

- `author.py`: new semantic plans and explicit provenance; no legacy/protected data input. The 40 Producer calibration rows do not count toward substantive expansion.
- `audit_run1.py`: immutable TRAIN/DEV-only failure and token audit, with read-input hashes.
- `release.py`: group-first authoring, deterministic canonical/five-fold membership, tokenizer measurement, exact role configuration and release freeze.
- `runtime.py`: stable ontology/contract reuse, explicit multi-span ownership, target-only encoding, metrics, fail-closed leakage and semantic gates.
- `runner.py`: verified canonical/fold schedules. Its only CLI mode is `--dry-run`.
- `train.py`: future local executor requiring separate operator authorization bound to one role, one split and the exact release hash. No provider client, download, protected evaluator, resume or automatic retry. Never called during this task.
- `collect_cv.py`: verify future run bindings and raw validation evidence, recompute scores and aggregate both fixed checkpoints over all five folds. No result exists yet.
- `dry_run.py`: irreversible process audit hook blocks benchmark target reads, model weights, subprocesses and networking; metadata-only contamination checks, full tokenizer checks, metric fixtures and fault injection.
- `report.py`: quantitative documentation from saved evidence.

Frozen inputs are `dataset.json`, `splits.json`, `selection_rules.json`, role `experiment.json` files and `review_adjudication.json`. `freeze.json` binds the release and frozen reused code/config dependencies. Runtime evidence and fixture evidence are distinct. Earlier review rounds are retained as review provenance, not alternative training corpora.

## Reproduce no-model verification

From repository root, using the local interpreter with Transformers 4.51.3/tokenizers 0.21.1:

```text
python -B tuning/second_domain_agnostic_v2/dry_run.py
python -B tuning/second_domain_agnostic_v2/runner.py --role producer --split canonical --dry-run
python -B tuning/second_domain_agnostic_v2/runner.py --role auditor --split 0 --dry-run
```

Splits `0` through `4` each use 240 TRAIN/60 validation rows per role; `canonical` is the already-frozen fold-0 membership. Every schedule contains two deterministic passes, 120 optimizer updates and validation at 60/120. All role configurations are identical across folds. Each role/fold has a separate future output directory; validation IDs cannot enter its optimizer schedule. CV is upstream robustness assessment and cannot change the canonical split or hyperparameters.

The optional rebuild commands (`audit_run1.py`, `release.py`, `report.py`, `release.py --freeze`) create a new local design artifact and are not training commands. Do not rebuild a release after model results to silently alter selection rules. Any substantive change requires a new reviewed release.

## Execution boundary and validation

No authorization file was created, and `train.py` was not run. Future execution requires the pinned Linux/Python/CUDA/dependency environment, local pinned model assets, an exact role/split/release permit, and a fresh run directory. Weight hashes are checked only after that future authorization. The current dry-run reads tokenizers/configuration, never weights. Executable model integration remains untested; design readiness does not establish runtime feasibility or semantic success.

All 600 targets pass the frozen role contracts; all 300 Producer labels pass the canonical renderer. Every fold passes grouped isolation, exact-once validation and class/domain checks. Fourteen deliberate leakage/access faults are rejected. Perfect-target, all-refusal, malformed-output and nonfinite-metric fixtures exercise the semantic gates; none is presented as a model result. Final input-only reviews cover all 600 packets with zero unresolved content-label disagreements, and human review remains zero.

Five structural superfamilies are the effective held-out groups, despite 600 document IDs and 20 rendering layouts. This synthetic compositional corpus has limited language diversity. Protected contamination checking uses existing metadata/fingerprints and provenance; it does not open protected text for similarity comparisons. The existing protected one-shot receipt is unconsumed and R06 controls are unchanged.

Future CV reports both fixed checkpoints, full per-fold metrics and separate aggregate distributions. No single composite score hides class collapse. Canonical candidate selection uses only canonical DEV and the prospective gates. No automatic protected evaluation follows selection.
