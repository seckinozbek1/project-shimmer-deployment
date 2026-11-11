# The first reference pair (D-S82 item 3, D-382 item 1)

Until a reference pair is measured, every launch stays on the A10. The sealer keeps a type above the A10 only when `tools/cloud_run/gpu_speed_order.json` has a checked `measured` entry for that machine type. This plan makes the first entry, for the fastest offered x86_64 single-GPU type. By the declared order that is a B200 if one is offered, else an H100 PCIe, else an A100.

## What runs

- **The items.** The three reference items in `config/factor_record.json` (`reference_set.items`):
  - ContraDoc `0436316e6bb3`;
  - SciTab `09b24267b75a`;
  - ContraDoc `01015e47de8a` (news_train_96).
  Each is staged from its own sealed workload digests (`workload_files`), so `factor_record.reference_workload` recognises it. That makes the bundle a reference-set run, the only bundle the sealer lets leave the A10 without an entry.
- **Both machines, at one commit.** The pair needs two records that differ in the machine alone (`factor_record.compare` gives `differs == ['machine_type']`). The declared A10 seconds come from runs at older commits (`d38ce3cd`, `2b585af1`), whose code factor differs, so they are history only. The three items therefore run twice from one sealed commit, as B3 entries on exposed bundles:
  - once with `--instance-types gpu_1x_a10`;
  - once with `--instance-types <the new type>`.
  Both launches go under the one ledger, as two loop instances that may run at once.
- **No `--comparison`.** The pair is two machine types on purpose. It is not an arm comparison.

## What is read

For each item:
1. Its workload seconds on both machines, from the batch entry's `batch_workload_<k>_timing.json`, the measure the declared A10 seconds use.
2. Its scores on both machines, through `tools/score_corpus.py` only.
3. `factor_record.machine_effect(a10_record, new_record, seconds_new, scores_a10, scores_new, seconds_a10=...)`, with the A10 seconds measured in this pair.

If any item moves a score, that is a hardware effect: `measured_entry` refuses it, and the type stays out until the cause is read.

## What is written

- The `measured` entry is `factor_record.measured_entry(pairs)` over all three items: per item its two run folders, both records' digests, the one commit and its result. The entry's factor is the median of the three items' factors (D-401 item 3), written now, before any pair is run. It is keyed by the machine type and committed to `gpu_speed_order.json` with a DECISIONS record naming the runs, the commit and the three factors.
- Any item that moved a score keeps the type out. Exact score equality may never hold across GPU generations (another kernel, another reduction order); then the type stays out, and the lead records it.
- Check before committing: `factor_record.check_measured` must pass on the new file. Any sealing with a broken entry refuses.

## Cost and time (estimates from the declared A10 seconds; replace them with the measured figures)

| Run | Workload | Launch to ready (MATCH copy) | Price | Estimate |
|---|---|---|---|---|
| A10, three items | about 17.5 min (332, 247 and 473 s) | about 15 min | 1.29 USD an hour | about 0.7 USD |
| New type, three items | unknown until measured; at most the A10's | about 15 min | 2.49 to 6.99 USD an hour | about 1.5 to 3.8 USD |

Each launch is forecast in `BUDGET.md` and passes the guard's cap, which now also reserves each running instance's overrun (D-382 item 5).

## After it

- Compared runs (B3, B1 and the cloud reference on the same items) may then seal on the new type, all arms of one comparison on that one type (`--comparison`, D-382 item 2).
- The pair only measures a time factor (D-389): a figure on one type is never compared with a figure on another, with or without the pair (`factor_record.require_machine_pair`). A comparison that moves to the new type re-runs every arm on it.
- The A10 figures already read stay A10 figures, with no conversion by the time factor.
