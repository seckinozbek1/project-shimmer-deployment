# Design: every seal on Lambda (standing order 85, D-668, D-674)

Written before any code, on lane/route-s-instance-assets (from be9cfd30, with (b) at b9c3739f).

## What changes

Today route S (ROUTE-S-A) still SEALS ITS JOB BUNDLE ON THE LAPTOP (`prepare_ordinary_final_run.py --arm S`):
that seal links and hashes the 22 GB asset archive (`bind_existing_assets`, `input_sha`), builds
`project.tar.gz` and `seal_source.tar`, and writes the manifest; then binding, reverify, the asset check (now
deferred by (b)), preflight and admission run on the laptop. Order 85: no seal step on the laptop at all. The
laptop writes a REQUEST; the instance seals the job and verifies the assets.

## The request (laptop, no seal step)

`seal_route.write_request(out, source, requests_path, reuse_bundle, inputs, budget, parallel)` writes into a
new folder, reading no asset archive and building no project archive:

- `seal_source.tar` (the bound commit's tracked tree from git objects, `bound_tree_archive`, as today) and
  `commit_object.bin`;
- `seal_workloads.tar` (the requests' files, `job_requests`, as today), the read copies and the attestation
  (`read_copies`, `attestation`, as today), `reuse_manifest.json` (the reuse bundle's manifest, as today);
- `seal_request.json`: schema `seal-request-v1`; the job block (`job_block`, as today); the asset identity
  read from the reuse manifest (archive digest, bytes, members digest, models) and never from the archive;
  the budget from `budget_fields` (instance candidates, caps, reserves) for arm S; the image read from the
  inventory as the sealer reads it; `local_control_hashes` of the controller files (LF tree); every file above
  by digest (`files`).

## The launch (laptop controller, request mode)

`ordinary_final_bound_cloud.py --request <folder>` (beside `--bundle`, one of the two):

- the request admitted (`seal_route.request_error`): schema, every file at its digest, the controller hashes
  equal to the running controller's, the read copies not stale, the attestation's refusals empty;
- the guard decides on the request's budget exactly as on a manifest's; the ledger lines name the request;
- the instance gets the request's files only; the asset archive comes from the provider-side copy and must
  MATCH the request's digest (no laptop archive exists, so MISSING, MISMATCH or UNREACHABLE refuse the run
  after the instance is up, the instance then terminated and the ledger closed as at any stop).

## On the instance

1. `instance_job_seal`: the tree extracted from `seal_source.tar` and held to the request's tree id
   (`exact_commit`, as today); the env made from the archive's wheels; the asset archive verified once
   (`verify_ordinary_final_assets`) against the reuse manifest's fingerprints, and the job refused before any
   seal unless it passed for the request's digest ((b)'s rule); then the sealer seals the job bundle there
   (`--arm S --seal-requests ... --reuse-assets <reuse bundle on the instance>`), its receipt from that one
   verification.
2. The job runs as today (`seal_route.run_job`): every bundle sealed, receipts, project store, archives stripped.
3. Evidence: the job bundle's manifest and seal travel back with the sealed bundles.

## Admission (laptop)

`seal_route_driver.py admit --request <folder> --run <run folder>`: as today, bound to the request's digest
instead of a laptop job manifest; the returned job manifest must name the request's digest and tree; every
bundle's reverify and preflight run from an LF checkout of the request's commit.

## Proofs (each neutralised, must fail)

- the request carries no asset archive and no project archive, and every file by digest;
- a request with a changed file, other controller hashes, a stale read copy or attestation refusals is refused
  before any provider call;
- request mode refuses an asset copy that does not MATCH;
- the instance refuses the job before any seal when the assets do not verify for the request's digest;
- the instance's job manifest names the request's digest and tree, and admission refuses one that does not;
- the guard's decision on a request equals its decision on the manifest the same budget would seal.

## Units

1. request writer and `request_error` (seal_route.py) with proofs;
2. bound wrapper and controller request mode, the copy MATCH required;
3. the runner's `instance_job_seal` phase;
4. admission bound to the request;
5. the rule text (CLAUDE_REFERENCE.md ROUTE-S-A), the re-seal sentence, a fresh checker, the arm G gate on Lambda.
