# Convention assignment design (proposal, not built)

This document is a proposal. Nothing in it is built. It exists because W2 of the night chain
(`docs/fix/STEP_W2_REPORT.md`) stopped at its own premise check: no agent declares what it
handles in a form an assignment could be derived from, no convention declares what it is
about in a form that could match an agent, and the one structured field on each side
(`category`) is two unrelated vocabularies. The operator then decided how the gap is to be
closed, and asked for this design before any code. Every code claim below carries a
`path:line` for a line opened during the read-only research that preceded it; the answer keys
under `benchmark/corpora/` were not opened.

## The decision, restated precisely

Not a shared vocabulary that both sides negotiate. A one-way label on each side, compared by
code that knows no subject name at all:

- Each agent declares the subjects it handles. The operator writes those once, for all
  eighteen. This stays domain agnostic because what an agent does (verifying, redacting,
  resolving citations, checking structure) is the same whatever the document is about.
- Each convention carries the subject its operator chose when writing it. That knowledge
  lives in the operator's own file and never enters code.
- The assignment is the comparison of those two lists. The comparison is the only thing in
  code, and it contains no subject name.

Three requirements: a convention matching no agent is never dropped, it is surfaced for the
operator (relabel the rule, or a subject is missing from the agent side); the agent-side
subject list is data, not code, editable without touching a module; and the assignment
happens once, when conventions are loaded, not per call.

## The two sides today, restated precisely

**The agent side.** `config/agent_registry.json` declares 18 agents at lines 6-132, each with
`does[]` and `does_not[]` (free prose, no ids, no enum), `category` (8 values across 18
agents), `model`, `backend`, `may_use_web`, `may_handle_sensitive`. `config/agent_contracts.json`
declares output shape only (`item_kind`, `fields`, `required`, sometimes `directives`). Neither
file has a field that names what an agent handles in a form code could compare. The registry
is the sole owner of agent identity (its own line 4), and `scripts/build_agent_harness.py`
reads only these two files (179-233).

**The convention side.** `scripts/convention_parser.py` delimits rules structurally: a
markdown heading (`^#{1,6}\s+\S`, 228-229) is never itself a rule and sets the category for
what follows; a list item is one rule; consecutive non-blank lines are joined into one rule
at the next blank line (166-215). The operator's own rule id is taken from the heading by
`_HEADING_RULE_ID` (`\bconv-[a-z0-9]+(?:-[a-z0-9]+)*\b`, 251) and kept verbatim as the rule's
`category` (254-278); only an id-less heading goes to the seven-bucket English keyword table
`_CATEGORY_KEYWORDS` (240-248). A registry entry has exactly seven keys, written by one
function: `id, category, rule, source_file, source_location, severity, action`
(`ConventionRule.as_dict`, 60-63). Severity comes from the rule text alone (31-35, 118-122);
the `[required]` tag the operator writes on a heading such as
`## CONV-D01 , conv-value-in-range [required]` is read by nothing and discarded (271-278), which
is why CONV-006 (heading `CONV-D03 [required]`) is `advisory` in the generated registry
(`config/convention_registry.json:44-52`). JSON input keeps an operator id and drops any key
the dataclass does not have (132-158).

**Who receives a rule today.** This is the fact that shapes the whole design, and W2 did not
state it because W2 stopped earlier:

| agent | receives conventions today | where |
|---|---|---|
| PRACTICE_AUDITOR, STYLE_GUARDIAN | yes, every rule, in wide mode: `evaluate_against` lists every registry id (`pipeline.py:1460-1463`) and the full registry goes to each via `_run_one` (`:1489-1505`) to `assemble_context` to `_render_conventions` (`bus_reader.py:221-231`, first 40 rules, 240 chars each) | `CONVENTION_REVIEW_AGENTS` (`pipeline.py:334`) |
| PRACTICE_AUDITOR alone | yes, in paired mode: one rule per call (`pipeline.py:1679-1710`); the judging agent is pinned to `CONVENTION_REVIEW_AGENTS[0]`, so STYLE_GUARDIAN never runs in paired mode | `:1679`, and `:1256` for the earlier-version comparison |
| the six EDITOR ranks | the whole registry, per rank, on escalation only (`_dispatch_rank`, `pipeline.py:2405-2429`); the rank is chosen by `_observation_triggers_escalation` (`:2364-2376`), never by a rule | phase 6.5 |
| REDACTOR | only rules that compile as redaction rules, by a keyword sniff over category and id (`sensitivity_layer/rules.py:35, 63-66`), redact verbs, or prohibition phrasing (`:107-125`) | phase 9 |
| VERIFIER, FACT_CHECKER, LEGAL_ANALYST | no rule during their phase; rule ids are stamped onto their findings afterwards (`pipeline.py:2056-2065`) | phases 3 and 5 |
| AMENDMENT_DRAFTER | findings, not rules; the model call is off by default and the amendment is rendered in Python from the typed Finding (CLAUDE.md, "Writing an amendment") | phase 6 |
| PROCESSOR, SPEECH_ACT_TAGGER, ARCHIVIST, INST_FINDER, CITATION_RESOLVER | no rule reaches them by any path; INST_FINDER and CITATION_RESOLVER are AUDIT-ONLY by contract, their output consumed by nothing downstream (`agent_contracts.json:211, 226`) | phases 3 and 4 |

So "every agent declares the subjects it handles" meets a pipeline in which four agents have
a live rule-consuming path, three have a stamped-afterwards path, and five have none. A
declaration on the five is data with no consumer today. The design below does not hide that:
the assignment records, per rule, which matched agents can actually act on it, and a rule
whose only matches have no consumer is surfaced exactly like a rule with no match. Wiring a
consumer for those agents is a separate decision, named in the last section.

## Where the agent-side subject list lives

Three places were considered.

**A. A `subjects` array per agent in `config/agent_registry.json`, beside `does` and
`does_not`.** Recommended. The registry is already the sole owner of agent identity, model and
backend (its line 4), every existing gate check that pins agent structure reads it, and the
harness builder reads it, so part 3 of the harness (below) can be regenerated from the same
file with no second source. It is data, not code: editing a list needs no module change.
Gate check 174 scans `config/` for operator-declared domain vocabulary (`verify_session1.py:
10961-11065`), which is the right guard for this list: a subject name that is a domain word
would fail the gate, as it should.

**B. A separate `config/agent_subjects.json`.** Keeps the registry untouched, at the cost of
two files that must agree on the agent set (a new gate check to keep them aligned, and a
second place for a future agent to be forgotten).

**C. Inside `config/agent_contracts.json`.** Wrong home: contracts describe output shape,
and a subject is about input, what a rule may ask of the agent.

Shape under A, per agent:

```json
"PRACTICE_AUDITOR": {
  "does": [...], "does_not": [...],
  "subjects": ["conformance"],
  ...
}
```

Rules on the list: lower_snake_case tokens, one or two words, no whitespace; the list may be
empty ONLY with a sibling `subjects_note` string saying why (the same discipline the harness
uses for an unresolved part: an empty list with no reason is indistinguishable from one nobody
wrote). The gate asserts every agent has the key and that an empty list carries the note.

## What a convention's subject field looks like

On the operator's side, the subject must be written in the operator's own file and read by
code that contains no subject name. Three shapes were considered, all read structurally.

**A. Bracket tags on the rule heading.** Recommended. The operator already writes brackets
there (`## CONV-D01 , conv-value-in-range [required]`, `device_conventions.md:11-16`) and the
parser already has the heading in hand at `convention_parser.py:188-194` (and lowercased at
271) and discards the bracket. A structural regex over every `[...]` on the heading yields
tokens; a token that matches one of the severity labels the parser already knows
(`_SEVERITY_PATTERNS`, 31-35: required, recommended, advisory) is severity; every other token
is a subject. Code knows the bracket shape and the three severity words it already knows; it
learns no subject name. One bracket per tag or several tokens in one bracket, both readable;
recommend one bracket per tag for legibility:

```
## CONV-D01 , conv-value-in-range [required] [conformance]
## CONV-D07 , conv-grounding [required] [conformance] [basis]
```

Side effect the operator should decide on deliberately: reading the bracket for severity
fixes the `[required]`-ignored defect above (CONV-006 would become `required`). It is the
same code path, so the two changes travel together unless the operator says otherwise.

**B. A `subject: ...` line under the heading.** Today such a line is appended to the paragraph
buffer (207-212) and becomes part of the next rule's text, or its own rule if separated by a
blank line and at least 16 characters long. A hook before that append could read a
`key: value` line while the buffer is empty. The key word (`subject`) would be a literal in
code; the values would not. Workable, but it is a second syntax beside the bracket the
operator already uses, and a stray `subject:` line inside a rule paragraph would silently
change that rule's text today.

**C. A `subjects` key in JSON input.** Needed anyway for `_parse_json` (132-158), which
drops unknown keys because the dataclass has fixed fields.

On the registry side, in every case: one new key, `subjects` (a list, `[]` when the heading
carries none), added to `ConventionRule` (50-58), `as_dict` (60-63) and the three
constructors (150-157, 179-183, 201-205). Kept SEPARATE from `category`, which stays the
operator's own rule id, so `finding_record.source_rule_id_for` (268-286), the server's rule
lookup by category (`server.py:2222-2248`) and the redaction compiler (`rules.py:107-125`) are
untouched. The four consumers that enumerate entry fields (`server.py:2240-2248`,
`bus_reader.py:227-230`, `summary_generators.py:94-103`, `ontology_graph.py:139-146`) need
nothing: the rendered prompt block carries id, category, severity, action and text, and the
subject is a routing fact, not something the model needs to read.

## How the comparison works

The whole of it, in code that contains no subject name:

```python
def assign_conventions(conventions, agent_registry):
    """Once, at load. Exact token equality, no synonyms, no substrings, no ranking."""
    declared = {name: set(spec.get("subjects") or []) for name, spec in agent_registry["agents"].items()}
    by_rule, by_agent = {}, {name: [] for name in declared}
    for c in conventions:
        tags = set(c.get("subjects") or [])
        matched = sorted(a for a, subs in declared.items() if tags & subs)
        status = "untagged" if not tags else ("assigned" if matched else "unassigned")
        by_rule[c["id"]] = {"subjects": sorted(tags), "agents": matched, "status": status}
        for a in matched:
            by_agent[a].append(c["id"])
    return {"by_rule": by_rule, "by_agent": by_agent}
```

Decisions embedded in those lines, each one the operator's to confirm (last section):

- **Any overlap, not full containment.** A rule tagged `[conformance] [basis]` reaches every
  agent declaring either. A rule that must reach two agents is written with two tags.
- **Exact equality after lowercasing and whitespace stripping.** No normalisation beyond
  that, no plural folding, no synonym table anywhere. The form written on an agent is the
  form written on a rule, or they do not match, and the mismatch is visible (below).
- **Once at load.** The insertion point is `scripts/pipeline.py:3224-3227`, where
  `parse_conventions` and `write_registry` produce `conv_registry_dict`, before the first
  phase call at `:3317`. The result is written to the run's `audit/convention_assignment.json`
  and threaded beside `conv_registry_dict` into the phases that already receive it
  (`:3317-3364`).
- **One place where both review modes read it.** Inside `phase_5_5_convention_review._process_doc`,
  after the pairing map is built (`:1432-1439`) and before the mode branch at `:1483`. Wide:
  the loop at `:1490-1505` builds a task only for an agent whose `by_agent` list is non-empty,
  and passes that agent `convention_registry={"conventions": [its assigned rules]}` and an
  `evaluate_against` of those ids instead of all ids (`:1463`). Paired: `pairs_from_map`
  (`paired_review.py:1375-1390`) is filtered to rules assigned to the judging agent before
  `plan_calls` (`:918-1011`).
- **The denominators follow the assignment.** `_local_progress_baseline` (`pipeline.py:476-486`)
  and `_cost_projection` (`:2752-2770`) both count `len(CONVENTION_REVIEW_AGENTS) * num_op_docs`
  on the assumption that every convention-review agent runs once per document. Both read the
  assignment instead, or the progress bar and the pre-run estimate lie once an agent is skipped.

## What happens to an unmatched rule, on both sides

**A rule no agent declares a subject for** (`status: unassigned`). Never dropped. Four places,
all following patterns already in the repo for the amendment refusals:

1. In `audit/convention_assignment.json`, with the tags it carried and the reason
   (`no agent declares: <tag>`), written at load, so it exists even if the run dies later.
2. On the bus, one INFORM whose body is `{event: "CONVENTION_UNASSIGNED", backend: "computed",
   model: "python", payload: {agent: "ORCHESTRATOR", doc_id: "", items: [...]}}`, one flat item
   per rule (`rule_id`, `source_rule_id`, `subjects`, `reason`), never Finding-shaped, modelled
   on the `AMENDMENT_REFUSED` post at `pipeline.py:2119-2137`.
3. A read route `GET /runs/{run_id}/convention-assignment` in the pattern of
   `/runs/{run_id}/amendment-refusals` (`server.py:2148-2170`: `_validated_run_dir`, a
   bus-reading helper, `{run_id, count, ...}`, 200 with an empty list), plus its README row,
   which is all gate check 167 requires in both directions (`verify_session1.py:10023-10114`).
4. A console section in the disappears-when-empty pattern of `amendmentRefusalsHtml`
   (`console.html:2102-2123`), wording chosen by `isHumanView()` (`:648-673`): Reviewer
   "Rules no agent handles (N)", Developer "convention_assignment.unassigned (N)".

The operator then relabels the rule or adds the subject to an agent. Nothing else changes.

**A rule with no tag at all** (`status: untagged`). Today every such rule (which is every
rule) reaches PRACTICE_AUDITOR and STYLE_GUARDIAN. Three possible behaviours, the operator's
to pick: keep today's routing for untagged rules and list them in the assignment as
`untagged (default routing)`, visible but not blocking; treat them as unassigned; or refuse the
parse. The first is the least change and keeps every existing corpus working unchanged; it is
recommended here as the default, with the count of untagged rules printed at BOOT beside
`convention_registry rules=N`. Note that with the parser as it stands the two preamble
paragraphs of a conventions file become untagged rules (next-to-last section), so an untagged
count that is not zero is also the signal that a file has prose before its first heading.

**An agent that declares subjects no rule carries** (its `by_agent` list is empty). This is
the condition W3 was waiting for. In phase 5.5 that agent is not dispatched, and the fact is
recorded, not inferred from silence: in the assignment file (`agents_with_nothing_assigned`),
on the same bus event, on the same route, and as the fourth visible console state (below).

**An agent that matched but has no consumer** (the five production agents, and, until wired,
the three stamped-afterwards agents). The assignment carries, per matched agent, whether the
pipeline has a path that hands it a rule (`consumer: true|false`, a fact derived from the
fixed phase lists, not from prose). A rule whose every matched agent has `consumer: false` is
listed under `assigned_no_consumer`, surfaced with the unassigned rules, and the console says
so in words: "declared, no path". This is the honest state of a declaration on PROCESSOR or
INST_FINDER today, and it is visible rather than a dormant scaffold.

## The smallest set of subjects that covers the eighteen agents (proposed, not decided)

Three independent proposals were produced from the same real registry and each was
adversarially verified against it (coverage of all 18, contradiction with a `does_not`,
domain words per `config/domain_vocabulary.json`, subjects no operator rule could carry):

| angle | subjects | coverage | verdict, in brief |
|---|---|---|---|
| minimal-first | 9 | 18/18 | sound merges; four subjects are agent mandates, not things an operator writes on a rule (extraction, amendment, editorial, classification); `compliance` borderline as a name; merging VERIFIER, FACT_CHECKER and LEGAL_ANALYST under one subject hands a web-requiring rule to two agents whose `does_not` refuses the web |
| operator-first | 18 | 18/18 | the names are the ones an operator would write; but ARCHIVIST is routed three evaluative subjects against its `does_not "Analyze (evaluative judgment)"` (`agent_registry.json:48`), the editorial mandates are relabelled as three subjects though the rank is chosen by escalation, and `style`/`wording` differ only by an agent that contradicts its `does_not` |
| mechanism-first | 23 | 18/18 | the most precise definitions (each subject is a check the pipeline runs); not minimal: six subjects route only to PRACTICE_AUDITOR, and ARCHIVIST on `absence` contradicts the same `does_not` |

The set proposed here takes the minimal angle's criterion (one subject per routing target
that must be distinguishable, split only where a merged subject would hand an agent a rule its
`does_not` refuses), the operator angle's names where they are the word an operator would
write, and the mechanism angle's finding that a rank of the editorial board is never chosen by
a rule. Twelve subjects. Every claim in the evidence column is a `does` or `does_not` line of
`config/agent_registry.json`.

| subject | agents | evidence (registry line) | consumer today |
|---|---|---|---|
| `conformance` | PRACTICE_AUDITOR | does "Evaluate operational content against the convention registry", "Check procedures against current best practice", "Flag anti-patterns", absence detection (25-26); does_not "Verify raw facts", "Assess legal basis" (27) | live (wide and paired) |
| `wording` | STYLE_GUARDIAN | does "Enforce linguistic register", "Check style consistency", "Evaluate terminology/rephrasing/borrowing conventions" (39); does_not "Change content (style only)", "Verify facts" (40) | live in wide mode; never called in paired mode (`pipeline.py:1679`) |
| `basis` | LEGAL_ANALYST | does "Assess legal basis of source claims", absence detection on mechanisms the corpus shares (32-33); does_not "Search the web independently" (34) | stamped afterwards (`:2056-2065`); no rule during its phase |
| `facts` | FACT_CHECKER | does "Search external sources for evidence", "Produce factual verdicts with source citations" (19); does_not "Judge procedures", "Check style" (20); the only reviewing agent with `may_use_web: true` besides PRACTICE_AUDITOR | stamped afterwards |
| `fidelity` | VERIFIER | does "Cross-check outputs against source documents", "Flag divergence between draft and source" (13); does_not "Search the web" (14) | stamped afterwards |
| `redaction` | REDACTOR | does "Apply the operator redaction rules to document spans" (71); does_not "Judge on its own what is sensitive" (72); the only agent with `may_handle_sensitive: true` (74) | live, by the keyword sniff (`rules.py:35`) |
| `editorial` | EDITOR_CLERK, EDITOR_HEAD_OF_UNIT, EDITOR_HEAD_OF_SECTION, EDITOR_HEAD_OF_DEPARTMENT, EDITOR_DEPUTY_DG, EDITOR_DG | the six carry a byte-identical `does_not` ("Modify the deliverable or the amendments master", "Gate whether the deliverable ships", 94-129); the rank is chosen by escalation (`pipeline.py:2364-2376`), so one subject for the board, not one per rank | live (the whole registry per rank, `:2425`) |
| `amendment` | AMENDMENT_DRAFTER | does "Propose rephrased text for flagged passages per convention guidelines" (80); does_not "Invent findings" (83) | partial: reads findings, not rules; the model call is off by default |
| `extraction` | PROCESSOR | does "Extract content from source documents", "Draft outputs in prose or structured form" (7); does_not "Verify its own work" (8) | none |
| `intent` | SPEECH_ACT_TAGGER | does "Classify pragmatic intent of utterances" (65) | none (audit-only in effect: no consumer of its tags found in `scripts/`) |
| `references` | CITATION_RESOLVER, ARCHIVIST | CITATION_RESOLVER does "Build cross-document reference graphs", "Map citation chains" (59); ARCHIVIST does "Index documents", "Establish chronology", "Maintain reference chains" (46), does_not "Analyze (evaluative judgment)" (48), so the subject is resolution and order, never a judgment about where a citation is required | none (CITATION_RESOLVER is AUDIT-ONLY, `agent_contracts.json:226`) |
| `actors` | INST_FINDER | does "Map topics to institutions", "Build institution registries" (53) | none (AUDIT-ONLY, `agent_contracts.json:211`) |

Twelve subjects, eighteen agents, each agent in exactly one. No subject name or definition
is a term or stem of any family in `config/domain_vocabulary.json` (checked by all three
verifiers). Two names were chosen against a near alternative for a stated reason:
`conformance` rather than `compliance` (a verifier flagged `compliance` as naming a field of
practice; `conformance` says the same thing without that reading) and `basis` rather than
`grounding` (the repo already uses "grounding" for `input/context/` files and the
`grounding_summary.md` deliverable; a second meaning would collide).

**Finer labels are the operator's option, and change no routing.** An operator who wants to
write `[figures]`, `[presence]` or `[practice]` on a rule rather than `[conformance]` can have
PRACTICE_AUDITOR declare all four. The comparison does not care; the pairing map still decides
the unit by the rule text's field vocabulary (`pairing_map.py:217-231`), and the arithmetic
still decides what is computable (`paired_review.py:918-1011`). The subject decides the agent,
nothing else. This is also the answer to the mechanism angle's 23: those distinctions are real,
but they are distinctions in what the pipeline computes, not in who receives the rule.

**What a rule shape looks like under each subject**, so the operator can test the set against
rules they would actually write (domain-free examples):

- `conformance`: "every figure must fall inside the band the reference gives"; "every entry must
  state a value under each label the reference marks as required"; "the steps recorded must
  follow the order the reference prescribes".
- `wording`: "one term per concept, the glossary's term wherever the concept appears"; "the
  document keeps one register throughout"; "a reference to another document follows one
  citation form".
- `basis`: "a statement of what applies must rest on a passage in the reference corpus; a
  statement with no passage is thin, not wrong".
- `facts`: "a claim about the outside world must be confirmed against a source outside the
  corpus or marked unverifiable".
- `fidelity`: "a passage restated from the source must not add, drop or alter what the source
  states".
- `redaction`: "any grouped-digit identifier attached to a named person must be withheld from
  every output".
- `editorial`: "findings record what conflicts with a stated rule, never a guess about cause or
  priority"; "no appraisal, no diagnosis, no speculation". These scope-restricting rules exist
  in every shipped corpus today (`device_conventions.md:56-60`, `cataloguing_conventions.md:45`,
  `lab_conventions.md:36`) and have no dedicated consumer; the board's advisory review is the
  one place that reads the whole deliverable against them.
- `references`: "every reference to another document must resolve to a document in the corpus";
  "a later version is listed after the earlier one".
- `actors`: "a body named in the document must appear in the reference's list of bodies".
- `intent`: "a sentence written as a recommendation must not be counted as an obligation".
- `extraction`, `amendment`: rules about the pipeline's own draft or its own corrections
  ("keep the source's numbering"; "a margin comment names the rule and the passage"). All three
  verifiers found these are constraints on pipeline output, already enforced by contract,
  rather than something an operator writes about a document. They are declared so that every
  agent declares something; whether PROCESSOR and AMENDMENT_DRAFTER should instead declare an
  empty list with a note is the operator's call (last section).

## What W3 becomes once assignment exists

W3 ("firing, and the fourth visible state") was skipped because "an agent with no conventions
assigned" was not a state that could occur (`docs/fix/STEP_W3_REPORT.md:12-19`). With the
assignment it is a state that occurs at load, and W3 becomes three concrete pieces, each
following a pattern already in the repo:

1. **The firing gate.** In the wide loop (`pipeline.py:1490-1505`) build a task only for a
   convention-review agent whose `by_agent` list is non-empty, and zip the same filtered list
   at `:1505`; `_gather_or_serial` (`:946-950`) already tolerates an empty task list. In paired
   mode, zero assigned rules for the judging agent means zero plans and zero calls, which
   `:1679-1710` already handles. The gate applies to the convention-review phase only: the
   production agents run regardless, because they produce the material the review consumes,
   and gating them on rules would starve the review. The two denominators above follow.
2. **The fourth visible state.** A new holder appended in `loadFindings`
   (`console.html:2147-2162`), an `apiJson('/runs/<id>/convention-assignment')`, and a render
   function that returns `''` when there is nothing to say and otherwise `h2` + muted note +
   `ul`, in the two wordings: Reviewer "Agents with nothing to check (N)" and "Rules no agent
   handles (N)"; Developer "convention_assignment.agents_with_nothing_assigned (N)" and
   "convention_assignment.unassigned (N)". Same data in both views, wording only. The three
   states already built (an amendment, a refused finding, a failed contract) are untouched.
3. **The gate check**, with a real neutralise-and-restore target: on a temporary registry and
   a temporary agent list, an agent declaring a subject no rule carries is shown NOT to be
   dispatched (the wide loop's task list omits it), an unassigned rule is shown in the
   assignment file and on the bus, and the route and the console render both; then the
   declaration is added to a rule and the agent is shown to be dispatched again. A second
   neutralisation removes an agent's `subjects` key entirely and expects the gate to fail on
   the missing key, so an undeclared agent can never pass as one with nothing assigned.

## Which of W4's unresolved harness parts this closes

`config/agent_harness.json` marks three parts unresolved for every agent
(`build_agent_harness.py:158-176`, constants copied per agent at `:213, :215, :217`):

- **Part 3, the rule cluster assigned to it: closes.** The per-agent value is the agent's
  declared `subjects` (from the registry, so the builder needs no new source) and, per run,
  the rules the assignment gave it. The harness stays a description of the agent, not of a
  run, so it carries the declaration and names the assignment file as where the per-run
  cluster is read.
- **Part 4, testing against that cluster: closes**, since its stated reason was only its
  dependence on part 3. Its value is the gate check above (the cluster is proved by
  neutralising a declaration and watching the assignment change) and, per agent,
  `scripts/harness/run_agent.py` run with a rule from that agent's own cluster.
- **Part 8, fires at all: must be regenerated**, because its text for the ten unconditional
  agents asserts "No per-agent rule-cluster gate exists (W2 stopped before one could)"
  (`build_agent_harness.py:91-99`), which becomes false for the convention-review agents. The
  separately owed D6 clause for LEGAL_ANALYST (`docs/fix/STEP_W6_REPORT.md:189-194`) belongs
  in the same regeneration.
- **Part 5, ontology: stays unresolved** until W7.

Gate check 195 hardcodes `KNOWN_UNRESOLVED_PARTS = {rule_cluster, testing_against_cluster,
ontology}` and fails if any of them is marked decided (`verify_session1.py:14398, 14427-14430`),
so closing parts 3 and 4 means shrinking that set to `{ontology}` in the same commit, or the
gate goes red by design.

## What the operator still has to settle

Numbered so each can be answered in a line.

1. **Untagged rules.** Keep today's routing (PRACTICE_AUDITOR and STYLE_GUARDIAN) and list them
   as `untagged (default routing)`, recommended; or treat as unassigned; or refuse the parse.
2. **Overlap semantics.** Any overlap between a rule's tags and an agent's list (recommended,
   and what the pseudocode does), or full containment.
3. **Where the agent list lives.** `subjects` in `config/agent_registry.json` (recommended), or
   a separate file.
4. **Tag syntax on the operator's file.** Bracket tags on the heading (recommended), a
   `subject:` line, or both; and whether the same read should also take severity from the
   bracket, fixing the `[required]`-ignored defect at the same time.
5. **Agents with no consumer.** Do PROCESSOR, SPEECH_ACT_TAGGER, ARCHIVIST, INST_FINDER and
   CITATION_RESOLVER declare a subject anyway (as proposed, visible as "declared, no path"), or
   an empty list with a note; and is wiring a rule path for any of them part of this change or
   a later one. The same question for AMENDMENT_DRAFTER.
6. **Scope of "does not run".** Convention-review agents only (recommended), or every agent
   with a consumer.
7. **Paired mode's judging agent.** Stays PRACTICE_AUDITOR for every pair (`pipeline.py:1679`),
   or the subject chooses it, so a `wording` pair nothing could compute goes to STYLE_GUARDIAN.
   The second makes STYLE_GUARDIAN fire in paired mode for the first time.
8. **The two English vocabularies now in code.** Retire `_CATEGORY_KEYWORDS`
   (`convention_parser.py:240-248`) once tags exist, or keep it for id-less headings. The
   redaction keyword sniff (`rules.py:35, 63-66`) should stay as a second net whatever is
   decided: under LAW-IV a rule the operator forgot to tag must never silently stop compiling.
9. **The names.** `conformance` (or `compliance`), `basis` (or `grounding`), `references` (or
   `citations`), `editorial` as one subject for six ranks, `actors`, `intent`. And singular or
   plural as the canonical form, since the comparison does not fold.
10. **The preamble defect.** Whether the parser is fixed in the same change so that prose
    before the first rule heading is not minted as rules (below).

## Things found on the way, not fixed here

- **Prose before the first heading becomes rules.** `_parse_text_lines` treats every
  paragraph as a rule (`convention_parser.py:166-215`); the `current_section = "preamble"`
  string is computed (169) but the flush closure's `section` parameter is never used
  (173-183). In `device_conventions.md` the two paragraphs under the file title (lines 3-4,
  6-7) became CONV-001 and CONV-002 with category `review` (the first word of the title
  heading, `:278`), and the `---` rule at line 9 is neither heading, list item nor blank, so it
  was minted as CONV-003 and then dropped by the `len(rule) >= 16` filter (215), which runs
  after ids are minted (113-115) and so leaves the gap. This is the W6 finding, now traced.
- **The `[required]` tag on a heading is discarded** (above); severity comes from the rule
  text alone, so CONV-006 is `advisory` against its author's `[required]`.
- **`config/agent_registry.json:127`** (EDITOR_DG's first `does` entry) contains two em
  dashes. The repo's hard rule is no em dashes anywhere; a config file is not exempt.
- **`config/domain_vocabulary.json` has no `previous_domain` family**, though its own note at
  line 14 and `verify_session1._previous_domain_pattern` (91-104) refer to one; check 22
  therefore takes its empty branch and passes (558-590).
- **Genesis Section C promises a category filter for STYLE_GUARDIAN** (`genesis.md:1312-1314`)
  that the code never implemented (`pipeline.py:1463` hands it every id). The subject
  comparison would fulfil that promise by a different mechanism; whether that is recorded as
  an appended genesis note is a governance question, not a code one.
- **`config/convention_registry.json` is stale relative to `input/conventions/`**, which is
  empty after W6's restore; the registry still holds the device corpus's ten rules from the
  07:17Z BOOT. It is regenerated at every BOOT and is gitignored, so this is a note, not a
  defect.

## What is built

Nothing. No code, no config, no gate check, no README change. This file is the whole of the
deliverable, left uncommitted for the operator to read; a commit of this file alone changes no
behaviour and can be made on the operator's word.

## Addendum, 2026-09-11: paired mode after the first tagged run (step A)

Decision 7 above chose a per-plan judging agent and said "do not filter pairs to a fixed
agent". Commit 3 built it with a fallback: a rule whose consumers hold no convention-review
agent was still judged by PRACTICE_AUDITOR. The first run on a tagged corpus showed what
that means: the pairing map never reads the assignment, so the tags changed nothing in
paired mode and the three board-only rules still reached the judging agent (51 of 64 pairs).
The operator's decision after that run: a plan whose rule has no convention-review consumer
makes no call and is recorded in the pairing map as assigned to the board only, never
silently dropped; wide mode's registry excerpt is filtered the same way. Built as step A
(`pipeline._paired_judging_agent` returns None for such a rule; `not_judged` and
`reattributed` in `audit/pairing_map.json`; `_wide_registry_for_agent`; gate check 206),
without measurement: no run has scored it. An untagged rule keeps PRACTICE_AUDITOR, as
answer 1 requires. Paired mode needs no separate firing gate (step B): the judging agent is
chosen per plan, so an agent with no assigned rule and no untagged rule receives no plan.
