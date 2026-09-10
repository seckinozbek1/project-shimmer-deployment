![Project Shimmer](project_shimmer_cover.png)

# Project Shimmer

An agentic framework that verifies the claims written in a document and detects changes
between versions of a document across negotiation rounds. It targets political, legal, and
diplomatic documents, but the mechanism is domain-agnostic by construction: no domain
vocabulary is hardcoded anywhere in `scripts/`, and an operator brings their own review
conventions, reference corpus, and (optionally) an earlier version of the document to
compare against. A fixed roster of 18 LLM agents reads, verifies, redacts, and amends,
governed by an append-only constitution. Producers and auditors are always different model
families, so no model checks its own work. Each run produces reviewed deliverables: flagged
provisions, cited findings, and proposed amendments, every one grounded in an
operator-defined convention (CONV-*) and a precise reference into the source corpus (REF-*).

Shimmer composes established mechanisms (multi-agent cross-family verification, retrieval,
information-flow control) under an amendment-governance frame. It does not claim novel
machine learning. See section M for positioning.

**Early testing used a five-document synthetic competition-law scenario** (a fictional
regulator's draft regulations and an operator-written review mandate), written specifically
as test material, not real regulatory documents; see section J for the historical
measurements taken against it. `benchmark/corpora/` carries the corpora this repository's
own gate exercises today, including a document-comparison scenario built from real,
publicly reported figures with every real party name replaced by an obvious placeholder
(Company A, Union B) before publication.

**This repository is a public source snapshot, MIT licensed** (see `LICENSE` and
`CITATION.cff`). It carries the source code, the configuration, and the test corpora that
prove the mechanism works; it does not carry any run history, any private material, or any
directory a run creates. `input/`, `output/`, `durable/`, and `tests/` (the full list is
below) are not part of this snapshot; section G explains what each one is for and what you
supply or generate to get one. This README is the first read for anyone cloning it fresh. It
is honest about what
works and what does not (sections J and K), and honest about the gap between what a working
deployment looks like and what a source-only snapshot ships (section G, section L).
Two operational documents sit alongside it: `docs/RUNBOOK.md` (install, launch, submit,
watch, approve, what each status means, what to do when a run hangs or BLOCKs, how to back
up and restore, how to read `cost_tracker.json`) and `docs/THREAT_MODEL.md` (assets, trust
boundaries, threats with their current mitigation and residual risk, and what is
deliberately out of scope).

### What's in this repository

127 tracked files (source, configuration, and test corpora; counted directly from the
repository tree, not from git, since directory creation and `.gitignore` behavior can differ
by tool). No compiled bytecode, no run output, and no cache directory is tracked; those are
excluded by `.gitignore` and, if present locally, are never committed.

```
shimmer-deployment/
├── README.md, CLAUDE.md, genesis.md      the guide, the agent operating contract, the spec
├── LICENSE, CITATION.cff                 MIT license, citation metadata
├── requirements.txt                      pinned Python dependencies
├── shimmer.bat, shimmer.sh               the launcher: builds .venv, installs deps, menu
├── scripts/                              the pipeline, the 18 agent modules, the server,
│                                          the gate (scripts/verify_session1.py), harness/,
│                                          sensitivity_layer/, ui/ (the console, one HTML
│                                          file plus its vendored typeface)
├── corpus_ingest/                        the external corpus ingestion contract, validator,
│                                          and its own test fixtures
├── config/                               governance and compiled config (constitution,
│                                          agent registry, contracts, domain vocabulary,
│                                          institution names, review scope, pricing)
├── benchmark/corpora/                    the four shipped test corpora and their answer
│                                          keys (see "Test corpora from other domains", H)
├── tools/                                run wrappers: run_local_demo, stage_corpus,
│                                          score_corpus, console_preview (a throwaway local
│                                          harness for looking at the console, not the product)
└── docs/
    ├── RUNBOOK.md, THREAT_MODEL.md       operational reference (see above)
    └── api/CONSOLE_PLAN.md,              the console's design, its two-view language
        CONSOLE_LANGUAGE.md,              (reviewer/developer, field by field), and the
        CONSOLE_STATE_AUDIT.md            audit of every state against what may exist
```

**Not shown above because they are not shipped, and a fresh clone does not have them:**
`input/`, `output/`, `durable/`, `ontology/`, `tests/`, `prompts/`, `snapshots/`,
`benchmark/keys/`, `.venv/`. Every one of these is either created by the launcher on first
run, created by the pipeline as it runs, or something the operator supplies. None of them
holds source code. Section G says exactly what each one is and how it comes to exist;
section L says which gate checks this affects.

---

## A. The constitutional model

Shimmer is governed by seven seed laws. They are enforced, not advisory, and are amended
only by a formal append-only process. Agents propose changes; only the operator ratifies;
agents never self-apply.

- **LAW-0, Operator sovereignty:** the operator is the sole source of constitutional
  authority. No agent may create, amend, or repeal a law.
- **LAW-I, Do no harm to the source:** no agent may alter, fabricate, or suppress source
  content. Agents may flag, annotate, and footnote.
- **LAW-II, Know your bounds:** each agent has a fixed capability set; it may request
  another agent's service but never perform it.
- **LAW-III, No self-audit:** no model may verify output produced by its own model family.
  Claude-produced content is audited by GPT (or local models), and the audit trail records
  which model produced and which verified each segment.
- **LAW-IV, Protect what is private:** operator-marked sensitive content is processed only
  by offline local agents. It must not cross a network or enter an API call. This law
  cannot be overridden by any later amendment or operator instruction; it outranks LAW-0
  for this scope, because a single leak is irreversible.
- **LAW-V, Remember before you act:** before any search, verification, or computation an
  agent consults, in order, the constitution, the precedent registry, the verification
  memory, and the run objectives, and acts on the first match.
- **LAW-VI, Structure is earned, not assumed:** organizational structure below the Top
  Orchestrator emerges from identified work through chartered task forces.

The constitution holds 7 seed laws and 28 ratified amendments (INFRA-017 through
INFRA-044). A meta-level tripwire (`scripts/constitution_guard.py`) protects the immutable
core and makes the verified, append-only, no-gap DELTA path the normal route to amend
governed structure: one write may add only one new amendment, an INFRA-NNN id must be the
next in sequence, and the entry must be operator-ratified (`operator_approved`). Modifying
or deleting an existing seed law or amendment is not a DELTA and is refused unless an
interactive operator handler approves it. A separate signature scan runs on the operator's
run objectives and on an agent-proposed DELTA, never on the constitution write itself. The
asymmetry is deliberate: that scan refuses agents (which can never amend governed
structure) but never hard-blocks the operator (sovereign under LAW-0), who gets
confirm-and-proceed interactively and log-and-proceed otherwise. The signature scan is a flag for operator attention, not
a complete semantic guarantee; it has false positives and false negatives.

### Vocabulary

- **INFRA-NNN:** a ratified amendment in the governance record. Append-only: an id is never
  reused, inserted between existing ids, or renumbered. A DELTA an agent proposes and the
  operator ratifies at run time is recorded instead with an auto-sequenced `AMEND-NNNN` id,
  checked for append shape and operator ratification but not for the no-gap sequence.
- **DELTA:** a proposed amendment before the operator ratifies it. Agents draft and
  propose; only the operator ratifies.
- **CONV-*:** an operator-defined convention (a rule the review applies).
- **REF-*:** a precise citation into the corpus. Every finding names a CONV-* rule id, and an
  affirmative finding that cites no REF-* is downgraded to UNCERTAIN and kept, not dropped.
- **WEB-REF-*:** a structured citation into a discovered web reference, minted with a stable
  id and cited the same way a REF-* is.

---

## B. Architecture

Eighteen fixed-role agents collaborate on an append-only message bus. Each emits one flat
per-item envelope (`{agent, doc_id, items[]}`, INFRA-037); consumers read by reference, and
a higher revision of an item supersedes an earlier one. Per-agent context is assembled per
provision through retrieval over a reference index (semantic retrieval via the embedding
store when present, term matching otherwise). The Top Orchestrator is pure Python (no LLM
call).

### The 18 agents and their models

Models are read live from the provider and named in the registry as bare aliases (never
dated ids); a deprecated model stops the run for operator approval.

**The table below is the CLOUD profile**, which is what `config/agent_registry.json` declares
and what a run makes when it can reach the providers. It is not what a local run uses: see
"The local profile" immediately after it. Every measured run in section J except the first was
a local run, so read the two tables together before drawing a conclusion about cost or quality.

| Stage | Agent | Backend / model |
|---|---|---|
| Read + extract (per doc) | PROCESSOR | Claude Sonnet 4.6 |
| | SPEECH_ACT_TAGGER | Claude Haiku 4.5 |
| | LEGAL_ANALYST | Claude Opus 4.8 |
| Read + extract (corpus) | ARCHIVIST | Claude Sonnet 4.6 |
| | INST_FINDER | Claude Haiku 4.5 |
| | CITATION_RESOLVER | Claude Haiku 4.5 |
| Verify + audit | VERIFIER | GPT-4o |
| | FACT_CHECKER (web) | GPT-4o |
| Convention review | PRACTICE_AUDITOR (web) | GPT-4o |
| | STYLE_GUARDIAN | Claude Haiku 4.5 |
| Amend | AMENDMENT_DRAFTER | Claude Opus 4.8 |
| Editorial board (lower) | EDITOR_CLERK, EDITOR_HEAD_OF_UNIT, EDITOR_HEAD_OF_SECTION | Claude Opus 4.8 |
| Editorial board (upper) | EDITOR_HEAD_OF_DEPARTMENT, EDITOR_DEPUTY_DG, EDITOR_DG | GPT-4o |
| Redact | REDACTOR | Qwen 2.5 7B Instruct (local) |

The GPT auditors review Claude-produced content, satisfying LAW-III. The editorial board
is a six-rank family split (3 Claude lower ranks, 3 GPT upper ranks). REDACTOR is the only
agent permitted to handle sensitive content, and it runs offline. Only FACT_CHECKER and
PRACTICE_AUDITOR may reach the web (`may_use_web`).

#### The local profile (`--backend-profile local`)

`--backend-profile local` remaps **17 of the 18 agents** to two local models and makes no
provider API call in a **review** run. REDACTOR is the exception: it was already local. The
agent-to-backend map lives in `pipeline._LOCAL_PROFILE` (the LAW-III producer/auditor split is
hardcoded there and never read from config); the two model ids are overwritten at import by
`_resolve_local_models` from `config/local_models.json`. The flag also sets
`SHIMMER_BACKEND_PROFILE`, because five behaviours (agent serialisation, the document clip, the
progress display, the role anchor, CPU embedding) key off the environment variable rather than
the flag; a run started with the flag alone once loaded local models and then ran them
concurrently, which cost a 47 minute run. **Draft mode is not covered by the profile:** phase 0
calls the Anthropic path directly (`_draft_generate` into `AgentWrapper.call_claude`, which never
consults the backend) while the profile has already rewritten AMENDMENT_DRAFTER's model id to a
local one, so `--task draft --backend-profile local` fails at memo generation and exits 5.
Drafting needs the cloud profile until phase 0 goes through `dispatch`.

| Cloud role | Agents | Local model |
|---|---|---|
| producer (11) | PROCESSOR, LEGAL_ANALYST, STYLE_GUARDIAN, ARCHIVIST, INST_FINDER, CITATION_RESOLVER, SPEECH_ACT_TAGGER, AMENDMENT_DRAFTER, EDITOR_CLERK, EDITOR_HEAD_OF_UNIT, EDITOR_HEAD_OF_SECTION | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` |
| auditor (6) | VERIFIER, FACT_CHECKER, PRACTICE_AUDITOR, EDITOR_HEAD_OF_DEPARTMENT, EDITOR_DEPUTY_DG, EDITOR_DG | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` |
| redactor (1) | REDACTOR | `Qwen/Qwen2.5-7B-Instruct` (from the registry, not remapped) |

What this costs, measured rather than assumed: **$0.00 and no network** (measured across every
local-profile run in the operator's own working record, not published in this snapshot; the
cloud comparison figure quoted in section J is historical and is not reproducible here). But
the local auditor is the model that fills the typed Finding
record, and on a document where arithmetic can settle nothing it produced **one valid typed
Finding out of 37 replies**, and even that one carried no usable rule id, so nothing reached the
deliverable (section J, the catalogue corpus). The local profile also switches the review to `paired` mode
by default, and the LAW-III separation the cloud profile provides (GPT auditors reviewing
Claude-produced content) does not hold locally, since one family produces and another audits but
both are small local models. Two consequences worth stating plainly: the quality figures in
section J are local-profile figures, and no cloud run of the newer corpora has been made.

### Pipeline phases

A run executes in this order. The phase numbers are the project's own labels, not a
contiguous sequence (there is no phase 2; phases 5.5 and 6.5 are intermediate stages).

- **Phase 0 (draft mode only):** generate a memo from the operator's question, then mark it
  the review target. This runs first, before document population and before the orchestrator
  boots. See section C.
- **BOOT + document population:** run the date cascade, resolve document roles (section D),
  and populate `input/operational/` (each promoted document is content-validated here, a
  first-page keyword check that flags possible misclassification and never drops a document);
  then load the constitution and bus, and on a first run only spawn learning assets from
  `input/context/` (the spawn is keyed on the durable sentinels and is a no-op afterwards);
  then parse conventions into a registry and build the reference index, which is built last
  because it needs the populated corpus.
- **Phase 1:** situation assessment (ORCHESTRATOR).
- **Phase 3-4:** content production. Per document: PROCESSOR, SPEECH_ACT_TAGGER,
  LEGAL_ANALYST. Corpus-level (once): ARCHIVIST, INST_FINDER, CITATION_RESOLVER.
- **Phase 5:** verification + fact-check (VERIFIER, FACT_CHECKER).
- **Phase 5.5:** convention review (PRACTICE_AUDITOR, STYLE_GUARDIAN). Skipped when no
  conventions are loaded. Runs in one of **two review modes** (see below).
- **Phase 6:** synthesis: the context summary, the operative summary, and the canonical
  amendment master (JSON + md + docx). Every amendment is rendered deterministically from the
  typed Finding records; the AMENDMENT_DRAFTER model call is off by default and
  `--amendment-polish` turns it back on as a wording-only pass.
- **Phase 6.5:** editorial review board: a bounded rank-by-rank climb, starting at
  EDITOR_CLERK, escalating only when a rank's confidence is low or it marks out-of-mandate,
  capped by `max_rounds` from `config/editorial_board.json`. Runs only on a run declared
  non-sensitive (the `--no-redaction-override` waiver in force); otherwise the whole board is
  skipped and the skip is recorded per deliverable.
- **Phase 7:** DELTA proposals surfaced to the operator (no self-apply).
- **Phase 9:** redaction screening (REDACTOR). Runs only when the sensitivity layer is
  ACTIVE (`sensitivity_layer.is_active()`, operator-activated, False by default); declaring a
  run sensitive is not on its own enough. Otherwise the scrub phase is skipped (PII is still
  flagged upstream in phases 5/5.5/6, just not scrubbed). LAW-IV is strict when it runs.
- **Phase 8:** persist artifacts and write the run summary.
- **Run end:** the learning engine captures provisions, rebuilds its graph, and updates the
  GNN. For a draft run, the generated memo and its manifest are cleared.

Multilingual support is built in: every language is embedded into one shared cross-language
space (`BAAI/bge-m3`), so an English query retrieves against non-English passages. Per-document
language detection still runs, drives direction-aware output for right-to-left scripts, and
remains the hook if a language-specialised model is ever added.

### The two review modes

Phase 5.5 runs one of two ways. `--review-mode` selects it; with no flag the default is
**`paired` under the local backend profile and `wide` under cloud**
(`pipeline.resolve_review_mode`), and an explicit flag always wins.

- **`wide`:** each convention-review agent sees the whole document and the whole registry
  and is asked to evaluate one against the other. One call per agent per document.
- **`paired`:** the run first builds a **pairing map** (`<run>/audit/pairing_map.json`),
  deciding which rules could apply to which units of the document and recording the reason
  for every pairing and every non-pairing. Python then computes the arithmetic. Three
  outcomes per pair, and only one costs a call: the figures disagree (the model is shown the
  computed values and asked only whether the difference is material, never to recompute
  them); nothing is computable (the model judges one unit against one rule on the text); the
  figures agree (no finding, **no call**). One call is made per distinct computed
  disagreement, not per pair. `--pairs-per-unit N` caps the pairs considered per unit; a pair
  the cap drops is counted and logged, never silently skipped.

The mode changes cost, not correctness: where arithmetic can decide, the finding carries
Python's numbers whatever the model says about them.

Every unit `split_units()` produces (`scripts/pairing_map.py`) also carries `index`, its
0-based position in the document's own order. This closed a real gap: a unit dict used to
carry no order-bearing field at all, so once a caller re-keyed the list to a dict on
`unit_id` (every real caller does, immediately), the model-facing side of a paired call had
no way to answer "which unit comes before or after this one," only "which unit is this."
`index` is added once at the single source (`split_units`) and survives every downstream
re-keying because each of those sites copies the whole unit dict by reference, never a named
subset of fields; it reaches `build_pairing_map`'s own entries the same way, threaded
through explicitly since that dict shape is built fresh, not copied. A second, related
defect in the same trace: `pipeline.py`'s `_paired_convention_review` used to build two
separate unit maps, one from the pairing map's own entries (no `text` field, assigned and
never read again) and one from a second, independent `split_units()` call (the one every
real call was actually built from). The dead map is gone; there is one unit map in that
function now, sourced once.

A paired call now also carries the unit's immediate neighbors (`docs/api/UNIT_CONTEXT_DESIGN.md`,
option B, built on `index` once order was fixed and proven separately, never before): the
text of the unit immediately before and after the one being judged, under
`preceding_unit_text`/`following_unit_text`, and a document-wide structural map
(`document_map`, id/title pairs only, no unit's own text) under option D, reused from the
same `document_units` list wide mode already builds for a different reason. Each field is
kept structurally distinct from what is being judged, never merged into `document_text`, so
a model can tell the unit it is judging from its context by field name alone, before reading
a word of content: `neighbor_note` and `structure_note` say in words what the field
separation already says in structure, that the neighbors are context to weigh, not evidence
to judge or cite, and the map is orientation, not a description of any unit's content. First
and last units correctly get only one neighbor, never an invented one; a unit with no
`index` is refused a neighbor rather than guessed from list position.

**The real limit, stated plainly rather than left implicit**: this makes a provision's
IMMEDIATE neighbor visible to the model judging it. It does nothing for a term defined at
the start of a document and used, unchanged, at the end: that relationship spans the whole
document, not one unit's boundary, and neither `preceding_unit_text`/`following_unit_text`
nor `document_map` (titles only, no content) carries what a distant unit actually says.
Closing that gap was considered and deliberately deferred, not attempted here: it would need
either sending far more of the document per call (which is what made wide mode summarize
rules instead of checking them, the exact failure paired mode was built to avoid) or a real
cross-run relevance signal telling the pipeline which distant units are worth attaching,
which the ontology graph and GNN do not yet provide (see below).

### Bands from the reference corpus

A rule often states no numbers of its own; it points at a table in the reference corpus.
`scripts/reference_tables.py` reads those tables so the comparison can be made in Python
instead of by a model reading prose. Four mechanisms, all structural, none carrying any
domain or language vocabulary:

- **A range is two numbers in one cell.** A cell holding exactly two quantities of the same
  unit, the first not greater than the second, separated by a short run of non-numeric text.
  No word for "to" appears in the module, in any language: the shape is the signal, and the
  column's own declared unit overrules whatever token happens to follow the first number.
- **The unit comes from the header, and a prose unit is read self-validatingly.**
  `Price band (TRY per tonne)` is accepted as `TRY/t` only because `TRY/t` is a unit **the
  document under review itself writes**. The parenthetical's **first and last** tokens each map to a
  document unit exactly, or as the unique document unit that is a prefix of it (`t` inside
  `tonne`); whatever sits between them is never read, so no connector word is known in any
  language. Both orders are composed, and the reading is accepted only if exactly one of them
  yields a unit the document uses: if both do, that is an ambiguity and it is refused. A
  reading the document does not corroborate is discarded rather than guessed at.
- **Key columns are learned**, from the rule text that cites the table and from which columns
  discriminate rows. A rule must name the **range column** as well, so a completeness rule that
  happens to mention the key column does not inherit a yield band.
- **A row matches a unit by word containment** over the unit's own labelled field values. The
  most specific match wins and a tie is refused, because a wrong row is a wrong band and a wrong
  band is a false finding.

The resulting `(low, high, unit)` is compared against the unit's figures by
`paired_review._band_comparisons`, the same above/below/in-range test the rule-stated band makes
in `compute_checks` (two passes today rather than one function: the rule-stated pass also
restricts the comparison to the fields the rule names, and emits nothing for a value inside the
band). The finding cites the `REF-*` id of the reference passage the table came from.

**The low side is not decided by arithmetic.** A rule can qualify the low side only: a figure
under the band is an irregularity *unless* something else is on file. Whether it is on file is
not in the figures. The condition is detected structurally (the document field labels the rule
names that this comparison and its row key do not use), and where it applies the finding is
carried as `conditional_on` and is never promoted to a settled amendment by the computed path.
`<run>/audit/pairing_map.json` records the evidence per unit under `band_conditions` before any
verdict fires.

**Two recorded limits.** A key cell that encodes a numeric comparison in prose ("protein 12.5
percent and above") cannot be matched by word containment; the rows tie, the tie is refused, and
no band is produced rather than one being guessed. Resolving it would need a list of direction
words, which is exactly the domain leak the vocabulary probe exists to catch. And a band stated
in prose rather than in a table is not read here; the rule-text path still covers a rule that
states its own numbers.

### Typed Finding records

Agents do not talk to each other in prose. A finding that travels between agents is a
**Finding record** (`scripts/finding_record.py`), one flat canonical-envelope item
(INFRA-037): `rule_id` (a `CONV-*` in the registry), `source_rule_id` (the operator's own id
for that rule), `unit_id`, `value_a`/`unit_a` and `value_b`/`unit_b` (a figure and its unit,
two fields rather than a nested object), `relation`, `record_verdict` (`ok` or `irregular`,
deliberately not `verdict`, which every agent already uses for its own values),
`source_refs` (`REF-*` / `WEB-REF-*`) and `explanation`. The explanation is for the human
reader and is stripped from any payload travelling to another agent. The schema lives in
`config/agent_contracts.json` under `finding_record`; the module reads it rather than
carrying a second copy. These records are what `GET /runs/{run_id}/findings` serves (section I).

Four **optional** fields were appended by INFRA-044 (none required): `field_label` (the
document's own label for the field), `delta` (`value_a` minus `value_b`, same unit only),
`band_distance_change` (how far the field moved relative to the band the rule states, now
minus the earlier version; negative is toward) and `provenance` (`computed` when Python minted
the record from figures it read itself; absent when an agent wrote it). Five relations were
appended after the existing ones: `changed_from_prior`, `unchanged_from_prior`,
`moved_toward`, `moved_away`, `absent_since_prior`. Every record carrying one of them is
`ok`-verdict by construction and is **never an amendment**: movement, sameness and absence are
information for the reader, not an irregularity.

### Comparing a document with its earlier version (round N against round N-1)

A negotiation is reviewed round by round, and the question about round N is rarely only "is
this inside the mandate": it is what moved since the last offer, which way relative to the
mandate, what held, and what was dropped. Shimmer answers that from typed fields, in Python,
with no model call:

1. The operator declares the earlier version as a **role**, never inferred: the manifest's
   `prior` list (`input/context/_review_targets.json`, section D), which the intake wizard
   asks about. A prior is grounding and is never promoted to `input/operational/`; a file
   named both as a target and as a prior is reviewed, not compared, with a logged warning.
2. Python reads the earlier version's figures exactly as it reads the document's: `Label:
   value unit` lines and the single value column of a table, matched by **label word-set
   equality** (`paired_review.prior_index`, `prior_lookup`,
   `reference_tables.prior_values_for_scalars`). Every match cites the earlier paragraph's
   `REF-*`; a line and a summary table that agree are both cited.
3. For each field both versions state: the same figure is `unchanged_from_prior`; a different
   figure with exactly **one band from a paired rule that names the field** is `moved_toward`
   or `moved_away` by the sign of the change in distance to that band (`band_distance_change`
   carries that signed change, negative toward the band and positive away); a different figure with no band to orient it is
   `changed_from_prior`. A field the earlier version stated under this heading that no unit
   states any more is `absent_since_prior`, carrying the earlier figure as `value_b` and no
   `value_a`, and citing any registry rule that names it (a completeness rule that could
   never have paired with a unit lacking the field).
4. Anything that cannot be settled is **refused on the record**, never minted: a tie between
   rows or between differing earlier statements, a unit mismatch, disagreeing bands, an
   earlier statement with no citation on file, a table with no discriminating key column, a
   term whose earlier heading has no counterpart. Refusals are written into
   `audit/pairing_map.json` (`prior_comparisons` per unit, `prior_orphans` per document) and
   rendered under "Not comparable".
5. The records travel as one computed `PRACTICE_AUDITOR` envelope on the bus
   (`backend=computed`, `model=python`), reach `GET /runs/{run_id}/findings`, and are rendered by one shared
   renderer (`finding_record.render_prior_comparison`) in **both** `document_summary.md` and
   `review_findings.md`, with the same records carried in `review_data.json` under
   `prior_comparisons`. Only records with `provenance=computed` appear in that section: a
   model in wide mode may emit one of these relations with figures of its own, and those stay
   among the ordinary findings under their category.

The comparison runs in both review modes, before the mode branch, and costs no model call. An
optional review `--question` (section C) is folded into the run objectives the review phases
receive (4, 5, 5.5 and 6; the editorial board builds its own) and is echoed at the top of
`document_summary.md` and `_run_summary.md`; it is never parsed.

The figure reader was extended for this material, structurally: a currency **symbol** before
the number (any Unicode character of category Sc) or a short all-caps **code** before it
(`ZQK 12,000`) is the unit, and a prefix outranks a following prose word (`$105 per year`
reads as 105 dollars, not 105 "per"); an accented unit keeps its letters; a **multi-word
unit** (`30 calendar days`) is read whole only when the document itself writes that phrase
after a figure more than once; comma-grouped thousands with several groups (`1,254,000`) are
read. No currency, unit or word is named in the code.

### How an amendment gets written

Every amendment is rendered **deterministically from the typed Finding records**. The
`AMENDMENT_DRAFTER` model call is off by default.

That decision rests on measurement, not preference. Holding one run's arithmetic identical and
changing only the amendment prose, recall moved from **2/9 to 5/9** (the 2/9 is one live draw
of the model's wording, labelled as one draw rather than an average; the deterministic
ablation arms around it are what establish the conditional), and a true band finding
scored as a **false positive** purely because its sentence said "exceeds the typical yield
range" instead of "8.8 t/ha, above the reference bound of 3.4 t/ha". The conventions ask for
the specific figures; the model kept leaving them out. The figures used to be a fallback used
only when the model said nothing, and the model almost always said something.

So the **computed figures lead every comment**, always, and carry their units, the registry
rule id and the operator's own id for it, and the `REF-*` the finding rests on. Nothing about
that depends on a model call succeeding.

`--amendment-polish` turns the model back on as an **optional wording pass**, and its job is
narrow by construction rather than by instruction:

- it is called **once per irregular finding** (an ok-verdict record, such as every comparison
  with the earlier version, never buys a call), and sees that finding, that finding's own unit
  and that finding's own rule, not the whole document and not everybody else's findings;
- it may return exactly **two fields**: `explanation`, one sentence for a person, which
  follows the figures rather than replacing them; and `proposed_text`, the corrected line as
  it should read, which is the one thing arithmetic genuinely cannot produce and which the
  template otherwise leaves empty;
- **no amendment is ever taken from the model.** Its two values are merged into a record
  Python already built, and the template builds the amendment from there, so the rule id, the
  location, the refs and the figures are never in its reach. A field a model cannot write is a
  field it cannot get wrong;
- a call that fails, times out or answers with nothing leaves the record untouched and the
  template writes the amendment exactly as it would have.

### Grounding behaviors

Two gates keep the deliverable honest. The **verifiability gate** flags a confident positive
finding that cites nothing as UNCERTAIN rather than passing it, and keeps it. The
**empty-convention carve-out (INFRA-042)** relaxes the CONV-* requirement on an **amendment**
only when the convention registry is empty (`convention_ref` stops being required and the
comment grounds on a REF-* or a WEB-REF-*), never when conventions exist. It is
amendment-scoped: no finding path relaxes its `CONV-*` rule id.

---

## C. Task modes: review and draft

Both modes produce the same deliverable (a docx with tracked changes and grounded
comments). The difference is the input.

- **Review (default):** the operator provides a finished document. The pipeline reviews it
  and produces tracked-changes amendments. "Check this memo."
- **Draft:** the operator provides a question or brief (`--task draft --question "..."`).
  Phase 0 retrieves relevant grounding from the corpus, generates a formal memo with the
  AMENDMENT_DRAFTER (Opus) model citing REF-* identifiers, writes it to `input/context/`,
  and marks it the review target (`source=system_draft`). The existing phases then review
  the generated memo exactly as they would review an operator-provided document. At run end
  the generated memo and its manifest are removed, so they do not persist as a stale target.

All three entry points (launcher, chat, server) offer both modes with the same `--task` /
`--question` flag names.

A **review** run accepts an optional `--question "..."` too: a framing question ("which
terms moved toward the mandate since the earlier offer, which held, and what was dropped?")
appended to the run objectives the review phases receive (4, 5, 5.5 and 6, not the editorial
board) and echoed in `document_summary.md`
and `_run_summary.md`. It is operator input, so the meta-law signature scan reads it with the
objectives; it is never parsed by the code. The `RUN_OBJECTIVES` prompt section is capped at
200 tokens, and an over-long question is warned about on stderr rather than silently cut.

---

## D. Document role resolution (the 4-tier chain)

Both grounding cases and documents under review can live in `input/context/`. A 4-tier
chain (`scripts/role_resolution.py`) decides which is which; first match wins.

1. **Operator instruction:** a manifest at `input/context/_review_targets.json` names the
   targets. Authoritative; never overwritten. Written by the intake wizard
   (`source=operator`), by draft mode (`source=system_draft`), or by tier 2 of this chain
   itself (`source=convention`). Its keys are `targets`, `grounding` and `prior` (lists of
   basenames), plus the `source` provenance tag and `resolved_at`. `prior` is the grounding
   file(s) that are an **earlier version** of a document under review, compared against it as
   described in section B. The wizard asks which grounding document, if any, is the earlier
   version; a hand-written manifest names it directly.
2. **Convention:** a `review_targets:` field in `input/conventions/review_mandate.md` names
   the targets, and this tier writes them into the manifest as `source=convention`. From the
   next run on they are read back at tier 1 and this tier is not consulted again, so delete
   `_review_targets.json` after editing `review_targets:` or the edit is silently ignored.
3. **Sidecar + date cutoff:** the existing mechanism. Ingested sidecar grounding files are
   excluded from promotion (integrated mode), and `config/review_scope.json`'s date cutoff
   sorts the rest (documents at or after the cutoff are under review; earlier ones are
   context).
4. **Content inference:** a guarded stub behind `--infer-roles`, off by default. Not
   implemented beyond a placeholder; it logs and leaves files to the date cutoff.

With no manifest and no `review_targets:` field, behavior is identical to the date-cutoff-only
mechanism, so existing workflows are unchanged.

---

## E. The convention system

Conventions are the operator's review framework. They live in `input/conventions/`, and every
file there is parsed at BOOT into `config/convention_registry.json` (markdown, plain text, JSON,
PDF, DOCX and HTML are all accepted, in any number; no file name is required). A convention
set is normally two markdown files, by convention rather than requirement:

- `review_conventions.md`: the operator's review rules, written as headings that may carry
  the operator's own rule ids (for example CONV-DEADLINE, CONV-HEARING,
  CONV-CONFIDENTIALITY). The parser mints the registry id itself (`CONV-001`, `CONV-002`,
  ...) and keeps the operator's heading id as the rule's `category`, which every finding
  reports as `source_rule_id`. Each finding cites at least one registry CONV-* id and carries
  the operator's own id alongside it.
- `review_mandate.md`: the reviewing entity, the engagement scope, and the review
  standard (advisory, grounded, with concrete proposed amendments).

**This repository does not ship a corpus or a convention set in `input/`**; `input/` is not
part of this snapshot (section G, "What's in this repository"). The corpus used to develop
and describe this mechanism was agricultural (one wheat producer-declaration sheet reviewed
against a reference corpus, in English), and that shape is what the paragraphs above
describe, but you supply your own conventions and corpus under `input/` to run a review; the
launcher's intake wizard (section H) walks you through placing them. Four corpora from other
domains DO ship, under `benchmark/corpora/` (section H), with committed answer keys, and are
what this repository's own gate exercises. To review your own domain, place your conventions
and corpus under `input/` (or stage one of the shipped corpora with `tools/stage_corpus.py`);
nothing in `scripts/` is domain-specific.

Sensitivity is also convention-defined. A convention counts as a redaction rule when its
category or its id carries a redaction keyword (`confiden`, `redact`, `privacy`, `pii`), when
its rule text uses a redact verb or prohibition phrasing ("must not contain", "shall not be
published"), or when its parsed action is already `redact`; the local redactor applies the rules
that compile, and redaction intent that fails to compile is warned about, never dropped silently. There is no
engine-side default: with no compiled redaction rule in force, a run hard-stops for a
conscious operator choice (supply a rule, or pass `--no-redaction-override`).

---

## F. The sensitivity model (LAW-IV in practice)

- **Normal mode (default):** the pipeline reviews, flags defects, and proposes amendments.
  Personal data and confidential figures are not scrubbed from the deliverables, and nothing
  scans for them: they surface only if one of your own `confidentiality` / `redaction` CONV-*
  rules makes the review agents flag them. You receive the full output. Use this when the
  documents are not sensitive.
- **Sensitive mode (unreachable until the operator activates the LAW-IV layer):** everything
  in normal mode, plus the local Qwen redactor scrubs operator-marked spans from the output
  before deliverables are finalized. "Applied" means verified absent by a post-apply grep
  gate: a span that survives or cannot be located BLOCKS the deliverable rather than shipping
  it. The whole scrub is gated on `LAYER_ACTIVE` (`scripts/sensitivity_layer/__init__.py`),
  which ships False, so today nothing is scrubbed on any path: a sensitive run submitted to
  the server refuses to start (exit 6), and a sensitive run started from the launcher or the
  intake wizard starts with the layer-inactive override and then skips phase 9.

Sensitive spans are defined by operator conventions, never judged by a model. The full
LAW-IV outbound masking layer (holding spans local and replacing them with typed
placeholders before any network or API call, with every masking appended to
`durable/governance/exposure_ledger.jsonl`) is **built and wired but operator-activated**:
`LAYER_ACTIVE` defaults to False, and that one switch gates three things, not just the network
boundary: outbound masking, the phase-9 deliverable scrub, and the learning engine's
masked-write gate. While inactive, a run hard-gates and refuses to start unless the operator
passes `--sensitivity-layer-inactive-override` (logged). Every launcher path passes it: the
normal run and the server pass it alongside `--no-redaction-override`, and the intake wizard's
Sensitive mode passes it too, withholding only `--no-redaction-override` so the redaction policy
stays on.

The learning engine's masked-write gate is keyed on the same activation switch, not on the
run's sensitivity: with the LAW-IV layer active it stores ids, counts, categories and typed
placeholders and never raw spans (`ontology_capture.mask_field`). While the layer is inactive
(the shipping default) it writes the real content, so the cross-run stores under
`ontology/stores/` are payload-free only once the operator activates the layer.

---

## G. Prerequisites and setup

**Prerequisites:** Python 3.9 (invoked as `py -3.9`), git, API keys (outside the repo),
and, for redaction, the local Qwen model with a GPU strongly recommended.

### Quick start on a fresh clone

1. Clone the repository.
2. Run the launcher, which does steps 3 to 5 below for you:

   ```
   shimmer.bat        (Windows)
   shimmer.sh          (macOS/Linux)
   ```

   It finds Python, creates and activates a local `.venv` (not shipped; built here, on your
   machine, every time), installs the dependencies from `requirements.txt` into it, runs the
   readiness preflight (`scripts/preflight.py`: keys, Qwen, GPU, live model ids), and shows the
   menu described in section H. This is the one command a fresh clone needs to reach a working
   menu; steps 3 to 5 below are what the launcher is doing, spelled out for anyone scripting
   the same setup by hand or debugging why it failed.
3. **API keys, which you must supply; none are shipped.** Place them in an external
   `config.py` OUTSIDE the repository. Shimmer locates it via `$SHIMMER_CONFIG_PATH`, then a
   sibling `../api_keys/config.py`, then the repo-root `.env_path` pointer. ANTHROPIC and
   OPENAI keys are required for the cloud profile (see below for a keyless local-only path);
   BRAVE is optional. Model selection is owned by `config/agent_registry.json`, never by the
   key file.
4. **Documents to review, which you must supply; `input/` is not shipped.** Create
   `input/context/`, `input/conventions/`, and `input/operational/` (the launcher's intake
   wizard does this for you when you choose option [5]; or run `py -3.9 -X utf8
   tools/stage_corpus.py --corpus clinical_reference` to populate `input/` from one of the
   shipped test corpora instead of writing your own). Put your review conventions
   (`review_conventions.md`, `review_mandate.md`, or your own files) in `input/conventions/`
   and your documents plus any reference/grounding material in `input/context/`; the intake
   wizard sorts, dates, and places them, and writes the tier-1 manifest (section D). If you
   only want to see the pipeline run end to end without writing your own review framework,
   staging a shipped corpus (section H, "Test corpora from other domains") is the fastest path
   to a first real run.
5. If you plan a **local-only run** (no cloud API calls, `--backend-profile local`): fetch the
   local checkpoints the profile uses. The redactor is `Qwen/Qwen2.5-7B-Instruct` (full
   precision, sensitive runs only). A `--backend-profile local` run instead uses the two ids in
   `config/local_models.json`, today `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` (producers) and
   `unsloth/Phi-3.5-mini-instruct-bnb-4bit` (auditors); the pre-quantised pair keeps peak host
   RAM at the 4-bit size. All three need torch and transformers and run offline. This is the
   only step 3-5 you can skip entirely for a first, keyless, local-only smoke test, since local
   checkpoints are fetched automatically at first use (next paragraph) rather than needing to
   be fetched by hand.

Setup itself downloads no model weights unless you set `SHIMMER_QWEN_PULL=1`, though it may
fetch the large CUDA torch wheel. The multi-gigabyte local checkpoints and the multilingual
embedding model are fetched at first use, so the first run is slow. Do not interrupt it; later
runs reuse the cached weights, genuinely offline: `agent_wrapper.py`'s real loader
(`_load_qwen`, the function every local-profile agent call actually goes through) now passes
`local_files_only=True` on every `from_pretrained` call, matching `server.py`'s own pre-run
check, which already resolves the same model ids the same way and refuses to start a run if
either is missing. Found live, on a real run: before this fix, that promise was one-sided,
the pre-run check said "cached, you're fine" while the real loader reached the hub on every
single call anyway, and a routine network hiccup turned into a fatal error killing the run's
first agent call, on a machine where the weights were genuinely, fully cached. A container on
a rented machine, or any closed network, would have died the same way while being told
everything was fine. The embedding model gets a narrower version of the same fix: it tries
`local_files_only=True` first (so the common, already-cached case never touches the network),
falling back to a network-permitted load only on a genuine cache miss, since unlike the
generation models nothing checks this one's cache before a run starts, and "fetched at first
use" above is real, intended behavior for a genuine first run, not something to break.

**What a first run creates that this repository does not ship**: `.venv/` (the launcher),
`input/operational/` gets populated from `input/context/` (the pipeline, every run),
`output/runs/<id>/` (the pipeline, one per run), `durable/` (BOOT, on first run, learned
reference assets and governance state), and `ontology/stores/` (the pipeline, phase 8, end
of every run: `graph.json` and `gnn_state.json`). None of these are source; none of them
need to exist before you start; the tools that need them create them.

`ontology/stores/` is unfinished, not dormant, and this is stated plainly rather than left
for a reader to assume from its place in the architecture: it writes real state every run
(a graph of documents, findings and the rules they cite, plus a small autoencoder fit over
that graph's structure) but nothing in the pipeline reads either back. No agent payload, no
Finding-producing code, and no phase before 8 opens `graph.json` or `gnn_state.json`; the
only other consumers are the module that builds the next run's graph from the last one (a
write-path detail, not a review-time read) and the gate's own non-mutating self-tests. It
is real, executed machinery, not a stub, but it is a write with no reader yet, and should be
read as exactly that rather than as a working cross-run relevance signal the review already
draws on.

The `[ontology_gnn]` line each run prints to stdout (`scripts/ontology_gnn.py`) now says
this plainly too, not only in this README: it used to lead with `loss=`, `weight_delta=`
and `device=`, the exact vocabulary of a real training run, with the honest caveat sitting
after them as a parenthetical a reader's eye skips past the numbers to reach. It now leads
with the words, not the numbers: a self-supervised reconstruction fit with no Tier-2 signal
yet, explicitly not a trained relevance model. The computation this logs is unchanged, same
values, same `summary` dict returned to its caller; only what the words say about what those
values mean was fixed.

To install dependencies without the launcher (for example, in a CI environment that manages
its own venv):

```
py -3.9 -m pip install -r requirements.txt
```

Declared dependencies: anthropic, openai, transformers, pypdf, python-docx, lxml,
beautifulsoup4, fpdf2, sentence-transformers, numpy, langdetect, ddgs, torch, fastapi,
uvicorn[standard], python-multipart. `preflight.py` installs the two small optional libraries
(beautifulsoup4, langdetect) if missing, and pip-installs any other missing Qwen-backend
library except torch (`_attempt_lib_pull`), whose correct wheel is platform and CUDA
specific.

---

## H. Running Shimmer (four entry points)

### 1. The launcher (recommended starting point)

`shimmer.bat` (Windows) or `shimmer.sh` (macOS/Linux) takes you from a fresh clone to a
running review: it finds Python, builds and activates a local `.venv`, installs
dependencies, runs the readiness preflight, then shows a menu:

```
[1] Run a review (CLI)      -> asks Review or Draft. Review runs the intake wizard, then the
                               pipeline; Draft asks for the question and runs the pipeline
                               directly with --task draft (plus the two override flags, so a
                               launcher draft is declared non-sensitive)
[2] Open the chat interface -> scripts/chat.py
[3] Start the server        -> scripts/server.py
[4] Run the verify gate     -> scripts/verify_session1.py
[5] Import documents         -> the intake wizard only: place files, set the cutoff, and write
                               the tier-1 review-targets manifest (no run)
[Q] Quit
```

The intake wizard scans a folder, classifies each file (conventions, config, sidecar, or
document; anything else is skipped), prints and optionally edits the date cutoff, lets you
choose normal or sensitive mode, asks the parallelism and document-count limits, then places
the files and finally asks which documents are under review and which file, if any, is an
earlier version of one of them.

### 2. The chat interface

`python scripts/chat.py` opens a small tkinter window. When the local Qwen model is
available it parses plain-language instructions ("draft me a memo on whether X is abuse of
dominance"; "review ./my_docs in normal mode"); otherwise it falls back to a command mode
(`help`, `status`, `review <folder>`, `draft a memo on <topic>`, `import <folder>`,
`set cutoff <date>`, `normal mode` / `sensitive mode`, `why did you flag <term>`, `quit`).
It confirms before running anything, streams pipeline progress into the window, and after a
run answers questions by searching the latest run's bus log. It is stateless across
sessions.

### 3. The pipeline directly

```
py -3.9 scripts/pipeline.py --non-interactive
```

Key flags: `--task review|draft`, `--question "..."` (the brief for draft, or an optional
framing question for review), `--mode standalone|integrated`,
`--max-docs N`, `--max-concurrent-docs N` (default 4), `--backend-profile cloud|local`
(`local` runs all inference on local models with no provider API call, and also sets
`SHIMMER_BACKEND_PROFILE` for the modules that read it), `--review-mode wide|paired` and
`--pairs-per-unit N` (see "The two review modes"),
`--sensitivity-layer-inactive-override` (declare a non-sensitive run so it starts with the
masking layer inactive; logged), `--no-redaction-override` (run with no redaction; logged),
`--amendment-polish` (optional model wording pass, OFF by default; see "How an amendment gets
written"),
`--infer-roles` (enable the tier-4 stub), `--output-dir DIR`, `--run-objectives "..."`,
`--skip-model-check`, and the snapshot controls (`--save-snapshot` / `--load-snapshot` /
`--reset-snapshot` / `--list-snapshots`). Run `--help` for the full list.

For a local run, prefer the wrapper in `tools/`:

```
py -3.9 -X utf8 tools/run_local_demo.py --non-interactive [pipeline args...]
```

It starts the pipeline in-process (the pipeline module's filename is denied in shell
commands in this repository, so a local run is started by importing the module), adds
`--backend-profile local` if the caller named none, sets `SHIMMER_BACKEND_PROFILE` to match,
passes everything except its own three flags (`--sample-file`, `--sample-seconds`,
`--gpu-memory-fraction`) through unchanged, and samples RAM and VRAM to a JSON file that is
**rewritten after every sample**,
so the peaks survive a kill. A run the OS terminates for memory is exactly the run whose peak
memory you wanted. `tools/run_local_demo.ps1` is the PowerShell entry to the same thing.

Each run writes into its own folder under `output/runs/`, named for readability as
`<YYYY-MM-DD>__<slug>` (the draft question for a draft run, or the document count and type
such as `5doc_review` for a review run); server-pinned runs keep their submitted name.
Inside, `deliverables/` holds one subfolder per document, named after the document, plus a
top-level `_run_summary.md` index (what was reviewed, amendments per document, total cost,
and a link to each subfolder; with an earlier version declared, how many terms were compared
and how many are absent since it, and the review question when one was given). Each document
subfolder holds `tracked_changes.docx`,
`review_data.json`, `review_findings.md`, `grounding_summary.md`, `document_summary.md`, and
`reviewed_document.md` (the doc-name prefix is dropped since the folder already names the
document). With an earlier version declared, `document_summary.md` and `review_findings.md`
both carry a "Compared with the earlier version" section (moved toward, moved away, changed,
unchanged, absent, outside a stated band now, not comparable) and `review_data.json` carries
the same records under `prior_comparisons` with `prior_refusals` and `prior_orphans`; the
amendments list is untouched by them. A draft run also keeps the generated memo in its
subfolder as `memo.md`. `audit/`
holds the editorial and contract-violation artifacts, plus `pairing_map.json` (which rules
could apply to which units and why, the `band_conditions` record described in section B, and
per unit the `prior_comparisons` block: earlier figures found, every check made, every
refusal), and `logs/` holds the append-only
`agent_bus.jsonl`, the cost tracker, and the run summary. Runs never overwrite
each other. Follow a run live with `py -3.9 scripts/bus_viewer.py --follow`.

### 4. The single-agent harness (`scripts/harness/`)

A whole pipeline run is a bad instrument for asking why one agent produced nothing. The
harness runs **one agent, one unit of material, one rule, one backend**, on either profile:

```
py -3.9 -X utf8 scripts/harness/run_agent.py \
    --agent PRACTICE_AUDITOR --profile local \
    --unit-file unit.txt --unit-id u01 \
    --rule-file rule.txt --rule-id CONV-001 \
    --out results.json
```

`--profile local` uses the same checkpoints, loader and role anchor as
`--backend-profile local`; `--profile api` uses the agent's own cloud spec from
`config/agent_registry.json`, which stays the sole owner of model choice (`--api-backend` and
`--api-model` override it for a controlled comparison and the override is recorded in the
result). `--agent` repeats for a batch.

The harness does **not** build its own prompt: it builds the wrapper the pipeline builds,
with the pipeline's own `_build_wrapper`, so the bytes reaching the model are the bytes the
pipeline would send for the same inputs. Gate check 146 holds that property in place, and
fails if this module ever grows its own prompt assembly. Nothing here writes the prompt or
the unit text to disk; results carry the model's output, its length and its hash.

Two companions: `probe_arithmetic.py` asks whether the model can do the arithmetic at all
with no review framing (no agent identity, no constitution, no conventions, no document, no
output contract; figures generated from a seeded random source, never read from the
operator's corpus), and `score_envelope.py` scores a batch of `run_agent.py` results for
envelope compliance, verdict accuracy and latency. An empty but valid envelope counts as
compliant, because that is what the contract says.

### Benchmarking (`benchmark/keys/`, never committed)

`benchmark/keys/` holds the answer key, the control document, the ledger scripts and the
frozen scorer for measuring recall against a corpus with known planted defects. It is
**gitignored** and never committed, so it is absent from every clone of this repository, not
only this public snapshot; an operator who wants recall measurement writes their own answer
key and corpus under `benchmark/keys/` locally. Only the scorer reads the key. Nothing in
`scripts/`, `config/` or `tests/` may contain a planted benchmark figure: gate check 145
(the contamination probe) scans those directories plus the harness fixtures for the key's
figures and fails if one appears, which is what makes a recall number mean anything.
**This repository does not ship a `tests/` directory**, so check 145 fails here with "no
test fixtures to scan" (see section L) until an operator adds one; that failure says the
probe has nothing to check, not that contamination was found.

---

### Test corpora from other domains (`benchmark/corpora/`)

A domain-agnostic system that has only ever been run on one corpus has not been tested for
domain agnosticism. `benchmark/corpora/` holds corpora built from **real public data in other
domains**, each with `context/` (the reference material and the document under review),
`conventions/` (operator rules) and a committed `answer_key.json` written before any run, which
`tools/score_corpus.py` scores a run against. Unlike `benchmark/keys/`, these keys are in the
repository, because the figures they carry are not planted in the operator's own corpus. They sit
outside the vocabulary probe's scanned roots, so their vocabulary stays operator input.

| corpus | source | what it tests |
|---|---|---|
| `clinical_reference` | the published [reference ranges for blood tests](https://en.wikipedia.org/wiki/Reference_ranges_for_blood_tests) | the band path on unfamiliar vocabulary, en-dash ranges, and a unit written in its own column rather than the header |
| `catalogue_records` | the [Dublin Core Metadata Element Set](https://www.dublincore.org/specifications/dublin-core/dces/) | a document with **no quantities anywhere**, so arithmetic can settle nothing and every rule is about presence, vocabulary or agreement between fields |
| `negotiation_r3_to_r4` | company offers of 19 and 31 October 2024 in a real 2024 labor negotiation, real publicly reported figures with the company and the union replaced by obvious placeholders (Company A, Union B) before publication | the **round-N comparison**: the 19 October offer declared as the earlier version of the 31 October offer, a mandate with bands, currency figures written `$7,000`, a label that disappears between rounds and so exercises the absent path (since the source verification of 2026-09-08 the corpus's own answer key records that `absent_since_prior` record as FALSE about the negotiation: the $12,000 bonus combines the earlier $7,000 bonus and the $5,000 401(k) lump sum, so nothing was withdrawn), and the review question |
| `negotiation_r2_to_r3` | the offers of 23 September (press-reported) and 19 October 2024 in the same negotiation | the same mechanism one round earlier: nothing was dropped between these two offers, so no `absent_since_prior` record should appear. Terms that first appear in the later offer produce neither a record nor a refusal, which the key now records as a defect rather than a property: a term that ARRIVES between rounds is structurally invisible, and the per-year schedule of the 23 September offer was reported on the day and was omitted from the corpus |

The two negotiation corpora carry their manifest (`_review_targets.json` with `prior`) inside
`context/`, so staging one declares the earlier version as well.

Stage one with `tools/stage_corpus.py`, which moves the current `input/` contents into a
timestamped holding directory first and restores them afterwards, and carries no domain
vocabulary of its own:

```
py -3.9 -X utf8 tools/stage_corpus.py --list
py -3.9 -X utf8 tools/stage_corpus.py --corpus clinical_reference
py -3.9 -X utf8 tools/stage_corpus.py --restore output/staged_inputs/<holding-dir>
```

A corpus whose conventions declare no confidentiality rule hard-stops the run by design
(section F); pass `--no-redaction-override` to declare the run redact-nothing, logged.

**What the first unseen corpus found in its first ten minutes**, none of which the original
corpus could have exposed: the unit was read only from a table header, so a unit column beside
the figure dropped every band; `"1 450 to 1 990"` with no column unit was not recognised as a
range at all, because `to` was read as the first bound's unit; `135-145` with an ASCII hyphen
parsed as `135` and `-145`; a value *inside* its band produced no check, so Python settled the
pair and then asked a model anyway (35 calls for 29 pairs); and the convention parser's English
keyword table silently reclassified an operator rule whose slug contained the word "value",
overwriting the operator's own id and losing attribution for every finding under it. Scoring
the run found three more: the paired review's **computed findings were never posted to the
bus**, so `GET /findings` and any bus reader were blind to the findings Python actually made;
a header's unit parenthetical leaked into its label unless the unit happened to be two letters,
so the sum check silently never ran for `Extent (zed)`; and an identifier column with no digits
was reported as a missing field. The second corpus, with no figures anywhere, killed a run with
one malformed model reply (`parsed` arrived as a bare list), and the review of the negotiation
design found two more ASCII-only regexes (`_LABEL_LINE`, `needed_fields`) that the R3 Unicode
fix had not reached. All eleven are fixed; nine have a gate check, and the two Unicode label defects found in the
parallel design review do not. That is the argument for a second corpus, and a third.

## I. The server and the corpus ingestion contract

`scripts/server.py` is a thin, token-gated FastAPI dock: one collaborator hands grounding
cases to Shimmer, starts a run, watches the queue, and pulls results, all over the network,
without touching the code or terminal. It is a connecting dock for one collaborator, not a
hardened public service.

**Pilot posture, stated plainly.** A single shared bearer token behind a temporary tunnel is
a PILOT posture. It is not a customer deployment posture. One secret is held by everyone who
has it: there are no user accounts, no per-user credentials, no way to tell two callers
apart in the logs, no revocation short of restarting the server with a new hash, no rate
limiting, no audit trail tied to a person, and no expiry. Anyone who obtains the token can
submit runs that spend money on the operator's API keys and can download any run's
deliverables. That is an acceptable trade for one named collaborator over a link the
operator opens and closes deliberately. It is not acceptable for a paying customer, a second
organization, or an address left running unattended. Real customer use needs per-user
identity, revocable credentials, request attribution and a deployment that outlives a laptop.
None of that is built, and none of it should be assumed from the presence of a token gate.

### Connecting to the API, step by step

What a consumer program actually does, in order. Every route is listed in the route table
below, and gate check 167 fails if that table and the app disagree.

**Step 0, before you connect: is it up, and what will it do?**

```
curl -s "$BASE/health"
# -> {"status":"ok","version":"1.0","backend_profile":"local","default_review_mode":"paired"}
```

`/health` needs no token. It tells you the two things you must know before submitting:
which backend the server runs on (`local` = no provider API calls, `cloud` = paid), and
which review mode a submission gets if you do not name one. Everything after this except
`/console` needs `Authorization: Bearer <token>`; without it every gated route returns 401.

**Step 1, submit the work.**

```
curl -s -X POST "$BASE/submit" \
  -H "Authorization: Bearer $TOKEN" \
  -F "task=review" -F "review_mode=paired" \
  -F "files=@./declarations.md" -F "files=@./_corpus_ingest.json"
# -> 202 {"run_id":"20260907_161514__41cebd", "status":"queued",
#         "task":"review", "sensitive":false, "review_mode":"paired", "files":[...]}
```

Keep the `run_id`: every later call is keyed on it. `review_mode` is optional and defaults as
`/health` said; an unrecognised value is a 400, not a silent fallback. Uploads are validated
against the corpus ingestion contract before anything is queued, and an invalid bundle comes
back as a 400 with the violation report rather than a failed run twenty minutes later.

**Step 2, poll while it works.**

```
curl -s "$BASE/runs/<run_id>" -H "Authorization: Bearer $TOKEN"
# -> {"state":"running", "outcome":null, "progress":"phase=5.5/9 doc=1/1 agent=PRACTICE_AUDITOR ...",
#     "review_mode":"paired",
#     "pairs_planned":104, "pairs_arithmetic_only":99, "model_calls":13}
```

Poll every 20 to 30 seconds. The three counters move DURING the run, so a caller can show
real progress rather than a spinner: `pairs_planned` is how many (unit, rule) pairs the map
decided could apply, `model_calls` is how many model calls have been made so far, and
`pairs_arithmetic_only` is how many pairs Python settled without asking a model. Stop polling
when `state` leaves `queued`/`running`/`awaiting_approval`; see the status table below for
what each terminal `outcome` means, and note that `governance_stop` is a distinct outcome
from `crashed`, never rendered the same way.

**Step 3, read the structured review.** This is the part a program consumes.

```
curl -s "$BASE/runs/<run_id>/findings" -H "Authorization: Bearer $TOKEN"
```

```json
{"run_id": "...", "count": 5, "findings": [
  {"agent": "PRACTICE_AUDITOR", "doc_id": "declarations",
   "rule_id": "CONV-005", "source_rule_id": "CONV-A01", "unit_id": "u07",
   "relation": "above_band", "record_verdict": "irregular",
   "value_a": 16.0, "unit_a": "qm/zed", "value_b": 7.1, "unit_b": "qm/zed",
   "source_refs": ["REF-0051"],
   "explanation": "The computed value is 16.0 qm/zed, above the reference bound of 7.1 qm/zed."}
]}
```

Typed, flat, and machine-readable: no prose parsing. `rule_id` is the registry's id and
`source_rule_id` is **the operator's own id for the same rule**, which is what lets a caller
reconcile a finding against the rulebook the operator actually wrote. `source_refs` cite the
reference passage the finding rests on. Each object also carries `item_id` and `revision`
(INFRA-037 supersession) and the four INFRA-044 comparison fields `field_label`, `delta`,
`band_distance_change` and `provenance`, which the example above omits. Superseded revisions are
already removed. An empty list with 200 means "nothing found", which is different from 404, "no
such run".

**Step 4, if you need to justify a finding, ask why those rules were applied.**

```
curl -s "$BASE/runs/<run_id>/pairs" -H "Authorization: Bearer $TOKEN"
```

Returns the pairing map: per document the counts, and per unit the rules paired and rejected,
each with the reason recorded before any verdict fired, plus the rule ids left undecided (ids
only, no reason). Carries no document text. This is the audit trail for "why was this rule checked against this section, and why
was that one not".

**Step 5, fetch the human deliverable if a person needs it.**

```
curl -s "$BASE/runs/<run_id>/deliverables" -H "Authorization: Bearer $TOKEN" -o results.zip
```

A zip in the BP-16 layout: one folder per document with `review_findings.md`,
`review_data.json`, `tracked_changes.docx`, the two summaries and the reviewed document, plus
a top-level `_run_summary.md`. Not gated on completion: it zips whatever exists under
`deliverables/` right now (checking `X-Shimmer-Partial` or `documents[]` on `GET
/runs/<run_id>` tells you whether that is everything or only part of it). To fetch one
document alone instead of the whole run, use `$BASE/runs/<run_id>/deliverables/<doc_id>`. Use
`/runs/<run_id>/findings` and `/runs/<run_id>/pairs` for a program and
`/runs/<run_id>/deliverables` for a reader.

**Step 6, answer a governed decision if one is waiting.** Rare, and only when the pipeline
pauses on purpose (a deprecated model, a constitution amendment):

```
curl -s "$BASE/approvals" -H "Authorization: Bearer $TOKEN"
curl -s -X POST "$BASE/runs/<run_id>/approval" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision":"APPROVE","rationale":"..."}'
```

The server records the decision and nothing more; it never evaluates it. The response (202)
carries `recorded: true` and the run's `run_state` as it stood just before the write, never a
claim that the decision was approved: poll `GET /runs/<run_id>` afterward to see what the
pipeline actually did with it.

**Notes a caller needs.** One job runs at a time and the queue drains in submission order, so
`GET /runs/<run_id>` may report `state: "queued"` behind someone else's run; `GET /runs` shows
the whole picture. Run state is written to disk on every transition, so a server restart keeps
the run history: the in-flight run comes back as `interrupted` internally (`state: "stopped"`,
`outcome: "crashed"` on `GET /runs/<run_id>`), and a run still `queued` at restart keeps its
record but loses its staged uploads, so resubmit both. Every route taking
a `run_id` validates it against the server's own mint format and answers 404 for anything
else, so a malformed or guessed id can never reach a path expression.

### Server quickstart (two terminals)

**Terminal 1, the server (stays running).**

```
# 1. activate the venv the launcher created
.venv\Scripts\activate                 # Windows
source .venv/bin/activate               # macOS/Linux

# 2. mint a token + its sha256 hash ONCE (the plain token is never stored, only the hash)
python -c "import secrets, hashlib; t=secrets.token_hex(32); print('Token (give to the collaborator):', t); print('Hash (set as SHIMMER_TOKEN_HASH):', hashlib.sha256(t.encode()).hexdigest())"

# 3. set the hash and start the server
set SHIMMER_TOKEN_HASH=<hash>           # Windows;  export SHIMMER_TOKEN_HASH=<hash> on macOS/Linux
python scripts/server.py
```

Hand the token (the first string, never the hash) to the collaborator out of band, once. For
remote access, expose the local port with a temporary tunnel and share the public https URL
it prints:

```
cloudflared tunnel --url http://localhost:8000
```

**Terminal 2, the client (submit, poll, download).** On Windows PowerShell, use `curl.exe`
(not `curl`, which is an alias for `Invoke-WebRequest` with different syntax). All routes are
Bearer-token gated. The line continuations below are bash; on Windows `cmd` put each `curl`
on one line.

```
TOKEN=<the token from Terminal 1>
BASE=http://localhost:8000              # or the https URL the tunnel printed

# review run: upload one or more documents PLUS the ingestion sidecar (mandatory: a bundle
# with no _corpus_ingest.json is rejected with 400, violation sidecar_present)
# review_mode is optional; omitted it is paired on the local profile, wide on cloud
curl -s -X POST "$BASE/submit" \
  -H "Authorization: Bearer $TOKEN" \
  -F "task=review" -F "review_mode=paired" \
  -F "files=@./doc1.md" -F "files=@./doc2.md" -F "files=@./_corpus_ingest.json"
# -> 202 {"run_id":"<id>","status":"queued","task":"review","sensitive":false,
#         "review_mode":"paired","files":[...]}

# draft run: a question instead of files
curl -s -X POST "$BASE/submit" \
  -H "Authorization: Bearer $TOKEN" \
  -F "task=draft" \
  -F "question=Is a 20 working-day merger review period consistent with best practice?"

# poll until state leaves "queued"/"running"/"awaiting_approval"
curl -s "$BASE/runs/<run_id>" -H "Authorization: Bearer $TOKEN"

# the structured review: typed Finding records, and the pairing map behind them
curl -s "$BASE/runs/<run_id>/findings" -H "Authorization: Bearer $TOKEN"
curl -s "$BASE/runs/<run_id>/pairs"    -H "Authorization: Bearer $TOKEN"

# download the deliverables zip (whatever exists so far; check X-Shimmer-Partial)
curl -s "$BASE/runs/<run_id>/deliverables" -H "Authorization: Bearer $TOKEN" -o results.zip
```

`/runs/<run_id>/findings` and `/runs/<run_id>/pairs` are the machine-readable answer;
`/runs/<run_id>/deliverables` is the human one. A run with no findings yet is a 200 with an
empty list, not a 404: "nothing found" and "no such run" are different answers and a poller
must be able to tell them apart.

The zip preserves the BP-16 layout: one folder per document plus the top-level
`_run_summary.md` (section H). Jobs run one at a time; `/runs/<run_id>/deliverables` is not
gated on completion (api STEP B4): it zips whatever documents are done so far, and says so
via `X-Shimmer-Partial` and the filename when the run has not finished successfully.

**Environment variables.** Most are read once at startup and the resolved subset prints to
stderr; `SHIMMER_TOKEN_HASH` is read per request, `SHIMMER_BACKEND_PROFILE` is read live on
every call that needs it, and the two rows marked as read by the pipeline subprocess are read by
the child, not this process:

| Variable | Default | Effect |
|---|---|---|
| `SHIMMER_TOKEN_HASH` | required | sha256 hash of the access token; the server refuses to start without it |
| `SHIMMER_MODE` | `integrated` | pipeline `--mode`; integrated activates the ingested-corpus promotion exclusion |
| `SHIMMER_TASK` | `review` | default task for `/submit` (`review` or `draft`) |
| `SHIMMER_SENSITIVE` | `false` | false passes the layer-inactive and no-redaction overrides |
| `SHIMMER_MAX_DOCS` | `4` | `--max-concurrent-docs` |
| `SHIMMER_PORT` | `8000` | uvicorn port |
| `SHIMMER_HOST` | `0.0.0.0` | bind interface (a tunnel needs all interfaces) |
| `SHIMMER_AUTO_CLEAR` | `true` | remove ingested grounding files (and any system_draft artifacts) after each run |
| `SHIMMER_OUTPUT_DIR` | `output/runs/` | per-run output root |
| `SHIMMER_CONVENTION_REGISTRY` | `config/convention_registry.json` | custom path to the convention registry `_pairs_view` and `GET /rules/{rule_id}` read for a rule's operator-own id and its own text; overridable for the same reason `SHIMMER_OUTPUT_DIR` is, a test harness needs its own throwaway registry, never the real repository's |
| `SHIMMER_LOG_LEVEL` | `info` | uvicorn log level |
| `SHIMMER_RUN_TIMEOUT_S` | `0` | seconds before a run's pipeline subprocess is terminated then killed; `0` means unbounded (prior behavior). On expiry the job is marked `failed` with a timeout reason and `exit_code: null`; cleanup still runs |
| `SHIMMER_LOCAL_RUN_TIMEOUT_S` | `7200` | overrides `RUN_TIMEOUT_S` when `SHIMMER_BACKEND_PROFILE=local`. Local inference is far slower than cloud API calls; 2 hours is the default. `0` means unbounded |
| `SHIMMER_BACKEND_PROFILE` | (unset) | `local` selects the local-only backend profile (all inference on local models, no provider API calls). Unset or any other value uses the default cloud profile |
| `SHIMMER_PROVIDER_TIMEOUT_S` | `600` | per-request wall-clock timeout (seconds) passed to the Anthropic and OpenAI clients; read by the pipeline subprocess, not the server process itself |
| `SHIMMER_MAX_UPLOAD_MB` | `25` | per-file upload size cap in megabytes for `/submit` |
| `SHIMMER_MAX_UPLOAD_TOTAL_MB` | `200` | whole-submission upload size cap in megabytes |
| `SHIMMER_MAX_UPLOAD_FILES` | `50` | max number of files accepted in one `/submit` |
| `SHIMMER_APPROVAL_WAIT_S` | `3600` | read by the pipeline SUBPROCESS (not this process): how long the `--operator-channel file` handler waits for a human's `approval_decision.json` before defaulting to `DEFERRED` |

**Routes.** This table is the complete set the app registers; gate check 167 fails if it and
the app disagree in either direction.

Every run-scoped route lives under `/runs/{run_id}/...` (api STEP B5): `/status/{run_id}`,
`/queue`, `/results/{run_id}`, `/findings/{run_id}`, `/pairs/{run_id}` and
`POST /approvals/{run_id}` were retired outright, each already fully replaced by a route below.
There is no back-compat alias for any of the retired names; nothing else calls this server yet.

| Method | Route | Auth | Returns |
|---|---|---|---|
| `POST` | `/submit` | token | 202 and a run id. Multipart `files` + `task` + optional `question`, `sensitive`, `review_mode`. Draft requires a question, review requires files. Rejects an over-count submission with 400 before any file is written, and an oversized one before it is queued (its staging directory is deleted), per the upload caps above. |
| `GET` | `/runs` | token | Every run as the complete run resource (see `/runs/{run_id}` below), oldest submission first. |
| `GET` | `/runs/{run_id}` | token | api STEP B1/B2/B3/B4/B5: one run's complete record in a single call: `state` (`queued` / `running` / `awaiting_approval` / `stopped` / `cancelled`), `outcome` (populated once `state` is `stopped` or `cancelled`: `succeeded` / `governance_stop` / `crashed` / `timed_out` / `cancelled`), `stop_reason`, `pending_approval` (populated once `state` is `awaiting_approval`: `topic`, `message`, `payload`, `asked_at`, `default_on_timeout`, `timeout_at`), `documents` (per-document `status` and `deliverables_url`, a REAL fetchable route once that document is done, not a display string), `log_url`, `has_log` (whether `<run>/logs/pipeline_stdout.log` exists yet, checked on disk on every call, so a caller can say plainly whether there is a log to read before ever calling `log_url`, rather than discovering a 404 only after asking), plus `task`/`submitted_at`/`started_at`/`completed_at`/`exit_code`/`error`/`progress`/`files`/`sensitive`/`review_mode`/`question`. Does **not** carry the raw internal `status` string (dropped in api STEP B5: `state`/`outcome`/`stop_reason` is the sole vocabulary here, so a caller never has to reconcile two descriptions of the same run). |
| `GET` | `/runs/{run_id}/findings` | token | The run's typed **Finding records** as JSON (section B), including the ok-verdict prior-version records with `field_label`, `delta`, `band_distance_change` and `provenance`; filter on `relation` in `moved_toward` / `moved_away` / `changed_from_prior` / `unchanged_from_prior` / `absent_since_prior` to answer the round question by program. |
| `GET` | `/runs/{run_id}/pairs` | token | The run's **pairing map**: counts, and per unit the rules paired / rejected with the reason for each plus the undecided rule ids (ids only, no reason), and per unit `prior_hit_count`, `prior_check_count` and `prior_refused_count` (integers only). No document text. Each paired/rejected entry now also carries `source_rule_id` (the operator's own id for that rule, `finding_record.source_rule_id_for`, the same lookup a Finding record already uses), so a rule reads the same identifier here as it does in `/findings`, never the registry's bare number alone. |
| `GET` | `/runs/{run_id}/amendments` | token | console fresh-eyes addition: the run's proposed corrections, read from every DONE document's own `deliverables/<doc_id>/review_data.json` (BP-16), the same master file the archive's `review_findings.md`/`tracked_changes.docx` are pure renders of. Per amendment: `original_text` (the document's actual passage, since the source fix in `paired_review.py`'s `amendment_from_finding`; a run produced before that fix still carries the old shape, the bare unit id, on disk, flagged by `original_text_is_passage: false` rather than presented as the real passage), `proposed_text` (`null` unless a model or `--amendment-polish` supplied one), `source_rule_id` (the operator's own id, falling back to `convention_ref` only when absent, the same rule every rule id on this surface follows), `comment` (the reasoning, required by both the computed and model-drafted contracts), `unit_id_repaired_to` (`null` unless the boundary repair below fired), plus `finding_unit_id`/`finding_rule_id` to join back to the Finding it corrects. `200` with an empty list, not an error, when no document has finished yet or none produced an irregular finding. A real cloud run against a benchmark corpus found a second, real gap in the source fix itself: `unit_texts` is keyed by the pipeline's own `split_units` id (`u02-record-cat-birch`), but a WIDE-mode agent (`PRACTICE_AUDITOR`) was writing a Finding's `unit_id` as the document's own identifier for the record it described (`CAT-BIRCH`), never told which id space to use, so the lookup silently missed for every wide-mode finding. Closed at three layers: `pipeline.py`'s convention-review payload now carries `document_units` (the real id/title list) to both convention-review agents, `config/agent_contracts.json`'s `finding_record.says.unit_id` now tells them to copy from it verbatim, and `amendment_from_finding` still tries one narrow, structural second chance (`_repair_unit_id`) for whatever a model gets wrong anyway: the miss-shaped id found written inside exactly one unit's own text, case-insensitively. A single unambiguous match is used and recorded as `unit_id_repaired_to`; zero or multiple matches refuse, same honest fallback as before, never guessed. |
| `GET` | `/runs/{run_id}/amendment-refusals` | token | A real, irregular finding the pipeline could not turn into an amendment, named plainly rather than left to vanish. Found live: PRACTICE_AUDITOR wrote genuinely irregular findings (real `relation`, real `record_verdict: irregular`, a real explanation) whose rule id landed under a field name `amendment_from_finding` did not yet recognise, since `config/agent_contracts.json` used to declare a different rule-id field name per agent (`procedure_id`, `conv_id`, `rule_id`, `convention_ref`, four names for one concept); before this route and its underlying fix, every one of those findings was silently dropped, with nothing on the bus, in a deliverable, or here, saying it had ever existed. Fixed at the source (`finding_record.resolved_rule_id`, one shared resolver checking all four names, used by `amendment_from_finding` and its dedup key), and this route exists for whatever a future finding still cannot be built from: `paired_review.ensure_amendments_for_findings` takes an optional `refusal_sink`, and `pipeline.py` posts whatever lands in it as a distinct bus event (`AMENDMENT_REFUSED`), never Finding-shaped, so it is correctly invisible to `/findings` (a refusal is not a finding) while still reachable here. Per refusal: `doc_id`, `unit_id`, `rule_id` (the resolved value, if any), `reason`, and the source finding's own `relation`/`explanation`. `200` with an empty list, not an error, when nothing was refused, the common case. Rendered in the console as its own section, disappearing when empty, same discipline as every other content-dependent section on this surface. |
| `GET` | `/rules/{rule_id}` | token | console fresh-eyes addition: one rule's own text as the operator wrote it, from the current `config/convention_registry.json`. Not run-scoped, a rule's text does not vary per run. Matches by either id: the registry's own (`CONV-007`) or the operator's own (`CONV-A02`). Returns `id`, `source_rule_id`, `rule` (the operator's own text), `severity`, `action`, `source_file`, `source_location`. `404` with a distinct `detail` ("no rule with this id in the current registry") when the current registry, which regenerates at BOOT and can differ from whatever was in force when a citing run executed, has no such rule; that mismatch is itself informative, not hidden behind a generic not-found. |
| `POST` | `/runs/{run_id}/cancel` | token | api STEP B2: stops a run. A queued job is removed before it ever starts; a running job's subprocess is terminated (then killed). Both land on `state="cancelled"`. `409` if the run is already in a terminal state (including already cancelled), refused with a reason naming its actual state, not a silent no-op. `404` for a malformed or unknown `run_id`. Deletes nothing on disk. |
| `POST` | `/runs/{run_id}/approval` | token | api STEP B3: records a human's decision on the run's pending governed question. Body `decision` + `rationale`; writes `<run>/audit/approval_decision.json` atomically and **nothing else**, never evaluates whether the decision is an approval (that stays entirely with `model_registry`/`constitution_guard`, read back by the pipeline subprocess's own poll loop). `202`, never `200`: the response carries `recorded: true` and the run's `run_state` as it stood the instant *before* the write, and never claims the decision was approved, only that it was recorded. `404` for a malformed `run_id` or one with no pending approval; `409` if this approval was already answered (a decision file already exists); `400` if `decision` is missing or empty. This is the sole route that answers a pending approval (api STEP B5 unified it with the retired `POST /approvals/{run_id}`, which wrote the same file but returned `200` with a thinner body and no repeat-answer guard). |
| `GET` | `/runs/{run_id}/deliverables` | token | api STEP B4: a zip of whatever exists under `deliverables/` right now, not gated on the run being complete (`GET /runs/{run_id}`'s own `documents[]` already says which documents are ready). May be **partial**: carries `X-Shimmer-Partial: true`/`false` and names it in the filename (`..._partial.zip` vs `..._deliverables.zip`) whenever the run did not stop with `outcome=succeeded`. `404` for a malformed/unknown `run_id` or one with nothing under `deliverables/` yet. |
| `GET` | `/runs/{run_id}/deliverables/{doc_id}` | token | api STEP B4: a zip of ONE document's own deliverables folder, what `documents[].deliverables_url` on `GET /runs/{run_id}` points at. `404` for a malformed/unknown `run_id`, or a `doc_id` this run has no finished folder for (whether it never existed or is simply not done yet; `GET /runs/{run_id}`'s `documents[]` is where a caller learns which). |
| `GET` | `/runs/{run_id}/log` | token | api STEP B4: the run's complete merged stdout/stderr as `text/plain`, streamed from `<run>/logs/pipeline_stdout.log`, what `log_url` on `GET /runs/{run_id}` has pointed at since api STEP B1. `404` for a malformed/unknown `run_id` or one with no log written yet. |
| `GET` | `/approvals` | token | Every run currently awaiting a governed decision, each entry carrying the same shape as `GET /runs/{run_id}`'s `pending_approval` field (api STEP B5: previously a thinner, independently-computed shape with no `message`/`default_on_timeout`/`timeout_at`). |
| `GET` | `/console` | **none** | The operator console HTML. |
| `GET` | `/health` | **none** | `{"status", "version", "backend_profile", "default_review_mode"}` and nothing else. |

The two ungated routes are ungated by design. A browser has no token on first load of
`/console`, and the console itself asks for one before calling anything else. `/health` is an
unauthenticated liveness probe: it carries no `SHIMMER_` name or value, no path, no hash and no
token, only the two enumerated words a caller needs before it can submit (`backend_profile` is
`local` or `cloud`, `default_review_mode` is `paired` or `wide`).

`/console`, not the bare root: a pre-existing gate check (94) proves every run-scoped route
rejects a path-traversal-shaped `run_id` with 404, and every HTTP client normalizes a
`..`-bearing path client-side before sending, so `GET /runs/../..` always arrives at the server
as a plain request for `/`; a route registered at bare `/` would turn that check's 404 into a
false 200.

Every route taking a `run_id` rejects any value not matching the server's own mint format with
404 before building a path, and `/runs/{run_id}/findings` and `/runs/{run_id}/pairs` return the
same 404 for a well-formed id with no run folder. Jobs run one at a time; each job's state is
also written to `<run>/status.json` on every transition (queued, running, then one of the
statuses below), so a restart does not lose run history; the in-flight run is rewritten
`interrupted`, and a run still `queued` at restart keeps its record but loses its staged
uploads, so the submitter resubmits both. The child pipeline's complete merged stdout/stderr
streams to `<run>/logs/pipeline_stdout.log` as the run proceeds (not just the 2000-character
failure tail kept on the job record), and is fetchable directly via `GET /runs/{run_id}/log`.

**The `review_mode` field and the review counters.** `/submit` accepts `review_mode` (`paired`
or `wide`, section B). Omitted, it resolves exactly as the pipeline resolves it with no
`--review-mode` flag: paired under the local backend profile, wide under cloud. The resolved
mode is echoed in the 202 body, recorded in `<run>/status.json`, and passed to the child as
`--review-mode <mode>` always, so the mode the caller was told they got is the mode that ran.
Unlike `task`, an unrecognised value is **rejected with 400** rather than falling back: the two
modes differ by roughly an order of magnitude in model calls, and a typo must not buy a wide
cloud run on the operator's keys.

`GET /runs/{run_id}` carries three counters derived from the run folder on every call, so they
move while the run is in flight:

- `pairs_planned` : every `(unit, rule)` pair the pairing map decided could apply, summed over
  the run's documents.
- `model_calls` : model calls made so far, all phases, one per line of
  `<run>/logs/cost_tracker.jsonl`.
- `pairs_arithmetic_only` : pairs the run settled without asking a model. Reported **only in
  paired mode**; in wide mode it is `null`, because a phase-5.5 call there is a whole-document
  review and subtracting it from a pair count would be arithmetic on unlike things.

**The `sensitive` field and the console's privacy choice.** `/submit` accepts a `sensitive`
form field (`"true"`/`"false"`, default `SHIMMER_SENSITIVE`) so privacy posture is a visible,
per-run choice rather than only a server-wide default. The console renders it as an explicit
checkbox with two sentences of plain explanation: a non-sensitive run (unchecked, the default)
sends document text to cloud providers and waives redaction; a sensitive run (checked) keeps
redaction on, but a sensitive run submitted HERE refuses to start (exit 6), because this server
withholds the layer-inactive override for a sensitive job while the full LAW-IV masking layer
ships inactive. (The launcher and the intake wizard pass that override even in sensitive mode,
so a sensitive run started there starts and skips the scrub instead; section F.) The two override flags
(`--sensitivity-layer-inactive-override`, `--no-redaction-override`) are appended only when the
resolved value is non-sensitive, exactly as the old server-wide `SHIMMER_SENSITIVE` check did.

**Status vocabulary.** A job is `queued` from `/submit` until the single worker picks it up,
then `running`, then exactly one terminal status. The server always passes
`--operator-channel file` to the pipeline subprocess (STEP 6), and every pipeline exit code
maps to a distinct terminal status instead of the old blanket "failed" on any non-zero exit.
This raw `status` string is the internal job field (still what `<run>/status.json` on disk
records); `GET /runs/{run_id}` and `GET /runs` do **not** return it (api STEP B5), reporting
`state`/`outcome`/`stop_reason` instead: the table below adds the `state`/`outcome` each
`status` value maps to.

| Status | Exit | `state` | `outcome` | Meaning |
|---|---|---|---|---|
| `queued` | - | `queued` | - | Accepted and waiting; the files are staged, not yet in `input/context/`. |
| `running` | - | `running` (or `awaiting_approval`, see `pending_approval` above) | - | The worker is streaming the child's output. |
| `completed` | 0 | `stopped` | `succeeded` | Success. |
| `snapshot_conflict` | 2 | `stopped` | `crashed` | `--save-snapshot` only. |
| `stopped_model_approval` | 3 | `stopped` | `governance_stop` | Governance outcome. |
| `stopped_redaction_gate` | 4 | `stopped` | `governance_stop` | Governance outcome. |
| `blocked` | 5 | `stopped` | `governance_stop` | Governance outcome. This code is **overloaded** upstream: a redaction BLOCK at run-end, OR a draft-mode phase-0 generation failure. The exit code alone cannot tell them apart, so check the run's log tail (`GET /runs/{run_id}/log`). |
| `refused_sensitivity_layer_inactive` | 6 | `stopped` | `governance_stop` | Governance outcome. |
| `operator_abort` | 7 | `stopped` | `crashed` | The operator declined a meta-signature escalation. |
| `interrupted` | - | `stopped` | `crashed` | The server restarted while this run was in flight (STEP 2). The submitter resubmits. |
| `failed` | other | `stopped` | `crashed`, or `timed_out` if `exit_code` is `null` | Any other non-zero exit, or a run timeout (`exit_code` is then `null` and the reason is in `error`). |
| `cancelled` | any | `cancelled` | `cancelled` | `POST /runs/{run_id}/cancel` was called (api STEP B2); the only status this table produces that no exit code maps to. |

`blocked`, the two `stopped_*` statuses and `refused_sensitivity_layer_inactive` are the four
governance outcomes, the pipeline refused or paused ON PURPOSE, and the console renders them
distinctly from a genuine crash.

**The console** (`GET /console`, served from `scripts/ui/console.html`, one file, vanilla
JavaScript, no framework, no build step, no CDN dependency) lets a human submit runs, watch
them, answer a pending approval, read findings, browse the pairing map, read the amendments
proposed against them, and download deliverables, without a terminal. It ships two complete
views of the same data, switched with
a labeled control in the masthead and remembered per browser tab: the **reviewer view** (the
default, on every first load) reworks every developer-facing fact into plain language, a
finding reads as a sentence naming what was checked and against what rather than a row of
field codes, a run is named from what was submitted (`files[0]`, or the question for a
draft) rather than shown only as its run id, a crash says the review did not finish and
nothing was lost rather than showing a traceback, and a governance stop, a system fault and a
timeout each get their own distinct wording so a stop-on-purpose is never confused with a
failure; the **developer view** is the original field-level surface (raw `run_id`, `rule_id`,
`relation`, the full stop_reason detail, the raw pairing/findings tables) and stays fully
intact under the switch. The reviewer view is a rewording, never a filtering: nothing the
developer view shows is dropped, only reworded or moved into a small secondary citation.
Findings and the pairing map are fetched for every state a run can be in except `queued`, not
only a clean `succeeded` completion: phase 5.5 writes both the moment it pairs a unit, with no
outcome of its own, so a run that later crashes, times out, is stopped by a rule, is
cancelled, or is still running or paused for an approval can carry real findings from before
whatever happened next; both views show them, labeled plainly as found before the run ended
and not a complete review, rather than the console silently asking only when the run finished
cleanly and treating everything else as though nothing had been found. Every irregular finding
that has a matching amendment (`GET /runs/{run_id}/amendments`, the last thing the pipeline
produces that used to reach no view at all) shows its proposed correction directly beneath its
own row: the passage as it stands, the passage as proposed, the rule it rests on in the
operator's own id, and the reasoning, together, since a correction with no reasoning attached
is worth less than one with, and the console says so plainly rather than presenting the two the
same way. A paused run (`awaiting_approval`) shows its phase ladder the same as a running one,
since it is internally still `running` on the server with an approval on top; and a pending
approval carrying neither a message nor a payload (the server does not require either) says so
plainly rather than presenting Approve/Deny with nothing above them to decide from. Full field-by-field
translations for every relation, every state/outcome combination, a run identifier, a phase
label, a crash, a governance stop, a pending approval and a partial archive are recorded in
`docs/api/CONSOLE_LANGUAGE.md`; the complete promise/hide audit across every state, outcome
and data combination in `docs/api/CONSOLE_STATE_AUDIT.md`; the design rationale (palette,
typography, layout, the dark masthead) in `docs/api/CONSOLE_PLAN.md`. The access token is
entered once, reached via a quiet "Not signed in" / "Signed in" link (not a permanent field:
it is needed once per browser tab, not on every screen), kept in `sessionStorage` (survives a
reload of the same tab, cleared when the tab closes, never a URL, never `localStorage`), and
sent as the `Authorization: Bearer` header on every call the page makes. `tools/console_preview.py`
is a throwaway local harness (explicitly marked as not part of the product) that starts a real
server with the pipeline subprocess stubbed out, no model call, and seeds one run in each
reachable state, for looking at the console without spending a real run: `py -3.9 -X utf8
tools/console_preview.py`, then open the URL and use the token it prints; Ctrl+C throws away
all of it. A governed decision that would otherwise stop a `--non-interactive` run
unconditionally (e.g. a deprecated-model swap `enforce_current_models` cannot auto-resolve) is
instead parked by `pipeline.py`'s file-backed operator channel (`--operator-channel file`,
`scripts/pipeline.py::_make_file_operator_handler`) as `<run>/audit/pending_approval.json`; the
console's approval block on that run's own page shows it, and Approve/Deny writes
`<run>/audit/approval_decision.json`, which the waiting pipeline subprocess polls for and
relays verbatim into an `OperatorDecision`. The handler and this server route never evaluate
the decision themselves: that stays entirely in `model_registry.enforce_current_models` and
`constitution_guard._is_approved` (both repaired in productization STEP 1a/1b).

**The ingestion contract** (`corpus_ingest/CONTRACT.md`) governs the handoff. Each submission
carries a sidecar `_corpus_ingest.json` with `ingest_run_id`, `generated_at`, and a `cases[]`
list; each case has `file`, `case_id`, `title`, `citation`, `jurisdiction`, `date`,
`language`, `source_verification` (status + url), and `role`. Each listed `file` must be an
ASCII-safe `.md` name carrying a delimited 4-digit year (`case_alpha-2021.md`) whose year
matches that entry's `date`; both are hard failures. Files with
`role=context_grounding` are retrieved precedent, never the document under review, and under
`--mode integrated` (the server's default) they are excluded from operational promotion; a
`--mode standalone` run warns and promotes them anyway. The validator
(`corpus_ingest/validate_contract.py`) runs on every submission that carries files, before
anything enters `input/context/` (a draft submitted with no uploads has nothing to validate);
invalid bundles are rejected with a 400 and the violation report.

---

## J. Cost and performance (observed)

From operator testing before productization, on a five-document synthetic competition-law
corpus (five regulations plus five grounding cases), single Claude API key. **That corpus has
since been removed from the operator's working repository** (not published; this is a public
snapshot of source only, section G), so the figures in this block are historical and cannot
be reproduced here; the local-profile measurements below can be:

- **Cost (historical, not reproducible here):** about **$2.67 per run** (43 model calls, 0
  failures). Claude 28 calls (~410k input / 57k output tokens, ~$2.30); GPT-4o 15 calls
  (~130k input / 8k output, ~$0.37). No run under `output/runs/` corroborates it (run output
  is never published; every local-profile run in the operator's own record was $0.00).
  Prompt caching is wired (Claude explicit cache_control; GPT automatic prefix cache); cache
  reuse in a single short run is modest.
- **Wall-clock, three configurations observed on the operator's machine and not published in
  this repository** (no cloud run wall-clock is published; every published wall clock below
  is a local-profile run):
  - **~66 min** baseline (full sensitive run; the local Qwen redaction phase ran
    sequentially per document and dominated the tail).
  - **~15 min** with the redaction phase shortened.
  - **~7.5 min** non-sensitive (no redaction; the cloud review by itself).

In that configuration the redaction phase was the tail: the cloud review (phases 1 through 7)
was the fast part and the local Qwen redactor the bottleneck, apparently running at CPU speed
despite a GPU being reported available. Phase 9 no longer executes at this HEAD (section F), so
that is a historical bottleneck; on the local-profile runs below the time goes into local
inference in phases 3 to 5.5.

**Local profile, paired review, measured end to end** on a single-document declaration
corpus with nine planted defects, scored by a frozen scorer against a withheld answer key.
**One live run, a single draw, not an average** (the same standing rule that labels the two
tables below: every number in this section is one measured run, never an average across
runs, and the run logs behind these numbers are not published in this snapshot):

| | value |
|---|---|
| recall | **6 of 9** |
| false positives | **0** |
| attribution (finding carries the operator's own rule id) | **4 of 6** |
| wall clock | **17.8 min** |
| cost | **$0.00** (no provider API call) |
| model calls in the review phase | **5**, against 104 candidate pairs |
| amendments written by a model | **0** (all rendered from typed Findings) |
| peak RAM / VRAM | 5.87 GB / 7170 MB |

The 99 pairs that made no model call are where the time went: Python settled them from the
figures. The baseline this replaces scored 5 of 9 with attribution 0 of 5 and made 4 calls.

**Two corpora from other domains, real public data, keys held out** (`benchmark/corpora/`,
staged with `tools/stage_corpus.py`, scored with `tools/score_corpus.py`; one local run each,
so these are single draws, not averages):

| | `clinical_reference` (real reference ranges, six results) | `catalogue_records` (real metadata element set, six records, no figure anywhere) |
|---|---|---|
| planted flaws | 5 | 5 |
| recall, mechanical | 1 of 5 (3 of 5 by inspection: the three out-of-range values were found, correct figure and direction, but this run executed pre-fix code that lost the rule id and never posted the computed records) | 0 of 5 |
| false positives in the deliverable | 0 | 0 |
| clean items flagged | 0 | 0 |
| wall clock | 57.1 min | 39.5 min |
| model calls in the review phase | 35 for 29 pairs (pre-fix; 14 *planned* on fixed code, not re-run) | 41 for 41 pairs (nothing computable) |
| cost | $0.00 | $0.00 |

**The two negotiation corpora, round N against round N-1, keys held out** (one local run each,
single draws). The task given to the pipeline, in both: *review the later offer against the
mandate, with the earlier offer declared as the earlier version, and answer "which terms moved
toward the mandate since the earlier offer, which held, and what was dropped?"*

| | `negotiation_r3_to_r4` (19 Oct as prior of 31 Oct) | `negotiation_r2_to_r3` (23 Sep as prior of 19 Oct) |
|---|---|---|
| prior-version records expected | 13 | 6 |
| recall, exact (label, relation, both figures) | **13 of 13** | **6 of 6** |
| false comparison records | **0** | **0** |
| stray refusals | **0** | **0** |
| attribution to the operator's own rule id | **13 of 13** | **6 of 6** |
| citations per record | 2 REF-* | 2 REF-* |
| model calls the comparison cost | **0** | **0** |
| band findings | 2 of 2 found, 1 of 2 attributed (pre-fix) | **3 of 3 found, 3 of 3 attributed** |
| false band records (since fixed, checks 183/184) | 5, one reaching a deliverable as an amendment | 1, plus 1 false amendment from a prose column |
| judging calls | 25 for 17 pairs | **8 for 9 pairs** |
| wall clock | 61.4 min | 46.9 min |
| cost | $0.00 | $0.00 |

**Read these numbers with a correction the operator's own working record carries but this
snapshot does not publish.** An independent verification confirmed the arithmetic and
overturned the framing. In short: the
figures are real and every value pair is exact, but **2 of the 19 records are false about the
actual negotiation** (the $12,000 ratification bonus *combines* the earlier $7,000 bonus and the
$5,000 401(k) lump sum, so nothing was withdrawn and the "+5,000 moved toward" is the same money
counted twice), and **the score measures the corpus rather than the capability**: one author
wrote the labels in both documents, the mandate quoting those labels, and the key listing them a
third time, against a mechanism that is string equality over exactly those labels. A probe that
reworded only the later document's labels turned 13 records into 15, twelve of them false
absences, with the refusal list still empty. What is proven is that the path computes correctly
on input shaped for it; whether it can find a term without pre-aligned vocabulary, and whether
it refuses rather than fabricates when it cannot, is unproven and the one probe available says
it fabricates.

Two further defects surfaced in the band pass around it, both since fixed with checks 183 and
184. The first cut run 1's judging calls from 25 to 17 on identical input (its own saved pairing
map, replayed) and removed five false band records.

The clinical and catalogue runs measure two different things. The clinical run found every planted out-of-range
value in Python and exposed eight defects in the plumbing around that arithmetic, each fixed and
each with a gate check; the catalogue run's first attempt added a ninth (a crash on a malformed
judging reply), and two Unicode label defects found in a parallel design review were fixed in the
same step, without a gate check of their own. The catalogue run measures the
floor: with nothing to compute, three of the five flaws were never asked about because a
completeness rule is rejected for exactly the unit that lacks its field (H4's pairing rule,
backwards for that kind of rule), and the local judge's 37 replies on the other pairs
produced one valid typed Finding and no usable rule id, so nothing reached the deliverable.
The typed-record gate that held the deliverable at zero false positives (the judge flagged 30
of 41 pairs, clean records included) held out the true findings with them. Both conclusions are
recorded as open design decisions in the R5 report, not patched.

---

## K. Known limitations

Stated honestly, from operator testing:

- **Recall is corpus-dependent and well short of complete.** On the single-document
  declaration corpus with nine planted defects: **6 of 9** with zero false positives. On two
  held-out corpora from other domains: **1 of 5** mechanically on `clinical_reference` (3 of
  5 by inspection, on pre-fix code) and **0 of 5** on `catalogue_records`, where nothing is
  computable. Each is a single live run, not an average. The 87% (21/24) quoted here in
  earlier revisions was cloud-era testing on a corpus no longer in the operator's working
  repository and is not reproducible.
- **Run-to-run variance is unmeasured.** The model layer is sampled, so a single run is not a
  complete review, but no corpus in this repository has been scored twice: every benchmark
  number in this README is a single draw and is labelled as one, and the run logs behind them
  are not published in this snapshot. The same submission can also fail two different ways (a
  format failure on one run, a real redaction survivor BLOCK on another).
- **Redactor span quality and redaction wall-clock (both from cloud-era sensitive runs; the
  phase does not execute at this HEAD).** When the LAW-IV layer was last active, the Qwen
  redactor proposed over-broad spans (a generic phrase rather than the figure), which the
  post-apply grep correctly BLOCKed, and the sequential redaction phase dominated the run at
  what looked like CPU speed despite a GPU being reported available. The fix is better span
  selection or a tighter convention (match the figure, not the words), not weakening the gate.
  Neither has been re-measured since phase 9 became gated on `LAYER_ACTIVE`, which ships False.
- **Arabic citation gap:** the Arabic grounding document was retrieved but not consistently
  cited in amendments, a retrieval quality gap addressed by the bge-m3 embedding swap.
- **Local runs are unreliable on a laptop GPU.** On the development machine (RTX 3070 Ti
  Laptop, 8 GB, hybrid with an integrated adapter) roughly one local run in three or four
  dies partway through: the NVIDIA kernel driver faults (`nvlddmkm` event 153, WER
  `LiveKernelEvent` 0x117 / 0x141) and Windows resets the display driver, which destroys the
  CUDA context and kills the process instantly. There is no Python traceback, no wrapper
  summary and no memory pressure: the process simply ends. It has hit three different phases
  and three different agents, so it is not a code path. The mitigation is to raise the TDR
  timeout from its 2-second default (`HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers`,
  `TdrDelay`, admin plus reboot), which is a machine-level change and is not made by this
  repository. Cloud runs are unaffected.
- **Band matching is word containment, so a key cell that encodes a numeric comparison in
  prose is not matched.** Such a row yields no band rather than a guessed one. Resolving it
  would need a list of direction words, which is the domain leak the vocabulary probe exists
  to prevent.
- **A band applies to the fields its rule names, so a rule that names no field of a unit
  still compares against every figure in that unit sharing the bound's unit of measure.**
  That is deliberate (a rule naming nothing could otherwise never fire) but it is the one
  remaining way a stated band can reach a figure it was not written for.
- **Label tokenisation drops words of two characters or fewer**, which is a fragment in an
  alphabetic script and a whole word in a logographic one, so a CJK field label is still
  dropped. Accented and non-Latin alphabetic labels work (fixed in R3); logographic ones do
  not yet.
- **A completeness rule is rejected for exactly the unit that lacks its field.** The pairing
  rule "a rule pairs only with a unit carrying every field it names" is right for a
  computational rule and backwards for "every record must state a creator": measured on the
  catalogue corpus, 3 of 5 planted flaws were never asked about for this reason. The
  `missing_field` check that would catch them in Python runs only on paired (unit, rule).
  Deciding which rules are completeness rules without a keyword list (an operator-declared
  rule kind is the domain-agnostic route) is an open operator decision. The round-N
  `absent_since_prior` path does not depend on pairing and is unaffected.
- **A renamed label whose value also changes is still reported as withdrawn.** A field
  label renamed between two versions, while its value stays within a tolerance (2% relative
  by default, `config/rename_tolerance.json`, operator-editable), is now refused rather than
  reported `absent_since_prior`: check 185 proves it, both directions, on the negotiation
  corpus and by neutralise-and-restore. What is still not solved is the harder case: when
  BOTH the label and the value change between versions, nothing corroborates that this is a
  rename rather than a withdrawal, so the field is still reported `absent_since_prior`,
  wrongly. On the negotiation corpus this leaves **5 wrong cases out of 13**, down from
  **12 wrong out of 13** before the fix. A term that is new in the later version produces
  neither a record nor a refusal; a one-row summary table
  has no discriminating key column and supplies no figure; direction (`moved_toward` /
  `moved_away`) exists only where a paired rule names the field and states or points at
  exactly one band, otherwise the change is `changed_from_prior`; a record for a field no
  rule names cites the unit's first paired rule (the existing fallback for rule-independent
  findings), which is weak attribution and is visible in `source_rule_id`.
- **The figure reader does not scale magnitude words** (`1.2 million` reads as 1.2) and reads
  a multi-word unit only when the document writes the phrase after a figure more than once;
  a token such as `3,141` is read as a grouped thousand, not a decimal comma, which is the
  reader's long-standing convention.

---

## L. The verification gate

`scripts/verify_session1.py` is the standard health check. Its total is the length of its
CHECKS list (**186** at the time of writing), not a hardcoded number, so adding a check
raises the total by itself. Each check proves behavior with executed coverage on fixtures and
is non-mutating (it uses tempdirs and never writes the real durable, ontology, or config
stores). Run it every session and before every commit:

```
py -3.9 -X utf8 scripts/verify_session1.py
```

**On a fresh clone of this snapshot, four checks fail, by design, before you have run
anything.** All four fail for the same reason: this repository ships source only, and each
of these checks proves something about a directory the launcher or the pipeline creates on
first run, not something this repository carries.

| check | fails because |
|---|---|
| 01, directory structure | `input/`, `output/`, `durable/`, `prompts/`, `snapshots/` and their subdirectories are not shipped; the launcher (section G) creates the ones it needs on first run |
| 28, `input/` exists and accepts documents | `input/` is not shipped; it is where the pipeline reads documents from, and it does not exist until you or the launcher create it |
| 31, `input/` has `context/`, `operational/`, `conventions/` | same root cause as check 28: no `input/` yet |
| 145, no planted benchmark figure in `config/`, `scripts/` or `tests/` | `tests/` is not shipped (see "Benchmarking" above); the contamination probe has nothing to scan, so it fails rather than passing silently |

A gate that passed all 186 checks on an empty checkout would be proving nothing about those
four; failing loudly is correct here; there is nothing to test, not something broken. Every
other check passes on a fresh clone with no setup beyond `py -3.9 -m pip install -r
requirements.txt`. Once you have run the launcher (or built `input/` and staged a corpus
yourself, section G), checks 01, 28 and 31 pass; check 145 needs a `tests/` directory with
planted-figure fixtures, which this snapshot does not carry and an operator adds locally if
they want that specific check.

**The vocabulary probe (check 174) and `config/domain_vocabulary.json`.** A standing,
deterministic check that no operator-declared domain term appears in the code surface
(`config/`, `scripts/`, `tests/`, `tools/`). `input/` and `benchmark/` are never scanned:
they are operator material, and domain vocabulary is exactly what they are supposed to
contain. `config/convention_registry.json` is exempt for the same reason, being gitignored
and generated at BOOT from `input/conventions/`.

The term list lives in the JSON file and **nowhere in the check**, which is the whole point:
the previous guard (check 22) hardcoded its regex against the domain of the day and
therefore could never catch a leak from any other domain. Check 22's own terms live in that
file too, under `previous_domain`, currently empty in this public snapshot (there is no
prior operator's domain to guard against here) and populated again the moment an operator
adds terms to it, so no domain word is ever written into code.

Severity is per family. `fail` turns the gate red; `warn` reports a count in the check's
detail without blocking, which is how an existing backlog is made visible without making the
gate unlandable. Promoting a family to `fail` is a one-line edit. ALL-CAPS terms match
case-sensitively, because matching a currency code case-insensitively hit Python's `try:`
keyword 365 times.

It covers the directory structure, the constitution and registries, the message bus and
orchestrator, every agent's contract, conventions and references, the date cutoff and
embedding store, the canonical envelope, the redaction and masking layers, the editorial
board, the learning engine, the verifiability and meta-law gates, the corpus ingestion
contract, the FastAPI front door (including that the route table in this README equals the
routes the app registers), the task-mode flags, draft mode, the single-agent harness, the
benchmark contamination probe, the pairing map and paired review, the structured-review
routes, and (checks 178 to 184) the extended figure reader, the INFRA-044 record and the
round-N comparison executed on a real orchestrator with no model call, its rendering in both
deliverables, the review question's path into the run objectives, the scan and the child argv, that a
band a rule states is compared only against the fields that rule names, and that a column of
prose carrying one incidental figure is not treated as a column of measurements.

---

## M. Related work and positioning

Shimmer composes established mechanisms; the contribution is the composition plus the
amendment-governance framing, not novel mechanisms. It sits in two lineages.

Multi-agent debate and cross-family verification:

- Du, Y., Li, S., Torralba, A., Tenenbaum, J. B., Mordatch, I. (2023). Improving Factuality
  and Reasoning in Language Models through Multiagent Debate. arXiv:2305.14325. (ICML 2024.)
- Liang, T., et al. (2023). Encouraging Divergent Thinking in Large Language Models through
  Multi-Agent Debate. arXiv:2305.19118.
- Chang, E. Y., Chang, E. Y. (2025). Multi-Agent Collaborative Intelligence: Dual-Dial
  Control for Reliable LLM Reasoning (MACI). arXiv:2510.04488.

Runtime governance and information-flow control:

- Zhong, P. Y., Chen, S., Wang, R., McCall, M., Titzer, B. L., Miller, H., Gibbons, P. B.
  (2025). RTBAS: Defending LLM Agents Against Prompt Injection and Privacy Leakage.
  arXiv:2502.08966.
- Chinaei, M. H. (2026). Causality Laundering: Denial-Feedback Leakage in Tool-Calling LLM
  Agents. arXiv:2604.04035. (Introduces the Agentic Reference Monitor, ARM, which enforces
  provenance invariants at the execution boundary.)

Positioning: Shimmer composes multi-agent cross-family verification and runtime
information-flow control under an append-only, operator-ratified constitution with a formal
amendment process, applied to defect-intolerant multilingual regulated document review. The
mechanisms are established; the contribution is the composition and the amendment-governance
framing. LAW-IV is an information-flow locality law with a per-item exposure ledger as its
audit trail.
