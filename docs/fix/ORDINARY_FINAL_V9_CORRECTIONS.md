# The pass after ordinary final run v9: the preamble unit, and the asset copy designed

Status: **B IMPLEMENTED AND PROVEN LOCALLY; A DESIGNED, NOT AUTHORIZED; NO LAUNCH.** Local only:
no cloud, no model execution, no weight loading. No weights, HPO settings, telemetry
architecture, workload or routing changed. The one behaviour change is in the unit splitter and
is stated under B, including the one new model call it will cost a run and the catch it does
NOT produce.

## The judgment, before starting

B was the right item and the right order, but its premise did not survive measurement:

- **It will not reach the fifth planted entry.** The sheet writes its per-laboratory counts as
  `Result count declared, Northgate laboratory: 4`. The structural label reader
  (`pairing_map._LABEL_LINE`) admits no comma inside a label, so those two lines are not
  fields. The header yields one scalar (the declared total, 6) and no addends, and
  `compute_checks` on it against CONV-L03 returns nothing. With the unit in place the rule
  pairs on the header, because its words name `total result count declared`, but the plan is
  `uncomputable`: a model question, which the promotion invariant keeps out of the amendments.
  Widening the label reader would reach the catch and would change label parsing on every
  corpus; it is a separate decision, recorded below, and was not made here.
- **It was less contained than measured last pass.** `bounded_extraction.ledger` derives span
  ownership from `split_units`, so a preamble unit changes the owner of the preamble span and
  the `unit_index` of every hydrated PROCESSOR item. Two other corpora carry fields in their
  preambles (`http`, `two offer`) that enter those vocabularies. Both were measured on all
  twelve documents rather than assumed harmless.

A as design-only was right. Not launching was right, and B strengthens it: a run now would
measure one extra uncomputable model call and no new catch.

## B. The preamble unit

**What changed.** `pairing_map.split_units` makes a unit of the text before a document's first
body heading whenever that text carries content beyond heading lines and horizontal rules
(`_preamble_unit`). Its id is `u00-` plus the slug of the document's own H1 title, the way a
section is named after its heading, and never a heading ordinal; its kind is `preamble`, its
index 0. A lead that is only a title line makes no unit, so the gate's shared fixtures still
split into their headings alone. `unmatched_findings` skips a preamble: "no rule applies" is its
normal state, not a missing field.

**Before and after, every corpus document.** Measured with the real splitter, vocabulary,
pairing map, unmatched net and extraction ledger, before and after the change
(`scratchpad/split_before.json`, `split_after.json`, diffed):

| Document | Units before to after | Existing ids moved | Span ids and offsets | Vocabulary added | Pairing changes on existing units |
|---|---|---|---|---|---|
| catalogue_records/catalogue_records.md | 6 to 7 | none | identical (7) | none | 0 |
| catalogue_records/metadata_element_reference.md | 4 to 5 | none | identical (5) | none | 0 |
| clinical_reference/analyte_reference_ranges.md | 4 to 5 | none | identical (5) | `http` | 0 |
| clinical_reference/result_sheet.md | 6 to 7 | none | identical (7) | `batch`, `total result count declared` | 12, all CONV-003 undecided to rejected on the six results |
| device_log_review/device_class_reference.md | 2 to 3 | none | identical (3) | none | 0 |
| device_log_review/device_log_flawed.md | 19 to 20 | none | identical (20) | none | 0 |
| device_log_review_clean/device_class_reference.md | 2 to 3 | none | identical (3) | none | 0 |
| device_log_review_clean/device_log_clean.md | 19 to 20 | none | identical (20) | none | 0 |
| negotiation_r2_to_r3/offer_2024_09_23.md | 6 to 7 | none | identical (7) | none | 0 |
| negotiation_r2_to_r3/offer_2024_10_19.md | 6 to 7 | none | identical (7) | none | 0 |
| negotiation_r3_to_r4/offer_2024_10_19.md | 6 to 7 | none | identical (7) | none | 0 |
| negotiation_r3_to_r4/offer_2024_10_31.md | 5 to 6 | none | identical (7) | `two offer` | 0 |

On every document the only span whose owner changed is the preamble span (from no owner to
`u00-...`); every span identity and offset pair is byte-identical, so the PROCESSOR wire is
unchanged. Every existing unit's index rose by one, which is the list position `index` is
defined as; nothing parses the numeric prefix. The identities measured before the change are
pinned in `benchmark/fixtures/unit_identity_before_preamble.json` and check 273 requires every
one of them to survive.

**The regression the diff caught.** On the two negotiation offers dated 2024-10-19, every rule
is rejected on the preamble and none is undecided, so the unmatched-findings net fired on it and
would have minted a computed `missing_field` finding, and so an amendment, against a document's
title block. The exclusion above removes that; the pre-existing finding on `u06-summary-table`
in those documents is unchanged, and no preamble reaches the net on any corpus.

**CONV-L03 on the sheet, measured.** The header unit carries `batch` and
`total result count declared`. CONV-003 names the latter, pairs on the header, and is rejected on
all six results (`unit lacks total result count declared`). `extract_fields` on the header
yields the one scalar and no columns; the two per-laboratory lines fail `_LABEL_LINE` on the
comma. `plan_calls` produces exactly one CONV-003 plan, on the header, of kind `uncomputable`.
No computed check, no absence, no computed amendment. **Recall on a new run would still be 4 of
5 by the computed path**; the fifth entry would be answered, if at all, by PRACTICE_AUDITOR's
model judgement on the header, which stays on the bus and never becomes an amendment.

**The v9 saved evidence, re-scored under the changed splitter:** 4 of 5 with reasons confirmed,
zero false positives, zero distractor hits, unchanged. The saved bus carries no CONV-003 finding;
a splitter change cannot mint one retroactively, and the scorer still reports the sheet entry as
`EVIDENCE_ABSENT_FROM_CORPUS` against v9's own pairing map.

**What a run will do differently.** Phase 5.5 gains one PRACTICE_AUDITOR call (the uncomputable
CONV-003 plan on the header) where v8 and v9 made none; every PROCESSOR item carries a
`unit_index` one higher and the header's item carries a unit id; the pairing map records
CONV-003 as paired on one unit and rejected on six instead of undecided on six. Nothing else in
the workload changes.

**The decision that actually reaches the fifth entry.** Either the label reader admits a comma
inside a label (a parser change that runs on every corpus and needs its own before-and-after
measurement, exactly like this one), or the operator's document writes the labels without one
(which edits the test). Neither was done. The first is the honest candidate for a later pass.

**Proofs.** Check 273 with four executed proofs and one neutralize/fail/restore/pass entry (a
splitter that makes no preamble unit reproduces the pre-change state, under which CONV-L03 could
reach no unit). Two earlier proofs (checks 270 and 272) pinned the old shape and were
re-measured to the new one; nothing in the code moved to satisfy them.

## A. The provider-side asset copy, designed only

**The problem in figures.** Across v5 to v9 the asset upload is 36.9 to 37.8 minutes of a 52.8
to 55.4 minute billed run: 68 to 70 percent. The archive is 13,149,972,480 bytes and has not
changed since v5 (`8f0cbd81...`, rebound five times). Everything else on the instance takes about
15 minutes including the workload.

**Where the copy lives.** A provider-side persistent filesystem in the same region (Lambda's
filesystems attach to an instance at launch and persist independently of it). The copy is the
sealed `assets.tar` byte for byte, plus one sidecar `assets.sha256` written by this machine.
Keeping it there costs storage at the provider's rate for about 13 GB; at typical block-storage
pricing that is on the order of $2 to $3 a month, which is roughly the upload cost of two runs.
The copy exists in exactly one region; a run in another region uploads as today.

**How a run proves the remote copy is the sealed archive.** Today's guarantee is a sha256 the
instance computes over bytes this machine sent, compared to the manifest. The copy keeps that
guarantee by moving the hash, not weakening it: the instance hashes the attached copy in the
same `archive_integrity` phase and compares it to the manifest's `assets_archive.sha256`. The
manifest is still transferred from this machine with the support files, so the comparison is
against a value the sealer wrote locally, never against the sidecar. The sidecar is a
convenience for the controller's pre-check, not the proof. If the hash disagrees, the copy is
untrusted and the run refuses (see below). Hashing 13 GB on the instance took 19.8 to 20.4
seconds in every run; that phase does not get longer.

**When the sealed assets change.** The copy is keyed by its hash: the filesystem holds
`assets-<sha256 prefix>.tar`. A bundle whose manifest names a different assets hash finds no
matching copy and the controller falls back to uploading, then (only after the instance has
verified the uploaded bytes against the manifest) writes them to the filesystem under the new
name. The old copy is deleted only by an explicit operator action, never by a run. Rebinding,
which has been every seal since v5, changes nothing: same hash, same copy.

**Missing, stale, partial or unreachable.** One rule: the copy is used only if the instance's
own hash of it matches the manifest; every other state is "no copy." Missing (no file under the
expected name) and stale (a file under another hash's name) are the same case: fall back to
upload. Partial (file present, hash mismatch) is treated as corruption: fall back to upload and
mark the copy for deletion in the receipt, never overwrite it silently. Unreachable (filesystem
failed to attach, or attached but unreadable) is fall back to upload. In every fallback the run
proceeds exactly as v9 did, and the receipt records which path was taken and why. The run
never refuses because a copy is absent; it refuses only where it refuses today, on a hash that
does not match after the bytes are on the instance.

**The phase sequence.** `assets_transfer` becomes a three-way phase: attach and hash the copy;
on match, skip the upload; on any other outcome, upload as today and then seed the copy. Every
phase after `archive_integrity` is unchanged, and `archive_integrity` itself is unchanged, since
it hashes whatever is on the instance. The rehearsal today proves the archive it is about to
send is intact and that a corrupted archive is refused; with the copy it must additionally
rehearse both polarities of the copy path on the local Linux target: a matching copy that is
used and an unmatching one that is refused and replaced by upload. The single-workload claim
and the fresh-directory precondition are untouched; the record that two authorizations were
lost to transport changes is the reason the fallback is "do exactly what v9 did."

**What it would have to prove locally before a run depended on it.** (1) The controller's
attach-and-hash step on a local filesystem with a matching copy, a mismatching copy, a missing
copy and an unreadable path, each producing the documented outcome and receipt. (2) That a
manifest naming a new assets hash never matches an old copy. (3) That the fallback path is
byte-identical to the current `assets_transfer` phase: the same scp invocation, the same
integrity check, so the v9-proven path is what runs when the copy is absent. (4) That seeding the
copy happens only after the instance has verified the uploaded bytes, and is skipped on any
integrity failure. (5) The rehearsal extended with the two copy polarities. Only after those
five, one authorized run whose receipt shows the copy was used and the hash matched.

**Expected saving.** Upload is 37 to 38 minutes per run; a hash of the copy is about 20 seconds,
already paid today. The saving is about 37 minutes of a 54 minute run, or $0.80 of $1.16 at
$1.29 an hour, leaving a run at about 17 minutes and $0.36. Over the five runs so far that
would have been about $4.00 of $5.81.

**What could make it smaller.** Filesystem attach time at launch, which is unmeasured and
could be minutes; storage cost, which accrues whether or not a run happens and exceeds the
saving if fewer than about three runs a month occur; a region without capacity, which forces
either a wait or an upload; the first run after any asset change, which uploads and seeds and
saves nothing; and any provider-side read throughput slower than the local disk, which would
lengthen the 20 second hash. The saving is real only for a cadence of several runs a month in
one region against unchanging assets, which has been the case since v5.

## Part 3

See the gates table below and the sealed bundle in the commit that follows.
