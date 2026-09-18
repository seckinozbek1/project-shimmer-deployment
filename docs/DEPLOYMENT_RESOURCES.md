# Standing billable resources

Every provider resource this project keeps between runs is recorded here: what it is, what it
holds, what it costs, how it was made, how a run verifies it, and the rule that deletes it. An
instance is not such a resource: every run creates one and terminates it in the same run, and
the receipts prove the inventory is empty afterwards.

This project owns exactly one standing billable resource, recorded below. It was created by the
operator by hand, because no tool here can create one (see "How it was created").

## The ordinary final asset copy: `shimmer-filesystem` (EXISTS)

**What it is.** One persistent filesystem in `us-east-1` holding the sealed ordinary final asset
archive, so a run attaches and hashes it instead of uploading 13.15 GB. The upload is 36.9 to
37.8 minutes of every run measured so far, about 70 percent of billed time. The run that first
declares it uploads and seeds, and saves nothing; the saving begins with the run after.

| Field | Value |
|---|---|
| Kind | Lambda persistent filesystem |
| Region | us-east-1 (the only region this project launches in) |
| Name | `shimmer-filesystem` |
| Size | 20 GB, the smallest tier holding the 12.25 GiB archive with headroom |
| Contents | exactly one file, `assets-<sha256>.tar`, the sealed archive under its own digest. Today that digest is `8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6`, rebound unchanged since bundle v5 |
| Monthly cost | **$4.00** at the operator's confirmed published rate of $0.20 per GB per month, inside the $5.00 per month cap. Billed WHILE IT EXISTS, whether or not an instance mounts it and whether or not a run happens |
| Reachability | only from instances in `us-east-1`, its own region. A run in another region cannot use it and uploads instead |
| Mount | `/home/ubuntu/shimmer-filesystem`, where Lambda mounts an attached filesystem by its own name. The declaration carries it verbatim and the controller probes `<mount>/assets-<sha256>.tar` |

**How it was created.** By the operator, by hand, in the provider console on 2026-09-19. It was
NOT created from this machine, and could not have been, for two reasons recorded the same day:

1. **The API cannot create it from this machine.** `tools/lambda_experiment_provider.py` admits
   five endpoints (`instances`, `instance-types`, `images`, `ssh-keys`, the bounded launch) plus
   SSH-key deletion and termination, and refuses everything else, including every filesystem
   endpoint; this was executed and refused, not assumed. Widening that allowlist to a
   create-and-bill endpoint is a larger change than the one attach field the operator
   authorized, and is not made here.
2. **The published rate is not readable from this machine.** No allowlisted endpoint returns
   storage pricing. A standing charge is not accepted against an unverified number.

**How to recreate it by hand.** In the Lambda console, in `us-east-1`, create one filesystem of
the smallest size holding 12.25 GiB with headroom (20 GB at the time of writing), note its name
and the mount path the console reports, and confirm the published rate times the size is at or
below $5.00 per month first. Nothing else is needed: the archive is seeded by the first run that
declares the filesystem, not by hand.

**How a bundle declares it.**

```
py -3.12 tools/declare_asset_copy.py --bundle docs/fix/ordinary_final_cloud_run_<n> \
    --filesystem-name <name> --mount </mount/path>
```

That writes `asset_copy_declaration.json` into the bundle, keyed by the bundle's own archive
digest. Without that file the controller runs the upload path exactly as run v9 did, proven
byte-identical.

**How a run verifies it.** The instance, not this machine, hashes the copy at
`<mount>/assets-<sha256>.tar` and compares it to the sealed manifest's digest. MATCH is copied
into place and the upload skipped; MISSING, MISMATCH, UNREACHABLE or a failed copy fall back to
the upload. `archive_integrity` then hashes whatever is on the instance, as always. A MISSING
copy is seeded only after that phase passes, with `mv -n`, so nothing already there is
overwritten; a MISMATCH is recorded suspect and left untouched for the operator. Every outcome
is written to `asset_copy_receipt.json` in the bundle.

**How it is recreated from the sealed assets alone.** The archive is not unique to the
filesystem: `docs/fix/ordinary_final_cloud_run_<n>/assets.tar` is the same bytes, and its digest
is in the bundle's manifest and its `authorization_binding.json`. Create a new filesystem, then
let any run declaring it seed the copy, or copy the archive up by hand to
`<mount>/assets-<sha256>.tar`. No state lives only on the filesystem.

**The deletion rule.** The filesystem is deleted when the prototype roadmap closes. Before
deleting it, confirm that **no bundle still declares it**:

```
grep -rl "filesystem_name" docs/fix/ordinary_final_cloud_run_*/asset_copy_declaration.json
```

Every hit names a bundle that would attach it at launch. Either those bundles are spent (their
`LAUNCH_INTENT.json` exists, so they cannot launch again) or their declaration is removed first.
Only then delete the filesystem in the console, and record the deletion here with its date.
Deleting it costs nothing but the next run's upload time; nothing is lost.

**Storage cost accounting.** While the filesystem exists, its cost accrues whether or not a run
happens, and it is NOT part of a run's soft or hard budget. A run's status reporting shows it
separately. At fewer than about three runs a month the storage exceeds the upload it saves.
