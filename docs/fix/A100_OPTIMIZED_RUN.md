# Optimized A100 experiment, 14 September 2026

One model run completed and its evidence was recovered after the original SSH
connection stalled. The automated controller remains **ABORTED / NON-BENCHMARK**;
recovery does not promote it to a clean benchmark. All 40 hashed evidence files
were verified within the 41-file collection, saved-artifact scoring was reproduced
locally, and provider termination was verified. Estimated cost was **$2.20** at
the operator-supplied $1.99/hour, below the $5 target and $10 ceiling. This estimate
spans first observed active state through verified termination, not an invoice.

## Measurements

| Measurement | Preserved A100 baseline | Recovered optimized run |
|---|---:|---:|
| Cold wall | 1,958 s | 2,413.046 s |
| Generation time | 1,920.789 s | 2,378.756 s |
| Model calls | 20 | 20 |
| Median GPU utilization | 41% | 40% |
| Sampled peak GPU memory | 8.23 GiB | 12.86 GiB |
| Calls reaching token cap | 5 | 18 |
| Contract-refused tasks | 2 | 4 |
| Amendments | 3 | 3 |
| Location recall | 3/5 | 3/5 |
| False positives / distractor hits | 0 / 0 | 0 / 0 |

There was no measured speedup. Observer wall increased by 455.046 seconds (23.24%)
relative to the preserved 1,958-second baseline. The baseline observer clock was
1,956.350 seconds; comparing observer clocks gives the same conclusion. Native
pipeline wall for the recovered run was 2,408.265 seconds. These run timings
exclude deployment, downloads, scoring, collection and teardown.

DAG mode used one CUDA worker with two resident models. Maximum concurrent calls
was **1**, and the semantic critical path traversed all 20 tasks with 2,384.658
seconds of service time. Generation occupied 98.58% of observer wall. Worker idle
time was 23.254 seconds; scheduler wait was zero, dependency wait 0.003 seconds and
barrier wait zero. Overlapping task measurements do not imply concurrent GPU work.

All 20 backend calls returned, but only 16 task outputs were accepted. ARCHIVIST,
VERIFIER, FACT_CHECKER and EDITOR_CLERK had contract-refused outputs. Eighteen calls
hit their token caps. Matching amendment and recall counts does not establish
reason correctness or broad quality equivalence.

First generation began 1,213.562 seconds (20m 14s) after first observed active state.
SSH readiness took 17.216 seconds. Transfer, integrity checks and dependency
installation took 1,122.506 seconds; model hydration took 44.995 seconds. The
5.30 GB local upload dominated setup. Short paid preparation time was not achieved
on this connection.

## Reproducibility and evidence boundary

The source commit was `15d0721fbc24cd38fdaa6bc4969d7b18ad66387e`. The run selected
dependency DAG, Agent Execution Briefs, automatic input language, English output,
inactive multi-round mode and the sealed model revisions and generation limits.
Only one model run started. The completed baseline was preserved.

The consumed experiment ID is `a100_optimized_retry_20260914`. Its bundle is local
under `output/cloud_ready/`; collection is under
`output/cloud_collected/a100_optimized_retry_20260914/`. These ignored artifacts
are retained operator evidence and are not included in the source repository.

| Local artifact | Purpose |
|---|---|
| `recovered/evidence/` | Recovered run, observer, scheduler and scoring evidence. |
| `RECOVERY_COLLECTION_VERIFIED.json` | Collection integrity verification. |
| `RECOVERED_RUN_SUMMARY.json` | Machine-readable recovered result. |
| `RECOVERED_RUN_REPORT.md` | Detailed local recovery account. |
| `EXPERIMENT_STATUS.json` | Original aborted controller outcome, preserved. |
| `TERMINATION_VERIFIED.json` | Provider-confirmed teardown at 18:39:53.368121 UTC. |
| `output/cloud_prep_audit/retry_quality_assessment.json` | Separate local assessment of accepted outputs, caps and quality limitations. |

The last row is relative to the repository; other rows are relative to the
collection directory. Missing local evidence must not be interpreted as a passing
check on another checkout.

After recovery, explicit SSH/SCP connection and keepalive limits were added.
They detect dead peers but do not guarantee recovery from every stuck channel.
The original bundle and controller evidence remain immutable. See the
[preparation guide](../CLOUD_RUN_PREPARATION.md) for the maintained workflow.
