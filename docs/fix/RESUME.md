# Remote runtime contract hardening, 2026-09-15

Read this file first and continue without asking. Do not push.

Closed the preparation defect behind the bounded remote attempt at 253cc7b.
Authoritative runtime: tools/cloud_run/runtime.json. Source compatibility is
>=3.12,<3.13; the sealed reference intentionally retains exact Python 3.12.3.
Runtime resolution records a compatible absolute executable. Source integrity,
actual compilation and critical imports precede dependency installation and
model acquisition. Existing package mismatches fail without automatic upgrades.
The Docker source-preflight stage is a prerequisite of package/model layers.
No image was rebuilt and no package/environment installation was performed.

Maintained bounded entry: tools/prepare_remote_experiment.py. Its default is
readiness checks only; --execute requires separate authorization. Historical
output/remote_short_burst_20260915 and docs/fix/remote_short_burst_20260915 scripts
remain evidence, not launch targets. Do not use their default-Python setup script.
See REMOTE_RUNTIME_HARDENING.md and runtime_hardening_20260915/ for evidence.

Validation: 148 unit tests passed (25 runtime, 83 cloud preparation/controller,
8 transport, 7 transfer, 17 recommendation/source-layer, 8 local-runtime tests).
Two runtime/source guard neutralisations fail as expected and restore. Real
Python 3.12.3 compiled 145 files and imported nine critical modules without a
model stack. Startup-readiness and shell syntax checks passed. Desktop session,
selection, GUI/mutations, port lifetime and real batch entry passed; the broader
live-server fixture is blocked because compatible local Python lacks fastapi.
Its child exited and was collected. No dependency repair was attempted.

Historical result remains CLOUD_FULL_RUN_INDETERMINATE. All 32 historical hashes
match. No model inference evidence or missing projection field was fabricated.
Instance 95bbd0c1a9e64361b80c0ff8011b84a3 was provider-confirmed absent at
2026-09-15T07:17:18.016016+00:00 in the previous task, with conservative instance
cost upper bound $0.1219585353. This task made no provider/cloud/SSH/SCP calls.
No model load, full pipeline, multi-round or paid inference API; no push.
Existing untracked SHIMMER_HANDOFF.md and durable/ were preserved.

Next task: repeat the remote short-burst feasibility measurement only after
separate operator cloud approval, using a prepared compatible runtime and the
maintained source/runtime gates. Do not initiate that retry from this handoff.
