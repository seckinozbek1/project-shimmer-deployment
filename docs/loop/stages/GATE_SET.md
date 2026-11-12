# The D-S92 gate set

Written 9 November 2026 by `choice-build` on lane/gate-set, before anything is drawn (D-S100, D-374);
revised after the vekil leakage audit of 705c75fa (14 gaps, D-425), Seckin's D-S118 (the largest
set role B can draw, D-429) and his D-S120 (option A, a claim set of about 230 ContraDoc documents and
250 SciTab claims, which replaces D-S118's maximum, D-453). Nothing below has been drawn, counted from a label or read. Development,
exposed, once drawn; never tuned on. The sealed material is role B's alone: this file names rules,
sizes and digests, never an item.

Code: `benchmark/adapters/common/gate_leakage.py` (the shared leakage check, D-S102 item 3, its rules in
`docs/loop/stages/LEAKAGE_PROTOCOL.md`), `benchmark/baselines/gate_set.py` (the exclusion list, the
draw and the class setting), `benchmark/baselines/gate_score.py` (the gate's figures and both bars),
proofs in `scripts/gate_set_checks.py` (run by gate check 325). Power: `docs/loop/stages/gate_set_power/`.
Role B's request: `docs/loop/stages/GATE_SET_ROLE_B_REQUEST.md`.

## 1. Why role B: the development side, re-marked

The rule (the vekil finding of D-372): **an item whose result, or whose near-duplicate group-mate's
result, fed a later recipe, threshold, rule or lesson counts as tuned.** Counted from ids, groups and
folder names only (no key, no label, no text):

| ContraDoc development, 231 documents in 163 groups (D-S63 delivery) | Documents | Mark |
|---|---|---|
| the fresh set (D-S56, 100 documents) and the other members of its groups | 114 | excluded: read once at the fresh read only |
| G1 half A | 30 | tuned (C_BAR thresholds, judge calibration) |
| G1 half B | 30 | tuned: read for T, its figures shaped attempt 2e's recipe (D-326, `TRAIN_JUDGE_DATA.md`) |
| B3 runs outside G1 (L2 to L12b) | 5 | tuned: their failures drove fixes (D-128) |
| never read, in a group with a half A or half B document | 52 | tuned by the group-mate rule |
| clean | **0** | |

SciTab development: 95 claims in 29 tables from 15 papers, every table G1's, so every one is tuned
under the rule. **No clean development item is left on either benchmark.** The gate set therefore
comes from material the loop has never read, through role B (D-S100): ContraDoc groups from the sealed
pool, SciTab from the benchmark's own source held by role B. No synthetic item is used.

## 2. The pools

- **ContraDoc:** role B's sealed side after D-S63, 660 documents in 479 near-duplicate groups (B's
  report, D-S63 delivery). The fresh set is on the development side; the leakage check excludes it again
  by id (rule 4). Under `external/s05/D-S56/` there is the one exception (D-442): the fresh set's ids file, `external/s05/D-S56/contradoc_fresh100_ids.json`, read for its ids only, admitted by its pinned digest (`ec2498fd...`) and only by `gate_set.py exclude-ids --fresh-ids`; nothing else under `external/s05/D-S56/` is read by any gate tool, on either side.
- **SciTab:** role B's holdout pool, 1,129 claims in 184 tables (PREREGISTRATION.md section 5, band A),
  split by paper. The paper's in-context example tables are excluded by table id (rule 4).
  Not-enough-info claims are drawn in their natural share (D-380).

Role B confirms both pools' counts from its own manifests before the check, and records each source
file's SHA-256.

**Preregistration v3's SciTab sealed share is kept (D-440).** v3's SciTab sealed evaluation is an
earlier, specific commitment (D-S18 item 5, D-133), and D-S118's "largest" does not release it. Its size
is the preregistration's, read there, not chosen: **SciTab 30 documents**, a document being one table
(`docs/benchmarks/PREREGISTRATION.md`, version 2, section 2; sha256 `0c1884fb...` at aee36aaa).
`gate_set.hold_back_v3` holds it back from the **whole** holdout pool, before the quick subset and
without consulting the leakage result (so the share does not depend on the loop's parts): every paper
in the order of SHA-256 of `20261109-v3-sealed:` plus the paper id, taken whole until the share holds
30 usable tables or more: a demonstration table (the paper's in-context examples, role B's list, given
with `--demonstration-tables`) is not counted. Its paper ids are listed in the draw's output, ids only,
with the held papers the leakage check flagged (`v3_papers_the_check_flagged`) beside them, for v3 to
read; they stay sealed. Only Seckin may
release it. ContraDoc is not in v3 and keeps no share.

## 3. The draw (seeded, as D-S63; `gate_set.py`)

Run by role B after the leakage check (section 4), on the groups and papers it kept, before any label
is read. The claim set has a **fixed size, set before any count** (D-S120, D-453, option A, replacing
D-S118's maximum). Fewer available is **refused, never filled**: role B reports the counts and stops.
**No threshold, floor, rule or part list here or in the leakage protocol is changed after any count
of any check is seen.** Only Seckin may change one after that, in writing; the loop never does.

- **ContraDoc.** The kept groups sorted by SHA-256 of `20261109-gate-quick:` plus the group key; the
  first 40 are the quick subset. Of the other kept groups, in the order of SHA-256 of `20261109-D-S92:`
  plus the group key, **the first 230** are the claim set (`CONTRADOC_CLAIM_GROUPS`). One document a
  group: the lowest SHA-256 of `20261109-D-S92:` plus its unique id (D-S45's rule, a new salt).
- **SciTab.** First v3's sealed share is held back (section 2). Then the kept papers outside it, in the
  order of SHA-256 of `20261109-gate-quick:` plus the paper id, taken whole until the quick subset holds
  at least 8 tables and 48 claims; then the other kept papers, in the order of SHA-256 of
  `20261109-D-S92:` plus the paper id, taken whole until the claim set holds **at least 352 claims,
  whatever the class setting** (250 / 0.71, the paper's own not-enough-info share), the draw stopping at
  the first paper that reaches it (D-458, which replaces D-454 item 2 and D-457). **The draw never reads
  a label**: no class setting and no not-enough-info id reaches it, and there is no second draw. The
  class setting is declared afterwards on the drawn claim set (D-380, section 7): under 2-class its
  not-enough-info claims leave at the freeze and about 250 are scored, under 3-class all of them; the
  scored count is reported as it falls. The floor is 352 drawn, with no table floor; a pool that cannot
  reach it refuses the draw. ContraDoc likewise: whole groups, one document each, until 230 documents,
  the floor being 230 (D-454 item 1; the 276 floor of D-S118's maximum gives way). The remaining kept
  groups and papers stay sealed.

The draw refuses a leakage result that did not apply the cosine rule, names no exclusion file, was made
on another input, was fingerprinted without every part of section 9 (`gate_set.REQUIRED_PARTS`), or ran
on other fingerprints, another exclusion file, another step 2 record or another assignment than the
digests it is given (`--fingerprints-sha256`, `--exclude-ids-sha256`, `--cosine-step-sha256`; the
assignment hashed from the file it is given).
The two sets are disjoint by construction (D-373), and no group or paper is split.

## 4. Leakage, proved before any read

`LEAKAGE_PROTOCOL.md` holds the four rules and their thresholds, written before any candidate is
checked: exact text (normalised SHA-256 of records of 4 words or more), 8-word runs (`overlap.py`'s
runs, at least 1 shared, digit-only runs not counted), embedding cosine (bge-m3, at least .92, one text
form on both sides, only ever lowered by step 2's rule) and source or group (`exclude_ids.json`). Every
candidate is checked against every part of section 9; a group or paper goes whole when one member hits.
The counts by rule and by part, the files skipped and the digests the check ran on are written into
section 9 after role B returns them.

## 5. Sizes and power (D-S120 option A, D-453; at the first claim read's 97.5 percent level, for the bars as coded)

Bar (a) as coded (`gate_score.compute`): the point difference from B1 at least .10 **and** the low end
of the interval above zero. Bar (b) as coded: the point difference from the cloud reference at least
-.05, its interval shown beside it. Both are Seckin's (D-S92) and unchanged. The first claim read is
at the 97.5 percent level (D-403). The sizes are Seckin's choice (D-S120, option A); this section states
their power, it does not choose them.

**ContraDoc, 230 documents, binary judgment accuracy, paired** (`contradoc_power.py`; one document a
group, so items are independent; normal approximation; d the discordant share):

| At a true difference of | interval alone (low end above 0), d .27 / .30 | bar (a) as coded, d .27 / .30 |
|---|---|---|
| 10 points | .77 / .72 | .50 / .50 |
| 15 points | .99 / .98 | .94 / .92 |

- **Bar (a) as coded is .50 at a true 10-point difference at any size**: the point estimate clears .10
  only about half the time when the truth is exactly .10. This is a property of the bar, not of the size.
- **Bar (b):** as coded (point at least -.05), at a true zero difference and d .25: .94. It passes a
  system truly 5 points below the cloud reference about half the time (.50), so as coded it does not
  show closeness. Read on its interval (low end above -.05): .23 at 97.5 percent, .33 at 95, .45 at 90.

**SciTab, 352 claims drawn (D-458), macro-F1 in the declared setting, cluster
bootstrap over tables** (`scitab_power.py`, simulated in macro-F1: the system's accuracy set so its
expected macro-F1 is 10 points above B1's; a table effect of sd .6 on the probit scale, the arms' errors
correlated at .2, the paper's class mix; 1,000 simulations and 1,000 bootstrap draws; level .975; seed
20261109):

| Claim set | low end above 0 | bar (a) as coded | command |
|---|---|---|---|
| 3-class, 352 drawn and scored (58 tables of about 6.1) | .81 | .49 | `scitab_power.py 3 58 1000 0.2 0.975` |
| 2-class, 352 drawn, about 250 scored (58 tables of about 4.3 scored) | .80 | .52 | `scitab_power.py 2 58 1000 0.2 0.975 4.3` |

With 1,000 simulations each figure's Monte Carlo standard error is at most about .016. The assumptions
are stated, not measured.

**The quick subsets** (ContraDoc 40 documents, standard error near .08 on a paired difference at d .27;
SciTab 8 tables) are direction only.

**What is left sealed.** ContraDoc: the kept groups beyond the quick subset's 40 and the claim set's 230
(about 209 of 479, less the leakage check's exclusions), and the excluded groups. SciTab: v3's 30-table
share (section 2), the kept papers beyond the claim set, and the excluded papers. Preregistration v3 is
resized on what remains (#74).

## 6. The claim set and the quick subset (D-373, D-403, D-422)

- **Quick subset:** steering only. It may be read as often as needed, its figures never enter a claim,
  and every read is logged as a steering line in `docs/loop/HELDOUT_OPENINGS.md` (set, configuration
  digest, time, "steering read, no claim") and in `GATE_SCOREBOARD.md`. `gate_score.figures` on the quick
  subset's digest shows the 95 percent interval and says "steering only".
- **Every gate figure comes from `gate_score.figures`**, which takes the set FILE, refuses one whose
  digest is not a pin, and refuses arms that do not score exactly that file's items, each under its own
  document (so the claim set's rows can never be read as the quick subset), and is bound to it
  (`CLAIM_SET_SHA256` and `QUICK_SET_SHA256`, pinned when section 10 is committed); any other set is
  refused; on the claim set's digest it never reads at the quick subset's 95 percent. `gate_score.compute` is
  the computation alone and labels its output "not a gate read".
- **Claim set: read once** (D-422), with the configuration chosen on the quick subset. The read is an
  opening in `docs/loop/HELDOUT_OPENINGS.md`, committed before the result is computed (D-330), naming
  the attempt, the configuration's digest and its alpha: .05 / 2^k at the k-th read (D-373, D-403), so
  the first read is at the 97.5 percent level; this is how D-S92's 95 percent interval is read once
  more than one read is possible.
- **A later claim read** happens only if a decision on the loop branch says why, carrying the declared
  marker line `**Quick-subset evidence.**` that names the quick-subset read which motivated the change.
  Nothing between claim reads is chosen from claim-set results. `figures` counts k itself, from the
  rows of the loop branch's `HELDOUT_OPENINGS.md` table whose Part column is exactly `gate-claim-set` and
  whose cells write the claim set's digest in full (a 64-hex token; a prefix is not counted), numbered 1,
  2, ... in their k column (the current read's own row committed first). A freeze line, a steering row
  (Part `gate-quick-subset`) and a short-prefix row are not counted; rows out of order refuse the read. It refuses k = 0, refuses k > 1 without such a decision
  (`decision_names_quick_evidence`, read from the loop branch by git), and scales its bootstrap draws so
  each tail holds at least 20 (2,000 at the first read).
- **Calibration** (judge 2f, D-371) is fitted off both sets: its rows are P2A's r1 half A pairs
  (`external/s05/P2A/choice_prompts_r1.json`, pinned `9d5b3e1f...` in `fresh_test.half_a`), all G1
  development items, which rule 4 excludes from the gate by group and paper.

## 7. Scoring, in each paper's metric (D-S99, D-376, D-380)

- **ContraDoc** (Li et al., NAACL 2024, Table 2): binary judgment accuracy, ABSTAIN counted wrong, the
  headline; precision, recall and F1 of the contradictory class beside it. Evidence: **R-acc(pos)**,
  the share of truly contradictory documents whose cited evidence contains the gold evidence (exact
  containment, stricter than the paper's BERTScore above .98), and **EHR over true positives**. B3's
  unit-level evidence figure is labelled "unit-level, not the paper's EHR".
- **SciTab** (Lu et al., EMNLP 2023, Table 4): macro-F1 in the set's **declared** class setting,
  decided once, after the draw and before any read (D-458), by `gate_set.class_setting`: role B counts
  the gold classes of the drawn claim set through the scorer (`tools/score_corpus.py` item_table, counts
  only); **3-class when it holds at least 30 not-enough-info claims and at least 15 percent of its claims**, **otherwise
  2-class**, and then the not-enough-info claims of **both** the claim set and the quick subset leave by
  id, counted. The claim set is drawn at 352 (section 3), so about 250 are scored; the freeze reports
  the scored and drawn counts and sets no floor after removal (D-458). 3-class reads against TARGET_TABLE S1's 0.65 bar; 2-class against Table
  4's 2-class figures (GPT-4 zero-shot 78.22; Vicuna-7B 63.62), labelled "close". The quick subset takes
  the claim set's setting. In code: `scitab/adapter.py` headline (`--class-setting`), `judge_read`,
  `choice_read` and the gate scoring take the declared setting and never read it off the gold present.
- **Every figure** carries its item count and its bootstrap interval (over documents for ContraDoc, over
  tables for SciTab, one paired resample for every arm, `gate_score.figures`), at the read's level; a
  gain is called only when its interval says so. G1 and J1's bar is labelled a refutes-flag test.

## 8. B1 on the same items

The judge's prompts on gate items are built in the shipped form (the claim form with its tools slot,
`choice_judge_prompt.json`), from the gate bundles, not from `fresh_test.half_a`, which keeps pairs only.

Role B builds the B3 and the B1 bundles of every drawn document in one adapter build call, with these
inputs, given here and in the request (G1's, from its `parts.json`): `--max-context 32768
--output-allowance 2048 --token-counter benchmark/dryrun/token_counter.py` (sha256 `95e8c968...`)
`--b1-prompt benchmark/baselines/b1_prompt.json` (sha256 `25a7d40e...`), `--side holdout --development`,
and `--assignment` for ContraDoc. Each document's items file is one file for both arms. The ids file
lists, per document: its opaque id, group or paper, the items file's SHA-256, the B1 prompt's SHA-256
and the bundle manifest's SHA-256; the read refuses an entry whose B3 and B1 digests differ. B1 runs
the comparator groups C_BAR names (`judge_direct`, `judge_reason`, the better taken, a tie to
`judge_reason`, D-241's abstain floor).

## 9. Provenance per part: no gate item in any part's data

Each part is fingerprinted on the lead's side (`gate_leakage.py fingerprint --part name=path;path...`),
its files read by LEAKAGE_PROTOCOL.md's reading rules: JSON, text and the members of .tar.gz, .tar
and .zip archives; other archives refused; other files, key files and model assets skipped and listed;
nothing under `external/s05/D-S56/`, the fresh ids file included. The fingerprint file holds every file's SHA-256 and the skipped
list, so the digests below are checked there. The last two columns are filled from role B's result (D-543): candidates hit
are ContraDoc / SciTab, from `REPORT.json` `step2_leakage` `candidates_by_part` (one candidate can hit several parts; ContraDoc
144 candidates in 111 groups and SciTab 28 in 5 papers were excluded, by rule: ContraDoc exact 47, runs 144, cosine 57, source 47;
SciTab exact 0, runs 1, cosine 1, source 27; cosine threshold 0.86 from step 2's record `cosine_step.json` `73f9b6a1...`, under
the 0.92 ceiling, where the across-group 99.9th percentile is 0.651 and `separates` is true; groups checked 517 ContraDoc and 65
SciTab; short candidate texts, LEAKAGE_PROTOCOL's figure, ContraDoc 0 and SciTab 16). Gate items hit
were counted by the lead with a script on ids only: of the frozen sets' 270 ContraDoc groups and 30 SciTab papers, none is among
the excluded groups, every one is among the kept groups, and no drawn document, table or claim is an excluded id.

| Part (its name in the fingerprints) | Its data | Digests on record | Candidates hit | Gate items hit |
|---|---|---|---|---|
| `judge_mix_2e` (open item 92) | `external/s05/T2E/replay_prompts.json#rows,held_out` | `08b20660...` (11,367 rows, 592 held out) | 2 / 0 | 0 |
| `judge_mix_1` | `external/s05/T/T_TRAIN/replay_prompts.json#rows,held_out` | `eec83759...` | 32 / 0 | 0 |
| `judge` | `external/s05/T/`; `external/s05/T2E/` (calibration_2e to 2e3 included); `external/s05/P2A/` (r1, the 2f calibration rows) | r1 `9d5b3e1f...`; half_b_documents `79330fe5...` | 63 / 1 | 0 |
| `auditor` | `external/s05/AUD/` (the 789 questions, the 12,000-row session, each archive) | questions `9dbd82f2...`; half A `06154dae...`; half B `b5a47e96...` | 6 / 0 | 0 |
| `auditor_tuning` (the shipped Auditor896 and its predecessors) | every `tuning/auditor_*` folder (auditor_external_relation_v1 and v2 among them), `tuning/first_domain_agnostic_v1` (its training_bundle.zip read), `tuning/second_domain_agnostic_v2`, `tuning/second_tuning_eval_runtime_v2`, `tuning/second_tuning_eval_runtime_v2_1` | each file in the fingerprints | 0 / 0 | 0 |
| `producer` | `tuning/producer_v3/`, `tuning/producer_v4/`, `external/s05/P1/` (partitions_tune, partitions_heldout and the superseded copies) | partitions_heldout `ab005115...` | 8 / 0 | 0 |
| `verifier` | `external/s05/VER/` | each bundle's manifest | 11 / 0 | 0 |
| `ontology` | `shimmer-scratch/ontology_pairs/`, the scratch folder beside the checkout (attempts 1 and 2, measure, train; untracked) | each file in the fingerprints | 0 / 0 | 0 |
| `dev_cases` | `benchmark/dev_cases/` | each file in the fingerprints | 0 / 0 | 0 |
| `development` | `external/contradoc/dev/`, `external/contradoc/dev_moved/`, `external/scitab/dev/`, and each folder under `external/s05/` named in `gate_set.PART_PATHS` (matched as path prefixes, never substrings), that is every folder except `D-S56`, `T`, `T2E`, `P2A`, `AUD`, `P1`, `VER` (G1, J1, D-S45, the L, C, R and CASES runs) (SAVINGS_PROOF among them, D-404's run) | each file in the fingerprints | 107 / 1 | 0 |
| (rule 4) | `external/s05/GATE/exclude_ids.json`, from `gate_set.py exclude-ids`: the fresh set by id only, from `external/s05/D-S56/contradoc_fresh100_ids.json` (`ec2498fd...`), the one file under D-S56 any gate tool reads (D-442), its path and digest in the list's `fresh_ids_provenance` | `a0bfa6d8...` | 47 / 27 (rule `source`) | 0 |

The fingerprint refuses to run while any entry of `external/s05/` other than `D-S56` and `GATE`
belongs to no part (`gate_leakage.uncovered`), so a new run folder is never left out.

A gate item hit in any row is removed with its whole group or paper before the set is frozen; the
frozen sets' two digests (the freeze's `claim_set_ids.json` and `quick_set_ids.json`, section 10) are
written here, and judge 2f's pin reads the claim set's (D-375). The claim set's digest enters
`HELDOUT_OPENINGS.md` only in the `gate-claim-set` row of each claim read.

## 10. Frozen

Filled 12 November 2026 from role B's session B_D-S100 (D-543): `_handoff/B_D-S100_DONE.json` names
`REPORT.json` `e7150f0d...`, and the lead re-hashed it and each of its ten report files (all equal). Bound commit
`43cfe625`; preregistration `0c1884fb...`; inputs as the request named (fingerprints `ad64bab9...`, cosine step
`73f9b6a1...`, exclude ids `a0bfa6d8...`; SciTab's exclusion list adds the four tables the paper's prompts print,
`2cf68302...`). Each draw ran once, nothing refused, no threshold, floor, rule or size changed.

| Set | ContraDoc | SciTab |
|---|---|---|
| Claim set | 230 documents in 230 groups | 363 claims, 61 tables, 24 papers (needed 352) |
| Quick subset | 40 documents in 40 groups | 78 claims, 13 tables, 6 papers |

- **SciTab's class setting:** 3-class, from the drawn claim set's gold counts (supports 122, refutes 110,
  not enough info 131; 131 is at least 30 and at least 15 percent), so no claim is left out
  (`scitab_class_setting.json` `951d516a...`).
- **Leakage:** section 9. ContraDoc 707 candidates (the 47 moved documents among them, excluded by rule 4),
  406 groups kept; SciTab 1,129 candidates, 60 papers kept; v3's sealed paper `1812.11321v1` was flagged and is out.
- **Files skipped** by the fingerprint, per part: auditor 795, auditor_tuning 93, dev_cases 10, development
  42,611, judge 1,278, judge_mix_1 0, judge_mix_2e 0, ontology 734, producer 441, verifier 1,647 (key files
  and model assets, unread by design).
- **Builds:** each set as shipped and with its declaration (`compare: passages`, `compare: cells`), no document
  cut; `bundles.json` `9529b93a...`. The sealed manifests lose each drawn ContraDoc group whole (270 drawn, 98
  siblings with them): ContraDoc 660 to 292 documents, SciTab 1,129 to 688 claims.
- **The two set files**, written by `gate_set.py freeze` into `external/s05/GATE/freeze/` with Windows line
  ends, digests of those bytes: `claim_set_ids.json` **`b0a942ad5dd3ba9a544beb4296056d030b73a8e8a18dd0e98e39ecee66d2357e`**,
  `quick_set_ids.json` **`0127b0809d762fcd4d33602e54cb4ef39a9e727442fcccbdf541104e3283a1f1`**. They are pinned as
  `gate_score.CLAIM_SET_SHA256` and `QUICK_SET_SHA256` in this commit. A copy elsewhere travels byte for
  byte; a freeze run again on Linux would write other bytes and is not the set.

At the freeze, `gate_set.py freeze --contradoc-ids ... --scitab-ids ... --class-setting ... --out-dir ...`
writes the claim set and the quick subset as **two separate files**, `claim_set_ids.json` and
`quick_set_ids.json` (ids only, with the scorer's opaque item and document ids). It takes SciTab's
class-setting result with role B's `not_enough_info_ids`: under 2-class those claims leave both files and
a table left with none leaves too, under 3-class the list must be empty, and the files record the
setting. It refuses two sets that share a ContraDoc group or a SciTab paper.
Their SHA-256 are pinned as `gate_score.CLAIM_SET_SHA256` and `QUICK_SET_SHA256` in one commit with this
section; neither is the digest of the draw's ids files, which hold both sets. **Only `gate_score.figures`
output may be recorded as a gate figure**, on the scoreboard, in a decision or in a report.
