# Human startup audit, 2026-09-13

Read-only trace at local HEAD `83866c9`, before implementation selection.
The prior closure commit is preserved. Scope is locked roadmap item 1 only.

## Existing desktop journey

1. A Windows user must discover that `shimmer.bat` is the entry point. README
   G/H describes it as a command and interleaves installation and developer use.
   Double-clicking it opens a command window. It finds Python, activates or
   creates `.venv`, and runs pip on every launch. A partial existing venv wins
   over a working host interpreter. The CUDA replacement can fail yet continue.
2. Backend selection precedes the menu. Blank or invalid answers mean Cloud.
   `SHIMMER_BACKEND_PROFILE` reaches preflight, wizard and server, but the user
   must interpret package/model/provider diagnostics before choosing a task.
3. Preflight (`scripts/preflight.py`) mixes readiness with installation, external
   key-template creation and optional downloads. Even Local calls `step_config`;
   its FAIL rows remain in `_RESULTS`, so the final nonzero status contradicts
   the prose saying absent cloud credentials do not block Local. Some preflight
   failures permit continuing to the menu. This is not a passive startup check.
4. Menu [1] asks Review or Draft. Review invokes `intake_wizard.run`: type a
   folder path, interpret classifications and internal destination paths, edit
   a date cutoff, choose sensitivity, parallelism and document cap. It confirms
   before copying, but the cutoff may already have been written; blank/EOF
   confirms the review import. Target and earlier-version choices occur later.
   Draft requires a typed brief and calls `run_mode_only`, whose confirmation
   does require an explicit yes. Review and Draft launch a pipeline in the
   terminal, independently of the server's queue and console.
5. The wizard owns classification through `convention_parser`, backend flags
   and Normal flags. Its Sensitive branch can switch to Normal on a blank
   answer when Qwen is unavailable, and adds the inactive-layer override when
   LAW-IV masking is inactive. The server has a stricter Sensitive path: neither
   override is supplied and the pipeline refuses with exit 6. These are existing
   divergent choices, not permission to weaken the server boundary.
6. Menu [3] generates a usable random bearer token and holds its SHA256 hash in
   the child environment. It prints the token with HTTP-header instructions.
   A configured hash suppresses creation even if the user no longer has the
   corresponding token. It prints the correct `/console` URL, using
   `SHIMMER_PORT`, but does not open it. The user copies a URL and then a token.
7. Direct server instructions still require a Python command to generate a
   token/hash pair and manual environment syntax. `server.py` defaults to
   `0.0.0.0`, prints the bare root (404) and tunnel instructions. It requires
   the hash and checks local tokenizers using the pipeline's resolved profile.
   `/console` and its fonts are public UI assets; data requests require the
   bearer token. The existing constant-time hash comparison must be retained.
8. The console stores the token in this browser tab's sessionStorage and sends
   it in Authorization headers, never in URLs. Its sign-in screen does not tell
   a desktop user where to get the token. The Submit screen exposes Review/Draft,
   an operating-system file picker, paired/wide, and an unchecked Sensitive box.
   Its Normal explanation incorrectly always says Cloud, including Local.
9. `/submit` always runs the external corpus validator on uploads. An ordinary
   document fails without an ingestion sidecar; users must know an internal
   metadata contract to review their own files. The wizard already distinguishes
   standalone operator documents from integrated external corpora. The console
   does not offer that distinction or document-role selection. Do not manufacture
   a sidecar or weaken validation of a declared integrated bundle.
10. `/submit` stages and queues validated files; `_run_job` constructs actual
    task/question/backend/review-mode/privacy arguments. The pipeline retains
    model approval, LAW-IV, redaction, validation and failure outcomes. Starting
    the server alone starts no review. Readiness should not be confused with a
    completed model load or a completed review.
11. Ctrl+C stops the foreground server in the old menu. There is no server
    lifespan shutdown handler for queued/running work; cancellation and timeout
    terminate individual processes. Browser close does not stop the server.
    Process ownership, explicit stop and restart need an understandable surface.
12. `tools/run_local_demo.ps1` delegates to its Python wrapper and prefers the
    venv. It is a developer performance/run wrapper, not a clickable console.
    Docker `serve`, `run`, `verify` remain developer paths requiring terminal,
    mounts, token environment and port mapping. Docker is not needed for the
    Windows desktop path. `tools/console_preview.py` stubs reviews but its
    `_seed_ontology` writes the live ontology store: do not run it against this
    operator workspace. Use an isolated fixture harness for this item.

## Friction inventory and boundaries

Commands, internal paths and multiple terminals appear in README G/H/I and
RUNBOOK installation/server/client instructions. Environment syntax and token
hashes are mandatory on the direct server path, avoidable but poorly explained
in the menu. Folder typing, generated metadata, pipeline filenames, concurrency
and review-mode names appear in normal intake. Import/dependency errors can
expose raw Python/pip output or close a double-click window with no next action.
There is no one coordinated desktop-to-authenticated-console journey.

Preserve all developer entry points. Reuse classification, model/profile
resolution, privacy flags, the bearer hash gate, actual server configuration and
real validation. No model choice changes, provider generation, real review,
governance changes, new large framework, runtime-state cleanup or push are
authorized. Installation on a clean Windows machine remains the later
fresh-clone item. Missing prerequisites must fail visibly now.
