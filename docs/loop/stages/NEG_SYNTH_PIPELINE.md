# The synthetic negotiation item pipeline (standing order 102, D-707, D-709)

16 November 2026, lane/neg-synth. Code only: no item was generated, no model called, nothing spent. Method:
NEG_FINAL_ITEMS_METHOD.md section 2 (its sources 1 to 10). Rules: D-671, D-692, D-706, D-707 (synthetic items in
development sets, one validation set and the pilots, **never in the final test**), D-709 (they start now, before
the real count ends), NEG-ADVISOR-A, NEGOTIATION-MEASURE-A, WORDS-A, checks 22 and 174.

## 1. What each part does

| Part | File | Who runs it |
|---|---|---|
| Declared distributions, constraints, screens' thresholds, the split | `config/neg_synth.json` | read by every tool |
| The generator's prompt template | `config/neg_synth_generator.json` | filled by `tools/neg_synth.py` |
| Sampler, brief, assembler, validator, provenance, set marks, final-test guard | `tools/neg_synth.py` | role S |
| Cue-only check | `tools/neg_synth_cue.py` | role V |
| Deduplication (fingerprint, check, within the synthetic sets) | `tools/neg_synth_dedup.py` | the reference holder, then role B |
| The labeller's runner, its prompt (`config/neg_synth_labeller.json`) and model (`labeller` in `config/neg_synth.json`) | `tools/neg_synth_label.py` | role V, on Lambda |
| The synthetic row of the report, the headline real items only | `tools/score_neg_advisor.py` (`report`, `is_headline`) | role N's scoring |
| Proofs, checks 455 to 459 and 472 to 474 | `tools/neg_synth_checks.py` | the gate |

**The card.** One seed gives one card from two random streams. `structure` is what any reader of the item may see:
round k (1 to 4, so a round k+1 exists), the parties and their kinds, the excerpt's articles (2 to 4 bracketed
with 1 to 3 competing wordings each, one closed, one new in about half the items after round 1), the two
indexes (with a dropped article in about half), and the statement slots (party, round, article, wording or
article as a whole). `hidden` decides the key: the persona, every wording's fate in round k+1 (kept, changed,
removed, open; at most one wording of an article kept or changed, each wording resolved with the same share
whatever the article's size; a whole article gone in about 10 percent), the
stance of every statement, the persona's red lines, which statements use the firm wording, and a trade on record
in about 30 percent. `declared_key` is the scorer's own labels (`score_neg_advisor` section 4 rules) from the
card. A hidden draw is retried (at most 200 times, the structure never) until the item has at least one
`conflict` and one `no_conflict` wording, one movable and one settled wording (M10, AM-3) and one red-line
wording (AM-2); a seed with none is counted and never used.

**Record kinds (D-711).** The kind alternates with the seed, so every set's draws hold complete-record and
missing-notes items about half and half (600 seeds: 300 and 300). A missing-notes item keeps one party in the item
with none of its notes on record: its statements are never asked of the generator (the brief says none is on
record), it is never the persona, and its key answer on every article is `not_stated`. Every build records
`record_kind` and `missing_parties`; the scorer refuses a synthetic build without a declared kind, and
`neg_synth.py set-check` refuses a set folder lacking either kind (check 472).

**The brief holds no key.** It is rendered from `brief_view(card)`, which reads `structure` alone, so two hidden
draws of one structure give the same brief byte for byte (check 456). The generator writes every variant of
every slot: a wording and a revision for every competing wording, and four versions of every statement (in
favour, against, firm limit, accepting). Python alone picks which one the item uses: round k shows every wording
in brackets; round k+1 keeps it (kept), uses its revision (changed), keeps it in brackets (open) or leaves it out
(removed); a statement's version follows its hidden stance, the firm version for a red line. The generator never
learns a fate, a stance, a red line, the persona or a trade, and it is never shown a key, a rubric, a Shimmer
prompt, a pilot, development or final item, `benchmark/`, `scripts/` or any role folder.

**The validator** (`validate`), by Python only: every slot present and no other; word bands; no square bracket,
identifier (`S1`, `A3.1`, `POS-`, `PAR-`, `P-`) or option marker in a text; a revision keeping 0.30 to 0.70 of
its wording's 5-grams; no shared 5-gram between two wordings of one article or with its lead-in; four distinct
statement versions; then the build file is assembled, the scorer's own `build_item` runs on it and every field of
its key (fate, conflict, advanced, red line, supported earlier, state, alignment, approach targets,
configuration) must equal the card's declared key. A rejected item is regenerated once from a fresh card, then
dropped and counted. Whether a statement says what its version says is role V's labelling, never a word table.

**Provenance.** `PROVENANCE.jsonl` in the set folder, one row per accepted item: item id, set, `synthetic: true`,
seed, sampler digest (LF bytes of the sampler, its two declarations and the scorer), card, brief, reply and build
SHA-256, generator family and live model id (a bare alias; a dated snapshot or a Qwen or Phi family is refused),
decoding settings, regeneration count, time, validator result. Roles V and B write their own rows (labeller
family and model id, agreement, leakage maxima, cue result) in their folders; role N joins them by item id at
the freeze.

**Never in the final test.** Every build file says `synthetic: true`; a set folder carries `SYNTHETIC_SET.json`
with its declared set; `check_split` refuses any set whose purpose is final or test;
`refuse_synthetic_in_final(<final folder>)` refuses a final-test folder holding any synthetic build or item or a
synthetic mark, and role N runs it before the final test's freeze.

## 2. The split plan

Seeds are `base + offset + i`. Role S draws the base once (`seed-base`, 2^40 to 2^40 + 2^52) into its own folder
and never shows it; the plan below names offsets only, so no one outside role S learns which seed went to which
set. Each set draws `drawn` seeds and keeps the first `target` items, in seed order, that pass the validator, the
deduplication and the labeller; the rest are counted, never used.

| Set | Purpose | Items kept | Seeds drawn | Offset |
|---|---|---|---|---|
| dev_1 | development | 40 | 80 | 0 |
| dev_2 | development | 40 | 80 | 1,000 |
| dev_3 | development | 40 | 80 | 2,000 |
| validation | validation (one set) | 40 | 80 | 10,000 |
| pilot_1 | pilot, read once then development (D-671) | 24 | 48 | 20,000 |
| pilot_2 | pilot, read once then development | 24 | 48 | 21,000 |
| validation_strata | top-up of validation, stratified (two_singles 10, teams 10, one_vs_coalition 10) | 30 | 120 | 11,000 |
| c4val_1 | fix C4's own validation set (D-789), stratified 10 per structure | 40 | 120 | 12,000 |
| c4pilot_1 | fix C4's own pilot (D-789), plain draw, counts check only | 24 | 64 | 22,000 |

**Fix sets (D-789; `split.fix_rule`, `check_fix`, check 644 proof 6).** A set naming `fix` and `fix_decision` is one
fix's own fresh validation or pilot set: its own seed range, never a top-up, not counted as the plan's one
validation set or a pilot, at most one of each purpose per fix, its name of the label pass's set-name form. C4's
order of work: docs/loop/stages/NEG_C4_MEASURE_PREP.md.

**Stratified draw (D-711 items 2 and 3, D-715 item 1, D-732; check 644).** A set declaring `strata` draws each
seed inside one party structure, (seed // 2) modulo its strata in the scorer's order, crossed with the record
kind; the two-party structures fix the parties' kinds, three_or_more draws its number and kinds as before.
`select` keeps the declared count of each structure, first in seed order, never borrowing. `validation_strata`
names `tops_up: validation`: its kept items join the one validation set (role S session 3's draw held 51
three_or_more, 1 two_singles, 1 teams, 0 one_vs_coalition, below the scorer's 5 per structure). The six sets
above draw exactly as before. Report: NEG_STRATIFIED_DRAW_REPORT.md.

208 items kept from 416 seeds in the six plain sets. The pilots match the first pilot's 24 items; the validation set the advisor plan's
40 held-out items. Every figure on synthetic items is reported in its own row, with its n, its answers stated as
from construction (D-706 item 3, Bean et al.): `score_neg_advisor.report` reads the real items alone as the
headline (figures, cells, claims, the bar and the power record) and the synthetic items apart under `synthetic`,
their claims indicators and their bar never the bar; cells also by record kind (check 474).

**Measured on the declared distributions** (600 seeds, the sampler alone, with D-711's record kinds): no seed
refused; 300 complete-record and 300 missing-notes items; fates removed 36 percent, open 33, kept 17, changed 14;
**M10 movable 47 percent, settled 53**; conflict 39, no conflict 40, not stated 21 (flat across one, two and
three wordings: 0.19, 0.21, 0.23); red lines held 371, not held 331, open 310; alignment cells not stated 3,762,
opposed 1,595, aligned 886; every configuration present (everyone 26 percent, one against a group 25, bilateral
20, shifting 19, group against group 11). Fixture replies on 300 seeds all pass the validator.

**Two structural cues removed before any item.** The cue check, run on fixture replies of random words, first
flagged conflict: the share of `not_stated` rose from 0.22 to 0.42 and `kept` fell from 0.26 to 0.14 as an article
went from one to three competing wordings, a cue the bracket-count feature reads with no text at all. Two sampler
rules caused it and were changed: a party that speaks wording by wording now speaks to every wording of the
article; and "at most one wording of an article resolved" is drawn as one winner with probability n times r
(r = 0.33), so every wording is kept or changed with the same share whatever the article's size. After the
change the shares are flat across one, two and three wordings (not stated 0.19, 0.21, 0.23; kept 0.17, 0.18,
0.17), and the check flags nothing on 48 fixture items.

**The cue check's baseline (D-714).** Read literally, the method's rule compares the cue model's macro-F1 with
the majority class's. That baseline gives every class but one an F1 of zero, so on balanced classes a model with
no cue clears it: on a cue-free fixture of four balanced fates the lower bound is 0.12 against 0.10, flagged.
Seckin approved the label-permutation null instead (D-714, 16 November 20:54): `config/neg_synth.json` declares
`baseline: permutation`, and the majority-class figure and flag stay written beside it as information only
(proof 459).

## 3. The order

1. **Role S** (Claude, this account's usage, 0 USD). `seed-base`; per set `draw`; `coverage` (refuses a batch
   below the declared class minimum); each prompt to a tool-less generator call; `assemble` per reply (rejects
   print problem codes only); a rejected seed's next attempt is the set's next unused seed. The session names
   no card path (D-716): the tool finds `<role root>/work/keys/<set>` from `--set` (and one card from
   `--item <id>`), the role root from SHIMMER_ROLE_S_ROOT or the code checkout's parent, as declared in
   `config/neg_synth.json` `card_folder` (check 510).
2. **Reference fingerprint** (the holder of the pilot, development and real items: role N, or the lead for the
   development material it already reads). `neg_synth_dedup.py fingerprint --part pilot=... --part dev=...
   --embed`: hashes and vectors only. Where the laptop cannot hold bge-m3 (19 November 2026,
   SYN_DEDUP_INPUTS_REPORT.md), the embedding rides the replay pass (EMBED-ROUTE-A): `neg_synth_dedup.py export`
   writes the texts the command will embed, `embed_records.py build` the parts, the lead seals and launches them
   unopened, `merge --require-complete` reads the vectors back, and `fingerprint ... --vectors <merged> --records
   <records.jsonl> --sidecar` writes the fingerprint with its vectors in `<stem>.vectors.npy` beside it.
3. **Role B.** `candidates` from role S's set folders, `check` against the fingerprint, `within` across every
   synthetic set; ids to role S only, counts to the lead. On the rented route role B exports its candidates too
   (`export --candidates`) and runs `check` and `within` with `--vectors` and `--records` in place of `--embed`.
4. **Role V** (Lambda, an open-weight Llama, Gemma or OLMo instruct model, D-706 item 1). Labels every kept
   position (article, wording, stance) and red line from the item text alone, never the card or the build
   file: role S gives it `neg_synth.py label-sheets` (the articles, the parties, the persona, and each quote
   with its party and round only; check 456). Role S then runs
   `neg_synth.py label-compare`, which drops an item with any mismatch or missing label and gives the kappa
   (AM-1's `agreement`) to the lead. Role S then runs `neg_synth_cue.py screen` per set (it holds the builds,
   whose labels role V must not see). The runner is `tools/neg_synth_label.py run --sheets ... --out ...
   --record ...`: the labeller is OLMo (Apache-2.0 and ungated, so no token reaches the instance; public training
   data; a family Shimmer does not use; a 7B instruct model fits an A10), its candidates read live and the first
   open one used with its revision recorded; one narrow question per statement, greedy, every reply read once by
   `tools/answer_form.py`; a field still not read leaves the position unlabelled, counted by reason (check 467).
   On Lambda (Seckin 18 November 2026 14:20: role V launches its own job under the guard, the ledger and the
   reaper; the lead sees counts only) the questions ride a sealed B1 replay pass: `neg_synth_label.py build-pass`
   holds each sheets file to role S's SHA-256 and renders every question on the laptop;
   `benchmark/baselines/neg_synth_label_pass.py` (handed the file by `replay_prompts.py`) resolves the labeller
   from the sealed model cache alone, since a loop instance denies the network, and leaves one reply record a
   prompt; `neg_synth_label.py read-pass` reads each set's labels from the fetched evidence (check 520). The launch
   folder template is `external/s05/V_SYNLAB1_template` (outside git). The model comes from the one-off asset build
   `external/s05/ASSET_OLMO2` (ASSET-BUILD-A, D-736, D-739), held on the Lambda file system only. Each label carries
   the labeller's probability at its deciding token (check 522); role V then draws Seckin's 200 blind positions,
   writes them in tens to `_xfer/V_to_supervisor`, reads his answers from `_xfer/supervisor_to_V` and writes counts
   only to the lead (`tools/neg_synth_review.py`, check 523); no label is ever a few-shot example (check 524).
5. **Role N.** `score_neg_advisor.py build` per set folder (the token budget), freeze, `refuse_synthetic_in_final`
   on the final test.
