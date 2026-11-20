# The synthetic negotiation items' deduplication inputs (NEG-SYNTH-A step 2 and 3, D-732, D-707)

19 November 2026, lane/syn-dedup-inputs (from lead/night-20261119 c6b58904). Rules: NEG-SYNTH-A, EMBED-ROUTE-A,
GATE-LEAKAGE-A, LAUNCH-CHAIN-A, PARALLEL-LAMBDA-A (each Lambda step up to 5 USD pre-approved, D-708).

## 1. What was wrong

The synthetic sets (pilot_1, dev_1 and the 53-item validation set of role S session 3) were never deduplicated.
`tools/neg_synth_dedup.py check` needs reference fingerprints, and neither existed in the form needed:

- role N session 36 handed back `_xfer/N_to_lead/S36/reference_N_noembed.json` only (corpora 59,757, dev 17,608,
  pilot 1,757, rounds 4,478 records; hashes, no vectors): its embedded run waited for about 4.4 GiB of free RAM;
- the lead's fingerprint of the development material it reads (`reference_lead.json`, D-732 wave 1) was never made;
- role B's SYNDEDUP2 request runs `check ... --embed`, which loads bge-m3 (about 2.3 GiB) on a laptop with about
  1.4 GiB free; `within` needs the embedder too.

A second limit was found on the way: the fingerprint keeps its vectors as JSON floats, about 20 characters each, so
the lead's 30,033 rows would be about 600 MB of JSON and role N's larger, which no process on this laptop can load.

## 2. What was built (a37ccd7f)

`tools/neg_synth_dedup.py`:

- `export (--part ... | --candidates ...) --out-dir DIR`: the exact texts `fingerprint`, or `check` and `within`,
  give the embedder, in the one embedding form, written as `freeze_negotiation_set.export_records` does
  (`records.jsonl`, one row a distinct text keyed by its SHA-256, and an empty laptop run for the merge). No model.
- `--vectors <merged> --records <records.jsonl>` on `fingerprint`, `check` and `within`: the merged vectors of the
  replay pass (`embed_records.py merge --require-complete`) stand in for bge-m3 through
  `freeze_negotiation_set.vectors_encoder`, which refuses another key list, a missing row and a text the records do
  not hold. `--embed` and `--vectors` together are refused.
- `fingerprint --sidecar`: the vectors go to `<stem>.vectors.npy` beside the fingerprint (float32, one row a distinct
  text, the owning parts listed per row); the JSON keeps the file name, shape and SHA-256, and `check` memory-maps it
  read-only and refuses a missing, changed or misshapen file. The inline form stays as it was for small fingerprints.
- Proof `dedup_takes_the_rented_route_vectors_as_the_embedder` in check 459 (`tools/neg_synth_checks.py`): the routed
  vectors equal the embedder's, `check` and `within` give the same ids, the sidecar form gives the same cosine ids, a
  changed sidecar and an unknown text are refused; neutralised (the route embedder made to return zeros), failed,
  restored, passed. Group 459 run alone: 5 proofs PASS. The gate was not run on the laptop.

## 3. The lead's fingerprint: launched through the chain

Folder `external/s05/SYN_DEDUP_LEAD` (outside git), built from `GNN_TRAIN_6f48d5ed`'s, whose bound worktree
(`.claude/worktrees/gnn-train-6f48d5ed` at 6f48d5ed, diff empty, LF, frozen files linked) it uses read-only: its
`embed_records.py` is byte-identical to the lane's, and nothing of the new dedup code runs on the instance.

- Material (`parts.json`; NEG_FINAL_ITEMS_METHOD.md section 2 and NEGOTIATION_CORPORA.txt: the development sets under
  `external/` that role N cannot read): `development` = ContraDoc dev and dev_moved, SciTab dev, and the small
  `external/s05` development folders of `gate_set.PART_PATHS_2026_11_16` (D-S45, labels, suite_gen,
  suite_staging.json, R1, SAVINGS_PROOF, miss_diag, staging_records_d092); `judge_training` = the two judge
  prompt files T2E and T_TRAIN. 53,106 texts, 30,033 distinct rows, 44.8 M characters (about 4.6 M tokens after
  bge-m3's 8,192-token cut on the two longest rows). Export peak about 0.27 GiB.
- Left out, with the reason: `external/s05/R2` (662 MB) and `R_constraint` (134 MB) and the run-evidence folders
  REFPAIR, ROUTE_GATE_174_340 and T253 (tens of GB of archives): the laptop cannot read them at its free memory;
  J1 is no longer on disk. Open item 164.
- The pass: `work/embed_parts/part01/replay_prompts.json` (embed-records-v1, 15 chunks, 23.5 MB, one part; the
  sealer's replay declaration reads 15 prompts, the credential scan 0 hits, the pass options are accepted), one
  exposed B1 bundle `SYNDDL_EMBED` sealed through route S, one A10 launch.
- Cost (tools/loop/step_cost.py on the fresh inventory of 19 November 15:53 UTC, A10 at 1.29 USD an hour): seal 32 min
  0.89 USD; embedding 58 min 1.62 USD with the asset copy (66 min 1.84 USD without); 2.52 USD in all. Each step's
  guard cap (1.5 x forecast: 1.34 and 2.43 USD) is under the 5 USD pre-approval; the watchers stop each step there
  and both together at 5 USD, writing STOPPED_ASK.txt.
- Armed: `chain.json` (request, seal, admit, embed) at 18:49 +0300 after the preflight passed. The chain's first
  request (18:52) failed before any provider call: `inputs/provider_inventory.json` was missing (0 USD). Fixed:
  `launch.py inventory` run (read-only), the preflight now refuses without the inventory and the lock, preflight
  passes again. The chain's retry wrote the seal request at 19:07:01 (rc 0) and started the seal
  (purpose syn-dedup-lead-seal) at 19:07:07; admit and embed follow on the chain.
- After the embedding, by hand: `launch.py result` (needs 1.0 GiB free) merges the vectors, builds
  `result/reference_lead.json` with `reference_lead.vectors.npy` (30,033 x 1,024, about 123 MB) and copies both to
  `_xfer/lead_to_B/syn_dedup`, digests and counts in `result/handover.json`.

## 4. Role N's embedded fingerprint: a request, not a lead run

The lead cannot run the route on role N's material: `reference_N_noembed.json` holds hashes only, and role N's
texts (its corpora list, the development items, the pilot and the real rounds) never leave role N's folder except
inside the route's own sealed pass, which only role N can build. Written:
`_xfer/lead_to_N/syn_dedup/REQUEST_ROLE_N_SYNDEDUP.md` with the code bundle `shimmer_f1961c32_to_a37ccd7f.bundle`
(1,012,537 bytes, SHA-256 9fdbb632...; base f1961c32, which role N has since session 41). Part A: export with its
session 36 parts, `embed_records.py build`, the pass files and `EMBED_PASS.json` (digests and counts) to
`_xfer/N_to_lead/SYNDEDUP`, STOP; if a rule of role N's forbids a part (for example the real rounds) from travelling,
it hands over nothing and the lead asks Seckin (the 14 November freeze route carried the held-out set). The lead then
seals and launches the parts unopened (a folder like SYN_DEDUP_LEAD) and places the evidence in
`_xfer/lead_to_N/syn_dedup/evidence`. Part B: merge, `fingerprint --vectors --records --sidecar`, counts equal to
session 36's, `reference_N.json` and its sidecar to `_xfer/N_to_lead/SYNDEDUP`. Start file
`docs/loop/private/role_starts/start_n_syndedup_a.cmd`: role_start_check PASS. Not started.

## 5. Role B: the start files match what will exist

The SYNDEDUP2 request (not read by the lane: lead_to_B is write-only for it; role_start_check printed its one
command, `check ... --embed`) is kept and amended by `REQUEST_ROLE_B_SYNDEDUP2_ADDENDUM.md` in the same folder, with
the code bundle `shimmer_e958ecc4_to_a37ccd7f.bundle` (11,619 bytes, SHA-256 0fb36c26...; base e958ecc4, which role B
has since BSTF2): no `--embed`; the two fingerprints are `reference_N.json` and `reference_lead.json`, each with its
sidecar; all three sets (SYNDEDUP1 never ran); two sessions.

- `start_b_syndedup2a.cmd` (new), Part A: candidates of the three sets, `export --candidates`, `embed_records.py
  build`, the pass files and counts to `_xfer/B_to_lead_dev/SYNDEDUP2`. role_start_check: PASS. It needs no
  fingerprint, so it can start now, beside the lead's launch.
- `start_b_syndedup2.cmd` (changed; the old one kept as `.pre_addendum`), Part B: merge, `check` against both
  fingerprints with `--vectors`, `within`. Its precheck now names the files that will exist: Part A's done file,
  `reference_N.json` and `reference_N.vectors.npy`, `reference_lead.json` and `reference_lead.vectors.npy`, and
  `evidence/EVIDENCE.json` of the candidates' launch. role_start_check: FAIL on exactly those six, every other guard
  and all 10 request commands ALLOWED; it passes once they are placed. Not started.

## 6. What waits on whom

| Step | Waits on | Cost |
|---|---|---|
| SYN_DEDUP_LEAD request, seal, admit, embed | the launch chain (armed) | 2.52 USD forecast |
| `launch.py result`, copy to role B | the lead, after the embed; 1.0 GiB free RAM | 0 |
| Role N Part A | the lead starts start_n_syndedup_a.cmd | 0 |
| Role N's parts sealed and launched | the lead, after N Part A (one folder like SYN_DEDUP_LEAD a part) | about 2 to 3 USD a part, forecast from N's row count |
| Role N Part B | the lead places the evidence and starts it | 0 |
| Role B Part A | the lead starts start_b_syndedup2a.cmd (can be now) | 0 |
| Role B candidates' launch | the lead, after B Part A (small: a few thousand rows) | about 2 USD |
| Role B Part B | reference_N, reference_lead and the candidates' evidence placed | 0 |
| Any synthetic figure | role B's counts and role S's drops | |
