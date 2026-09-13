# Shimmer operator runbook

This guide describes the current desktop/console path. See the
[README](../README.md) for exact API routes, environment variables, agent routing,
measured limitations and image status. The [routing audit](fix/ROUTING_UI_AUDIT.md)
records the source trace and verification. Earlier runbook instructions remain in
the [historical archive](history/RUNBOOK_PRE_ROUTING_AUDIT.md).

## Start Shimmer

Run `start_shimmer.bat` from the configured Windows checkout. Keep the desktop
starter open: it owns the local server and provides Stop. It selects the configured
Python environment and checks packages, cached model assets and the requested
backend/privacy posture before starting. Its readiness report is a prerequisite
check, not a generated review or a quality test.

Choose Local for the installed local Review models, or Cloud for configured
provider-backed review. Cloud can incur provider charges. A backend badge in the
browser describes the current server; it does not reconstruct a past run's model.
The server does not accept a different backend for each submission. Restart it
through the starter to change the backend.

If readiness fails, read its named missing prerequisite. Correct that installation
or configuration issue before retrying; repeated Start does not install packages
or download weights. Do not substitute an empty cache directory for real model
files. Local needs the configured Qwen, Phi and bge-m3 assets and their compatible
runtime. The pinned container has separate weight-format requirements. CPU-only
local review is not certified by a successful package check.

The starter opens `/console` and offers Copy token. Paste the token into the
console's access field. It is held in that browser session and sent in the
Authorization header. Never place it in a URL, log, screenshot, repository or
shared document. An expired or replaced server session can require reconnecting
with its new token. `/health` needs no token and proves only server liveness and
declared posture. It cannot diagnose model generation or certify readiness.

## Choose the task, privacy and document roles

**Review** evaluates supplied targets against the provided grounding and
conventions. Add files, mark the documents to review, and identify any prior
versions separately. A prior version supplies comparison evidence and is not
itself a new target. Other files can be grounding/reference material. Check the
filename selections before confirming. Do not use a prior version as a target
merely to make it visible; ambiguous overlaps do not create a valid comparison.

Explicit target selection overrides the normal date-cutoff path. Otherwise an
undated document can be excluded; inspect the Undated documents section for the
recorded exclusion and the selected roles. Inference of document roles is a
guarded stub, not an automatic semantic classifier.

**Draft** requires a question. Its first memo is generated through a direct Claude
path and then reviewed. **Local Draft is unsupported.** The console warns about
this limitation; selecting Local does not turn the Draft memo into a local call.
Use the supported Cloud path only when provider use is intended and configured.

**Normal** declares the input non-sensitive and records the no-redaction/inactive
layer overrides. It reviews full content; it does not automatically determine
whether that content should have been called sensitive. **Sensitive** requires
available, active sensitivity protection. The shipped layer is inactive, so the
native submission path refuses that choice. Do not treat a Normal run or an
available ZIP as proof of safe Sensitive handling.

Choose paired or wide review if needed. Local defaults to paired; Cloud defaults
to wide. Paired review combines supported deterministic comparisons with model
questions; wide asks convention reviewers over the document. The default routing
profile is dense/reference. The API/console does not select sparse per submission;
the explicit CLI sparse profile currently preserves the same conservative firing
policy and has no accepted new suppression rule.

Read the confirmation summary and confirm before submitting. Native intake
requires explicit task/privacy/confirmation, validates filenames and target/prior
arrays, and refuses conflicting existing files or unsupported conventions. A
202/queued response is acceptance into the queue, not successful execution or
approval of a governed change. One server job runs at a time.

## Follow the run

Open the run from Runs. Progress names the last reported phase/agent/document;
it is not a completeness percentage or a reliable remaining-time promise.
Local generation can take a long time. The saved synthetic baseline took
84m 14.4s; that is one run, not an estimate for your documents.

| Display/state | Meaning and next action |
|---|---|
| Waiting to start | Queued. No model execution is implied. |
| In progress | Child process running; inspect progress, findings already written and the log. |
| Paused: needs your decision | Read the pending governed question and rationale. Approval records your answer; the pipeline determines its effect. If the question is missing, inspect the log before answering. |
| Process finished | Server observed successful exit. Inspect completion, refusals, coverage and source citations; it does not mean every agent succeeded or every defect was found. |
| Stopped on purpose | Governance stop, with recorded reason. Correct the stated issue; do not assume a crash. |
| Stopped by a system fault / timeout / cancelled | Incomplete execution. Existing findings/files may still be available and are partial. |
| Unknown / not recorded / unavailable | Evidence is absent or invalid. Do not translate it into success, zero work or a clean review. |

Agent activity shows the profile recorded by that run, dispatch attempts, explicit
non-calls, unreached agents, failures, recovered replies and capped replies.
Counts describe an evidence snapshot. A dispatch attempt can fail before usable
generation. Recovered output passed a parser/contract path, not a reasoning test.
A capped reply can omit work. Developer view adds each agent's latest state,
individual reasons, trigger and bounded additional calls. Assignment's idle-agent
list describes rule matching, not actual activation. Missing activation artifacts
in old runs are reported as unavailable instead of invented zeroes.

Pipeline completion is read separately from process status. `completed` means the
pipeline recorded reaching its end; an interrupted run may leave a `running`
record. Neither certifies quality. Editorial observations are advisory; a concern
does not itself block delivery. Redaction NONE, APPLIED, SKIPPED, BLOCKED and
HELD_WARNING have different meanings. A held format warning is not a clean pass.

## Findings, citations, outputs and logs

Findings and pairing information can be visible before successful completion.
Read amendment refusals, contract failures, unjudged rules and unknown coverage
alongside findings. Empty sections do not prove nothing was missed. Developer
view exposes more technical evidence without making it a new quality score.

Click a REF citation to see the excerpt in this run's reference index. A missing
ID is shown as not recorded. WEB-REF labels are currently text only in the console.
Clicking a rule shows the **current registry's** text, explicitly labeled as
potentially different from the rule used by the run. For historical investigations,
read the run's saved excerpts and bus evidence; a run-scoped rule snapshot is not
served. Full absence, band-condition and prior-comparison detail may require the
on-disk pairing map rather than the simplified API projection.

Outputs live in `output/runs/<run folder>/` (or the configured server output root).
Server folders use the run ID; CLI folders can gain a readable date/label while
retaining `audit/run_identity.json`. In `deliverables/<doc_id>/`, `review_data.json`
is the amendment master, `review_findings.md` and `tracked_changes.docx` are its
renders, and summaries plus `reviewed_document.md` provide supporting views.
Draft also preserves `memo.md`; `_run_summary.md` indexes the run's deliverables.

Whole-run and per-document downloads contain files already present. Document
"done" means its folder contains a file; it is not a stage-completion or privacy
certificate. The whole-run ZIP marks partial based on server outcome. A successful
exit can still have deficient coverage. A per-document ZIP does not carry that
whole-run partial flag. Download access is not separately gated on privacy release.

The console log panel reads `logs/pipeline_stdout.log` for server runs. Raw bus,
cost and call evidence live in `logs/`; reference index, pairing/assignment,
activation, editorial evidence, audit synthesis and completion live in `audit/`.
Direct CLI stdout is not automatically that server log. Keep the terminal capture
when using advanced entry points.

## Stop, interruption and rerun

Cancel a queued or running job from the console. It stops the job and preserves
saved run evidence. Use the desktop starter's Stop to stop its owned server and
children. Closing the browser alone leaves them running. There is no HTTP server
shutdown endpoint. Do not kill unrelated Python processes.

After interruption, inspect the run's state, stop reason, completion record and
log. Server restart reconstructs saved run resources and marks interrupted jobs;
it does not resume generation in the middle of a phase. Temporary upload staging
may have been cleaned, and native cleanup may have removed unchanged files it
created under input. Keep the originals and resupply files for a new submission.
Do not assume the old upload can be replayed from server state alone.

Rerunning is a new run with a new identity, not an idempotent continuation. It may
produce different sampled output and update durable state. First fix the cause
of refusal/failure, check roles and ensure conflicting native files are resolved
deliberately. Do not delete operator input or alter governance to force a rerun.
Governed decisions already recorded require their own meaning to be inspected,
not copied blindly into another run.

## Preserve and back up state

Keep operator source files, conventions, role manifests, `durable/`,
`ontology/stores/`, governance/config files and prior run evidence. Deleting a
run does not delete durable learned state or ontology records. Do not describe
all ignored files as regenerable: sampled results and operator decisions cannot
be recreated by rebuilding source.

`scripts/backup_state.py --dest <backup-directory>` copies `durable/`,
`ontology/stores/` and three configs (`constitution.json`, `agent_registry.json`,
`pricing.json`) with a hash manifest. `--verify <backup-folder>` checks that
manifest. It does **not** back up all operator input, conventions, run evidence,
model caches or other configuration. Preserve those separately when needed.
There is no automatic restore command. Stop writers, verify the backup, retain
the current state and review any proposed config replacement before a deliberate
restore. Restoring an older constitution can undo governed amendments.

Reset/snapshot tools distinguish usage-derived state from protected global and
governance categories. Do not use reset as routine cleanup or as a substitute for
understanding a failed run. Consult `scripts/durable_paths.py` and the governed
snapshot/reset flow before a separately authorized reset.

## Advanced API, checks and unsupported boundaries

Use the [current route table](../README.md#api-and-developer-entry-points).
Native API requests must explicitly select `intake_mode=standalone`, privacy and
confirmation. Omitting intake mode keeps the older sidecar ingestion validator;
setting a standalone server mode alone does not select native intake. Direct
server defaults bind all interfaces; the normal desktop path selects loopback.
No tunnel or remote setup is part of ordinary startup.

The offline host gate is `py -3.9 -B -X utf8 scripts/verify_session1.py --offline`.
Read PASS/WARN/SKIP/FAIL counts and named limitations, not just exit status.
Offline skips and missing corpus/input evidence do not become passes. Some gate
checks load cached models; do not overlap them with another GPU workload. The
[current verification record](../README.md#verification-status) distinguishes
host, unmounted image and focused console checks. No online gate was run for this
audit. The secret guard and staged review remain required before a commit.

Unsupported/unproven here: Local Draft; usable Sensitive review with the shipped
inactive layer; complete semantic coverage; historical rule reconstruction through
the rule endpoint; general sparse speedup; ontology/GNN feedback into agent tasks;
automatic resume; private-document quality; fresh-clone startup; and a complete
review inside the unmounted image. Fresh-clone and deployment work belong to later
locked roadmap items.
