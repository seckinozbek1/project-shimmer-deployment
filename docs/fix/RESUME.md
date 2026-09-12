# RESUME: session closed, 2026-09-13

**Read this file first in a cold session. Do not resume the old technical backlog.**
ZERO through TWENTY-ONE and baseline normalization are complete. The next approved
product task is **Make Project Shimmer human-clickable / human-startable**.
This closure session did not begin that task or run a real document review.

## Repository checkpoint

- Windows workspace: `C:\Users\secki\local\shimmer-deployment`.
- Sole intended origin: `https://github.com/seckinozbek1/project-shimmer-deployment`.
- At closure entry, both `main` and `origin/main` were
  `b733188cb038dbcc482e68aecf69cbefb04587e4`. The operator had pushed all prior work.
- Final HEAD is the focused local documentation commit titled
  `Close the session and preserve the locked product handoff`, directly after
  `b733188`. Resolve its exact SHA with
  `git log -1 --format=%H -- docs/fix/RESUME.md`; this avoids embedding a commit's
  own unknowable hash in its content.
- After that commit: tracked working tree clean, one unpushed documentation commit,
  `origin/main` still at `b733188`, one commit behind local `main`. No agent push.
- Intentional untracked state: `SHIMMER_HANDOFF.md` and `durable/`. Preserve both;
  neither belongs in the closure commit. `output/` contains ignored local evidence
  and tools, including the large build cache; these are not fresh-clone assets.
- Reestablish state with the four commands below after the required staged-secret
  scan. No remote fetch or push is needed to read these local tracking refs.

```powershell
git status --short --branch
git branch -vv
git log --oneline -15
git log --oneline origin/main..HEAD
```

The recovery started at `64b83e0`, then 31 commits ahead of `2c88112`.
Those counts and the later 52/53-unpushed counts are historical, not current.
[PROTOTYPE_CHECKPOINT.md](PROTOTYPE_CHECKPOINT.md) records the TWENTY-ONE snapshot
at `2562578`; [LEDGER.md](LEDGER.md) preserves the dated implementation evidence.
The old handoff, historical open-work lists and older TODO material do not reopen
completed items. ZERO-C was formerly misnamed ONE; the actual learning item ONE
was already closed.

## Verified milestone and coverage limits

Baseline normalization is `b733188`, with assertions retained and nine restoring
mutation proofs. The final measured host gate is **253 PASS, 0 WARN, 2 SKIP,
0 FAIL/ERROR, TOTAL 255**, native exit **0**. No known host baseline FAIL remains.
Evidence: `output/baseline_host_gate.log`, `output/baseline_host_exit.json`.

- On this host, check 01 skips only because optional `prompts/` and `snapshots/`
  are intentionally absent. Under the unmounted-image contract, wholly absent
  `input/`, `output/` and `durable/` roots can also be SKIP with their declared
  provisioning reasons. `config/` and `scripts/` remain required. Wrong types,
  broken links and missing declared children under a present root still FAIL
  before optional absence is considered.
- Check 145 skips only when optional
  `tests/fixtures/planted_figure_hashes.json` is unavailable. It explicitly says
  contamination cannot be ruled out. Its absence is not evidence of cleanliness.
  Malformed, empty, unreadable or wrongly typed available fixtures, invalid
  digests, missing required source roots, incomplete scans and contamination FAIL.
- Check 254 exercises real checks 01/145 with valid, absent and invalid fixtures.
  Nine neutralizations changed an independently observed result before check FAIL;
  restoration recovered both the result and PASS. Grouped numeric token scanning,
  traversal/read errors, nested links and disappearing text entries are covered.
  Evidence: `output/baseline_proof.py`, `output/baseline_proof.log`.

Latest relevant image: **shimmer:baseline**,
`sha256:4a3321795ee3c01a91d2fe151517cce07da87b7c1818ec8beedd415cd8272a34`,
14,408,312,142 bytes. All 126 intended shipped paths matched at `b733188`
using SHA256 with CRLF normalized to LF: `output/baseline_source_audit.json`.
All model/conversion layers reused: `output/baseline_build.log`.
This closure changes repository documentation and README prose only. The existing
image retains the earlier README; runtime code, gate implementation/fixtures, models and configuration
are unchanged. No image rebuild or expensive gate repeat was needed for closeout.

The full unmounted image gate is **243 PASS, 0 WARN, 10 SKIP, 2 FAIL/ERROR,
TOTAL 255**: `output/baseline_container_gate.log`. Only checks 28/31 FAIL because
the image has no intake tree. Check 01 and 145 SKIP; check 254 PASS. Other SKIPs are
15/38 (network), 222 (host launchers), and 215/217/224/227/230 (unshipped corpora).
Do not describe this full image gate as green.

The latest separate model/ensemble probe remains the **TWENTY-ONE** probe,
`output/twentyone_offline_probe.log`: six steps PASS in 29.6 seconds, zero guarded
HTTP/socket/DNS attempts, `--network none --gpus all`, no host mounts. It loads
real bge-m3 and executes declared five-voter decisions. It was not rerun or
relabelled as a baseline probe. Check 193 separately proves a real cached Phi
load; check 139 exercises the CUDA construction branch with construction stubbed.
These are loading and fixture proofs, not proof of generation by every model.

Seven monitored live files remained byte-identical through normalization:
`output/baseline_state_before.json`, `output/baseline_preservation.log`.
The first real end-to-end review of this prototype remains intentionally unrun
under the previous no-pipeline-run development rule. Real provider output quality,
general domain independence, broader corpus performance and candidate-finder gain
remain unverified. Historical runs were not backfilled.

## Locked operator-owned product roadmap

**Do not reorder, add, remove, merge or skip items without asking the operator.**
A suggested change requires an operator decision before changing this list.

1. Human-clickable / human-startable product flow.
2. Local performance diagnostic.
3. Local speed-optimization audit.
4. README + upstream/downstream routing + UI audit.
5. FinOps + VM/GPU feasibility analysis.
6. VM run/debugging only if the FinOps result shows that repeated debugging runs are acceptably cheap.
7. Fresh-clone smoke test.
8. Prototype release-readiness pass.

Item 6 is conditional, not guaranteed. Python packaging is parked and is not a
roadmap item. The older assumption that development should immediately move to a
GPU VM is superseded by this order and its FinOps condition.

When the next session begins item 1, inspect `shimmer.bat` first after this file
and the operating contract. Trace the existing launcher/menu, server and console
startup, token creation/handling without revealing values, backend and sensitivity
selection, preflight/dependency errors, presented URLs, Windows behavior,
stopping/restarting, paths requiring manual CLI knowledge, and implementation
details exposed to a nontechnical user. The objective is understandable, clickable
normal startup while preserving governance and visible failures. This is an
inspection handoff only; no item 1 implementation occurred during closure.

Existing entry files for that trace are `scripts/intake_wizard.py`,
`scripts/preflight.py`, `scripts/server.py`, `scripts/ui/console.html` and
`tools/entrypoint.sh`. Their existence was checked; their startup behavior was
not newly audited during closeout.

## Machine and repeatable commands

Pinned host interpreter: `py -3.9`, resolving to
`C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe`.
It works with the installed project dependencies when given proper host access.
The repository virtual environment did not contain the heavy dependencies.
Sandbox visibility can hide installed dependencies and Docker. Do not install
replacements or migrate Python to disguise an access problem. Only one heavy
GPU/model workload may run at a time on this laptop.

Docker is installed at
`C:\Users\secki\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe`.
Do not assume the Program Files location or a working PATH. Use host access for
Docker and dependency-heavy Python when the sandbox cannot see them.

Proven host gate:

```powershell
py -3.9 -X utf8 scripts/verify_session1.py
```

For reliable native exit capture, reuse
`py -3.9 -X utf8 output/run_baseline_host_gate.py`. This writes the baseline log
and exit JSON. The initial PowerShell stderr-redirection wrapper reported an error
despite a zero-failure table; `output/baseline_powershell_gate.log` is retained.
The direct subprocess rerun proved native exit 0 without any assertion/filter change.

Proven local cache is `output/shimmer_build_cache`. The helper
`py -3.9 -X utf8 output/build_checkpoint.py baseline` wraps this pattern and writes
build log/metadata. Use a new alphabetic checkpoint slug for a future image.

```powershell
$shimmerDocker = 'C:\Users\secki\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
& $shimmerDocker buildx build `
  --build-arg BAKE_WEIGHTS=true `
  --cache-from type=local,src=output/shimmer_build_cache `
  --cache-to type=local,dest=output/shimmer_build_cache,mode=max `
  -t shimmer:baseline .
```

Export/import solved repeated weight downloads without global Docker changes or
registry upload. Historical BuildKit GC was plausible, not a proven eviction
event. Keep the measured cache remedy; do not repeat that investigation.

Proven source-parity helper:

```powershell
py -3.9 -X utf8 output/audit_image_source.py shimmer:baseline output/baseline_source_audit.json
```

It compares image files to host bytes after CRLF normalization and records image
identity. Also compare the intended path inventory; matching only discovered
paths cannot prove no intended file was omitted. The saved baseline inventory
contains 126 paths. A rerun against the closure tree will report the deliberate
README difference until a future product image includes it.

Proven full image gate wrapper:
`py -3.9 -X utf8 output/run_baseline_container.py gate`.
It runs Python with `--offline`, `--network none --gpus all` and no mounts against
`shimmer:baseline`. Its exit 1 represents the documented checks 28/31.
The separate probe's proven direct invocation shape is:

```powershell
& $shimmerDocker run --rm --pull never --network none --gpus all --entrypoint python shimmer:twentyone tools/container_offline_probe.py
```

Expose the GPU only where needed; source audit needs none. Do not mount host caches
or data when proving baked-image independence. Existing wrappers overwrite their
named logs, so preserve historical evidence or use a new checkpoint before reruns.
Do not rerun these expensive commands merely to reconstruct this closure.

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

**Standing boundaries.** No pipeline run on this laptop, provider/cloud generation,
paid operation or push under the standing development authorization. The locked
roadmap does not authorize a VM run before its condition is met. Preserve local
history and operator data; no reset, clean, rebase, amend or stash. No new dependency
without a written ledger reason. Preserve ratified five-voter semantics and REFUSES
cases, and never weaken governance to simplify startup. Read `CLAUDE.md` and
`genesis.md` before product changes. Scan staged files before Git operations,
never expose credentials, and stop on a real exposed key. No new em dashes.
For later product work, close one item before opening the next, pay its README/image
debt, run appropriate behavioral evidence and adversarial review, then update RESUME.

## Existing assets to reuse

All paths below were checked during closure. `output/` assets are local and ignored;
tracked tools and reports survive a fresh clone. Do not copy helper contents here.

| Existing asset | Purpose |
|---|---|
| `output/build_checkpoint.py`, `output/shimmer_build_cache` | Baked build and reusable exported cache. |
| `output/baseline_build.log`, `output/baseline_build_metadata.json` | Latest model-layer reuse and image build evidence. |
| `output/audit_image_source.py`, `output/baseline_source_audit.json` | Image identity and 126-path source parity at b733188. |
| `tools/container_offline_probe.py`, `output/twentyone_offline_probe.log` | Tracked behavioral probe and latest measured separate result. |
| `output/run_baseline_host_gate.py`, `output/baseline_host_gate.log`, `output/baseline_host_exit.json` | Native host gate capture and verified exit. |
| `output/run_baseline_container.py`, `output/baseline_container_gate.log` | Offline full-image gate, pinned to baseline. No baseline separate-probe log exists. |
| `scripts/effect_proof.py`, `output/baseline_proof.py`, `output/baseline_proof.log` | Consumer-effect protocol and nine restoring baseline mutations. |
| `output/twentyone_proof.py`, `output/twentyone_proof.log` | Five quote-forecast/consumer mutations. |
| `output/eighteen_ui_proof.py`, `output/fifteen_ui_proof.py` | Existing API-to-console JavaScript fixture proofs; reuse as patterns. |
| `output/baseline_state_before.json`, `output/baseline_preservation.log` | Seven-file operator-state preservation evidence. |
| `docs/fix/PROTOTYPE_CHECKPOINT.md`, `docs/fix/LEDGER.md` | Historical takeover inventory and dated evidence, including inherited decisions. |
| `docs/fix/READING_NOT_EFFECT.md` | Historical worked example behind the now-completed THIRTEEN method. |
| `docs/fix/TWENTY_LEARNING_SIGNAL.md` | GNN conclusion and bounded evaluation proposal. |

`output/run_image_checks.py` exists for checks expected to PASS; do not use it to
reinterpret expected SKIPs 01/145. Old checkpoint finalizers are historical
automation and can overwrite current handover text; do not rerun them for closure.

**Session closed. Next session reads this file, then begins only roadmap item 1
when product work resumes.**
