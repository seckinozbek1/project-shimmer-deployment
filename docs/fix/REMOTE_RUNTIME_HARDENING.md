# Remote experiment runtime hardening, 15 September 2026

## Closed preparation defect

The attempt recorded at `253cc7b` used image-default Python 3.10.12. Its ad hoc
setup script created a venv from `python3`, installed packages and downloaded
both model snapshots before importing the probe. It bypassed the older sealed
deployment's explicit Python 3.12.3 check. `agent_wrapper` then imported
`finding_record.py:395`, whose f-string syntax the selected interpreter could
not parse. No model loading or inference evidence was obtained.

The maintained paths now share a runtime contract and hard source gates. The
historical launcher remains archived evidence, not a supported entrypoint.

## Source of truth and audit

[tools/cloud_run/runtime.json](../../tools/cloud_run/runtime.json) is the single
machine-readable Python requirement. The existing `prepare_cloud_run.RUNTIME`
dictionary was moved there rather than retaining competing definitions.

* Source compatibility: `>=3.12,<3.13`. The observed grammar failure establishes
  the minor-version requirement, not an exact patch requirement.
* Sealed reference: `==3.12.3`, retaining the existing explicit runtime assertion,
  ensurepip pin, wheel compatibility environment and reproducible baseline.
* Core package versions remain in the existing `runtime.lock`; no dependency
  version was changed and no new installed package was introduced.

The [broad initial inventory](runtime_hardening_20260915/runtime_inventory_before.json)
records active commands and declarations. Main discrepancies and dispositions:

| Surface | Previous behavior | Current behavior |
|---|---|---|
| Sealed preparation/wheel tools | Repeated 3.12.3/CPython tag literals | Read shared contract; local source gate before sealing |
| Sealed deployment controller | Named `python3.12`, repeated exact assertion | Query candidates before transfer; record/use returned absolute executable |
| Remote sealed setup | Version check, then dependencies before source imports | Version/integrity/source gates before pip; dependency recheck before models |
| Ad hoc bounded setup | Image-default `python3`; downloads before imports | Replaced by maintained `prepare_remote_experiment.py` path |
| Source-layer CLI | Hash inventory only | Compatible interpreter plus real compile/import preflight before manifest |
| Docker | Explicit 3.9 installation despite current syntax | Derive minor from contract; source-check stage must pass before dependency/model layers |
| Windows/POSIX startup | Prefer 3.9 or first Python/venv | Stdlib resolver selects compatible absolute executable; incompatible existing setup venv refuses |
| Desktop candidate probe | Accepted any Python >=3.9 | Reads shared major/minor requirement |
| Local bounded runtime overlay | Assumed caller's interpreter | Asserts shared runtime before inspecting the package cache |
| Active documentation/examples | Mixed 3.9 and 3.12 instructions | Compatibility/reference distinction documented consistently |

Historical reports and archived scripts were excluded from migration. Their
commands describe what actually happened and must not be silently rewritten.

## New preparation order and failure behavior

The complete usage contract lives in
[CLOUD_RUN_PREPARATION.md](../CLOUD_RUN_PREPARATION.md#shared-runtime-contract-and-fail-fast-order).
The maintained bounded entrypoint implements:

1. Resolve candidates and query actual versions. Re-query the reported absolute
   executable to reject changed aliases. Record required/observed versions.
2. Verify source hashes and coverage of executable Python files.
3. Compile actual source bytes with that interpreter. Import the real critical
   graph and bounded entrypoint in an isolated subprocess. Block network,
   subprocess work and accidental pipeline/model-stack imports at this stage.
4. Verify declared core dependency versions, then imports. Existing mismatches
   refuse without an automatic upgrade.
5. Install missing dependencies only when explicitly enabled; recheck afterward.
6. Only then acquire models, hydrate and perform explicitly authorized bounded
   inference, using the same executable. Emit readiness only after success.

An incompatible interpreter, source failure or dependency mismatch cannot reach
the expensive callbacks. Each preparation output is fresh; failures cannot leave
a stale success marker. Standalone model acquisition and probe entrypoints repeat
the runtime/source/dependency gates before their own work. Probe outputs are also
fresh and cannot overwrite an earlier attempt's failure artifact.

The sealed controller resolves Python before source transfer. Its already
verified bootstrap interpreter creates an empty venv; the venv is then explicitly
resolved as the final interpreter. All subsequent source checks, pip, hydration,
observer and scoring commands use that absolute venv executable. This is a
recorded environment transition, not a fallback to PATH.

Docker uses a separate stdlib-only preflight stage and a constant success marker
as a dependency of package/model layers. Final source stays after model layers
to retain cache reuse. No image was built here; native image/package readiness
still needs an explicitly authorized validation.

Legacy sealed bundles lacking the runtime/source-preflight seal are rejected by
the controller before provisioning. Contract or preflight-helper drift also
requires local resealing.

## Deterministic evidence

[Validation record](runtime_hardening_20260915/validation.json): **148 unit tests
passed**, plus the startup-readiness check and shell syntax checks.

| Suite | Passed |
|---|---:|
| New runtime contract | 25 |
| Cloud preparation/controller | 83 |
| Transport / transfer | 8 / 7 |
| Report recommendations/source layer | 17 |
| Local runtime overlay | 8 |

The five required cases are covered directly: simulated Python 3.10 stops every
expensive action and readiness; 3.12 proceeds through ordered gates; source
syntax/import failure stops preparation; an older PATH default cannot win; and
executed mocked CLI installation/acquisition/probe subprocesses all use the
selected absolute executable. Additional cases cover alias identity changes,
unreadable Windows Store aliases, hash drift, unhashed source, exact-patch profile
separation, missing/mismatched dependencies and hydration-entrypoint bypass.

Two restoring neutralisation tests prove that removing the version or source
gate makes the corresponding behavioral assertion fail. The original functions
are restored afterward. No model is used by these proofs.

The real local Python 3.12.3 subprocess compiled **145 source files** and imported
**nine critical modules**, including the actual bounded probe, without a model
stack, with site packages disabled (`-I -S`). This uses real interpreter compilation, not `ast.parse(feature_version=...)`.

Desktop session, selection, GUI, mutation, port-lifetime and actual Windows batch
entry checks passed. Its broader live-server fixture is **environment blocked**:
the compatible local Python lacks `fastapi`. The owned child exited and was
collected. No package installation was attempted to hide that limitation.

## Historical record and next step

All **32 recorded historical artifact hashes** still match. The earlier result
remains **CLOUD_FULL_RUN_INDETERMINATE**; no inference result or unknown projection
field was populated. Its verified shutdown and approximately $0.122 cost remain
unchanged.

This task performed no provider call, cloud provisioning, SSH/SCP, package
installation, model loading/generation, full pipeline or multi-round execution.
Operator-owned untracked files were preserved. No push.

**Next task: repeat the remote short-burst feasibility measurement only after
separate operator cloud approval**, using the maintained runtime-gated path and
a compatible prepared interpreter/image. Do not rerun the archived setup script.
