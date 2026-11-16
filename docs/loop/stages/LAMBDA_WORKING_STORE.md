# The persistent Lambda working store (standing order 99)

Written 16 November 2026 by lane ops-costs. Order 99 (D-703 item 4, Seckin 17:24): "The laptop stays
light: the working data lives on a persistent Lambda file system kept current, and that file system is
part of the backup coverage." This page answers the task "write the plan and tooling that move tonight's
working data there (dry run only, with two cost figures), or write the reason it is not used". It does
both: the tooling is built and run as a dry run, and the decision for tonight is that the rest of the
working data is not moved, for the reasons in section 3. Nothing was launched, copied or deleted. 0 USD.

## 1. What the file system already holds, and what is left on the laptop

`shimmer-filesystem` (us-east-1, mounted at `/home/ubuntu/shimmer-filesystem`) held 80 GiB at the
listing of 16 November 16:07 UTC (`docs/loop/private/fs_listing/shimmer-loop-fs-listing-20261116t160713/`):

| On the file system | GiB | Read by |
|---|---|---|
| image layers (`image/model`, `image/wheels`, `image/env`) | 38 | every launch with layers (IMAGE-A) |
| asset archives `assets-750cf50d...tar` and `assets-8f0cbd81...tar` | about 33 | every us-east-1 launch (ASSET-COPY-A, MATCH) |
| project archives (`projects/`) | 9.5 | seal jobs and gate runs (ROUTE-S-A) |

So the inputs that every Lambda launch reads again and again are already the working store. What is
left on the laptop was measured by the new planner (`tools/loop/working_store.py`, section 2), run on
the main checkout's `external/` on 16 November at about 21:30 +0300, hard links counted once:

| Class | Files | GiB |
|---|---|---|
| candidate (could be sent) | about 102,600 | 16.80 |
| already on the store (the 750cf50d asset archive, in `external/s05/P1/P3_TRAIN`) | 1 | 20.72 |
| stays local (benchmark answer keys by name, role B's held items) | 3,272 | 0.01 |

The largest candidates: the leakage fingerprint `external/gate_prep_D-S100` (1.94 GiB), the vLLM test
folder (2.35 GiB unique), the three route gate folders (1.45 to 2.08 GiB each, mostly `seal_source.tar` and
`gate_source.tar` copies), `s05/T` (1.52 GiB in 67,264 files) and `s05/P1` (1.28 GiB besides the archive).

## 2. The tooling (built, dry run only)

- `tools/loop/step_cost.py` (STEP-COST-A, #298): two cost figures for any planned Lambda step, without
  and with its named saving measures, priced from the provider inventory and the storage record, never
  typed in. Checks 500 and 501.
- `tools/loop/working_store.py` with `config/working_store.json` (WORKING-STORE-A): walks the laptop
  roots, keeps answer keys (by name, never opened), role B's held items, the scorer's keys and
  credential-like names local, counts what the store already holds, prices the move and each part Lambda
  jobs read repeatedly with the estimator, and prints one `tar -cf - -T <part>.list | ssh` command per part
  as text. It has no execute switch. Check 504.

Run it again with `py -3.12 -X utf8 tools/loop/working_store.py --json <scratch>/plan.json`. The step files
behind the figures below are in `docs/loop/stages/lambda_working_store/`; each is priced with
`py -3.12 -X utf8 tools/loop/step_cost.py --step <file>`. Inventory: the 16 November 18:10 UTC one
(`external/s05/ROUTE_GATE_3daa1c3c/inputs/provider_inventory.json`, A10 at 1.29 USD an hour, the only
single-GPU type with us-east-1 capacity in it). Storage: 0.20 USD per GiB a month
(`docs/loop/private/filesystem_storage.json`).

## 3. Two cost figures for the move, and the decision for tonight

| Step | Without the saving measures | With them | Measures |
|---|---|---|---|
| Move every candidate, uplink alone (5.8 MB/s) | 120.8 min, 6.74 USD | 56.9 min, 4.95 USD | asset_copy: the 20.72 GiB archive on the store is not sent again |
| The same with the uplink shared with tonight's Drive backup (about 2 MB/s) | 340.8 min, 12.89 USD | 155.4 min, 7.70 USD | asset_copy, as above |
| The leakage fingerprint read by two Lambda launches | 12.0 min, 0.33 USD | 0 min, 0.39 USD | warm_file_system: sent once (about 0.17 USD more) and held for a month |

Each figure is the guard's IV.3 forecast (x1.3) plus 3.36 USD of storage for a month in the move rows. The
move with its saving measure is just within the 5 USD per-step pre-approval when the uplink is free; with
the uplink shared it is above it and would need Seckin's word.

**Decision: the remaining working data is not moved tonight.** The reasons:

1. **What Lambda reads repeatedly is already there.** Every launch reads the asset archive, the image
   layers and the project archives from the store. No Lambda job planned tonight (FOR_SECKIN 20:07 and
   20:13: the full gate, the re-seal and #297 run, the 50-document pilot, the quick read, the
   fresh_prompts embedding) reads any laptop part more than once: each job's own inputs travel once inside
   its sealed request (`seal_workloads.tar`, megabytes). `lambda_reads` is therefore empty, and a move
   would save no Lambda minute tonight.
2. **It would not make the laptop lighter.** The laptop's limit tonight is RAM (2.0 to 2.4 GiB free while
   this was written), and data on a remote disk frees no RAM. Disk has room (48 GB free). The laptop copy
   could not be removed after a move in any case: the frozen scorer, the leakage check, the role exchange
   and the Drive backup read it on the laptop, and DELETE-SAFE-A forbids removing it without a recent
   off-machine backup.
3. **The store cannot be read from the laptop.** The file system is reachable only from a running
   us-east-1 instance, so every laptop-side read of moved data would cost an instance (the 16 November
   listings took 5 and 10 billed minutes, 0.11 and 0.22 USD, for names and sizes only).
4. **The uplink is busy.** Tonight's Drive backup (orders 98 and 101) uses the same uplink and is waiting
   on it (`backup_log.jsonl`, drive_paced lines at 21:16 to 21:20). A 16.8 GiB send now would slow both
   and, at the shared rate, costs 7.70 USD even with the saving measure, above the pre-approval.
5. **No guarded copy path exists.** `tools/loop/fs_listing.py` is listing-only by design (pinned command
   set, no write). A send needs its own guarded launch (budget guard, ledger lock, reaper deadline, pinned
   commands, termination in a finally block). It is recorded in OPEN_ITEMS, not built tonight.

**When a part does go to the store.** A part is added to `lambda_reads` (with the launches that will read
it and the source of that plan) once Lambda jobs are planned that read it more than once, and the planner
prices it both ways first. The third row shows why the count matters: for two reads of the fingerprint,
a month on the store (0.39 USD) costs more than sending it twice (0.33 USD); it pays from about three
reads a month. The first likely candidate is the leakage fingerprint, if the leakage check for a future
set runs on the rented-machine route (D-705 item 4). Answer keys, role B's held items, the scorer's keys,
the negotiation sets (Drive only, `config/backup_extra_roots.json`) and credentials never go, whatever
the count (D-676 item 3, BACKUP-NEVER-LAPSE-A, LAW-IV for sensitive content).

## 4. Left open

- The guarded send launch (section 3, reason 5).
- Order 99's "that file system is part of the backup coverage": `tools/loop/backup_coverage.py` walks only
  the laptop. What the store holds is either rebuilt from sealed digests (image layers, asset and project
  archives, each named by its SHA-256 and also on the laptop or in Drive) or not yet held there, so nothing
  is uncovered today; a store-side coverage line would need a listing launch per check.
- The figures rest on the measured upload rates of earlier runs (5.8 MB/s alone, about 2 MB/s shared); a
  move would measure its own rate (PROGRESS-A) before its forecast is trusted.
