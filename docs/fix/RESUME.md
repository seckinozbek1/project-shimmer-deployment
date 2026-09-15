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
