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

### Three-way comparison: Shimmer, the bare model and the cloud model

The bare model is Qwen2.5-7B-Instruct, the same open model Shimmer builds on, asked directly with no Shimmer steps around it.
The cloud model is claude-opus-4-8, a large model run by an outside provider. Written by hand from
docs/RESULTS.md and the decision records (no tool produces this table); the same figures appear in the README,
docs/RESULTS.md and the progress page.

| Measure and items | Shimmer | Bare model | Cloud model | What this row is |
|---|---|---|---|---|
| Negotiation, open point detection: untouched, the same 20 synthetic items (132 proposals) | 0.407 (0.348 to 0.480) | no score: 81 of 132 proposals have no answer piece | 0.381 (0.334 to 0.449) | Untouched items, current code, the same 20 items for all three. The intervals overlap, so the two are about equal; neither is ahead of the other. |
| Negotiation, stance matches fate: same 20 items | 0.330 (0.244 to 0.435) | no score: same reason | 0.295 (0.221 to 0.364) | Same items and code as the row above. The intervals overlap: about equal. |
| Contradictions (ContraDoc): untouched, 8 documents | 0.875 (0.625 to 1.0) | not measured | not measured | No bare or cloud run exists on these untouched items, so there is nothing to put beside the Shimmer figure. |
| Table claims (SciTab): untouched, 15 claims | 0.846 on 13 answered (coverage rule loosened by the project owner after the result was seen) | not measured | not measured | No bare or cloud run exists on these untouched items. |
| Contradictions (ContraDoc): seen, 40-document steering subset, older code | 55.0 percent; does not count: 26 of 40 undecided | 52.5 percent | 90.0 percent | Seen items, code from before the 18 to 19 November fixes; the same 40 documents for all three, but the Shimmer run is void, so this is no comparison. |
| Table claims (SciTab): seen, 78-claim steering subset, older code | 0.190; does not count: every claim undecided | 55.8 | 81.7 | Seen items, the same older code and the same 78 claims; the Shimmer run is void. Figures as recorded in docs/RESULTS.md. |
| Negotiation, conflict detection: seen, development pilot | 0.629 (18 items) | 0.217 (18 items) | 0.648 (14 of the 18 items) | Seen items. The bare figure comes from older saved answers without the Python step, and the cloud figure from a 14-item subset, so the three are not on equal footing. |

- The cloud target moved from at most 5 to at most 10 points below the cloud model on 20 November 2026 (D-842),
  before anyone looked at an untouched item and after every earlier check on seen items had missed 5. The project
  owner's reason: 5 points would be an unfair comparison against a large cloud model.
- "No score" for the bare model means its answers were too incomplete to score under the coverage rule. It does
  not mean that Shimmer did better.
- Rows are not comparable with each other: they differ in items, code version and measure. Compare within a row only.
- The bare and cloud figures are references only.
- The 0.987 on 24 seen pilot items is left out of this table: those are development items, and the fix was made
  with them. See "Seen against untouched" below.

### Seen against untouched

"Seen" items were used to build or tune the system; "untouched" items were not. A figure on seen items is
often higher, because fixes were made with those items in view. So no seen figure counts toward a target.
Each negotiation line below gives the seen figure, the bare and cloud figures where they exist (with the set
and version they ran on), the untouched figure, and the 0.60 mark. Figures are from the decision records and
[docs/RESULTS.md](docs/RESULTS.md).

| Line | Seen, system | Seen, bare model | Seen, cloud model | Untouched, system | Mark |
|---|---|---|---|---|---|
| Conflict | 0.987 (0.964 to 0.998) on the 24 development pilot items, round 2 with the fix, from saved answers; 0.629 on the older 18 seen items (179 proposals), earlier system | 0.217 on the 18 items, from older saved answers without the Python step | 0.648 on 14 of the 18 items | 0.955 on 31 items | 0.60 |
| Open point | 0.473 (0.403 to 0.561) on the 24 items with the adopted setting (round 2 with the fix); 0.538 (0.468 to 0.607) with round 3, which was not adopted | no figure: the scorer refused it, too many answers missing | 0.507 (0.425 to 0.612) on its 14-item subset of the 24, from the answers of the 15 November pilot | 0.393 on 31 items; 0.407 on the cloud's 20 | 0.60 |
| Stance | 0.429 (0.344 to 0.533) on the 24 items, adopted setting; 0.276 on the same answers read with a different scoring switch (open_stance_m4) | no figure: the scorer refused it | 0.396 (0.292 to 0.537) on its 14-item subset of the 24 | 0.299 on 31 items; 0.330 on the cloud's 20 | 0.60 |

- Why the seen figures do not count: the 24 pilot items are development items, and the fix was made and
  chosen with them. The older 18 items were seen in the same way. The untouched items were scored once, with
  the marks written first.
- Fixed answers on the older 18 seen items (179 proposals): giving the same answer to every proposal scores
  0.444 on open point (always "accept" or always "reject"), and on stance 0.480 for always "reject" and 0.318
  for always "accept". They show how far a fixed answer gets on that set; they were not computed on the 24 or
  the 31 items.
- On seen items too, the cloud model is below 0.60 on open point and stance.

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

- A refused extraction on some tables: the step that pulls facts out of a table
  sometimes refuses, and it is not asked again.
- A limit on how long one reasoning step may write.
- Two known faults.
- A larger set of table claims.
- A summary file the system writes when a long session has to be compacted. Planned for beta.

### Switched off in the alpha

Some parts of Shimmer are built or planned but are not used in the alpha. Each line says why, and what happens instead. The scores were measured with these parts off, unless a line says otherwise.

- Institution finder: off by default since 13 November 2026, because its job has no use yet and no other part reads its output. Nothing takes its place. The operator can switch it on for one run. The 54 alpha development items ran with it off.
- Fact-checker: withheld from every run since 19 September 2026, because every item it returned in three test runs was wrong. Nothing takes its place. It stays registered, so it can be switched back on.
- Masking of personal data: built but off. Switching it on needs the operator's approval, and its tests are planned for the beta. Instead, a run marked sensitive is refused. A run starts only if the operator declares it not sensitive, and that choice is logged.
- Table tool: the alpha code still has it switched on, although a test on 38 tables did not meet its 90 percent bar (4 ended incomplete). It is used only for rules that compare table cells. The SciTab score was measured with this code, so it is not proof that the tool works.
- Operator red lines: in the alpha, the operator can give them. They were tried only on practice items, with sample red lines we wrote. Finding red lines inside texts without the operator is planned for the beta. Until then nothing does it.
- Difference check: built but off as shipped, and the pipeline does not call it, so a run does not show these changes. Wiring it into the run needs a re-seal, which comes after the alpha. Its threshold was set on its own small practice set.
- "What if" step in the negotiation game: not in the alpha. It was placed in the beta on 20 November 2026, and the alpha scope was frozen the same day. Nothing takes its place.
- Graph network (GNN): off, because two attempts failed bars written before any figure. Instead, the ontology uses the plain knowledge graph. Any further attempt is for the full release.
- ContraDoc low-confidence rule: not in the headline score. Adding it to the headline is planned for the full release. A separate line, with unsure pairs counted and labelled, is shown beside the headline.
- Speed measurement: not done yet. It is planned for the beta, and no speed claim is made.
- Review desk: no key is needed, but only on this computer. This is a free local trial, and security work comes in the beta. Keyless mode opens every protected route of the server to this computer, not only the desk. Other computers need the token.
- Review desk language: the desk and its guide are in English only in the alpha. A short Turkish guide to a first review already exists ([docs/GUIDE_TR.md](docs/GUIDE_TR.md)).
- Local drafting without a provider: built, but not yet proven end to end. Under Cloud, drafting uses a provider model instead.

Sources, dates and conditions for every figure, and the rules for testing:
[docs/RESULTS.md](docs/RESULTS.md), [docs/LESSONS.md](docs/LESSONS.md). Limits and
privacy: [docs/LIMITATIONS.md](docs/LIMITATIONS.md), [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

## How to start

- Install, hardware and cost: [docs/INSTALL.md](docs/INSTALL.md)
- First review, step by step: [English](docs/GUIDE_EN.md), [Turkish](docs/GUIDE_TR.md); every task: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- The review desk, one plain page for a single review: [docs/DESK_GUIDE.md](docs/DESK_GUIDE.md).
  The review desk was built for v1.0-alpha (the current state of the code, not a release that reached its targets) and was fixed after the alpha freeze, on 22 November 2026. The freeze tag v1.0-alpha-freeze-f and snapshot ce8854a9 stay as they were; the desk fixes are in tags code-2026-11-22-f and code-2026-11-22-g. English only in the alpha. Keyless local mode (the desktop starter's default) opens every protected route of the server, not only the desk, to any program or user on this computer; other computers are refused.
  Keyless for local trial only (loopback); a non-local address needs the token.
- Agents, output files, server routes and settings: [docs/RUNTIME_REFERENCE.md](docs/RUNTIME_REFERENCE.md)
- Contributing: [CLAUDE.md](CLAUDE.md) and the founding design, [genesis.md](genesis.md)

## Citation and licence

Cite with [CITATION.cff](CITATION.cff). MIT licence ([LICENSE](LICENSE)). Version:
[VERSION](VERSION); changes: [CHANGELOG.md](CHANGELOG.md).
