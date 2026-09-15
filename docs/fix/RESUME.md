# First tuning experiment review preparation - 15 September 2026

**FIRST_TUNING_EXPERIMENT_REVIEW_PENDING**.
Implementation: `4d7645da2d4d896b6657f09ce5ba2b84d209e6d8`.
See [FIRST_TUNING_EXPERIMENT_REVIEW_PREPARATION.md](FIRST_TUNING_EXPERIMENT_REVIEW_PREPARATION.md)
and [administrative submission instructions](../../benchmark/first_tuning_experiment_v1/ADMIN_SUBMISSION.md).

New frozen `first-tuning-experiment-v1`: 27 numeric thresholds plus derived R07;
all six catastrophic zero limits unchanged. Selected 192 unique packets (96/96),
all 72 held-out examples, ten domains, 16 templates, maximum 80 document families,
114 unseen-template examples. Selected 48 second reviews (24/24; 48 families).
Two blank packet-only ZIPs are ready. Never distribute admin mappings or labels.

115 checks pass; six effect proofs; one existing optional skip. 482 files and 482
archive members scanned, zero leakage/credential/privacy findings. Frozen v1/v2,
106 historical evidence entries and four historical rejections preserved.
Actual reviews 0/192 and 0/48; zero eligible training labels. Collect independent
human reviews and adjudicate disagreements, then rebuild coverage. Do not require
all 736 reviews for this first gate. Final acceptance still requires independent
sealed material and external ACL; first review readiness does not.
No cloud, paid API, model generation, training, LoRA/SFT, model/revision/quantization
change, full pipeline, multi-round or push. User-owned root handoff/durable untouched.

---

# Domain-agnostic benchmark hardening implemented - 15 September 2026

**DOMAIN_AGNOSTIC_TRAINING_EXPERIMENT_NOT_READY**.
Implementation: `fee042af676e2818ec6f7a7589deff0950e1f4fe`.
Read [DOMAIN_AGNOSTIC_TUNING_BENCHMARK_HARDENING.md](DOMAIN_AGNOSTIC_TUNING_BENCHMARK_HARDENING.md)
and [the v2 workflow README](../../benchmark/task_semantics_v2/README.md).

New dataset/evaluation version `semantic-benchmark-v2`; production contract remains
`semantic-task-v1`. All 30 v1 baseline-reference files and 106 historical A/B evidence
entries verify unchanged. The expansion adds 288 rows and references 448 preserved
rows: 736 total, 288 producer / 448 auditor, ten domains, 80 document families,
16 versioned structural template families (12 new). Train/dev/test/public adversarial
are 184 each. Tuning access is 368 rows; astronomy/ecology holdout is 72; unseen-template
test/adversarial is 368. There are 96 new substantive producer cases.

736 blinded JSON/Markdown packets ready, ZERO independent reviews, 736 pending,
zero actual disagreements/final adjudications, ZERO genuinely blind examples populated.
The new submission/resolution journal leaves authored labels frozen. Public adversarial
material remains public. The sealed vault requires independent contribution plus an
external operator-controlled account/ACL; application checks do not supply OS isolation.

35 new + 42 preserved dataset tests + 85 production checks pass (162; one pre-existing
optional skip). Ten total effect proofs. All 736 gold outcomes pass, all 1,008 negative
candidates are rejected (576 old + 432 compound). Four historical failures reproduce.
Zero detected leakage; credentials scanned clean. Evidence:
[domain_agnostic_hardening_20260915](domain_agnostic_hardening_20260915/).

Next: independent humans review the packet-only export; register and implement the
27 unresolved quantitative acceptance rules prospectively; commission independently
held final material in the protected external vault. Six zero catastrophic limits are
frozen now. Do NOT train or treat pending review as approval. No cloud, paid API,
training, LoRA/SFT, model/revision/quantization change, full pipeline, multi-round or push.
Root SHIMMER_HANDOFF.md and durable/ remain user-owned and untouched.

---

# Domain-agnostic task dataset implemented - 15 September 2026

**DOMAIN_AGNOSTIC_TUNING_DATA_READY** (infrastructure/seed readiness; no training authorization).
Implementation: `090b3d50129a71a6ad9bfe703464ea8120b17d91`.
Read [DOMAIN_AGNOSTIC_TUNING_DATASET.md](DOMAIN_AGNOSTIC_TUNING_DATASET.md) and
[benchmark/task_semantics/README.md](../../benchmark/task_semantics/README.md).

Frozen `semantic-task-v1`: live compact adapters/production validators unchanged.
448 authored examples: 96 producer / 352 auditor; eight balanced domains, 32 document
families, four template families; train/dev/test/adversarial 112 each. 64 refusals.
576 negative candidates across 18 transformations all rejected; 448 gold outcomes pass.
42 new tests + 85 existing production checks pass, one pre-existing optional skip;
seven total effect proofs. Four historical model rejections reproduced; all 106
historical artifact hashes unchanged. Zero leakage findings or similarity warnings.

The seed is single-authored English, with only four independent template groups.
Its adversarial partition is PUBLIC, not a blind final test. No model-quality claim.
Next: independent adjudication, more producer/template families, independently held
final/adversarial material and prospective acceptance criteria; only then a separately
authorized bounded task-tuning experiment. Do not start training from this handoff.

No cloud, paid API, training, LoRA/SFT, model/revision/quantization change, full pipeline,
multi-round or push. User-owned root handoff and durable state remain untouched.
Evidence: [domain_agnostic_tuning_20260915](domain_agnostic_tuning_20260915/).

---

# Remote contract model A/B complete ? 15 September 2026

**REMOTE_CONTRACT_MODEL_AB_FAIL**
**DOMAIN_AGNOSTIC_TUNING_RECOMMENDED=true ? producer and auditor.**
Read [REMOTE_CONTRACT_MODEL_AB.md](REMOTE_CONTRACT_MODEL_AB.md) and
[DOMAIN_AGNOSTIC_TASK_TUNING_DESIGN.md](DOMAIN_AGNOSTIC_TASK_TUNING_DESIGN.md).

Tested source `54df6a48e8646cf721d6d2e2f2ecb60125a92bef`, after local readiness
`1991060` / `9f2b275`. Four deterministic calls, unchanged models/revisions,
seed 7, 384 tokens and 25 seconds. 224 local checks, four compact mutation proofs,
and two tokenizer profiles passed before launch; one optional directory skip.

One A10 in us-east-1 at $1.29/h. OLD/NEW producer: 610/333 input tokens,
259/84 output tokens, 12.423/3.973 s. OLD/NEW auditor: 1875/488 input tokens,
384/350 output tokens, 18.176/16.325 s. Exact old/new prompt hashes matched.
All four responses contract-invalid and semantically unaccepted. One truncation
(OLD auditor); both NEW calls reached EOS. NEW producer emits one correct alias,
both claims and refs but omits the missing-date gap, sets empty despite claims,
and uses fences. NEW auditor emits MATCH and both refs with no invented rule,
but adds trailing prose and partly misattributes original missing information to
extraction loss. Correct judgment alone is not correct reasoning or acceptance.

Serial handoff was NOT admitted. No resampling or source/prompt revision on the
paid instance. No concurrency, serving migration, full pipeline, full benchmark,
multi-round, paid inference API or training. Each model loaded once; both resident,
no offload/reload/swap. Peak 10315/23028 MiB VRAM; active GPU median 42%.

Provider termination confirmed 10:52:20.890272 UTC. Independent final query at
10:53:04.306875 UTC: experiment absent, zero active account instances. SSH
registration/key pair removed. Billable upper bound 576.878 s / $0.20671457.
Security scan: 107 files and 183 archive members, zero credential hits and zero
sensitive provider fields. Evidence: contract_model_ab_20260915/; source/evidence
archives verified; ARTIFACT_HASHES.json indexes retained artifacts. No push.

The closed secure feasibility stage and deterministic local readiness remain
historical evidence. Do not reopen infrastructure/hardware work or enter another
prompt loop. Next recommended task is domain-diverse, grouped, held-out task-data
and evaluation design/curation, with frozen compact/refusal contracts, hard negatives,
evidence precision/recall, reason correctness, calibration and governance gates.
The attached design does not authorize training, another instance or a model change.
Cloud authorization for this experiment is consumed. Preserve operator-owned
SHIMMER_HANDOFF.md and durable/; the operator pushes.

## Prior local deterministic handoff (superseded by real-model measurement)

# Compact extraction + auditor contract A/B complete ? local only

**REMOTE_CONTRACT_AB_READY** (deterministic readiness, not measured model reliability).
Read [COMPACT_CONTRACT_AB.md](COMPACT_CONTRACT_AB.md).
Implementation/evidence: `19910604c00b7d132ae04cad492a8320dd6a73c3`.

The secure remote feasibility stage stays CLOSED / CLOUD_FULL_RUN_NOT_ELIGIBLE.
Do not reopen infrastructure/security/runtime/hardware work. No cloud is authorized
by this local follow-up. No full pipeline, multi-round, paid API, model/pin change,
quantization change, serving/concurrency optimization, ceiling increase or push.

Exact old rendered hashes and counts reproduced: producer 610, source-copy 482,
auditor 1875. The auditor is LlamaConfig/LlamaForCausalLM with Phi-style chat markers
at the unchanged configured Phi repository/revision. No local weights were loaded.

Scoped compact producer removes copied source/duplicate alias fields; Python uses
the existing ledger to reconstruct exactly. Scoped fidelity auditor compares original
with extraction, carries no invented numeric rule, and requires both selected refs.
Complete JSON precedes strict canonical validation; truncated prefixes stay invalid.
Normal Finding-record governance and unbound agent contracts remain unchanged.

Tokens (old ? new): producer prompt 610 ? 333, authored valid output 101 ? 59;
auditor prompt 1875 ? 488, authored valid output 107 ? 71. These are tokenizer
capacity measurements, not successful generated responses. MATCH reason, both refs,
missing-date question and exact source reconstruction pass authored fixtures.

Validation: 85 checks + 4 mutation/effect proofs + 2 pinned-tokenizer profiles pass.
One pre-existing optional-directory coverage skip (prompts/snapshots absent).
New evidence: compact_contract_ab/; zero credential hits in 23 scanned artifacts,
24 hash-manifest entries. Source and artifact integrity verified. Operator-owned
SHIMMER_HANDOFF.md and durable/ remain untouched. No push.

Next, only with separate authorization: bounded old/new producer and auditor A/B at
384 tokens / 25 seconds, measure actual semantic correctness, evidence, EOS/truncation,
latency and accepted producer ? independent auditor serial path. Human reason
adjudication remains required; nonempty reason is not semantic correctness. The
checkpoint's turn-end marker differs from its configured EOS: retain terminal-token
evidence rather than changing stop policy speculatively. No concurrency work yet.

## Previous secure feasibility handoff (closed stage)

# Ordinary remote feasibility measurement complete ? 2026-09-15

CLOUD_FULL_RUN_NOT_ELIGIBLE. Read REMOTE_SHORT_BURST_SECURE_FEASIBILITY.md.
The open remote ordinary short-burst measurement is complete with real negative
quality/performance evidence; this was not another preparation-only attempt.

Security/controller fixes: 6308374 and c342033. Executed source c342033.
135 local checks passed before launch. Raw provider metadata now crosses only
explicit allowlists, including the formerly raw public request() interface.
Post-run commit 545ca1d projects pip reports to package names/versions only.

One A10 in us-east-1 at $1.29/h; Python 3.12.3; Torch 2.5.1+cu121; Transformers 4.52.3.
165-file source bundle: 1,268,892 bytes / 3.846s. Runtime, source and dependency
gates passed before acquisition. Four real calls; one truncation; one structural
contract-valid reference output; zero semantic acceptance. Compact producer
12.365s / 259 tokens / 20.971 tok/s: ignored alias reconstruction and missing date.
Auditor 18.140 s / 384 tokens / 21.176 tok/s: truncated, wrong comparison, ungrounded
rule. Serial handoff and concurrency2/4 correctly not admitted after quality failure.
Both models resident, each loaded once, no CPU offload; VRAM peak 10,375/23,028 MiB.

Termination verified 09:29:29.821609 UTC; second safe query zero active instances.
Upper bound 507.125 s / $0.181719681. Temporary SSH registration and keys removed.
Safe evidence in remote_short_burst_secure_20260915/; no account/provider secret
exposure. Artifact sweep zero credential/auth-field hits. Historical evidence
and operator-owned SHIMMER_HANDOFF.md/durable untouched. No push.

Next task: local deterministic fixture work, then a narrowly scoped compact
extraction/auditor prompt-contract A/B at unchanged model pins and ceilings.
Require alias hydration, missing-information completeness, correct MATCH task,
reasoning and both references. Preserve observed auditor model_type=llama for
the configured Phi repository; do not relabel it. No serving migration yet.
No full pipeline, multi-round or paid inference API authorized. Any new cloud
measurement requires separate authorization; do not provision another instance.

## Previous handoff context

# Remote retry stopped and terminated, 2026-09-15

Latest result: CLOUD_FULL_RUN_INDETERMINATE. Read REMOTE_SHORT_BURST_RETRY.md.

One explicitly authorized Lambda A10 (c981f11ebc5849928826f716f72c6149) was launched
with Lambda Stack 24.04 at $1.29/hour. SSH readiness did not complete. No source
transfer, remote runtime gate, model download/load, or inference occurred.
Raw provider metadata accidentally exposed a temporary Jupyter access token.
Emergency termination was verified at 08:55:04.019863 UTC; second provider query
found zero active instances. Cost upper bound $0.1348098731 / 376.213599 seconds.
The operator authorized redaction and reporting, explicitly without a new instance.
Local redaction is verified; temporary SSH registration/key pair removed.

Local source fix d3ebb06 persists stage evidence and the hard pre-inference
checkpoint. 26 runtime tests and 83 cloud tests passed. New report/evidence live
in REMOTE_SHORT_BURST_RETRY.md and remote_short_burst_retry_20260915/.
The preserved controller_executed.txt is incident evidence, not a retry launcher.
Before another separately approved bounded cloud experiment, enforce the existing
safe_metadata allowlist before all provider-data persistence/display and test it.
Do not infer cloud eligibility or run the full pipeline. No second instance,
full pipeline, multi-round, paid inference API, or push. Historical evidence and
operator-owned SHIMMER_HANDOFF.md/durable are unchanged.

## Prior runtime-hardening handoff (preserved context)

# Remote runtime contract hardening, 2026-09-15

Read this file first and continue without asking. Do not push.

Closed the preparation defect behind the bounded remote attempt at 253cc7b.
Authoritative runtime: tools/cloud_run/runtime.json. Source compatibility is
>=3.12,<3.13; the sealed reference intentionally retains exact Python 3.12.3.
Runtime resolution records a compatible absolute executable. Source integrity,
actual compilation and critical imports precede dependency installation and
model acquisition. Existing package mismatches fail without automatic upgrades.
The Docker source-preflight stage is a prerequisite of package/model layers.
No image was rebuilt and no package/environment installation was performed.

Maintained bounded entry: tools/prepare_remote_experiment.py. Its default is
readiness checks only; --execute requires separate authorization. Historical
output/remote_short_burst_20260915 and docs/fix/remote_short_burst_20260915 scripts
remain evidence, not launch targets. Do not use their default-Python setup script.
See REMOTE_RUNTIME_HARDENING.md and runtime_hardening_20260915/ for evidence.

Validation: 148 unit tests passed (25 runtime, 83 cloud preparation/controller,
8 transport, 7 transfer, 17 recommendation/source-layer, 8 local-runtime tests).
Two runtime/source guard neutralisations fail as expected and restore. Real
Python 3.12.3 compiled 145 files and imported nine critical modules without a
model stack. Startup-readiness and shell syntax checks passed. Desktop session,
selection, GUI/mutations, port lifetime and real batch entry passed; the broader
live-server fixture is blocked because compatible local Python lacks fastapi.
Its child exited and was collected. No dependency repair was attempted.

Historical result remains CLOUD_FULL_RUN_INDETERMINATE. All 32 historical hashes
match. No model inference evidence or missing projection field was fabricated.
Instance 95bbd0c1a9e64361b80c0ff8011b84a3 was provider-confirmed absent at
2026-09-15T07:17:18.016016+00:00 in the previous task, with conservative instance
cost upper bound $0.1219585353. This task made no provider/cloud/SSH/SCP calls.
No model load, full pipeline, multi-round or paid inference API; no push.
Existing untracked SHIMMER_HANDOFF.md and durable/ were preserved.

Next task: repeat the remote short-burst feasibility measurement only after
separate operator cloud approval, using a prepared compatible runtime and the
maintained source/runtime gates. Do not initiate that retry from this handoff.
