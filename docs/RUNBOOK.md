# Shimmer runbook

Operational procedures for running Project Shimmer: install, launch, submit,
watch, approve, diagnose, back up, restore. Written for the operator at the
keyboard, not for a reader learning the architecture (that is `README.md`) and
not for an agent changing the code (that is `CLAUDE.md`).

Every command below is written for Windows PowerShell or `cmd`, which is where
this deployment runs. On macOS or Linux use the `.sh` launcher and forward
slashes; nothing else changes.

Contents:

1. [Install](#1-install)
2. [Launch](#2-launch)
3. [Submit a run](#3-submit-a-run)
4. [Watch a run](#4-watch-a-run)
5. [Approve a governed decision](#5-approve-a-governed-decision)
6. [What each status means](#6-what-each-status-means)
7. [When a run hangs](#7-when-a-run-hangs)
8. [When a run BLOCKs](#8-when-a-run-blocks)
9. [Reading cost_tracker.json](#9-reading-cost_trackerjson)
10. [Back up](#10-back-up)
11. [Restore from a backup](#11-restore-from-a-backup)
12. [The verify gate](#12-the-verify-gate)

---

## 1. Install

**Prerequisites.** Python 3.9 (the whole codebase targets it; `py -3.9` must
work), git, and roughly 8 GB of disk for the model caches. A CUDA GPU is
optional: the local Qwen redactor and the embedding store both run on CPU, just
slowly, and the OGE GNN warns rather than fails without one.

**One-time setup.**

```
git clone <repo> shimmer
cd shimmer
setup.bat                          # or: py -3.9 -m venv .venv
.venv\Scripts\activate
py -3.9 -m pip install -r requirements.txt
```

`requirements.txt` pins every dependency to an exact version, including the
FastAPI stack the server and more than twenty gate checks depend on. Do not
install unpinned; a drifting FastAPI version breaks the gate, not just the
server.

**API keys live OUTSIDE the repository.** Never inside it, never in a tracked
file, never in a shell history you keep. The loader looks in three places, in
order:

1. `$SHIMMER_CONFIG_PATH` (a path to the config module),
2. a sibling directory `../api_keys/config.py`,
3. the repo-root `.env_path` pointer file, which names the real location.

Only key VALUES are read, through a fixed allowlist. If the keys are not found,
every cloud agent degrades to "cannot verify / no key" and generation returns
nothing; the run does not silently produce empty deliverables, it reports the
failure per call in the cost log.

**Confirm the install** with the verify gate (section 12). A fresh clone should
reach `FAIL/ERROR=0`.

---

## 2. Launch

`shimmer.bat` is the master launcher: it bootstraps the venv, runs preflight,
and offers a menu.

```
shimmer.bat
```

| Option | What it does |
|---|---|
| `[1]` | Run a review (CLI). Asks Review (existing documents) or Draft (a memo from a question) |
| `[2]` | Open the chat interface (`scripts/chat.py`, tkinter) |
| `[3]` | Start the server (`scripts/server.py`, the token-gated dock) |
| `[4]` | Run the verify gate |
| `[5]` | Import documents: scan, classify, place, set the cutoff, no run |
| `Q` | Quit |

**Direct pipeline invocation** (what option 1 ends up running):

```
py -3.9 scripts\pipeline.py --non-interactive
py -3.9 scripts\pipeline.py --task draft --question "your question here"
```

**Starting the server by hand.** Mint a token and its hash ONCE, keep only the
hash in the environment, and hand the token to the collaborator out of band:

```
.venv\Scripts\activate
python -c "import secrets, hashlib; t=secrets.token_hex(32); print('Token:', t); print('Hash:', hashlib.sha256(t.encode()).hexdigest())"
set SHIMMER_TOKEN_HASH=<the hash>
python scripts\server.py
```

The server prints its resolved configuration to stderr on startup. Read that
line: it is the fastest way to catch a knob you thought you had set.

An external ASGI runner also works (`uvicorn scripts.server:app` from the
repository root), but note that it does NOT execute the `__main__` block, so it
skips the friendly "refusing to start without SHIMMER_TOKEN_HASH" message. The
auth boundary still fails closed: with no hash configured, every gated route
returns 401. Prefer `python scripts\server.py` so a missing hash tells you
immediately.

---

## 3. Submit a run

**From the console** (`GET /console` in a browser): paste the token once, choose
Review or Draft, attach files, tick or untick the sensitive checkbox, submit.

**From the command line.** On PowerShell use `curl.exe`, not the `curl` alias:

```
curl.exe -X POST http://localhost:8000/submit ^
  -H "Authorization: Bearer <token>" ^
  -F "task=review" ^
  -F "files=@C:\path\to\document.pdf" ^
  -F "files=@C:\path\to\_corpus_ingest.json"
```

A draft submission needs a question and no files:

```
curl.exe -X POST http://localhost:8000/submit ^
  -H "Authorization: Bearer <token>" ^
  -F "task=draft" -F "question=your question here"
```

`/submit` returns `202` and a `run_id`. Rejections are `400` and say why:
too many files (`SHIMMER_MAX_UPLOAD_FILES`), a file or submission over the size
caps (`SHIMMER_MAX_UPLOAD_MB`, `SHIMMER_MAX_UPLOAD_TOTAL_MB`), a draft with no
question, a review with no files, or a bundle the ingestion-contract validator
refused (the 400 body carries the violation report). Jobs run one at a time.

---

## 4. Watch a run

| Where | What it shows |
|---|---|
| `GET /status/{run_id}` | one job: status, timestamps, progress, error, exit code |
| `GET /queue` and `GET /runs` | the whole job list, rebuilt from disk at server start |
| `<run>/status.json` | the same record on disk, rewritten at every transition |
| `<run>/logs/pipeline_stdout.log` | the child pipeline's complete merged stdout and stderr, appended live |
| `py -3.9 scripts\bus_viewer.py --follow` | the live inter-agent bus and the per-call cost stream |
| the console's run list | the same `/runs` data, refreshed |

In the terminal, two line shapes matter:

- `[progress] phase=6/9 doc=1/2 agent=SYNTHESIZER status=running` is the machine
  -readable progress contract. The server and the chat interface parse it. Its
  format is fixed; do not reformat it.
- JSON lines such as
  `{"ts": "...", "level": "INFO", "run_id": "...", "phase": "6", "event": "phase_start phase=6 step=synthesis_deliverables"}`
  are the structured log. Grep them by `event`: `phase_start`, `phase_done`,
  `phase_skipped`, `redaction_summary`, `editorial_summary`, `audit_synthesis`,
  `rate_limit_retry`, `oge_capture`. They carry identifiers and counts only,
  never document or prompt text.

Cost is printed live per call as `[COST] <AGENT> +$0.0123 ...` and totalled at
run end.

---

## 5. Approve a governed decision

Some decisions are the operator's, never the agents': a deprecated model the
registry cannot auto-resolve, a constitution amendment. On an interactive run
the pipeline asks at the terminal. On a `--non-interactive` run (which is what
the server always uses) the question is PARKED instead of guessed:

1. the pipeline writes `<run>/audit/pending_approval.json` and posts an
   `ESCALATE` message on the bus;
2. it then waits up to `SHIMMER_APPROVAL_WAIT_S` (default 3600 seconds) for
   `<run>/audit/approval_decision.json`;
3. `GET /approvals` lists every run currently waiting. The console's Approvals
   section shows the same;
4. you decide:

```
curl.exe -X POST http://localhost:8000/approvals/<run_id> ^
  -H "Authorization: Bearer <token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"decision\": \"APPROVE\", \"rationale\": \"why\"}"
```

`decision` is `APPROVE`, `DENY` or `DEFER`. On timeout the handler returns
`DEFERRED` and the run stops rather than proceeding on an assumption.

Neither the server route nor the file handler evaluates your decision. They
relay it verbatim; the evaluation stays in `model_registry.enforce_current_models`
and `constitution_guard._is_approved`. An agent can never approve its own
governed change.

---

## 6. What each status means

| Status | Exit code | Meaning | What to do |
|---|---|---|---|
| `queued` | n/a | accepted, waiting for the single worker slot | wait; one job runs at a time |
| `running` | n/a | in flight | watch `/status` or the log |
| `completed` | 0 | finished, deliverables written | fetch `GET /results/{run_id}` (a zip) |
| `snapshot_conflict` | 2 | a snapshot operation refused to overwrite | resolve the snapshot name, resubmit |
| `stopped_model_approval` | 3 | a model needs your approval and none arrived | approve or deny (section 5), resubmit |
| `stopped_redaction_gate` | 4 | the local redaction backend is unreachable, or no operator redaction rule compiles | fix the Qwen backend or supply a compiling convention; or declare the run redact-nothing with `--no-redaction-override` |
| `blocked` | 5 | a LAW-IV redaction BLOCK: a span could not be confirmed absent. Also used for a draft-mode phase-0 generation failure | section 8 |
| `refused_sensitivity_layer_inactive` | 6 | a sensitive run was requested while the LAW-IV masking layer is inactive | this is by design; either run non-sensitive or activate the layer (an operator DELTA) |
| `operator_abort` | 7 | you declined at a prompt | nothing to fix |
| `interrupted` | n/a | the server restarted while this run was in flight | resubmit; the previous run's partial output stays under `output/runs/` |
| `failed` | any other non-zero, or a timeout | a genuine error or a run timeout | read `<run>/logs/pipeline_stdout.log` and the job's `error` field |

`blocked` and the three `stopped_*` statuses are GOVERNANCE OUTCOMES, not
crashes. The pipeline refused or paused on purpose. Treat them as a question
addressed to you, not as a bug.

---

## 7. When a run hangs

**First, decide whether it is actually hung.** A single agent call can legitimately
take minutes, and a rate-limit retry sleeps 20 then 40 seconds (Claude) or 60
seconds (GPT), logging `rate_limit_retry` each time. The embedding store's first
build downloads a model. Check, in order:

1. `<run>/logs/pipeline_stdout.log`: is the tail moving? Is the last line a
   `phase_start` with no matching `phase_done`?
2. the `[COST]` stream (`bus_viewer.py --follow`): are calls still landing?
3. `GET /status/{run_id}`: is `progress` advancing?

**Bound it in advance.** Two timeouts exist and both are off or generous by
default:

- `SHIMMER_PROVIDER_TIMEOUT_S` (default 600) is the per-request wall clock
  passed to the Anthropic and OpenAI clients. A hung provider call now fails
  with `timeout after Ns` instead of blocking forever.
- `SHIMMER_RUN_TIMEOUT_S` (default 0, unbounded) is the whole-run watchdog in
  the server. Set it to a number of seconds and a run that overruns is
  terminated (then killed), marked `failed` with a timeout reason and
  `exit_code: null`. Cleanup still runs.

Set both before starting the server:

```
set SHIMMER_PROVIDER_TIMEOUT_S=600
set SHIMMER_RUN_TIMEOUT_S=7200
```

**If it really is stuck and no watchdog is set**, kill the pipeline child
process. The server marks the job `failed` when the child exits. Restarting the
server rewrites any still-`running` record as `interrupted`, so the queue never
lies about a run that is no longer alive. Partial output under
`output/runs/<run>/` is left in place for inspection; nothing is auto-deleted.

---

## 8. When a run BLOCKs

Exit code 5 with status `blocked` means the LAW-IV privacy pass could not
confirm that an approved redaction span is ABSENT from an operator-facing
artifact. This is the one failure mode the system is designed to be
uncompromising about: a single leak is irreversible, so a deliverable that
cannot be proven clean is BLOCKED rather than shipped.

What to do:

1. Read the `REDACTION BLOCK` notice in `<run>/logs/pipeline_stdout.log` and the
   `redaction_summary` log event (`applied=`, `blocked=`, `held_warning=`).
2. Read the `ESCALATE` messages on the bus for that run
   (`py -3.9 scripts\bus_viewer.py`, channel `escalation`).
3. Look at the named deliverable under `output/runs/<run>/deliverables/<doc_id>/`.
   The block names which document and which span could not be located.
4. Do NOT hand the blocked deliverable to anyone while you investigate. That is
   the whole point of the block.
5. Fix the cause, which is usually one of: the redaction convention does not
   match how the span appears in the rendered artifact; the local redactor
   returned unparseable output (that is `held_warning`, a format failure, not a
   privacy violation, and it is logged to
   `durable/governance/redaction_format_warnings.jsonl`); or the span appears in
   a form the post-apply grep cannot locate.
6. Re-run once the convention or the redactor is fixed.

Exit 5 is also used for a draft-mode phase-0 generation failure (no memo was
produced). The exit code alone cannot distinguish the two, so check the log
tail: a draft failure says `draft phase 0 failed (no memo generated)`.

---

## 9. Reading cost_tracker.json

Every run writes two cost files under `output/runs/<run>/logs/`:

- `cost_tracker.jsonl` is the append-only EVENT MASTER: one line per model call.
  This is the audit trail. Fields include `timestamp`, `agent`, `backend`,
  `model`, input and output tokens, cache tokens, `cost_usd`, `ok`, `error`,
  `phase`, `doc_id`, `duration_ms`.
- `cost_tracker.json` is a DERIVED aggregate snapshot, rewritten after every
  call. It is a pure function of the events file.

The snapshot's shape:

```json
{
  "timestamp": "...",
  "total_cost_usd": 2.6712,
  "total_calls": 43,
  "total_failures": 0,
  "by_family": { "claude": { "calls": 28, "cost_usd": 2.41, "failures": 0,
                             "cache_read_input_tokens": 118400, ... },
                 "gpt": { ... }, "qwen": { ... } },
  "by_agent":  { "LEGAL_ANALYST": { ... }, ... },
  "by_phase":  { "3-4": { ... }, "5": { ... }, ... },
  "by_doc":    { "<doc_id>": { ... }, ... },
  "pricing":   { "claude-opus": { "input_per_mtok": 5.0, ... }, ... }
}
```

How to read it:

- **`total_cost_usd` is the number that matters.** Compare it against the
  pre-run estimate the pipeline printed before you approved the run.
- **`total_failures` above zero** means calls failed. Find them in the events
  file by `"ok": false` and read the `error` (already scrubbed of anything
  key-shaped).
- **`by_phase` tells you where the money went.** A phase with an unexpected
  share is the first place to look for a loop or a retry storm.
- **`by_doc` gives per-document cost**, which is what a per-document price would
  have to be based on.
- **Cache tokens**: `cache_read_input_tokens` (Claude) and `cached_input_tokens`
  (GPT) should be non-zero on any run with more than a couple of calls. A drop
  to zero means prompt caching stopped catching, and the run costs materially
  more than it should.
- **`pricing` is embedded in the snapshot** so a past run's cost stays
  interpretable after the price list changes. `config/pricing.json` carries an
  `as_of` date; verify it against the provider's current list price before
  billing anything real.

---

## 10. Back up

Two trees hold the only NON-REGENERABLE state in the system:

- `durable/` (learned and governance state that survives a reset, including the
  append-only governance audit trail: model approvals, constitution-guard
  decisions, redaction waivers, sensitivity overrides, the LAW-IV exposure
  ledger);
- `ontology/stores/` (the cross-run learning graph's append-master JSONL
  stores; `graph.json` and `gnn_state.json` are derived and rebuild themselves).

Everything else is regenerable: the convention registry is rebuilt at BOOT, the
embedding store rebuilds from `input/context/`, per-run output is a terminal
artifact.

```
py -3.9 scripts\backup_state.py --dest D:\shimmer_backups
py -3.9 scripts\backup_state.py --dest D:\shimmer_backups --label pre_upgrade
```

This copies both trees plus `config/constitution.json`,
`config/agent_registry.json` and `config/pricing.json` into a timestamped folder
`D:\shimmer_backups\shimmer_backup_<YYYYmmdd_HHMMSS>[_label]\`, and writes
`MANIFEST.json` with a SHA-256 and a byte length for every file. No compression,
no cloud, no scheduler: where the destination folder lives is your decision.

**Verify a backup**, at any time, on any machine that has the folder:

```
py -3.9 scripts\backup_state.py --verify D:\shimmer_backups\shimmer_backup_20260903_181500
```

It re-hashes every file the manifest lists and reports `MODIFIED`, `MISSING` and
`EXTRA`. Exit code 0 means intact, 1 means it is not.

**When to back up**, at minimum: before an upgrade or a dependency change,
before `--reset-snapshot`, before activating the sensitivity layer, and after
any run that produced a governance record you care about (an approval, a waiver,
a BLOCK). A backup takes seconds; the governance trail cannot be reconstructed.

Note: `durable/cache/embedding_store.pkl` is included when it exists and can be
large. It is regenerable, so if backup size ever matters you can delete it from
a copy of the backup, but then that backup no longer matches its manifest, which
`--verify` will correctly report. Prefer keeping the backup intact.

---

## 11. Restore from a backup

**There is deliberately no restore command.** A script that can overwrite live
durable and governance state on one command is a foot-gun: one wrong argument
silently replaces an append-only audit trail with an older one. Restore is a
copy you perform consciously.

1. **Stop everything.** No pipeline run, no server, no chat session. A running
   pipeline holds durable state open and will write over what you restore.
2. **Verify the backup first.** Never restore from a backup you have not
   verified:
   ```
   py -3.9 scripts\backup_state.py --verify D:\shimmer_backups\shimmer_backup_20260903_181500
   ```
   Restore only if it reports `INTACT`.
3. **Move the current state aside rather than deleting it.** You may need it:
   ```
   ren durable durable_before_restore_20260903
   ren ontology\stores stores_before_restore_20260903
   ```
4. **Copy the backup's trees into place:**
   ```
   xcopy D:\shimmer_backups\shimmer_backup_20260903_181500\durable durable /E /I
   xcopy D:\shimmer_backups\shimmer_backup_20260903_181500\ontology\stores ontology\stores /E /I
   ```
5. **The three config files are a SEPARATE, deliberate decision.**
   `config/constitution.json` is append-only and governed: restoring an older
   copy REMOVES amendments that were ratified after the backup, which the
   amendment guard exists to prevent. Only restore it if you have established
   that the live file is the damaged one, and read the diff first:
   ```
   fc config\constitution.json D:\shimmer_backups\shimmer_backup_20260903_181500\config\constitution.json
   ```
   The same caution applies to `config/agent_registry.json` (an approved model
   swap after the backup would be undone) and `config/pricing.json`.
6. **Run the verify gate** (section 12). It reads the constitution and the
   registries and will refuse a state that does not hold together.
7. **Keep the moved-aside directories** until a full run has completed
   successfully.

---

## 12. The verify gate

```
py -3.9 -X utf8 scripts\verify_session1.py
```

The total is the length of the CHECKS list, not a fixed number. What matters is
the summary line: `FAIL/ERROR=0` with `PASS=TOTAL`, and no `WARN` or `SKIP` on
an online run. Run it every session and before every commit.

`--offline` skips the two checks that touch the network (the live search and the
cold embedding-model download); they report `SKIP` instead of `PASS`. Use it for
a hermetic run. The ONLINE gate is the real bar.

The gate is non-mutating: it works in temporary directories and never writes the
real `durable/`, `ontology/` or `config/` stores. If a gate run ever leaves a
modified tracked file behind, that is a bug in the check, not an expected cost.

**Before every commit**, also run the secret guard:

```
py -3.9 scripts\guard_secrets.py
```

The repository ships a pre-commit hook at `.githooks/pre-commit` that runs it
automatically, but the hook is NOT installed by default. Install it once with:

```
git config core.hooksPath .githooks
```

Until you do, running the guard by hand is the only thing standing between a key
and a commit.
