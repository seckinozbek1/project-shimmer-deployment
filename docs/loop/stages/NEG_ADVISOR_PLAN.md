# The negotiation advisor: the pre-registered plan and bar (D-605, #262)

Written on 13 November 2026, 14:27 +0300 (from `date`), by lane neg-advisor, before any item exists,
before any source text is opened by the builder, and before any arm runs. Every threshold, label rule
and metric below is fixed here. A change after an item exists is a new commit that says what changed
and why, and is read as a change after sight of nothing but this plan: the builder never sees the
items, their labels or any per-item result (section 9).

Development, exposed. Not a gate benchmark. No published benchmark or metric exists for this task,
so every metric is "our metric, no published benchmark" on every page that shows it.

Amended on 13 November 2026, 14:51 +0300, by D-606 (the cloud reference on a seeded subset, the whole
test 6 to 12 USD), still before any item exists.

Amended a third time on 13 November 2026, 16:02 +0300, after the third checker's round: the cloud
reference's route as the code reads it (section 9, step 4: open-role-c, role C's flags, the drop folder
and append-handed-back) and its runner, the negotiation form of `cloud_reference_b1.py`.

Amended again on 13 November 2026, 15:42 +0300, after the second checker's round: the judge's and the
validator's models refused at score time unless they are Phi-4, the validator's prompts and digest bound,
the cloud arm started by the role session (section 9, step 4), and the gate check renumbered 356.

Amended on 13 November 2026, 15:21 +0300 (from `date`), by lane neg-advisor-2 after a checker's round,
still before any item exists: the judge and the validator load Phi-4 (section 6.3), the cloud subset's
draw is in the scorer (5.2), the bar's line 1 is one rule and line 4 is enforced (7.1), the
configuration binds the judge's prompts, the cloud subset and every checkpoint digest (7.4), who runs what
(9), the licence rule (10) and the per-field provenance table (4.5). What changed and why is in the
commit; nothing was seen.

**Expected to be indicator-only.** At about 40 items, 30 of them in the headline part, the one primary
claim has an estimated power of about **0.33** (section 7.3, at an intra-item correlation of 0.2), far
below the 0.8 the rule needs. So every figure
is expected to be reported as an indicator, with its interval, and no claim. The simulation at the
freeze decides, by the rule written in section 7.3, and the report says the same.

It runs only when the measurement has no machine waiting (D-S102 item 1), and it gives way to the gate.

## 1. What is measured

An advisor for one party in a multi-round negotiation. Given the round-k text, the positions on record
up to round k and a persona (a party or a coalition, with its stated positions as its mandate), the
advisor says, for each proposal on the table:

- whether it conflicts with the persona's mandate;
- whether to accept, reject or counter it, and for a counter, the middle-ground wording, with its
  reasons cited;
- which cross-issue trades to offer (a give for a get);
- whom to approach;

and, for the excerpt as a whole:

- a per-article alignment map: which parties align with the persona, which oppose it;
- each article's state: closed, dropped, still bracketed, new, or bound by an earlier concession.

## 2. The parts

| Part | Items | Source | How labelled | Licence |
|---|---|---|---|---|
| **P, primary: public multilateral** | 30 (INB 20, INC 10) | The WHO pandemic agreement's Intergovernmental Negotiating Body (apps.who.int/gb/inb: the bureau's texts and the negotiating texts of each session) and the plastics treaty's INC-5.1 and INC-5.2 (UNEP: the chair's texts and the compilation texts). Positions from the Earth Negotiations Bulletin (IISD) and the parties' own published submissions. BBNJ (un.org/bbnj, the drafts with track changes) is held in reserve, used only if P falls short of 30 | From the real round k+1 by deterministic diff, and from the positions on record (section 4) | WHO texts CC BY-NC-SA 3.0 IGO; ENB CC BY-NC-SA 4.0; UNEP and party submissions: terms to be confirmed by the role session before use (section 10) |
| **H, secondary: bilateral host agreement, synthetic** | 5 | Rounds reconstructed between a public start text (a model host country agreement, for example the one the UNFCCC publishes) and a public signed text (for example the COP31 host country agreement on unfccc.int). A signed agreement publishes no rounds (Seckin 13:42), so the intermediate rounds are written by the role session's author agent and marked **synthetic** on every row | From the reconstruction's own declared next round, by the same diff | UNFCCC terms to be confirmed |
| **G, small: LLM-Deliberation games** | 6 | The MIT games (github.com/S-Abdelnabi/LLM-Deliberation): multi-party, multi-issue, each party a private score table | By construction, from the score tables (section 4.4) | MIT |

**The headline is P alone.** H and G are reported apart, each with its n, never pooled into P: H is
synthetic and has 5 items, and G asks a different question (a deal, scored by construction).

If P keeps fewer than 30 items after the leakage pass and the licence check, BBNJ fills the places;
if it still falls short, the shortfall is recorded and nothing else takes the places.

## 3. The item

One item is one (process, round k, persona). It holds:

1. **The round-k excerpt:** 3 to 6 articles of the round-k text, chosen by structure, never by
   content (section 3.1).
2. **The two indexes:** the article ids and titles of the whole round-k text and of round k-1 (none
   for round 1), so that a dropped article can be named.
3. **The positions on record up to round k:** each a short verbatim quote with its source (an ENB
   paragraph or a submission's paragraph), its party, its round, and the article it was mapped to
   (section 4.2). Each has a stable id, `POS-<n>`.
4. **The persona:** one party or one coalition, its id, and its mandate: the positions on record that
   are its own, listed by id, with each one the role session marks a red line (only where the record
   itself calls it one: "cannot accept", "red line", "non-negotiable", read by the role session, never
   by a keyword table in code).
5. **The trades on record:** each earlier conditional offer of the persona that the record states
   ("X if Y"), as `{id, give, get, round}` over proposal ids, where both sides are still in the
   excerpt.
6. **The parties:** every party and coalition named in the excerpt's positions, each marked single
   or coalition.
7. **The proposals:** each bracketed alternative of an article (`[option A] [option B]`, "Alt",
   "Option 1"), or the whole article where it carries no alternative but is not agreed, each with a
   stable id `P-<article>-<n>`. A closed article carries no proposal.
8. **Passage ids:** every paragraph of the excerpt carries `PAR-<n>`, so a reason can cite it.

**Round history 1 to 5:** k-1 earlier rounds lie behind the item, from 0 to 4; the item's round count
is k. Every item states it, and every figure is also reported per round count.

### 3.1 Choosing the excerpt, by structure

Per (process, round k), the role session lists the articles of round k that are in round k+1 too or
were removed by it. It takes, in this order, until the excerpt holds 6 articles or the token budget
is reached:

1. every article bracketed in round k whose text changes in round k+1, sorted by the SHA-256 of
   `20261113-negadv:<process>:<k>:<article id>`;
2. one closed article (so that respecting a closed article can be checked), by the same sort;
3. one article new in round k, by the same sort, if there is one.

The excerpt holds at least 3 articles; a (process, round) with fewer is not used. The **token
budget**: the whole B1 prompt (instructions, excerpt, index, positions, persona) at most 24,000
tokens by Qwen2.5-7B-Instruct's own tokenizer, leaving the output allowance (section 5) inside its
32,768 positions. An article that would pass the budget is skipped and the next is taken.

### 3.2 Configurations, computed, never declared

Each item's configuration is computed by the scorer from the item and its key, in this order, the
first that holds:

1. **bilateral:** exactly two parties in the item;
2. **issue-based shifting alignment:** three or more parties, and two articles whose sets of parties
   aligned with the persona (in the key's alignment map) have a Jaccard below 0.5;
3. **group against group:** the persona is a coalition and at least one other party in the item is a
   coalition;
4. **one against a group:** the persona is a single party and at least one other party is a
   coalition;
5. **everyone with everyone:** anything else.

Every figure is reported per configuration and per round count, with its n; a cell with fewer than 5
items is given as **its count alone**, with no figure and no interval (section 9: a figure on so few items
comes too close to a per-item result). A comparison (a claim's test) on fewer than 5 items is likewise its
count alone.

## 4. The labels (the key)

Written by the role session with the items, before any arm runs. The builder never reads them.

### 4.1 From the next round, by deterministic diff

Text is normalised the same way everywhere: brackets and option markers removed, case folded, every
run of whitespace one space, curly quotes straight. Word 5-grams are taken on the normalised text.
The article of round k is matched to round k+1 by its id, or by the role session's renumbering map
where the text renumbers (recorded with the item; the validator does not check it, the checker's sample
does, by labelling each sampled proposal's fate again from the texts, section 4.3).

- **A proposal's fate in round k+1** (`fate`): `open` when the proposal's text still stands inside
  brackets in round k+1; otherwise, with s the share of the proposal's 5-grams present in the matched
  round-k+1 article, `kept` when s is at least 0.8, `changed` when s is at least 0.2 and below 0.8,
  `removed` when s is below 0.2 or the article is gone. A proposal under 5 words is matched by
  normalised substring instead: `kept` if present, else `removed`.
- **An article's state in round k** (`state`), from rounds k-1 and k and the record, first that holds:
  `binding` when the persona's own position on record accepted this article's round-k wording in an
  earlier round (an acceptance quote mapped to it, section 4.2); `dropped` when it is in round k-1's
  index and not in round k (listed by id only); `new` when it is not in round k-1 (never for round 1);
  `bracketed` when it carries brackets or an unagreed proposal; `closed` otherwise (agreed text,
  including "agreed ad referendum" where the record marks it). For round 1, `new` does not apply and
  the first round's articles are `bracketed` or `closed`.
- **Whether the persona's position advanced** (`advanced`), per proposal: `advanced` when the persona
  supports it on record and its fate is `kept`, or opposes it and its fate is `removed`;
  `not_advanced` for the two opposite cases; undetermined otherwise (excluded from that figure).

### 4.2 From the positions on record

- **Conflict** (`conflict`), per proposal: `conflict` when a persona position mapped to the proposal's
  article opposes its wording; `no_conflict` when a persona position mapped to it supports it or is
  satisfied by it; `not_stated` when the persona has no position on record on that article.
- **Alignment** (`alignment`), per (article, party other than the persona): `aligned` when the party's
  positions on the article agree with the persona's; `opposed` when they disagree; `not_stated` when
  either has none.
- **Approach targets:** the parties `aligned` with the persona on at least one article of the item and
  `opposed` on none.

**The position-to-article mapping is model-made** (D-605 risk). The role session's mapping model
reads each position quote and names the article and the stance (support, oppose, accept). A **second
model of another family** then validates every mapping, blind to the first's reasons; a mapping the
two disagree on goes to a fresh Claude labeller, and one all three disagree on drops the position,
counted. Agreement (Cohen's kappa over the triple (article, proposal, stance), one unit everywhere: the
plan, the brief and `validate-read`) is reported over every position of the build files (a position
with no answer row refuses the read; one whose answer does not parse counts as a disagreement), with the
validate prompts file's digest and the pass's model, which must be Phi-4; `score` binds both (the
configuration's `validate_prompts_sha256` and its `validate` checkpoint digest); below 0.60 the whole mapping
is revised once and measured again, and still below 0.60 the part is reported as unvalidated, every
figure resting on it an indicator for that reason too.

### 4.3 The checker's sample

An independent checker, a fresh Claude agent that neither built nor labelled, reads a seeded 20
percent of the items (at least 8; SHA-256 order of `20261113-negadv-sample:<item id>`) and labels
their fate, state, conflict, alignment and **red line** (per persona position: `red_line` or
`not_red_line`; the sheet shows no red-line mark) again from the texts. The per-field agreement with the
key is reported. A field whose kappa is below 0.60 is reported as such beside every figure resting on it.

### 4.4 The games, by construction

For a game item the persona is one game party, and the advisor proposes one deal (one option per
issue) and its trades. From the game's score tables, by Python:

- **above threshold:** the deal's score for the persona is at or above its own minimum;
- **feasible:** the deal scores at or above threshold for at least the number of parties the game
  requires, its veto parties included;
- **score up:** the deal's score for the persona is above its score for the round's last deal on
  record;
- **Pareto:** no deal in the game's whole option space (enumerated) scores at least as high for every
  party and higher for one;
- **good trade:** a trade whose give is an issue of lower weight than its get in the persona's table.

### 4.5 Where each field comes from

| Field | Made by | Validated by |
|---|---|---|
| excerpt (which articles) | deterministic: the seeded order of section 3.1 over the role session's list of round-k articles that change in round k+1 | the token budget refused in `build` |
| proposals (`P-<article>-<n>`) | deterministic: one per top-level bracket span, or the whole unagreed article | none needed |
| `agreed` mark of an article | role-session judgement from the record ("agreed", "agreed ad referendum") | checker's sample (state) |
| renumbering map | role-session judgement | checker's sample (fate) |
| position quotes and their sources | role session, verbatim | the leakage pass reads them; SOURCE.md names each |
| position's article, proposal and stance (the mapping) | **model-made**, the mapper (Claude) | validator of another family (Phi-4), then a fresh Claude labeller on disagreements; kappa over (article, proposal, stance) |
| red-line marks | role-session judgement, only where the record says so | checker's sample (`red_line`) |
| party kind (single or coalition) | role-session judgement | none (stated as a limit) |
| `post_cutoff`, `synthetic` | role-session judgement from the model card; declared for H | none (stated) |
| `fate` | deterministic: 5-gram shares against round k+1 (4.1) | checker's sample (fate) |
| `state` | deterministic from the two indexes, the `agreed` mark and the mapping (4.1) | checker's sample (state) |
| `binding` (a state) | deterministic from a persona `accept` position of an earlier round, so it rests on the model-made mapping | mapping validation; checker's sample (state) |
| `conflict` | deterministic from the mapping (4.2), so it rests on the model-made mapping | mapping validation; checker's sample (conflict) |
| `alignment` | deterministic from the mapping (4.2) | mapping validation; checker's sample (alignment) |
| approach targets | deterministic from `alignment` (4.2) | through alignment |
| `advanced` | deterministic from `conflict` and `fate` (4.1) | through both |
| `red_line` (of a proposal) | deterministic: a `conflict` resting on a persona `oppose` position the role session marked a red line | checker's sample (`red_line`) and mapping validation |
| `supported_earlier` | deterministic from the mapping's stances and rounds | mapping validation |
| configuration | deterministic from the parties' kinds and `alignment` (3.2) | through both |
| game labels | deterministic from the game's own score tables (4.4) | none needed |
| cloud subset | deterministic seeded draw (5.2) | its SHA-256 in the freeze and the configuration |

## 5. The arms

The same frozen items go to every arm, in one question form, with one reply schema (section 5.1) and
the same output allowance, **2,048 tokens**.

1. **B1.** The bare Qwen2.5-7B-Instruct (the base checkpoint the gate's B1 runs, under its frozen
   decoding policy), one prompt per item through its own chat template, on the replay pass. The form
   is committed in `benchmark/baselines/` before any reply.
2. **The system: the advisor form.** It is **not a shipped pipeline agent**: no advisor role exists
   in the pipeline today, and the report says so. It is the system's own pieces composed on the
   replay pass, at one frozen commit:
   - the advice, from the registry's `local_producer` model (Qwen2.5-7B-Instruct with the checkpoint
     the frozen configuration names), on B1's prompt and allowance;
   - an **audit of the advice by the other family**, the registry's `local_auditor` model as the
     system resolves it for VERIFIER (`unsloth/Phi-3.5-mini-instruct-bnb-4bit`, the active auditor of
     `config/local_models.json`, when this was written): one narrow call per piece of advice, asking whether
     the reasons it cites support it, answered `supported`, `unsupported` or `cannot tell`;
   - **Python's checks** (section 6.2), the same functions the scorer runs;
   - a piece of advice the audit calls `unsupported`, or a check refuses, is **withheld** and counts
     as `no_answer` in the figures it would enter. Its **audit trail** (the advice, the audit's
     answer, each check's outcome) is kept per piece of advice and reported as counts by stage: given,
     audited supported, withheld by the audit, withheld by each check.
3. **The cloud reference, on the cloud subset only** (D-606, section 5.2), started by the role session
   (section 9, step 4) through the role C runner's negotiation form (`cloud_reference_b1.py run-negotiation`). The
   model the lead names (section 11 shows the cost for the cheapest suitable one and for `claude-opus-4-8`),
   read live, B1's prompts byte for byte, for the subset's items alone. A paid run, asked first: it starts
   only after Seckin's "evet" to a FOR_SECKIN entry naming the run, its prompt count and its cost
   recomputed from the frozen counts (D-S106).

### 5.2 The cloud subset (D-606)

**Size, fixed now: 20 items** of the about 41, so the whole test stays inside 6 to 12 USD (section 11
shows the arithmetic). **Drawn by the scorer from the frozen set, seeded and stratified:**

1. A stratum is one (part, configuration, round count), named `<part>|<configuration>|<round>`; game
   items form one stratum per round count, with the configuration `game`.
2. The 20 places are shared among the strata in proportion to their sizes (quota = 20 x stratum size /
   items): each stratum takes the whole part of its quota, and the places left go one each to the
   largest remainders (ties broken by the stratum's name in sort order).
3. Then at least one place for each part that has an item: a part left with none takes one, for its
   largest stratum (ties by name), from the stratum whose places exceed its quota most (ties by name),
   among the parts that keep at least one place after.
4. Within a stratum, items are taken in the order of the SHA-256 of `20261113-negadv-cloud:<item id>`.
   With 20 or fewer items in the set, every item is taken.

The draw reads only the part, the configuration and the round count, never a label or a result. It is
`tools/score_neg_advisor.py`'s `cloud_subset`, run by `freeze`, which writes `cloud_subset.json` in the
set folder and names its SHA-256 in `FREEZE.json`, before any arm runs; the same SHA-256 is in the
configuration. The cloud reference's prompts file is built from the subset alone
(`neg_advisor.py build --form advice --groups b1 --subset <set>/cloud_subset.json`), each prompt B1's byte
for byte, and records the subset's SHA-256. `score` refuses when the subset on disk is not the freeze's
and the configuration's, when it is not the draw made again from the frozen keys, or when the cloud
answers are not of exactly the subset's items. **Reporting:** every cloud figure is on the subset only, and beside it B1's and the
system's figures **on the same subset**, next to their full-set figures. A2 (system against the cloud
reference) is computed on the subset's headline items alone; it was already an indicator and stays one.

### 5.1 The reply schema

One JSON object: `proposals` (per proposal: `id`, `conflict`, `stance` of `accept`, `reject` or
`counter`, `wording` for a counter, `reasons` as a list of cited ids, `PAR-*` or `POS-*`), `trades`
(each `{give, get}` of proposal ids), `approach` (party ids), `alignment` (per article: `aligned` and
`opposed` party ids), `state` (per article id, one of the five states). For a game item: `deal` (per
issue one option) and `trades` (issue ids). A reply that does not parse is `no_answer` on every row of
its item. An unknown id is ignored and counted.

## 6. The metrics, defined exactly

Every figure is computed per arm on the same rows. `no_answer` (a missing row, a reply that does not
parse, a field outside its declared values, a withheld piece of advice) is never in the key, so it is
always a miss for the true class.

### 6.1 Figures against the key

| Id | Figure | Rows | Definition |
|---|---|---|---|
| M1 | **Conflict Macro-F1** (primary) | proposals | Macro-F1 over the key's classes of `conflict`, `no_conflict`, `not_stated` |
| M2 | Alignment Macro-F1 | (article, party) cells | Macro-F1 over the key's classes of `aligned`, `opposed`, `not_stated`; a cell the reply omits is `not_stated` predicted (the reply lists only aligned and opposed) |
| M3 | Article-state Macro-F1 | articles | Macro-F1 over the key's classes of the five states |
| M4 | Stance and outcome agreement | proposals with fate `kept`, `changed` or `removed` | share where the stance is `accept` and the fate `kept`, `counter` and `changed`, or `reject` and `removed`. **One real draw of what the parties did, not a measure of good advice;** an indicator always |
| M5 | Mandate-consistent stance | proposals whose key `conflict` is `conflict` or `no_conflict` | share where the stance is `accept` on a `no_conflict` proposal, or `reject` or `counter` on a `conflict` one; beside it, the same share on the rows whose `advanced` is `advanced` and on those whose `advanced` is `not_advanced`, apart |
| M6 | Counter closeness | counters on proposals whose fate is `changed` | share of counters whose 5-gram Jaccard with the matched round-k+1 article is above the round-k proposal's own Jaccard with it (the counter moved toward what was agreed) |
| M7 | Approach precision and recall | items | over the parties approached, the share in the key's approach targets; over the targets, the share approached; averaged over items |

### 6.2 Python's checks, per piece of advice

Run alike on every arm as scoring, against the key. Inside the system arm, as its withholding, they
**never read the key**: there a check reads the reply's own `state` and `conflict` fields and the
item (its ids, its red-line marks, its trades on record) in place of the key's, and C-earlier, which
needs the key's stances, does not run.

- **C-cite:** every cited id is a `PAR-*` or `POS-*` of the item;
- **C-reason:** a `reject` or `counter` cites at least one id;
- **C-closed:** no `reject` or `counter` on a proposal of an article whose key state is `closed` or
  `binding`;
- **C-mandate:** no `accept` of a proposal whose key `conflict` rests on a red-line position, unless a
  trade of the reply names it as its give;
- **C-earlier:** no `reject` of a proposal the persona's own earlier position supports on record,
  unless a reason cites a later persona position;
- **C-trade:** a trade's give and get are proposals of the item and differ; each trade on record still
  open is either offered again or cited in a reason.

**M8, the check pass rate:** a piece of advice is one proposal entry of a reply; M8 is the share of
pieces passing C-cite, C-reason, C-closed, C-mandate and C-earlier, and each check's own pass rate.
C-trade is read per trade (the share of trades valid) and per trade on record (the share carried), and
reported beside M8, not inside it. C-reason also needs a counter to carry its wording. For the system, withholding is by construction, so its M8 on what it kept is near one;
M8 is reported on what each arm **gave** before withholding as well as on what it kept, and the
system's kept figure is never compared with another arm's.

### 6.3 Middle-ground wording, judged blind

Each counter on a proposal whose fate is `changed` or `kept` is graded by **Phi-4**
(`unsloth/phi-4-bnb-4bit`, JUDGE's registry `model`, already in the sealed assets) on the replay pass,
blind: it sees the round-k proposal, the persona's mandate quotes, the counter wording and the round-k+1
wording, with no arm, model mark or citation id (every `PAR-`, `POS-` and `P-` id is replaced), under an
opaque entry id, in one shuffled order (seed 20261113), and gives **2** (the counter keeps the persona's
mandate and lies between the proposal and what was agreed, or matches what was agreed), **1** (it keeps
the mandate but does not move toward what was agreed) or **0** (it breaks the mandate or is not
usable wording). **M9:** the mean grade over every counter an arm gave on those proposals, a counter the
system withheld scoring 0, and the share graded 2. A withheld counter counts in M9 only where the judge
would have graded it (a counter with wording, on a proposal whose fate is `changed` or `kept`): one rule,
`neg_advisor.judged`, for the judge's entries and for M9's withheld counters.

- **How Phi-4 is loaded.** JUDGE's registry `local.model` is null, so `bare_model.resolve_reader` alone
  would give the active auditor of `config/local_models.json`, Phi-3.5, VERIFIER's model. The judge and
  the validator groups of `neg_advisor_prompt.json` therefore declare `model`; `neg_advisor.reader_of`
  loads it only when it is the registry's own `model` of JUDGE on JUDGE's local backend, and refuses
  otherwise. No registry entry changed. Check 356 resolves both groups through the real registry and
  proves the model is Phi-4 and differs from the system auditor's, with the form as first written (no
  declared model) as its neutralisation. At score time the judge's and the validator's recorded model ids
  must be that registry model (`MODEL_BOUND_GROUPS`), since their checkpoint digests come from the same
  passes and cannot catch a Phi-3.5 pass on their own.
- **The family limit, stated beside M9:** Phi-4 is of the same family as the system's auditor
  (Phi-3.5), so it may favour wording that family has already shaped. It is of a different family from
  Qwen (B1 and the system's advice) and from Claude (the cloud reference), so neither of those is
  graded by its own family.
- **The checker's sample:** a fresh Claude agent, neither builder nor labeller, grades a seeded 25
  percent of the counters (at least 10) by the same rubric, blind the same way. Cohen's kappa with the
  judge is reported (`grade-read` writes `grade_agreement.json` with the judge answers' prompts digest);
  below 0.60, or with no agreement file of these judge answers, `score` reports M9 as **not validated**. A non-Phi judge is a recorded
  option for a later opening only, never a change inside one.

### 6.4 The games

**G1** the share of deals both above threshold and feasible; **G2** the share Pareto; **G3** the
share of trades that are good trades; **G4** the share with score up. Reported on the 6 game items,
with n, no interval.

### 6.5 Intervals and tests

The same machinery as the negotiation measurement, reused from `tools/score_negotiation.py`: the BCa
cluster bootstrap over items (seed 20261113; exact over every distinct resample below 10,000), the
jackknife over items, and the cluster permutation test of each paired difference. A resample whose
figure is undefined (a Macro-F1 with one key class) is left out and its probability mass reported.

## 7. Bar, claims and power

### 7.1 The bar, written now

The advisor **clears the bar** on the headline part P when all of these hold:

1. **One rule, for a claim and an indicator alike** (the gate's bar (a)): A1's paired difference, M1 for
   the system less B1's, is at least **10 points**, AND its BCa lower bound (at A1's level, one-sided
   0.05 / 2^k) is **above zero**;
2. the system's M8 on what it **gave** is not below B1's by more than 5 points (the audit and the
   checks are not hiding a worse model);
3. the system's withholding rate (advice withheld over advice given) is at most **30 percent**, so
   the system answers;
4. every figure is computed on a key whose mapping validation (section 4.2) and checker's sample
   (section 4.3) are at or above kappa 0.60, or the bar is reported as **not assessable**. `score` reads
   the set folder's `mapping_validation.json` (its latest round's kappa) and `checker_agreement.json`
   (every field, `red_line` included); a kappa below 0.60, a missing field or a missing file reads as not
   assessable.

Below that, the advisor does not clear the bar, and the report says which line failed. The bar is a
development bar; clearing it claims nothing outside these items.

### 7.2 The claims

| Claim | Figure | Comparison | Status |
|---|---|---|---|
| A1 | M1, conflict Macro-F1 | system against B1 | the one primary claim, one-sided at 0.05 / 2^k, if its power is 0.8 or more by the rule below; else an indicator |
| A2 | M1 | system against the cloud reference, on the cloud subset's P items | indicator |
| A3 | M2, M3 | system against B1 | indicators |
| A4 | M9 | system against B1 | indicator (one judge family, section 6.3) |
| A5 | M4, M5, M6, M7 | each pair of arms | indicators, never claims (M4 and M5 rest on one real draw) |

What shows a claim, all at once: its figure defined; the BCa lower bound of the paired difference above
zero; the jackknife lower bound above zero; the permutation p at most the alpha.

### 7.3 The power, sized honestly

A back-of-envelope figure now, for the plan only, and the one figure this plan quotes: about 30 P items
with about 5 proposals each, 150 rows; at an intra-item correlation of 0.2 the design effect is 1.8,
about 83 effective rows. For a true 10-point gap in a per-row accuracy near 0.65 with a per-row
difference standard deviation near 0.6, the standard error is about 0.066, z about 1.5, and the
one-sided power at 0.025 about **0.33** (about 0.2 at a correlation of 0.5). Macro-F1 is noisier than
accuracy, so the real power is lower.

**The rule, written now:** A1 is a claim only if its power, simulated at the frozen P counts (items
and proposals per item, the key's class shares) with 1,000 or more sets at intra-item correlations
0.2 and 0.5, is 0.8 or more at **both**. Each simulated set is tested by the scorer's own `test_claim`
with 500 bootstrap and permutation draws (fewer than the reading's 10,000, for time; stated in the record),
at the **alpha of the opening it is used for**: 0.025 for opening 1, 0.0125 for opening 2. The
simulation is `tools/score_neg_advisor.py power --k <k>`, its record committed before the opening as
`docs/loop/stages/NEG_ADVISOR_POWER.json` (the set's SHA-256, the counts, the opening k and its alpha,
the sets, the assumptions, the code's SHA-256); `score` refuses a record whose k and alpha are not the
opening's. Opening 2 therefore commits a new record at 0.0125 before its opening line. Assumptions: agreement with
the key system 0.70, B1 0.60, cloud 0.75; `no_answer` system 0.10 (its withholding), B1 0.05, cloud
0.02; all guesses, stated so. Expected: indicator-only.

### 7.4 Openings

At most two, in `docs/loop/HELDOUT_OPENINGS.md`, in the form
`neg-advisor opening k=<k> set=<set SHA-256> config=<configuration SHA-256>`, written and committed
by the lead before any result is read; the scorer refuses without it. The configuration (a JSON file of
digests and ids only, written by the role session) holds every field of `CONFIG_FIELDS`: the commit, the
B1, system and cloud prompts files' digests, the cloud model id read live, the judge's prompts file's
digest, the cloud subset's SHA-256, the checkpoint digests of the b1, system_advice, system_audit and
judge groups (each as the pass recorded it), the power record's digest, and every model id. `score`
refuses when any is missing, when an arm's answers are not of its prompts file, when the judge's answers
are not of the judge prompts named, or when a group's loaded checkpoint digest is not the configuration's.
Opening 2 only for an infrastructure failure read from the runs' own records before any score is seen
(D-451), the whole set again on the same models, prompts and subset, with its own power record (7.3).

## 8. Separation, leakage and contamination

- **Apart from the gate set and from all tuning.** No item comes from a gate set, a gate set's
  documents or any tuning material, and nothing is tuned on the items, ever.
- **The leakage pass** runs through the existing freeze machinery (`tools/freeze_negotiation_set.py`:
  its corpus reader, its 5-gram index and its bge-m3 encoder, in float32, on the laptop's CPU or an
  idle GPU under D-399), with its thresholds unchanged: a passage of 20 words or more is a
  near-duplicate at a 5-gram Jaccard of 0.5 or a cosine of 0.9, and a same source by URL or file stem.
  The corpora are the committed `docs/loop/stages/NEGOTIATION_CORPORA.txt` list, the negotiation
  measurement's own held-out set once frozen, and the gate sets' documents. An item over a threshold
  is replaced and checked again. Run by the role session, which writes `FREEZE.json` in its own folder
  and hands back counts only.
- **Contamination.** The INB and INC texts and ENB are public, so they may be in the training data of
  Qwen2.5 and of the cloud reference, which knows outcomes after Qwen2.5's cutoff too. Each item
  records whether its round k+1 was published after the base model's training cutoff as its model
  card states it; every figure is also given for the items after the cutoff. That limit stands beside
  every P figure, and favours the cloud reference most.

## 9. Who sees what

- **The builder** (this lane, the lead and every agent the lead starts) never opens an item, a label,
  a source text chosen for an item, or any per-item result. It writes this plan, the role brief, the
  scorer and the forms, all proven on fixtures that are not items.
- **Who runs what (the lead's ruling, 13 November).** The role session runs `build`, the answers, the
  judge's prompts, the grading and `score`, and hands back aggregates only. Every model pass (the
  validator; B1, the system's advice and its audit; the judge) is a **sealed** bundle the role session
  prepares from its own folder (SEALED-RUN-A: `--exposure sealed`, its own test manifest, prepared outside
  the repository), launched by the lead without opening it, the lead seeing counts and timings only. Step
  by step:
  1. The role session builds, validates, samples and freezes (sections 4 and 8); `freeze` also writes
     `cloud_subset.json`. It hands back the counts (brief section 9).
  2. The role session runs `power --k 1` in its folder and hands the record (counts, class shares, the
     simulated power; no item) to the lead, who commits it as `NEG_ADVISOR_POWER.json`.
  3. The role session builds the prompts files in its folder: B1 and the system (`--groups
     b1,system_advice`) and the cloud reference's (`--groups b1 --subset`).
  4. The role session seals the rented passes from its folder as sealed bundles and gives the lead only
     each bundle's path, its seal's SHA-256, its test manifest's SHA-256 and its prompt count. The lead
     asks Seckin's "evet" where a run is paid (section 11), launches each with the bound wrapper and
     `--frozen-tag`, its run folder inside the role session's folder, and reads counts and timings only.
     The cloud reference is role C's form of the role C runner (`cloud_reference_b1.py
     run-negotiation`), started by the role session on its own `prompts_cloud.json`, never by the lead,
     and only after Seckin's "evet", which the lead asks for and relays. The lead reads its count and
     cost only and never opens the prompts or the replies:
     4.1. **The lead opens role C's intent:** `py -3.12 -X utf8 benchmark/baselines/cloud_reference_b1.py
          open-role-c --cap-usd <cap> --seckin-approved "<heading time of the FOR_SECKIN entry>"`, after
          Seckin's "evet" to that entry (D-S106). Under the spend store's lock it holds the cap as
          running and writes an intent line of kind `cloud-reference-b1-role-c`, and prints the run id
          (`role-c-<12 hex>`) and the budget figure (the intent's own cap). The kind need not differ for
          the advisor: `append-handed-back` admits only run ids of an intent of that kind, and only the
          close line the form writes names `cloud-reference-neg-advisor-v1`. The lead hands the role
          session the run id, the figure and a copy of the FOR_SECKIN entry with its evet line.
     4.2. **The role session runs the form,** from its own clone (never the main checkout or a worktree
          of it: the form refuses where the lead's spend store is reachable): `SHIMMER_ROLE=C py -3.12 -X
          utf8 benchmark/baselines/cloud_reference_b1.py run-negotiation --prompts
          <RS>/prompts_cloud.json --out <RS>/cloud_run --cap-usd <the figure or less> --credit-usd <the
          credit left> --price-input-per-mtok <row> --price-output-per-mtok <row> --price-source "<page,
          date>" --deprecation-checked "<url>, <YYYY-MM-DD>, not deprecated" --seckin-approved "<heading
          time>" --for-seckin <RS>/for_seckin_copy.md --role-c-run-id <run id> --budget-left-usd <the
          figure> --spend-file <RS>/C_negadv_cloud_reference_spend.jsonl`. The replies stay in
          `<RS>/cloud_run/texts.json`; the measurement and the spend file hold counts, tokens and cost
          only.
     4.3. **The lead appends the spend file:** the role session hands back
          `C_negadv_cloud_reference_spend.jsonl` alone; the lead moves it into
          `docs/loop/private/cloud_reference_handed_back/` of the main checkout and runs `py -3.12 -X
          utf8 tools/loop/cloud_reference_spend.py append-handed-back
          <USER_HOME>/local/shimmer-deployment/docs/loop/private/cloud_reference_handed_back/C_negadv_cloud_reference_spend.jsonl` (the file by its absolute path in the main
          checkout: a relative path resolves against the working folder, a worktree's is refused). Until it
          is appended the guard (`cloud_reference_spend.lead_may_spend`) refuses the lead's next paid run
          and every instance launch; a line whose run id names no intent the lead opened, or whose spend
          passes the intent's cap, is refused (the second flagged at the top of FOR_SECKIN).
  5. The role session reads the answers (`neg_advisor.py answers`, `texts`), builds the judge's prompts
     (`judge-prompts`), seals the judge's pass as in step 4, reads its answers, and has a fresh checker
     grade the sheet (`grade-sheet`, `grade-read`).
  6. The role session writes the configuration (digests and ids only) and gives the lead its SHA-256 and
     its content; the lead commits the opening line.
  7. The role session runs `score` and hands the lead its printed aggregates: every figure with its
     interval, cells under 5 items as counts alone, the trail and the bar's lines. The per-item rows
     (`--per-item-out`) are written only inside the role session's set folder.
- **The role session** (a separate session, `NEG_ADVISOR_ROLE_BRIEF.md`) fetches the sources, checks
  their terms, builds and labels the items, runs the validator, the checker's sample and the leakage
  pass, freezes the set in its own folder outside the repository, never under `external/`, and hands
  back counts only: items per part, per configuration and per round count; rows per field; class
  shares; kappas; the leakage counts; the set's SHA-256.
- **The scorer** prints aggregates only, a cell under 5 items as its count alone. Its per-item rows are
  written only inside the role session's set folder (`--per-item-out`, refused anywhere else and inside
  the repository). Every file `benchmark/baselines/neg_advisor.py` writes (prompts files, passes,
  answers) is refused inside the repository.
- **Seckin does not label** (D-605 item 6).

## 10. Licences

- WHO INB material: CC BY-NC-SA 3.0 IGO. ENB: CC BY-NC-SA 4.0. Research use is within both; the items
  carry attribution and the licence, and any shared form keeps share-alike and non-commercial terms.
- **Every item carries `licence` and `attribution`** (from its build file; `build` refuses one without
  them), and its `SOURCE.md` is copied into `items/<id>/`, so it is in the frozen set's listing and digest.
- **The cloud provider, the rule.** Sending excerpts of public CC BY-NC-SA material to the cloud provider
  for a non-commercial research evaluation is **processing, not redistribution**: the text goes to a
  service that answers it and is not published or passed on. It is allowed only through the provider's
  API, under its default that API inputs are not used for training, never through a consumer product or
  any setting that shares data for training. A source whose terms forbid that processing, or whose terms
  are unconfirmed, is left out of the cloud subset's prompts or the cloud arm waits, and the hand-back says
  so.
- UN, UNEP and UNFCCC terms, and each party submission's: **unconfirmed.** The role session reads each
  source's terms before using it and records them in the item set's `SOURCES.md`; a source whose terms
  do not allow research use is not used.
- **Nothing is redistributed** (no item, no excerpt, outside the role session's folder and the rented
  machine that runs it) until each source's terms are confirmed for that use and Seckin agrees.
- LLM-Deliberation: MIT; its notice travels with the game items.

## 11. Size, time and cost

**Size:** about 40 items: INB 20, INC 10, synthetic bilateral 5, games 6.

**Cost, the arithmetic (D-606: the whole test about 6 to 12 USD).** Rented: the A10 at 1.29 USD an hour
(the live price of 8 November) times the 1.3 forecast factor, 1.68 USD an hour. Generation at about 25
tokens a second for the 7B model on the A10 (a planning figure, replaced by the measured one), so a
2,048-token reply takes about 82 seconds.

| What | Minutes | USD |
|---|---|---|
| Setup with the asset copy MATCH, one session for every rented form | 15 | 0.42 |
| B1, 41 items, up to 2,048 output tokens each (82 s) | 56 | 1.57 |
| System advice, the same | 56 | 1.57 |
| System audit, about 5 pieces an item, 205 short calls at about 3 s, with Phi-3.5's load | 12 | 0.34 |
| The Phi-4 judge, about 120 counters at about 2 s, with its load | 7 | 0.20 |
| The role session's validator, about 320 positions at about 3 s, its own session with setup | 31 | 0.87 |
| **Rented, all** | **177** | **4.97** |
| If the asset copy is MISSING, the measured 64 minutes of upload (D-332) | +64 | +1.79 |

**The cloud reference on the 20-item subset**, each call at most 24,000 input tokens (the token budget,
section 3.1) and 2,048 output, typical about 12,000 input. Prices read on 13 November 2026, 14:51 +0300,
from https://platform.claude.com/docs/en/about-claude/pricing (per million tokens, input and output):

| Model | Per call, worst | 20 calls, worst | 20 calls, typical |
|---|---|---|---|
| Claude Haiku 5.5 (0.10 and 0.50) | 0.0034 | 0.07 | 0.04 |
| Claude Sonnet 5.5 (2 and 10) | 0.0685 | 1.37 | 0.89 |
| `claude-opus-4-8` (5 and 25; the row of `cloud_reference_prices.json`) | 0.1712 | 3.42 | 2.22 |

**The cheapest suitable model is Claude Sonnet 5.5**, the lead's choice to confirm: Haiku 5.5 is cheaper
still, but a small model is no ceiling for a reference arm, which is what the reference is for. Its row
must be written into `cloud_reference_prices.json` by the lead from the provider's page before a run,
and its id read live.

**The whole test:** rented 4.97 plus Sonnet 5.5's subset 0.89 to 1.37 is **5.9 to 6.3 USD**; with
MISSING, 7.7 to 8.1; with `claude-opus-4-8` in its place, 7.2 to 8.4, or 9.0 to 10.2 with MISSING. Every
case is inside 12 USD. The subset of 20 is not forced by the cloud price at Sonnet 5.5 (the whole set
would add only about 1.4 USD more at worst); it is D-606's rule, and it keeps the Opus case inside the
band too. **Outside the band, stated:** opening 2 (only for an infrastructure failure, about 5 USD more)
and the bge-m3 leakage pass, which runs on the laptop at no provider cost.

The role session, labellers, checkers and judges that are Claude agents are Claude usage, counted in
the usage watch, not provider dollars. **Each paid run asks Seckin first** (D-606, D-S106): the rented
session, the validator's session and the cloud reference each start only after his "evet" to a
FOR_SECKIN entry that names the run, its prompt count and its cost recomputed from the frozen counts and
the built prompts files, not the forecast above.

**Time:** the plan, the brief and the scorer and forms on 13 November; the role session's items by the
morning of 14 November; the arms in one session when the gate has no machine waiting; first findings
by the end of 14 November, if a machine is free. If none is, the findings wait; nothing is dropped
to reach the date.

## 12. The order

1. This plan, committed. 2. The role brief, committed before the role session starts. 3. The scorer
and the forms, with fixture-only proofs in the gate. 4. The role session's items, labels, validation,
checker's sample, leakage pass, freeze and cloud subset; counts handed back. 5. The power record
committed. 6. The prompts files and the sealed bundles (the role session's), the runs (launched by the
lead, counts and timings only). 7. The judge's prompts, its sealed pass and the checker's grading
sample. 8. The configuration (the role session's), the opening line (the lead's), then `score` (the role
session's) and its aggregates handed back (section 9).
