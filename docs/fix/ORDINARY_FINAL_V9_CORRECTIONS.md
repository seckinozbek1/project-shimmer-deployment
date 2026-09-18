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

## The second half of the pass: what the first half turned up

### 1. The label reader and the comma: measured, and left alone

Measured with the comma admitted into the label character class, patched in process over all
twelve corpus documents (`scratchpad/split_comma.json` diffed against the current tree):

| Document | Lines that become label lines | Vocabulary added | Pairing changes on existing units |
|---|---|---|---|
| catalogue_records/metadata_element_reference.md | `Metadata Element Set, published at https://...` | `metadata element set published http` | 0 |
| clinical_reference/analyte_reference_ranges.md | `A returned result sheet states, for every result: the sample identifier, ...` | `returned result sheet state every result` | 0 |
| clinical_reference/result_sheet.md | the two per-laboratory count lines | `result count declared eastfield laboratory`, `result count declared northgate laboratory` | 0 |
| the other nine | none | none | 0 |

Two of the three documents gain a FALSE field from a prose sentence that happens to hold a comma
before a colon. Pairing on existing units changes nowhere, because no rule names those words.

And the decisive fact: **it does not reach the fifth entry anyway.** With the comma admitted the
header yields three scalars (6, 4 and 3) and no column, and `compute_checks` still returns
nothing, because the sum check sums a TABLE COLUMN against a scalar whose label contains the
column's words and requires the column to carry a unit; there is no scalar-plus-scalar form and
the counts carry no unit. CONV-003's plan stays `uncomputable`. Reaching the entry would need new
arithmetic (a sum of like-labelled scalars against a total), which is exactly the adjustment the
operator ruled out. **Decision: not implemented.** A contained version, if the entry is ever
worth it: admit a comma only when the line's value parses as a quantity, which excludes both
prose sentences above and admits both count lines, together with a scalar-sum check as its own
measured change. Neither was done.

### 2. The asset copy's five local proofs, built

The design's mechanism is now in the controller, off by default, with its proofs in
`tools/ordinary_final_controller_checks.py` and its polarities in the rehearsal. Nothing
authorizes its use; a bundle with no `asset_copy_declaration.json` runs the v9 path unchanged.

| Proof | What it executes | What it establishes |
|---|---|---|
| 1. attach-and-hash in four states | the real `execute()` against a modelled mount: MATCH, MISSING, MISMATCH, UNREACHABLE | MATCH is copied into place and no upload runs; the other three upload; MISMATCH is recorded suspect and the copy is untouched; UNREACHABLE never seeds |
| 2. a new digest never matches an old copy | a mount holding `assets-<old digest>.tar` against a manifest naming another digest | the probe reports MISSING, the upload runs, the seed lands beside the old copy, which stays |
| 3. the fallback is byte-identical | the scp argv with no declaration against the argv with a MISSING copy, bundle paths normalised; the launch body with no declaration | identical argv; no `file_system_names`; no `asset_copy_*` phase; the receipt says `declared: false` |
| 4. seeding only after verification | phase order MISSING to `archive_integrity` to `asset_copy_seed`; `archive_integrity` scripted to fail | the seed starts only after integrity passed; on failure no seed is attempted and the mount is unchanged |
| 5. the rehearsal, three polarities | the real controller through a real Linux shell with a directory standing in for the mount: matching, corrupt and missing copies | see the rehearsal receipt for the bundle sealed at the end of this pass |

One neutralization is in the controller gate: a probe that stops hashing (`echo MATCH`) makes the
corrupt copy get used, and the MISMATCH proof fails. The provider adapter admits exactly one
`file_system_names` entry, label-validated, and refuses two, or any other new field; that is
proven too.

**What remains unprovable without a run:** that the provider attaches the named filesystem at
launch and mounts it where the declaration says; the attach time, which the saving estimate
does not include; and the throughput of hashing 13 GB from that mount, which the estimate takes
from the instance's local disk (about 20 seconds in every run). The local proofs cover the
controller's decisions on every outcome; they cannot cover the provider's part.

### 3. README.md

In the preamble pass the README moved by one sentence, under Optional capabilities: a document's
title block is its own unit and existing ids never move. Reviewed in full against the system as
it runs, it was accurate but silent on two things that now shape every run, and both were
added under Results and evidence: every amendment is rendered from a Python-computed finding and
a model's finding never becomes one; and an operator may withhold a phase-5 auditor per review
scope in `config/review_scope.json`. Nothing in it describes the asset copy, correctly, since no
run uses it.

### 4. What else this pass set aside

- **A new model call.** The preamble unit gives CONV-003 one `uncomputable` plan on the sheet
  header, so PRACTICE_AUDITOR is asked one question per run where v8 and v9 asked none. This
  is the designed behaviour for a paired rule nothing computes; the answer stays on the bus and
  never becomes an amendment. Recorded, not changed.
- **False fields in two preambles.** The analyte reference's URL line reads as a field `http`
  and one negotiation offer's lead reads as `two offer`. Pre-existing reader behaviour now
  exposed by the preamble unit; no rule names either word, so nothing pairs on them. Recorded.
- **Prior-version comparison.** Measured on both negotiation pairs with and without the
  preamble unit: 6 and 12 records, nothing added or removed. Closed.
- **The controller is not among the four files the seal hashes** (`local_control_hashes` covers
  the watchdogs, the common module and the runner). It IS hashed into the launch receipt and the
  bound-controller identity at launch, so a run records which controller ran, but the seal does
  not pin it. Noted for the operator; not changed, since changing what a seal binds is its own
  decision.
- **From the discovery pass, still open by design:** the classifier's discrimination (a corpus
  question), the partial-delivery path (proven locally only), FACT_CHECKER (in the backlog).

## Part 3, both rounds

The preamble pass (round one, `docs/fix/ordinary_final_v11_gates/`): correction checks 33 of 33;
compact 85 PASS; mutations 15 of 15; controller, startup, decoding green; integration 147 tests
and 30 proofs; main gate 256 checks with zero new failures against the clean baseline 5479ced;
sealed as bundle v10 and rehearsed, both polarities.

The second half (round two, `docs/fix/ordinary_final_v12_gates/`): controller gate 20 tests and
4 neutralize/fail/restore/pass proofs including the asset-copy probe; the transport, transfer
and cloud-run checks the README names (83 tests, network blocked) green after the adapter
change; integration 147 tests and 30 proofs; compact 85; mutations 15 of 15; startup and
decoding green; main gate 256 checks with zero new failures against the clean baseline a867a99.

One thing is recorded rather than smoothed over. The first main-gate run on the round-two tree
failed check 256 ("sensitive health imported a model probe while inactive"), a check that passed
on the previous tree, on the baseline, in isolation three times, paired with its predecessor
255 three times, and on the same tree in a second full run. It failed once in one full-gate
process and did not reproduce; the first log is kept as `main_gate_first_run.log` beside the
second. Nothing this round touches startup or preflight. It is a state-dependent failure inside
the gate process, observed once, and it is not attributed to any change here.
