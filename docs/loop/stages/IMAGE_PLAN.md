# A ready-to-run image on the filesystem (D-S108, D-S109): the plan

Lane `lane/image`, from `loop/2026-10-27` at `1ac2f028`. Written 9 November 2026 before any code.
Nothing here has run on an instance; every figure marked "measured" is read from saved run folders,
every other figure is a projection and says so. No provider call, launch or seal was made for it.

## 1. Measured today: launch request to first workload step

Source: the controller's own phase records in every saved run folder (`<phase>_timing.json`,
`activation.json`, `asset_copy_receipt.json`, `assets_transfer_archive.json`, and the first
`batch_workload_start_*_timing.json` or `ordinary_workload_start_timing.json`), 40 launches that
reached a workload under `external/s05/`, `external/s07/`, `external/s10/` and `docs/fix/`. The clock
starts at the launch intent, taken just before the launch request (`tools/ordinary_final_cloud.py:724`).
All on `gpu_1x_a10`, us-east-1. Medians, with the range:

| Phase (controller line) | Copy MATCH, 13.15 GB archive (n=26) | No copy, upload of 22.25 GB (n=9) | No copy, upload of 13.15 GB, v5 to v9 (n=5) |
|---|---|---|---|
| activation, provider boot (`:776`) | 252 s (168 to 441) | 204 s (141 to 327) | 212 s |
| ssh ready | 2 s | 2 s | 2 s |
| support_transfer, `project.tar.gz` (about 131 MB) and support files by scp (`:795`) | 34.5 s (31 to 76) | 37 s | 33 s |
| asset_copy_probe, `sha256sum` of the tar on the mount (`:797`) | 185 s (128 to 259) | | |
| asset_copy_use, `cp` from the mount (`:802`) | 21 s (20 to 175) | | |
| assets_transfer, scp from the laptop (`:809`) | | 3,906 s (3,800 to 10,675) | 2,252 s |
| archive_integrity, local `sha256sum -c` (`:811`) | 20 s | 32 s | 20 s |
| extract_payload, both tars (`:819`) | 20 s | 20 s | 20 s |
| create_environment, `venv` (`:820`) | 8 s | 8 s | 8 s |
| install_pinned_wheels, 92 wheels, `--no-index --require-hashes` (`:822`) | 80 s (79 to 92) | 80 s | 79 s |
| dependency_closure, `pip check` (`:823`) | 8 s | 8 s | 8 s |
| gpu_metadata (`:824`) | 8 s | 8 s | 8 s |
| not in a phase (watchdog arming, file writes) | 19 s | 18 s | 18 s |
| **launch request to first workload step** | **675.5 s, 11.3 min (552 to 890)** | **4,367 s, 72.8 min (4,212 to 11,142)** | **2,652 s, 44.2 min** |

What is uploaded: `project.tar.gz` (code, the two checkpoints `checkpoint-168` and `checkpoint-896`
under `docs/fix/.../evidence/`, and the bundle's workload; 131,217,543 bytes for C1) and, unless the
copy matches, `assets.tar`. What is installed: a venv and the 92 pinned wheels. No system package is
installed: the sealed Lambda image (`gpu-base-24-04`, id `d32e7189-2836-4db1-a04e-06e340506937`)
supplies Python 3.12.3 and the driver. The asset archives (from the manifests' member lists):

| Archive | Bytes | Members |
|---|---|---|
| `8f0cbd81...` (C1 and every MATCH launch) | 13,149,972,480 | Qwen2.5-7B 5.563 GB, wheels 3.027 GB, bge-m3 2.293 GB, Phi-3.5-mini 2.267 GB |
| `750cf50d...` (every launch since; seeded on the filesystem by CASES, `seeded: true`) | 22,248,529,920 | the same, plus phi-4 9.099 GB |

Readings worth stating:

- The mount reads at about 71 MB/s single stream (13.15 GB in the median 185 s probe; slowest 51 MB/s).
  A 22.25 GB copy has never been used: T2E_TRAIN_E stopped at the 300 s probe deadline (open item 94,
  fixed on `lane/tiers` at `bc2db064`). At the measured rate its probe would take about 313 s, so a
  22.25 GB MATCH launch projects to about 825 s (13.75 min), not measured.
- The seed of the 22.25 GB archive onto the mount took 44 s (CASES), about 500 MB/s as `cp` reported it;
  writes may be buffered, so this is a completion time, not a sustained rate.
- Phase times are quantised by the controller's polling (first poll at 2 s, then every 10 s,
  `tools/ordinary_final_cloud.py:292-293`), so every short phase (8 s, 20 s) is an upper bound; about
  6 to 10 s of each remote phase is bookkeeping.
- Activation with the filesystem attached (252 s) is longer than without it (204 to 212 s). The groups
  ran on different days; the measurement launch (section 4) records whether attaching costs time.
- Even with no setup at all, activation, ssh, the support transfer and the GPU reading take about 300 s
  (5 min) of D-S80's 7.5 min.
- The runner hashes every model file again before it imports anything (`tools/ordinary_final_run.py:1705`);
  that is inside the workload and reads from the page cache after a first read.

## 2. The two forms, and how each keeps every rule

Both keep the sealed bundle exactly as today (`assets.tar` and its digest, `project.tar.gz`, every member's
sha256 in the manifest). The image is a second, faster way to put the same bytes on the instance, used only
when the instance proves they are the sealed ones. Layers on the mount, each under its own key, written
once beside its final name and moved into place with no-clobber, never edited:

- `image/models/<model_id>--<revision>/`: the model's `hf_cache/hub/models--...` tree as the sealed archive
  holds it. Its manifest is the sealed manifest's own member list for that model; no new list.
- `image/env/<key>/`: a venv built on the mount, at that path, with the same command as
  `tools/ordinary_final_cloud.py:822`, from the sealed wheels. Key: sha256 of `install.lock`, the Lambda
  image id, the Python version and the build tool's digest. Its manifest (every file's sha256 and bytes,
  every symlink's target; about 25,195 files and 5.70 GB before bytecode, read from the 92 wheels) is
  written by the build and sealed into each bundle as a support file.
- Code, checkpoints and the workload stay in `project.tar.gz`, uploaded per bundle (about 35 s). Every
  bundle's archive differs because it carries its workload: 37 distinct archives at commit `2b585af1`,
  33 at `55f1dd15`, 25 at `d38ce3cd`, so a code layer keyed by the archive would almost never be reused.
  This departs from D-S108 item 1's "code at the bundle's commit" in the image; a split of code and
  checkpoints from the workload would save at most about 30 s a launch and changes `verify()`. Left out
  unless the lead rules otherwise.

**Form B, prebuilt and used in place (proposed default).** After ssh, one remote phase `image_check` runs
a sealed check script (a support file, hash-pinned) that hashes, in parallel, every file of the layers the
bundle names against the sealed digests and prints one state per layer: `MATCH`, `MISSING`, `MISMATCH`
or `UNREACHABLE`. All `MATCH`: each layer is bind-mounted READ-ONLY into the run root
(`<root>/hf_cache/hub/models--...`, `<root>/venv`), so the runner, `admit_cache_ref`, the runner's own
model hashes and `installed_runtime` read the same paths as today, and nothing a run writes can reach a
shared layer (a write fails loudly). The assets transfer, the copy, extract, venv and wheel install are
skipped; `pip check` and `gpu_metadata` still run. `archive_integrity` still hashes `project.tar.gz` on the
instance; for the assets, `image_check` IS the integrity check on what is on the instance, file by file,
against the sealed digests (the tar digest cannot be recomputed from files, so the per-member digests the
manifest already seals are what is compared). Any layer not `MATCH` falls back to the upload path byte for
byte as today, and the receipt says which layer and why.

**Form A, a Docker image loaded from the filesystem.** The env layer becomes an image tar on the mount
(`docker save`), loaded with `docker load` and run with `--gpus all`; models stay a separate directory,
bind-mounted read-only, since D-S108 allows it and putting 19 GB of weights through `docker load` would
read and write every byte. Integrity: `docker load` verifies each layer's digest on the instance, and the
loaded image id must equal the sealed one; models are checked as in form B. Its costs, before measurement:
it reads the env as form B does and also writes and unpacks it on local disk; it needs Docker and the
NVIDIA container toolkit on the Lambda image (not known; measured); its base image must be pinned by
digest and carry Python 3.12.3 for the existing Python gate; and the run executes inside a container, so
byte identity with the uploaded path is a separate thing to prove. The repository's `Dockerfile` is not
usable as it is: it installs from PyPI and a PPA at build time, unpinned by digest.

**Projection, to be replaced by the measurement.** Form B removes about 314 s (probe 185, copy 21, local
hash 20, extract 20, venv 8, install 80, at the medians) and adds `image_check`, H seconds. Fixed part
(activation, ssh, support transfer overlapped with the check, project integrity, `pip check`, GPU, rest):
about 345 s. H is bytes over read rate. A bundle naming three models carries 10.12 GB of models plus the
5.70 GB env; one naming four, 19.22 GB plus 5.70 GB.

| Read rate on the mount | Three models (15.8 GB) | Four models (24.9 GB) |
|---|---|---|
| 71 MB/s (single stream, measured) | H 223 s, start about 568 s (9.5 min) | H 351 s, about 696 s (11.6 min) |
| 150 MB/s (parallel, not measured) | H 105 s, about 450 s (7.5 min) | H 166 s, about 511 s (8.5 min) |
| 300 MB/s (parallel, not measured) | H 53 s, about 398 s (6.6 min) | H 83 s, about 428 s (7.1 min) |

So D-S80's 7.5 min is met only if parallel reads of many files beat the single stream by about 2x (three
models) to 3.3x (four). The tar's one digest can only be read as one stream; the image's many files can be
read in parallel. That is form B's structural advantage, and the one thing the measurement must settle.
A second lever, if needed: seal into each bundle only the models its arm loads, so fewer bytes are hashed.

## 3. Kept current after each merged change

- `tools/image/layer_plan.py` (laptop, no provider call) reads a freshly sealed bundle and lists its layer
  keys; `docs/loop/private/image_layers.jsonl` records what the filesystem holds, written only from
  instance receipts. A key the record lacks is a layer to build.
- What changes a layer: `install.lock`, the Lambda image or the build tool (env); a model id, revision or
  file (that model). A code-only merge changes no layer: code travels in `project.tar.gz`. The wheels and
  models have not changed since the phi-4 archive (`750cf50d`); the wheels are identical in both archives.
- The filesystem is reachable only from an instance (the adapter has no write endpoint, D-S50), so "update
  once before the next launch" happens at the start of the first launch after the change, as D-S109 item
  3 says: `image_check` reports `MISSING`, the run uploads what it needs, verifies it, builds only the
  missing layer onto the mount (beside its name, no-clobber), checks it, and then starts from it.
  A `MISMATCH` is recorded suspect and never replaced by a run (ASSET-COPY-A).
- Upload only the changed layer: the sealer also writes the assets as one tar per layer, each sealed by
  digest, so a new model uploads that model alone (phi-4: 9.1 GB, about 27 min at the laptop's measured
  5.7 MB/s) instead of 22.25 GB (65 min).
- Old digests: before a layer is replaced its key and digest are recorded (D-028) in the receipt and in
  `docs/loop/private/asset_copy_history.jsonl`. Per D-S109 item 2, a replaced layer, and both asset tars
  once the image is verified, are deleted only after the new image passes its test launch on an instance
  and no running loop instance's manifest names them; each deleted digest is listed in
  `docs/DEPLOYMENT_RESOURCES.md`. The filesystem itself is never deleted.
- Several instances share the mount (up to sixteen): layers are read-only in use, built under a new key,
  and never changed in place, so a build cannot disturb a running launch.
- Recommendation: keep the 92 wheels (3.03 GB, about 0.61 USD a month) beside the env layer, so an
  `install.lock` change uploads only the new wheels.

Storage (0.20 USD per GB per month, D-306): now about 35.4 GB (both tars), about 7.08 USD a month. After:
models 19.22 GB, env about 5.70 GB plus bytecode, wheels 3.03 GB, about 28 GB, about 5.60 USD a month.
While both are held, about 63 GB, about 0.42 USD a day; so the tars go the day the image passes.

## 4. The rented measurements (pricing and savings proofs, D-S105 item 2)

Both are loop launches through the bound wrapper on `gpu_1x_a10` in us-east-1 with the filesystem
attached. Cost at the A10's 1.29 USD an hour times the forecast factor 1.3, that is 1.677 USD an hour.

**M1, build and measure, one launch, forecast 60 min, 1.68 USD (cap at 1.5x, 90 min, 2.52 USD).** A new
sealed arm (as arm G is): its workload is the build tool, sealed with the bundle, run by the runner under
every guard. On the instance: (a) record whether Docker and the NVIDIA container toolkit are present, the
mount's type and options, local disk and memory (1 min); (b) hash `assets-750cf50d....tar` on the mount
cold, the single-stream baseline (about 5.2 min); (c) build the four model layers and the env layer on the
mount from that tar, timing the venv install on the mount and writing the env manifest (about 10 min);
(d) after dropping the page cache each time, hash a three-model set and a four-model set with 1, 4, 8 and
16 readers (about 12 min); (e) from the read-only bind mounts, import torch, run `installed_runtime`,
`pip check` and the hardware admission, cold and warm (2 min); (f) form A, if Docker is there: build the
env image, `docker save` it to the mount, then cold `docker load`, `docker run --gpus all` and the same
imports (about 12 min); (g) collect, terminate (about 7 min with activation). It writes the layers onto
the filesystem, so it is also the first build; the tars stay until M2 passes.

**M2, the test launch D-S109 item 4 asks for, one launch, forecast 20 min, 0.56 USD.** Through the
controller with the chosen form: mount, `image_check`, start from the image, `archive_integrity` on the
project, the hardware check, and one small known job; its start time and cost recorded. Byte identity
with the uploaded path, in the lead's choice: (i) the same job in the same session on both paths (strongest;
needs a per-entry setup switch), or (ii) against a run of the same sealed job at the same bound commit on
the copy path, if one runs anyway before M2. Recommendation: (i).

Total about 2.24 USD forecast, plus storage while both copies are held.

## 5. Expected start time and the saving per launch

Against D-S80's 7.5 min (450 s), launch request to first workload step:

| Path | Start | Status |
|---|---|---|
| Upload of 22.25 GB (what 9 of the 10 launches after the seed did, D-398) | 72.8 min | measured, n=9 |
| Copy MATCH, 13.15 GB | 11.3 min | measured, n=26 |
| Copy MATCH, 22.25 GB (the default from D-405 on) | about 13.75 min | projected from the measured rate |
| Image, form B, single-stream reads | 9.5 to 11.6 min | projected |
| Image, form B, parallel reads at 150 to 300 MB/s | 6.6 to 8.5 min | projected; M1 measures the rate |

Saving per launch at 1.29 USD an hour: against the upload, about 61 to 66 min, 1.32 to 1.42 USD (1.71 to
1.85 at the forecast factor); against a 22.25 GB copy MATCH, which D-405 already makes the default, about
2.2 to 7.1 min, 0.05 to 0.15 USD. Stated plainly: most of the money was lost to uploads the copy would have
avoided; the image adds a few minutes a launch on top of the copy, and whether it reaches 7.5 min depends
on the parallel read rate. If M1 shows it cannot, D-S80 item 5 applies: the miss and its size go to Seckin.

## 6. Code, once the lead says go

On `lane/image`, coordinated with `lane/tiers` (`judge-product`), which is changing the same controller
files for the probe deadline, the room check, the declaration on every bundle and seeding; this lane builds
on that design and does not duplicate it: the image path sits where the asset copy sits, with the same
states, receipt shape and fallback, and the same declaration file gains an `image` field.

1. `tools/image/build_image.py` and `tools/image/check_image.py` (the instance's tools, sealed as support
   files) and `tools/image/layer_plan.py`, each with fixture proofs; no provider call.
2. The sealer: the image block (layer keys, the env manifest digest, the per-layer tars).
3. The controller: `image_check`, read-only bind mounts, the receipt, the fallback and the post-integrity
   layer build; a change to the bound files, so every bundle is resealed once, with `lane/tiers`.
4. The arm for M1; the progress reader gets a reading for each new long phase (PROGRESS-A, check 274).
5. Proofs in the controller gate with neutralise, fail, restore, pass: a changed byte in any layer file is
   `MISMATCH` and falls back; a missing layer falls back and builds; the bind mounts are read-only; the
   fallback argv equals today's; a check that stops hashing is caught.
6. CLAUDE.md (ASSET-COPY-A, CONTROLLER-BINDING), `docs/DEPLOYMENT_RESOURCES.md`, the progress page and
   FOR_SECKIN figures after M1 and M2.

## 7. D-S109 applied to this plan (D-409)

1. **Built on what is there.** M1 builds every layer from `assets-750cf50d....tar`, already on the
   filesystem since CASES seeded it on 8 November: it is hashed on the mount first and used only on
   MATCH, so nothing is uploaded. The four model layers are that tar's own members, unchanged by digest;
   a later change rebuilds only the layer whose key changed and keeps every other layer in place.
2. **One current copy.** After M2 passes on an instance, both tars (`8f0cbd81...`, 13.15 GB, and
   `750cf50d...`, 22.25 GB) and any replaced layer are deleted, only while no running loop instance's
   manifest names them; each deleted digest is listed in `docs/DEPLOYMENT_RESOURCES.md`. This amends
   D-028's keep-the-old rule for this filesystem (D-S109 item 2); the filesystem itself is never deleted.
   Kept: the current layers and the wheels the env is built from (section 3).
3. **Check first, every launch.** `image_check` runs on the instance after ssh and before any workload
   step, against the sealed bundle's digests. Not current: the receipt says which layer and why, the
   filesystem is updated once from the bundle (upload of that layer, verify, build beside its name,
   no-clobber, check), and only then does the run start, from the image. A run never starts from a layer
   that did not read MATCH in that session. A MISMATCH layer is not overwritten: it is recorded suspect,
   the run starts from the uploaded path, and the lead deletes and rebuilds that layer under item 2.
4. **Test before use.** M2 (section 4) is that launch: mount, `image_check`, start from the image,
   `archive_integrity`, the hardware check, one small known job compared byte for byte with the uploaded
   path, its start time and cost recorded. No other launch uses the image before M2 passes.
5. **Storage cost.** `docs/loop/private/filesystem_storage.json` (private, gitignored), the shape the page
   reads: `gb_held` entries from the provider's own inventory only (GET `file-systems`, bytes used), never
   typed. Today it holds D-306's read, 12.02 GiB on 8 November, and notes apart that the 22.25 GB seed came
   after that read. A fresh read is taken at M1 (the controller's room check makes that same GET) and after
   each change. In the forecast: about 7.08 USD a month now (two tars, about 35.4 GB, not yet read), about
   0.42 USD a day while old and new are both held, about 5.60 USD a month after.

## 8. Built on fixtures (D-417): what the lead runs

Form B is built; nothing in it has run on an instance. Code: `tools/image_layers.py` (the instance's
tool, sealed as a support file), `tools/image_layer_plan.py` (laptop: plan, record, env-manifest),
the sealer's `--image-layers`, `--image-env-manifest` and `--image-measure`, the controller's image
phases (`image_check`, `image_build`, `image_recheck`, `image_bind`, `image_measure`), the progress
reader's four image readers, and the proofs in `tools/ordinary_final_image_checks.py` (in the
controller gate, each rule neutralised, failed, restored and passed). Off unless sealed.

- **M1 (build and measure).** Seal one small known job (a one-item B1 bundle is enough) with
  `--image-layers --image-measure` and `--reuse-assets` from a bundle whose archive is `750cf50d...`,
  so the copy probe reads MATCH and nothing is uploaded; the declaration as every bundle carries it.
  On the instance: `image_check` reads MISSING for every layer, the asset path runs (copy MATCH),
  `image_build` writes the model, wheels and env layers onto the mount from the verified extraction,
  `image_recheck` reads the models and wheels MATCH and the env UNSEALED, the run installs its own env
  (the uploaded path, so its job's result is the reference), then `image_measure`, then the job.
  Afterwards: `py -3.12 tools/image_layer_plan.py record --run <run folder>` and
  `py -3.12 tools/image_layer_plan.py env-manifest --run <run folder> --out <file>`, and a fresh
  storage read into `docs/loop/private/filesystem_storage.json`.
- **M2 (the test before use).** Seal the same job at the same bound commit with
  `--image-layers --image-env-manifest <file>`. Expected: `image_check` all MATCH, no archive
  fetched, every layer bound read-only, no env install, `archive_integrity` on the project, the
  hardware check, the job; its reply records compared byte for byte with M1's (option (ii) of
  section 4; same commit, same job, deterministic decoding). Start time and cost from its run folder.
- **Then.** If M2 passes, `--image-layers` becomes the default for every us-east-1 loop bundle (one
  line in the sealer), and the two asset tars are deleted under section 7 item 2.
