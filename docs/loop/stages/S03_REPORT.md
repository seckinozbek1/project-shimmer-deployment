# S3 report: the input and output formats, the generators, the development suite and the long-range corpus

Stage S3 of the autonomous loop of 27 October 2026, on branch `loop/s03`, created from `loop-s01-v1` (`cef0294`); tip `5ac15f3`. No pipeline run and no Lambda spend. Plain English; `<USER_HOME>` stands for the user's home folder. The stage was carried by two lead sessions: the first, until 12:45 +03:00, wrote the plan, the input-format draft and its first two settlements and merged the generators lane (`16199b9`, 11:41); the second, after the restart for push rights (Annex D, D-S5 item 6), merged S2 in and ran the checker rounds. The first-parent history from `cef0294` to `5ac15f3` is twelve commits; 72 commits in all, S2's included through the loop-branch merge.

## What was done

### S3a, the published formats (lead only)

- **Item 1, `docs/INPUT_FORMAT.md`** (`input-format-v1-draft`, first at `5bf6fa7`, D-018). Thirteen sections: what a test bundle is (the sealed test archive and the local working folder, D-041), documents and units, conventions, machine directives, the rule for applying directives, the manifest and the earlier version, the reference corpus, per-test settings, the answer key (single-version, negotiation-style and multi-round forms, with `expected_refusals` and typed reasons), the clean twin, the four perturbation probes, how a multi-round case is declared (written after the S2 merge, from S2b's live case manifest), and a glossary. Every term is defined at first use; every example is invented. Section 8 says no per-test settings file is read (open item 14).
- **Item 2, the one rule for directives** (section 5). Seven numbered points: a completeness rule declares `[requires: ...]` and `[scope: ...]` from its own text; every other rule declares nothing and pairs by the labels it names; never a scope without requires; every rule names a document label or declares a scope; every unit but the preamble is covered; scope values sit in label lines; no `[unless: ...]`.
- **Item 3, draft now, freeze later.** Every draft change is hashed into `docs/loop/VERSIONS.md` (history below). The freeze as `input-format-v1` is S8a's.
- **Item 4, the code-blind check.** Three code-blind readings (at `5bf6fa7`'s draft, at `0b25902` and at `bb88fc2`), plus the generators lane's 13 questions; every item settled from the code and every BLOCKING item closed (tables below).
- **Item 5, `docs/OUTPUT_FORMAT.md`** (`output-format-v1-draft`, first at `5fca716`, D-041). What a run folder contains and what each file means, for the scorer: folder names, completion and exit codes, the bus, the Finding record and change records, the deliverables and amendments, the typed refusal kinds (section 7.1), the audit files, model replies, multi-round outputs, the cloud session folder, and four open points (section 13). Open points 1 to 3 became open items 23 to 25; point 4 (multi-round scoring) sits with open items 17 and 26.

### S3b, the synthetic generators (`lane/s03-generators`, then four fix lanes)

- **`benchmark/generators/`**: seeded, standard library only, never importing Shimmer. Six families: (1) result sheets against reference ranges, (2) declarations with arithmetic, (3) financial statements, (4) contract terms across two or three versions, (5) regulation-style provisions, with a long-range layout, (6) neighbour-dependent stock counts. Domain words live in generator templates under `benchmark/` only.
- **Every test** is six bundles (the test, its clean twin and the four probes), at least 10 planted flaws of at least three kinds (f1 14 of 6, f2 18 of 8, f3 11 of 5, f4 10 of 6, f5 11 of 6, the long-range layout 11 of 4, f6 13 of 6), each with a typed reason, at least one clean distractor, and probe 3's later-only term carrying a keyed flaw.
- **Keys state ground truth, never Shimmer's output (D-042).** Flaws Python does not compute are keyed all the same: unit mismatches, rate and ratio errors, cross-row copies, neighbour-only carries, long-range windows and fees. Each family declares how to find them again (`ground_truth.py`), and each keyed rule's text is checked to still state what it keys.
- **Self-validation** runs before anything is written (a failing test writes nothing) and again in the gate check: the figure audit, the ground-truth scanners, the reference-text readings (D-051), the twin, the probes, the version facts and rename probes, the case manifest restated against the controller's rules, and the long-range distances and baselines.
- **Item 9, file-name traps.** No source file name matches `**/*key*`, `**/*config*.py`, `**/*secret*` or `**/*credential*` (asserted by the gate check); `git check-ignore` evidence below.
- **Item 10, gate check 281** (`scripts/generator_checks.py`, registered in `0b25902`): at the S3 tip 22 test cases pass; 14 of 14 neutralisations caught and restored; each validator message the round-3 adversarial check found never firing is produced by its own mutation; it skips when `benchmark/generators/` is absent (the container image). A source-level proof restored the old count-procedure sentence in `family_ledger.py`: generation refused to write and the check errored; restored, 22 cases pass (private proof records).

### S3c, the development suite

`benchmark/dev_suite/SEEDS.json` (committed): 14 tests, two per family and four for family 4 (two with two rounds, two with three). Generated into `benchmark/dev_suite/generated/`, ignored by git and by the container build. The README says the suite is exposed by construction and used only for development and regression.

### S3d, the long-range corpus

`benchmark/long_range/SEEDS.json` (committed): three family 5 tests in the long-range layout. Each planted flaw is decided by a figure stated only in its related unit, of the use's own track, at least twelve units away; the key names `related_unit` and the true `distance`. Generated into `benchmark/long_range/generated/`, ignored the same way.

## Generated counts (at the S3 tip)

Generated from the committed seeds at `2a26632` (the generator, format and seed files are byte-identical to `5ac15f3`); both listings record the input-format draft `47904fae...`. `generate.py check`: 14 of 14 and 3 of 3 tests valid.

| Suite | Tests | Bundles | Files written | Planted flaws (base bundles) |
|---|---|---|---|---|
| Development suite | 14 | 84 | 466 (plus `suite_listing.json`) | 194 |
| Long-range corpus | 3 | 18 | 93 (plus `suite_listing.json`) | 33 |

Every test has all four probes (14 each in the suite, 3 each in the corpus).

**Development suite, planted flaws per family and kind (base bundles):**

| Family | Tests | Kinds and counts | Total | Clean entries |
|---|---|---|---|---|
| f1 result sheet | 2 | `band_above` 6, `band_below` 4, `total_mismatch` 6, `blank_cell` 4, `missing_required_field` 4, `unit_mismatch` 4 | 28 | 6 |
| f2 declaration | 2 | `product_mismatch` 6, `total_mismatch` 6, `band_above` 4, `band_below` 4, `missing_required_field` 4, `rate_mismatch` 4, `ratio_mismatch` 4, `copy_mismatch` 4 | 36 | 6 |
| f3 statement | 2 | `current_total_mismatch` 6, `prior_total_mismatch` 4, `change_above` 4, `change_below` 4, `missing_required_field` 4 | 22 | 4 |
| f4 terms (band irregularities) | 4 | `breach_moved_away` 12, `breach_unchanged` 8, `breach_moved_toward` 8, `breach_new_term` 4, `breach_renamed_moved` 4, `breach_reformatted` 4 | 40 | 4 |
| f5 provisions | 2 | `notice_window_exceeded` 6, `answer_window_exceeded` 4, `fee_above_band` 4, `fee_below_band` 2, `missing_appeal_body` 4, `missing_definition_source` 2 | 22 | 6 |
| f6 stock count | 2 | `carry_in` 6, `carry_out` 6, `carry_mismatch` 4, `shrinkage_above` 4, `shrinkage_below` 2, `missing_counter` 4 | 26 | 11 |

Family 4 also carries, per test: eight rename-probe rows (32 in all, four of each kind); three `expected_refusals` (12 in all: `possible_rename` 4, `possible_successor` 4, `null` 4, the last for renames moved to another section); 14 `prior_records`; and a multi-round key with 17 planted entries for two rounds and 24 for three. Moved renames move by 2.09 to 40.0 percent (all inside the 2.05 to 45 percent window).

**Long-range corpus, per kind:** `notice_window_far` 12, `answer_window_far` 9, `fee_above_band_far` 9, `fee_below_band_far` 3 (33); 15 clean entries. Over every bundle of the committed seeds and the gate's fixed seed, the track-and-term baseline scores 0.545 to 0.818; first 4 and first k 0 to 0.273; nearest label 0 to 0.364; first label 0.182 to 0.455 (all below 1).

## Agreement with Shimmer (a measurement, never a gate)

Measured for this report with `generator_checks.report_agreement` on the 14 development tests and the 3 long-range tests (base bundles), run on an exported copy of `5ac15f3` outside the repository. The path is Shimmer's Python review of one document (`multi_round_rounds.review_document`) and, for the rename probes, `paired_review.absent_checks` on the two versions. That path computes no reference-table band, no date window and no change record, so those kinds read "not confirmed" by the path's scope, not because a full paired run would miss them.

| Family | Confirmed | Not confirmed, and why |
|---|---|---|
| f1 | 14 of 28 (`blank_cell` 4, `missing_required_field` 4, `total_mismatch` 6) | reference-table bands (`band_above` 6, `band_below` 4: not on this path); `unit_mismatch` 4 (a relation Python never writes) |
| f2 | 16 of 36 (`product_mismatch` 6, `total_mismatch` 6, `missing_required_field` 4) | bands 8 (not on this path); `rate_mismatch` 4, `ratio_mismatch` 4, `copy_mismatch` 4 (relations Python never writes) |
| f3 | 22 of 22 | none |
| f4 band irregularities | 40 of 40 | none |
| f5 | 6 of 22 (`missing_appeal_body` 4, `missing_definition_source` 2) | date windows 10 and fee bands 6 (not on this path) |
| f5 long-range | 0 of 33 | every kind is a date window or a fee band stated only in a distant unit |
| f6 | 22 of 26 | `carry_mismatch` 4 (a relation between two units; Python computes none) |

**Rename probes (family 4, four tests):**

| Probe | Ground truth | Shimmer | Reading |
|---|---|---|---|
| renamed, value unchanged | not withdrawn | refused as `possible_rename`, 4 of 4 | agrees |
| renamed, value moved (same section) | not withdrawn | refused as `possible_successor`, 4 of 4 | agrees |
| renamed and moved to another section | not withdrawn | written as `absent_since_prior`, 4 of 4 | **false withdrawal** |
| withdrawn | withdrawn | `absent_since_prior`, 4 of 4 | agrees |
| withdrawn beside an unrelated new term in the same measure | withdrawn | refused as `possible_successor`, 4 of 4 | **missed withdrawal** |

The two misses are the counter-cases D-042 required; a suite fitted to Shimmer would have hidden them. They are S5 development measurements of the S2b rename rule, not S3 defects (D-047, P16). The gate's fixed seeds give the same pattern. The round-1 lane's measurement on the development suite gave the same counts, except that family 2's ratio errors were planted only from round 2.

## The product change

- **Typed `reason_kind`** (D-042 decision 10, lane commit `1b7cc06`, merged `107bbe7`). Every refusal of a change record carries a `reason_kind` from `paired_review.PRIOR_REFUSAL_KINDS` beside its human sentence: `possible_rename`, `possible_successor`, `possible_successor_no_unit`, `tie`, `reverse_tie`, `no_citation`, `unit_mismatch`, `disagreeing_bands`, `no_key_column`, `value_column_count`, `no_rule`, `orphan`. It is written where each refusal is made (`paired_review.absent_checks`, `reference_tables.prior_values_for_scalars`, `pipeline._prior_comparison`) and kept by `pipeline._prior_refusals_for` in `review_data.json`'s `prior_refusals`. A scorer reads the kind, never the sentence (OUTPUT_FORMAT 7.1).
- **Gate check 284** (`scripts/prior_refusal_checks.py`): 11 fixtures and the pipeline path; neutralised two ways (the `review_data.json` copy drops the kind; `absent_checks` writes none), each caught and restored. **Why 284:** `loop/s04` already registers checks 282 and 283 and its documents cite them; no gate logic depends on a number, only on the list (searched). Renumbering S4's checks at its merge was rejected; S3 skips to 284 (D-047, P13). At the S3 tip the gate's `CHECKS` list has 283 entries (281 at the S2 close, plus 281 and 284).
- **Pinned-baseline amendment (IV.7).** One S3 entry in each of `benchmark/fixtures/topology_reference_contract.json` and `benchmark/fixtures/multi_round_baseline_contract.json`, reason "Operator-directed, 2026-10-27, loop stage S03: typed reason_kind on every refused change record (D-042 decision 10)", pointing at this report: `_prior_comparison` from `e79d78b2...` to `4fdf5134...`, and `_prior_refusals_for` from `d00896ef...` to `53ca8771...`. The change touches runtime files a sealed bundle pins, so any earlier seal refuses; none was sealed after S2. The scorer change it allows (reading `expected_refusals`) is open item 17.

## The loop-branch merge (IV.1)

`990ed88` (15:28 +03:00) merged the loop branch at `b63dbe2`, which holds the S2 tag `loop-s02-v1` (`3b802a1`) and S2's close records, into `loop/s03` in a commit of its own. The one conflict, `docs/fix/OPEN_ITEMS.md`, held two different items numbered 20; both were kept and S3's became item 22 (D-041). From then on the checkers diffed against `git merge-base loop/2026-10-27 loop/s03` (`b63dbe2`). The section-12 multi-round text, family 4's case manifest (`fb82aed`, merged `0b25902`) and `docs/OUTPUT_FORMAT.md` were written only after this merge. No fallback reset happened, so no second merge was needed. The loop branch has since gained eight record commits (D-042 to D-051 on the main checkout's copy, S4's decisions among them; D-041 lives on `loop/s03`'s copy); they touch only `docs/loop/DECISIONS.md` and come in at the stage merge.

## Ignore evidence (items 9, 11, 12)

`.gitignore` lines 200 and 201 and `.dockerignore` lines 25 and 26 ignore `/benchmark/dev_suite/generated/` and `/benchmark/long_range/generated/` (written by the generators lane at the lead's instruction, `381c775`; identical at `5ac15f3`).

- `git check-ignore -v`, run in the worktree that holds the generated suites (`2a26632`, same ignore files as the tip): a development-suite `answer_key.json`, a development-suite document, the suite listing, a long-range `answer_key.json` and a long-range document each match `.gitignore:200` or `.gitignore:201`.
- `git check-ignore -v --no-index` over all 24 tracked S3 files at `5ac15f3` (the 16 files of `benchmark/generators/`, both `SEEDS.json` and both READMEs of the suites, `scripts/generator_checks.py`, `scripts/prior_refusal_checks.py`, both format documents): no output, exit 1. None is ignored.

## Draft-hash history (`docs/loop/VERSIONS.md`)

| When (+03:00) | Draft | SHA-256 (first 8) | Why | Decision |
|---|---|---|---|---|
| 09:46 | input | `1875bf8e` | first draft | D-018 |
| 10:16 | input | `991c25f6` | 81 code-blind items settled | D-020 |
| 11:34 | input | `c2723037` | the generators' 13 questions settled | D-025 |
| 15:46 | input | `3f4a5077` | section 1 archive and working folder; section 12 | D-041 |
| 15:46 | output | `dcce00dd` | first draft | D-041 |
| 15:56 | input | `58bb6f4c` | section 6, the possible-successor refusal | D-041 |
| 17:00 | input | `451e5c9b` | round 1: multi-round keys, expected refusals, text | D-047 |
| 17:00 | output | `b0f293be` | round 1: refusal-kind table, review-mode inference | D-047 |
| 17:51 | input | `a1837a9c` | round 2 | D-049 |
| 17:51 | output | `895237fe` | round 2 | D-049 |
| 18:34 | input | `e20eebf0` | round 3 | D-050 |
| 18:34 | output | `bdd31b28` | round 3 | D-050 |
| 18:56 | input | `47904fae` | tie-break | D-051 |
| 18:56 | output | `2e65a790` | tie-break | D-051 |

The tip's files hash to the last two rows. The suites were regenerated and re-checked after each round's draft (`451e5c9b`, `a1837a9c`, `e20eebf0`, `47904fae`; private proof records). Between `3f4a5077`/`58bb6f4c` and round 1 they were not (round-1 completeness, item 4); the round-1 lane regenerated them. The adapter checks (282, 283) live on `loop/s04` and are re-run on the current draft once both stages are merged (S3a item 3).

## Code-blind check history (S3a item 4)

### D-020: the first reading, settled from the code (commit `d4398ad`)

A fresh `Plan` checker, given only `docs/INPUT_FORMAT.md` at `1875bf8e`, wrote a small test and listed 81 items: 52 guesses (10 BLOCKING) plus one reference (G53), 5 contradicting examples, 8 rules that could not be followed and 15 terms used before definition. A subagent settled each from the code by probing the pure functions on invented strings (no pipeline, gate or model); the lead reviewed the text. Sections are those of the draft at `d4398ad`.

| Id | Severity | Point | Closed in |
|---|---|---|---|
| G1 | SERIOUS | neutral naming forbade spaces in headings and labels | 1 (file and folder names only), 2 |
| G2 | MINOR | ".md only" against a JSON manifest and key | 1, file types |
| G3 | SERIOUS | byte-order mark and line endings | 1, encoding (open item 16, defect 3) |
| G4 | MINOR | `_` files in `conventions/` | 1, underscores |
| G5 | SERIOUS | slug edge cases (trailing hyphen, the 40-character cut) | 2, slug |
| G6 | BLOCKING | open list of small function words | 2, the full stop-word list printed |
| G7 | SERIOUS | is the rule text normalised for pairing | 4 |
| G8 | SERIOUS | decimal comma against thousands groups | 2, reading a number |
| G9 | BLOCKING | measure tokens: case and plurals | 2, when measures agree (case kept, no plural folding) |
| G10 | MINOR | measure algebra (`per`) | 2 |
| G11 | SERIOUS | dates read as figures | 2, 6, 7 (open item 16, defect 2) |
| G12 | SERIOUS | identifiers with digits | 2: identifiers carry letters only (defect 2) |
| G13 | MINOR | point decimals | 2 |
| G14 | SERIOUS | tolerance of figure comparisons | 6, 7, 9 |
| G15 | MINOR | heading level of a rule heading | 3 |
| G16 | SERIOUS | form of the operator's rule id | 3 |
| G17 | MINOR | do heading words count as rule text | 3 |
| G18 | SERIOUS | category tags outside the table | 3 |
| G19 | BLOCKING | a scoped rule without requires | 4, 5 rules 2 and 3, the section 3 example |
| G20 | SERIOUS | does "every unit" include the preamble | 5 |
| G21 | BLOCKING | which labels form the label universe | 4 (the target's units only) |
| G22 | MINOR | label matching by word set | 4 |
| G23 | MINOR | where a `[word: ...]` bracket errors | 3 |
| G24 | MINOR | does a table header carry a label | 4 |
| G25 | SERIOUS | which rule a computed finding is attributed to | 9, attribution |
| G26 | MINOR | outer `relation` against `claim.relation` | 9 |
| G27 | BLOCKING | are band bounds inclusive | 7 (a figure equal to a bound is inside) |
| G28 | BLOCKING | ratio findings with no field label | 7, 9 |
| G29 | MINOR | "one figure per measure" | 7, figure audit |
| G30 | BLOCKING | the low side of a table band | 7, the exact condition |
| G31 | MINOR | how short a header measure must be | 7 |
| G32 | MINOR | case in row matching | 7 |
| G33 | MINOR | range separators | 7 |
| G34 | BLOCKING | key form for a single-version test with a prior | 9 |
| G35 | BLOCKING | are change records false positives | 9 (only amendments count) |
| G36 | BLOCKING | negotiation rows per figure or per label | 9 |
| G37 | SERIOUS | which fields get change records; `absent_since_prior` | 6 |
| G38 | SERIOUS | orienting a change toward or away from a band | 6 |
| G39 | SERIOUS | the manifest's `source` and `resolved_at` | 6 |
| G40 | MINOR | the manifest naming itself; the target in grounding | 6 |
| G41 | MINOR | files the manifest does not name | 6, 13 |
| G42 | SERIOUS | unflawed units not listed as clean | 9 |
| G43 | SERIOUS | the twin's clean list, prior name, repairing a missing field | 10 |
| G44 | MINOR | the task field is display only | 9 |
| G45 | MINOR | "must" wording against completeness rules | 5 rule 2 |
| G46 | SERIOUS | the preamble and "no rule applies" | 5 |
| G47 | MINOR | preamble id without a title | 2 |
| G48 | SERIOUS | probe 1 and labels inside directives | 11 |
| G49 | MINOR | per-test settings undefined | 8 (open item 14) |
| G50 | MINOR | where bundles live | 1, 10 (open item 17) |
| G51 | MINOR | case in directive labels | 4 |
| G52 | MINOR | a reference file's title as a passage | 7 |
| G53 | reference | same point as G46 | 5 |
| E1 | SERIOUS | the decimal-comma example | 2 |
| E2 | SERIOUS | examples with spaces against neutral naming | 1 |
| E3 | BLOCKING | the scoped arithmetic example became a judged absence | 3 (only the completeness rule is scoped, with requires) |
| E4 | MINOR | ".md only" against JSON files | 1 |
| E5 | MINOR | lowercase scope label in the example | 4 |
| R1 | SERIOUS | neutral naming against the rule-heading syntax | 1 |
| R2 | MINOR | all files `.md` | 1 |
| R3 | BLOCKING | a label repeated across units cannot be keyed in `prior_records` | 9 (one row per record; give same-label units different figures) |
| R4 | BLOCKING | a firm `below_band` from a table seemed impossible | 7 (exact condition and example) |
| R5 | SERIOUS | the twin keeps labels yet repairs a missing field | 10 |
| R6 | SERIOUS | probe 1: "everywhere" against "leave directives unchanged" | 11 (document files only) |
| R7 | SERIOUS | scope values in table cells | 5 rule 6 |
| R8 | SERIOUS | a band and a column total in one measure | 7 |
| T1 to T15 | terms | sealed test, result, twin, finding, the reviewer terms, operator, Python and model, band, grounding, verdict ok, closest rule and false positive, scorer and recall, the three settings, multi-round case, `unit` in `prior_records` | each defined at first use (sections 1, 3, 5, 6, 7, 8, 9, 10, 12) |

Format choices made while settling (D-020): no scope without requires; every rule names a document label or declares a scope; every number in a value counts as a figure; single-version tests with a prior keep `planted` and `clean`; bundles need not sit in `benchmark/corpora/` (open item 17). Ten product defects were found on the way: open item 16, below.

### D-025: the generators lane's 13 questions (commit `04b7e24`, applied in `8683d63`)

The lane recorded 13 points where the draft was silent and the reading it chose. Settled from the code by probes on invented strings: ten readings stood; readings 9 (what a sentence is for the bound search), 10 (attribution scoring) and 13 (the 2% rename window: 2% of the larger figure, inclusive) changed the lane's audit; 11 (a table cell's measure) was stated more exactly. D-025's own count ("10 right, 2 wrong, 1 right only by luck") disagrees with this on item 10; D-042 records the generators README's account as the accurate one. D-042 later changed what a key may hold for readings 1, 12 and 13 (ground truth, not Shimmer's output).

### Round 1 code-blind reading (on `0b25902`): 2 BLOCKING, 12 MINOR

| Item | Point | How it closed |
|---|---|---|
| 1 BLOCKING | no answer-key format for a multi-round case | INPUT_FORMAT section 9 "Multi-round keys": entries scoped by `round_id` and `document_id`, every round keyed, a reused copy belongs to its own round (`1e6f938`, D-042 decision 10) |
| 2 BLOCKING | the rename probe undefined in multi-round; a refusal readable only as a sentence | rename probes are measured in the ordinary two-version review of the same files (section 12); every refusal carries a typed `reason_kind` (`1b7cc06`, check 284); a key lists expected refusals in `expected_refusals` (`1e6f938`) |
| 3 to 14 MINOR | refusal wording, operator ids in multi-round, override flags, source states, targets manifest, label universe per round, fixture field, review mode, model findings, supersession scope, `unit_id_repaired_to`, `context/` contents | text fixes in `1e6f938` (D-042 decision 11). Item 10 partly: the review mode is not yet written to `audit/run_options.json`; OUTPUT_FORMAT 8.1 says how to infer it (D-047) |

### Round 3 code-blind reading (on `bb88fc2`): 1 BLOCKING, 11 MINOR

| Item | Point | How it closed |
|---|---|---|
| 1 BLOCKING | how the ordinary two-version review of a multi-round bundle is produced and tied to its key | `562fde5`: for a sealed test, a second sealed archive (the same files without `case_manifest.json`), both hashes named in the key's top-level `archives`, and which run each key list is scored from. The tie-break then found the run discriminator wrong (every run creates `deliverables/`); `2a26632` decides by `audit/multi_round.json` and names `seal.json`'s `test_archive_sha256` as where a cloud run records its archive hash |
| 2 to 12 MINOR | placement of `expected_refusals`, required fields per key form, matching a refusal or a matched rename, `null` and `possible_successor_no_unit`, the 2.0408 percent limit, non-band rules in mandates, rule 4 in multi-round, a rename as one issue, multi-round matching details, model findings in negotiation scoring, the two meanings of `unit_mismatch` | text in `562fde5` (INPUT_FORMAT sections 5, 9, 12; OUTPUT_FORMAT 7.1) |

Round 2 ran no code-blind reading; its completeness checker found the new round-1 text unread by one, which round 3 then read.

## Open item 16: the ten defects (closure table)

Found while settling D-020, by probes on invented strings. None is fixed: S3 changed three of these files only to add `reason_kind` (`1b7cc06`), touching none of the ten behaviours (P16). All are open for the S6 sweep; 1, 2 and 3 lead it, and 2 is weighed by the S4 adapters and S5.

| # | Defect | File and function (lines at `0b25902` in OPEN_ITEMS) | Status |
|---|---|---|---|
| 1 | A `date_window` finding's field label joins a Python `set`, so its word order changes between processes; the scorer compares labels as exact text | `scripts/paired_review.py`, `date_pair_for_rule` (336) | open; format: give the first date's label exactly one word (section 7) |
| 2 | Dates and identifiers with digits read as figures with no measure (`2026-03-01` gives 2026, `SR-101` gives -101) and enter products and ratios; probes gave a false `below_band` and a false `product_mismatch` | `scripts/paired_review.py`, `_QUANTITY` (93), `_band_comparisons` (600), `compute_checks` (649) | open; format: identifiers carry letters only, dates only where a window rule needs them (section 2) |
| 3 | A UTF-8 byte-order mark drops content (decoded as `utf-8`, not `utf-8-sig`); a conventions file starting with one yields zero rules | `scripts/text_extract.py` (105, 126, `_extract_plaintext`); `scripts/convention_parser.py`, `_parse_text` (340) | open; format: UTF-8 without a byte-order mark (section 1) |
| 4 | A table header measure with a currency symbol or a non-ASCII letter passes one reader and fails the other, so that table's bands are ignored | `scripts/paired_review.py`, `_header_unit` (496), against `scripts/reference_tables.py`, `resolve_unit` (162) | open; format: letter codes in reference-table measures (section 7) |
| 5 | The negotiation scorer turns a missing field label into the word `none`, so every ratio band breach is a false positive no key can list | `tools/score_corpus.py`, `score_rounds` | open |
| 6 | A label repeated in one unit is read two ways: scope pins take the first value, figures the last | `scripts/pairing_map.py`, `unit_field_values` (scope pins), against `scripts/paired_review.py`, `extract_fields` (figures) | open |
| 7 | Rules dropped as shorter than 16 characters still consume registry ids | `scripts/convention_parser.py`, `_parse_text_lines` (344) | open; format states it (section 3) |
| 8 | Reattribution splits rule text raw instead of using the one tokeniser | `scripts/pipeline.py`, `_reattribute_computed_plan` | open |
| 9 | A paragraph repeated under two headings is attributed to the first | `scripts/paired_review.py`, `prior_index` (1716) | open |
| 10 | `[note:]` and `[2026: x]` are absorbed as subject tags instead of refused | `scripts/convention_parser.py`, `_heading_bracket_tags` (and `_DECLARATION_SHAPED`) | open |

## Remaining weakness (D-051)

The reference-text readings for families 1 and 2 and for the long-range layout only check coverage: every sentence of their reference files is declared and read, but no mutation shows that any of these readers can fail. Family 6's reader has such a proof (the old count-procedure sentence restored is caught). Recorded here, not a confirmed defect.

## Other open items recorded in S3

- **14** No per-test settings are read from a bundle (D-018).
- **17** The scorer reads keys only from `benchmark/corpora/`, and reads neither `expected_refusals`, nor the multi-round key, nor `archives`; it can only count the four relations Python never writes as missed. Needed before S5 scores the suite.
- **22** The pairing map's `band_conditions` reports a firm low side as conditional (audit record only); reproducible with `py -3.12 scripts/generator_checks.py --probe-open-item-22`.
- **23** Nothing hands a sealed run's folder to the scorer. **24** A judged absence can be counted twice, and a refused answer can locate a flaw. **25** An amendment's severity is always `required`. (OUTPUT_FORMAT section 13, points 1 to 3.)
- **26** Family 4's twin repairs only the last round, so it is not a multi-round twin.

## Departures

- **D-048 (PROCESS-DEPARTURE, IV.7).** `381c775`, `0638d8d`, `16199b9`, `990ed88`, `fb82aed`, `0b25902` and `107bbe7` had no full gate run of their own: the lanes ran only their own checks, and the lead's gate waits for 4 GB of free memory (D-013), which the running lanes kept below the floor.
- **D-050 (extension).** The same for `e2a3068`, `e11a08f`, `d67adba`, `bb88fc2`, `7d9ada3`, `562fde5` and `afb77e8`.
- **D-053 (PROCESS-DEPARTURE, IV.7).** Lane commits `8683d63`, `1b7cc06`, `8ef5322`, `1e6f938`, `a9f3bd4` and `2a26632`, the document-only commits `e094a74`, `5bf6fa7`, `d4398ad`, `04b7e24` and `5fca716`, and the S3 close commit (this report, `VERSION`, `CHANGELOG.md`) were not gated on their own. The gate at the tip and on the loop branch after the merge covers every one of these trees.
- Checks the lanes did run: check 281 and its neutralisations at every lane; check 284 and its neutralisations; and, in the round-1 lane, checks 22, 174, 179 to 185, 278 and 279 one by one (all pass; private proof records).

## Gate (IV.7)

Baseline: `docs/loop/GATE_BASELINE.md`; at the S2 close the loop branch gave PASS 250, WARN 1, SKIP 3, FAIL or ERROR 27 (the 31 non-pass checks of the baseline) over 281 checks. S3 adds checks 281 and 284 (283 in all).

| Commit | Main gate | Side gates |
|---|---|---|
| `3b802a1` (`loop-s02-v1`, reference) | PASS 250, WARN 1, SKIP 3, FAIL or ERROR 27 | all six pass |
| S3 commits up to `afb77e8` | not run (D-048, D-050, and the gap above) | lane check runs only |
| `5ac15f3` (S3 tip, worktree, 2026-10-28 08:20 to 08:27 UTC) | PASS 250, WARN 1, SKIP 3, FAIL or ERROR 29 of 283: the main checkout's 31 plus 28 and 31 (`input/` is ignored and absent in a worktree; worktree baseline recorded in `GATE_BASELINE.md`). 281 and 284 pass. No regression | controller gate passes (75 tests); the other five fail only on worktree gaps: check 01 of the three topology-style gates and the localization gate (`input/context`, `input/operational`, `durable/governance` missing), cloud-run checks the two evidence-file cases of the environment 2 baseline, and the final-integration gate 3 errors on files only the main checkout holds. Decided by the main-checkout run at the merge (below) |
| loop-branch merge of `loop/s03` | see the VERSIONS row of `loop-s03-v1` | see the same row |

## Checkers

All checkers ran as fresh `loop-checker` agents, three roles a round (completeness, adversarial, claims and hygiene; round 3 joined completeness and claims), plus the code-blind readings. Reports are in the private checker reports.

- **Plan check 1** (before work): 9 items, all closed in `e094a74`.
- **Round 1** (on `0b25902`): completeness 30 items, 23 covered, 6 gap items (2 SERIOUS, 4 MINOR); adversarial 12 (1 CRITICAL, 4 SERIOUS, 7 MINOR); claims 6 MINOR; code-blind 2 BLOCKING, 12 MINOR. The CRITICAL: family 4's rename probes were built so the S2b rule passed them, and check 281 pinned the key to Shimmer. D-042 turned every key into ground truth (eleven decisions). Closed by `lane/s03-fix1` (`1b7cc06`, `8ef5322`, `1e6f938`), merged `107bbe7` (D-047).
- **Round 2** (on `107bbe7`): completeness 78 items, 63 covered, 9 MINOR gaps; adversarial 0 CRITICAL, 4 SERIOUS, 5 MINOR (wrong ground truth: an unkeyed duty breach, unkeyed carry breaks in a reordered probe, a long-range corpus a positional baseline solved, unit mismatches no rule forbade); claims 6 MINOR. Closed by `lane/s03-fix2` (`e2a3068`, `e11a08f`, `d67adba`), merged `bb88fc2` (D-049).
- **Round 3, the last** (on `bb88fc2`): completeness with claims 80 items, 73 covered, 1 MINOR (the departure list); adversarial 0 CRITICAL, 1 SERIOUS (family 6's clean count after each carry broke CONV-LA as written), 3 MINOR; code-blind 1 BLOCKING, 11 MINOR. Closed by `lane/s03-fix3` (`7d9ada3`, `562fde5`), merged `afb77e8` (D-050); CONV-LA now states the column-sum reading, and an independent plain reading agrees with the key on 1,200 bundles.
- **Tie-break** (IV.4 step 5, on `afb77e8`): 2 SERIOUS confirmed in narrower form (the old carry sentence survived in family 6's procedure reference file; the multi-round scoring tie used `deliverables/`), 1 MINOR (no format named where a cloud run records its archive hash). All three fixed by `lane/s03-fix4` (`a9f3bd4`, `2a26632`), merged `5ac15f3` (D-051). The checker rounds of S3 are closed.

## Count line

S3 specification items: S3a 5, S3b 6 families plus the per-test requirements and the file-name traps, S3c 1, S3d 1, and the exit criteria. Checker items over three rounds and the tie-break: every one closed by a fix or recorded with its reason (D-042, D-047 to D-051). Open items found in S3 and not fixed: 14, 16, 17, 22, 23, 24, 25 and 26, eight in all, each "not now" for P9 reason (c) (outside S3's scope, owned by the S5 scoring work or the S6 sweep), each listed for a GitHub issue at this close. **N named 8, N worked 0 in S3, N not now 8 (reason c).**

## Loop-until-certain (III.2 step 4)

- **Round 1.** What is left: the gate at the tip (done, no regression), the side gates (worktree runs fail only on worktree gaps; the main-checkout run at the merge decides), the close records. Critical: none.
- **Round 2.** Is the format claim right that the tip's files hash to the last two VERSIONS rows? Re-read: the restart checker confirmed the hashes at `5ac15f3` match `47904fae...` and `2e65a790...`. Are the adapter checks on the current draft done? No: they live on `loop/s04` and run after the loop branch, holding S3, is merged into `loop/s04` (S4 close; S3a item 3). That is stated, not hidden.
- **Round 3.** Remaining uncertainty, recorded: the reference readers of families 1, 2 and the long-range layout have no mutation proof (D-051); the worktree side gates cannot show the five non-controller side gates pass, which only the main-checkout run at the merge shows.

## Effort

Opus, medium effort from 28 October 2026 (Annex D, D-S11). Before that, Opus at high effort.

## Still to do at the close

The gate on the loop branch after the merge, with the six side gates in the main checkout; the adapter checks 282 and 283 on the current draft at the S4 close; the tag `loop-s03-v1` and its `VERSIONS.md` row; the push and the issues (D-S5, D-S8).

## Spend

0.00 USD on instances in S3. The storage share of `shimmer-filesystem` accrues to the reserve and is recorded in `BUDGET.md` at the stage boundary.
