# Project Shimmer

Shimmer reviews documents against rules that a person writes down. It reads the
documents and compares their figures and fields with those rules and with reference
material. It proposes changes, with citations, for a person to accept or reject. It
never edits a source document, and every step leaves a record a reader can inspect.
It also advises on drafts in a negotiation with several rounds.

- Several agents (separate model-driven programs) built on models from different
  families check each other.
- Plain code decides every check that arithmetic or a field can settle. A model is
  asked only when code cannot decide.
- A finding written by a model stays visible and is marked as not checked by code. It
  never becomes a proposed change.
- The institution finder maps the institutions that a document names. It is optional,
  off by default, and under development.

How a review runs and how the agents are governed: [docs/METHOD.md](docs/METHOD.md).

## Current state (alpha, 22 November 2026)

"Alpha" means the code as it is today. It is not a finished release, and it fell
short of its targets. These are first results. The final test set has not been run
yet.

### Scores at a glance

Every measured set, one row each. "Untouched" items were not used to build or tune
the system; "seen" items were. Figures are those of [docs/RESULTS.md](docs/RESULTS.md).

| Measure | Set | Items | Answered | Score |
|---|---|---|---|---|
| Contradictions (ContraDoc), system | untouched | 8 documents | 8 | accuracy 0.875 (range 0.625 to 1.0, chance test p 0.249) |
| Table claims (SciTab), system | untouched | 15 claims | 13 | accuracy 11 of 13 answered = 0.846 (range 0.769 to 1.0, 4 tables, chance test p 0.026); 2 of 15 unanswered (13.3 percent); unanswered counted wrong: 11 of 15 = 0.733; coverage rule loosened by the project owner's decision for this set, after the result was seen |
| Negotiation, conflict, system | untouched | 31 synthetic items, 197 proposals | 192 | 0.955 (range 0.924 to 0.980, p 0.0001) |
| Negotiation, code checks, system | untouched | 31 synthetic items, 197 proposals | 192 | 1.0, with 2.5 percent of pieces dropped |
| Negotiation, open point, system | untouched | 31 synthetic items, 197 proposals | 192 | 0.393 (range 0.342 to 0.452, p 0.753) |
| Negotiation, stance, system | untouched | 31 synthetic items, 197 proposals | 192 | 0.299 (range 0.219 to 0.389, p 0.938) |
| Negotiation, approach, system | untouched | 31 synthetic items | too few | no score: too few answers for the coverage rule |
| Negotiation, open point, cloud model | untouched | 20 synthetic items, 132 proposals | 132 | 0.381 (range 0.334 to 0.449); system on the same items 0.407 (range 0.348 to 0.480) |
| Negotiation, stance, cloud model | untouched | 20 synthetic items, 132 proposals | 132 | 0.295 (range 0.221 to 0.364); system on the same items 0.330 (range 0.244 to 0.435) |
| Negotiation, open point and stance, bare model | untouched | 31 synthetic items, 197 proposals | 77 | no score: more than 5 percent of answers missing (120 of 197) |
| Table claims (SciTab), system | seen | 78 claims, 13 tables | not given here | three-class macro-F1 0.598 (range 0.444 to 0.656, chance p 0.0001) |
| Contradictions (ContraDoc), system | seen | 15 documents | not given here | accuracy 0.533 |
| Negotiation, conflict, earlier system | seen | 18 items, 179 proposals | not given here | three-class macro-F1 0.629 |
| Negotiation, open point and stance, earlier system | seen | 18 items, 179 proposals | not given here | 0.435 and 0.330 |

The coverage rule (at most 5 percent of answers missing) still holds for every
other measurement, ContraDoc included. The project owner loosened it for this one
SciTab set on 22 November 2026, after the result had been seen.

On 21 November we scored the system for the first time on untouched items: items the
project had not used to build or tune it. We did not check what the models saw in
their own original training. ContraDoc and SciTab are public sets. We wrote the
marks before we looked at any score, and we scored each set once.

### The three targets

- **Cloud model.** The system should score at most 10 points below the cloud model.
  The cloud model is claude-opus-4-8, a large model run by an outside provider.
  This target was 5 points until 20
  November. Before we looked at any untouched item, the project owner changed it to 10,
  after every earlier check on items we had already seen had missed 5. His reason: 5
  points would be an unfair comparison against a large cloud model. No result changed
  because of this: every earlier check still fell short of 10. No cloud run exists on
  the untouched ContraDoc and SciTab items, so the target was not read there.
- **Bare model.** The system should score at least 10 points above the bare model.
  The bare model is Qwen2.5-7B-Instruct, the same open model Shimmer builds on, used
  on its own with nothing around it. On negotiation it got no figure, so this target
  could not be read.
- **Negotiation.** Each of the five lines of the negotiation score has its own
  mark. Three of them are 0.60. The table below shows each line.

### Results

A range is where the true score probably lies. The chance test p tells how often luck
alone would give a score this good or better. A high p means luck alone often scores
this well.

| Task | Untouched items | Result |
|---|---|---|
| Finding contradictions in documents (ContraDoc) | 8 documents, 6 groups | accuracy 0.875 (range 0.625 to 1.0); chance test p 0.249 |
| Checking claims about tables (SciTab) | 3 papers, 4 tables, 15 claims | accuracy 0.846 on the 13 answered claims (range 0.769 to 1.0); chance test p 0.026; coverage rule loosened by the project owner, after the result was seen |
| Advising on negotiation drafts | 31 synthetic items, 197 proposals | five lines, below |

**ContraDoc.** The score is accuracy: 7 of the 8 documents were judged right. Two
documents hold a contradiction. The system found 1 of them and raised no false alarm.
Answering "no contradiction" every time would score 0.75 on this set. The chance test
cannot tell 0.875 from luck. The set is small.

**SciTab.** 11 of the 13 answered claims were judged right: accuracy 0.846 (range
0.769 to 1.0, 4 tables, chance test p 0.026). 2 of the 15 claims were left
unanswered (13.3 percent). Counting the unanswered ones as wrong gives 11 of 15 =
0.733. Our coverage rule allows at most 5 percent of answers missing, held back, or
filled in by the scoring code, so it refused this score at first. On 22 November
2026, after seeing the result, the project owner loosened the rule for this set
only; it still holds everywhere else. The set is small. This figure was read after
we fixed a fault in the code that reads the system's answers. The answers did not
change.

**Negotiation.** The 31 items are synthetic: a program wrote them. They are not
taken from real negotiations. A proposal is one bracketed option in an article of a
draft text. Its fate is what happened to it in the next round: still open, kept,
changed, or removed.

| Line | What it asks | Result | Against its mark |
|---|---|---|---|
| Conflict | Does a proposal clash with the position of the party being advised? | 0.955 (range 0.924 to 0.980, p 0.0001) | above 0.60 |
| Code checks | Do the advice pieces satisfy the code's own checks, such as "cited items exist"? | 1.0, with 2.5 percent of pieces dropped (the mark allows at most 10 percent) | at its mark of 1.0 |
| Open point | Is a proposal still open to change, or already settled? | 0.393 (range 0.342 to 0.452, p 0.753) | below 0.60 |
| Stance | Does the advice (accept, counter, reject) match what the parties did next? | 0.299 (range 0.219 to 0.389, p 0.938) | below 0.60 |
| Approach | Whom does the advice say to approach? | no figure, too few answers | refused |

### The cloud model on negotiation

The cloud model answered all 31 items. By a rule fixed in advance to limit cost, its
answers are scored on a set of 20 items (132 proposals). We also scored the system on
those same 20 items, from its saved answers.

| Measure | System (31 items) | System (same 20 items) | Cloud model (20 items) |
|---|---|---|---|
| Open point | 0.393 | 0.407 (range 0.348 to 0.480) | 0.381 (range 0.334 to 0.449) |
| Stance | 0.299 | 0.330 (range 0.244 to 0.435) | 0.295 (range 0.221 to 0.364) |

On the same items the system is slightly higher, but the ranges overlap, so the two
are about equal. On those 20 items the bare model had no answer for 81 of the 132
proposals. Over the whole set it had none for 120 of 197. More than 5 percent were
missing, so it gets no figure. We checked that the answers are really absent, not
misread.

### What the findings show

- **Level with the cloud model on two hard measures.** On open point and stance, on
  20 synthetic items, the system and the cloud model we tested are about equal. Even
  the cloud model we tested is far below 0.60 on them, so the measures are hard. The
  system's open point and stance figures cannot be told from chance, so being level
  tells us little yet. On synthetic items, what the parties did next was chosen by a
  program.
- **Conflict.** On synthetic items Shimmer found clashes well: 0.955. We have no
  baseline for this line yet.
- **Coverage.** Shimmer answered nearly all proposals (192 of 197). The bare model
  left 120 of 197 empty. This is coverage, not accuracy.
- **Test discipline.** The marks were written first, each figure was scored once, and
  a coverage rule refuses a score when too many answers are missing.

The 0.60 mark was set for our own benchmark, with no outside source for a normal level.
Together with the chance test results, that means the target needs to be reconsidered. The beta will make the benchmark
more reasonable, and it will review the chance test.

### Tests of the code

The frozen alpha code ran its own 502 checks. 485 of 502 checks were green, 6 were
skipped, and 11 known failures are carried as known.

### Left for the beta

- A refusal in the table tool: on some tables, a step that pulls out facts refuses
  and is not asked again.
- A limit on how long one reasoning step may write.
- Two known faults.
- A larger set of table claims.

Sources, dates and conditions for every figure, and the rules for testing:
[docs/RESULTS.md](docs/RESULTS.md), [docs/LESSONS.md](docs/LESSONS.md). Limits and
privacy: [docs/LIMITATIONS.md](docs/LIMITATIONS.md), [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

## How to start

- Install, hardware and cost: [docs/INSTALL.md](docs/INSTALL.md)
- First review, step by step: [English](docs/GUIDE_EN.md), [Turkish](docs/GUIDE_TR.md); every task: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- The review desk, one plain page for a single review: [docs/DESK_GUIDE.md](docs/DESK_GUIDE.md).
  Keyless for local trial only (loopback); a non-local address needs the token.
- Agents, output files, server routes and settings: [docs/RUNTIME_REFERENCE.md](docs/RUNTIME_REFERENCE.md)
- Contributing: [CLAUDE.md](CLAUDE.md) and the founding design, [genesis.md](genesis.md)

## Citation and licence

Cite with [CITATION.cff](CITATION.cff). MIT licence ([LICENSE](LICENSE)). Version:
[VERSION](VERSION); changes: [CHANGELOG.md](CHANGELOG.md).
