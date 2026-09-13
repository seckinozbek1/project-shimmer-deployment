# Human-startable product flow, 2026-09-13

Locked roadmap item 1 is implemented. The audit was written before choosing the
implementation: [HUMAN_STARTUP_AUDIT.md](HUMAN_STARTUP_AUDIT.md). This report covers
startup and its immediate intake wiring, not review quality or later roadmap work.

## Acceptance answer

> On a Windows machine where Shimmer's prerequisites are already installed, what single file does a normal user double-click, what do they see next, and how do they reach the usable console without typing a command?

Double-click **`start_shimmer.bat`**. A **Start Shimmer** desktop window shows
Local and Cloud radio buttons, neither selected, a console port defaulting to 8000
(or an inherited configured port),
a readiness report area, and **Check and start**. Choose a backend and press that
button. The starter selects an installed Python environment, checks prerequisites
without installing or downloading, and shows failures with a next action. If
ready, it asks whether to start the selected console. Declining starts no server.

Confirming starts an owned server on loopback and opens the browser at the actual
`http://127.0.0.1:<port>/console` address. Click **Copy access token** in the starter,
paste into the browser's password-style **Access token** field, and click **Use
this token**. The starter supplies a usable session token; the user never computes
a hash or types a URL. The server's startup environment receives only its SHA256
hash. The starter keeps the raw token in memory, and the browser keeps it in tab
session storage and sends it in authenticated request headers. It is copied to
the clipboard only when requested, never placed in a URL or logs.

The console's **Submit** screen asks Review or Draft, accepts files through the
system picker, exposes relevant target/earlier-version/reference roles, and requires
an explicit Normal or Sensitive choice. A summary precedes **Confirm and start**;
Cancel sends no submission. Starting the console alone performs no review.
**Stop Shimmer**, or confirming closure of the starter, shuts down the owned
server and unfinished work. Restart creates a new token. Closing only the browser
leaves the server running. Failed and interrupted work remains visibly incomplete.

This description is backed by the real Windows batch entry, actual GUI callbacks
with fixture widgets, a real isolated Uvicorn child and authenticated console,
and the shipped browser JavaScript in a DOM harness. Native visual rendering,
browser integration and clean-machine installation were not manually certified.

## Before and after

Previously the visible launcher mixed installation, preflight and a CLI menu.
Users needed folder paths, terminal decisions and URL/token copying; the direct
server path required manual environment variables and hashing. Ordinary browser
uploads required the external-corpus metadata contract. Sensitive wizard choices
could acquire a waiver, and blank input could authorize import.

The desktop starter now owns backend/readiness/server lifecycle, while the console
owns task/files/privacy/confirmation. Ordinary standalone inputs use explicit
roles and the real classifier/parser. Integrated submissions retain their existing
validator when the new intake mode is omitted. Existing CLI, API, local-demo and
Docker entry points remain. No dependency, model selection, convention routing,
agent semantics, LAW-IV rule or redaction requirement was changed.

## Shared authorities and failure boundaries

- `run_choices.py` resolves explicit backend and privacy flags for the new path
  and wizard. Legacy server defaults remain compatible. Sensitive emits no waiver;
  an unavailable privacy layer refuses it. Normal requires an operator choice.
- `startup_settings.py` supplies the server and starter host/port/console URL.
  Desktop use is loopback only, checks the port and authenticates to the actual
  child before opening the browser. Invalid ports fail visibly.
- `preflight.py --check-startup` reuses the configured local model profile,
  tokenizer/cache checks and actual privacy readiness. It reports packages,
  model files, GPU and selected-mode credentials without installation, provider
  calls, server imports or operator-state mutation. Cache presence is not proof
  of successful generation. Technical readiness details remain in the log viewer.
- The existing bearer hash comparison remains authoritative. Tokens are fresh per
  desktop session. Browser data calls still use Authorization headers.
- Standalone staging rejects invalid files, duplicate/conflicting names and a
  conflicting role manifest. Cleanup removes only unchanged files created by that
  job. Draft references stay grounding after the generated memo becomes the
  target. An existing memo filename refuses before retrieval/generation; exclusive
  creation protects a file appearing while generation is in progress.
- Server shutdown owns workers and child processes, blocks queue advancement and
  waits for exit. Owner-pipe EOF also stops the desktop server. A recovered queued
  record becomes interrupted with a resubmit reason because staging is unavailable;
  neither that record nor missing native staging may silently dispatch a review.

## Evidence

Final host gate: **256 PASS, 0 WARN, 2 SKIP, 0 FAIL/ERROR, TOTAL 258**, native exit **0**.
Evidence: `output/startup_host_gate.log`, `output/startup_host_exit.json`.
Host SKIPs remain 01 (optional prompts/snapshots) and 145 (unavailable contamination
fixture; contamination cannot be ruled out). No host failure remains.

Final unmounted image: **shimmer:startup**, `sha256:90ce701581520e4ec763d5d36d22d59f1120668200a76a820af156de0aca6356`,
14,408,409,659 bytes. All **136 intended shipped paths** match
the frozen source after CRLF normalization, with no missing or extra paths.
Evidence: `output/startup_build.log`, `output/startup_build_metadata.json`,
`output/startup_source_audit.json`, `output/startup_inventory.json`.
Model download and conversion layers were cache hits; no model configuration changed.

Full image gate: **246 PASS, 0 WARN, 10 SKIP, 2 FAIL/ERROR, TOTAL 258**, native exit **1**.
Only checks 28/31 fail because an unmounted image has no intake tree. This is the
same two-failure baseline boundary, not a green full image gate. SKIPs are
01/145, 15/38 (network), 222 (host launchers), and 215/217/224/227/230 (unshipped
corpora). Check 255 runs its portable lifecycle/GUI fixture portions in the image;
the Windows batch dispatch is proven on the host only. The browser JavaScript
harness runs on host Node, which is not shipped in the image.
Evidence: `output/startup_container_gate.log`. The command used `--network none
--gpus all`, no host mounts, and `scripts/verify_session1.py --offline`.

All **20 startup restoring mutations across platforms** pass: readiness 3, wizard 4, desktop 6,
submission targets 1, Draft grounding/collision 2, recovery 2, browser JavaScript 2.
Windows executes 19; the additional POSIX socket-lifetime proof executes in the
image, preserves live-listener refusal and proves immediate TIME_WAIT reuse.
The adversarial read resolved crash callbacks, partial-environment selection,
hidden readiness detail, lost queued uploads, missing native staging, Draft
reference promotion and memo collision. No confirmed startup blocker remains.
`output/startup_console_proof.log` records the browser fixture result.

All **16 monitored operator-state files** remain byte-identical,
with no added/missing files in the monitored input/durable/ontology inventory:
`output/startup_state_before.json`, `output/startup_preservation.json`.
Fixtures used isolated roots; no real review or provider generation ran.
The earlier in-flight diagnostic gate is retained separately as
`output/startup_diagnostic_host_gate.log` and `output/startup_diagnostic_host_exit.json`;
its transient failures are superseded by the frozen-source full gate above.
The first frozen-runtime full gate had 255 PASS, 2 SKIP and one failure: check247
still selected recovered records by their obsolete queued state. Its exact
submission-order assertion was retained and explicit interruption was added;
the focused check passed before the final full rerun. Evidence is retained in
`output/startup_recovery_contract_host_gate.log` and its exit JSON.
The first image gate had two additional failures, retained in
`output/startup_first_container_gate.log`: POSIX TIME_WAIT falsely blocked an
immediate restart, and a synthetic citation triggered an existing Linux date
parser edge, violating the fixture's undated-memo premise. The port probe now matches Uvicorn's reusable listener on POSIX while
retaining Windows exclusive binding. The Draft fixture uses the existing valid
five-digit reference form and verifies its undated premise. All original role and
collision assertions remain; production date parsing is unchanged. Focused image
proofs passed before rebuilding and repeating the full gates. The Linux year-1
date parsing edge is still an explicitly recorded limitation in the startup report.


New checks 255/256/257 cover desktop lifecycle, read-only readiness and native
submission respectively. Existing 220/223 now prove explicit cancellation and
privacy through emitted flags and actual intake effects; 116 follows delegated
server settings; 166 exercises the actual privacy switch in health responses.
Check 247 keeps its exact submission-order and identity assertions and now requires
recovered records to be interrupted in memory and on disk. Remaining gate assertions
are retained.

Fixtures exercise real batch dispatch, real GUI callbacks, package selection,
nonzero failure, confirmation decline, authenticated `/console`, disabled/mocked
browser launch, actual Stop/restart/owner EOF, and no forbidden child/provider
dispatch. Submission fixtures exercise actual role consumers and argv across
backend, task and privacy, compatibility validation, conflicts, operator-edit
preservation, missing staging and worker shutdown. Draft generation and retrieval
are injected stubs; no real review or provider generation runs.

Mutation proofs use fixture-validity checks and independent observable effects
before fail/restore/pass, covering confirmation, browser route, lifecycle,
GUI decline/failure, prerequisites, privacy, wizard confirmation, target roles,
Draft grounding and collision refusal, recovered queue state and browser submission.
`tools/startup_console_proof.js` runs the actual shipped JavaScript with fixture
DOM/network objects and checks confirmation timing, roles and sign-in guidance.

## Files changed

Entry/lifecycle: `start_shimmer.bat`, `scripts/desktop_launcher.py`,
`scripts/desktop_server.py`, `scripts/startup_settings.py`.
Shared readiness/choices: `scripts/preflight.py`, `scripts/run_choices.py`,
`scripts/intake_wizard.py`.
Console/intake: `scripts/server.py`, `scripts/ui/console.html`, and the bounded
Draft role/preservation change in `scripts/pipeline.py`.
Verification: `scripts/verify_session1.py`, `scripts/startup_launcher_checks.py`,
`scripts/startup_readiness_checks.py`, `scripts/startup_submit_checks.py`,
`scripts/intake_choice_checks.py`, `scripts/draft_intake_checks.py`,
`tools/startup_console_proof.js`.
Documentation: `README.md`, `docs/RUNBOOK.md`, `CLAUDE.md`, this report, the audit,
`docs/fix/LEDGER.md`, `docs/fix/RESUME.md`.

## Boundaries left for later work

Prerequisites must already be installed. Installer behavior, Python/Tcl/Tk
distribution, clean credentials/model provisioning, Windows browser/clipboard
policies and a full fresh-clone smoke test remain unverified. The launcher installs
nothing and does not hide missing prerequisites. Readiness checks do not validate
live provider credentials, guarantee model generation or demonstrate GPU speed.
Sensitive remains unavailable while its existing required layer is inactive.
The existing local Draft generation restriction is unchanged.

Image fixture validation also exposed a pre-existing Linux date-parser edge:
a four-digit synthetic citation suffix `0001` can be mistaken for year 1, whose
un-padded Linux formatting then fails date parsing. Production dating is unchanged.
The Draft role fixture now uses the existing five-digit reference format and
explicitly validates that its memo is undated; this is not a claim that the
date-parser edge was fixed.

The first real end-to-end review remains intentionally unrun. The older offline
model/ensemble probe remains historical evidence, not a new startup measurement.
No performance diagnostic, optimization, comprehensive UI/routing audit, FinOps,
VM, fresh-clone or release-readiness work was begun. Next: **Local performance
diagnostic**, in the unchanged operator-owned roadmap order. Local commit only;
the operator pushes.
