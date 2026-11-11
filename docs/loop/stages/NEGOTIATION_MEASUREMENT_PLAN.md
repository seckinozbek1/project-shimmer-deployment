# Negotiation features: the measurement plan (D-S102 item 8)

Written on 9 November 2026 by the `cases` lane, before any measurement of either feature. The first
version (`9ea2c278`, loop commit `3026bda3`) was checked by a vekil agent, `nego-plan-check`, which
found 16 gaps, and the lead ruled on each (D-389). Its recheck found more, ruled in D-395 and in the
lead's six rulings on `f931af7d`. This version applies them all; section 11 maps every gap and ruling
to the place it is closed.

The plan covers:
- positions toward or away (D-S46 item 2, issue #144);
- the round-3 suggested wording (D-S46 item 3, issue #210).

Development, exposed.

**Expected to be indicator-only** (D-430 item 8). At the deciding settings (1,000 simulated sets,
each arm's over-prediction of "cannot be told" modelled; section 2.7), C1's power is 0.07 and 0.04
with 8 headline cases and 0.09 and 0.04 with 12, far below the 0.8 the rule needs. So the measurement
is expected to report every figure as an indicator, with its interval, and no claim. The run at the
freeze decides, and the page says the same.

Nothing here is a gate benchmark. Neither feature has a published benchmark or metric, so D-S99's
"the paper's own metric" cannot apply. Each metric below is written here, before any figure exists,
and is labelled on the scoreboard and the page as "our metric, no published benchmark".

The work runs beside the gate and gives way to it (D-S102 item 1, D-S94 item 4). It takes a rented
machine only when the gate's plan has none waiting, never in the gate's batches, and never before
D-S105's savings are proven (D-387).

## 1. What has been read already, and so cannot be held out

Development material, read by this lane and by the checkers:

- `benchmark/dev_cases/host_agreement_three_rounds/`, `benchmark/dev_cases/draft_resolution_revision/`
  (A/C.2/74/L.34 and its Rev.1, and every version of that resolution) and
  `benchmark/dev_cases/negotiation_three_rounds/`;
- the movement checker's warehouse-lease case, and every quote of its two attack probes
  (`benchmark/fixtures/position_gaps_replay.json`);
- the fixtures of `scripts/position_gaps_checks.py`, `scripts/case_questions_checks.py`,
  `scripts/multi_round_rounds_checks.py` and `benchmark/fixtures/multi_round_fixture.json`;
- the first cases launch's outputs (D-332).

None of these may appear in the held-out set, in whole or in part. Figures already measured on them
(16 of 16 on the host case's movement key) stay development figures, labelled so, and are never
compared with held-out figures.

## 2. The held-out cases

### 2.1 Who writes them (H17)

- **Only role B downloads** (H17). Role B finds, opens and builds the real cases. The builder (the
  lead and every agent it starts) never opens a benchmark or holdout record before the freeze. The
  request is `NEGOTIATION_ROLE_B_REQUEST.md`.
- **Licence.** Each real case's `SOURCE.md` records the source and the licence that allows research
  use, and a case with no such licence is not used.
- **Role B also starts the author agent**, which writes the synthetic cases from the published input
  format only (Part III: "B's independent authorship of synthetic holdouts from the published input
  format only"). Its brief is `NEGOTIATION_AUTHOR_BRIEF.md`, committed before the agent drafts
  anything; any change to it is a new commit before drafting.
- **Where the cases are made.** The author agent writes in role B's own folder, outside the
  repository and never under `external/`. Role B builds the real cases there too, and moves the
  frozen set into place only after the leakage pass and the freeze (D-395 N9).
- **A fresh declarer agent**, started by role B, writes the supported party's position and fallback
  for each open issue of a real case. A real record rarely states them, so they are labelled
  "declared for the test, not the party's own", and the declarer reads the record only.

### 2.2 The three subsets

Twelve cases, three rounds each, two parties each, in three subsets kept apart in every table:

| Subset | Cases | How written | Required shapes |
|---|---|---|---|
| **R, real** | up to 4 | Role B, from public multi-round records the loop has not read, with two parties and at least six issues (the request's rule; licence recorded in `SOURCE.md`) | none: a real record is taken as it is, never edited to add a shape |
| **F, free synthetic** | half of the synthetic cases, rounded up | The author agent, with no list of shapes: three rounds of a negotiation in its field, written as such records are written | none |
| **S, shaped synthetic** | the other half | The author agent, with the quotas of its brief (figures in a shared measure, a position in words, a silent party, two figures in one sentence, different measures written in varied ways) | the brief's quotas |

**One rule for F and S, in this plan and the brief alike** (the lead's ruling on `f931af7d`, which
replaces D-395 N5's "F fixed at 4"). The synthetic cases number 12 less the real cases kept. F and
S share them equally, with an odd one going to F, so 8 give 4 and 4, and 9 give 5 and 4. S's share
of the headline cases is stated beside every headline figure.

**The fields, by a seeded draw** (D-395 N6). Twelve fields are sorted by the SHA-256 of
`20261109-fields:` followed by the field's name. The first F go to F and the next S to S. Role B
draws them and gives the author the two lists. The fields are listed in the brief.

S is drawn from what the system was built to handle, so it is a stress test.

**The headline is synthetic only (D-389):** F and S pooled, with F and S each shown beside it. R is
an indicator, reported apart with its n and no interval: it has at most four cases and is taken as
found.

If role B keeps fewer than 4 real cases, the synthetic cases take the remaining places by the rule
above, and the plan records the shortfall.

### 2.3 Contamination

Public records may be in the training data of B1's base model and of the cloud reference model.
That would favour those arms on R, so the limit is stated beside every R figure. The synthetic cases
are new text.

### 2.4 Declared units

The author, or for R the declarer, declares a `unit` for an issue only when both parties write every
figure on it in one measure, in the words the notes write right after the figure, as an operator
would. This is done before any arm runs.

### 2.5 The keys, written with the cases, before any arm runs

**The movement key** has one row per issue and pair of consecutive rounds.

- **The gap** is the absolute difference between the two parties' figures on the issue in one
  round, after both are put in one measure.
- **`moved_toward`** when the gap is smaller in the later round; **`moved_away`** when it is larger;
  **`unchanged_from_prior`** when the two gaps are equal within 0.5 percent of the larger, or are
  exactly equal as written. A party's own movement does not decide the row; the gap does.
- **Conversion counts.** A careful reader converts between measures the notes give enough to convert
  (3 months against 90 days, a monthly against a yearly figure, a percentage of a stated base against
  an amount). Where they can, the row is a movement.
- **`not_computable`** only where the text does not let a careful reader tell: a party says nothing
  on the issue in either round; a position has no figure and no quantity in words; a note states
  more than one figure on the issue and does not say which is its position; or the measures cannot
  be converted from what the notes say. The labeller writes one line why for every row. The key is
  the reader's judgement, not any rule about how a quote is written.

**The round-3 sheet** gives, for each open issue, the round-3 passages a good suggestion may rest on
and the agreed text it must leave alone.

**Labellers.**
- Labeller 1 is the author for F and S, and a fresh agent for R.
- Labeller 2 is a fresh agent, started by role B, who sees the cases, the declared units and the
  definitions above, never labeller 1's labels or notes.
- **Agreement** (D-389, D-419 gap 3). Cohen's kappa is taken on the movement key, pooled over every
  row of every case, with each case's kappa beside it. The 0.60 floor applies to the pooled figure.
  - **Below the floor:** both labellers see the rows they disagree on (each the other's label, never
    the other's reason) and may revise once. Their revised files are read, and kappa is recorded
    before and after the revision.
  - **Still below the floor:** a fresh labeller 3 labels every row.
  - **At or above the floor, at first or after the revision:** labeller 3 labels only the rows
    labellers 1 and 2 still disagree on.
  - **Either way,** the key is the majority of three, and a row with three different labels is
    dropped and counted.
- Both labellers share the definitions above, which raises kappa. That limit is stated beside it.
- **At the freeze, reported:** each class's share of every row and of the headline rows (F and S),
  and the Macro-F1 of two floors on the headline rows: an arm answering `not_computable` on every row,
  and one answering the majority class on every row.

### 2.6 Leakage proof before any read (D-S100 item 2, D-S102 item 3)

- **The unit compared is a passage** (a paragraph, split at blank lines). A case's score against a
  corpus is the maximum over all passage pairs. A passage under 20 words (a heading, a label line or a
  short clause, which any two records of one kind share) is not compared (D-395 item 10).
- **Near-duplicate:** word 5-gram Jaccard of at least 0.5 on normalised text (case folded,
  whitespace collapsed), or a bge-m3 cosine of at least 0.9. Exact match: normalised passages equal.
  Same source: a case's `SOURCE.md` URLs, or its document ids, equal to a URL written in a corpus
  or a corpus file's stem (D-419 gap 2). All thresholds are fixed here.
- **How each corpus file is read** (D-419 gap 1):
  - Markdown, text and HTML by paragraph;
  - JSON by its strings;
  - JSON Lines line by line, by each line's strings;
  - Word files (.docx) through the pipeline's own `text_extract`, as a run reads them.

  A file of any other kind, or one that cannot be read, is counted as skipped, per corpus and per
  kind, in FREEZE.json.
- **The corpora:**
  - everything in section 1;
  - every file under `tuning/`, `benchmark/dev_cases/`, `benchmark/fixtures/` and
    `benchmark/corpora/` tracked at the frozen commit;
  - the development sets under `external/` that the loop has read (ContraDoc and SciTab development,
    the J1 and judge-training rows);
  - and, for R, the other R cases.

  The list is committed with the freeze.
- **Where it runs:** on the laptop's CPU, with bge-m3 from the local cache and the network off, at
  the laptop's free memory (D-389). This is an embedding pass, not a pipeline run. It is run by role B,
  which is allowed to open the cases.
  - It runs in float32. A batch holds at most 16 passages (`BATCH_SIZE`) and at most 8,192 tokens
    (`TOKEN_BUDGET`), longest first, so long passages never share a batch; a passage over the budget
    is encoded alone, and one over bge-m3's 8,192 tokens is cut there and counted in FREEZE.json
    (`cut_at_max_tokens`). The encoder is handed 512 passages at a time (`ENCODE_CHUNK`), and each
    chunk's vectors go straight into one float32 array per corpus, 4 bytes a dimension, never a
    Python float (D-437 item 2): 29,354 passages hold about 115 MB of vectors. A progress line after
    each chunk gives the passages done of the total, the time running, the rate and the time left at
    that rate (PROGRESS-A).
  - **The device is an argument** (`--device cpu|cuda`, default `cpu`; the lead's ruling under D-399).
    The laptop GPU is used only when a reading taken first shows it idle: at most 1,024 MiB in use and
    10 percent busy. Otherwise it is refused before any model is loaded. The reading before and the
    reading after the model is released (at once, after the pass) are recorded in FREEZE.json. On the
    GPU, nvidia-smi is read again before the first chunk (another process could take the GPU while
    the model loads, after the pre-load check) and after every chunk (D-456): when the other processes hold more than
    1,024 MiB, or the card is more than 10 percent busy beyond this pass's own use, the pass stops on
    the GPU after that chunk, moves the model to the CPU, frees the GPU and goes on there, and every
    reading and the move are recorded (`gpu_readings`, `moved_to_cpu`). An unreadable reading counts as
    taken.
    - **Memory held by others.** Per process from nvidia-smi's compute-process list, only when every
      row is a number and this process's own pid is listed; this process's listed use less torch's
      reserved memory is then its overhead (`overhead_method: per_process`). Otherwise, a listing
      without this pid or [N/A] as Windows' display driver prints (measured on this laptop), it is the
      card's use less this process's own: torch's reserved memory and an overhead measured at the
      first chunk (`overhead_method: first_chunk_window`). **The window's limit:** that overhead takes
      the other processes to hold what the reading before the load showed, so a process that started
      between that reading and the end of the first chunk is counted as this pass's overhead and not
      seen afterwards, up to its size at that moment.
    - **Utilisation beyond this pass's own.** Read after the chunk has finished on the GPU
      (`torch.cuda.synchronize`) and one second more (`UTIL_SETTLE_SECONDS`), while this pass computes
      nothing, so the card's figure is the other processes' use. nvidia-smi averages over its own
      sample period, so a reading can still carry the end of this pass's chunk; the error falls on the
      side of moving to the CPU. Over 10 percent is not idle (D-399, judged so by the lead under
      D-456). **Limit:** one reading a chunk, in that one-second window, so another process's brief
      job that starts and ends between two readings is missed.
    - The 480-minute CPU pass runs on the GPU when it reads idle, one job at a time, after
      causal-probe's digest and choice-build's fingerprints (D-451).
  - **Each corpus is encoded once,** and each case once, not once per case (D-419 gap 12).
  - **The cosine test is one numpy matrix product per corpus** (the vectors are unit length, so the
    cosine is the dot product; D-430 item 2).
  - **The 5-gram test reads each passage's grams once** (D-437 item 3). Every case passage's gram set
    is built once, into one index from a gram to the passages that hold it
    (`freeze_negotiation_set.GramIndex`). Each corpus passage, and each other case's, is then read once
    against it; its Jaccard with a case passage is computed from the grams the two share. The answer
    is the same as comparing every pair, which check 347 proves on fixtures.
  - **Time forecast**, covering encoding, comparison and the 5-gram step. Before encoding, the tool
    counts every passage's tokens with bge-m3's own tokenizer and prints the passages, the encoding
    time at the measured 0.0055 seconds a token (on the GPU too, an upper bound, since its rate is not
    measured), the comparison time at a planning rate of 5e8 multiply-adds a second, and the 5-gram
    time at the measured 0.00003 seconds a passage. FREEZE.json records the forecast, the time taken, and the 5-gram step's own
    time (`jaccard_seconds`). Role B runs it one job at a time while memory is low (the lead, 21:07).
  - **Measured on the real corpus list** (`docs/loop/stages/NEGOTIATION_CORPORA.txt`, section 12):
    the repository's corpora hold 29,354 passages of 20 words or more and 4,936,533 tokens. That is
    tuning 19,080, benchmark/dev_cases 464, benchmark/fixtures 92, benchmark/corpora 162, scripts 7,383
    and tools 2,171. Code passages are long (median 174 tokens in scripts and 225 in tools, against 50
    in the development cases the dry run read), so the forecast is by token, not by passage. At 0.0055
    seconds a token that is about **7.5 hours of CPU encoding**, more for the 122 passages over 2,048
    tokens (measured at 0.0102 seconds a token), before the external development sets role B adds,
    which it counts when it runs the tool. The earlier 4.1 hours, at 0.5 seconds a passage, was wrong:
    it took the dry run's short passages for the corpus. On the GPU when it reads idle (D-399) the pass
    is expected to be far shorter; its rate is measured on the first chunk. The comparison is under a
    minute for 12 cases of about 30 passages each, and the 5-gram step about a second.
  - **`docs/` is not a corpus** (D-437 item 4, a note in the corpus list). No model under test was
    trained, tuned or prompted on it and no run reads it, so a case cannot leak from it into an
    answer. It holds this measurement's own plan, brief and rubric, which name the fixtures by design,
    and `docs/loop/private/`, which no lane reads.
  - **The corpus list fails closed** (D-430 items 4 and 5). A path that does not exist, or holds
    nothing readable, refuses the freeze. So does a file of a kind the tool neither reads nor finds
    accepted by name in the corpus list (`accept-skipped:`, each kind with its reason). Code, logs,
    CSV, TSV and YAML are read as text, since a builder script or a check can hold case-like
    sentences.
  - **A dry run** (`--no-embedding`) writes `FREEZE.dryrun.json`, never `FREEZE.json`, and the scorer
    refuses a freeze that is a dry run or has no embedding test (D-419 gap 10).
  - FREEZE.json records the cached snapshot's path and one SHA-256 over its weight and config files.
  - Measured in a dry run on non-held-out text (section 12): a peak working set of 2,381 MB, on the
    CPU, for 177 passages of the development cases. Load took 62 seconds and encoding 88.5. The run
    used the cached snapshot `BAAI/bge-m3` 5617a9f61b02, SHA-256 6efc3eb4a548... over its weight and
    config files. The encoder refuses any device other than the one asked for.
- **Result:** the counts per corpus and per threshold. A case over any threshold is replaced by role
  B, and the replacement is checked again. A vekil agent audits the draw, the checks and the counts.
- **The freeze:** the set's SHA-256, and every read recorded in `docs/loop/HELDOUT_OPENINGS.md`
  (section 7). Nothing is ever tuned on it.

### 2.7 Size, interval and power

- **The minimums give the n,** and the freeze refuses a case below them (D-419 gap 11): three
  rounds, two parties, at least 6 issues and at least 2 open issues. So there are at least 6 issues x
  2 pairs x 12 cases = 144 movement rows, and at least 2 open issues x 12 = 24 round-3 items, in all. The headline is synthetic only (section 2.2),
  so its n is at least 6 x 2 x 8 = 96 rows and 2 x 8 = 16 items when role B keeps four real cases,
  and up to the full 144 and 24 when it keeps none. More is not required, and the n is restated from
  the frozen counts.
- **The interval:** the BCa cluster bootstrap over cases (D-S102 item 14), seed 20261109, on each
  figure and on each paired difference between arms.
  - **Exact** where the distinct resamples number fewer than 10,000: every distinct resample, weighted
    by its multinomial probability (8 headline cases have 6,435). Otherwise 10,000 seeded draws.
- **The cross-checks,** each at the claim's own alpha (the lead's ruling on `f931af7d`, D-395 N3):
  - **A jackknife over cases of the pooled difference:** the leave-one-case-out pooled differences,
    their jackknife standard error, and a t on cases less one degree of freedom. These are not
    per-case figures.
  - **A cluster permutation test of the paired difference:** the two arms swapped or not within each
    case, exact over every arrangement below 10,000 (256 for 8 cases), else 10,000 seeded draws. The
    smallest p it can give is one over the arrangements: 1/256 for 8 cases.
  - Both are reported beside the BCa.
- **Classes:** Macro-F1 averages over the key's classes only. A label an arm predicts that is not the
  true one, `no_answer` among them, is a miss for the true class (D-395 N1). A resample whose key has
  one class only has no Macro-F1.
- **Undefined figures:** a resample whose figure is undefined (Macro-F1 with one key class, precision
  with no movement said) is left out, and its probability mass is reported. A claim whose own figure
  is undefined is not shown (D-395 N4).
- **One primary claim, C1, and the power that decides it** (D-414, D-419). C1 (Macro-F1, the system
  against B1) is the one claim. It is tested one-sided at the first opening's full alpha,
  0.05 / 2^1 = 0.025. C2 to C5 are indicators, reported with their intervals and tests and never
  claims.
  - **The rule, written now:** C1 is a claim only if its simulated power is 0.8 or more at **every**
    correlation simulated (0.2 and 0.5). One below 0.8 is enough to make it an indicator (D-430
    item 1). Then the measurement runs as indicator-only, stated so on the page and in the report.
  - **Where the power is decided:** at the frozen headline count (F plus S, once role B reports), by
    `tools/negotiation_power.py --freeze FREEZE.json --only C1` with 1,000 or more simulated sets.
  - **The assumptions, each with its source** (D-430 item 9):
    - **Class shares:** the frozen headline's own shares at the freeze. Source: FREEZE.json. The
      settings runs used 0.3 toward, 0.2 away, 0.1 unchanged, 0.4 not computable, a guess.
    - **Agreement with the key:** system 0.70, B1 0.55, cloud reference 0.75. A guess: no arm has been
      measured on held-out negotiation rows.
    - **`no_answer` rates:** system 0, B1 0.05, cloud reference 0.02. The system's 0 is from its
      design, since it writes a row for every issue and pair. B1's and the cloud's are guesses.
    - **Over-prediction of `not_computable` on rows the key labels with a movement:** system 0.30.
      The source is the worked case: without its declared units the system refused all five of its
      computed movement rows (D-322's 11 of 16), and with them none, so 0.30 is a guess between the
      two. B1 0.10 and the cloud reference 0.05 are guesses.
    - **Round-3 good rates:** system 0.50, B1 0.30. A guess: never measured.
    - **Intra-case correlation:** 0.2 and 0.5. A guess, simulated at both.
    - **Shared case effect:** half (`rho` 0.5). A guess.

    Each set is scored by the scorer's own `test_claim`, with every condition of section 7.
  - **The record:** `docs/loop/stages/NEGOTIATION_POWER_C1.json`, committed before the opening. It
    holds the set's SHA-256, the headline case count, the alpha, the number of sets, the assumptions
    and the simulation code's SHA-256 (D-430 item 6).
    - The scorer reads it from the commit, not the working tree, and refuses unless it matches the
      frozen set, its headline count, alpha 0.025 and 1,000 or more sets.
    - Its code digest and assumptions must be those of the committed `tools/negotiation_power.py`.
    - Its own SHA-256 must be the configuration's `power_record_sha256`.
    - It names each claim's status by this rule (`claim_by_plan_rule`: C1 a claim only at 0.8 or more
      at every correlation, every other claim an indicator) and lists the claims below 0.8 at any
      correlation (`below_0_8_at_any_icc`), so the record reads the way the scorer decides (D-437).
      The records committed before D-437 (`NEGOTIATION_POWER_MIN.json`, the `_PRELIM_` and `_SETTINGS_`
      ones) carry the older list `below_0_8_at_every_icc`, which is not the rule; their power figures
      stand as recorded, and none of them decides.
  - **The record of opening 1 governs both openings** (D-430 item 7). Opening 2 reruns the same
    configuration, so the same record and the same C1 status stand; it is never simulated again.

  **The power at the deciding settings, committed now** (D-430 item 8): 1,000 sets per correlation,
  the over-prediction model, C1 alone at 0.025, the code at `71be1936`.

  | Headline cases | Correlation 0.2 | Correlation 0.5 | Record |
  |---|---|---|---|
  | 8 | 0.066 | 0.036 | `docs/loop/stages/NEGOTIATION_POWER_C1_SETTINGS_8.json` |
  | 12 | 0.094 | 0.042 | `docs/loop/stages/NEGOTIATION_POWER_C1_SETTINGS_12.json` |

  Both are far below 0.8, so C1 is expected to be an indicator and the measurement indicator-only.
  The run at the freeze, on the frozen counts and shares, decides.

  **Earlier runs, recorded and not deciding:**
  - At alpha 0.005 with five claims (100 sets per correlation, before the over-prediction model;
    `docs/loop/stages/NEGOTIATION_POWER_MIN.json`), at 8 cases: C1 0.05 and 0.00, C2 0.03 and 0.00,
    the rest 0.00. That led to D-414.
  - C1 alone at 0.025, 100 sets per correlation, before the over-prediction model
    (`NEGOTIATION_POWER_C1_PRELIM_8.json` and `_12.json`): 8 cases 0.22 and 0.10, 12 cases 0.41 and 0.18.
    The over-prediction model lowers these, as it should: a system that refuses movements loses
    Macro-F1.

  The set is not extended after any opening.

## 3. Positions toward or away

### 3.1 The arms and their inputs

The same frozen rows go to every arm, from one source: the case manifest's declared sources.

1. **System.** The shipped path. Each case runs as a multi-round B3 entry in one exposed batch on the
   frozen configuration (section 7 names its commit, model ids, adapter digests and bundle hash).
   - The arm's labels are the `position_gaps` rows in `audit/multi_round.json`.
   - The CASE-QUESTIONS-A movement decision is about one party's own movement. It does not change
     a gap row, and is not scored here. Whether it runs at the frozen commit (a measured
     `case_movement` threshold) is recorded.
   - The gap rows themselves come from Python, with no model.
2. **B1.** The bare local model, as the gate's B1 runs it. One item per row: the issue's id, its
   declared unit where one exists, and the four declared quotes, the same ones the system reads, each
   named by party and round. A party's slot with no declared source reads "(this party states
   nothing on this issue in this round)".
   - One question asks which of four answers holds: the gap between the parties narrowed, widened,
     stayed the same, or cannot be told from these quotes. The prompt, `movement` form, is committed
     in `benchmark/baselines/` before any reply.
3. **Cloud reference.** cloud-console's runner, as in `CLOUD_REFERENCE_PLAN.md`: `claude-opus-4-8`,
   read live, B1's prompts byte for byte, one call per row. It has B1's movement allowance, 16 output
   tokens: one figure for both (D-419 gap 13).
4. **Ablation, descriptive only.** The system with every declared unit removed, which leaves D-319's
   same-sentence path. This setting was chosen after its result on the worked case (11 of 16, D-317,
   D-322) was seen, so it is a description, never a claim. It is computed from the frozen manifests
   with `unit` removed, through `multi_round_phase.computed_records` and `position_gaps.gaps` at the
   frozen commit, as a module call on the laptop (no pipeline run, no model), inside the same opening.

### 3.2 From every outcome to a label

| Arm's outcome | Label |
|---|---|
| `moved_toward`, `moved_away`, `unchanged_from_prior` (the system's row, or B1's and the cloud reference's parsed answer) | the same |
| The system's `not_computed`, with any `why` (`a_position_in_words`, `several_figures`, `quotes_differ_outside_figure`, `not_the_declared_unit`, `a_party_states_nothing`, `more_than_two_parties`, `different_parties`), and B1's and the cloud reference's "cannot be told" | `not_computable` |
| A system row missing for the issue and pair, a failed or stopped entry, a reply that names none of the four answers, an empty or failed call | `no_answer`, a fifth label that is never in the key, so always wrong |

The position records' `figure_left_out` and the round review's `possible_successor` refusals make no
gap row, so they do not enter this table.

### 3.3 The metric

Four co-primary figures, each against the settled key, on the headline rows (F and S), each with
its 95 percent interval:

- **Macro-F1** over the four key labels, with `no_answer` counted as a wrong prediction.
- **Movement precision:** of the rows an arm labels `moved_toward`, `moved_away` or
  `unchanged_from_prior`, the share that are right. One minus this is the confident-wrong rate,
  which D-319 was built to keep down.
- **Movement recall:** of the rows the key labels with a movement, the share the arm labels right.
- **Coverage:** of the rows the key labels with a movement, the share the arm labels with any
  movement, right or wrong.

Beside every figure:
- the two floors (section 2.5), computed on the same rows;
- the count of `no_answer` for every arm, the system's included (D-419 gap 13);
- F and S separately, and S's share of the headline cases;
- R as an indicator;
- the time per row;
- the two tolerances (D-395 item 11). The system calls two gaps equal within a relative 1e-6
  (`paired_review._close`), the key within 0.5 percent of the larger gap. So two gaps that differ by
  less than 0.5 percent but more than 1e-6 are `unchanged_from_prior` in the key and a movement for
  the system. The key holds labels, not gaps, so how many rows this decides is not counted. The
  statement stands beside the figures.

## 4. Round-3 suggested wording

### 4.1 The rubric, generalised before grading

The rubric of 8 November (`benchmark/dev_cases/host_agreement_three_rounds/ROUND3_RUBRIC.md`) was
written for one case. The text for any case is committed before grading as
`docs/loop/stages/NEGOTIATION_ROUND3_RUBRIC.md`, with its difference from the original stated line
by line. The four criteria (Q, P, A, U) and their pass rules are unchanged; only the case's names
become the case's declarations.

### 4.2 The arms and their inputs

The same open issues of the same frozen cases go to every arm, in one question form: the system's own
suggestion question (`case_questions.suggestion_question`, the template and limits of
`config/case_questions.json`). It shows the supported party, its declared position and fallback, the
parties' stated positions on the issue in every round (the manifest's declared sources), and the
numbered passages of the last round. It asks for one JSON reply with the suggested wording, a quote
copied from the last-round passage it rests on, one sentence why, and the passage numbers it cites.
Every arm has the same output allowance, 384 tokens. The arms differ in the passages shown and in the
model:

1. **System.** The same B3 batch: the case-questions step (agent PRACTICE_AUDITOR) for the supported
   party, one narrow question per open issue. **The system sees its own selection** (D-395 item 6):
   the last round's units the issue declares (`text_units`), which is Python's work and part of the
   system, not the whole round. It does not ask a question over `max_prompt_chars` (6,000 characters),
   and such an issue counts as no suggestion.
2. **B1.** The bare local model, the same question over every passage of every last-round document
   (`benchmark/baselines/negotiation_b1.py`, `whole_round_selection`), with no character limit. The
   form is committed before any reply.
3. **Cloud reference.** `claude-opus-4-8`, with B1's prompts byte for byte.

### 4.3 Scoring: Python first, the same on every arm

Python applies the checks of `scripts/case_questions.py` to every arm's output alike, as scoring:

- Q: the quote copied word for word from a round-3 passage;
- A: no agreed unit cited;
- P: where the position and fallback are one figure each in one measure, no figure of that measure
  outside them.

A reply that cannot be parsed into wording and quote fails Q. For the system, the step's own
refusals are the same checks, run on the same text.

**One rule for a quote and the agreed text, for every arm** (D-395 item 8;
`score_negotiation.quote_unit_closed`). A kept suggestion's quote is looked for in the text of each
last-round unit the case declares agreed. Curly quote marks are made straight and every run of
whitespace becomes one space, in both, with case kept. A quote that stands in an agreed unit is
refused as `quote_in_agreed_text`, whichever passages the reply cited.

### 4.4 Scoring: the graders, blind

Two fresh vekil graders score what Python cannot: whether the cited passage is the one the
suggestion rests on (Q), position and fallback in words (P), not taking back what the party accepted
(A), and usefulness (U, 0 to 2).

- **One common display.** Each item shows the wording and the passage it quotes, as plain text, with
  no citation ids, model mark, refusal reason or formatting from any arm. The items are in one
  shuffled order, seed 20261109, with the arms mixed.
- **Refusals are graded apart.** An output Python failed is scored not good and never shown in the
  first pass. In a second pass, after the first sheet is committed, the graders see the refused items
  with Python's reason and say whether each refusal was right.
- **Guessing the arm.** For each item, each grader also guesses its arm. The rate is reported against
  chance (one in three). If it is above the binomial 95 percent bound, the grading is reported as not
  blind, and C5 is an indicator for that reason too (D-395 item 7).
- **Self-preference.** Both graders are Claude agents, and the cloud reference is a Claude model. So
  the system-against-cloud-reference comparison on round 3 is reported as an indicator, never a
  claim (section 7).
- **Agreement and settling.** Agreement on "good" is Cohen's kappa, with the floor and fallback of
  section 2.5 and a fresh third grader.

### 4.5 The metric

- **Primary: the good-suggestion rate,** on the headline cases (F and S). An item is good only
  when Q, P and A all pass, by Python and by the graders. The rate is good items over open issues,
  with its 95 percent interval.
- **Beside it:**
  - mean U over all open issues, an item that is not good scoring 0;
  - mean U over the good ones;
  - each arm's refusal rate (Python's, and no suggestion given);
  - the share of the system's refusals the graders judge right;
  - the guess-the-arm rate;
  - each subset's figures;
  - the time per item.

## 5. Machine, forecast and cost per arm

All rented arms run on `gpu_1x_a10` in us-east-1, the type every comparison so far used, so no
machine factor enters (D-S82, D-S95 item 5). The asset copy is declared, and MATCH is expected while
the frozen model list is unchanged. With MISSING, add the measured 64 minutes of upload to the system
batch (D-332).

The planning prices:
- A10: the live price read in the plan, 1.29 USD an hour on 8 November, times the 1.3 forecast
  factor.
- Cloud reference: the planning price recorded in `CLOUD_REFERENCE_PLAN.md`, 5 USD per million input
  tokens and 25 per million output tokens for `claude-opus-4-8`, until the lead writes the row in
  `cloud_reference_prices.json`.

| Arm | What runs | Forecast minutes | Forecast USD |
|---|---|---|---|
| Positions and round 3, system | One batch of 12 multi-round B3 entries. Setup 15 (with MATCH), 12 x 1.5 for the cases (D-332 measured 1.5 and 0.5), and the suggestion step's model load with up to 36 narrow calls, about 15 | 50 | 1.40 |
| Positions, B1 | 144 short items on the bare model, model load included | 25 | 0.70 |
| Round 3, B1 | up to 36 long items, up to 384 output tokens each, the whole last round as input | 20 | 0.56 |
| B1 setup, shared | Instance setup with MATCH, both B1 forms in one session | 15 | 0.42 |
| Positions, cloud reference | 144 calls, about 500 input tokens each, at most 16 output (B1's allowance) | (calls only) | 0.36 input + 0.06 output = 0.42 at worst |
| Round 3, cloud reference | up to 36 calls, about 6,000 input tokens each (the whole last round), at most 384 output | (calls only) | 1.08 input + 0.35 output = 1.43 at worst |
| Ablation and power simulation | Python on this laptop, no model | about 5 | 0 |
| Leakage pass | bge-m3 on the laptop, role B's: 4.94 million tokens in 29,354 repository passages at the measured 0.0055 s a token on the CPU, plus the external sets (section 2.6); the GPU when it reads idle | about 480 on the CPU, one job at a time | 0 |
| Graders, labellers, declarer and author | Fresh Claude agents (vekil and role B's), Claude usage, not provider dollars | (usage) | 0 USD, counted in the D-S91 usage watch |
| **All arms** | Rented: 110 minutes in two sessions | **110** | **3.08 rented + 1.85 cloud reference = 4.93 at worst** |

The round-3 cloud input grew from the first version's 2,000 tokens because B1 and the cloud
reference get the whole last round (section 4.2).

**Before the "evet" request** (D-S106, D-395 N7), the prompt count and the cost are recomputed from
the frozen counts: the movement rows and the open issues of FREEZE.json, and the built prompts file's
measured lengths at about 4 characters a token. The request names those figures, not the forecast
above, and says if the estimate is above the API balance (D-S106 item 3).

Every forecast is replaced by the measured figure after its run, with the D-S82 factor record. No
arm's run is credited with a gain in another: one factor at a time, or the gain is stated as joint.

## 6. Scoreboard rows (demo-console's schema)

The gate's table in `docs/loop/private/GATE_SCOREBOARD.md` charts every column headed
`<benchmark>: system / B1 / cloud ref` against the D-S92 bars. These two features have no bar, so
they get their own table in the same file, under the heading
`## Negotiation features (D-S102 item 8)`. It has the same column shape, so the page reads it the
same way, and its gap columns read "no bar":

| Time | What changed | Set | Positions toward or away (Macro-F1, 4 labels; our metric): system / B1 / cloud ref | gap | Round-3 wording (good-suggestion rate; rubric Q, P, A): system / B1 / cloud ref | gap | Since last |
|---|---|---|---|---|---|---|---|
| (none yet) | plan written; held-out cases not yet drawn | | | no bar | | no bar | |

Each filled row carries a detail table beside it, per D-S102 item 4:

- the metric and its setting;
- n (rows or items, and cases);
- per arm, each co-primary figure with its 95 percent interval, and the beside-figures of sections
  3.3 and 4.5;
- machine type, price and region;
- run minutes and speed (seconds per row and per item);
- run and cumulative cost;
- the evidence path;
- the opening number and its alpha;
- the D-S82 factor record, written by Python from the run's own records.

The page section (D-S102 item 8) is demo-console's. It reads only these fields. It states, as the plan's
opening does, that the measurement is expected to be indicator-only (D-430 item 8).

## 7. Openings, claims and alpha (D-330, D-395)

**The order of a launch** (D-395 N8): seal the bundles first; then write and commit the opening line
with their hashes; then launch.

**The opening line,** written and committed by the lead before the result is read, in
`docs/loop/HELDOUT_OPENINGS.md`, in the form
`negotiation-heldout opening k=<k> set=<set SHA-256> config=<configuration SHA-256>`. The
configuration record whose SHA-256 it names holds:

- the system's commit, its model ids, its adapter digests, and its sealed bundles'
  `execution_manifest_sha256`;
- B1's checkpoint, its decoding (the frozen evaluation policy of its backend, `decoding_policy.py`,
  named with its protocol file and digest; D-395 item 6), and the prompts file's digest;
- the cloud model id resolved live.

**The scorer refuses.** `tools/score_negotiation.py`, built with its checks before the freeze,
refuses to score unless all of these hold (D-419 gaps 4, 5, 6 and 10):

- the freeze is not a dry run, and it ran with its embedding test;
- the opening line exists and is committed, and k is at most 2;
- C1's power record matches the frozen set (section 2.7);
- the configuration holds every field the checks read (the system's manifests, B1's and the cloud's
  prompts digests, B1's model digests, the cloud model id, the power record's digest), and both B1 and
  the cloud reference are given, B1 with its pass's measurement and the cloud with its model id
  (D-430 item 3);
- every arm's own records match the configuration:
  - each system run's `execution_manifest_sha256` is among the configuration's;
  - B1's and the cloud reference's answers are of the configuration's prompts files;
  - B1's model digests (its pass's `replay_measurement.json`) are the configuration's;
  - the cloud reference's model id is the one resolved live;
- every frozen case has a system run. A failed entry counts as named only by the runs' own records
  (D-437 item 1):
  - each `--system-run` is a run folder, never a file such as a FINAL_STATUS.json;
  - an entry's records are read only at its **entry root,** the folder holding both
    `collection_integrity.json` and `seal.json`, never from under `downloaded/` (what came back from the
    instance; D-456 item 1);
  - a run with no case record (`audit/multi_round.json`) is a failed entry only when its bundle holds
    its case manifest and a FINAL_STATUS.json that says `ORDINARY_FINAL_CLOUD_RUN_FAILED`, whatever
    its pipeline state (a run can reach its end, state `completed`, and fail its assessment, as with
    `semantic_incomplete`), or a controller failure record. A successful run's FINAL_STATUS.json is
    refused;
  - a failed entry is of one of two kinds, read off the entry's own records (D-451 and D-456).
    **Infrastructure,** only for a cause of the runner or the machine, each named in
    `score_negotiation`: one of the controller's own failure records beside FINAL_STATUS.json
    (`controller_failure.json`, `launch_recovery_failure.json`, `collection_failure.json`: the launch,
    ssh, the upload, the collection, a lost instance or its deadline), even with no FINAL_STATUS.json;
    no result from the runner at all (the instance lost before it wrote its result); or a terminal
    error whose recorded identity (`failure_identity`'s `error_type` and `error_module`) is the host
    out of memory, `builtins.MemoryError` (`INFRASTRUCTURE_ERRORS`). A class of the same name from any
    other module is not excused. A CUDA out-of-memory error (`torch.cuda.OutOfMemoryError`,
    `torch.OutOfMemoryError`) is the system's own (the lead's ruling under D-456): the system's batch,
    context and model choices set GPU memory, and PREFILL-E records it as a named failure of the run.
    **The system's own reasons:** everything else, including any other terminal error (a pipeline
    exception), `backend_failure` (a model call that failed inside the pipeline), `semantic_incomplete`,
    `required_contract_failure`, `pipeline_not_completed` and the multi-round reasons. The runner's
    own reasons, when its result names any, decide the kind; a controller record is then listed beside
    them, never in their place (D-456 item 3), since the controller writes its records later, at
    collection;
  - **A limit, outside this lane:** the scorer reads the controller's records by these four names
    (FINAL_STATUS.json and the three failure records). Whether the controller always writes them at
    the entry root, and in a batch for every entry, is the bound controller's code, not this lane's;
    it is sent to judge-product to state or fix. **judge-product's answer (open item 97):** the
    controller does not guarantee them. The three failure records are written only on their own
    failures and only in the session folder, never in an entry's, and FINAL_STATUS.json exists only
    where the analyser ran. So in a batch the controller-record path does not fire today, and an entry
    lost before its collection has no record at its root: the scorer refuses the scoring, and the
    missing entry is a ground for opening 2. What would settle it: an `entry_outcome.json` the
    controller writes at every entry it reached, with a proof;
  - either kind scores `no_answer` on every row of its case. Its rows stay in the frozen key and in
    every figure; the report counts and names them apart by kind (`system_failures`: per kind the
    cases, their causes and their `no_answer` rows). A failure of the system's own never refuses the
    scoring, so the system's failures are never left unscored, and only an infrastructure failure can
    call for opening 2 (`opening_2_may_be_called`);
  - a case with a case record in any run given is never also a failed entry;
  - one run per case: two runs for one case refuse;
- an answers file holds one model group.

Positions and round 3 are scored in the same refused path. Round 3 reads the system's suggestions off
its runs, B1's and the cloud reference's off their answers, the agreed units off the frozen set, and
the settled grading sheets.

**At most two openings** (D-395 item 3).
- Opening 1 is the read.
- Opening 2 is decided from the runs' status records alone (entries failed or stopped for an
  infrastructure reason, a lost instance or a missing entry; never a failure for the system's own
  reasons, D-451), before any score is seen. It reruns the
  whole set, never only the failed entries, on the same configuration, with no change of code, model,
  prompt or key, and its line says so. There is no third opening.
- There is no tuning half, because nothing in either feature is tuned on these cases. D-330's
  precondition is therefore replaced, by the lead's ruling recorded in D-395: "no tuning half; the
  configuration fixed and named before the first opening".

**The claims** (D-414):

| Claim | Feature and figure | Comparison | Status |
|---|---|---|---|
| C1 | Positions, Macro-F1 | system against B1 | the one primary claim, at 0.025 one-sided, if its power at the frozen headline count is 0.8 or more; else an indicator (section 2.7) |
| C2 | Positions, movement precision | system against B1 | indicator (D-414) |
| C3 | Positions, Macro-F1 | system against the cloud reference | indicator (D-414) |
| C4 | Positions, movement precision | system against the cloud reference | indicator (D-414) |
| C5 | Round 3, good-suggestion rate | system against B1 | indicator (D-414; the lead's ruling on `f931af7d` item 4) |

- **The alpha.** C1 is tested one-sided at 0.05 / 2^k at opening k: 0.025 at opening 1, and 0.0125 at
  opening 2. The indicators are tested at the same alpha, so their numbers read the same way, and
  none is called shown.
- **What shows a claim.** All of these must hold:
  - its figure is defined;
  - the BCa lower bound of the paired difference lies above zero;
  - the jackknife lower bound lies above zero;
  - the permutation p is at most the alpha.
- **C2 and C4 carry two more conditions** (D-395 item 1; the lead's ruling on `f931af7d` item 5), now
  as indicators. The
  paired movement recall difference and the paired coverage difference must each be not below zero
  at the same alpha, meaning their BCa upper bounds lie at or above zero. Both are stated beside the
  claim.
- **An indicator** (`score_negotiation.INDICATORS`) is reported with the same numbers and is never
  called shown.
- **The rows of every claim** are the headline rows: F and S pooled.
- **Reported, never claimed:**
  - movement recall and coverage;
  - the round-3 system against the cloud reference (self-preference, section 4.4);
  - the ablation;
  - every subset's figures (R has too few cases for an interval: its figures are given as
    indicators, with n and no interval);
  - every beside-figure.

## 8. What each figure is not

- The cases are development cases written or chosen for this test. They are not a benchmark, and
  never compared with any published figure.
- S is shaped toward what the system was built for.
- R may be in the models' training data.
- All graders are one model family.

## 9. The order, and what waits on what

1. This plan, committed. Then the author brief and the role B request, updated to it and committed
   before any drafting.
2. The scorer (`tools/score_negotiation.py`, with the label mapping of section 3.2, the BCa cluster
   bootstrap, the empty-class rule and the refusal of section 7), the power simulation, the freeze
   tool, the `movement` and `suggestion` B1 forms, and the generalised rubric. Each comes with checks
   (neutralise, fail, restore, pass), on fixtures that are not the held-out cases. No machine.
3. Role B's real cases, the author's synthetic cases, the declarer, labeller 2 (and labeller 3 if
   needed), the leakage pass, the vekil audit, the power simulation on the frozen counts, and the
   freeze. Claude usage and the laptop's CPU only.
4. The system batch and the B1 session sealed on the named configuration; then the opening 1 line,
   with their hashes, committed; then the launch (D-395 N8), only when D-S105 allows and the gate's
   plan has no machine waiting. cloud-console runs
   the cloud reference at the same time. That run uses only Seckin's own key as `load_api_keys`
   resolves it, and it starts only after his "evet" to a FOR_SECKIN entry with a push (D-S106). The
   entry names the run, and the prompt count and the estimated cost recomputed from the frozen counts
   and the built prompts file, as section 5 says. It does not name this plan's forecast (D-419
   gap 14).
5. Python's scoring, then the graders (first pass, then the refusal pass), then the scorer, the
   scoreboard rows and the page.

## 10. Speed

The time per row (positions) and per item (round 3) of each arm is read from its own records and
stands on the scoreboard (section 6).

## 11. The vekil check's 16 gaps, and where each is closed

1. The key copied the system's refusal rule: section 2.5 (conversion counts, `not_computable` only
   where a reader cannot tell, class shares and two floors at the freeze); section 3.3 (Macro-F1,
   movement precision, recall and coverage co-primary, the floors beside every figure).
2. No answer credited as `not_computable`, and unmapped outcomes: section 3.2 (`no_answer`, a fifth
   label, always wrong; the full mapping).
3. D-330 not applied: section 7 (the line before the read, the scorer's refusal, at most two
   openings, five named claims, alpha 0.05 / 2^k / 5; since D-414 one claim, C1, at 0.05 / 2^k).
4. Shapes built for the system: section 2.2 (subsets R, F and S, F with no shape list, reported
   apart); the brief committed before drafting (section 9, step 1).
5. Pooling, too few real cases, invented positions, licence, H17, contamination: section 2.1
   (only role B downloads, the licence line, the declarer), 2.2 (the headline synthetic only, R an
   indicator), 2.3 (contamination), 7 (claims on the headline rows).
6. Arms' inputs and the configuration undefined: sections 3.1 and 4.2 (one source, the silent slot,
   the same round-3 inputs and 384 tokens), section 7 (commit and digests in the line before the
   read), section 3.1 (the movement decision is not scored).
7. Graders could see the arm: section 4.4 (one display, refusals in a second pass, guess-the-arm
   rate, self-preference makes the cloud comparison an indicator).
8. Python checks on the system only: section 4.3.
9. Power, n, interval and empty classes: section 2.7 (simulation, n from the minimums, BCa with a
   cluster t cross-check, the empty-class rule).
10. The dedup unit, corpora and where the embedding runs: section 2.6 (the maximum over passage
   pairs, the committed corpus list, the laptop's CPU at its free memory).
11. Tolerance and the meaning of the gap: section 2.5.
12. No kappa floor or third reader: sections 2.5 and 4.4 (floor 0.60, one revision round, then a
   fresh third labeller).
13. The ablation's history and rerun: section 3.1, item 4.
14. The rubric written for one case: section 4.1.
15. Mean U over good suggestions only: section 4.5.
16. Speed missing: sections 6 and 10.

### The recheck and the lead's rulings on it (D-395, and six on `f931af7d`), and where each is applied

- D-395 1, and the `f931af7d` ruling 5: the precision claims' recall and coverage conditions are in
  section 7 and in `score_negotiation.test_claim`.
- D-395 3: opening 2 is decided from run status alone and reruns the whole set; the precondition is
  cited to D-395 (section 7).
- D-395 4: the author brief now gives the files and the key definitions before the free cases, and
  the example shapes in the shaped section only.
- D-395 5: the real-case rule (two parties, the first two named in the record's own order, at least
  six issues, else rejected with one line) is in the role B request.
- D-395 6: the system sees its own selection (section 4.2), and B1's decoding is in the opening line
  (section 7).
- D-395 7: a guess rate above the bound makes C5 an indicator (section 4.4).
- D-395 8: one rule for a quote in agreed text, for every arm (section 4.3).
- D-395 10: the passage floor is 20 words, and bge-m3's path and digest are recorded (section 2.6).
- D-395 11: both tolerances are stated beside the figures (section 3.3).
- D-395 N1: Macro-F1 is over the key's classes only (section 2.7).
- D-395 N2, and the `f931af7d` ruling 4: the per-claim power simulation and its result are in
  section 2.7. Every claim was an indicator at that alpha; D-414 then made C1 the one claim at 0.025.
- D-395 N3, and the `f931af7d` ruling 3: the jackknife over cases and the permutation test, at the
  claim's alpha (section 2.7).
- D-395 N4: undefined figures are counted, and such a claim is not shown (section 2.7).
- D-395 N5 and N6, and the `f931af7d` ruling 2: F and S in equal shares, with an odd one to F; the
  fields by a seeded draw (section 2.2 and the brief). Ruling 2 replaces N5's "F fixed at 4".
- D-395 N7: the prompt count and the cost are recomputed from the frozen counts before the "evet"
  request (section 5).
- D-395 N8: seal, then the line, then launch (sections 7 and 9).
- D-395 N9: the cases are made in role B's own folder and moved in after the freeze (section 2.1).
- The `f931af7d` ruling 6: the bge-m3 dry run (section 12).

## 12. The bge-m3 dry run (the `f931af7d` ruling 6)

Run on 9 November 2026 on this laptop, on non-held-out text: the 177 passages of 20 words or more in
the Markdown files under `benchmark/dev_cases/`.

- The encoder was `freeze_negotiation_set.bge_m3_encoder`: the repository's own loader, forced to the
  CPU, float32, batches of 16.
- The peak working set was 2,381 MB, with 3,301 MB free before the run.
- Load took 62.2 seconds, and encoding 88.5 seconds (about 0.5 seconds a passage).
- The snapshot was
  `models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181` in the local Hugging Face cache,
  with SHA-256 `6efc3eb4a548a41568077b4d4734cf477b8d949682e1dfe3a219d92f96ff0a69` over its weight and
  config files.

A first attempt without the CPU setting loaded the model on the GPU. The encoder now sets the local
profile, under which `embedding_store` places bge-m3 on the CPU, and refuses any other device.

**On a slice of the real corpus list** (D-437 items 2 and 3; 9 November, the CPU, nothing held out):

- **Reading** the six corpora took 18.3 seconds and 66 MB.
- **The 5-gram step:** an index of the 464 development-case passages (built in 0.02 seconds) read 5,871
  corpus passages, every fifth, in 0.17 seconds: 0.00003 seconds a passage, about one second for the
  whole list.
- **Token lengths** (bge-m3's tokenizer): tuning median 49, 99th percentile 895, longest 7,608; scripts
  median 174, longest 14,432; tools median 225, 99th percentile 4,486, longest 8,509. 2,243 passages
  are over 512 tokens, 122 over 2,048, and 2 over 8,192 (cut there). 4,936,533 tokens in all.
- **Encoding with fixed batches of 16** (the code before this fix), on 1,024 passages taken at an even
  stride: the working set passed **6,089 MB** within 13 minutes, with about 3 GB free, and the run was
  stopped. Sixteen long passages had shared one batch.
- **Encoding with the token budget** (this fix), the freeze's own encoder: 32 passages of about 60
  tokens in 10.9 s, 32 of about 370 in 61.2 s, 32 at the 99th percentile (up to 1,231 tokens) in
  207.1 s (0.0054 s a token), and the four longest (cut to 8,192) in 323.5 s (0.0102 s a token). The
  peak working set stayed at **2,674 MB**, reached while the model loaded and the list was tokenised,
  not while encoding. Vectors are float32.

### The recheck of `91576374` and the lead's rulings on it (D-414, D-419), and where each is applied

1. The leakage pass now reads .docx through `text_extract` and .jsonl line by line, and counts skipped
   files; a planted .docx and a planted .jsonl duplicate each refuse the freeze in the checks
   (section 2.6).
2. The same-source test is implemented: SOURCE.md URLs and document ids (section 2.6).
3. Kappa is taken on the pooled key, with the revision round recorded and the path above the floor
   stated (section 2.5).
4. The scorer scores round 3 in the same refused path (section 7).
5. Every arm's records are checked against the configuration, and a frozen case with no system run is
   refused (section 7).
6. An answers file of more than one model group is refused (section 7).
7. D-414 is applied: C1 alone at 0.025 one-sided, C2 to C5 indicators, C1's power decided at the frozen
   headline count (section 2.7, section 7, CLAUDE.md's NEGOTIATION-MEASURE-A).
8. The power simulation models each arm's over-prediction of `not_computable`, with 1,000 or more sets
   (section 2.7).
9. The power at the freeze uses the headline's class shares (section 2.7).
10. A dry run writes `FREEZE.dryrun.json`, which the scorer refuses (section 2.6).
11. The freeze refuses a case below the minimums (section 2.7).
12. Each corpus is encoded once, with a time forecast (section 2.6).
13. One movement allowance for B1 and the cloud reference (16 tokens), and a `no_answer` count for every
    arm (sections 3.1, 3.3 and 5).
14. Step 4 names the recomputed figures (section 9).
15. The gate check is 347 (the lead's renumbering); to be checked again at merge.

### The recheck of `57948a33` and the lead's rulings on it (D-430), and where each is applied

1. C1 is a claim only at 0.8 or more at every correlation, with a mixed-case proof (section 2.7;
   `c1_status`; check 347).
2. The cosine pass is in numpy, with a forecast covering encoding and comparison, and the cost table
   restated from the measured passage count (sections 2.6 and 5).
3. The record checks fail closed (section 7).
4. A missing or empty corpus path refuses (section 2.6).
5. Skipped files of a kind not accepted in the corpus list refuse (section 2.6;
   `NEGOTIATION_CORPORA.txt`).
6. The power record is read from the commit, its digest is in the configuration, and its code and
   assumptions are compared with the committed code (section 2.7).
7. The opening-1 power record governs both openings (section 2.7).
8. The power at the deciding settings is committed, and the plan's opening and the page say the
   measurement is expected to be indicator-only (the top, sections 2.7 and 6).
9. One line per assumption with its source, or saying it is a guess (section 2.7).

### The recheck of `04bc7b22` and the lead's rulings on it (D-437), and where each is applied

1. The failed-entry path: run folders only, one per case; a failed entry only from a FINAL_STATUS.json
   that says failed, in a failed or stopped state, for an infrastructure reason; a successful run's
   FINAL_STATUS.json, a failure for the system's own reasons and a case with a case record in a run
   given are each refused; the `--system-run` help names a folder (section 7; `refuse_system_runs`,
   `failed_entry_why`; check 347, two proofs).
2. Memory: float32 arrays in chunks of 512, batches of at most 16 passages and 8,192 tokens, longest
   first, and the peak measured on a slice of the real corpus list before any full pass: 6,089 MB and
   rising with fixed batches, 2,674 MB with the token budget (sections 2.6 and 12; check 347, two
   proofs). The measurement also corrected the forecast: about 7.5 hours of CPU encoding, not 4.1, so
   the forecast is now by token (sections 2.6 and 5).
3. The 5-gram step: one index of the cases' gram sets, each passage's grams made once, the same answer
   as every pair; in the forecast at the measured 0.00003 seconds a passage, about a second for the
   list (sections 2.6 and 12; check 347, one proof).
4. `docs/` is not a corpus, with its reason in the corpus list (section 2.6).
5. The power record names each claim's status by the plan's rule (`claim_by_plan_rule`) and lists the
   claims below 0.8 at any correlation; the older list is described where the earlier records are
   named (section 2.7; check 347, one proof).
6. The lead's ruling D-451: a failure for the system's own reasons, with no case record, scores
   `no_answer` on every row of its case and is named apart in the report; it never refuses the
   scoring, and never calls for opening 2. An infrastructure failure stays as built (section 7;
   `failed_entry_kind`; check 347, the proof `the_systems_own_failure_named_apart`).

### D-456, the lead's three additions on `f268d233`, and where each is applied

1. Both kinds of failed entry score `no_answer` on every row of their case, kept in the frozen key and
   counted apart by kind; only infrastructure can call for opening 2 (section 7; check 347,
   `a_failed_case_keeps_every_row_as_no_answer`).
2. Infrastructure only for a cause of the runner or the machine, listed: the controller's failure
   records, no runner result, the host out of memory; a pipeline exception and `backend_failure` are
   the system's own (section 7; check 347, `a_pipeline_exception_is_the_systems_own`).
3. The GPU pass reads nvidia-smi after every chunk and moves to the CPU when another process takes the
   GPU, recording the readings; the reading works where Windows hides per-process figures (section 2.6;
   check 347, `the_gpu_pass_moves_to_the_cpu_when_taken`, `the_gpu_read_where_the_driver_hides_processes`).

### D-456, part 1: nego-plan-check on `f268d233`, and where each is applied

1. A FAILED status counts as a failed entry in any pipeline state, `completed` included, and is the
   system's own unless an infrastructure cause is shown (section 7; check 347,
   `a_failed_status_in_any_state_is_the_systems_own`, on FAILED, state completed, `semantic_incomplete`,
   no case record).
2. A terminal error is read by its recorded identity, type and module; only the listed memory errors
   are excused (section 7; check 347, `a_terminal_error_read_by_its_recorded_identity` and
   `a_pipeline_exception_is_the_systems_own`).
3. The GPU pass reads nvidia-smi after every chunk; when another process takes the GPU it finishes on the
   CPU, the readings recorded (section 2.6; check 347, `the_gpu_pass_moves_to_the_cpu_when_taken`, with an
   injected reading). D-399's rule reads the whole card, which this pass's own model fills while it runs,
   so after the first chunk the rule is applied to the other processes' share: more than 1,024 MiB held
   by others is not idle. Their GPU utilisation cannot be told apart from this pass's own, so it is
   recorded and not judged.

### D-456, part 2: nego-plan-check on `e69dbe57`, and where each is applied

1. Records only at the entry root, never under `downloaded/` (section 7; check 347,
   `records_read_only_at_the_entry_root`, with `controller_failure.json` and an infrastructure
   FINAL_STATUS.json planted under `downloaded/`).
2. A per-process listing without this process's pid falls back to the card's use less this process's
   own (section 2.6; check 347, `a_listing_without_this_process_is_not_per_process`).
3. The runner's reasons decide the kind, a controller record listed beside them (section 7; check 347,
   `the_runners_reasons_decide_the_kind`).
4. The overhead from the per-process listing when it works; the first-chunk window's limit stated
   (section 2.6).
5. Utilisation beyond this pass's own, judged at 10 percent after the sync and one second (the lead,
   after first ruling it recorded only), a brief job in that window possibly missed (section 2.6;
   check 347, `utilisation_beyond_this_process_at_10_percent`, with an injected 40 percent reading).
6. `backend_failure` stays the system's own: its models run on the instance (the lead, D-456).
   So does a CUDA out-of-memory error; only `builtins.MemoryError`, the host's memory, is excused
   (check 347, `a_cuda_out_of_memory_is_the_systems_own`).
7. The controller's writing of the four records is stated as a limit and sent to judge-product
   (section 7).
8. The GPU is read before the first chunk too (section 2.6; check 347,
   `the_gpu_read_before_the_first_chunk`, a GPU taken while the model loaded).
