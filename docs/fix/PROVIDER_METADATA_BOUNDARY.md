# Provider metadata boundary closure

The previous experimental controller bypassed `safe_metadata` and persisted a
raw instance object. Historical controllers remain evidence and are not launch
targets. The maintained entry is now `tools/run_remote_experiment.py`.

## Active boundary audit

* `cloud_run_watchdog.LambdaTermination.request`: projects every instance through
  `provider_instance` and `safe_metadata` before returning; termination response
  bodies are discarded. The former raw-response public API is closed.
* `lambda_experiment_provider.LambdaExperiment`: inherits that instance boundary;
  uses explicit separate response allowlists for inventory, images, SSH public
  registrations and one-instance launch IDs. Unknown fields/subtrees drop.
  All transport/parse errors have constant diagnostics and suppressed context.
* `run_remote_experiment.poll_state`: reprojects an injected provider's state
  before status persistence. The controller never receives raw HTTP responses.
* `deploy_cloud_run` and the existing termination watchdog: already use the
  sanitized `instance()` interface and `safe_metadata` before artifacts.

Raw response bodies exist only inside the client transport in memory. They are
never an artifact, status object, log or exception payload. URL-bearing provider
fields are not needed and are omitted entirely. This is an allowlist, not a
growing list of secret field names.

## Deterministic proofs

`tools/lambda_metadata_checks.py` covers known, future and nested secrets,
repeated status polls and artifact sweeps, malformed operational fields,
HTTP/library failures, safe termination proof, other endpoint projections,
an executed reviewed-bundle check, and a controller structural guard.
Neutralising the instance projector makes the behavior assertion fail; restoring
it makes the same assertion pass. All planted values are synthetic.

The installer now resolves the missing pinned dependency closure before install.
Its dry-run plan must contain only declared exact versions and cannot replace an
existing distribution. Core package importability is rechecked before acquisition.
Local Linux-target wheel/metadata resolution validated the 41-package closure;
runtime pins and configured model checkpoints remain unchanged.

The controller requires passing security, runtime, source, cloud and bundle gates
and writes `REMOTE_RETRY_LOCAL_GATES_PASS=true` before its one-shot launch. It
transfers only reviewed tracked source, three required tracked configurations and
their manifest. It verifies source integrity and imports before creating the
explicit isolated environment; the final absolute compatible interpreter handles
all dependency/model/probe subprocesses. Provider-default ML packages cannot
silently contaminate the experiment environment.

Cloud authorization, source-export authorization, the $2 ceiling and single-instance
limit come from the current operator task. No full pipeline or multi-round is
authorized. The experiment report will distinguish local proofs from actual
remote measurements and document verified teardown.
