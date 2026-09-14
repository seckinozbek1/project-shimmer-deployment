# Single-GPU experiment preparation

This workflow prepares a sealed, reproducible comparison bundle locally, then
runs it once on a manually provisioned Lambda instance. It is an experiment tool,
not the console's provider-backed Cloud mode or a general application installer.
Preparation and deployment dry-run do not provision an instance or run models.

## Scope and prerequisites

The fixed profile is ordinary Local Review of the synthetic `clinical_reference`
corpus: dense activation, paired review, dependency DAG, one `cuda:0` worker with
two resident models, Agent Execution Briefs enabled, automatic input language and
English output. Draft and multi-round workloads are excluded. Semantic ordering
and governance barriers remain intact; DAG selection does not imply concurrency.

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

## Prepare locally

Use a new experiment ID and replace the placeholder paths below with existing
operator-side files. The hourly rate is an explicit operator input. The example
uses $1.99/hour, a $5 soft target and a $10 absolute budget ceiling.

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
It creates an exclusive directory, transfers and verifies the bundle, installs
hashed wheels offline, checks CUDA, hydrates models and starts one observed run.
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
requests termination 120 seconds before the calculated $10 ceiling and retries
until the provider verifies termination. Keep the operator workstation and its
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
