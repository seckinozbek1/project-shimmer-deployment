# The negotiation benchmark: the plan of its next stages (D-637, D-645)

Written on 15 November 2026, 15:04 +0300 (from `date`), by lane neg-draft-bench (neg-advisor-2), from
7a4be3c9, before any item of it exists. Design only: no spend, no item opened, no role session started. Every
rule below is fixed before the build, as the advisor's plan fixed its own (`NEG_ADVISOR_PLAN.md`), and a change
after an item exists is a new commit that says what changed and why.

Amended on 15 November 2026, 15:08 +0300, by D-639 (Seckin 15:03), before any item: the benchmark is built in
parallel with the current fixes, not as a gate in front of them; annotators may be of any family, Claude
included, double-blind from each other, their labels read only by the frozen scorer; no human annotation now
(a later step, section 5.5); and section 2a gives the evidence for adding our own benchmark. Amended at 15:10
with the scout's result (sections 2 and 2a; the rubric's frame in 5.3; no annotator grades its own family's
arm, 5.2). Restructured at 15:14 by D-640 (Seckin 15:07) into two tracks: track A, the system's decisions
against the real next round (sections 4 and 5); track B, each finding scored by the adapted rubric's criteria
(section 5b), from Seckin's draft rubric (`docs/loop/private/benchmark_inputs/Checking_AI_Proposed_Findings_Rubric_Draft.pdf`)
adapted as `docs/loop/private/benchmark_inputs/RUBRIC_SHIMMER_v0.md` (private, cited by file name only); the
design checked against Bean et al. 2025 (section 8a).

**Amended on 15 November 2026 by D-644 (Seckin 15:36), lane fix-side, before any item exists.** This amendment governs
wherever an older paragraph says otherwise.

- **Track A only, now.** Answers come from the real next round, with no rubric labels. So D6, the graded
  acceptability, leaves track A and waits with track B (sections 4 and 5).
- **No Gemini, OpenAI or Mistral annotator, and no external API key.** Where track A needs an agent, it is a
  Claude agent on a light model, double-blind, under the self-family rule (section 5.2a). Track A as amended
  needs no agent to score any arm: D1 to D5 are computed in Python (section 4).
- **Track B** stays in the plan, marked: it waits for the rubric review and a separate decision (section 5b).
- **About 40 headline items rather than 18,** if the material allows (section 3.4).
- **Cost and time restated** without external APIs (section 9).
- **Superseded where they differ:** section 5.2's default annotators, section 7's annotator bullet, section 9's
  first table and section 10's order. The text they replace is in this file's history (77e90c1e).

**One benchmark (D-645, Seckin 15:37), amended 15 November 2026 by lane fix-side, before any track A item exists.**
There is one custom benchmark for multi-round negotiation, called **the negotiation benchmark** throughout this
file. The branch and file names (`lane/neg-draft-bench`, `NEG_DRAFT_BENCH_PLAN.md`) stay as they are. Its
stages:

1. **The pilot:** the advisor test (section 0).
2. **Track A:** the system's decisions against the real next round (section 4).
3. **Track B:** each finding by the rubric. It waits (section 5b).

Each stage grows from the pilot, and none is a separate build. Where this file says "the benchmark's pass" it
means a track A (or later track B) pass of the negotiation benchmark.

## 0. The pilot (D-645)

**What the pilot is.** The negotiation benchmark's pilot is the advisor test now being scored. Its rules are
`NEG_ADVISOR_PLAN.md`, which this file never edits: the pilot's rules were written before its items.

- **Its parts:** the frozen set of role N (set SHA-256 `6a8af3c7...`; 24 items, 18 headline, 179 proposals, by
  counts only, `NEG_ADVISOR_POWER.json`), its arms' pass (B1 and the system on the A10, 14 November, D-632), the
  cloud reference on its seeded subset (D-606) and its judge pass.
- **Its scorer:** `tools/score_neg_advisor.py`, with the bootstrap, jackknife and permutation of
  `tools/score_negotiation.py`.

**The pilot's results stay the pilot's.**

- They are reported as "the negotiation benchmark, pilot (the advisor test)", with the pilot's own opening lines
  and power record.
- They are never pooled with track A's figures, and no pooling rule is fixed here. So none may be applied after
  any track A run: a pooled figure would need a rule committed before the first track A opening, and this plan
  writes none.
- The pilot's replies (its arms' pass) are not reused as track A or track B replies. They were made for the
  advisor's form, before track A's gold fields and form existed.

**What track A reuses from the pilot, and exactly where it does not:**

| Pilot part | Reused by track A | Where it does not fit |
|---|---|---|
| The frozen items, their round-k excerpts, proposals, positions, personas and matched round-k+1 texts (`next_articles`), under set `6a8af3c7...` | **as is**, the same SHA-256 | track A adds fields (T1's articles asked and gold texts) and a part P2 (section 3.4). These are new frozen files with their own digests beside the pilot's, never a rewrite of the pilot's set |
| The leakage pass (5-gram, bge-m3 cosine, same source) and its counts | **as is** for the 24 items, no new risk since no new text | P2's items are new text: the same pass is run on them through the vectors route (68b7537c), and its counts are recorded apart |
| The digests (set, configuration, cloud subset) and `freeze`'s machinery | the pilot's digests are named in track A's `FREEZE.json` as its base | track A's configuration differs (its form, its metrics), so it has its own configuration SHA-256 and opening lines (`neg-draft opening ...`), never the pilot's |
| `score_neg_advisor.py` functions: `fate` (open, kept, changed or removed, the diff of plan section 4.1), `jaccard5`, `bracket_spans`, `split_article`, `macro_f1`, the 5-cell rule and the statistics | **reused** by track A's scoring, imported, not copied | D1's closeness gain, D2's ROUGE-L, D3's per-alternative bracket resolution and T1's and T2's reply parsing are not in it. They are added as new subcommands of the same scorer (for example `score-draft`), each proven on fixtures, the pilot's `score` left byte for byte as it is |
| The cloud subset draw (D-606, seeded) | the same 20 items for the cloud reference on the 24-item part | at about 40 items, a subset of P2 is drawn by the same seeded rule as a new draw, recorded with its own SHA-256 |
| The judge pass and the Phi-4 mapping validation | **not reused** | track A has no judged metric (D-644: D1 to D5 are Python's); D6 and track B wait |
| The arms' prompts (`neg_advisor_prompt.json`, the advisor form) | **not reused** | track A asks T1 and T2 in its own declared structured form (section 4); a new prompts file of its own |

Development, exposed. Our benchmark: no published benchmark fits (section 2, the scout's
result), so every figure is "our metric" until a fitting published one is found and run beside it.

## 1. What is measured, in two tracks (D-640 item 1)

**Track A, the system's decisions:** accept, reject, middle wording and article status, scored against the real
next round (section 4; under D-644 the only track built now, with D1 to D5 alone). **Track B, the system's findings
(waits for the rubric review and a separate decision, D-644 item 5):** each finding (in the advisor form, each piece
of advice with the passages it cites) scored by the adapted rubric's criteria, each reported separately (section
5b). **The same items for every arm:** B1 (the bare base model), the cloud reference (on its seeded subset, the
same items for B1 and the system beside it) and Shimmer (D-640 item 5).

D-637: a purpose-fit benchmark for multi-round negotiation drafts, built before v1.0, so that the system's
drafting claims can be defended. Given the record of a negotiation up to round N (the round-N text with its
brackets, the two indexes, the positions on record, a persona and its mandate), the system does one of two
tasks for a stated set of articles:

- **T1, the draft:** write round N+1's text of each article, as the next negotiating text would read it;
- **T2, the moves:** for each proposal on the table, say what round N+1 does with it: kept, changed, removed or
  still open (the advisor's `fate` classes), and for a changed proposal, its new wording.

T2's labels are the advisor's `fate`, computed from the real next round by the deterministic diff of
`NEG_ADVISOR_PLAN.md` section 4.1; T1's gold is the real next round's text itself. Both are judged against what
the parties actually agreed or wrote next, never against what a model thinks good drafting is, except for the
one graded criterion of section 5, which is labelled.

## 2. Existing benchmarks and rubrics (the scout's result)

From the scout of 15 November 2026 (`scratchpad/neg_bench/SCOUT.md`, the lead's). Each entry keeps the scout's
tag: **verified** (the scout read the primary page), **search summary** (from a search result, not read), or
**unverified**. A search-summary entry is cited here as such, never as verified, and is read at its source
before the freeze.

**No published benchmark takes its gold from the real next draft of a public negotiation** (searched across
treaty, UN, climate, trilogue and labour negotiations). Ours is new. The nearest:

| Name | What it does | Fit to T1 and T2 | Licence | Tag |
|---|---|---|---|---|
| TradeVerse (WTO specific trade concerns), arXiv 2608.06549 | real multi-round WTO meeting records, the last round held out, labels from the proceedings; task 3 writes the responding country's last-round statement | partial: real rounds and a held-out last round, but a statement, not a draft text | paper CC BY 4.0; data licence not found | verified (page); licence unverified |
| UNBench (UN Security Council 1994 to 2024), arXiv 2502.14122, AAAI 2026 | statement generation from the draft, the votes and earlier statements, gold the official speech, scored by ROUGE and SBERT (best ROUGE about 0.21) | partial: real UN records, no draft-to-draft task; its ROUGE-only scoring is the caution for our own overlap metrics | not stated | verified (page) |
| RedlineBench (Crosby and micro1), Hugging Face crosbylegal/RedlineBench | multi-turn contract redlining over four alternating turns, scored on attorney-written pass/fail rubric items in five dimensions by three LLM judges, majority vote; no inter-judge agreement reported | the structural match (round-by-round drafting, next-turn redline), but its gold is simulated | CC BY 4.0 | verified (page and card) |
| War of Words I and II (European Parliament amendments) | whether an amendment to a draft law is adopted, gold the real outcome | partial: real proposal-versus-adopted outcomes (a T2 analogue), binary, no wording | Zenodo licence not checked | search summary |
| Raw sources, no dataset: UNFCCC dated drafts, Carbon Brief COP text trackers, the COP21 text archive, EU four-column trilogue tables (released per request) | versioned real drafts with brackets, or positions beside a compromise column | source material for more items (section 3.2), not a benchmark | UN documents generally reusable; others per source | search summary |

The rest the scout listed (NegotiationArena, LAMEN, PieArena, CaSiNo, CraigslistBargain, Deal or No Deal, the
Diplomacy deception set, IteraTeR) are games, crowdsourced dialogues or single-author revision, with no real
negotiated next text; IteraTeR is the method precedent for predicting revision t+1 from revision t (search
summary).

**Run beside ours, once each licence is confirmed for this use:** TradeVerse (the nearest external check: real
rounds, last round held out) and UNBench's statement task (a public, coded UN baseline). Neither licence is
stated, so neither runs until the role session records it in `SOURCES.md`. **RedlineBench** is used for the
harness and the rubric's frame only, never as a measure of real negotiations, since its gold is simulated.

**Rubrics.** No published negotiation-draft rubric reports agreement figures, so ours is written (section 5.3).
It starts from **RedlineBench's five dimensions** (legal correctness, adherence to commercial context,
negotiation quality, counterparty acceptance prediction, deal-closing orientation; verified), rewritten for
public multilateral texts, with per-item pass or fail. It adds the method of arXiv 2609.16482 (verified page):
atomic items frozen from the case record, the judge validated on a held-out human set. LAMEN's computed
faithfulness (public offers inside the private range; search summary) maps onto the advisor's Python check
C-mandate, which is computed, never judged.

**Annotation precedents** (all search summary): a jury of judges from different families beat one large judge
with less self-preference (PoLL, arXiv 2404.18796); model-model Krippendorff alpha predicted human-model
agreement (arXiv 2408.05534); judges favour their own family's outputs even unlabelled (Panickssery, Bowman and
Feng, arXiv 2404.13076); one study found LLM coders at alpha about 0.55 against humans, under the 0.67
threshold (arXiv 2408.15895). Each sets a rule in section 5.2 or 5.4.

## 2a. Why our own benchmark (D-639 item 4)

A purpose-built agent judged on general benchmarks alone is measured on constructs it was not built for. The
sources are the scout's section 4 (tags as there: only UNBench's entry was read at its source by the scout; the
rest are search summaries, cited as such and read at their source before the freeze):

- **Construct validity.** A review of 445 LLM benchmarks finds patterns in phenomena, tasks and metrics that
  undermine validity claims (A. M. Bean, R. Kearns, A. Romanou et al., "Measuring what Matters: Construct
  Validity in Large Language Model Benchmarks", NeurIPS 2025 Datasets and Benchmarks; search summary).
  General-purpose benchmarks are poor evidence of general capability, tasks chosen without a theory of what
  they stand for (I. D. Raji, E. M. Bender, A. Paullada, E. Denton and A. Hanna, "AI and the Everything in the
  Whole Wide World Benchmark", NeurIPS 2021 Datasets and Benchmarks; search summary).
- **Scenario coverage.** Covering the deployment scenario and metrics beyond accuracy changes conclusions, so a
  scenario must be named to be measured (P. Liang et al., HELM, TMLR 2023; search summary).
- **Domain-built items and domain-validated judges.** Legal reasoning needed 162 tasks built by legal
  professionals (N. Guha et al., LegalBench, NeurIPS 2023; search summary). Judges must be validated per task,
  since their reliability varies with the property judged (A. Bavaresco et al., JUDGE-BENCH, ACL 2025; search
  summary).
- **The diplomatic case.** Political and diplomatic tasks needed a benchmark built from UN records, and general
  overlap metrics (ROUGE) scored every model low on diplomatic text (UNBench, AAAI 2026; **verified**).
- **Contamination.** Benchmark items leak into training data and inflate scores; fresh, held-out, post-cutoff
  gold is a remedy (Xu et al., arXiv 2406.04244, and Cheng, Chang and Wu, arXiv 2502.14425; preprints, search
  summary). This plan's gold is the real next round, with each item's post-cutoff mark (the advisor's
  `post_cutoff`) and its figures reported apart.
- **Supporting, not settling** (preprints, search summary): agents degrade on production tasks drawn from real
  requirements (AlphaEval, arXiv 2604.12162), do not transfer between domain and general settings (General
  AgentBench, arXiv 2602.18998), and are not measured on deployment needs (CLEAR, arXiv 2511.14136); LLM
  judges reward formal completeness over practical judgment in legal work (LawFlow, arXiv 2504.18942).
- **For this task.** None of the loop's benchmarks (ContraDoc, SciTab, PUBHEALTH, the gate's sets) asks for round
  N+1's negotiating text or for what the next round does with a bracketed proposal, and none takes its gold
  from what parties actually agreed next. A claim that Shimmer drafts or advises in multi-round negotiation
  needs a test whose items are such rounds and whose gold is the real next round.

The lane's earlier entries from its own knowledge (Jacobs and Wallach, FAccT 2021; Bowman and Dahl, NAACL 2021)
are not in the scout's list; they stay out until read at their source.

## 3. The items and their gold

### 3.1 Sources, by the real next round

Gold comes from the real next round of public multi-round negotiations wherever possible, as in the advisor's
set: the WHO pandemic agreement's negotiating texts (INB), the plastics treaty's INC-5.1 and INC-5.2 texts,
BBNJ in reserve. A synthetic round (the advisor's part H) has no real next round, so it is left out of T1 and
T2's headline and reported apart, marked synthetic. The LLM-Deliberation games (part G) have no draft text and
are left out.

### 3.2 Built on the frozen negotiation material

The advisor's frozen set (role N's, `NEG_ADVISOR_PLAN.md`) already holds, per item, the round-k excerpt, its
proposals, its positions, the persona and the matched round-k+1 text of every article (`next_articles`), frozen
with a leakage pass. Known to the builder by counts only: 24 items in the arms' pass, 18 of them headline
public items, 179 proposals (`NEG_ADVISOR_POWER.json`); the builder has opened none.

- **Reused as is (the pilot's, section 0):** the items, their excerpts and their round-k+1 texts, under the
  same set SHA-256, so track A adds no new source text and no new leakage risk on these 24 items. T2's `fate` labels are already in the advisor's
  key, computed by the diff (no annotator).
- **Added by the role session:** per item, the articles T1 asks for (every excerpt article whose text changes
  in round k+1, by the advisor's own selection rule), and T1's gold text (the matched round-k+1 article, with
  its brackets as published).
- **More items, if the scout or the power needs them:** further (process, round) pairs from the same sources,
  chosen by the advisor's seeded rules (its section 3), labelled by the same diff, and checked by the same
  leakage pass. They are new items, frozen with the set's own machinery, never mixed with the pilot's figures (section 3.4, part P2).

### 3.3 Who sees what

As in `NEG_ADVISOR_PLAN.md` section 9: the builder (this lane, the lead) sees no item, label, gold text or
per-item result; a role session builds, labels and freezes in its own folder and hands back counts; sealed or
exposed passes run on rented machines launched by the lead unopened.

### 3.4 The path to about 40 headline items (D-644 item 6)

**Where the set stands, by counts only.** Role N's frozen set has 24 items in the arms' pass, 18 of them
headline public items (part P), and 179 proposals (`NEG_ADVISOR_POWER.json`, set `6a8af3c7...`). Part P was planned
at 30 (INB 20, INC 10) with BBNJ in reserve (`NEG_ADVISOR_PLAN.md` section 2), so the sources already in the plan
fell short. The builder does not know by process which items were kept or whether BBNJ was drawn. The role
session reports that as counts. About **22 more headline items** are needed for about 40.

**The rule for adding items.** New (process, round k to k+1) pairs only, each with a published round-k text and
a published round-k+1 text of the same articles. They are chosen by the advisor's seeded selection rules (its
section 3), labelled by the same deterministic diff (its section 4.1), and frozen as a new part P2 under its own
SHA-256. P2 has no key of the pilot's (no advisor labels), and it is never mixed into the pilot's figures. The benchmark's headline
is P and P2 together, reported per process and per round count as well.

**Candidate public sources, each to be read at its source by role N before use.** Nothing below has been opened
for this plan; the yield per round pair is not known.

| Source | Round texts | Terms (what is known now) | Notes |
|---|---|---|---|
| BBNJ, the IGC sessions (un.org/bbnj) | draft texts with track changes, IGC-3 to IGC-5 | un.org's terms of use: personal, non-commercial use, "without any right to resell or redistribute them" or "to compile or create derivative works". Read 15 November at un.org/en/about-us/terms-of-use; a per-document copyright note is not read | already in the advisor's plan as the reserve. Research use only; redistribution would need permission |
| UN business and human rights treaty, OEIGWG (OHCHR) | the zero draft (2018) and the revised drafts of July 2019, August 2020, August 2021 and July 2023, each the basis of the next session; later Chair-Rapporteur reformulations reported (search summary, not confirmed at OHCHR) | OHCHR's terms not read | four or more consecutive round pairs with article structure; the strongest single addition |
| WHO IHR amendments, WGIHR (apps.who.int/gb/wgihr) | the bureau's texts across the sessions of 2023 to 2024 | WHO material CC BY-NC-SA 3.0 IGO, as INB (to confirm for these documents) | same publisher and terms as INB, so the same publication rule |
| WHO pandemic agreement annex, PABS, IGWG (2025 to 2026) | the bureau's texts per session | as WHO (to confirm) | post-cutoff for most models, so its figures are reported apart as post-cutoff |
| Plastics treaty, INC-2 to INC-4 (UNEP) | the zero draft and the revised draft of INC-4 | UNEP terms to be confirmed, as for INC-5 | earlier rounds of a process already in the set: the same-source rule of the leakage pass applies |
| UN cybercrime convention, the Ad Hoc Committee (UNODC) | consolidated negotiating documents and revised drafts, 2022 to 2024 | UNODC's terms not read | a third publisher |

**What it needs:**

- **Licence.** Role N records each source's terms in the advisor's `SOURCES.md` before use. A source whose terms
  forbid redistribution (un.org as read) is admitted for the measurement only, and left out of anything published
  (section 7).
- **Leakage check.** The advisor's leakage pass on the added items, rerun through the vectors route (68b7537c),
  as section 6 says: 5-gram overlap, bge-m3 cosine and same source.
  - It checks against the frozen set's other items and against the system's development material (the 13
    November development pairs, `NEG_ADVISOR_PLAN.md`).
  - Under LEAKAGE_PROTOCOL's "every set" rule, it also checks against the parts named there.
  - An item hit goes whole, with its process round.
  - Embedding about 22 items' texts is small: one replay-pass embedding job on Lambda, or the laptop GPU when
    idle (D-399, D-629).
- **Role N session.** One session, detached and restricted as the advisor's (D-528). It finds the round texts,
  applies the seeded selection and the diff, freezes P2 and hands back counts. A text whose article blocks the
  parser cannot split is handled by section 5.2a's extraction rule, or left out and counted.
- **Calendar.** About 1 to 1.5 days of role N time: sourcing and terms half a day, building and the diff half a
  day, then the leakage pass and the freeze. The power record is recomputed at the new frozen count before the
  opening (section 8). If fewer than about 40 headline items survive, the shortfall is recorded and the plan runs
  at the count it has, indicator-only below power 0.8.

## 4. Track A: the metrics of the system's decisions

All on the frozen headline items, per arm, with n; every figure per process and round count as well; a cell
under 5 items is its count alone.

| Id | Task | Figure | How |
|---|---|---|---|
| D1 | T1 | **Closeness gain** (primary) | per article, the draft's word 5-gram Jaccard with the real round-N+1 text, less the round-N text's own Jaccard with it: positive when the draft moved toward what was agreed. Averaged per item, then over items |
| D2 | T1 | Closeness | the draft's 5-gram Jaccard and ROUGE-L F with the real round-N+1 text, as they are |
| D3 | T1 | Bracket resolution | per bracketed alternative of round N, whether the draft keeps it, drops it or leaves it bracketed, scored against the real round N+1 by the advisor's fate rule; Macro-F1 |
| D4 | T2 | Move Macro-F1 | Macro-F1 over the key's `fate` classes (kept, changed, removed, open), `no_answer` always a miss |
| D5 | T2 | Changed-wording closeness | for proposals whose real fate is `changed`, the given wording's closeness gain, as D1 |
| D6 | T1 | Graded acceptability (labelled): **not in track A now; waits with track B** (D-644 item 2) | section 5: the rubric's grade of each draft, 0 to 2, by the annotators |

**Under D-644, track A is D1 to D5, every one computed in Python, with no agent reading any arm's output.**

- **Gold:** the real next round, by the advisor's rules: the deterministic diff of `NEG_ADVISOR_PLAN.md` section
  4.1 and its article selection.
- **The metrics:** 5-gram Jaccard, ROUGE-L F, the fate rule and Macro-F1, all code in the frozen scorer.
- **Every arm's reply is read in Python.** Each arm answers in one declared structured form: per article, its
  draft text; per proposal, its fate class and, for `changed`, its wording.
  - A reply that does not parse, or names an article or proposal the item does not hold, is `no_answer` on
    those rows for every arm alike, never repaired by an agent.
  - So the cloud reference's drafts (a Claude arm) are scored exactly as B1's and the system's, and the
    self-family rule (section 5.2a) is never engaged in scoring.

The arms are the advisor's: B1 (the bare base model), the system (its producer, its audit and
Python's checks), and the cloud reference on its seeded subset (D-606).

## 5. The labelled criterion D6, the middle wording (waits with track B, D-644 item 2)

D6 is a rubric label, so under D-644 it is not built now. It waits with track B for the rubric review and a
separate decision. Sections 5.1 to 5.5 stay as its design. Section 5.2a is the agent rule that holds now, for
every agent track A uses.

### 5.2a Agents in track A now (D-644 item 3)

Track A as amended scores no arm with an agent (section 4). An agent may be used in **one** place only, by
role N, before any arm runs: **extraction from a source text.** That means splitting a published round text
into its article blocks where the parser cannot, or pairing a round-k article with its round-k+1 article where
the diff's numbering rule cannot.

- **Claude agents on a light model** (the lightest Claude model read live from the provider, never
  hardcoded), within the usage pace of about 1 weekly point an hour.
- **Double-blind.** Two agents extract each such text, each in its own session, neither seeing the other. Their
  outputs must agree after whitespace normalisation. Otherwise the article is left out and counted, never
  resolved by a third guess.
- **The self-family rule.** These agents read only the source texts, never a draft or a reply of any arm. So no
  Claude agent ever scores or reads the cloud reference's output (Claude). If a later step needed an agent to
  read arm outputs, the cloud arm would be computed only, or reported as **not scored for that arm**, never scored
  by a Claude agent.
- **No label leakage.** Extractions are part of the frozen set, built in role N's folder, and seen by the
  builder by counts only (section 3.3).

### 5.1 The label

Each draft of an article is graded **2** (it keeps the persona's mandate and reads as negotiating text the
parties could table: complete sentences, bracket syntax kept, no invented article), **1** (usable text that
breaks one of those) or **0** (unusable, off the article, or breaks the mandate). The grader sees the round-N
text, the mandate, the draft and the real round-N+1 text, blind to the arm, in one shuffled order (seed
20261115), as the advisor's judge (`NEG_ADVISOR_PLAN.md` section 6.3).

### 5.2 The annotators (D-639 item 2)

The annotation workflow sits outside Shimmer, so an annotator may be of any family, Claude included. What holds:

- **Double-blind:** two annotators grade every draft, each in its own session with its own context, neither
  seeing the other's grades, notes or existence, nor the arm of a draft. A disagreement goes to a third
  annotator, blind the same way; a draft all three grade differently is reported as unsettled, counted.
- **No label leakage:** the labels are written only into the role session's frozen key folder, kept like
  `benchmark/keys` (outside every tree that builds, tunes or selects Shimmer, never committed, never opened by
  the builder or any agent that changes Shimmer) and read only by the frozen scorer. No label, grade or rubric
  note reaches a prompt, a training row, a threshold, a model choice or a checkpoint selection of Shimmer.
- **Shimmer's own separation unchanged:** inside Shimmer the producer and the auditor stay of different families
  (LAW-III), and the arms run exactly as the advisor's plan defines them.
- **Superseded by D-644 item 1** (no Gemini, OpenAI or Mistral; no external API key). For D6 and track B, when a
  separate decision opens them, the annotators are Claude agents under section 5.2a's rules. The cloud arm is then
  not graded, since only Claude agents remain. The text below is the plan as of 77e90c1e. The default choice (each
  read live, never hardcoded): annotator 1 a fresh Claude agent; annotator 2 Google
  Gemini through its API; the third, for disagreements, OpenAI GPT. Two families for the two graders, so one
  family's own preferences are not doubled (PoLL's precedent, section 2).
- **No annotator grades its own family's arm.** Judges favour their own family's outputs even unlabelled
  (section 2), so the Claude annotator's place is taken by the third annotator for the cloud reference's
  drafts (a Claude arm), and a Qwen or Phi annotator is never used (the system's and B1's families). The
  all-Claude choice (three fresh agents, the no-API option) therefore cannot grade the cloud reference's drafts:
  under it, D6 is reported for B1 and the system only.

### 5.3 The rubric and its two checks

- **The rubric:** written, since no published negotiation-draft rubric reports agreement (section 2): 5.1's
  grade, broken into per-item pass or fail criteria from RedlineBench's five dimensions rewritten for public
  multilateral texts, with its atomic items frozen per item from the record (arXiv 2609.16482's method), in a
  file of its own committed before any grading, worked examples from development material only (never an item).
- **Check 1, the labels against the rubric** (D-637 item 4, kept): one agent that graded nothing re-grades a seeded 20 percent of the drafts (at least 30) against the rubric and states, per draft,
  whether the label follows it; the share that does is reported.
- **Check 2, the rubric itself:** a separate agent, of another family than check 1's, reviews the rubric: whether each grade is defined, whether a grader could tell 2 from 1 from the text alone,
  and what it would change; its review and any change made from it are recorded before grading starts.

### 5.4 Agreement and its floor

Krippendorff's alpha for ordinal data between the two annotators, with its bootstrap interval; Cohen's
weighted kappa beside it. **Floor: alpha 0.667**, the lowest value Krippendorff allows for tentative
conclusions. Below it the rubric is revised once (check 2's agent sees which drafts disagreed, never the grades)
and the grading repeated; still below it, D6 is reported as not validated and every claim resting on it is an
indicator.

### 5.5 Human annotation, later (D-639 item 3)

No human annotates now. The scout recommends a small expert-labelled anchor set, since every study it found
that measured judges against humans found task-dependent gaps (section 2); under D-639 item 3 that anchor is a
later step only, planned after the agent annotation has been measured (its agreement and check 1's share
reported): its size, who grades and how it is compared with the agents' labels are written then, as a change
to this plan before it runs. Until then D6 carries the scout's caution beside it: agent agreement is not
agreement with people.

## 5b. Track B: each finding by the rubric (D-640 items 1 to 3): waits for the rubric review and a separate decision (D-644 item 5)

Nothing in this section is built or run now. Its annotators are no longer those of section 5.2's old default
(D-644 item 1).

**The finding.** In this benchmark's pass, each piece of advice an arm gives (a proposal's conflict, stance and
counter wording, with the `PAR-` and `POS-` ids it cites) is one finding; its cited passages are those ids'
texts. Track B scores the benchmark's own pass, run after the freeze, never the advisor's arms pass of 14
November (its replies existed before track B's reference judgements, and section 7 of the rubric requires the
judgements first).

**The criteria, the draft's nine, each reported apart, never summed:** support, saying "not enough evidence"
(abstaining), confidence, cause and correlation, attribution, accuracy, consistency, time, and scope of the
proposed change. Each check's
result is one of four (met, partly met, not met, cannot decide, the last naming the missing record); a criterion
that does not apply is left out with its reason. Each problem carries one of the rubric's fixed failure labels
(15, defined in `RUBRIC_SHIMMER_v0.md` section 6), stored with the grade, so every finding with the same problem
can be counted. Per criterion and per arm: the share met, partly met and not met, with n and a cluster
bootstrap interval over items; per label, its count per arm.

**Where code decides.** Where Shimmer already decides a criterion in code (a quote not in its unit refused, an
uncited affirmation downgraded, figures computed by Python, decoding deterministic), the rubric file names the
gate check; the annotators grade what code does not decide, and the two are reported apart.

**Reference judgements, written and frozen first** (D-640 item 3, the rubric's section 7): a role session builds
claim and passage pairs from public or synthetic material (the items' public texts, synthetic pairs for hard
cases they lack), including the four hard cases (a
passage reworded in the later version, moved or removed, a nearby passage that almost supports, a passage out of
context), and two agent annotators of different families label them (supports, partly supports, does not
support, contradicts), double-blind; a third agent breaks ties. Their agreement (Krippendorff's alpha, ordinal)
is reported, and the pairs and labels are frozen (SHA-256 in the freeze) before any system run of the benchmark.
They calibrate the annotators: an annotator whose labels on the frozen pairs fall below the floor of section 5.4
does not grade track B.

**The annotators** are those of section 5.2 (two double-blind agents of different families, a third for ties, no
annotator on its own family's arm), labels kept like `benchmark/keys`. **Seckin** sets the standards (the rubric,
its floors) and labels nothing.

**The record-layer tests.** The rubric's six history tests become checks of Shimmer's record layer (test 6, repeat runs, a rough check
only), each named in
`RUBRIC_SHIMMER_v0.md` section 8 with the gate check or code site it maps to: the original version and passage
kept (built: runs never overwrite, the append-only bus, the earlier version read and never amended), a regression
run (built: the gate), the label reworded between versions (built: refused, never resolved, checks 185 and 279),
a revised source reopening its findings and a reopened finding adding an entry (partly: recomputed and
superseded, with no reviewer status), and two reviewers' split kept and a repeat-run comparison (not built in
Shimmer). They are reported as the record layer's state beside track B, not as a score of any arm.

## 6. The freeze

As the pilot's (section 0), with the pilot's machinery: rules, items, gold and the scorer frozen before any
track A run (the rubric too, when track B is opened). `FREEZE.json`
names the pilot's set SHA-256 as its base, T1's added fields' and P2's own SHA-256, the rubric's SHA-256, the scorer's SHA-256,
the leakage counts (the advisor's pass, rerun only for added items, through the vectors route of 68b7537c) and
the annotators' configuration. A committed opening line (`neg-draft opening k=<k> set=<sha> config=<sha>`)
precedes any score; at most two openings, the second only for an infrastructure failure.

## 7. Publication terms

- **Text:** WHO INB material is CC BY-NC-SA 3.0 IGO; ENB is CC BY-NC-SA 4.0; UNEP, UNFCCC and BBNJ terms are read
  and recorded per source by the role session before use (the advisor's `SOURCES.md` and `sources.json`). The
  published data keeps attribution, non-commercial and share-alike terms, and leaves out any source whose terms
  do not allow redistribution.
- **Labels, gold and scorer:** the gold texts are the sources' own (same terms); the labels and the scorer are
  ours, published under the repository's licence.
- **Annotators (D-644):** no excerpt is sent to any external annotator API. The only outside API in track A is
  the cloud reference arm's own, under the advisor's rule (`NEG_ADVISOR_PLAN.md` section 10).
- **Sources read for measurement only:** un.org's terms (section 3.4) permit personal, non-commercial use without
  redistribution. Items from such a source are measured and never published, unless permission is obtained.
- **Nothing is published** before each source's terms are confirmed for redistribution and Seckin agrees.

## 8. Power

**Primary claim, one:** D1, system against B1, a paired difference per item, one-sided at 0.05 / 2^k, by the
advisor's machinery (BCa cluster bootstrap, jackknife, permutation). Planning figure only: 18 headline items
with about 4 changed articles each; at a per-item standard deviation of the closeness gain near 0.10 and a true
gain of 0.05, the standard error is about 0.024 and the one-sided power at 0.025 about 0.55. **Expected:
indicator-only** unless more items are added (about 40 headline items give about 0.88 under the same guesses).
Under D-644 item 6 the plan aims at about 40 headline items (section 3.4). The planning figure moves from about
0.55 at 18 to about 0.88 at 40. It is a guess until the simulation at the frozen count, which alone decides
claim or indicator.
The rule, as the advisor's: a claim only if a simulation at the frozen counts, with 1,000 or more sets, gives
0.8 or more; the record committed before the opening.

## 8a. The design against Bean et al. 2025's eight recommendations (D-640 item 4)

Source: A. M. Bean, R. Kearns, A. Romanou et al., "Measuring what Matters: Construct Validity in Large Language
Model Benchmarks", NeurIPS 2025 Datasets and Benchmarks (the scout's section 4; search summary, to be read at its
source before the freeze). The eight recommendations as D-640 item 4 lists them:

| Recommendation | How this design meets it | What is missing |
|---|---|---|
| 1. Define the phenomenon | Track A: what the next negotiating text does with a proposal and how the parties worded it; track B: whether a finding is supported by its cited passages and keeps its history (section 1, the rubric's section 1) | the phenomenon's boundary for cross-issue trades and approach advice is not defined here (left to the advisor plan) |
| 2. Measure only the phenomenon | track A's gold is the real next round (no style judgement); track B's criteria are reported apart, never summed; the rubric excludes writing style | D1's 5-gram closeness also rewards copying the round-N text; the gain over round N (D1) controls for it, the raw closeness (D2) does not |
| 3. Representative data | real rounds of public multilateral negotiations, seeded selection by structure (the advisor's rules), per-process and per-round-count figures | three processes only; bilateral and commercial negotiations absent (part H is synthetic and apart); the scout's raw sources (UNFCCC, EU four-column tables) are not yet packaged |
| 4. Careful reuse of data | built on the advisor's frozen set, its leakage pass and digests reused; no item reused from a gate set or any tuning | the advisor's arms pass is not reused for track B (its replies predate the reference judgements) |
| 5. Contamination | the leakage pass (5-gram, bge-m3 cosine, same source); each item's post-cutoff mark and its figures apart | public texts may be in every model's training data; the cloud reference knows later outcomes; no item is post-cutoff for the cloud reference with certainty |
| 6. Statistics | paired cluster bootstrap, jackknife and permutation; a claim only with simulated power at 0.8; agreement with its interval; cells under 5 items given as counts | power is about 0.55 at 18 headline items: indicator-only unless items are added |
| 7. Error analysis | track B's fixed failure labels counted per arm; refusals and unsettled grades counted; per-process and per-round figures | no planned qualitative review of the worst cases by a person (D-639 item 3: no human annotation now) |
| 8. Justify validity | section 2a (construct validity, task fit), the label-free gold of track A, the reference judgements and agreement of track B, this table | the sources are search summaries until read; agent agreement is not agreement with people (section 5.5) |

## 9. Cost, time and the effect on v1.0

### 9.0 Track A only, without external APIs (D-644 item 4): the table in force

Estimates from the same measured rates as below. Lambda at 1.68 USD an hour (the A10 times 1.3). The drafting
pass is scaled from the arms' pass of 14 November: 48 prompts, 52 minutes and 1.12 USD measured; 95 minutes and
2.66 USD forecast (D-632). The low figure of each range is the measured rate, the high one the forecast's.

Volumes: about 46 items (the 24 frozen, of which 18 headline, plus about 22 P2 headline items), 2 rented arms,
so about 92 prompts. Claude usage is counted as agent hours against Seckin's pace of about 1 weekly point an hour,
so an agent hour is about one weekly point. A light-model extraction agent uses less; its hours are an upper
bound.

| What | Lambda | API (the cloud reference arm alone) | Claude agent hours (about weekly points) | Calendar |
|---|---|---|---|---|
| This amendment, the plan (free) | 0 | 0 | about 1 lane hour | 15 November |
| Role N: T1's fields on the frozen 24 items (articles asked, gold text), by the advisor's deterministic rules | 0 | 0 | about 3 | 0.5 day |
| Role N: P2, about 22 more headline items (sourcing, terms, seeded selection, diff, freeze), section 3.4 | 0 | 0 | about 5 to 8 | 1 to 1.5 days |
| Extraction agents where the parser cannot split a text (two light Claude agents, double-blind, section 5.2a) | 0 | 0 | at most about 1 | inside the above |
| Leakage pass on P2 (bge-m3 vectors route, 68b7537c) | 0 on the idle laptop GPU, or about **0.5 to 1 USD** | 0 | lead hour | 0.25 day |
| B1 and system drafts on the A10, about 92 prompts, one pass as the arms' pass | about 1.7 to 3 h, **2.1 to 5.1 USD** | 0 | lead hour | 0.5 day |
| Cloud reference drafts: the D-606 seeded subset of 20 items, or the subset scaled to the 40 headline items | 0 | **0.9 to 1.4 USD** (20 items); **about 1.8 to 2.8 USD** (40) | 0 | with the above |
| Scoring D1 to D5 in Python, freeze, opening line, report | 0 | 0 | about 2 | 0.5 day |
| **Track A, about 40 headline items** | **2.1 to 6.1 USD** | **0.9 to 2.8 USD** | **about 12 to 16** | **about 2.5 to 3 days, in parallel** |
| Track A on the 24 frozen items alone (no P2) | 1.1 to 2.7 USD | 0.9 to 1.4 USD | about 6 to 7 | about 1.5 days, in parallel |

- **No annotator API cost** remains (D-644 item 1). Every metric is Python's (section 4). The only API spend is
  the cloud reference arm's own, counted toward the API ceiling in the spend store (`cloud_reference_spend.api_room`).
- **Above 3 USD, asked first** (D-629). Track A at about 40 items totals about 3 to 8.9 USD (Lambda and the cloud
  reference), so it is asked as one FOR_SECKIN entry, each figure recomputed from the frozen counts and the built
  prompts files. On the 24 frozen items alone it is 2.0 to 4.1 USD, and asked likewise when above 3.
- **Effect on v1.0:** in parallel with the current fixes, never a gate (D-639 item 1). The shared limits are the
  laptop's one-heavy-job rule (D-629), the one role N session at a time, and agent usage at about 12 to 16 weekly
  points.

### 9.1 Both tracks with API annotators: the earlier table (superseded by D-644; kept as the plan's record)

Prices read on 15 November 2026, between 15:02 and 15:04 +0300, per million tokens (input and output): Google
https://aistudio.google.com/docs/pricing (`gemini-3.1-pro-preview` 2.00 and 12.00; `gemini-3.8-flash` 0.75 and
3.75 through 31 December; Batch 50 percent), OpenAI https://developers.openai.com/api/docs/pricing
(`gpt-6.1-sol` 2.00 and 10.00; `gpt-6.1-terra` 1.00 and 5.00; Batch 50 percent), Mistral https://mistral.ai/pricing
(Mistral Large 0.50 and 1.50), Anthropic from `NEG_ADVISOR_PLAN.md` section 11 (Claude Sonnet 5.5 2 and 10). Lambda
from the A10's 1.29 USD an hour, times 1.3, 1.68 USD an hour (`NEG_ADVISOR_PLAN.md` section 11). Volumes: 18
headline items, about 72 drafted articles (about 4 an item), 3 arms, so about 216 drafts to grade; a grading
call about 6,000 input and 300 output tokens. The drafting pass has the arms' pass's shape (one prompt per item
per arm, up to 2,048 output tokens, the system's audit derived), measured on 14 November at 52 minutes and
1.12 USD for 48 prompts (D-632), forecast 95 minutes and 2.66 USD.

| What | Lambda | API | Claude usage | Calendar |
|---|---|---|---|---|
| Design, scout, rubric (now, free) | 0 | 0 | about 1 lane hour | 15 November |
| Role session: T1 fields on the frozen set, the rubric file | 0 | 0 | about 3 role hours | 0.5 day |
| B1 and system drafts on the A10 (24 items x 2 arms, one pass as the arms' pass) | about 1 to 1.6 h, **1.1 to 2.7 USD** | 0 | lead hour | 0.5 day |
| Cloud reference drafts, the D-606 subset (20 items, Sonnet 5.5, at most 24,000 input and 2,048 output tokens a call) | 0 | **0.9 to 1.4 USD** | 0 | with the above |
| Annotator 1, a fresh Claude agent (216 drafts) | 0 | 0 | about 2 agent hours | 0.25 day |
| Annotator 2, Gemini 3.1 Pro (216 drafts) | 0 | **3.4 USD** (1.7 with Batch) | 0 | 0.25 day, 1 day with Batch |
| Third annotator, GPT-6.1-sol: the disagreements (about 30 percent, 65 drafts) and the cloud reference's drafts in the Claude annotator's place (about 80) | 0 | **2.2 USD** | 0 | with the above |
| Check 1 (30 drafts) and check 2 (one rubric review), Claude agents | 0 | 0 | about 1 agent hour | with the above |
| Track B, reference judgements: about 150 claim and passage pairs, two annotators (a Claude agent, Gemini 3.1 Pro) and a third on ties | 0 | **about 0.8 USD** | about 1 agent hour | 0.25 day |
| Track B, findings: about 540 (about 7.5 pieces of advice an item, 24 items, 3 arms) graded by a Claude agent and Gemini 3.1 Pro, one call a finding for all criteria (about 6,000 input and 600 output tokens) | 0 | **10.4 USD** (5.2 with Batch) | about 4 agent hours | 0.5 day, 1 day with Batch |
| Track B, the third annotator (GPT-6.1-sol): ties (about 30 percent, 160) and the cloud reference's findings in the Claude annotator's place (about 180) | 0 | **6.1 USD** | 0 | with the above |
| Freeze, score, report | 0 | 0 | about 2 role hours | 0.5 day |
| **Both tracks, the default annotators** | **1.1 to 2.7 USD** | **23.8 to 24.3 USD** (16.6 to 17.1 with Gemini on Batch) | about 14 to 16 agent hours | **about 3 to 3.5 days, in parallel** |
| Track A alone, the default annotators | 1.1 to 2.7 USD | 6.5 to 7.0 USD (4.8 to 5.3 with Gemini on Batch) | about 9 to 11 agent hours | about 2.5 days, in parallel |
| Both tracks, all-Claude annotators (three fresh agents; D6 and track B then for B1 and the system only) | 1.1 to 2.7 USD | **0.9 to 1.4 USD** (the cloud reference alone) | about 25 to 30 agent hours | about 3.5 days, in parallel |
| Both tracks, two API annotators (Gemini 3.1 Pro and GPT-6.1-sol, Mistral Large on ties) | 1.1 to 2.7 USD | about 30 USD (about 16 with Batch) | about 8 to 10 agent hours | about 3.5 to 4 days, in parallel |

- **Above 3 USD, asked first** (D-629): every row is above 3 USD except the all-Claude one, which totals 2.0 to
  4.1 USD (the Lambda pass and the cloud reference); the test is asked as one FOR_SECKIN entry (the Lambda pass,
  the cloud reference and the grading), each figure recomputed from the frozen counts and the built prompts files.
- **Keys:** an API annotator needs Seckin's own key for its provider under standing order 2 (Google for the
  default annotator 2, OpenAI for the third). If a key does not exist, a Claude agent takes that place (any
  family is allowed, D-639), recorded before grading.
- **Effect on v1.0 (D-639 item 1):** built in parallel with the current fixes (D-634 to D-638), never a gate in
  front of them: about 2.5 calendar days of its own, most of it waiting for the passes and the annotators, run
  beside the fixes and the gate attempts. It moves v1.0 only if v1.0 is set to carry its first figures; the
  shared limits are the laptop's one-heavy-job rule (D-629) when its pass is sealed, and agent usage.

## 10. The order

**Under D-644, track A only:**

1. This amended plan, committed.
2. Role N adds T1's fields to the frozen set and builds and freezes P2 (section 3.4). This includes the leakage
   pass and any double-blind extraction (section 5.2a). The output is `FREEZE.json`: the set with P2, the scorer.
3. The power record is recomputed at the frozen headline count and committed.
4. The FOR_SECKIN cost entry (section 9.0); nothing above 3 USD before his yes.
5. The benchmark's pass: B1 and the system on Lambda (launched by the lead, unopened), and the cloud reference
   on its subset (role N's route), the same items for all three.
6. The opening line, then D1 to D5 in Python, then the report of aggregates per arm, per process and per round
   count.

Track B and D6 wait (D-644 items 2 and 5). The steps below are the plan as of 77e90c1e, kept for when a separate
decision opens them.

1. This plan and the adapted rubric (`RUBRIC_SHIMMER_v0.md`, private), committed; the rubric reviewed by another
family (check 2) and Seckin's standards set. 2. The role session adds T1's fields to the frozen set, builds track
B's claim and passage pairs, and has them labelled double-blind (reference judgements); both frozen
(`FREEZE.json`: the set, the rubric, the pairs and labels, the scorer). 3. The power record committed. 4. The
benchmark's pass: B1 and the system on Lambda (launched by the lead unopened), the cloud reference on its subset
(role N's route), the same items for all three. 5. Track A's grading (D6) and track B's grading of every finding,
with check 1. 6. The opening line, then the score, then the report of aggregates, track A and track B apart,
with the record layer's state beside track B.
