# The producer's training attempt (D-S57 item 3, D-S62 items 4 and 5)

Written on lane `producer` at `aa17a653` on 8 November 2026, BEFORE any training row is built and
before any of the test items below is read with a candidate. Nothing here has run. A change to any
part of this file after training data exists starts a new attempt (D-S62 item 4).

## 1. What is frozen first

The contract, the prompt and the role map this attempt trains for, by SHA-256 (CRLF read as LF):

| File | SHA-256 |
|---|---|
| `config/compact_extraction_prompt.json` (the validated two-turn prompt, EXTRACTION-A) | `d19bc35f4eab1e75f08a6a5504d5cf78cfc5036aa066986289e8fa03947b68e3` |
| `config/contract_decoding.json` (DECODING-B) | `0370183d9d351edef78fc4050587256162c58da832d9b8612ccf98d1ac5dbdbd` |
| `scripts/compact_contracts.py` (the validator, unchanged) | `f8226a727bc2bde4e534a8463dee7be53db17913e4fb23e2d8566e870c6c3003` |
| `config/agent_contracts.json` | `04b5be8c326d1cd5000c95c788c36a18cb7c6d1a1e30dd4c4143aafd51b5ce4e` |
| `config/decoding_policy.json` | `a51a93f054918712177e9178367c9afdd7495da735575504c2475a1294f299c6` |
| `tuning/producer_v3/evaluation_protocol.json` | `51da77c94497ef74b5f913901c20abbe965101dbbb950cb0d5b62b4c16b3cc1a` |

Role map: unchanged (`pipeline._LOCAL_PROFILE`; every local_producer role on the producer).
INFRA-050 is not applied and nothing here needs it. Checkpoint 168's prompt stays byte for byte
(check 263): the candidate is trained and tested on exactly that prompt form.

## 2. The change from 168, named first

The same recipe as 168 (`tuning/producer_v3/experiment.json`: the 4-bit base, LoRA rank 8,
alpha 16, dropout .05, the seven projections, AdamW 1e-4, batch 4, two passes, strict
determinism), on MORE and more varied data. The 336 training rows of v3 (machine-authored, 20
domains) are kept, and about 340 rows are added. In those rows real public text carries the
planned atoms. One thing changes and one thing is measured: whether real carrier text from new
source families teaches the contract so that it holds without the constraint, and transfers to
spans unseen in training. Only the full checkpoint is tested. The half checkpoint is saved and
not read, so no checkpoint is chosen on the test items.

## 3. The mix, stated before it is built

| Source (training split only) | Licence, read from its card on 8 November | Family | Rows |
|---|---|---|---|
| v3 rows (`tuning/producer_v3/dataset.json`, train) | the repository's own, machine-authored | 20 constructed domains | 336 |
| GovReport (`launch/gov_report`, train) | CC BY 4.0 | government research reports | 140 |
| BillSum (`FiscalNote/billsum`, train, US bills only) | CC0 1.0 (the card states no licence for the California bills, so they are not used) | legislation | 100 |
| QASPER (`allenai/qasper`, train) | CC BY 4.0 | scientific papers (SciTab's family) | 40 |
| TAT-QA (`next-tat/TAT-QA`, train) | CC BY 4.0 | financial reports (FinDVer's family) | 40 |
| FinQA (`czyssrs/FinQA`, train) | MIT (the repository's LICENSE) | financial reports (FinDVer's family) | 20 |

From the benchmarks' own source families: 100 of 676 rows, 14.8 percent, under D-S62 item 5's
quarter. Left out: every share-alike source (Wikipedia text and tables, TabFact's Wikipedia
tables although its code is MIT, FEVER), D-281. Also left out: CUAD, ContractNLI, SciTab,
ContraDoc and FinDVer in any split, every development item named below, and everything sealed. A
candidate trained on this mix is publishable under D-281. Each licence is quoted again in the
data manifest the builder writes.

How a row is made: v3's compositional method (`tuning/producer_v3/author.py`). A public paragraph
is the carrier. Python inserts declared atoms from the frozen policy's own categories: claims under
CLM ids, gap statements, uncertainty, refs it places itself (EXTRACTION-B). It builds the canonical
target from what it inserted, so every label is known by construction and none is judged. A
carrier paragraph sharing an 8-word run with any test item below is dropped, as T did. The rows
are rendered through `compact_contracts.validated_messages`, the run-time form, at most two owned
spans a request (EXTRACTION-C).

## 4. The test, the same items for 168 and the candidate, and the rule

Every item is replayed in one session on both checkpoints, through `replay_prompts.py`'s paths:
`sdpa_constrained` is the product's path and `sdpa` the unconstrained one.

- **(a) DEV-84** (`--dev`; read before, exposed). Under `sdpa_constrained`, no row that is valid on
  168 may be invalid on the candidate, and the refusals must be the same 9 rows.
- **(b) The 52 saved failing partitions** (R1's `records` set,
  `external/s05/R_constraint/bundle_B1/replay_prompts.json`, sha256 `75d11e8a...`; read before).
  Under `sdpa`, decoded WITHOUT the constraint: 168 is valid on 0 of 52. The candidate is better
  when its candidate-only valid count k has a one-sided sign test of 0.5^k at most .0125 (k at
  least 7 with 168 at 0). Under `sdpa_constrained` both must stay 52 of 52.
- **(c) A fresh set of about 100 spans** in the run-time form. Half come from documents of the
  training sources that no training row uses. Half come from one held-out public source, chosen
  and its licence read before the set is built. Labels are by construction. The set is written and
  its digest committed before training, and it is read once. Score: a row is right when its reply
  equals the constructed target item for item (claims, refs, questions, uncertainty, status) under
  `sdpa_constrained`. The candidate is better at .0125 by the sign test on the discordant rows.
- **(d) No regression on the other roles.** The roles file
  (`benchmark/baselines/producer_replays.py roles`, 180 prompts of six roles) is replayed with the
  candidate's adapter. On any role where 168 is better than the candidate under that file's rule
  B, the candidate fails.

**Replacement rule.** The candidate replaces 168 only when (a) holds, (d) holds, and (b) or (c)
shows it better. Otherwise 168 stays (D-S57 item 3), and the result is reported as measured.
Every reading is on development items, (a) and (b) already read, reported as such (D-S62
item 1). Attempts are counted.

## 5. What must be built, none of it a bound controller file

1. A data builder (public carriers, the policy's atoms, the manifest with licences, the overlap
   filter).
2. `benchmark/baselines/producer_train.py`, riding the replay pass as `judge_train.py` does
   (schema `producer-training-v1`). It trains on the v3 recipe with loss over the canonical target,
   then runs (a) to (d) on 168 and on the candidate.
3. In `bare_model.LocalBackend`, final mode loading the base with a declared adapter, beside the
   resident 168.

Gate proofs for each, with neutralisations.

## 5a. Built, before any training (8 November 2026)

Built from carriers fetched on 8 November (`tuning/producer_v4/fetch.py`, `sources.json`) by
`tuning/producer_v4/author.py`, rebuilt byte for byte from the same carriers. Nothing has been
trained or read with a candidate.

- **Training rows.** `external/s05/P1/v4/train_rows.json`, sha256
  `18edd92af4f65ec36c21f2e34d13610c98c79b4d308e1b8a7eedd8ace68a1283`.
  - 676 rows: v3 336, GovReport 140, BillSum 100, QASPER 40, TAT-QA 40, FinQA 20.
  - Benchmark families 100 rows, 14.79 percent. 64 refusals, 179 two-span rows.
  - Every v4 target passes the run's compact validator on its own rendered prompt (308 valid);
    the 32 refusals are refused by it as designed.
  - Mean 928 tokens a v4 row (longest 1,472), against v3's 783 (longest 984).
- **Fresh set.** `external/s05/P1/v4/fresh_prompts.json`, sha256
  `708555b360b89c207e52e3a74ef89717b1ad9633524eb151e40f0d5bd28a1c69`.
  - 100 spans: in-family GovReport 17, BillSum 17 and QASPER 16, from documents no training row
    uses; held out PubMedQA 50.
  - 92 targets valid and 8 refusals. Each prompt was rendered by the renderer that reproduces all
    84 DEV prompt digests.
- **Sealed training file.** `external/s05/P1/train_bundle_inputs/replay_prompts.json`, recipe
  `b750af8fcd9a08e16d460c4900572ec6942add408e3c0e2a10a627e32c8a633a`, file sha256
  `37755823692a9a638135d390d880456e332cc54452682ab2781f4e94e4c48340`.
  - The compact test: 472 rows, 236 prompts each asked of `tuned` and `candidate` (DEV 84,
    the 52, fresh 100).
  - The roles file: 360 rows, `base` asked of `candidate` instead.
  - Training time cap: 5,400 s.

## 6. Forecast (rates partly measured, partly assumed)

Revised on the built rows. **Training:** 676 rows x 2 passes is about 2.2 times v3's tokens a pass
at v3's measured rate (16.4 minutes for 168 updates), so about 36 minutes. **Test:** 472 rows on
two paths, 944 generations at about 15 s each, from R1's measured 272 in 96 billed minutes
including setup (an estimate), about 236 minutes. **Roles:** 360 rows on sdpa, about 150 minutes
(assumed: the candidate is taken to write as much as 168). **Total:** with setup 20, upload 64 and
pack 15, about 521 minutes: 11.20 USD at 1.29 an hour, x1.3 = 14.56, cap 21.84. Without the upload,
457 minutes: 9.83, 12.78, cap 19.17. The original estimate follows.

- **Training.** About 338 updates at v3's measured 5.85 s median an update (16.4 minutes for 168
  updates, A10, `docs/fix/PRODUCER_TUNING_V3_RESULTS.md`). Real carrier text is longer, so 1.5x is
  assumed: about 50 minutes.
- **Evaluation, per checkpoint.** DEV-84 on two paths, about 45 minutes, from v3's 15 to 17 s a DEV
  generation. The 52 on two paths, about 35 minutes (assumed from R1). The fresh set on two paths,
  about 54 minutes (assumed). The roles file, about 75 minutes for the candidate only, at about
  8 tokens a second estimated from saved record timestamps; 168's rows come from the roles replay.
  Candidate about 209 minutes, 168 about 134 minutes.
- **Total.** Setup 20, upload 64 (0 on an asset-copy MATCH), pack 15: about 492 minutes,
  10.58 USD at 1.29 an hour, x1.3 = 13.75, cap 20.63 (without the upload: 428 minutes, 9.20,
  11.96, cap 17.94).
- **Parallel option.** 168's evaluation needs no training, so it can run on a second instance at
  the same time (the four-instance limit of that day is gone, D-S95).

## 7. By 12 November

- **Can be ready:** the two replays (bundles ready to seal now), this plan, the builder, the
  trainer and the fresh set, built and gated over about 9 and 10 November, and one sealed
  training session read by 11 November.
- **Cannot be:** any role other than PROCESSOR trained in a narrow run-time form. That needs
  INFRA-050 answered and contracts that do not exist yet; it continues after 12 November and is
  named in the 9 November report.

## 8. Success rules, written before any attempt (D-S72 item 2, D-S73; 8 November 2026)

These rules come before the first launch and are attacked by a fresh checker with every lane's
rules. They replace section 4's single replacement rule with a success rule and a progress rule.
Section 4's conditions (a) to (d) are the base. They act on lessons in `docs/loop/LESSONS.md`
(loop branch `594d3284`; L-6 from its later state), and were fixed under D-330 (HELDOUT_OPENINGS.md at `235194fd`):
- **L-3:** training taught a different question when the rows were not in the run-time form.
  Every row here is in 168's run-time form, and each target passes the run's validator.
- **L-4:** an effect chosen on the data that measured it misleads. The held-out part below is
  never read to choose anything, and power is stated from an out-of-sample effect.

### 8.1 The parts of the read development material, by file and digest

The 52 saved failing partitions and the 100 fresh spans are each split in half BY DOCUMENT
(D-330 item 1). Within each stratum (each fresh source; the partitions as one), the documents are
ordered by SHA-256 of `producer-success:20261108:` plus the document's identity, and each whole
document goes to the side holding fewer rows. A partition's document is its `doc_id` across runs,
so one benchmark document re-run in two loops is one document.
- **Counts (committed in `split.json`).** Partitions: 17 documents, 6 tuning and 11 held out, 0 on
  both sides. Fresh: 70 documents, 35 and 35, 0 on both sides.
- **The split is `tuning/producer_v4/split_heldout.py`,** which refuses a document on both sides.
  The files are under `external/s05/P1/success/`.
- **Superseded.** The first split, by call id at `4ad2d699`, is in `success_superseded_by_call_id/`.
  No attempt read it.

| Part | File | Rows | SHA-256 |
|---|---|---|---|
| no-loss set, every attempt | `dev84.json` | 84 | `3f8a4ae814495c7b4f0ef0dcc97672e624c8244eb0b5017e20e636523399d5cb` |
| tuning, every attempt | `partitions_tune.json` | 26 | `db5b577bc8b2ad22eaf31ef62208f21cb8740b20be0ff1e8ff93a6cd7730cf0b` |
| tuning, every attempt | `fresh_tune.json` | 48 (BillSum 7, GovReport 9, QASPER 8, PubMedQA 24) | `2d5d1558fb7a8a362c6840dcb6006912c9d556de0e3dd1a27a28ba51a8d82e06` |
| descriptive, every attempt (LESSONS L-6) | `case_tune.json`: the 18 PROCESSOR calls of the two worked-case reviews (D-332), the draft resolution's refused partition among them | 18 | `dd5323f4e487c9c099157c3bb056107c7a4f27009e1d0481dbe0429a0230fea1` |
| HELD OUT | `partitions_heldout.json` | 26 | `2409618dd33765e4a3d7472d6df15a28e94bfe4f3ac33cc0bb37a0fc96509134` |
| HELD OUT | `fresh_heldout.json` | 52 (BillSum 10, GovReport 8, QASPER 8, PubMedQA 26) | `721af11d6905b039cec2523d679663c28aeea1085cef09be8fc541746a5d2f48` |
| no-regression set, every attempt | bundle 1, the roles file (`producer_replays.py roles`): six roles, 30 saved prompts each | 180 prompts | `db6e61f3bc91f48eb1bd549b36d2a3667acd34a542ca36a4ca1875d06d20eea5` |

`case_tune` has no gold: it is reported (valid, refused, interventions) and decides nothing. It
is there because LESSONS L-6 names the refused partition as read development evidence for this
lane.

**Attempt 1's training file** is the one to seal. It carries no held-out row:
- recipe `1ee13c02a0fd3ccc1b987f90c4fca9036f093e6131f496d817b542394ebc2200`;
- file `25e964d860e07a7a5df0520c89acd9c1f1e527dbb3c2fe242f4cc058176e7f35`;
- 352 test rows (DEV 84, partitions 26, fresh 48 and case 18, each asked of `tuned` and
  `candidate`), the same 676 training rows, credential scan 0.

`37755823...` and `d6781be4...` are superseded and were never sealed.

**The held-out pass is built** (D-330 item 3), in `benchmark/baselines/producer_score.py` and
`producer_train.heldout_run`:
- `heldout-assemble` writes a test-only file (`producer-heldout-v1`: the paired held-out prompts
  and the candidate's saved adapter, held to its digests; no training).
- It is REFUSED unless `docs/loop/HELDOUT_OPENINGS.md`, AS COMMITTED (`git show`), holds the single
  line for part `producer PROCESSOR candidate` and that attempt. The line must name every held-out
  file's digest and a tuning-record commit, with k and alpha agreeing with 0.05 / 2^k.
- That commit's `docs/loop/producer_attempts/attempt_N_tuning.json` must, as committed, have
  passed and name the attempt.
- `heldout-score` is refused on the same gate and returns pass or fail with counts only, naming
  no item.
- Its proofs, including a neutralised one, are in `tools/producer_training_checks.py` (check 335).
- The held-out part tells the next recipe pass or fail only (LESSONS L-4).

The other rules:
- Training rows and the test never overlap: a training payload inside a test prompt is refused by
  `producer_train.check`.

### 8.2 PROCESSOR's candidate: success

The untrained form is checkpoint 168, the shipped producer. Every test is a one-sided sign test on
the discordant rows: `candidate_only` wins, `tuned_only` losses. Each margin below is the SMALLEST
net count that passes its test (D-330 item 2), computed by `producer_score.smallest_passes`.

| Test | Alpha | Smallest passing (wins, losses) |
|---|---|---|
| tuning part, every attempt | .0125 | (7, 0), (9, 1), (11, 2), (13, 3) |
| held-out part, opening k = 1 | .05 / 2 = .025 | (6, 0), (8, 1), (10, 2), (12, 3) |
| held-out part, opening k = 2 | .0125 | (7, 0), (9, 1), (11, 2), (13, 3) |

Held-out openings follow `HELDOUT_OPENINGS.md`: the k-th is tested at .05 / 2^k, so a false
success over every opening stays at most .05.

A candidate SUCCEEDS, and replaces 168, only when all of these hold:
1. **No loss on DEV-84** (section 4 (a)), on `sdpa_constrained`, the product's path. The rows the
   candidate leaves invalid are exactly 168's (the 9 refusals), so no valid row is lost and no
   refusal is turned into a reply.
2. **No role worse** (section 4 (d)). On bundle 1's six roles, no role on which 168 is better than
   the candidate at one-sided .0125.
3. **Better on the tuning part,** at .0125, by at least one of:
   - (b-T) `partitions_tune` on `sdpa` with no constraint, judged valid by the unchanged validator;
   - (c-T) `fresh_tune` on `sdpa_constrained`, judged equal to the constructed target, item for
     item.
   The record is committed as `docs/loop/producer_attempts/attempt_N_tuning.json`
   (`producer_score.py tuning`).
4. **The gain holds on the held-out part** at the opening's alpha (k = 1: .025), on the same
   measure kind: (b-H) on `partitions_heldout`, or (c-H) on `fresh_heldout`, read once through the
   gated pass. Passing 3 and failing 4 is not success.

Power, in L-4's way: at about 26 to 52 rows a true gain is shown only when it is large in
discordant terms. A failure is reported as "not shown at this size", with the counts.

### 8.3 PROCESSOR's candidate: real progress per attempt

An attempt makes REAL PROGRESS when its tuning record's net count beats the best earlier
attempt's (168 for attempt 1, net 0) by at least 3 on (b-T) or (c-T), and it keeps conditions 1
and 2 (`producer_score.tuning`, `real_progress`). An attempt short of that is told in FOR_SECKIN
with a push: what was tried, why it fell short (from its records), and what the next recipe
changes, citing the lesson. Then the next attempt goes on (D-S72 items 1 and 3). The held-out
part never enters this measure.

### 8.4 The published bar (D-S73)

No comparable published figure exists (8.4a), so the bar is the untrained form, 168, as above.
Every report says so beside its figures. B1 does not apply: B1 is a benchmark baseline, not this
task.

### 8.5 The narrowed roles (INFRA-050)

None is trained in this round. Each first needs labelled development material in its run-time
form, and none exists yet. The first to be trained is claim support (LEGAL_ANALYST), whose rule
follows.
- **Untrained form.** The same question asked of the shipped producer (168) in the choice form, no
  adapter change.
- **Success.**
  - Macro-F1 over GROUNDED, THIN, UNSUPPORTED and OUT_OF_SCOPE on its held-out half beats the
    untrained form by at least 5 points.
  - A paired sign test on the rows the two classify differently, at one-sided .0125.
  - No class's recall falls by more than 10 points.
  - The same direction on its tuning half.
- **Real progress.** At least 2 points of macro-F1 on the tuning half over the best earlier
  attempt.
- **Published bar.** Claim-support datasets are not this setting (one unit against one passage
  Python ranked, four answers). Any published figure it is shown beside is labelled as a
  different setting, never a like-for-like comparison.

Its development set will be built from public validation splits, licence read from each card,
none from a Shimmer benchmark's source families. It is split tune and held out by the same
seeded rule, and both are named here by file and digest in a commit before its first attempt. No
attempt launches until then.

The other narrowed roles (speech act, citation target, editorial verdict, name and role,
inventory element) get their rules in the same form, each before its own first attempt.

### 8.4a The comparable published figure (D-S73): none, and the search record

The task is Shimmer's own contract: the frozen v3 policy's compact reply, one item per owned span,
the CLM ids written in the span, refs Python placed, and gap and uncertainty atoms from a finite
policy, on its own constructed and saved rows with its own scorer. No published system reports on
this contract, its items or its scorer.

The search: the nearest published tasks, from the published record, with venue and year. They
were not re-fetched tonight, under D-S76's usage pace.

| Nearest published task | Source and date | How it differs |
|---|---|---|
| Unanswerable reading comprehension, SQuAD 2.0 | Rajpurkar, Jia and Liang, ACL 2018 | one question per paragraph, a span or "no answer", EM and F1; no gap or uncertainty atoms, no owned spans |
| Hedge and uncertainty cue detection, CoNLL-2010 shared task | Farkas et al., CoNLL 2010 | sentence-level uncertain or certain and cue spans in biomedical and Wikipedia text; no missing-information atoms, no ids or refs |
| Document-level relation extraction, DocRED | Yao et al., ACL 2019 | entity-pair relations from a fixed relation set on Wikipedia; no absence, no uncertainty, no grounding to placed refs |
| Check-worthy claim detection, CLEF CheckThat! | Nakov et al., CLEF 2018 onward | ranks sentences for check-worthiness, MAP; no extraction of claims by id, no gaps |
| Unanswerable questions over papers, QASPER | Dasigi et al., NAACL 2021 | question answering with unanswerable, F1; a training carrier here, not the task |

Each differs in label set, unit and scoring. Showing any of their figures beside ours would be the
like-for-like claim D-S73 item 2 forbids. So the bar is the untrained form, 168, and every report
of this part says so in those words.

### 8.4b How this work moves the system toward the bar (D-S74 item 1)

The programme's bar is the published level on SciTab and ContraDoc (D-S73). PROCESSOR's extraction
decides no label on either: the judge and the paired review do. Its effect is indirect, and the
plan states what is MEASURED (D-330 item 4) rather than a guard it is not.

1. **Measured: k of 26 partitions valid without the constraint**, on each half (8.2, (b)), and the
   share equal to target on the fresh rows.
   - Before DECODING-B, 52 of 283 producer partitions were refused in L7 to L11, and each refusal
     made its document semantically incomplete, so it was not scored as a review. The constraint
     fixed all 52 in R1.
   - This measurement says whether the candidate holds the contract without the constraint. It
     does not by itself protect any future run.
2. **Measured: bundle 1** (`db6e61f3...`, 180 saved prompts of six roles) measures whether 168's
   adapter, loaded by every producer role in final mode, changes the contract validity of those
   six roles against the base. The result is either a fix to the system the benchmark runs
   through, or a recorded fact for the technical report (D-S74 item 2).
3. **Would remove, once INFRA-050 lands and is measured,** two measured exclusion causes from
   benchmark runs:
   - the over-context calls on FinDVer (SPEECH_ACT_TAGGER 35,340 and LEGAL_ANALYST 36,413 tokens
     against 32,768);
   - the out-of-memory stop of INC-015.
   Nothing of this is in the product yet: every narrowed form ships `reply`.
4. **Justified, though it does not move the bar directly (D-S74 item 1).** D-S57 item 3 asks that
   every model be trained in its run-time form, and the attempt costs about 12 USD. Beaten or not,
   it is a measured ablation for the technical report, against the untrained form, on a held-out
   half no attempt was tuned on.

### 8.6 Forecast for attempt 1, revised for the 352-row test

- **Rows:** 352 test rows on two paths, about 704 generations at about 15 s (estimated from R1),
  plus 360 roles rows.
- **Time:** about 36 min of training, about 176 min of test and about 150 min of roles.
- **Cost:** with setup 20, upload 64 and pack 15, about 461 minutes: 9.91 USD, x1.3 = 12.88,
  cap 19.32. Without the upload: 397 minutes, 8.54, 11.10, cap 16.65.
- **The held-out read:** only after a committed opening, a later short session of 78 prompts x 2
  checkpoints x 2 paths, about 80 minutes with setup (estimated).
