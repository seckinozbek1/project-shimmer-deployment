# Brief for the role session: the negotiation advisor item set (D-605, #262)

Written on 13 November 2026, 14:30 +0300 (from `date`), by lane neg-advisor, for the lead to hand to a
separate role session. It is self-contained: the role session needs this brief, the plan
(`docs/loop/stages/NEG_ADVISOR_PLAN.md`) and the tools it names, nothing else from the loop. Amended on
13 November 2026, 15:21 +0300, by lane neg-advisor-2 before any item exists: Phi-4 for the validator and
the judge, the licence fields, the token budget in `build`, the cloud subset, the sealed passes and who
runs what (section 6a), and the hand-back's files.

## 0. Who you are and what you never do

You are the role session that builds the held-out item set for the negotiation advisor. The builder
(the lead, lane neg-advisor and every agent the lead starts) never sees an item, a label, a source
text chosen for an item or any per-item result. You do. So:

- **Work only in your own folder**, outside the repository and never under `external/`, here called
  `<RS>`. Nothing you build is committed, pushed, pasted into a message to the lead, or written under
  the repository (the tools refuse it). The one file you write in the repository is the hand-back of
  section 9, counts only.
- **Hand back counts only:** no quote, no position, no article text, no persona, no label, no
  per-item figure, in any message or file the loop reads.
- **No pipeline run.** Never name the pipeline driver in a shell command. A tokenizer, the freeze
  machinery's encoder (section 8) and Python's own tools are allowed on the laptop; a model call is
  made only on a rented machine, through a launch the lead makes (section 6).
- **Seckin does not label.** Every label is written by an agent you start or computed by the tool.
- No em dashes in anything you write. Every time you write comes from `date`.
- Read every source's terms before you use it (section 2).

## 1. What to build

About 40 items in four groups (plan section 2):

| Group | Items | Source |
|---|---|---|
| P-INB | 20 | WHO pandemic agreement INB: apps.who.int/gb/inb (bureau texts, negotiating texts per session); positions from the Earth Negotiations Bulletin (IISD, enb.iisd.org) coverage of INB sessions, where it exists, and the parties' own published submissions and statements |
| P-INC | 10 | Plastics treaty INC-5.1 (Busan) and INC-5.2 (Geneva), UNEP (unep.org/inc-plastic-pollution): the chair's texts and the compilation texts; positions from ENB and party submissions |
| H | 5 | Bilateral host-agreement rounds, **synthetic**: a public start text (a model host country agreement, for example the one the UNFCCC publishes) and a public signed text (for example the COP31 host country agreement on unfccc.int). A signed agreement publishes no rounds, so the rounds between are written by an author agent you start (section 5.3) |
| G | 6 | LLM-Deliberation games, MIT licence: github.com/S-Abdelnabi/LLM-Deliberation |

**Reserve:** BBNJ (un.org/bbnj, the drafts with track changes), only if P falls short of 30 after the
licence check and the leakage pass. If P is still short, record the shortfall; nothing else fills it.

**Not usable:** anything in the loop's development material (`NEGOTIATION_MEASUREMENT_PLAN.md`
section 1), anything in `benchmark/`, `tuning/` or a gate set, any held-out negotiation case of role
B's, and anything written for this project.

## 2. The terms of each source, first

Before any text of a source enters an item, read that source's terms of use and record them in
`<RS>/neg_advisor_set/SOURCES.md`: the URL, the publisher, the licence or terms in their own words (a
one-line paraphrase plus the URL of the terms page), whether research use is allowed, and whether
redistribution is allowed. Known: WHO INB CC BY-NC-SA 3.0 IGO; ENB CC BY-NC-SA 4.0; LLM-Deliberation
MIT. **Unconfirmed:** UN, UNEP, UNFCCC, BBNJ and each party submission. A source whose terms do not
allow research use is not used, and the hand-back counts it. Nothing is redistributed (plan
section 10).

Beside `SOURCES.md`, write `<RS>/neg_advisor_set/sources.json`, one entry per source read:
`{"used": true or false, "research_allowed": true, false or null, "redistribution_allowed": true, false or
null}` (null for unconfirmed); the hand-back counts these, no text.

**The cloud provider, the rule (plan section 10):** sending public CC BY-NC-SA excerpts to the cloud
provider for this non-commercial research evaluation is processing, not redistribution, and is allowed
only through the provider's API under its default that API inputs are not used for training. An item
whose source's terms forbid that, or are unconfirmed, does not go to the cloud arm; say so in the
hand-back's shortfall.

## 3. Choosing the items, by rules fixed before you read any text in full

### 3.1 Rounds

For each process list its rounds in order (a round is one negotiating text a session worked on, with
its date and document symbol), from titles, dates and document lists alone. A round k is usable when
round k+1 exists and is public. Write the list in `<RS>/neg_advisor_set/ROUNDS.md` before opening any
round's text past its first page.

### 3.2 Round counts and personas

Spread each group over round counts 1 to 5 (k = 1 to 5; fewer where the process has fewer rounds):
at most 4 P-INB items and at most 2 P-INC items per round count. For each usable (process, k):

1. list the parties and coalitions with at least two positions on record that you can source to
   round k or earlier (ENB paragraphs, submissions);
2. sort them by the SHA-256 of `20261113-negadv-persona:<process>:<k>:<party id>`;
3. take them in that order, one item per (process, k, persona), until the cap for that round count is
   reached. Write the order and what you took in `ROUNDS.md`.

Configurations (bilateral, one against a group, group against group, everyone with everyone, shifting
alignment) are **computed** by the scorer later; you do not choose for them and do not edit anything
to reach one.

### 3.3 The excerpt

By the plan's section 3.1 exactly: the bracketed articles of round k that change in round k+1 in the
seeded order `20261113-negadv:<process>:<k>:<article id>`, then one closed article, then one new
article, until 6 articles or the token budget (the whole prompt at most 24,000 tokens by
`Qwen/Qwen2.5-7B-Instruct`'s own tokenizer, loaded alone, no model). At least 3 articles, or the
(process, k) is not used. Count tokens with the tool (section 4: `build` prints each item's token
count and refuses one over the budget).

## 4. The item files

For each item, under `<RS>/neg_advisor_set/build/<item_id>/`, write `build.json` (schema
`neg-advisor-build-v1`) and `SOURCE.md`. `item_id` is lower case, digits and hyphens, for example
`inb-k3-eu`. Then `tools/score_neg_advisor.py build --set <RS>/neg_advisor_set` turns every build file
into `items/<item_id>/item.json` (what the arms see) and `items/<item_id>/key.json` (the labels),
computing the fate and state labels by the plan's deterministic diff. Never write `item.json` or
`key.json` by hand.

`build.json` holds:

- `item_id`, `part` (`P`, `H` or `G`), `process`, `round` (k), `synthetic` (true for H), `post_cutoff`
  (true when round k+1 was published after Qwen2.5's training cutoff as its model card states it);
- `licence` (the source's licence in words, for example "CC BY-NC-SA 3.0 IGO") and `attribution` (the
  publisher and document, as the licence asks); `build` refuses an item without them and copies them
  into `item.json`;
- `persona`: `{id, kind}` with `kind` `single` or `coalition`; `red_lines`: the ids of the persona's
  positions the record itself calls a red line ("cannot accept", "non-negotiable" and the like, read
  by you, not by a word list);
- `parties`: `[{id, kind}]`, every party and coalition named in the item's positions;
- `articles`: the excerpt, `[{id, title, text}]`, the round-k text with its brackets as published;
  the tool splits each `text` at blank lines into `PAR-<n>` paragraphs and each bracket group into
  proposals `P-<article>-<n>` (an article with no bracket that is not agreed is one proposal; mark an
  agreed article `"agreed": true`, and it carries none);
- `round_index` and `previous_index`: `[{id, title}]` of the whole round-k text and of round k-1
  (`previous_index` empty for k = 1);
- `next_articles`: `{article id: the matched round-k+1 text, or null when it is gone}`, and
  `renumbering`: `{round-k id: round-k+1 id}` where it renumbers;
- `positions`: `[{id, party, round, article, stance, quote, source}]`, each `id` `POS-<n>`, `stance`
  one of `support`, `oppose`, `accept`, `quote` verbatim, `source` the URL and paragraph; and for a
  position on one proposal rather than the whole article, `proposal` (its 1-based bracket number);
- `trades_on_record`: `[{id, give, get, round}]`, each side an article id and bracket number, for the
  persona's own stated conditional offers whose two sides are still in the excerpt;
- for a game item (`part` `G`) instead of articles: `game` with `issues` (`[{id, options}]`), every
  party's score table (`tables`: party, issue, option, score), `thresholds` per party, `required` (the
  number of parties a deal needs), `veto` (the parties every deal needs), and `last_deal` (one option
  per issue, the round's last deal on record). The item shows the persona only its own table.

`SOURCE.md` names each document used (URL, symbol, date, publisher, terms line from `SOURCES.md`)
and what was left out and why. `build` copies it to `items/<item_id>/SOURCE.md`, so it is part of the
frozen set's digest; a build folder without one is refused.

`build` counts every item's whole advice prompt with `Qwen/Qwen2.5-7B-Instruct`'s own tokenizer and chat
template (the tokenizer alone, from the local cache), prints each item's count, and refuses the whole set,
writing nothing, when any item is over 24,000 tokens. Shorten that item's excerpt by the plan's section
3.1 (skip the article that passes the budget, take the next) and build again.

## 5. The agents you start

Each fresh, none the lead's, each given only what is named.

1. **The mapper** (a Claude agent): for each item, given the round-k articles and the position quotes
   with their sources, it writes each position's `article`, `proposal` where it is on one, and
   `stance`. It never sees round k+1.
2. **The validator, of another family** (section 6): checks each mapping, blind to the mapper's
   reasons.
3. **The author** (a Claude agent), for H only: given the public start text and the public signed
   text, it writes rounds between them, each round a full text with brackets where the two sides still
   differ, plus each side's stated positions per round, in the record's register. Every H item is
   `synthetic: true`. It sees neither the plan's metrics nor any other item.
4. **The checker** (section 7), a fresh Claude agent that neither mapped nor authored.

## 6. Validating the position-to-article mapping

1. `tools/score_neg_advisor.py validate-prompts --set <RS>/neg_advisor_set --out <RS>/validate_prompts.json`
   writes one prompt per position: the article texts, the quote, and the mapper's article and stance
   to confirm or correct (form `neg-advisor-validate`).
2. The prompts run on a rented A10 through the replay pass on **Phi-4** (`unsloth/phi-4-bnb-4bit`,
   JUDGE's registry model, already in the sealed assets; the form's validate group declares it, because
   JUDGE's registry `local.model` is null and would otherwise resolve to Phi-3.5). You seal the pass
   yourself from `<RS>` as a **sealed** bundle (section 6a) and ask the lead for the launch, naming only
   the bundle's path, its seal's SHA-256, its test manifest's SHA-256 and its prompt count. The lead
   launches without opening it, after Seckin's "evet" for the paid run. The run folder is in `<RS>`.
3. `tools/score_neg_advisor.py validate-read --set <RS>/neg_advisor_set --prompts <RS>/validate_prompts.json --answers <answers>` writes
   `mapping_validation.json`: the agreement and Cohen's kappa over (article, proposal, stance) on every
   position, each run kept as one round, so a revision's kappa stands beside the first. It refuses answers
   that are not of that prompts file, a pass that did not load Phi-4, or a position with no answer row; it
   records the prompts digest and the pass's model and digest, which the configuration then names
   (`validate_prompts_sha256`, `checkpoint_digests.validate`).
4. Every disagreement goes to a fresh Claude labeller, who sees the texts and both mappings with no
   reasons, and picks one or neither; neither drops the position (counted). Below kappa 0.60 the whole
   mapping is revised once by the mapper (it sees which positions disagree, never the validator's
   answer) and validated again; still below 0.60, record it: the plan then reports the part as
   unvalidated.
5. Rebuild with `build` after any change, so the key reflects the settled mapping.

## 7. The checker's sample

After the build, `tools/score_neg_advisor.py sample --set <RS>/neg_advisor_set --out <RS>/checker_sheet.json`
draws 20 percent of the items (at least 8) by the plan's seeded order and writes a sheet with the
texts and no labels. The checker labels each sampled item's fate, state, conflict and alignment from
the texts, by the plan's section 4 definitions, and, per persona position, whether the record calls it a
red line (`red_line` or `not_red_line`; the sheet shows no red-line mark). `sample-read --sheet <filled
sheet>` writes `checker_agreement.json`, the per-field kappa against the key. After the runs, the same tool
draws the 25 percent counter sample for the wording grade (`grade-sheet`, then `grade-read --set
<RS>/neg_advisor_set`, which writes `grade_agreement.json`); you start a fresh checker for it.

## 8. The leakage pass and the freeze

`tools/score_neg_advisor.py freeze --set <RS>/neg_advisor_set --corpora docs/loop/stages/NEGOTIATION_CORPORA.txt --extra <the negotiation held-out set, once frozen> --extra <each gate set's documents>`
on the laptop's CPU with the network off (or `--device cuda` only when the GPU reads idle, D-399),
one job at a time while memory is low. It reads every item's article and position passages, runs the
freeze machinery's thresholds unchanged (a passage of 20 words or more: 5-gram Jaccard 0.5, bge-m3
cosine 0.9, a same source by URL or stem), writes `FREEZE.json` in the set folder with the set's
SHA-256, and prints counts only. It also draws the cloud subset (plan section 5.2) and writes
`cloud_subset.json` in the set folder, its SHA-256 in `FREEZE.json`. An item over a threshold is replaced
by the next in its seeded order and the freeze runs again.

## 6a. The runs and the score, step by step (the lead's ruling)

You run the build, the answers, the judge's prompts, the grading and the score; the lead launches the
rented passes and never opens them. In order:

1. `tools/score_neg_advisor.py power --set <RS>/neg_advisor_set --k 1 --out <RS>/NEG_ADVISOR_POWER.json`;
   hand the file to the lead (counts, class shares and the simulated power, no item), who commits it.
2. The prompts files, in `<RS>`: `benchmark/baselines/neg_advisor.py build --set <RS>/neg_advisor_set
   --form advice --groups b1,system_advice --out <RS>/prompts_arms.json` and `... --groups b1 --subset
   <RS>/neg_advisor_set/cloud_subset.json --out <RS>/prompts_cloud.json`.
3. Seal each rented pass from `<RS>` as a sealed bundle (SEALED-RUN-A: `--exposure sealed`, your own test
   manifest, prepared outside the repository), the prompts file as its replay prompts. Give the lead only
   the bundle's path, its seal's SHA-256, the test manifest's SHA-256 and the prompt count. The lead asks
   Seckin's "evet", launches with the bound wrapper and `--frozen-tag`, the run folder in `<RS>`, and reads
   counts and timings only.
4. The cloud reference: you start it yourself, never the lead, through the role C runner's negotiation
   form, on your own `<RS>/prompts_cloud.json`. Tell the lead its prompt count; the lead recomputes its cost
   from the frozen counts, asks Seckin's "evet" and relays it. Start nothing before it. Then:
   4.1. **The lead opens role C's intent:** `py -3.12 -X utf8 benchmark/baselines/cloud_reference_b1.py
        open-role-c --cap-usd <cap> --seckin-approved "<heading time of the FOR_SECKIN entry>"`, after
        Seckin's "evet" to that entry (D-S106). Under the spend store's lock it holds the cap as running
        and writes an intent line of kind `cloud-reference-b1-role-c`, and prints the run id (`role-c-<12
        hex>`) and the budget figure (the intent's own cap). The kind need not differ for the advisor:
        `append-handed-back` admits only run ids of an intent of that kind, and only the close line the
        form writes names `cloud-reference-neg-advisor-v1`. The lead hands the role session the run id,
        the figure and a copy of the FOR_SECKIN entry with its evet line.
   4.2. **The role session runs the form,** from its own clone (never the main checkout or a worktree of
        it: the form refuses where the lead's spend store is reachable): `SHIMMER_ROLE=C py -3.12 -X utf8
        benchmark/baselines/cloud_reference_b1.py run-negotiation --prompts <RS>/prompts_cloud.json --out
        <RS>/cloud_run --cap-usd <the figure or less> --credit-usd <the credit left>
        --price-input-per-mtok <row> --price-output-per-mtok <row> --price-source "<page, date>"
        --deprecation-checked "<url>, <YYYY-MM-DD>, not deprecated" --seckin-approved "<heading time>"
        --for-seckin <RS>/for_seckin_copy.md --role-c-run-id <run id> --budget-left-usd <the figure>
        --spend-file <RS>/C_negadv_cloud_reference_spend.jsonl`. The replies stay in
        `<RS>/cloud_run/texts.json`; the measurement and the spend file hold counts, tokens and cost
        only.
   4.3. **The lead appends the spend file:** the role session hands back
        `C_negadv_cloud_reference_spend.jsonl` alone; the lead moves it into
        `docs/loop/private/cloud_reference_handed_back/` of the main checkout and runs `py -3.12 -X utf8
        tools/loop/cloud_reference_spend.py append-handed-back
        <USER_HOME>/local/shimmer-deployment/docs/loop/private/cloud_reference_handed_back/C_negadv_cloud_reference_spend.jsonl` (the file by its absolute path in the main
        checkout: a relative path resolves against the working folder, a worktree's is refused). Until it is
        appended the guard (`cloud_reference_spend.lead_may_spend`) refuses the lead's next paid run and
        every instance launch; a line whose run id names no intent the lead opened, or whose spend passes
        the intent's cap, is refused (the second flagged at the top of FOR_SECKIN).
5. `neg_advisor.py answers --prompts ... --run <the run's pass folder> --out <RS>/...` for each pass, and
   `texts` for the cloud reference.
6. `score_neg_advisor.py judge-prompts`, then the judge's pass sealed and launched as in step 3, then its
   answers; then `grade-sheet`, a fresh checker, and `grade-read`.
7. Write `<RS>/configuration.json` (digests and ids only: every field the plan's section 7.4 names, the
   checkpoint digests as each pass's answers and `mapping_validation.json` record them) and give the lead its SHA-256 and content. The
   lead commits the opening line.
8. `score_neg_advisor.py score --set <RS>/neg_advisor_set --configuration <RS>/configuration.json --k 1
   --b1 ... --system ... --cloud ... --judge ... [--per-item-out <RS>/neg_advisor_set/per_item.json]`.
   Hand the lead its printed aggregates and nothing else; the per-item rows stay in the set folder.

## 9. What to hand back

One file, `docs/loop/private/NEG_ADVISOR_ROLE_DONE.md` in the main checkout, written by
`tools/score_neg_advisor.py handback --set <RS>/neg_advisor_set --out <that path>`, which writes
counts only and refuses to write any text field. It reads the set's keys, `mapping_validation.json`,
`checker_agreement.json`, `FREEZE.json`, `sources.json` (section 2) and `role_counts.json`, which you write
with whole numbers only under `positions_dropped`, `items_replaced`, `shortfall_P`, `shortfall_H` and
`shortfall_G` (anything else is refused):

- items per group, per round count and per configuration;
- rows per field (proposals, articles, alignment cells, counters possible, game items) and each key
  class's share;
- the mapping kappa (before and after any revision), positions dropped, and the checker's per-field
  kappa;
- the leakage counts per corpus and threshold, the items replaced, and the cloud subset's SHA-256;
- the sources used and refused, by count, with the terms states (research allowed, redistribution
  allowed, unconfirmed);
- the set's SHA-256 and `FREEZE.json`'s SHA-256;
- any shortfall.

Then send the lead one message: "neg-advisor set frozen", the set's SHA-256 and the hand-back's path.
Nothing else.

## 10. Time

The items by the morning of 14 November. If a source's terms or a missing round leave the set short,
hand back what is built with the shortfall rather than waiting.
