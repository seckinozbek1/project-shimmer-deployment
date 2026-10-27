# Single-GPU experiment preparation

This workflow prepares a sealed, reproducible comparison bundle locally, then
runs it once on a manually provisioned Lambda instance. It is an experiment tool,
not the console's provider-backed Cloud mode or a general application installer.
Preparation and deployment dry-run do not provision an instance or run models.

## Shared runtime contract and fail-fast order

[tools/cloud_run/runtime.json](../tools/cloud_run/runtime.json) is authoritative.
Its experiment compatibility profile is `>=3.12,<3.13`; the sealed comparison
profile intentionally retains `==3.12.3`, ensurepip 24.0 and the existing locked
Linux wheels. The exact patch pin belongs to that reproducible reference profile,
not to Python source grammar. Do not downgrade source syntax for older images.

`runtime_contract.py` can bootstrap under an older image Python using only the
standard library. It queries candidates, checks the contract, re-queries the
reported absolute executable, and refuses incompatible defaults. A bare Python
name may start this resolver; it cannot select the interpreter that runs Shimmer
without passing the version gate. Required and observed versions are reported.

Maintained experiment preparation follows this order:

1. Local compatible-interpreter/source compile/import preflight before a source
   manifest or ready-to-provision bundle can be produced.
2. After separately authorized instance readiness, resolve and record compatible
   remote Python before source transfer. The sealed controller implements this;
   source-layer manifests also carry the generated experiment bootstrap command.
3. Verify transferred source hashes and complete executable-source coverage.
4. Compile source bytes using the selected interpreter, then import the critical
   Shimmer graph, including `agent_wrapper` and `finding_record`. The bounded
   entrypoint is also imported for the experiment profile. No pipeline or model
   stack is executed by this source gate.
5. Check declared core package versions/imports against `runtime.lock`. Existing
   mismatches fail, without upgrades. Missing packages require explicit installation.
6. If installation was explicitly enabled and packages were missing, install and
   recheck. Never acquire models after a failed check.
7. Acquire pinned models, then hydrate and perform the separately authorized
   bounded workload. A failure prevents a readiness marker.

The sealed path first creates its empty venv with the verified bootstrap Python,
then explicitly resolves that venv as the final executable. All source preflight,
pip, hydration, observer and scoring commands use that same absolute venv path.
The bounded path uses one already prepared compatible environment and never
creates or silently switches environments.

Local source-only validation (no model stack, installation or network):

```powershell
python tools/runtime_contract.py --resolve --path-only
python tools/runtime_contract.py --source .
python tools/prepare_source_layer.py --output output/source_layer.json
python tools/runtime_contract_checks.py
```

For a future separately approved bounded attempt, the maintained entry is
`tools/prepare_remote_experiment.py`. Supply `--root`, the source-layer `--manifest`,
a fresh `--output`, and optionally an explicit `--interpreter` candidate. Without
`--execute`, it only checks readiness; even `--install-missing` cannot install.
`--execute` admits the fixed ordinary short-burst cache preparation and probe;
`--install-missing` additionally permits only missing declared core dependencies.
The existing environment must have compatible transitive dependencies. No automatic
upgrade, provider call, SSH/SCP or provisioning is implemented by this entry.

Historical `docs/fix/remote_short_burst_20260915/` and
`output/remote_short_burst_20260915/` scripts are preserved evidence, not supported
launch targets. Do not rerun their default-Python setup script. The historical
`CLOUD_FULL_RUN_INDETERMINATE` result and unknown inference fields remain unchanged.

Docker derives its Python minor from the same contract. A separate stdlib source
preflight stage must produce its success marker before dependency/model layers
can build. The constant marker preserves cache reuse after compatible source
changes. The image and native dependency stack still require a separately
approved build/runtime validation; source checks alone do not certify them.

## Scope and prerequisites

The fixed profile is ordinary Local Review of the synthetic `clinical_reference`
corpus: dense activation, paired review, dependency DAG, one `cuda:0` worker with
two resident models, Agent Execution Briefs enabled, automatic input language and
English output. Draft and multi-round workloads are excluded on this path: it
seals `dependency_dag`, and the topology rule keeps multi-round to
`reference_serial`, so a multi-round declaration here is refused as such. A
declared multi-round Review is sealed on the ordinary final path instead (see
[Ordinary final loop launches](#ordinary-final-loop-launches)). Semantic ordering
and governance barriers remain intact; DAG selection does not imply concurrency.

This general path is not a loop launch path. `tools/deploy_cloud_run.py` and
`tools/run_remote_experiment.py` refuse any instance named `shimmer-loop-...` and
any loop ledger or `R_INPUTS` argument, so a loop launch can only go through the
guarded ordinary final controller.

The target is one `gpu_1x_a100_sxm4` instance with an A100-SXM4 40 GB. It must provide
Linux x86-64, glibc >= 2.35, Python 3.12.3 with venv/ensurepip 24.0, a compatible
NVIDIA driver and at least 40 GiB free after transfer. The locked runtime uses
PyTorch 2.5.1+cu121. See [runtime.lock](../tools/cloud_run/runtime.lock) and
[models.json](../tools/cloud_run/models.json) for exact packages and revisions.

Local preparation needs a clean tracked checkout at an explicitly selected full
commit SHA, the fixed model caches, an exact Linux CPython 3.12 wheelhouse, the
converted BGE safetensors asset, and preserved comparison evidence. In particular,
`output/a100_smoke_20260914/collected/runtime_frozen.txt` supplies the baseline
runtime, and `output/a100_optimized_20260914/model_hydration.json` supplies saved
revision evidence. These local evidence files are not included in a fresh clone;
the synthetic corpus and its scoring key are tracked. Preparation fails closed when they are absent.
Changing the source commit records a new source identity; it does not establish
quality equivalence with the historical baseline.

The operator workstation also needs OpenSSH, SCP and curl. Reuse an existing SSH
identity with its adjacent `.pub` file. The private key stays outside the bundle.
Preparation and dry-run validate file existence and the public key without reading
or decrypting the private key and without requiring a live SSH agent. Supply the
public key, or select its existing registration, during manual provisioning.

Provider credentials remain in an external private configuration file containing
a `LAMBDA_API_KEY` assignment, or the supported environment variable. The loader
parses that assignment without executing the file. Credential values, private keys
and passphrases must never enter source, bundle contents or diagnostics.

### How the ordinary final tools find the credential file

The ordinary final controller (`tools/ordinary_final_cloud.py`), its status reader
(`tools/ordinary_final_status.py`) and the two live preflights
(`tools/ordinary_final_bound_preflight.py`, `tools/ordinary_final_v3_preflight.py`)
carry no credential path. Each one asks the repository's single resolver,
`resolve_config_path()` in `scripts/agent_wrapper.py`, through the controller's
`credential_path()`, and uses the first file that exists, in this order:

1. the file (or the folder holding `config.py`) named by `SHIMMER_CONFIG_PATH`;
2. the sibling `../api_keys/config.py`, one level above the repository root;
3. the path written in the repository-root `.env_path` pointer.

The lookup happens at the moment of use, never at import: importing these tools
locates nothing. The controller looks just before its first provider call, after
the seal and controller checks, and hands the same path to the watchdog process
and to the independent cleanup check. If no candidate exists, the tool stops with
one line, `No provider credential file found; set SHIMMER_CONFIG_PATH to the
operator credential file`, before any provider call, instance, key or launch
intent. The status reader prints that line as the instance state instead. The
file is only located here; reading it stays with the provider adapter.

### Where the rehearsal works on the Linux side

`tools/ordinary_final_rehearsal.py` asks the local Linux shell (WSL) for its own
home folder when the rehearsal starts, never at import, and works only in
`<that home>/shimmer-rehearsal`. It refuses an empty home, the root `/`, or a path
that is not absolute and normalised. Every `rm -rf` it issues is built by one
function that refuses any target other than that folder or a path below it. The
rehearsal mocks the provider, so it locates no credential file at all.

## Prepare locally

Use a new experiment ID and replace the placeholder paths below with existing
operator-side files. The hourly rate is an explicit operator input. The example
uses $1.99/hour. Preparation takes this path's caps on the command line
(`--soft-usd`, `--hard-usd`, required) and seals them into `experiment.json`
(`soft_budget_usd`, `absolute_budget_usd`); the deployment tool passes those sealed
values to the watchdog. No per-run cap is a code default; the loop's budget rule and
the two reserves are code constants (see the ordinary final section below). This
path does not launch while the loop budget is open (a loop ledger with `budget_open`
and no `budget_close`).

```powershell
# Download exact public runtime wheels locally when the wheelhouse is absent.
python tools/prepare_cloud_wheels.py --download

python tools/prepare_cloud_run.py --experiment-id new_comparison --expected-commit FULL_COMMIT_SHA --hourly-rate 1.99 --credential-file C:/private/config.py --identity-file C:/Users/OPERATOR/.ssh/shimmer_lambda

python tools/cloud_run_checks.py --json
python tools/cloud_run_transport_checks.py
python tools/cloud_run_transfer_checks.py
```

`--model-cache`, `--wheelhouse` and `--output` override preparation locations.
Preparation verifies the source archive, dependency closure, fixed revisions,
actual DAG parser/decorator behavior, credential exclusion and local fixture
checks before writing `READY_TO_PROVISION.json`. A failed mandatory check leaves
a report without a ready seal. Existing destinations are never overwritten.

The bundle contains selected runtime source and the synthetic corpus, hashed
runtime wheels, the prepared BGE asset, fixed model-download specifications,
scoring material and remote observation scripts. It excludes operator documents,
durable state, full local model caches, SSH keys and provider credentials. Qwen
and Phi download at fixed revisions on the target. Expect a multi-gigabyte upload;
measure local transfer capacity before starting a paid instance.

## Deployment dry-run

Without `--execute`, the command validates the bundle and local prerequisites and
prints a plan. It makes no SSH or provider connection. Documentation-only values
are suitable for this step:

```powershell
python tools/deploy_cloud_run.py --host ubuntu@203.0.113.1 --bundle output/cloud_ready/new_comparison --instance-id 00000000000000000000000000000000 --running-since 2026-09-14T00:00:00Z --hourly-rate 1.99 --credential-file C:/private/config.py --identity-file C:/Users/OPERATOR/.ssh/shimmer_lambda
```

A ready seal and dry-run do not prove target hardware compatibility, successful
SSH authentication, inference quality or provider availability.

## Execute after manual provisioning

Provision the matching single instance manually only when ready to deploy.
Record its real IP, ID and timezone-qualified provider running/billing timestamp.
Use that timestamp, not the time the deployment command is invoked.

```powershell
python tools/deploy_cloud_run.py --host ubuntu@INSTANCE_IP --bundle output/cloud_ready/new_comparison --instance-id INSTANCE_ID --running-since RUNNING_UTC --hourly-rate 1.99 --credential-file C:/private/config.py --identity-file C:/Users/OPERATOR/.ssh/shimmer_lambda --interactive-ssh --execute
```

`--interactive-ssh` allows OpenSSH to prompt locally for a protected key's
passphrase. The deployment tool does not receive it. If the explicit identity is
already unlocked in an agent, batch operation can omit this flag. A separate
per-experiment known-hosts file accepts the first host key and rejects changes.

The controller arms an independent local watchdog, checks the provider instance
identity, class, count, status and rate, then verifies SSH, Python and GPU identity.
It resolves compatible Python before transfer, creates an exclusive directory,
transfers and verifies the bundle, and compiles/imports source using the selected
venv interpreter before installing missing hashed wheels. Dependency imports and
CUDA readiness must pass before model acquisition and the single observed run.
It does not repeat local audits or behavioral tests on the paid node.

The upload timeout defaults to 1,200 seconds and is configurable through
`--upload-timeout-seconds`. The effective deadline is bounded by remaining budget
with 120 seconds reserved for termination. SSH/SCP use a 10-second connection
timeout and 15-second keepalives with three missed replies allowed. These detect
an unresponsive peer, but cannot detect every stuck channel on a responsive peer.

## Collection, budgets and failure handling

The controller collects only experiment evidence, verifies its hashes and requests
termination. Local records live under `output/cloud_collected/EXPERIMENT_ID/`.
Permanent attempt directories prevent reusing an experiment ID. There are no warm
runs or automatic model retries. Failure requests teardown instead of leaving the
instance idle for investigation.

Budget accounting includes setup, inference, scoring and collection. The watchdog
(`tools/cloud_run_watchdog.py`) requires `--soft-usd` and `--hard-usd`; the
deployment tool supplies the experiment's sealed caps. It resolves the
instance's name first, with retries, refuses a `shimmer-loop-` instance, and on a
failure terminates only an instance whose name it resolved and which is not a loop
instance; anything else is left to the operator. It requests termination 120 seconds before the calculated hard ceiling
and retries until the provider verifies termination. An emergency termination after
a failed deployment requests termination at once and reads no cap. Keep the operator workstation and its
watchdog running. A provider outage can prevent timely termination; an unverified
termination is never reported as verified. The configured budget is an enforced
termination policy, not a guarantee against provider or network failure.

Lifecycle records distinguish instance running, SSH readiness, deployment,
dependency/model readiness and actual first generation. Evidence includes model
calls, GPU samples, scheduler waits, measured concurrency, critical-path timing,
scoring and teardown. Completion requires one finished run, successful scoring,
collected hashes and provider-verified termination.

A remote process can finish while automated collection fails. Preserve the
original controller classification. Separately recovered artifacts require their
own integrity and scoring checks and do not turn an aborted deployment into a
clean benchmark. The [optimized A100 run report](fix/A100_OPTIMIZED_RUN.md) documents
one such recovery, its performance limitations and verified teardown. Its consumed
experiment ID and sealed bundle must not be reused.

## Ordinary final loop launches

The ordinary final path runs the frozen Producer and Auditor checkpoints on one
rented single-GPU instance, from a bundle sealed by
`tools/prepare_ordinary_final_run.py` and launched by
`tools/ordinary_final_bound_cloud.py` through the controller
`tools/ordinary_final_cloud.py`. Every launch on this path is a loop launch.

### Seal a bundle

```powershell
python tools/prepare_ordinary_final_run.py --output-dir BUNDLE_FOLDER --ledger LEDGER.jsonl --forecast-minutes MINUTES --storage-forecast-usd DOLLARS
```

| Sealer flag | Meaning |
|---|---|
| `--output-dir` | The new bundle folder; an existing execution identity is never resealed. |
| `--source-commit` | The commit the runtime source is bound to (default `HEAD`); the working tree must match it. |
| `--reuse-assets` | Bind a previously verified asset archive instead of building a second copy. |
| `--inputs-from` | Folder holding `runtime.candidate.lock` and `provider_inventory.json` (default: the `docs/fix` bundle). |
| `--workload` | A test archive or folder: `context/`, `conventions/`, `_review_targets.json` and, for multi-round, `case_manifest.json`. Default: the clinical workload. |
| `--exposure` | `exposed` (default) or `sealed`. |
| `--test-manifest` | Role B's seal manifest, for a sealed bundle. |
| `--protected-test` | Only on a sealed bundle prepared by role B. |
| `--ledger` (repeatable), `--forecast-minutes`, `--storage-forecast-usd` | The IV.3 inputs. All three are required. |

The sealer writes the budget into the manifest from the live price in the
provider inventory and the loop ledger: the ordered instance candidates (the
A10 first, then any other single-GPU x86-64 type with at least the run's VRAM at
a live price no more than twice the A10's last recorded price, cheapest first),
each candidate's rate cap, the soft cap (the forecast) and the hard cap (the
per-run cap), and both reserves. None of these figures is typed in.

A sealed bundle (`--exposure sealed`) is built outside the repository from the
test archive. Its seal carries the SHA-256 of role B's test manifest, the test
archive hash and the code commit, and the sealer prints counts only; an exposed
bundle's seal says `exposed, no manifest`. The sealer refuses to seal
`SHIMMER_INST_FINDER=off` unless the bound constitution holds a ratified amendment
naming INST_FINDER and SHIMMER_INST_FINDER, using the pipeline's own test read
from the bound source. Paths outside the runtime prefixes enter the source
archive only when listed in `ARCHIVE_EXTRAS` in the sealer; a listed path the
bound commit lacks fails the build in one line, and test material never travels
inside the source archive.

A workload carrying `case_manifest.json` is sealed as a declared multi-round
Review. The case manifest must be the live schema (schema version 1, the live
field set, `fixture: false`, every source span measured on the bundled document
text). It is sealed as a support file, its hash is also recorded as
`case_manifest_sha256`, and the run flags are the ordinary flags under
`reference_serial` with no topology file, followed by `--multi-round
--multi-round-manifest case_manifest.json`. The runner admits the workload only
when it is declared, sealed and valid, and its assessment passes a multi-round
run only when the saved case record shows outcome `reviewed` and activation
`activated`.

### Launch

The bundle then goes through the existing steps (asset verification, the bound
local reverification `tools/ordinary_final_bound_reverify.py` and the live
preflight `tools/ordinary_final_bound_preflight.py`, which now reads the sealed
candidates with the same type rule as the launch) before the launch:

```powershell
python tools/ordinary_final_bound_cloud.py --bundle BUNDLE_FOLDER --ledger LEDGER.jsonl --purpose dev-smoke --forecast-minutes MINUTES --storage-forecast-usd DOLLARS --forecast-includes-upload
```

| Wrapper flag | Meaning |
|---|---|
| `--bundle` | The sealed bundle. |
| `--ledger` | The loop ledger: read by the guard, and it receives the launch and termination lines. Required. |
| `--read-ledger` (repeatable) | Another ledger the guard reads (role R's). |
| `--r-inputs` | `R_INPUTS.json` when role R launches. |
| `--purpose` | A short identifier saying why this run exists (lower case, digits, hyphens, at most 40 characters). Required. |
| `--forecast-minutes`, `--storage-forecast-usd` | The measured basis and the storage forecast. Required. |
| `--forecast-includes-upload` | States that the forecast includes the asset upload. Required whenever no asset-copy declaration applies to this bundle. |
| `--output-dir` | Run in a fresh folder `<output-dir>/<bundle name>` instead of in the bundle; the asset archive is read where it is. |
| `--test-manifest`, `--frozen-tag` | Required for a sealed run. |
| `--batch` | A batch file `{"entries": [{"item", "arm", "bundle"}]}`. |
| `--test-version`, `--test-author`, `--key-author`, `--scorer-author`, `--scorer-version` | Report fields for `RUN_REPORT.md`. |
| `--detach` | Start the controller as a detached process and return; its output goes to `controller_detached.log` in the bundle and its pid to `controller_process.json`. |

Before the launch request, `tools/loop_budget_guard.py` decides from the ledgers
and the live price. The `--ledger` must be one the reaper reads (the private ledger
or R's); the guard always reads both of those beside any `--read-ledger`, needs a
`budget_open` line among them, and holds an exclusive lock beside the ledger from
its decision through the intent line, reading the provider inventory again just
before it. It refuses, in one line, when another loop instance is running (an
open launch in a ledger, or a `shimmer-loop-` name in the provider inventory),
when the per-run cap `min(1.5 x forecast, 50 - spend - caps of running loop
instances - storage forecast - 1)` is below the forecast (measured minutes times
the live price times 1.3), or when the capped run time does not cover the forecast
time plus the run's stop reserve. The cap rule alone keeps spend plus forecast plus
storage at or below 49 dollars. Spend is counted once per launch across every
ledger read; a termination closes a launch by its instance id or its name. The controller also refuses when the sealed hard cap no longer fits
under the cap at the live price; reseal in that case.

The instance type follows the IV.3 rule: `gpu_1x_a10` in `us-east-1`, polling the
free inventory for up to 30 minutes, then the sealed candidates in order, each at
no more than its sealed rate cap and twice the A10's reference price. The
runner's hardware check reads the selected candidate's requirements, and the
watchdog turns the manifest's caps, the candidate's rate cap and the sealed
reserves into deadlines.

The instance is always named `shimmer-loop-...`. The `launch_intent` line, with
the deadline, is written to the ledger before the launch request; `launch` and
`termination` lines follow; a launch recovered after a lost reply gets its
`launch` line before its termination, and the ledger is closed in its own step
before the rest of the cleanup. A ledger line carries only time, instance id and
name, type, region, price, purpose, forecast, cap, deadline, actual minutes and
actual cost (plus the reaper's `by` and `reason`), and the writer refuses any other
field. The purpose is a short identifier (lower case, digits, hyphens). While an instance can exist
the controller keeps the workstation awake through `tools/loop/keep_awake.py`,
and the ledger deadline is what the loop reaper `tools/loop/instance_reaper.py`
acts on if the controller itself dies.

### Sealed runs and batches

A sealed run is launched only with the same test manifest and the frozen tag;
the controller requires the bundle hash and the tag's commit to equal the seal's
and the run folder to sit outside the repository. It prints counts and timings
only (`phase N at S s`), attaches no provider storage, never reads or seeds the
asset copy, and writes nothing in the repository except ledger lines.

`--batch` runs several bundles in one instance session. Every item runs arm B3
then arm B1 before the next item starts, the first scheduled entry (the first
item's B3) must be the bundle the session was launched with, and the bundles share one environment, one asset archive and one sealed budget.
Each entry gets its own run folder under `batch/`, its own seal entry,
authorization and collected evidence, so a stop leaves every finished pair
complete.

### Asset copy

The provider-side asset copy is used only when the bundle carries the operator's
`asset_copy_declaration.json` with `operator_authorized: true` and this bundle's
own `assets_sha256` (`tools/declare_asset_copy.py` writes it from the bundle's
digest). A declaration for another archive is refused, the controller never
writes one, and a launch outside `us-east-1` does not use it. Without a MATCH the
archive is uploaded, and the launch plan must say the forecast includes that
upload. A new bundle has no declaration, so its forecast includes the upload.

### Report and binding

```powershell
python tools/analyze_ordinary_final_run.py --bundle RUN_FOLDER
python tools/analyze_ordinary_final_run.py --bundle RUN_FOLDER --batch
```

The analyser writes `FINAL_STATUS.json` and `RUN_REPORT.md` (Annex A 11.12). The
report starts with the purpose line and the sealed-or-exposed line, then lists
every 11.12 field: date, code commit, test version, test manifest hash, authors,
scorer version, models and checkpoints, decoding settings, backend and machine,
instance type and price, cost, the scored fields (left to the scorer and said
so), agents withheld (FACT_CHECKER with both of its reasons), the
`SHIMMER_INST_FINDER` value, multi-round, asset copy MATCH or not, role
separation for a sealed run, and what the result does not show. A field that
does not apply says why. `--batch` writes one report per batch run folder.

The controller is bound to the bundle it was sealed with. Loop S2 changed six of
the seven bound files (`tools/cloud_run_common.py`, `tools/cloud_run_watchdog.py`,
`tools/ordinary_final_bound_cloud.py`, `tools/ordinary_final_cloud.py`,
`tools/ordinary_final_run.py`, `tools/ordinary_final_watchdog.py`), so every bundle
sealed before S2 refuses with `Controller source changed` and must be sealed
again.

The rehearsal (`tools/ordinary_final_rehearsal.py`) launches the same way against
its mocked provider: each rehearsal bundle gets a fresh ledger of its own,
`rehearsal_ledger.jsonl`, beside it (never the loop's ledger), the instance name
`shimmer-loop-rehearsal`, the budget fields a new manifest carries, and the
current controller binding.
