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
deployment tool supplies the experiment's sealed caps. The deployment tool
(`tools/deploy_cloud_run.py`), not the watchdog, resolves the
instance's name first, with retries, refuses a `shimmer-loop-` instance, and on a
failure terminates only an instance whose name it resolved and which is not a loop
instance; anything else is left to the operator. The watchdog requests termination 120 seconds before the calculated hard ceiling
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
| `--arm` | `B3` (default, the full pipeline) or `B1` (the bare-model baseline `benchmark/baselines/bare_model.py`). Written into every manifest as `arm`. |
| `--items` | B1 only: the adapter's `items.json` (item ids, no gold), sealed as a support file. |
| `--b1-checkpoints` | B1 only: a JSON list of passes `{"name", "checkpoint", "args"}` (`checkpoint` may be left out, see below), run in that order, each into `evidence/b1/<name>`. Each `args` list may hold only options `bare_model.py` itself takes (see below). A replay pass `{"name", "replay": true, "args"}` runs `replay_prompts.py` instead (section "The E evidence run"). |
| `--replay-prompts` | Exposed B1 only: the `replay_prompts.json` a replay pass reads (D-061 item 4), sealed as a support file. |

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
from the bound source.

The producer's attention and prefill (D-058, D-061, D-063) are sealed the same way,
in the manifest's `environment`, and the runner replaces every `SHIMMER_` variable
with the sealed ones, so the instance's `scripts/final_models.py` loads the producer
with exactly the sealed values. With nothing set at sealing they are
`SHIMMER_PRODUCER_ATTENTION=sdpa`, `SHIMMER_PRODUCER_ATTENTION_DECISION=D-063`,
`SHIMMER_PRODUCER_PREFILL_CHUNK=one_shot` and `SHIMMER_PRODUCER_PREFILL_DECISION=D-063`
(option A, adopted by D-061's declared fallback in D-063): every producer call runs
sdpa pinned to the memory-efficient backend and prefills its prompt in one shot,
through the one generate helper (`final_models.generate_with_prefill`). B1 runs the
same. The models `_load_qwen` loads run sdpa pinned the same way, one shot. Each
reply record names the kernel, the prefill and the decisions, and what the prefill
measured (chunks, tail tokens, prefill seconds). v5 to v12 ran the producer eager
in one shot, the kernel it was trained and evaluated with. A measurement run is
sealed otherwise by setting the variables in the sealing shell, each with the
recorded decision that asks for it, for example E (eager, chunks of 512 tokens
through the KV cache, 2 tokens left to generation; D-061):

```powershell
$env:SHIMMER_PRODUCER_ATTENTION = 'eager'
$env:SHIMMER_PRODUCER_ATTENTION_DECISION = 'D-061'
$env:SHIMMER_PRODUCER_PREFILL_CHUNK = '512'
$env:SHIMMER_PRODUCER_PREFILL_DECISION = 'D-061'
python tools/prepare_ordinary_final_run.py --output-dir BUNDLE_FOLDER --ledger LEDGER.jsonl --forecast-minutes MINUTES --storage-forecast-usd DOLLARS
Remove-Item Env:SHIMMER_PRODUCER_ATTENTION, Env:SHIMMER_PRODUCER_ATTENTION_DECISION, Env:SHIMMER_PRODUCER_PREFILL_CHUNK, Env:SHIMMER_PRODUCER_PREFILL_DECISION
```

The sealer evaluates the bound `final_models.producer_attention` and
`final_models.producer_prefill` (through `attention_setting` and `prefill_setting`)
and refuses, in one line, eager without a decision, an attention decision with sdpa
other than D-063, a chunk size without a prefill decision, a prefill decision with
`one_shot` other than D-063, a decision that is not `D-NNN`, or any other value; a
bound `final_models` from before D-061 is refused. The Auditor896 classifier is not governed by these
settings: it loads eager, as its runtime contract says. The report's backend field
states the sealed attention and prefill (section "Report and binding").

Paths outside the runtime prefixes enter the source
archive only when listed in `ARCHIVE_EXTRAS` in the sealer (today
`benchmark/adapters/` and `benchmark/baselines/`, so the B1 and B2 tools and the
adapters they import reach the instance; their `fixtures/` folders and `*_checks.py`
files stay out); a listed path the bound commit lacks fails the build in one line,
and test material never travels inside the source archive.

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

A B1 bundle (`--arm B1`) is sealed from the same workload as its B3 twin. Its
manifest carries `arm: B1` and `b1`: the passes (each a short name, the
checkpoint it loads and the `bare_model.py` arguments that pin it, for example its
`--expect-digest`; the manifest keeps them under `checkpoints`), the
item ids of the bundle's one document (the items in `items.json` whose
`document_id` is the stem of the one target in `_review_targets.json`) and the
digest of `items.json`, which travels as a support file and never inside the test
archive. A checkpoint may not carry `--bundle`, `--items`, `--out`,
`--checkpoint` or `--development`, which the runner sets itself. Everything else
it carries must be one of the options `bare_model.py`'s own parser takes
(`--agent`, `--profile`, `--max-new-tokens`, `--expect-model-id`,
`--expect-digest`, `--expect-decoding`, `--prefill-chunk`, `--prefill-decision`,
`--attention`, `--attention-decision`, each followed by its value or written
`--option=value`, and the flag `--sensitive` alone), spelled in full: the parser
takes no abbreviation, and the sealer refuses an unknown option, a missing value or
a flag with a value, so a checkpoint the instance would refuse is refused at
sealing instead. The runner's `B1_SEALED_ARGS` lists these options, and a
controller check holds it, with the runner's own options, equal to the parser's.
B1 follows the producer (D-061, D-063): its run proper is sdpa pinned to the
memory-efficient backend with one-shot prefill under D-063, and needs neither
option. `--attention` is `sdpa` (the default) or `eager`; `eager` is accepted only
together with `--attention-decision D-NNN`, the recorded decision that asks for the
measurement pass, and `--attention-decision` with `sdpa` only when it is `D-063`.
`--prefill-chunk` is `one_shot` (the default) or a positive number of tokens (E is
512); a chunk size is accepted only together with `--prefill-decision D-NNN`, and a
`--prefill-decision` with `one_shot` only when it is `D-063`. The sealer refuses
each case `bare_model.py` would refuse (a controller check holds the two rules
equal case by case).

A pass's `name` is a free label: lower case letters, digits and underscores,
unique in the bundle. It names the pass's output folder `evidence/b1/<name>`.
Its `checkpoint` is `tuned` or `base`, and the runner passes it to `bare_model.py`
as `--checkpoint`. A pass sealed without `checkpoint` loads the checkpoint its
name names, as every pass did before D-056 condition 6, so such a pass must be
named `base` or `tuned`; a bundle sealed with `{"name", "args"}` passes keeps its
meaning. Each checkpoint's `--expect-digest` is the digest `bare_model.py` computes
for that checkpoint, `<revision>:<model.safetensors sha256>` for the base and that
followed by `+adapter:<adapter sha256>` for the tuned producer (both from
`config/final_models.json`, recorded in `docs/loop/VERSIONS.md`); a run whose
loaded digest differs stops before its first item. A B1 bundle is
never multi-round. A B3 bundle carries none of these fields; a manifest sealed
before S5 has no `arm` and is a B3 bundle.

On the instance the same runner, `ordinary_final_run.py`, runs both arms and keeps
every guard for both: the authorization (which must name the arm the bundle was
sealed with; an authorization naming no arm is a B3 one), `RUN_CLAIMED`, the
budget-stop thread with its `os._exit(124)`, the sealed model cache, the pinned
runtime and the network denial. For a B1 bundle it then loads the sealed
project's `benchmark/baselines/bare_model.py` in its own process, never imports
the pipeline, and calls its `main()` once per sealed pass, in order, with
`--bundle <project>/input --items <bundle>/items.json --out
evidence/b1/<name> --checkpoint <checkpoint>` followed by that pass's
sealed arguments. It writes `evidence/b1/expected_records` (items times
passes) first, for the progress reader. The assessment in
`evidence/result.json` passes a B1 entry only when every pass returned 0
and left exactly one reply record per item in its own folder (each item's label
naming one record's call id) and no other record; no pipeline marker is asked
for, and `pipeline_exit_code` is null. The controller's cleanup stops a B1 run
exactly as it stops a B3 run, by the runner's name.

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
| `--batch` | A batch file `{"entries": [{"item", "arm", "bundle"}], "form": "paired"}`; `form` is `paired` (the default) or `b3_only` (exposed bundles only). |
| `--test-version`, `--test-author`, `--key-author`, `--scorer-author`, `--scorer-version` | Report fields for `RUN_REPORT.md`. |
| `--detach` | Start the controller as a detached process and return; its output goes to `controller_detached.log` in the bundle and its pid to `controller_process.json`. |

Before the launch request, `tools/loop_budget_guard.py` decides from the ledgers
and the live price. The `--ledger` must be one the reaper reads (the private ledger
or R's); the guard always reads both of those beside any `--read-ledger`, needs a
`budget_open` line among them, and holds an exclusive lock beside the ledger from
its decision through the intent line, reading the provider inventory again just
before it. It refuses, in one line, when another loop instance is running (an
open launch in a ledger, or a `shimmer-loop-` name in the provider inventory),
when the per-run cap `min(1.5 x forecast, ceiling - spend - caps of running loop
instances - storage forecast)` is below the forecast (measured minutes times the
live price times 1.3), or when the capped run time does not cover the forecast time
plus the run's stop reserve. The ceiling is the smaller of the reaper's hard stop
and the budget less one dollar, so the cap rule alone keeps spend plus forecast plus
storage at or below both. The budget is not a number in the code: the guard and the
reaper read it from the latest `budget_open` or `budget_change` line in the ledgers
(the hard stop is that line's `hard_stop_usd`, or the budget less one dollar when
the line names none). A launch with no readable budget line is refused, and the
reaper terminates every loop instance while it can read none. An open launch accrues
spend only up to its recorded deadline; past it, with no instance of its name
listed, the reaper closes it with one termination line charged to the deadline (a
ceiling, counted as actual and never refunded), written to the ledger that holds
the launch. Spend is counted once per launch across every
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
complete. Each entry's `arm` in the batch file must equal the `arm` its bundle
was sealed with (refused before any launch otherwise), and the controller writes
it into the entry's authorization, which the runner checks again on the instance.

A batch file with `"form": "b3_only"` carries exposed bundles that have no B1
arm (regression bundles, multi-round cases, the development suite): every entry
is B3, each item appears once, the entries run in the order given and are paired
with nothing (`paired_with` is null in each seal entry). A sealed run refuses
this form before any provider call; the paired form still refuses a batch
without its B1 entries.

Past the soft budget the controller starts no new remote work except stopping the
workload and collecting evidence. A batch entry's own collection (its
`batch_pack_evidence` and `batch_evidence_hash` phases, then the download) is part
of that exemption, so an entry that finishes past the soft budget is still
collected into its own run folder; the next entry is then refused and the session
evidence is collected as before.

### Stage, seal and launch a batch of benchmark bundles

A benchmark build is not yet a workload. The adapters (`benchmark/adapters`) and
the generators (`benchmark/generators`) write each bundle as `context/` (with
`_review_targets.json` inside it), `conventions/` and `answer_key.json`, and an
adapter writes the item table `items.json` beside its bundles. The sealer wants
the targets file at the top of the workload folder and refuses anything but
`context/`, `conventions/`, `_review_targets.json` and `case_manifest.json`.
`tools/stage_workload.py` makes the one from the other:

```powershell
python tools/stage_workload.py --build BUILD_FOLDER --out STAGED_FOLDER
python tools/stage_workload.py --bundle BUILD_FOLDER/BUNDLE --out WORKLOAD_FOLDER --items-out ITEMS.json
```

With `--build` every bundle of the build is staged: `STAGED_FOLDER/<bundle>/workload/`
is the sealer's `--workload`, and, when the build has an `items.json`,
`STAGED_FOLDER/<bundle>/items.json` is the sealer's `--items` for that bundle's B1
twin. The tool copies `context/`, `conventions/` and `case_manifest.json` byte for
byte (the sealer normalises line endings, not the staging) and moves the targets
file to the top. It never copies the answer key, `parts.json` or any other build
record, and a file under `context/` or `conventions/` whose name reads like a key
(`answer`, `key` or `gold` as a word of its name) refuses the whole staging before
anything is written. The item table holds only the bundle's own document's items,
with the four fields `bare_model.py` reads (`item_id`, `document_id`, `rule_id`,
`benchmark`), and is written outside the workload folder. The tool prints counts
only. A generator build has no `items.json`, so its bundles are staged for B3 only.
Third-party documents are staged only under the ignored `external/<name>/s05/`
(H17), never inside a tracked folder. Gate check 287 holds this on a synthetic
fixture.

Then seal one B3 and one B1 bundle per item from the same staged workload, all
binding the same asset archive (the first bundle builds or reuses it, the others
pass `--reuse-assets` with it), with the same ledger and forecast inputs:

```powershell
python tools/prepare_ordinary_final_run.py --output-dir external/NAME/s05/ITEM_B3 --workload STAGED_FOLDER/ITEM/workload --reuse-assets ASSET_BUNDLE --ledger LEDGER.jsonl --forecast-minutes MINUTES --storage-forecast-usd DOLLARS
python tools/prepare_ordinary_final_run.py --output-dir external/NAME/s05/ITEM_B1 --workload STAGED_FOLDER/ITEM/workload --arm B1 --items STAGED_FOLDER/ITEM/items.json --b1-checkpoints B1_CHECKPOINTS.json --reuse-assets ASSET_BUNDLE --ledger LEDGER.jsonl --forecast-minutes MINUTES --storage-forecast-usd DOLLARS
```

`B1_CHECKPOINTS.json` names the base checkpoint first and the tuned one second,
each pinned by its recorded model id and digest:

```json
[{"name": "base", "args": ["--expect-model-id", "MODEL_ID", "--expect-digest", "REVISION:WEIGHTS_SHA256"]},
 {"name": "tuned", "args": ["--expect-model-id", "MODEL_ID", "--expect-digest", "REVISION:WEIGHTS_SHA256+adapter:ADAPTER_SHA256"]}]
```

The first benchmark dry run (L2) also measures D-056 condition 6: B1 eager against
sdpa for both checkpoints, one repeat of the tuned sdpa pass, and each pass's peak
GPU memory. Its `B1_CHECKPOINTS.json` seals five passes. The base passes come
first: the tuned producer stays resident once loaded, and a pass's peak memory
counts everything on the device, so a base pass run after a tuned one would count
the tuned producer's weights too (each pass records what was allocated when its
counters were reset, `allocated_at_start_bytes`, which shows it):

```json
[{"name": "base", "checkpoint": "base", "args": ["--expect-model-id", "MODEL_ID", "--expect-digest", "REVISION:WEIGHTS_SHA256"]},
 {"name": "base_eager", "checkpoint": "base", "args": ["--expect-model-id", "MODEL_ID", "--expect-digest", "REVISION:WEIGHTS_SHA256", "--attention", "eager", "--attention-decision", "D-056"]},
 {"name": "tuned", "checkpoint": "tuned", "args": ["--expect-model-id", "MODEL_ID", "--expect-digest", "REVISION:WEIGHTS_SHA256+adapter:ADAPTER_SHA256"]},
 {"name": "tuned_eager", "checkpoint": "tuned", "args": ["--expect-model-id", "MODEL_ID", "--expect-digest", "REVISION:WEIGHTS_SHA256+adapter:ADAPTER_SHA256", "--attention", "eager", "--attention-decision", "D-056"]},
 {"name": "tuned_repeat", "checkpoint": "tuned", "args": ["--expect-model-id", "MODEL_ID", "--expect-digest", "REVISION:WEIGHTS_SHA256+adapter:ADAPTER_SHA256"]}]
```

`MODEL_ID`, `REVISION`, `WEIGHTS_SHA256` and `ADAPTER_SHA256` are the producer's
`model_id`, `revision`, `base_hashes["model.safetensors"]` and
`files.adapter.sha256` in `config/final_models.json`. L2 was sealed before D-060:
its passes ran sdpa by default and eager as the measurement. A bundle sealed under
D-061 refused that file (eager was then the default and took no decision); from
D-063 on it is admitted again, its unpinned sdpa default now the pinned, one-shot
default recorded under D-063. In final mode `scripts/final_models.py` sets strict
determinism for the whole process, so a `_repeat` pass measures whether a pass is
byte-identical when run again.

#### The E evidence run (D-061 item 4) and the measurement passes from D-063 on

E (eager, chunked prefill) was to be adopted for S8 only on its own evidence
(D-060's thresholds: at least 90 percent of the tuned checkpoint's replies
byte-identical with one-shot eager and at least 95 percent of labels agreeing). L3e
ran it, sealed under D-061 with E as the run proper, and E missed the threshold;
D-061's declared fallback adopted option A (D-063). A bundle sealed from D-063 on
refuses L3e's pass file (its one-shot and sdpa passes name decisions the defaults
no longer take). The same measurements are sealed from D-063 on as one exposed B1
bundle carrying the four tuned passes, in this order, and a replay pass over B3's
own producer prompts:

```json
[{"name": "tuned", "checkpoint": "tuned", "args": ["--expect-model-id", "MODEL_ID", "--expect-digest", "REVISION:WEIGHTS_SHA256+adapter:ADAPTER_SHA256"]},
 {"name": "tuned_eager", "checkpoint": "tuned", "args": ["--expect-model-id", "MODEL_ID", "--expect-digest", "REVISION:WEIGHTS_SHA256+adapter:ADAPTER_SHA256", "--attention", "eager", "--attention-decision", "D-061"]},
 {"name": "tuned_e", "checkpoint": "tuned", "args": ["--expect-model-id", "MODEL_ID", "--expect-digest", "REVISION:WEIGHTS_SHA256+adapter:ADAPTER_SHA256", "--attention", "eager", "--attention-decision", "D-061", "--prefill-chunk", "512", "--prefill-decision", "D-061"]},
 {"name": "tuned_repeat", "checkpoint": "tuned", "args": ["--expect-model-id", "MODEL_ID", "--expect-digest", "REVISION:WEIGHTS_SHA256+adapter:ADAPTER_SHA256"]},
 {"name": "replay", "replay": true, "args": ["--decision", "D-061"]}]
```

`tuned` is the run proper (option A: sdpa, memory-efficient backend pinned, one
shot, D-063), `tuned_eager` the one-shot eager reference (the kernel the producer
was trained with), `tuned_e` E, and `tuned_repeat` the determinism check. Each pass
records its peak GPU memory and, per call, the prefill (chunks, tail tokens,
prefill seconds; summed and maximised in `b1_summary.json` under `prefill_time`).
Compare with `bare_model.py compare` (`tuned` against `tuned_eager`, `tuned`
against `tuned_repeat`, `tuned_e` against `tuned_eager`). The items of the short
documents are under 1,536 tokens, so the evidence on prompts of at least three
chunks comes from the replay pass and from the long documents.

The replay pass runs `benchmark/baselines/replay_prompts.py` on a sealed
`replay_prompts.json`, written beforehand on the laptop from an earlier run's
reply records (no model; it reads only the saved payloads, never a reply, a label
or a key, and refuses a sensitive run's hashed records and any folder under
`benchmark/keys/`):

```powershell
python benchmark/baselines/replay_prompts.py extract --records RUN_L2/evidence/run/RUN_ID/audit/model_replies --records RUN_L2_2/evidence/run/RUN_ID/audit/model_replies --out external/NAME/s05/replay_prompts.json
python tools/prepare_ordinary_final_run.py --output-dir external/NAME/s05/E_ITEM1_B1 --workload STAGED_FOLDER/ITEM1/workload --arm B1 --items STAGED_FOLDER/ITEM1/items.json --b1-checkpoints E_PASSES.json --replay-prompts external/NAME/s05/replay_prompts.json --reuse-assets ASSET_BUNDLE --ledger LEDGER.jsonl --forecast-minutes MINUTES --storage-forecast-usd DOLLARS
```

`--replay-prompts` is accepted only for an exposed B1 bundle; the file travels as
a support file (`replay_prompts.json`, its digest and prompt count in the
manifest's `b1.replay`), never in the source archive, and the runner refuses a
replay pass in a sealed run. A replay pass is `{"name", "replay": true, "args"}`;
its `args` may hold only `--paths` (default `e,one_shot,sdpa,e_repeat`),
`--decision` (required exactly when a measurement path, `e`, `one_shot` or
`e_repeat`, is run; `sdpa` is the run proper's setting under D-063) and `--max-new-tokens` (default: each prompt's own recorded allowance); the
runner sets `--prompts` and `--out`. On the instance it loads the tuned producer
once and runs every prompt through each path, writing one reply record per prompt
per path (hashes only) and `evidence/b1/replay/replay_measurement.json`: per path
the peak GPU memory and prefill seconds, per prompt the reply's SHA-256, output
tokens and prefill, and per pair of paths (e against one_shot, e against e_repeat,
sdpa against one_shot, e against sdpa) the byte-identical, equal-JSON and failure
counts over every prompt and over the prompts of three chunks or more. An
out-of-memory error on one path is recorded for that prompt and the path goes on
(that is the measurement), never retried. The report's B1 row states each path's
peak memory and longest prefill and each pair's counts. The 30,720-token
measurement at full context is one more replay prompt of that length (an L2 item
prompt or a document cut to it); B3's longest development prompt with the other
models loaded is read from a B3 entry's own reply records (`prefill` per call)
and its run's peak GPU memory.

Each pass's `b1_summary.json` carries `gpu_memory`: the peak allocated and the
peak reserved bytes from the moment the model was loaded and verified to the end
of the last item (null on a machine without CUDA). After collection the passes are
compared with `bare_model.py compare`, which needs no model:

```powershell
python benchmark/baselines/bare_model.py compare --a RUN/evidence/b1/base --b RUN/evidence/b1/base_eager --out RUN/analysis/b1_base_eager.json
python benchmark/baselines/bare_model.py compare --a RUN/evidence/b1/tuned --b RUN/evidence/b1/tuned_eager --out RUN/analysis/b1_tuned_eager.json
python benchmark/baselines/bare_model.py compare --a RUN/evidence/b1/tuned --b RUN/evidence/b1/tuned_repeat --out RUN/analysis/b1_tuned_repeat.json
```

Each comparison file gives, per item, whether the two replies are byte-identical
(their recorded SHA-256 and byte length, so a sensitive pass compares too) and
whether the two labels agree (the same label, or both abstained), with the counts.
It holds item ids, booleans and counts only, never a reply's text or a label.

The batch file lists every item's B3 and B1 bundles, the first item's B3 first
(it is the bundle the session is launched with):

```json
{"form": "paired", "entries": [
  {"item": "ITEM1", "arm": "B3", "bundle": "external/NAME/s05/ITEM1_B3"},
  {"item": "ITEM1", "arm": "B1", "bundle": "external/NAME/s05/ITEM1_B1"},
  {"item": "ITEM2", "arm": "B3", "bundle": "external/NAME/s05/ITEM2_B3"},
  {"item": "ITEM2", "arm": "B1", "bundle": "external/NAME/s05/ITEM2_B1"}]}
```

and the launch names the first B3 bundle and the batch file, with the run folder
outside the repository:

```powershell
python tools/ordinary_final_bound_cloud.py --bundle external/NAME/s05/ITEM1_B3 --batch BATCH.json --output-dir external/NAME/s05/runs --ledger LEDGER.jsonl --purpose dev-NAME --forecast-minutes MINUTES --storage-forecast-usd DOLLARS --forecast-includes-upload --detach
```

On the instance each B1 entry runs `bare_model.py` once per sealed pass, in the
sealed order, into `evidence/b1/<name>/` (`evidence/b1/base/` and
`evidence/b1/tuned/` for the two-pass file above), each holding one reply record
and one label per item and its `b1_summary.json`. Afterwards
`tools/analyze_ordinary_final_run.py --bundle RUN_FOLDER --batch` writes one report
per entry. For bundles with no B1 twin (a generator build, regression bundles,
multi-round cases) use `"form": "b3_only"` with B3 entries only.

### Asset copy

The provider-side asset copy is used only when the bundle carries the operator's
`asset_copy_declaration.json` with `operator_authorized: true` and this bundle's
own `assets_sha256` (`tools/declare_asset_copy.py` writes it from the bundle's
digest). A declaration for another archive is refused, the controller never
writes one (for the autonomous loop of 27 October 2026 only, the operator
authorised the loop to write declarations for the bundles it runs and to replace
the filesystem's archive after recording the old digest; `docs/loop/DECISIONS.md`
D-028), and a launch outside `us-east-1` does not use it. Without a MATCH the
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

The backend field names the producer's sealed attention and prefill (D-058,
D-060, D-061, D-063): for the default, "producer and B1 sdpa, prefilled in one
shot, memory-efficient backend pinned (D-063); differs from v5 to v12, which ran
the producer eager"; the decision for a measurement run (eager, or a chunk size);
"the default before D-063" for a bundle sealed under D-061 (eager, chunks of 512);
"sealed under D-058" for a bundle sealed sdpa by default before D-060; and "sealed
before D-058" (eager, one shot) for an older bundle. The row "Execution
assessment" states the runner's assessment: passed, or each reason in words; a
run that reached its end with exit 0 but whose completion record marks the
semantic work incomplete is `semantic_incomplete` (D-061 (b)), never
`pipeline_not_completed`. The row "B3 prompts over the model context" counts
the B3 calls refused before generating because their prompt and output allowance
exceeded the model's context (the `prompt_over_context` telemetry events, also
listed under `b3_prompts_over_context` in `FINAL_STATUS.json`), with the documents
they belong to: each such document is a declared exclusion of B3, never scored.

Every report also names the entry's arm. A B1 entry never runs the pipeline and
so never writes `run_completion.json` or model telemetry; the analyser reports it
from the runner's own assessment (`evidence/result.json`) and each sealed
checkpoint's collected `b1_summary.json`. Its status is
`ORDINARY_FINAL_CLOUD_RUN_COMPLETED` only when that assessment passed and every
sealed pass's summary was collected. Its "Models and checkpoints" row gives each
pass, by name, its model, digest and whether the adapter was applied (and the
checkpoint it loaded when the name is not that checkpoint's), and its "B1
checkpoints" row gives each pass's exit code and its counts (items, parsed,
abstained, undecided, backend failures, repaired replies, replies that reached the
output allowance), its attention and prefill (a measurement pass with its
decision), its longest prefill and its peak GPU memory, allocated and reserved (or
that it was not measured, on a machine without CUDA); a replay pass is reported
from its `replay_measurement.json` (per path peak memory, longest prefill and
failures, per pair the byte-identical counts); `FINAL_STATUS.json` carries the same
under `b1_checkpoints`.
Counts only: no label, evidence or reply text enters the report.

The controller is bound to the bundle it was sealed with. Loop S2 changed six of
the seven bound files (`tools/cloud_run_common.py`, `tools/cloud_run_watchdog.py`,
`tools/ordinary_final_bound_cloud.py`, `tools/ordinary_final_cloud.py`,
`tools/ordinary_final_run.py`, `tools/ordinary_final_watchdog.py`), so every bundle
sealed before S2 refuses with `Controller source changed` and must be sealed
again. The S5 join changed `tools/ordinary_final_run.py` once more (the sealed B1
argument check), so every bundle sealed before it refuses the same way. D-056
condition 6 changed it again (passes with a checkpoint, the attention options), so
every bundle sealed before that change refuses the same way too. D-061 changed it
again (eager by default, the prefill options, replay passes, `semantic_incomplete`),
so every bundle sealed before D-061, L2's included, refuses the same way and must be
sealed again. D-063 changed it again (the B1 rule and the replay paths follow the
sdpa one-shot default), so every bundle sealed before D-063, L3e's included,
refuses the same way and must be sealed again.

The rehearsal (`tools/ordinary_final_rehearsal.py`) launches the same way against
its mocked provider: each rehearsal bundle gets a fresh ledger of its own,
`rehearsal_ledger.jsonl`, beside it (never the loop's ledger), the instance name
`shimmer-loop-rehearsal`, the budget fields a new manifest carries, and the
current controller binding.
