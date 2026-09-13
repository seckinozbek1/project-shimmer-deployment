# RESUME: local performance diagnostic complete, 2026-09-13

**Read this file first in a cold session. Next locked item: Local speed-optimization audit.**
ZERO through TWENTY-ONE, baseline normalization and roadmap items 1 and 2 are complete.
Do not resume old technical backlogs or begin a later roadmap item out of order.
The authorized synthetic native baseline reached the pipeline end. Private/operator
document review and fresh-clone testing remain unrun.

## Repository checkpoint and normal startup

- Workspace: `C:\Users\secki\local\shimmer-deployment`.
- Sole intended origin: `https://github.com/seckinozbek1/project-shimmer-deployment`.
- The operator pushed the human-startable work. At diagnostic entry, both main
  and local origin/main were `5b72b16c67b02890ffc8be39096b5bad10e1c05c`, above
  preserved `83866c9` and `b733188cb038dbcc482e68aecf69cbefb04587e4`.
- This item is the local commit titled `Record local performance diagnostic baseline`.
  Resolve its hash with `git log -1 --format=%H -- docs/fix/RESUME.md` after a
  staged-secret scan. Main is one commit ahead of the unchanged local origin/main
  tracking ref. No fetch or push occurred. The operator pushes.
- Preserve intentional untracked `SHIMMER_HANDOFF.md` and `durable/`, and all
  ignored operator input/output/ontology state. None is part of this commit.
  Do not reset, clean, rebase, stash or amend history.

The normal Windows entry is **`start_shimmer.bat`**. Its Start Shimmer window asks
Local/Cloud, checks installed prerequisites and confirms server startup. The browser
opens at the actual `/console` address. Copy access token in the starter, paste
into the console, click Use this token. Submit owns Review/Draft, files/roles,
explicit Normal/Sensitive and confirmation. Stop Shimmer owns shutdown; restart
gets a new token. No commands, manual hash or Docker are needed for this path.
Prerequisites must already be installed. Failures block startup visibly.

Read [HUMAN_STARTUP_AUDIT.md](HUMAN_STARTUP_AUDIT.md) for the pre-change trace and
[HUMAN_STARTUP_REPORT.md](HUMAN_STARTUP_REPORT.md) for acceptance, exact UI,
decisions, changed files, adversarial findings, proofs and remaining limits.
README and RUNBOOK use the new primary flow. CLI/API/local-demo/Docker remain.

## Current diagnostic baseline

Read [LOCAL_PERFORMANCE_DIAGNOSTIC.md](LOCAL_PERFORMANCE_DIAGNOSTIC.md) for the
pre-instrumentation timing map, complete measurements, proofs and ranked candidates.
The scope was diagnosis only. No optimization or shipped/runtime change was made.

- Unchanged shipped `clinical_reference`: 3 input files / 5,265 bytes, one target
  `result_sheet.md`, 6 units, all 5 conventions. Standalone Normal paired Review,
  explicit existing role manifest, unchanged local models and budgets. No answer
  key opened/scored, no private document reviewed, no provider or paid call.
- Native wall **5,054.4 s / 84 min 14.4 s**, 08:50:49.611 to 10:15:03.996 UTC,
  exit 0. `run_completion.json`: completed, reached_end true, 1 document,
  3 amendments. All 26 dispatch/generation/cost/evidence rows joined, no open spans.
- Generation **4,947.4 s / 97.9%**. Qwen producer 13 calls / 3,040.1 s;
  Phi auditor 13 calls / 1,907.3 s. First loads 12.843 / 9.423 s; producer reload
  12.163 s. Twenty-three resident generation-cache hits, one model resident at
  each load return. CPU bge-m3 first use 2.628 s; encoding 55.422 s.
- Phase ranking: production 38.73 min, convention review 16.49 min,
  verification 15.55 min, editorial 12.43 min. All model generations serialized.
- RTX 3070 Ti Laptop / 8 GiB: peak VRAM 7.51 GiB. Process RSS peak 6.67 GiB;
  system available RAM minimum 115.5 MiB. GPU generation utilization medians
  82% producer / 34% auditor. Early thermal slowdown confirmed; later CPU/GPU
  clock variation and underutilization are measured, with cause not established.
- Twelve capped calls and two contract-violation dumps limit quality claims.
  Board is REVIEWED with one consolidated observation and no failed rank, despite
  the clerk's 8,192-token cap. Actual-contract replay matches the saved parsed
  result after a 112-retokenized-token prefix. The unconsumed suffix is a strong
  audit candidate, not proof of safe early stopping or exact time savings.
- Warm derived-store consumer reused 11 passages in 0.143 s with zero model
  imports/loads. Neutralize/fail/restore/pass cache and parser proofs pass;
  instrumentation and interrupted/error reducer fixtures pass. A preliminary
  62.2 s guard-defect attempt reached no generation and is preserved separately.
- One metadata HTTP API entry was blocked and recovered from local cache; no
  successful egress or provider dispatch. Do not describe this native run as
  zero attempted HTTP requests. The older image probe is separate evidence.
- All 128 copied runtime source files, 3 synthetic inputs and 18 monitored
  operator-state files remain byte-identical. Caches and untracked state preserved.

Evidence and ignored diagnostic helpers: `output/local_performance/`, including
`baseline/events.jsonl`, `summary.json`, `inference_calls.json`, `reconciled.json`,
native lifetime, cache/parser proofs, resource snapshots and an evidence manifest.
These helpers are local evidence, not fresh-clone assets. Never rerun the harness
over the existing baseline root or invoke its preparation path over operator state.
All benchmark and probe processes have exited; no heavy workload remains running.

This documentation-only item owes no new full gate or image rebuild under the
operator's explicit diagnostic exception. The startup gate/image below are prior
results, not new executions. No README behavior debt was introduced. The next item
must evaluate output consumption, host variability and legal-follow-up value before
assuming repeated loads or deterministic arithmetic dominate. No candidate has
been implemented. No later roadmap item has begun.

## Previous shipped startup gate and image

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


The latest separate model/ensemble probe remains TWENTY-ONE,
`output/twentyone_offline_probe.log`: six steps PASS in 29.6 seconds with zero
guarded HTTP/socket/DNS attempts and no host mounts. It was not rerun or relabelled.
Check 193 separately proves a real cached Phi load. Startup cache checks and
fixture/model-load evidence do not prove generation quality or real review success.

## Locked operator-owned product roadmap

**Do not reorder, add, remove, merge or skip items without asking the operator.**

1. Human-clickable / human-startable product flow. **Complete.**
2. Local performance diagnostic. **Complete.**
3. Local speed-optimization audit. **Next.**
4. README + upstream/downstream routing + UI audit.
5. FinOps + VM/GPU feasibility analysis.
6. VM run/debugging only if the FinOps result shows that repeated debugging runs are acceptably cheap.
7. Fresh-clone smoke test.
8. Prototype release-readiness pass.

Item 6 remains conditional. Python packaging is parked. Items 3 through 8 have
not begun. Fresh-clone Windows installation, browser policies,
credential/model provisioning and full native visual QA remain unverified.
Sensitive remains unavailable while its required existing layer is inactive.
Local Draft retains its documented existing generation limitation. No model choice,
routing, LAW-IV or agent semantics changed to make startup appear successful.

## Machine and repeatable evidence

Pinned host interpreter is `py -3.9`, at
`C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe`.
It sees installed user-site dependencies with proper host access. Sandbox absence
is not an installation failure: do not reinstall/migrate dependencies for it.
The desktop compares installed project/current interpreters and displays its
choice. Only one heavy GPU/model workload may run at a time on this laptop.

Docker is `C:\Users\secki\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe`.
Use host access when sandbox visibility hides it. No global Docker settings changed.

- Exact host gate: `py -3.9 -X utf8 scripts/verify_session1.py`.
  `output/run_startup_host_gate.py` captures that native subprocess and exit JSON.
- Image cache/build: `output/build_checkpoint.py startup`, using
  `output/shimmer_build_cache`, BAKE_WEIGHTS=true, local cache import/export.
  Use a new alphabetic slug for future checkpoints; do not overwrite this evidence.
- Parity: `output/audit_image_source.py shimmer:startup output/startup_source_audit.json`.
  Always compare the intended inventory too, not only discovered files.
- Full image gate: `output/run_startup_container.py gate`, unmounted/offline/GPU.
- Browser fixture: `node tools/startup_console_proof.js`.
- `output/startup_git.py` scans staged contents without displaying credential values
  before its requested Git operation. Its exact inspected fixture exceptions are
  in `output/startup_staged_fixture_allowlist.json`; they exempt no provider pattern
  or whole file. It and other output helpers are local ignored
  evidence, not fresh-clone assets.

`tools/console_preview.py` can seed live ontology; never run it against operator
state merely to test a screen. Startup proofs use isolated temporary roots.
Old checkpoint finalizers can overwrite current handovers; do not rerun them.
`PROTOTYPE_CHECKPOINT.md` and older LEDGER entries remain historical, not new work.

## Engineering methods to preserve


**Offline models.** Baked bge-m3 needs safely prepared safetensors. The established
build converts weights using a temporary patched CPU reader with weights-only
loading and removes that dependency in the same layer; runtime pins stay intact.
Do not reintroduce runtime pickle conversion. Resolve cached generation models to
their local snapshot directory before Transformers loading. Repository-ID loading
can attempt hidden custom-generation network checks despite local-only settings.
Refuse custom generation overrides in snapshots. Count HTTP, socket and DNS
attempts, including attempts caught internally; eventual success is not proof of
offline behavior. The real offline model/ensemble probe is stronger than cache
presence.

**Behavioral verification.** Reading a value does not prove an effect. Changed
behavioral checks require neutralise/fail/restore/pass, with an independently
observable behavior change before check failure counts as evidence. A second
safe branch can make a neutralization a no-op. Validate fixtures parsed as
intended before behavioral assertions. Prefer real consumer paths to source-text
assertions. Assignment is not a call; a call is not a successful response.
Missing evidence stays unknown. Intentionally unavailable coverage is SKIP;
malformed/incomplete available fixtures, incomplete scans and regressions FAIL.
An unavailable contamination fixture cannot establish a clean scan. Reuse
`scripts/effect_proof.py`; its protocol is bounded, not a universal test-quality
detector.

**Saved runs and scoring.** Planned questions are not emitted findings. Exposure
must reach an assigned consumer; suspension is scoped to an exact unit/rule pair.
Keep computed and judged absence separate. Preserve completed-empty versus
interrupted outcomes and historical unknowns; exit 0 alone does not prove the
pipeline reached its end. Typed relation scoring is generic, including
`date_window`, and reads every document master in the run. Numeric document
positions require unique unit identity. Run identity survives folder renames;
submission time orders recovered work. PROCESSOR truncation must reach downstream
auditors explicitly, and failed-contract best-effort drafts are not complete
extraction. The local PROCESSOR and existing board request use 8192 output tokens;
cloud budgets were not generalized from local evidence. Complete valid
prose/fence-wrapped envelopes already recover; never invent closing syntax for an
unfinished envelope. The 14-judged/7-computed forecast is a question checked by
actual runs, not a promise of emitted compliant claims.

**GNN and ontology.** Retain the candidate finder and measure it against the
deterministic relation baseline at a fixed review budget. Its current structural
reconstruction objective does not establish learned relevance or review
correctness. Arithmetic/structural mechanisms offer narrow labels, not general
semantic ground truth. The 78 apparent historical operator-verdict rows were
test-fixture writes, not valid human supervision; isolation was fixed and the
append-only historical rows preserved. Building a new learning component remains
an operator decision. Read [TWENTY_LEARNING_SIGNAL.md](TWENTY_LEARNING_SIGNAL.md)
for the assessment and measurement design.

**Standing boundaries.** The operator explicitly authorized the controlled local
synthetic benchmark for the now-closed diagnostic item. That exception does not
grant blanket authorization for future runs. Otherwise no pipeline run on this
laptop, provider/cloud generation, paid operation or push under the standing
development authorization. The locked
roadmap does not authorize a VM run before its condition is met. Preserve local
history and operator data; no reset, clean, rebase, amend or stash. No new dependency
without a written ledger reason. Preserve ratified five-voter semantics and REFUSES
cases, and never weaken governance to simplify startup. Read `CLAUDE.md` and
`genesis.md` before product changes. Scan staged files before Git operations,
never expose credentials, and stop on a real exposed key. No new em dashes.
For later product work, close one item before opening the next, pay its README/image
debt, run appropriate behavioral evidence and adversarial review, then update RESUME.


**This item is closed. Stop here; the next locked product item is Local speed-optimization audit.**
