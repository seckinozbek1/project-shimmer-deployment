# Ordinary final run v12: the sealed controller and the seeded asset copy

One authorized run, bundle `docs/fix/ordinary_final_cloud_run_v12`, on one Lambda
`gpu_1x_a10` in `us-east-1` at $1.29 an hour, launched 2026-09-19 and terminated in the same
run. It is the first run bound to its own controller and the first to attach the standing
filesystem. Execution integrity passed a second consecutive time and the score is unchanged
from v8 and v9: recall 4 of 5 with every reason confirmed, no false positives.

## Identity

| Field | Value |
|---|---|
| Source and preparation commit | `88e9ba2c713440c6f20fdb133f5fd0aa7406672f` |
| Execution manifest | `4740e1da8fd66d112d5136f2d07ec8f5b9ef3838530f9fd6bacf70cd783b75c2` |
| Seal | `1a71857dc941a531bbfaa472dad0684cfb8dfb639ca743d908ce9817f0842159` |
| Project archive | `a84822deb1f3b11c781a7d3e3f37101424b0d663a89c36af91906c4dd5108287` |
| Asset archive | `8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6` (rebound from v11, not rebuilt) |
| Controller | `92f953526074685bfd7cdcb3d7ff704be278cee1b452ddff38992e9a84b6e268` |
| Bound wrapper | `e3da53b9bbb49fd4ebaadee930d85f684fbd552e9a1fe4723486fe1fa5cb6937` |
| Provider adapter | `102b897210015bfe3884094ba41ca5fb7d274313785e9f9f8eb01d2df7432c88` |
| Instance | `aab7cda0363e4456832ed80d8e3d5388`, A10 24 GB, 30 vCPU, 200 GiB RAM |
| Evidence archive | `5bdd80e5176a48ad623bb2a4d6de7285f09632cc9b5a9de52e1d0606a69e2a84` |

The three controller hashes are in the sealed manifest's `local_control_hashes` and are
verified before the first provider call, so this run could not have launched under a
changed controller. Before v12 the seal pinned the runtime the controller carries but not
the controller itself, and only the launch receipt recorded its hash, after the instance
already existed.

## Execution integrity

```
execution_integrity_passed : true
pipeline_exit_code         : 0
reasons                    : []
failed_backend_attempts    : 0
run state                  : completed, reached_end true, 1 document, 4 amendments
```

Second consecutive pass after v9. FACT_CHECKER stays withheld on this corpus by
`config/review_scope.json`; that is the v9 configuration, not a failure of this run.

## Score against the enriched key

| Measure | v12 | v9 |
|---|---|---|
| Recall, location only | 4/5 | 4/5 |
| Recall, reason confirmed | 4/5 | 4/5 |
| False positives | 0 | 0 |
| Distractor hits | 0 | 0 |
| Attribution | 4 of 4 | 4 of 4 |
| Amendments | 4 | 4 |
| Typed findings on the bus | 10 | 10 |

Relations found: two above band, one below band, one missing field, six sum mismatch. The
fifth planted entry (`sheet`, CONV-L03) is still missed, and the evidence class is still
`EVIDENCE_PRESENT_IN_MODEL_PAYLOAD`: the preamble unit reaches the sheet header and the call
carried both the rule and the unit, so the defect is not reachability any more. The
per-laboratory counts are written with a comma inside the label, which the structural label
reader does not admit, so the sum has no addends. Widening that reader is a separate
decision on every corpus and was not taken to reach a catch.

## The asset copy, first use

The bundle declared `shimmer-filesystem` at `/home/ubuntu/shimmer-filesystem`. The
filesystem was attached at launch through the adapter's one new field and mounted on the
instance.

| Stage | Result |
|---|---|
| Probe | `MISSING`, in 7.8 s. Not `UNREACHABLE`: the mount answered, and the archive was simply not there yet |
| Path taken | the upload fallback, byte for byte as v9 ran it |
| Upload | 13.15 GB in 37.4 min at 5.86 MB/s, exit 0 (v9: 37.8 min) |
| Archive integrity | passed in 19.8 s, `project.tar.gz: OK`, `assets.tar: OK` |
| Seed | after integrity, 13.15 GB written in 31.9 s at about 412 MB/s, `mv -n` then `test -f`, exit 0 |
| Receipt | `declared true, state MISSING, seeded true, used false, suspect false` |

**What this run does and does not measure.** It measures the attach (the filesystem was
mounted and answerable within the 7.8 s probe, with no separate attach delay visible in the
237 s activation) and the WRITE throughput to the mount, about 412 MB/s, roughly 70 times
the upload rate. It does NOT measure the hash throughput a saving run will see: with no file
present the probe had nothing to hash. The first run to find `MATCH` will produce that
figure. This run therefore saved nothing, as expected for the run that seeds the copy.

## Phases

| Phase | Duration |
|---|---|
| activation | 4.0 min |
| assets_transfer | 37.4 min |
| ordinary_workload | 6.3 min |
| install_pinned_wheels | 1.3 min |
| support_transfer | 0.5 min |
| asset_copy_seed | 0.5 min |
| archive_integrity | 0.3 min |
| extract_payload | 0.3 min |
| every other phase | under 0.2 min each |

Total billed time about 53 minutes for an estimated $1.15, inside the $5.00 soft budget and
well inside the $7.00 hard ceiling. The workload itself ran 6.3 min: 50 model calls, 12 of
12 agents, 7 Auditor896 pairs, peak RAM 5.41 GB, peak VRAM 11.96 GB of 24 GB.

## Teardown

```
TERMINATION_VERIFIED       : status terminated, instance aab7cda0...
instances_after            : []
cleanup                    : inventory_empty true, temporary_provider_ssh_removed true,
                             local_ssh_material_removed true
independent confirmation   : fresh provider client, inventory [], temporary key absent,
                             only the operator's own standing key remains
```

**The filesystem is not terminated, deliberately.** `shimmer-filesystem` persists with the
seeded archive on it, billing $0.20 per GB per month for 20 GB, $4.00 a month, accruing
whether or not a run happens and separately from any run budget. Its state cannot be read
from this machine: the provider adapter admits no filesystem endpoint and never will, so
the post-cleanup receipt records the expectation and the reason rather than a reading. The
next run that declares it, in `us-east-1`, is the first check of what is on it.

## Progress reporting

Every long phase of this run was reported with four measured values (done of total, elapsed,
rate, remaining at that rate), read from the work itself because the controller captures its
transfers with no incremental output. That reader is now the tracked tool
`tools/ordinary_final_progress.py`, proven against this run's own figures by
`tools/ordinary_final_progress_checks.py` and held by gate check 274 and
`tools/ordinary_final_progress_gate.py`. The practice is recorded as PROGRESS-A in
CLAUDE.md.
