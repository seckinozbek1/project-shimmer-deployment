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
own gate exercises today: a document-comparison scenario built from real, publicly reported
figures with every real party name replaced by an obvious placeholder (Company A, Union B)
before publication, and a self-authored device-log corpus built on 11 September 2026 to
measure neighbour context and convention distribution, not yet scored.

**What has and has not been measured, stated here rather than in a footnote.** Every scored
figure in this README (sections J and K) comes from runs made before 10 September
2026 on the code of the initial snapshot. On 10 and 11 September the review path changed in
more than a dozen commits (neighbour context, unit order, the rule-id resolver, the
convention assignment and per-plan judging agent, the convention distribution, call
evidence, longest-match labels, declared scope with Python-first absence, the container).
Each of those changes was traced in code and is proved on gate fixtures; **none has been
scored by a run.** The one corpus built to measure them, `device_log_review`, was run twice
on 11 September and stopped by the operator both times before any deliverable existed; its
clean twin was never run. The last scored run predates all of that work, and the measurement
is owed. Until it is made, every mechanism dated 10 or 11 September below should be read as
built, not as working, and the worst-case reading is the honest one.

**This repository is a public source snapshot, MIT licensed** (see `LICENSE` and
`CITATION.cff`). It carries the source code, the configuration, and the test corpora the
repository's own gate exercises; it does not carry any run history, any private material, or
any directory a run creates. `input/`, `output/`, `durable/`, and `tests/` (the full list is
below) are not part of this snapshot; section G explains what each one is for and what you
supply or generate to get one. This README is the first read for anyone cloning it fresh. It
is honest about what
works and what does not (sections J and K), and honest about the gap between what a working
deployment looks like and what a source-only snapshot ships (section G, section L).
Three operational documents sit alongside it: `docs/RUNBOOK.md` (install, launch, submit,
watch, approve, what each status means, what to do when a run hangs or BLOCKs, how to back
up and restore, how to read `cost_tracker.json`), `docs/THREAT_MODEL.md` (assets, trust
boundaries, threats with their current mitigation and residual risk, and what is
deliberately out of scope), and `docs/PRODUCTIZATION_STATE.md` (where the productization
chain stands, commit by commit, and what is owed).

### What's in this repository

202 tracked files at the time of writing (source, configuration, documentation, and test
corpora; counted from `git ls-files`, and the same count from a tree walk with the
not-shipped directories excluded). The exact number has gone stale within a day of being
written twice, so read it as "about 190". No compiled bytecode, no run output, and no cache
directory is tracked; those are excluded by `.gitignore` and, if present locally, are never
committed.

```
shimmer-deployment/
├── README.md, CLAUDE.md, genesis.md      the guide, the agent operating contract, the spec
├── LICENSE, CITATION.cff                 MIT license, citation metadata
├── requirements.txt                      pinned Python dependencies
├── shimmer.bat, shimmer.sh               the launcher: builds .venv, installs deps, menu
├── Dockerfile, compose.yaml,             the container image (CUDA base, Python 3.9, the
│   .dockerignore, .gitattributes         pinned requirements, optionally the model weights),
│                                          the run flags recorded as two compose profiles,
│                                          what the build context excludes, and the LF pin on
│                                          shell scripts so the container can exec them
├── scripts/                              the pipeline, the one agent wrapper that runs all
│                                          18 registry agents, the server, the gate
│                                          (scripts/verify_session1.py), the convention
│                                          assignment, the call-evidence recorder and the
│                                          false-negative classifier, the harness builder,
│                                          the ontology store, its reader, the relation
│                                          extractor, the conflict memory and the candidate
│                                          finder, harness/, sensitivity_layer/, ui/ (the
│                                          console, one HTML file plus its vendored typeface)
├── corpus_ingest/                        the external corpus ingestion contract, validator,
│                                          and its own test fixtures
├── config/                               governance and compiled config (constitution,
│                                          agent registry and contracts, the generated
│                                          nine-part agent harness, domain vocabulary,
│                                          institution names, review scope, pricing, local
│                                          model ids, editorial board tunables, redaction
│                                          cues, rename tolerance, relation patterns)
├── benchmark/corpora/                    the shipped test corpora (five scenarios in six
│                                          directories, one with a clean twin) and their
│                                          answer keys (see "Test corpora from other
│                                          domains", H)
├── tools/                                run wrappers: run_local_demo, stage_corpus,
│                                          score_corpus, entrypoint.sh (the container entry
│                                          point), archive_ontology_stores (the ontology
│                                          stores as one dated zip outside the repository),
│                                          console_preview (a throwaway local harness for
│                                          looking at the console, not the product)
└── docs/
    ├── RUNBOOK.md, THREAT_MODEL.md,      operational reference (see above) and the state
    │   PRODUCTIZATION_STATE.md           of the productization chain
    ├── api/                              the console's design (CONSOLE_PLAN, CONSOLE_LANGUAGE,
    │                                      CONSOLE_LAYOUT_PLAN, CONSOLE_STATE_AUDIT), the API
    │                                      surface (SURFACE_DESIGN, SURFACE_INVENTORY), the
    │                                      unit-context design (UNIT_CONTEXT_DESIGN) and the
    │                                      convention assignment design
    │                                      (CONVENTION_ASSIGNMENT_DESIGN)
    └── fix/                              one report per productization step
                                           (STEP_*_REPORT.md), the D options paper, and the
                                           console screenshots
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

| Stage | Agent | Backend / model | Subjects |
|---|---|---|---|
| Read + extract (per doc) | PROCESSOR | Claude Sonnet 4.6 | none, by decision |
| | SPEECH_ACT_TAGGER | Claude Haiku 4.5 | none, by decision |
| | LEGAL_ANALYST | Claude Opus 4.8 | `basis` |
| Read + extract (corpus) | ARCHIVIST | Claude Sonnet 4.6 | none, by decision |
| | INST_FINDER | Claude Haiku 4.5 | none, by decision |
| | CITATION_RESOLVER | Claude Haiku 4.5 | none, by decision |
| Verify + audit | VERIFIER | GPT-4o | `fidelity` |
| | FACT_CHECKER (web) | GPT-4o | `facts` |
| Convention review | PRACTICE_AUDITOR (web) | GPT-4o | `conformance` |
| | STYLE_GUARDIAN | Claude Haiku 4.5 | `wording` |
| Amend | AMENDMENT_DRAFTER | Claude Opus 4.8 | none, by decision |
| Editorial board (lower) | EDITOR_CLERK, EDITOR_HEAD_OF_UNIT, EDITOR_HEAD_OF_SECTION | Claude Opus 4.8 | `editorial` |
| Editorial board (upper) | EDITOR_HEAD_OF_DEPARTMENT, EDITOR_DEPUTY_DG, EDITOR_DG | GPT-4o | `editorial` |
| Redact | REDACTOR | Qwen 2.5 7B Instruct (local) | `redaction` |

The GPT auditors review Claude-produced content, satisfying LAW-III. The editorial board
is a six-rank family split (3 Claude lower ranks, 3 GPT upper ranks). REDACTOR is the only
agent permitted to handle sensitive content, and it runs offline. Only FACT_CHECKER and
PRACTICE_AUDITOR may reach the web (`may_use_web`).

An agent's `subjects` (declared in `config/agent_registry.json`, added 11 September 2026)
decide which convention rules reach it: a rule's heading bracket tags (section E) are
compared with each agent's subjects by exact token equality, once at BOOT, by code that
names no subject. Six agents declare none on purpose, each with a `subjects_note` saying
why: PROCESSOR, ARCHIVIST, SPEECH_ACT_TAGGER and AMENDMENT_DRAFTER are reached by no
convention-review path, and INST_FINDER and CITATION_RESOLVER post output that no
deliverable reads today.

#### Why eight agents made no model call in the saved reviews

The two 12 September device reviews each called ten of the eighteen agents,
with 29 and 39 calls respectively. `cost_tracker.jsonl` and `call_evidence.jsonl`
agree agent by agent. All eight rules had consumers; that does not require all
eighteen agents to run. The same eight had no call in both runs:

| Agent | Why no model call | Correct under the current policy? |
|---|---|---|
| STYLE_GUARDIAN | No rule was assigned to its `wording` subject, and no rule was untagged. | Yes. The convention-review firing gate excludes it. |
| AMENDMENT_DRAFTER | Phase 6 selected `template_path`; typed findings produced amendments without optional model polishing. | Yes. This is the default synthesis route. |
| REDACTOR | Redaction was explicitly waived and the privacy stage logged `non_sensitive_mode`. | Yes for those declared non-sensitive runs; this is not a completed privacy check. |
| EDITOR_HEAD_OF_UNIT | The clerk did not trigger escalation, so the next rank was not summoned. | Yes under the configured escalation policy. |
| EDITOR_HEAD_OF_SECTION | No escalation chain reached this rank. | Yes under the same policy. |
| EDITOR_HEAD_OF_DEPARTMENT | No escalation chain reached this rank. | Yes under the same policy. |
| EDITOR_DEPUTY_DG | No escalation chain reached this rank. | Yes under the same policy. |
| EDITOR_DG | No escalation chain reached this rank. | Yes under the same policy. |

Both saved board records say `REVIEWED`, `ranks_run: [EDITOR_CLERK]`, `rounds: 0`.
The clerk returned four and three `concern` observations, all `CONFIDENT`, with
no `out_of_mandate` flag. The actual escalation predicate returns false for both:
`CONFIDENT` maps to 1.0, above the configured 0.7 threshold. A concern verdict
alone does not summon a senior rank. Replaying an otherwise identical uncertain
observation does trigger escalation. This explains who was called; it does not
validate the clerk's claims or count the five uncalled ranks as finding nothing.
The saved logs, board artifacts and executed predicate results are recorded in
`docs/fix/LEDGER.md` under SIX.

#### What the scorer can say about a rule's review

`tools/score_corpus.py` displays a review state for each planted entry. It reads
`audit/convention_assignment.json`, the unit's existing `suspended` record in
`audit/pairing_map.json`, and `logs/call_evidence.jsonl`. It never re-evaluates an
`unless` condition or treats assignment as proof that a model was asked.

| Review state | Recorded evidence |
|---|---|
| `never_assigned` | The rule's assignment says `unassigned`. |
| `no_consumer` | The rule's assignment says `assigned_no_consumer`. |
| `suspended` | The planner withdrew this exact unit and rule. Another unit under the same rule is unaffected. |
| `asked` | A call to an assigned consumer received the rule text and the unit. A clipped or merely requested rule does not count. |
| `assigned_not_asked` | Call evidence exists, but no assigned consumer has recorded exposure to that unit and rule. |
| `unknown` | Required evidence is missing or ambiguous, including an older or untagged assignment with no recorded consumer list. |

The scorer separately counts asked entries with no matching finding. That does
not prove the response succeeded or that the model made a reasoning error. Raw
recall still includes every planted entry, including any finding on a suspended
unit. Asked recall includes only recorded exposure to assigned consumers and
excludes suspended entries; it remains a measure of location, not correct reason.
A suspended entry is shown in the table and suspension count, and is excluded
from the false-negative mechanism diagnosis. Its withdrawal remains the paired
review's state even if an earlier broad prompt exposed the rule. Missing or
ambiguous artifacts stay visible as unknown. Older paired-call logs store a numeric
document position; the reader accepts that format only with a uniquely resolved
unit, while an actual document identifier retains its own scope. Check 218 executes these distinctions
through the real scorer over declared temporary artifacts and a synthetic key.

#### The local profile (`--backend-profile local`)

`--backend-profile local` remaps **17 of the 18 agents** to two local models and makes no
provider API call in a **review** run. REDACTOR is the exception: it was already local. The
agent-to-backend map lives in `pipeline._LOCAL_PROFILE` (the LAW-III producer/auditor split is
hardcoded there and never read from config); the two model ids are overwritten at import by
`_resolve_local_models` from `config/local_models.json`. The flag also sets
`SHIMMER_BACKEND_PROFILE`, because five behaviours (agent serialisation, the document clip, the
progress display, the role anchor, CPU embedding) key off the environment variable rather than
the flag; a run started with the flag alone once loaded local models and then ran them
concurrently, which cost a 47 minute run (killed in phase 3, before `apply_backend_profile`
made the flag set the variable; the failure cannot recur from the flag alone). **Draft mode is
not covered by the profile:** phase 0 calls the Anthropic path directly (`_draft_generate`
through `_draft_generate_with_evidence`, which records the call's evidence and then calls
`AgentWrapper.call_claude`, never `dispatch`, so the backend profile is never consulted) while
the profile has already rewritten AMENDMENT_DRAFTER's model id to a local one, so `--task draft
--backend-profile local` fails at memo generation and exits 5. Drafting needs the cloud profile
until phase 0 goes through `dispatch`.

| Cloud role | Agents | Local model |
|---|---|---|
| producer (11) | PROCESSOR, LEGAL_ANALYST, STYLE_GUARDIAN, ARCHIVIST, INST_FINDER, CITATION_RESOLVER, SPEECH_ACT_TAGGER, AMENDMENT_DRAFTER, EDITOR_CLERK, EDITOR_HEAD_OF_UNIT, EDITOR_HEAD_OF_SECTION | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` |
| auditor (6) | VERIFIER, FACT_CHECKER, PRACTICE_AUDITOR, EDITOR_HEAD_OF_DEPARTMENT, EDITOR_DEPUTY_DG, EDITOR_DG | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` |
| redactor (1) | REDACTOR | `Qwen/Qwen2.5-7B-Instruct` (from the registry, not remapped) |

What this costs, measured rather than assumed: **$0.00 in provider cost and no provider API
call** (measured across every local-profile run in the operator's own working record, not
published in this snapshot; the cloud comparison figure quoted in section J is historical and
is not reproducible here). "No network" is narrower: before 10 September 2026 the local loader
still contacted the model hub on every load (fixed that day; gate check 193 now proves a cached
load with the network blocked at the socket), and the embedding model is fetched on first use
if it is not cached. The local auditor is the model that fills the typed Finding record, and on
a document where arithmetic can settle nothing it produced **one valid typed Finding out of 37
replies**, and even that one carried no usable rule id, so nothing reached the deliverable
(section J, the catalogue corpus). That figure predates 10 and 11 September: the rule id it
lacked was being written under the agent's own contract name, `procedure_id`, and is now read
(`finding_record.resolved_rule_id`); `relation`, `record_verdict` and `explanation` are now
required fields for PRACTICE_AUDITOR; and the wide-mode unit-id mismatch is closed (the
paired-mode gap, section H, is still open). The figure has not been re-measured since. The local profile also switches the review to `paired` mode by
default. The LAW-III family split still holds locally (a Qwen producer, a Phi auditor; the
backend column is never read from config), but the auditor is a 3.8B model rather than
GPT-4o, so the separation buys far less scrutiny than the cloud pairing. Two consequences
worth stating plainly: the quality figures in section J are local-profile figures, and no
cloud run of the newer corpora has been made.

**The output budget is sized per call type, not one number for every local call** (check 216).
Before 11 September every local call, regardless of what it was being asked to produce, was
capped by one hardcoded ceiling in `agent_wrapper.py`, `min(max_tokens, 1024)`, a proxy for a
wall-clock bound rather than a measured content requirement (local `generate()` has no
wall-clock timeout parameter, so wall time is bounded by token count instead, decoding speed on
a given device being roughly constant). Measured on a real run against the device corpus: 9 of
16 calls hit exactly 1024, several producing zero usable items (`parse_trace` showed dozens of
recovery candidates, mostly empty, the shape a response cut mid-item leaves behind), and the one
preserved raw truncated response lost its sixth finding entirely, cut mid-string with no closing
quote. The five PRACTICE_AUDITOR paired-judging calls that did NOT hit the cap ranged 202 to 645
tokens, real evidence that call type's true ceiling sits well under 1024. `pipeline.py` now
names five budgets, each wired to its real call site: `PAIRED_JUDGING_MAX_TOKENS` (768, below
the old 1024 with headroom above the largest real, uncapped call observed), and
`AUDIT_MAX_TOKENS`/`PRODUCTION_MAX_TOKENS`/`DEEPEN_MAX_TOKENS`/`WIDE_REVIEW_MAX_TOKENS` (2048,
raised rather than left at 1024 for every call type with direct evidence of losing output
there; wide-mode review was not exercised on the measured run, so its number is carried forward
unchanged rather than guessed). `agent_wrapper.LOCAL_MAX_OUTPUT_TOKENS` (8192) is the outer
ceiling. The five phase defaults above remain below it; larger requests are bounded by it.
Both local models' own context windows (Qwen 32768, Phi 131072 positions) are far
larger than any of these figures.

Local PROCESSOR calls have a separate `local_max_output_tokens: 8192` allowance
in `config/agent_contracts.json` (check 245). Both saved 12 September replies hit
2048 tokens; complete extraction envelopes for the current source paragraphs
measure 6288 and 6081 tokens with the cached producer tokenizer, or 4588 and 4381
with compact JSON. The largest item is 157 tokens. 8192 is the next doubling of
the former 4096 backstop that fits the measured full reply plus that reserve.
The local backstop permits this allowance. It also permits the editorial board's
existing `config/editorial_board.json` request of 8192, previously clamped to
4096 on local calls. FOUR therefore raised the board's effective ceiling too;
check 245 now exercises `_dispatch_rank` and verifies the actual dispatched
budget. The board's operator configuration remains authoritative within the
local ceiling. Ordinary production and audit defaults, and cloud budgets, stay
unchanged. Cloud calls ignore PROCESSOR's local declaration.
This gives the measured extraction room to finish; longer output can still hit
the limit and remains explicitly marked as truncated.

PROCESSOR feeds its parsed draft to VERIFIER and FACT_CHECKER in phase 5. Both
now receive `processor_draft_available` and `processor_draft_truncated`; a failed
contract's best-effort parse is withheld, and the auditors are told that missing
extraction content is not evidence of missing source content. Valid partial
replies remain available with their truncation flag. Paired review constructs
its units, comparisons and work payload from source directly. Optional recent
bus context can still carry previous agent output, so this is not a claim that
a model's entire prompt is independent of PROCESSOR.

The FOUR host gate is 244 PASS and the two known environment failures out of
246 checks. The local checkpoint image for this change is `shimmer:four`.

**Reply packaging and payload validity are separate.** The existing parser accepts
a complete canonical envelope inside prose, a Markdown code fence or inline code.
It prefers a populated valid envelope over an earlier empty one. Check 148 now
executes all those forms through `run_task` with mocked dispatch and verifies
that supplied item fields survive. Nested items, missing core fields, bare lists,
cut envelopes and replies with no JSON remain contract violations. No parser or
payload contract was loosened for FIVE. Replaying the three saved clean-run
violations found two unfinished envelopes and one reply with no JSON, all at
2048 tokens, rather than three valid payloads lost to packaging. This closes the
packaging claim; it does not establish that future model replies finish or obey
the contract. FOUR separately supplies measured room for local PROCESSOR output.

**A cut is now recorded as a cut, never silently parsed as a whole answer.** `call_local` and
`call_qwen` compare the generated length against the cap they were given (the model's own
end-of-sequence token always yields fewer tokens than the cap; reaching the cap always yields
exactly it, so no heuristic on the text is needed) and set `usage["truncated"]` accordingly.
`AgentWrapper.run_task` carries the flag three ways: onto a `CONTRACT_VIOLATION` bus post (a
truncated response that failed to parse, the shape a real VERIFIER call took), onto an
`AGENT_OUTPUT` bus post even when parsing succeeded (the more dangerous silent case: a cut
landing exactly at the end of a complete item reports fewer items than the agent actually had,
with nothing before this saying so), and onto the returned dict either way. Cloud calls do not
yet carry this signal: `call_claude`/`call_gpt` do not surface the SDK's own stop reason here,
a gap recorded rather than closed by this job.

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
  then parse conventions into a registry, assign each rule to the agents whose declared
  subjects match its bracket tags (written to `audit/convention_assignment.json` with the
  operator's own rule id beside every registry id; a rule no agent can act on is posted to
  the bus as `CONVENTION_UNASSIGNED`, never dropped), and build the reference index, which
  is built last because it needs the populated corpus.
- **Phase 1:** situation assessment (ORCHESTRATOR).
- **Phase 3-4:** content production. Per document: PROCESSOR, SPEECH_ACT_TAGGER,
  LEGAL_ANALYST. Corpus-level (once): ARCHIVIST, INST_FINDER, CITATION_RESOLVER.
- **Phase 5:** verification + fact-check (VERIFIER, FACT_CHECKER).
- **Phase 5.5:** convention review (PRACTICE_AUDITOR, STYLE_GUARDIAN). Skipped when no
  conventions are loaded. An agent fires only if the BOOT assignment gave it a rule or some
  loaded rule is untagged (the firing gate); in paired mode the judging agent is chosen per
  plan by the rule's subject. Runs in one of **two review modes** (see below).
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
- **Run end:** the learning engine captures provisions into the ontology stores under a
  storage scope (one scope today; a later provision supersedes an earlier one rather than
  deleting it), rebuilds its graph, and updates the GNN. For a draft run, the generated memo
  and its manifest are cleared.

Multilingual support is built in: every language is embedded into one shared cross-language
space (`BAAI/bge-m3`), so an English query retrieves against non-English passages. Per-document
language detection still runs, drives direction-aware output for right-to-left scripts, and
remains the hook if a language-specialised model is ever added.

### The two review modes

Phase 5.5 runs one of two ways. `--review-mode` selects it; with no flag the default is
**`paired` under the local backend profile and `wide` under cloud**
(`pipeline.resolve_review_mode`), and an explicit flag always wins.

- **`wide`:** each firing convention-review agent sees the document (clipped to 6500
  characters on the cloud profile, 12000 on local) and the rules assigned to it plus every
  untagged rule, and is asked to evaluate one against the other. At most one call per agent
  per document; a rule no convention-review agent is shown is recorded in the pairing map
  under `not_judged`.
- **`paired`:** the run first builds a **pairing map** (`<run>/audit/pairing_map.json`),
  deciding which rules could apply to which units of the document and recording the reason
  for every pairing and every non-pairing. Python then computes the arithmetic. Per pair the
  planner records a kind, and only some kinds cost a call: the figures disagree (`computed`
  or `band`, one call per distinct disagreement, the model shown the computed values and
  asked only whether the difference is material, never to recompute them); nothing is
  computable (`uncomputable`, one call on the text, one unit against one rule); a declared
  required field is absent (`absence_computed`, no call, Python decides); a scoped rule
  leaves the requirement to its own wording (`absence_judged`, one call per unit in scope);
  the figures agree (no finding, **no call**). A plan of any of those kinds whose rule has
  no judging agent is set aside under the map's per-document `not_judged` list, keeping its
  own kind, and makes no call. Every model call, in either mode, writes one structural record to
  `logs/call_evidence.jsonl` (which unit, neighbours, references and rules actually reached
  the prompt; never text), so a missed defect can later be classified as present in the
  payload, present upstream but never shown, or absent from the corpus (section H).
  `--pairs-per-unit N` caps the pairs considered per unit; a pair
  the cap drops is counted and logged, never silently skipped. A rule pairs with a unit when
  the unit carries every field label the rule's text names, and a label counts as named by
  the longest match only: a rule saying "calibration authority signature" names that label
  and not also a shorter "calibration authority" the document defines elsewhere (D, option
  1, 2026-09-11, built without measurement; gate check 208). A rule whose heading declares a
  scope pairs on that scope instead (section E), and its declared required fields become
  Python-decided absence findings (`absence_path: computed`, no call) or, without a declared
  requirement, one model question per unit in scope (`absence_path: judged`); the map's
  `absence` list and counts record which path decided each (D, option 2; gate check 209).

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

**The convention distribution reaches the paired path** (step A, 2026-09-11, built without
measurement: the gap was traced in code, the fix is proved on fixtures by gate check 206, and
no run has scored it). The pairing map never reads the assignment, so the operator's subject
tags used to change nothing in paired mode: a rule assigned to the editorial board only still
reached PRACTICE_AUDITOR by fallback. Now a plan whose rule has no convention-review consumer
(assigned to the board only, or matched by no agent) makes no call and is recorded in
`audit/pairing_map.json` under `not_judged` (unit, rule, kind, the consumers it was assigned
to, the status), never silently dropped; an untagged rule keeps PRACTICE_AUDITOR; a
rule-independent computed plan (a sum, a product, a missing field, the same arithmetic
whichever rule prompted it) attributed to such a rule is first re-attributed to a paired rule
on the same unit that has a judging agent, recorded under `reattributed`. Wide mode is
filtered the same way: each convention-review agent's registry excerpt and `evaluate_against`
list carry its assigned rules plus every untagged rule, and the rules no convention-review
agent is shown are recorded under `not_judged` with no unit. The board's own reading of those
rules in phase 6.5 is unchanged. Paired mode needs no separate firing gate (step B): the
judging agent is chosen per plan, so an agent with no assigned rule and no untagged rule
receives no plan; the one change is that the empty result a document with nothing to judge
owes goes under an agent the firing gate lets fire, or, when no agent fires, nowhere, logged
as `paired_review_no_firing_agent`. `GET /runs/{run_id}/pairs` serves `not_judged` and
`reattributed` beside the pairs; the `absence` record, `band_conditions` and the full
`prior_comparisons` detail are read from `audit/pairing_map.json` itself, the route carrying
the `prior_*` counts only and nothing of `absence` or `band_conditions` (an open gap,
recorded in section I).

**A rule's subject tag decides whether it is ever asked, and that is easy to get wrong.**
Measured on the 2026-09-12 overnight runs: the phase 5.5 log announced 75 calls on the device
corpus and 19 were made, 81 and 25 on its clean twin. The gap was `not_judged`, 51 and 54
plans, and 13 of them (16 on the clean twin) were CONV-D06, the neighbouring-entry rule. It
carried the operator's `[editorial]` tag, which routes to the six editorial agents, none of
which consumes rules in paired mode, so every neighbour pair was planned on the right fields
and never asked. The three neighbour-dependent planted flaws read as a mechanism failure when
the mechanism had paired them correctly and the question was never put. D06 is now tagged
`[conformance]`: it is a rule about the document, unlike D07 and D08, which are about how a
finding must be written and stay `[editorial]` and deliberately cost no calls. The fallback
that once sent every rule to PRACTICE_AUDITOR is NOT restored; restoring it would drag D07
and D08 back in and buy 38 calls per run to ask device entries about citation style.

The phase 5.5 log line now says `planned=` where it said `calls=`, because it is emitted
before the loop that makes the calls and can only know intentions. A second line,
`paired_review_calls`, reports `planned`, `made`, `not_judged` and `absence_computed` after
the loop, where all four are known and reconcile.

**A judged absence is checked before it is posted.** A scoped rule that declares no required
field asks the model whether its requirement applies to one unit and is met. The model may
answer that a field is missing, and on the 2026-09-12 clean twin nine such answers were
false: seven asserted a calibration authority signature missing from entries whose own parsed
fields list it. All nine named no field at all, so nothing could check, cite or score them.

Two refusals now apply, and the first is about FORM rather than truth. A `missing_field`
answer that names no field is refused as malformed: the operator's own grounding rule already
requires a finding to state the entry and the figures it concerns, and this is the same
discipline the verifiability gate applies when it downgrades an affirmative finding that
cites nothing. A model that spots a real absence and forgets to name the field is refused
too; naming it is the minimum for the claim to exist as a claim. Second, an answer that does
name a field is refused when the unit demonstrably carries that field, which Python has
already parsed into `fields_present`. Every other relation, and a named field the unit really
lacks, are left untouched. Refused answers are recorded under `absence_refused` in the
pairing map, never silently dropped.

No inference is made about which field an unnamed claim means. Two heuristics for that were
tried against the real artifacts and both suppressed a legitimate answer on a rule scoped on
one field whose requirement is about another.

### Normalisation: one tokeniser, shared

Every comparison between a rule's wording and a document's own labels runs through one
function, `pairing_map._norm_label`. It lowercases, splits on non-word characters, drops
closed-class stopwords and tokens of two characters or fewer, and folds a trailing plural.
Three properties matter, and each exists because its absence cost a measurable failure:

- **A hyphen JOINS two word characters rather than splitting them.** "Class-A" is the name of
  a device class, one token, not the word "class" followed by a letter. Splitting it and then
  dropping the single letter by the length floor collapsed "Class-A sensor", "Class-B sensor"
  and "Class-C sensor" into the identical `('class', 'sensor')`, so no band or field match
  could tell three different tolerance bands apart. The join is done with an ASCII sentinel
  substituted before the split, because a Unicode look-alike hyphen is *not* a word character
  under `re`'s own UNICODE classification and fails silently the same way the raw split did.
- **A trailing plural is folded** (`_stem`): strip a trailing `s`, or fold `-ies` to `-y`.
  Two suffix rules, no irregular plurals, nothing else. It refuses where a trailing `s` is
  almost never a plural marker: after `ss` ("class"), `us` ("corpus"), `is` ("diagnosis"),
  or on a word of three characters or fewer. Without it, a glossary saying "fault timestamp"
  and a rule saying "state the two timestamps" could never match, however the split was tuned.
- **Both sides go through it.** Two independent raw word-bag builders used to serve the rule
  side (`needed_fields`, `date_pair_for_rule`), and they had already drifted from each other
  and from this function before either defect was found. They were deleted rather than
  synchronised: a fold applied to one side of a subset test does nothing at all.

Checked against every corpus on disk before landing, not just the two device twins
(`docs/fix/HYPHEN_SURVEY.log`, `docs/fix/HYPHEN_PAIRS_CHECK.log`): 60-odd hyphenated tokens across
six corpora, and the label renames the stem causes (`rights` to `right`, `requires` to
`require` in `catalogue_records`) move both sides together, so the **pair sets are byte-identical
before and after on all twelve corpus documents**. The only behavioural change is the intended
one. Recorded limits, not claimed away: `len(w) > 2` is an alphabetic assumption that still
drops a CJK label, and the stem is English morphology specifically, which a language whose
plural is not a trailing `s` neither gains from nor loses to.

### Bands from the reference corpus

A rule often states no numbers of its own; it points at a table in the reference corpus.
`scripts/reference_tables.py` reads those tables so the comparison can be made in Python
instead of by a model reading prose. Five mechanisms, all structural, none carrying any
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
- **A labelled prose sentence is a table with the punctuation removed, one shape only** (check
  215): a LABEL, a colon, and a RANGE in the same sentence ("Class-A sensor: standard tolerance
  band 20 to 60 units."). `parse_prose_band_sentence` reads the label before the colon and the
  range after it with `cell_range`, the same reader a table cell uses, so the same refusal
  discipline applies without a second implementation: exactly two quantities of one unit close
  enough together to be a range, a descending pair refused, and a sentence carrying a third,
  unrelated figure refused rather than guessed at. `parse_prose_bands` groups every matching
  sentence in a passage into a synthetic table (one column of labels, one of ranges, headed by
  the words between the colon and the first figure, e.g. "standard tolerance band"), wired into
  `parse_tables` itself, so every existing caller of `bands_for_unit` reads a labelled prose band
  with no new call site. The reference material is never rewritten to make it parse: an operator's
  table stays a table and an operator's prose stays prose, read as written.

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

**One recorded limit, and one narrowed.** A key cell that encodes a numeric comparison in prose
("protein 12.5 percent and above") cannot be matched by word containment; the rows tie, the tie
is refused, and no band is produced rather than one being guessed. Resolving it would need a
list of direction words, which is exactly the domain leak the vocabulary probe exists to catch.
A band stated in prose rather than in a table used to go unread here entirely; check 215 reads
the one shape a labelled prose sentence takes (a label, a colon, a range, in one sentence, see
"Bands from the reference corpus" above), and a prose statement outside that shape, or the
rule-text path for a rule that states its own numbers, are both still covered as before.

### Duration arithmetic

Two of the device rules say "acknowledged within the standard fault window" or "must not
exceed the standard service interval", and both state their own instruction plainly: "state
the two timestamps and the gap between them." That is an instruction to compute, not to
judge, and nothing in this pipeline subtracted two dates before check 217.

`paired_review.date_pair_for_rule(unit_text, rule_text)` reads a date pair from a unit by the
rule's own connecting words, structurally, in one of two shapes: two SEPARATE `label: value`
lines each holding one ISO date ("Fault logged: 2026-06-01 09:00" / "Fault acknowledged:
2026-06-03 09:00"), or one label line whose value holds two ("Service record: last calibration
visit 2026-01-01, next calibration visit logged 2026-06-01"). The connecting words that must be
named by the rule are the label's own words UNIONED WITH the value's own words (dates removed),
not the label alone: a same-line pair's outer label may use different words from the ones
actually describing each date, the same reasoning Job A's `column_phrase` already applies to a
table header. A unit with no date field the rule names, or with a THIRD candidate the rule
could equally name, yields no pair: which one is the pair is not decidable by field matching
alone once ambiguity exists, and this function refuses rather than guesses, the same discipline
`reference_tables.py` already holds throughout.

`reference_tables.scalar_bound_from_entries(entries, rule_text)` reads the matching SINGLE-VALUE
bound from the reference corpus's own prose ("The standard fault window is 24 hours..."), the
sibling of Job A's range reader for a sentence that states one number rather than two: exactly
one quantity, connecting words (every content word in the sentence besides the number and its
unit) named by the rule, a tie between two candidate sentences refused rather than picked from.
`compute_checks` emits a `date_window` Finding relation only when BOTH a pair and a bound are
found for the same rule; either alone computes nothing, the same honest outcome
`bounds_from_rule` already gives a rule with no bound of its own.

**A pre-existing defect surfaced while proving this, in three places, and the fix closes all
three.** An externally supplied bound (Job C's own `duration_bound`, and R1's own
reference-table band before this fix) is invisible to `plan_calls`' "nothing computed" fallback,
which re-derives from the rule's text alone and never receives the caller's external bound. A
DISAGREEING external bound therefore double-booked: a correct plan from the per-rule loop, plus
a spurious second one asking the model the same question again. Reproduced with no Job C code
involved (an out-of-range table band, the R1 mechanism from before this job), so it was not new;
closed for both mechanisms by tracking every rule a band OR a duration check reached ANY verdict
for, agreeing or not, and excluding those from the fallback. An agreeing band or duration still
costs no call at all, the "computed and settled" outcome both were always meant to give. A THIRD
instance sits one layer further in: a rule that is BOTH scoped (D, option 2) AND settled by a
duration check used to get its declared `absence_judged` plan (minted unconditionally, before
the band/duration loop even runs) as well as the correct `duration` plan, asking the model a
now-redundant question when Python had already answered the sharper one. Not observed on the
device corpus today (D04's and D05's own duration checks do not currently succeed there), but
latent the moment either wording gap below closes; closed by dropping a scoped rule's declared
`absence_judged` plan when duration or band settles that same rule, while its own
`absence_computed` plans and its fallback to `absence_judged` when nothing is computed are both
left untouched.

**Real-corpus outcome: D04 settles; D05 does not, and no longer for a word-form reason.**
Both rules were blocked on singular/plural mismatches until the shared tokenizer gained a stem
(`pairing_map._norm_label`, "Normalisation" below): the bound sentence said "fault timestamp"
against a rule saying "state the two timestamps", and the value line said "calibration visit"
against a rule saying "logged calibration visits". The stem folds both, on both sides, so
**D04 now finds its date pair AND its 24-hour bound and settles**. D05's bound is also found,
once the search covers the document under review's own text: this corpus's task description
says plainly that "the document's own glossary section states the standard fault window,
service interval..." so the glossary lives INSIDE `device_log_flawed.md` itself, not in the
separate `device_class_reference.md` the way D01's class tolerance bands do, and excluding the
document under review (Job A's own table-reading pattern, copied here uncritically at first)
made D05 permanently unsolvable until the document's own text was searched too. **D05's date
pair needed a second, separate fix, one no stem could reach:** its value line's connecting
words carried "last", "next" and "record", none of which the rule states, because
`_label_lines_with_dates` collected the whole post-date remainder as if it were vocabulary the
rule could name. That was noise collection rather than matching. The connecting words are now
drawn PER DATE, from the window running from the previous date to this one, and for a two-date
line only their INTERSECTION is kept: a word describing what the pair IS sits beside both dates,
a word telling one date FROM the other sits beside only one. On the service record the windows
are {last, calibration, visit} and {next, calibration, visit, logged}, and the intersection is
{calibration, visit}, exactly what the rule names. The line's own label and its date
description are also kept as two independent routes rather than unioned, since requiring a rule
to state both meant the wrapper label "Service record" blocked a pair the rule describes
outright. Nothing here knows that "last" is an ordinal; it knows only that it sits beside one
date and not the other. **Both duration rules now settle on the flawed twin**, and on the clean
twin both compute, agree (9 hours against a 24-hour window, 73 days against a 90-day interval)
and cost no call at all.

### What the two fixes cost in model calls

The plan on both device twins, recomputed deterministically with the current tree and no run,
against the baseline this work started from:

| | flawed twin | clean twin |
|---|---|---|
| model calls before (normalisation and connecting words both unfixed) | 32 | 41 |
| model calls now | **17** | **23** |
| cut | 47% | 44% |

Where the calls went, flawed twin: D01 moves from `uncomputable` to 6 computed `band` plans
(the three class labels are distinguishable, so each reading meets its own class's tolerance
band), D04 and D05 each become one computed `duration` plan, and D02's 5 `absence_computed`
plans are unchanged. On the clean twin D01 yields 3 computed bands and both duration rules
compute, agree and produce no plan at all, which is why its settled count is lower while its
calls still fall. The remaining calls are D03 (genuine judgment, by the operator's own
decision) and D06 (neighbouring-entry, genuine judgment); D07 and D08 are never paired, being
properties of a finding's shape rather than comparisons over a document's fields.

This is the figure the work is judged on, and it is the one predicted from tracing the two
blockers rather than from the rule-to-field matcher, which was measured separately and changes
nothing on this corpus (field relevance does not propagate to unit pairing when a requirement
set is already satisfied).

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
An agent may name the rule under its own contract's field (PRACTICE_AUDITOR writes
`procedure_id`); every consumer reads it through `finding_record.resolved_rule_id`, which
accepts `rule_id`, `procedure_id`, `conv_id` or `convention_ref`, because five real irregular
findings had been dropped silently by a builder that read `rule_id` alone. For
PRACTICE_AUDITOR the `relation`, `record_verdict` and `explanation` are required, not
optional: measured before the change, 33 of 39 local calls asserted a violation with none of
them.

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
receive (3-4, 5, 5.5 and 6; the editorial board builds its own) and is echoed at the top of
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
changing only the amendment prose, recall moved from **2/9 to 5/9** on the original wheat
corpus (the 2/9 is one live draw of the model's wording, labelled as one draw rather than an
average; the deterministic ablation arms around it are what establish the conditional; the
figures predate the 10 and 11 September changes to the amendment builder and the scorer and
have not been re-measured), and a true band finding
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

A finding is never dropped on the way to an amendment. An irregular record the template
cannot build into one (no resolvable rule id, no locatable passage) is recorded with its
reason and posted to the bus as `AMENDMENT_REFUSED` (`GET /runs/{run_id}/amendment-refusals`);
a call whose output fails its contract is posted as `CONTRACT_VIOLATION`
(`GET /runs/{run_id}/contract-violations`). Every irregular finding a convention-review call
produces therefore ends as exactly one of an amendment or a refused finding, and a reply
that fails its contract ends as a contract violation; a valid reply with nothing irregular
is the fourth outcome, which is not silence either but a compliant empty answer.

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
appended to the run objectives the review phases receive (3-4, 5, 5.5 and 6, not the
editorial board) and echoed in `document_summary.md`
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

### Where a document's date comes from, and what happens when there is none

Tier 3 makes the date load-bearing: it decides whether a document is reviewed at all. The
date is resolved at BOOT by `scripts/document_dating.py`, and every tier is **local**.

1. **The filename.** The full date first (`2024_09_23` reads as 2024-09-23), then `YYYY-MM`,
   then a bare year.
2. **The document's own text.** The full date it states, then a bare-year scan. Neither is
   truncated.
3. **Container metadata** (PDF creation/modification date), low confidence.

There is **no network tier**. One existed and was removed rather than made conditional. It
searched the web for the document's title to guess a publication date, which meant two runs
over the same bytes could review different sets of documents depending on what a search
engine returned, and it sent the document's title off the machine on every non-sensitive run.
A measurement whose population is decided off-machine is not a measurement, and a title is
document content.

**An unresolved date is loud.** A document with no date fails the cutoff and is not reviewed,
which is invisible in the deliverables: a document that was never reviewed and a document
that was reviewed and produced no findings both show up as an absence of findings. So the
run records them in `audit/undated_documents.json`, the pipeline names each one on stderr,
`GET /runs/{run_id}/undated-documents` serves them, and the console lists them. `excluded`
(undated and not under review) is kept apart from `reviewed_anyway` (undated but named in a
manifest, which is not a drop).

**Some documents genuinely cannot be dated, and that is a limitation, not a bug.** Of the
twelve documents in the shipped test corpora, six state no year anywhere in their text and
carry none in their filename. Nothing local can date those, and the system will not guess.
If they are meant to be reviewed, the operator says so: name them in
`input/context/_review_targets.json`, or set `cutoff_type` to `all` in
`config/review_scope.json`. Putting a date in the filename also works, but it is the weakest
of the three, because it records what someone typed rather than what the document says.

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
  the operator's own id alongside it. A heading may also carry bracket tags,
  `## CONV-D01 , conv-value-in-range [required] [conformance]`: a token matching one of the
  three severity words the parser already classifies from rule text (`required`,
  `recommended`, `advisory`) sets that rule's severity directly instead of the text
  classification; every other token is a subject, carried on the registry entry's
  `subjects` list, read verbatim and lowercased, for the convention-assignment comparison:
  at BOOT each rule's tags are compared with the subjects each agent declares in
  `config/agent_registry.json` by exact token equality (code that names no subject), the
  result is written to `audit/convention_assignment.json` and served by
  `GET /runs/{run_id}/convention-assignment`, an untagged rule keeps today's routing to every
  convention-review agent, and a rule no agent can act on is posted to the bus as
  `CONVENTION_UNASSIGNED` rather than dropped (section H 4a for what an agent's cluster is,
  section I for the route). Two further bracket forms are declarations, read by their leading word and never
  as subjects (D, option 2, 2026-09-11, built without measurement; gate check 209):
  `[scope: class=A, device]` names the field labels, each optionally pinned to a value, that
  identify the units the rule governs, and `[requires: calibration authority signature]`
  names the field labels whose absence from a unit in scope is a finding. A rule with a
  declared scope pairs with exactly the units carrying its scope fields (and values), and
  the fields its text happens to name are no longer requirements, so a rule that mentions a
  glossary term is not rejected for every entry that lacks the glossary's label. Where a
  required field is declared and absent, Python decides and no model is called; where a
  scope is declared but no requirement is (the requirement is conditional in the rule's own
  words, "Class-A requires it, Class-B does not"), the model is asked one narrow question
  per unit in scope and its answer is stamped with the unit and rule by the pipeline. The
  pairing map records which path decided each absence. The labels and values are the
  operator's own; nothing derives a scope from text or counts. A heading with no brackets at
  all parses exactly as before. Prose written before the first heading that carries an
  operator rule id (a file title, an introduction, a scope statement) is preamble and is not
  minted as a rule. The rule is keyed on the operator id, not on position: a first heading
  that carries an id is a rule section, and a list item is never suppressed wherever it
  sits, so a conventions file that opens on an id-less heading with list items (the gate's
  own seed shape) parses exactly as before. One shipped corpus declares scopes: the device
  corpus's four absence rules (`benchmark/corpora/device_log_review/conventions/`), applied
  on the operator's corrected wording after a deterministic probe of the first draft
  (`docs/fix/STEP_DECL_REPORT.md`: a scope value must be written as the document writes it,
  `class=Class-A sensor` and not `class=A`, and a rule about a duration carries a scope and
  no requires, so the one entry it is about reaches the model, rather than a requires that
  turns it into a presence rule firing on every other entry). On that corpus the declared
  form plans 37 calls on the flawed log and 43 on the clean twin against 34 and 46 with no
  declaration, five and two of them Python-decided absences with no call. Unmeasured: no
  run has scored it.
- `review_mandate.md`: the reviewing entity, the engagement scope, and the review
  standard (advisory, grounded, with concrete proposed amendments).

**This repository does not ship a corpus or a convention set in `input/`**; `input/` is not
part of this snapshot (section G, "What's in this repository"). The corpus used to develop
and describe this mechanism was agricultural (one wheat producer-declaration sheet reviewed
against a reference corpus, in English), and that shape is what the paragraphs above
describe, but you supply your own conventions and corpus under `input/` to run a review; the
launcher's intake wizard (section H) walks you through placing them. Five corpora from other
domains DO ship, under `benchmark/corpora/` (section H), one of them with a clean twin, each
with a committed answer key; four are built from real public data and the fifth
(`device_log_review`) is synthetic, authored for this repository and held to the lower
standard its own key states. They are what this repository's own gate exercises. To review your own domain, place your conventions
and corpus under `input/` (or stage one of the shipped corpora with `tools/stage_corpus.py`);
nothing in `scripts/` is domain-specific.

Sensitivity is also convention-defined. A convention counts as a redaction rule when ANY of
four independent triggers fires, and the set is a union, so a trigger can only ever add a
redaction rule and never remove one:

1. its category or its id carries a redaction keyword (`confiden`, `redact`, `privacy`, `pii`);
2. its rule text uses a redact verb or prohibition phrasing ("must not contain", "shall not be
   published");
3. its action is `redact` **and the operator DECLARED that action**. An action inferred from
   the rule's wording never decides a redaction question: the heading bracket reads severity
   and subjects only, so on the review path an action is a keyword table's guess about a verb,
   and a guess must not settle a LAW-IV matter. Only the JSON convention path can declare one;
4. the **five-voter semantic ensemble** (below) reads the rule as redaction intent.

Trigger 2 matches BOTH VOICES of a prohibition: "the address must not be published" and "the
reviewer must not publish the client's address" both compile. It once matched only the passive
form, so an operator writing the active form had written a redaction rule the system silently
discarded, and under LAW-IV a silent non-compile publishes content the operator marked for
removal. The active list is deliberately narrow (`publish`, `disclose`, `print`, `reveal`,
`release`, `transmit`): verbs whose object is document content. `show` and `share` were tried
and removed, because "we must not show favouritism" compiled as a redaction rule.

A rule about what a REVIEWER may conclude is excluded even when it uses a redaction verb:
"Findings must withhold judgement about equipment condition" names no removable content, and is
a review convention, not a redaction rule.

The local redactor applies the rules that compile, and redaction intent that fails to compile is
warned about, never dropped silently. A rule that compiles but authorises **no shape detector**
is also reported, as `REDACTION_RULE_UNAPPLIED` on the bus: there are three detectors
(identifier, figure, name), and a rule naming an address, a date of birth, a location or free
text matches none of them. Authorising nothing is the correct answer for such a rule, but it
must not be a silent one, or the operator believes content is being removed when it is not. There is no engine-side default: with no compiled
redaction rule in force, a run hard-stops for a conscious operator choice (supply a rule, or
pass `--no-redaction-override`).

### The five-voter semantic ensemble

Where a decision rests on **what words mean**, it is decided by five independent voters against
operator-visible reference text, never by a literal keyword table and never by one method alone.
Regex keeps everything **structural**: declared syntax, bracket declarations, ids, delimiters,
formats, run-id shapes. That is reading, not interpreting.

The five are **SBERT**, **KeyBERT**, **TF-IDF**, **bag of words**, and **word by word
agreement**. A decision is yes at three of five or above.

The reason is measured, not preferred. A keyword table is one person's vocabulary frozen into
code, and it failed three times in this repository in the same shape, silently and in one
direction: a convention `severity` where 6 of 44 rules matched no pattern at all and fell to a
default; an `action` that read a rule about reviewer restraint as `redact`; and the passive and
active prohibition forms above.

Five properties hold, and each is enforced in code rather than by convention:

- **every decision records all five votes**, with score and matched reference, not only the
  outcome. A vote nobody can read is a keyword table with extra steps;
- **reference text lives in `config/semantic_references.json`**, beside the band tables and the
  domain vocabulary, where an operator can read and change it;
- **each threshold is measured**, in `config/semantic_thresholds.json`, with the error rate it
  produces recorded beside it. Method and full result: `docs/fix/ENSEMBLE_THRESHOLDS.md`;
- **no voter is dropped silently.** If fewer than five can run, the decision REFUSES and names
  the missing ones, because three of three is a different rule from three of five;
- **one interface for all five**, so a voter can be replaced or measured alone.

Two measured details worth knowing. A voter scoring exactly zero has found no evidence and
abstains into a no, whatever its threshold. And the dense voter, measured to have no misses,
may **veto a NO** at a higher bar of its own, never a yes: the veto can only add redaction,
which is the conservative direction.

**The model.** The ensemble uses the embedding model this project already ships (`BAAI/bge-m3`,
`scripts/embedding_store.py`), through the same loader and cache. No second model, and no new
Python dependency: `sentence-transformers`, `scikit-learn`, `numpy` and `torch` were already
required. **This makes the weights load-bearing for a parse-time decision.** Without them the
ensemble refuses, the three structural triggers still decide, and the refusal is recorded rather
than silently read as a no. In a container that does not carry the weights, redaction intent is
therefore decided by triggers 1 to 3 alone, exactly as it was before this change.

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
   OPENAI keys are required for the **cloud** profile; BRAVE is optional. The launcher asks
   which backend you will run on before the preflight, because the answer decides what
   readiness means. Under the local profile the preflight reports absent keys and carries on
   to the checks a local run actually depends on (Qwen reachability, the GPU), so a
   local-only operator reaches the menu with no key file at all. Under the cloud profile it
   still stops before the menu when no key file is found. It used to run the cloud checks
   unconditionally and exit on that same code, so a local-only operator could not reach the
   menu and never learned whether their local stack was ready. Model selection is owned by
   `config/agent_registry.json`, never by the key file.
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
   RAM at the 4-bit size. All three need torch and transformers; the two 4-bit checkpoints
   additionally need bitsandbytes (the quantised weights) and accelerate (the `device_map`
   load path), both pinned in `requirements.txt` since 10 and 11 September 2026. All run
   offline once cached. This step needs no action by hand, since local checkpoints are
   fetched automatically at first use (next paragraph).

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
of every run: `provisions.jsonl` and its immutable log `provisions_log.jsonl`, the proposal
accumulator `delta_proposals.jsonl`, all three kept per scope by the storage layer, then the
derived `graph.json` and `gnn_state.json`). None of these are source; none of them need to
exist before you start; the tools that need them create them.

`ontology/stores/` is unfinished, not dormant, and this is stated plainly rather than left
for a reader to assume from its place in the architecture: it writes real state every run
(a graph of documents, findings and the rules they cite, plus a small autoencoder fit over
that graph's structure) and **no phase of a review reads any of it back**. No agent payload,
no Finding-producing code, and no phase before 8 opens `graph.json` or `gnn_state.json`; the
only other write-path consumer is the module that builds the next run's graph from the last
one. It is real, executed machinery, not a stub, but the review itself does not draw on it,
and it should be read as exactly that rather than as a working cross-run relevance signal.

**A human can now read the store** (ontology chain, job 1). `scripts/ontology_reader.py` is
its first read path, and it answers the one question the store can answer today: which agent
produced which provision, under which rule, in which run, at which revision. It is reachable
three ways: `GET /ontology` and `GET /ontology/provisions/{id}` (section I), a section on the
console's Agents page that disappears when the store is empty, and the module's own
inspector, which needs no server and no run:

```
py -3.9 -X utf8 scripts/ontology_reader.py
py -3.9 -X utf8 scripts/ontology_reader.py --json
py -3.9 -X utf8 scripts/ontology_reader.py --provision "<document>::<REF-0001>"
```

What that reading is good for, said without overselling it: attribution after the fact (who
said this, under what rule, when), coverage (which rules and agents the store has ever seen,
so a rule that never produced a provision is visible), and the plain fact that the store is
no longer write-only, since a store nobody can inspect is indistinguishable from one that is
silently broken. What it is **not**: it is not retrieval, not relevance, and not a signal any
review draws on; it reads the provenance of decisions already made. The long-range case is
untouched by it, because that needs relations between provisions, which job 2 adds below and
which this reader does not itself produce. The reader carries identifiers and provenance only and never a provision's own text.
**Built, not measured**: every store in this repository is empty (`provisions.jsonl` is zero
bytes), since the only writer is run-end capture and no run has been made since the store was
scoped, so gate check 210 proves the read path on fixtures alone. The first real content
arrives on the first run after the move to a GPU box.

**Relations between provisions** (ontology chain, job 2) are the second thing the store can
now hold. The graph records where a finding came from and never that one provision relates to
another, which is exactly what the long-range case needs: a term defined at the start of a
document and used at the end, the distance the adjacent-neighbour mechanism explicitly does
not reach. `scripts/relation_extract.py` produces that relation two deterministic ways. A
cross-reference extractor, whose every pattern lives in `config/relation_patterns.json` and
none in code, resolves a captured reference to a real unit by exact match then unique
containment and **refuses an ambiguity** rather than picking one, because a wrong relation is
worse than none. And embedding similarity over units of the same document, with the ranker
**injected** rather than imported, so the module never depends on an embedding store and
never loads a model; only pairs at least two units apart are considered, since a unit is
trivially similar to its neighbour and that case is already covered. Relations are shaped as records
for the same scoped store provisions use, with a stable composite id so re-extraction
supersedes rather than duplicates, and read back by `relation_summary`, which keeps the two
mechanisms distinguishable: `by_method` counts observations while `relation_count` counts
pairs, so the two no longer sum to the same number once any pair is agreed, and that is the
point rather than an inconsistency. A relation says one unit names, or reads like, another;
it does **not** say they agree or conflict, and it is not evidence for any finding.

**One relation per pair, and agreement is a fact the store holds.** The two mechanisms used
to emit the same relationship twice, because the store id encoded direction and type and they
disagree on both: a cross-reference from unit 9 to unit 1 and a similarity between unit 1 and
unit 9 are one relationship written as two records that both persisted. Every count therefore
double-counted exactly the pair a reader would most want to trust, the one two independent
mechanisms agree on, and agreement was visible only as duplication. Now a pair is merged into
one record keyed on its sorted ids, carrying `found_by` (the mechanisms that found it),
`agreed` (derived, `len(found_by) > 1`, never asserted) and `observations`, one per mechanism,
each keeping **the direction that mechanism reported**, so a reader can see that the
cross-reference said one direction and similarity the other. Nothing is discarded by the
merge; the store id carries neither direction nor mechanism, which makes the duplicate
impossible by construction rather than merely unlikely.

**There is deliberately no weighting between the two mechanisms**, and none will be declared
until the long-range corpus is scored. The reason is recorded in
`config/relation_patterns.json` so nobody adds one casually: a cross-reference is a boolean (a
pattern matched and resolved unambiguously) while a similarity is a score that on the fixtures
occupied a band about 0.07 wide, so any weight mixing them would let the boolean decide every
ordering while the weight only appeared to be doing work. **One ordering rule is declared**,
because it needs no number: a pair found by both mechanisms ranks above a pair found by one.
Nothing beyond that is ordered.

**None of the three similarity settings is a measured value**, and the config says so beside
each one. `min_score` 0.75 and `max_per_unit` 3 are conventional defaults with no evidence
under them, written when the mechanism was built. `min_units_apart` 2 is the one with an
argument behind it, and the argument is structural rather than empirical: a unit is trivially
similar to the one beside it and the adjacent-neighbour mechanism already covers that case, so
the value follows from what this mechanism is for. Change any of them freely; none is a
finding.
**Built, not measured, not wired into a run, and nothing in a review reads a relation
today**: no phase of the pipeline imports the extractor, so no run produces or stores a
relation; gate check 211 proves both mechanisms on fixtures, and the operator scores them on the long-range corpus
after the move before anything relies on either.

**When the ontology and a rule disagree, the pair is refused** (ontology chain, job 3).
`scripts/ontology_conflicts.py` implements the operator's decision, and the wording matters
because every part of it is a rule about what NOT to do. A conflict is the narrow structural
case where the store remembers one governing rule for a provision and the current run would
apply another; nothing semantic is inferred, and the module compares identifiers, never
meanings. In the run that meets it the pair produces **nothing**: not a guess, not the
store's answer, not the rule's, recorded as refused with both sides named. The refusals are
put to the operator together at the end of the run. The next run applies their answers, and
the answer is written into the ontology under a stable conflict id, so **the same conflict is
never put to the operator twice**; a conflict whose sides have changed gets a different id
and is correctly asked again, because it is a different question. Three answers are
recognised, not two: the rule wins, the store wins, or keep refusing, since "keep refusing"
is a real decision and is not the same as never having answered. An unrecognised answer is
refused rather than stored. The override rate (answers where the rule won over the store's
memory) is tracked and served by `GET /ontology/conflicts`, carrying its own caveat in the
response body: **at single-operator volume it is not statistically meaningful** and must
never be read as a quality measure. **Built, not measured, and not yet wired into a run**: no phase of the pipeline calls this
module, so no run detects, refuses or applies a conflict today, and the store is empty
besides; the call site is one place in phase 8 beside the existing capture. Gate check 212
proves the whole cycle on fixtures.

**The GNN as a candidate finder** (ontology chain, job 4) is the second half of the relation
work, built beside the deterministic baseline and not instead of it.
`scripts/ontology_candidates.py` runs the persisted encoder over the graph and proposes which
provisions **may** relate, ranked by proximity in that encoder's space. It never asserts a
relation, writes no relation record, and returns one row per unordered pair, highest first,
with the pairs the baseline already found excluded on request so the two mechanisms are
compared by what each finds that the other does not. Decision 9's shape is unchanged: the
graph narrows, a model decides, the reasoning stays in text, and the score is shown rather
than hidden.

**What the ranking rests on, said here as plainly as in the code and the console: graph
structure alone.** Node type, degree, edges. With no Tier-2 signal the engine has learned
nothing, so `ranked_on`, `learned_relevance: false` and `tier2_signal: empty` travel in the
response beside every candidate and in the state summary, and no consumer can render a
candidate set without them. A candidate set ranked on structure is a real thing and a modest
one; it is never learned relevance. Gate check 213 proves the finder, both routes and the
console section on fixtures, and fails if the qualifier is ever replaced by a
learned-relevance claim, including a subtler one that mentions the phrase without denying it.
**Built, not measured**: no candidate set has been scored against anything, and the operator
scores the baseline and the finder on the long-range corpus after the move, choosing between
them then.

Its storage layer is `scripts/ontology_store.py` (night chain W7, the ontology foundations),
and four things are decided there. Scope: every record carries the scope it was written
under and a store opened under one scope returns nothing written under another, enforced on
every read and write inside the layer rather than by a filter a caller must remember; the
identifier has one value today (`DEFAULT_SCOPE`), bound in one place in the pipeline's
phase 8, because the operator's unit of isolation is the engagement and no engagement
concept exists yet (the mechanism is built, the concept is not). Provenance: each provision
record carries `{time, agent, run, type}`, the agent being the one whose Finding the
amendment rests on; `type` is `document` for everything captured today, and the rule-derived
type is declared unfilled (`PROVENANCE_TYPE_RULE`) and refused by `provenance()` until that
path has been run and its record shape observed, since no run has ever exercised it; there
is no confidence field, by decision. Dual track: `provisions.jsonl` is the live store and
`provisions_log.jsonl` the immutable log (only ever appended to); a re-captured id supersedes
its earlier revision, `ProvisionStore.current()` returns only the highest revision per id so
a superseded entry is excluded at the query layer, every supersession is logged, and
`compact()` moves superseded revisions from the live store into the log. Supersede is built;
delete is declared and refuses, because the user-facing deletion case is an operator decision
not yet finalised. `tools/archive_ontology_stores.py` archives the stores as one dated zip
outside the repository (verified by digest before anything is emptied) and empties them.
Gate checks 200 to 202 prove the three mechanisms; the earlier ontology checks (57 to 64, 72
to 74, 143) still hold on the new layer, and the two whose fixtures seed provision records
(59 and 60) now write them through the store, since a bare line with no scope is invisible by
design.

The `[ontology_gnn]` line each run prints to stdout (`scripts/ontology_gnn.py`) now says
this plainly too, not only in this README: it used to lead with `loss=`, `weight_delta=`
and `device=`, the exact vocabulary of a real training run, with the honest caveat sitting
after them as a parenthetical a reader's eye skips past the numbers to reach. It now leads
with the words, not the numbers: a self-supervised reconstruction fit with no Tier-2 signal
yet, explicitly not a trained relevance model. The computation this logs is unchanged, same
values, same `summary` dict returned to its caller; only what the words say about what those
values mean was fixed.

**A correction, recorded because it was stated the other way for weeks.** The GNN does
**not** reset its weights every run. `gnn_update` loads any prior state, restores the
persisted encoder and decoder weights when the feature dimensions match, keeps a high-water
mark of the node ids it has already trained on, backpropagates only over nodes new since
that mark, and persists the updated mark; the feature width is constant across runs by
construction (deterministic feature hashing into fixed buckets), which is exactly what makes
a persisted weight matrix stay valid. Weights accumulate. What is absent is the **Tier-2
signal** (recurrence of proposals and findings across runs, verification verdicts,
precedent), which stays empty until runs populate it. So the engine learns nothing because
there is nothing yet to learn from, not because it forgets. The distinction matters for what
can be built on it: persistence is not the missing piece, a signal is.

To install dependencies without the launcher (for example, in a CI environment that manages
its own venv):

```
py -3.9 -m pip install -r requirements.txt
```

Declared dependencies: anthropic, openai, transformers, pypdf, python-docx, lxml,
beautifulsoup4, fpdf2, sentence-transformers, numpy, langdetect, ddgs, torch, bitsandbytes,
accelerate, fastapi, uvicorn[standard], python-multipart. bitsandbytes and accelerate are
needed only by the local profile's 4-bit checkpoints; accelerate was present on the
development machine only transitively and was pinned after a fresh install (the container)
could not load a single local model without it. `preflight.py` installs the two small
optional libraries (beautifulsoup4, langdetect) if missing, and pip-installs any other missing
Qwen-backend library except torch (`_attempt_lib_pull`), whose correct wheel is platform and
CUDA specific.

### Running in a container

A container path was built on 10 and 11 September 2026 and, like everything else from those
two days, has had its gate run but no review scored. The image (`Dockerfile`) is
`nvidia/cuda:12.1.1-base-ubuntu22.04` with Python 3.9 from deadsnakes, torch 2.5.1 from the
cu121 index, then `requirements.txt`. It copies framework source: `scripts/`, `config/`,
`tools/`, `corpus_ingest/`, the three root markdown files and `requirements.txt`,
plus the three declared synthetic files in `benchmark/fixtures/` needed by the
condition, severity and external-rule checks. No operational input, benchmark
corpora or answer keys, durable state, output, or Git history is copied. `.dockerignore` excludes `.git`,
`input/`, `durable/`, `output/` and `benchmark/keys/`; the corpora under `benchmark/` stay
out of the image because the `COPY` list names only the three fixtures. It sets
`PYTHONPATH=/app/scripts:/app` and
`HF_HOME=/root/.cache/huggingface`, so a mounted host cache and baked weights land at the
same path.

Two build modes behind one build argument:

```
docker build -t shimmer:local .                              # unbaked: small, expects a mounted model cache
docker build --build-arg BAKE_WEIGHTS=true -t shimmer:baked . # baked: the three checkpoints downloaded into the image
```

The baked build also prepares bge-m3 as `model.safetensors`. A cached `.bin` file
alone cannot load with the pinned torch 2.5.1 runtime. Conversion uses a temporary
torch 2.6.0 CPU installation with its restricted `weights_only=True` reader; that
build dependency is removed in the same layer. Runtime model ids and package pins
stay the same. `scripts/model_weights.py --model <cached-model-id>` can prepare a
local cache under torch >= 2.6; an older runtime refuses to convert pickle weights.
Already prepared weights need no conversion and load with torch 2.5.1.

Check the baked image itself, with no mounts:

```
docker run --rm --network none --gpus all --entrypoint python shimmer:baked tools/container_offline_probe.py
```

The probe executes redaction intent, shape authorisation and rule compilation,
checks all five votes with scores and references, and fails on attempted network
access as well as failed decisions. It makes no generation or provider call.

For builders whose cache cannot retain all weight layers, keep a local cache
outside the build context (this repository excludes `output/`):

```
docker buildx build --build-arg BAKE_WEIGHTS=true --cache-to type=local,dest=output/shimmer_build_cache,mode=max -t shimmer:baked .
docker buildx build --build-arg BAKE_WEIGHTS=true --cache-from type=local,src=output/shimmer_build_cache --cache-to type=local,dest=output/shimmer_build_cache,mode=max -t shimmer:baked .
```

The measured local cache occupies 14.41 GB. A subsequent source rebuild reused all
three weight downloads and the conversion layer, with no weight download repeated.
The producer cache record had disappeared while its image layer remained; the
builder reports a 20 GiB garbage-collection policy. Automatic collection explains
that possibility, but the historical eviction event was not recovered. The local
cache is the verified remedy and needs no global Docker configuration change.
It is local build state, never source to commit, and retained blobs can grow across
builds. No registry upload is involved.

`compose.yaml` names `image: shimmer:local` and declares no `build:` key, so it runs the
image the first line builds and builds nothing itself.

The weight layers sit **before** the source layers in the Dockerfile (reordered 11
September): a layer's cache key is its parent chain, so with the weights last every edit
under `scripts/` threw the three downloaded checkpoints away and pulled them again. With the
weights first, a source-only rebuild of the baked image reuses them. Each download is retried
up to five times with a growing pause, because the Docker Desktop proxy on the development
machine has dropped TLS mid-download.

The entry point (`tools/entrypoint.sh`) takes one command and passes everything after it
through unchanged: `serve` (the HTTP server), `run` (a review, through
`tools/run_local_demo.py`, so the pipeline module's filename is never named), and `verify`
(the gate, `verify_session1.py --offline`), `verify` by default; anything else is rejected
with a message naming the three. The offline gate, with the network blocked at the socket
and the host cache mounted:

```
docker run --rm --network none --gpus all -e SHIMMER_TOKEN_HASH=<sha256> \
    -v <host-hf-cache>:/root/.cache/huggingface shimmer:local verify
```

`compose.yaml` records the run flags once, as two profiled services so `docker compose up`
with no profile starts nothing by accident: `--profile serve` (port 8000) and
`--profile run run review` (one review, `run --non-interactive`). Both require
`SHIMMER_TOKEN_HASH` and `HOST_HF_CACHE` set in the shell, never in the file, and mount
`./config` (writable: an operator-approved model swap rewrites the registry), `./durable`,
`./ontology/stores`, `./output/runs`, `./input` and the host model cache.

What the first container start found, 11 September, all held closed since: the entry point
had checked out with CRLF line endings on Windows, so the kernel looked for an interpreter
named `/bin/sh\r` and the container failed with "no such file or directory"
(`.gitattributes` now pins `*.sh` and the entry point to LF and the Dockerfile strips a
trailing CR before setting the executable bit); no local model could load because
`accelerate` was never in `requirements.txt` (pinned); and gate check 197 read a benchmark
corpus file the image does not ship (its corpus assertions now run where the file exists and
are named absent otherwise, and its proof runs on a synthetic heading every tree has).

**Measured inside the unbaked image rebuilt at commit `139083a`**, network blocked
(`--network none`) and the host model cache mounted: `PASS=215 WARN=0 SKIP=7 FAIL/ERROR=6
TOTAL=228` in about 390 s.

Six failures, and all six are the environment rather than the code, unchanged across
rebuilds. Four are the source-only ones section L lists (01, 28, 31, 145). The other two are
the machine: **139** needs a CUDA branch and the container has no GPU, and **193** loads a
cached local model with the network blocked, which the mounted host cache does not satisfy
inside the container. Those observations describe that image and invocation.
ZERO-C retested both with `--gpus all` on 12 September: checks **139 and 193 PASS**.
The local loader resolves a cached snapshot directory before calling Transformers.
Version 4.52.3 probes custom generation code by repository id despite the
local-files-only flag; a local directory keeps that lookup local too. Cached
custom generation overrides are refused so resolving a directory grants no new
code-execution permission. The configured checkpoints use standard generation. Check 193
counts attempted access, including errors the library catches, and its real
neutralisation removes snapshot resolution. The cached Phi checkpoint loads with
network access blocked, and the current Docker
runtime exposes one CUDA device. The six-step ensemble probe also PASSes with no
mounts and no attempted network access. This proves local loading and semantic
decisions, not a completed review; no pipeline run was performed.

The completed ZERO-C host gate is **243 PASS, 0 WARN, 0 SKIP, 2 FAIL, 245 total**.
The image gate is **233 PASS, 0 WARN, 8 SKIP, 4 FAIL, 245 total**, with network
disabled, GPU enabled and no mounts. The six-step ensemble probe passes.

The ZERO-C image carries all three synthetic fixtures used by checks 236, 238 and
239. Check 239 runs its severity, suspension, conflict-summary and restraint proofs
there; its result explicitly says the corpus regression assertions were not run. A
nonempty corpus set must still provide the regression set; an empty directory
left by another gate check does not constitute a corpus. The deliberately
absent runtime directories account for checks 01, 28 and 31, and the absent ignored
contamination fixture accounts for 145. These source-only limits remain visible.

Seven skips: the two network checks `--offline` always skips, plus five that need files the
image does not ship. The image copies `scripts/`, `config/`, `tools/` and `corpus_ingest/`
only, so the launchers and `benchmark/corpora/` are absent **by design**. Checks 215, 217,
222, 224 and 227 name the absent file and why rather than failing, which is the difference
between a deliberate shipping decision and a broken check. Checks 220 and 225 pass with the
half they cannot verify there narrowed, and each says so in its own result line rather than
claiming a proof it did not run.

The host offline gate at that same commit is `PASS=224 WARN=0 SKIP=2 FAIL/ERROR=2 TOTAL=228`,
and the full host gate is `PASS=226 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=228`.

The figures further down are from an earlier image built at commit `9e3302f`, kept as the
record of that build.

Measured inside the rebuilt unbaked image, network blocked, host cache mounted, against the
210-check gate as it stood that afternoon: `PASS=204 WARN=0 SKIP=2 FAIL/ERROR=4 TOTAL=210`
in 873 s. The four failures are the source-only ones section L lists (01, 28, 31, 145); the
two skips are the network checks (15, 38) that `--offline` skips. Check 193 loaded a cached
model with the network genuinely blocked.

Measured inside the **baked image as rebuilt at commit `9e3302f`** (the "current tree" when
this was written, not the current HEAD), network blocked and
**nothing mounted**: `PASS=209 WARN=0 SKIP=2 FAIL/ERROR=4 TOTAL=215` in about 370 s, the
three checkpoints resolving from the image's own layers
(`docs/fix/STEP_BAKED_REBUILD_2_REPORT.md`). The failure and skip sets are identical to every
earlier run; the extra passes are the checks added since, the ontology chain and the console
audit. A source-only rebuild reuses **two of the three** weight layers and re-downloads the
third (about 165 s), which is less than the layer reorder was expected to save. That has now
happened on two consecutive rebuilds with near-identical timing, so it is systematic; three
explanations were ruled out (the three RUN blocks are structurally identical, a cache entry
for the third layer does exist with the same properties as the other two, and no prune
happened between builds) and the cause is recorded as unestablished rather than guessed. **What is not proven:** no review has been run inside
either container, so "the review runs offline in the container" is not claimed, only "the
gate does, and the weights are there".

---

## H. Running Shimmer (four entry points)

### 1. The launcher (recommended starting point)

`shimmer.bat` (Windows) or `shimmer.sh` (macOS/Linux) takes you from a fresh clone to a
running review: it finds Python, builds and activates a local `.venv`, installs
dependencies, asks which backend you will run on, runs the readiness preflight for that
backend, then shows a menu.

The backend question comes first because it decides what readiness means: a local run calls
no provider, so cloud keys are irrelevant to it. The answer is exported as
`SHIMMER_BACKEND_PROFILE`, which the intake wizard reads so it does not ask the same
question again, and the wizard emits `--backend-profile` into the run flags. That flag was
missing entirely before, so every launcher and chat review took the pipeline's default,
which also silently chose the review mode (`resolve_review_mode` selects paired under local
and wide under cloud). Because the wizard owns the flag, the launcher and the chat interface
both get it from one place.

```
[1] Run a review (CLI)      -> asks Review or Draft. Review runs the intake wizard, then the
                               pipeline; Draft asks for the question, then asks the same
                               backend and sensitivity questions the review path asks
                               (intake_wizard.py --mode-only), then runs --task draft
[2] Open the chat interface -> scripts/chat.py
[3] Start the server        -> scripts/server.py, after generating an access token if
                               SHIMMER_TOKEN_HASH is not already set
[4] Run the verify gate     -> scripts/verify_session1.py
[5] Import documents         -> the intake wizard only: place files, set the cutoff, and write
                               the tier-1 review-targets manifest (no run)
[Q] Quit
```

**The draft path asks about sensitivity rather than deciding it.** It used to hardcode
`--sensitivity-layer-inactive-override` and `--no-redaction-override`, so every launcher
draft was declared non-sensitive without a prompt, while the review path asked. A draft memo
is generated from the same grounding corpus a review reads, so it is the same decision and it
is yours. Both paths now ask through the same wizard function, so they cannot drift apart:
choose Normal and both overrides are passed because you chose them; choose Sensitive and
`--no-redaction-override` is omitted, so redaction stays on. Declining the plan runs nothing.
An empty answer at the confirm declines, because a closed stdin must not read as consent to a
run whose sensitivity was never confirmed.

**Option [3] completes the token handshake itself.** If `SHIMMER_TOKEN_HASH` is not set it
offers to generate an access token, prints the token **once** (it is the only copy, and the
server stores only its hash), keeps the hash in its own environment, and starts the server in
the same step. It used to print the hash and send you away to set it by hand before returning
to the menu, which the launcher can do for itself since it is the process that starts the
server. Send the token as `Authorization: Bearer <token>`.

It then prints the URLs that actually serve something: `/console` for the operator console
and `/health`, the one route that needs no token, both on `SHIMMER_PORT` (default 8000).
There is **no page at `/`**: the app registers no bare root handler, so the old
`http://localhost:8000` the launcher printed was a 404 on arrival.

The intake wizard scans a folder, classifies each file (conventions, config, sidecar, or
document; anything else is skipped), prints and optionally edits the date cutoff, lets you
choose normal or sensitive mode, asks the parallelism and document-count limits, then places
the files and finally asks which documents are under review and which file, if any, is an
earlier version of one of them.

A convention file is recognised by what is IN it, not by what it is called. The wizard asks
`convention_parser` itself whether a file carries headings with your own rule ids (the same
test the parser uses to tell a real rule heading from preamble prose), so
`cataloguing_conventions.md`, `lab_conventions.md` or any other name you choose is filed as
review rules. The two legacy names (`review_conventions.md`, `review_mandate.md`) still work
on the name alone. This used to be a two-name match while the parser read every file in
`input/conventions/` regardless of name, so intake was strict exactly where the parser was
permissive: none of the shipped corpora used either name, and every one of their rule sheets
was filed as a document to be reviewed as prose, its rules never compiled.

The review plan then reports what the parser extracted from those files: the rule count per
file, the subject tags, and how many rules carry a `[scope: ...]` or `[requires: ...]`
declaration. Intake had no surface for any of it, so a mistyped tag or a heading the parser
did not read as a rule was invisible until the run produced nothing. A file that yields no
rules at all says so, and names the heading shape it was looking for.

The wizard also declares the ingestion mode it is importing under. A `_corpus_ingest.json`
sidecar means an externally fed corpus, so the wizard passes `--mode integrated` and the
files the sidecar marks `context_grounding` stay grounding instead of being promoted to the
documents under review; with no sidecar the run is standalone, the pipeline's own default.
The wizard emitted neither before, so an ingested corpus ran as standalone and the promotion
exclusion never fired. The wizard never WRITES a sidecar: for your own files there is no
role, date or source verification to record, and inventing them would be fabricating
provenance.

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
py -3.9 scripts/pipeline.py --non-interactive --sensitivity-layer-inactive-override --no-redaction-override
```

The two overrides are not optional on a hand-typed command. The first is required on every
run until the operator activates the LAW-IV layer (section F; exit 6 otherwise); the second
is required whenever no operator redaction rule compiles, which is the case for every shipped
corpus. The launcher, the intake wizard and the server add both for a normal run. The same
applies to `tools/run_local_demo.py` below, which passes its arguments through unchanged.

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
py -3.9 -X utf8 tools/run_local_demo.py --non-interactive --sensitivity-layer-inactive-override --no-redaction-override [pipeline args...]
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
subfolder as `memo.md`. `audit/` holds the editorial and contract-violation artifacts,
`convention_assignment.json` (the subject comparison computed once at BOOT: per rule its
tags, the agents matched, the consumers with a live rule path, the status, and the
operator's own rule id beside the registry id; per agent the rules it matched), and
`pairing_map.json` (which rules could apply to which units and why; the `band_conditions`
record described in section B; per unit the `prior_comparisons` block: earlier figures
found, every check made, every refusal; and per document `not_judged` and `reattributed`,
the plans no convention-review agent judged and the computed plans moved to a rule that has
one, plus `absence`, which path, Python or the model, decided each declared absence).
`logs/` holds the append-only `agent_bus.jsonl`, the cost tracker, the run summary, and
`call_evidence.jsonl`: one record per model call, written by the agent wrapper just before
dispatch, carrying only structural identifiers and counts, never text: the call id, run,
timestamp, phase, per-document position, agent, backend, model and task; the payload's own
document id and the reviewed unit id; the neighbouring unit ids supplied as context; the
heading unit; the document map's unit ids; the reference ids supplied and the subset the
renderer actually kept whole; the rule ids requested and the subset whose line the registry
section kept whole; the rule the payload itself carried; whether the registry and reference
sections were clipped; how many recent bus messages were rendered and how many dropped for
budget; the payload's field names; the length of a whole-document payload and whether the
token clip cut it; and the prompt length. Never a passage of text, so the file is not a
second copy of the document. The rendered subsets are read off the finished section texts
by `bus_reader.rendered_line_ids`, never assumed from the input lists, and a rule that was
requested but not rendered never counts as having reached the call. The same call id sits
on the call's cost row and on the bus post it produced, so the three join; gate check 204
reconstructs one executed call from the file alone and check 207 proves the rendered
report. The draft memo's own model call (which bypasses the wrapper's task path) writes the
same record to the run's `call_evidence.jsonl`; the arithmetic probe, which runs outside any
run folder, carries the same identifiers (call id, task, prompt length) in its own `--out`
records instead, with the call id on its cost row when a cost directory is given. Runs never
overwrite each other. Follow a run live with `py -3.9 scripts/bus_viewer.py --follow`.

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
the unit text to disk; results carry the model's output, its length, its hash and a parse
trace (counts only). A harness call does go through the pipeline's `run_task`, so the run
folder the harness creates under `output/runs/` receives the same per-call evidence record
as a pipeline run (identifiers and counts, never text) and a cost row carrying the same call
id.

Two companions: `probe_arithmetic.py` asks whether the model can do the arithmetic at all
with no review framing (no agent identity, no constitution, no conventions, no document, no
output contract; figures generated from a seeded random source, never read from the
operator's corpus), and `score_envelope.py` scores a batch of `run_agent.py` results for
envelope compliance, verdict accuracy and latency. An empty but valid envelope counts as
compliant, because that is what the contract says.

### 4a. The nine-part agent harness (`config/agent_harness.json`)

A different sense of "harness" from section 4 above: not a tool for running one agent call,
but the complete specification of what an agent IS, nine parts per agent (the agent itself;
the constitution it carries by default; the rule cluster assigned to it; testing against that
cluster; ontological knowledge drawn in as required; the format it receives work in; the
format it hands work back in; whether it fires at all; how far it re-fires). Built by
`scripts/build_agent_harness.py` from `config/agent_registry.json` and
`config/agent_contracts.json` directly, so it cannot drift from the source it describes; never
hand-edited. Four parts (constitution-by-default, receive-format, hand-format,
re-fire-condition-and-limit) are decided once, identically, for every agent and live in the
file's `shared_parts` block; the re-fire limit is 0, since no retry mechanism exists anywhere
between `pipeline.py` and `agent_wrapper.py`, a contract violation drops the item rather than
retrying it. Firing (part 8) is traced per agent group, six shapes: the production and audit
lists fire unconditionally; the two convention-review agents pass the W3 firing gate (an agent
fires if the convention assignment gave it a rule or any loaded rule is untagged, and in
paired mode each pair's judging agent is chosen by the rule's subject; an untagged rule keeps
PRACTICE_AUDITOR, and a rule with no convention-review consumer gets no judging agent at all,
its plan recorded in the pairing map as not judged); LEGAL_ANALYST fires once in phase 3 and, under the local profile, once more
per finding its first call produced (the D6 two-pass split); REDACTOR fires only while the
sensitivity layer is active; AMENDMENT_DRAFTER skips when a fresh payload already sits on the
bus; the editorial board fires by parsimony, each rank above EDITOR_CLERK summoned only on a
confidence-below-threshold or `out_of_mandate` escalation. Parts 3 and 4 (the rule cluster
assigned to an agent, and testing against it) are decided by the convention assignment
(`docs/api/CONVENTION_ASSIGNMENT_DESIGN.md`): an agent's cluster is the `subjects` it
declares in `config/agent_registry.json`, empty by the operator's decision for the six agents
no convention-review path reaches (each carries a `subjects_note` saying why), and per run the
rules matched to it are read from `audit/convention_assignment.json`; the cluster is proved by
gate checks 198 and 199. One part (ontology) stays undecided until the ontology work runs,
written into the file as `"decided": false` with a stated reason, never omitted: an omitted
part is indistinguishable from one nobody thought of, and gate check 195 fails if any of the
18 agents is missing a part, if a cluster in the file drifts from the registry it was built
from, or if the one unresolved part is silently marked decided.

### Benchmarking (`benchmark/keys/`, never committed)

`benchmark/keys/` holds the answer key, the control document, the ledger scripts and the
frozen scorer for measuring recall against a corpus with known planted defects. It is
**gitignored** and never committed, so it is absent from every clone of this repository, not
only this public snapshot; an operator who wants recall measurement writes their own answer
key and corpus under `benchmark/keys/` locally. Only the scorer reads the key. Nothing in
`scripts/`, `config/` or `tests/` may contain a planted benchmark figure: gate check 145
(the contamination probe) scans those directories plus the harness fixtures for the key's
figures and fails if one appears, which is what makes a recall number mean anything.
**This repository does not ship a `tests/` directory**, so check 145 fails here with
"tests/fixtures/planted_figure_hashes.json is missing: the contamination probe cannot run,
so contamination cannot be ruled out" (see section L) until an operator adds that fixture;
that failure says the probe has nothing to check, not that contamination was found.

---

### Test corpora from other domains (`benchmark/corpora/`)

A domain-agnostic system that has only ever been run on one corpus has not been tested for
domain agnosticism. `benchmark/corpora/` holds corpora from other domains, **four built from
real public data** and one (`device_log_review`, with its clean twin) authored synthetically
for the adjacent-neighbour measurement, each with `context/` (the reference material and the
document under review), `conventions/` (operator rules) and a committed `answer_key.json`
written before any run, which `tools/score_corpus.py` scores a run against. Unlike `benchmark/keys/`, these keys are in the
repository, because the figures they carry are not planted in the operator's own corpus. They sit
outside the vocabulary probe's scanned roots, so their vocabulary stays operator input. The
scorer reports recall per flaw `kind` when a key labels its planted entries with one (a corpus
may plant several kinds on purpose, to separate what a mechanism catches from what it does
not; a key without `kind` prints the overall figure alone), and it scores a run that ended
before synthesis from the bus findings alone, printing a NOTE that no deliverable exists and
that the amendment-based figures are therefore 0 and mean nothing, rather than refusing.

**A rule nothing could act on is not a failed rule** (check 218). The scorer reads the run's
own `audit/convention_assignment.json` and reports, apart from recall, how many planted entries
name a rule whose status is `unassigned` (it carries subject tags and none matched an agent) or
`assigned_no_consumer` (an agent declared its tag but consumes no rule in this mode). Both mean
the rule had no assigned consumer. Eligibility alone does not establish a call: `recall, asked`
requires the rule and unit to appear in a recorded call to an assigned consumer. Unit-specific
suspensions are reported separately and excluded from that denominator. An eligible entry with
no such call is `assigned_not_asked`; missing assignment or call evidence is `unknown`. Raw recall
retains every planted entry. Recorded exposure does not prove a successful response or reasoning.

**The relation breakdown is built from the run, not from a list.** Every relation the run's typed
findings actually carry is named and counted. This exists because `date_window`, the duration
comparison, was computed, posted and counted toward recall while every relation-aware section of
the scorer partitioned on the prior-version and band relations alone, so the newest mechanism was
invisible in the only view a reader sees. A relation appended to the Finding record now appears
the first run that produces one, with no edit here.

Computed amendments retain the finding's typed relation and figures, so a scorer can also
confirm a `date_window` reason from `deliverables/<document>/review_data.json` when the bus record
is unavailable. Older amendments without those fields remain reason-unverifiable. The relation
count above describes bus findings; amendment-only matches appear in the entry table and reason
score. EIGHT's declared fixture computes 48 hours against a 24-hour bound and confirms the reason
through each artifact path independently.

**One run keeps one identity across artifacts** (check 247). New CLI and server runs use
32 lowercase hexadecimal UUID characters from the same generator. Folder names are labels:
the CLI can rename a folder for readability without changing its run id. The identity is
persisted in `audit/run_identity.json` and reused by call evidence and completion records.
A fresh caller-pinned output folder also receives a generated identity. Reopening an older
run reads its recorded identity, including a unique id in saved call evidence, without
rewriting historical files. Conflicting call identities are refused. Older timestamped
server IDs remain valid in API paths; restart queue order follows submission time.

**Run completeness is saved for both launch paths** (check 246). The pipeline writes
`audit/run_completion.json` when work starts and when its entry point returns or raises. It
records the stable run id, UTC start/finish times, exit code, whether final work was reached,
and final document/amendment counts when available. `completed` requires both the explicit
end-of-work mark and exit code 0. An early return, including an operator stop returning 0,
is `stopped`; exceptions and catchable interruptions are `failed` or `interrupted`. If final work
was reached but the return was unsuccessful, the scorer says `FINISHED WITHOUT SUCCESS` and
shows the exit code, rather than claiming the work never finished. A hard kill
leaves `running`, which means started without a recorded finish and cannot establish completion.
The record follows a renamed run folder. Only exception types are saved, never exception text.

Both scorer routes read this evidence. Completed work with zero reported amendments is distinct
from incomplete work; a missing deliverable remains an absence of amendment evidence even when
completion was recorded. Older server runs retain their separate `status.json`, which describes
process state and is reported as such when pipeline completion is absent. Older command-line
runs without either record remain completion-unknown. Existing artifacts are not backfilled.

The scorer also classifies every planted entry the run failed to produce, per entry, into
exactly one of four classes, from the run's saved artifacts alone (`scripts/fn_evidence.py`;
the scorer is the only reader of a key and hands each missed entry to the classifier as a
dict): `EVIDENCE_PRESENT_IN_MODEL_PAYLOAD` (a recorded call in `logs/call_evidence.jsonl`
carried the rule's TEXT, in the payload itself or rendered whole in the registry section,
never merely requested, and showed the unit, as the reviewed unit, a supplied neighbour, or
inside an unclipped whole-document payload; possibly a reasoning failure),
`EVIDENCE_PRESENT_UPSTREAM_BUT_NOT_IN_PAYLOAD` (the unit is in the parsed document and the
rule was loaded, but no call carried both: the pairing map never paired them, or the run's
evidence file records no such call; a rule that was never paired is always this class,
never the first), `EVIDENCE_ABSENT_FROM_CORPUS` (the key names a unit the parsed document
does not contain, or a rule the run never loaded: a gold-key problem), and `UNKNOWN`
(whatever the artifacts cannot prove: no pairing map, a rule id no saved artifact maps to a
registry id, or a planned pair on a run that predates the recording). Nothing is inferred;
every classification prints the artifact it rests on. The mapping from the operator's own
rule id to the registry id is saved per run at BOOT in `audit/convention_assignment.json`
(`source_rule_id` beside every registry id), so a run older than that column classifies
its misses `UNKNOWN` rather than guessing. Gate check 205 proves the four classes on
fixtures; a rule the model was never asked and a rule it failed to answer no longer land in
one recall number.

| corpus | source | what it tests |
|---|---|---|
| `clinical_reference` | the published [reference ranges for blood tests](https://en.wikipedia.org/wiki/Reference_ranges_for_blood_tests) | the band path on unfamiliar vocabulary, en-dash ranges, and a unit written in its own column rather than the header |
| `catalogue_records` | the [Dublin Core Metadata Element Set](https://www.dublincore.org/specifications/dublin-core/dces/) | a document with **no quantities anywhere**, so arithmetic can settle nothing and every rule is about presence, vocabulary or agreement between fields |
| `negotiation_r3_to_r4` | company offers of 19 and 31 October 2024 in a real 2024 labor negotiation, real publicly reported figures with the company and the union replaced by obvious placeholders (Company A, Union B) before publication | the **round-N comparison**: the 19 October offer declared as the earlier version of the 31 October offer, a mandate with bands, currency figures written `$7,000`, a label that disappears between rounds and so exercises the absent path (since the source verification of 2026-09-08 the corpus's own answer key records that `absent_since_prior` record as FALSE about the negotiation: the $12,000 bonus combines the earlier $7,000 bonus and the $5,000 401(k) lump sum, so nothing was withdrawn), and the review question |
| `negotiation_r2_to_r3` | the offers of 23 September (press-reported) and 19 October 2024 in the same negotiation | the same mechanism one round earlier: nothing was dropped between these two offers, so no `absent_since_prior` record should appear. Terms that first appear in the later offer produce neither a record nor a refusal, which the key now records as a defect rather than a property: a term that ARRIVES between rounds is structurally invisible, and the per-year schedule of the 23 September offer was reported on the day and was omitted from the corpus |
| `device_log_review` (with its clean twin `device_log_review_clean`) | synthetic, authored for this corpus, not real public data (see the limitation below) | the adjacent-neighbor mechanism (`docs/api/UNIT_CONTEXT_DESIGN.md`) and its real limit, directly: 6 neighbor-dependent flaws (3 that read wrong alone but are sound once the entry immediately before is read, 3 that read sound alone but are contradicted by the entry immediately after), 3 long-range flaws (a term defined in the document's own opening glossary conflicts with its use 16 to 18 units later, farther than adjacent context reaches), and 3 self-contained flaws (visible in one unit alone, a control on the other two). The clean twin repeats the same document with every flaw repaired, to measure false positives on a genuinely clean input separately from recall on the flawed one |

**`device_log_review`'s limitation, stated plainly, not left implicit**: unlike the four corpora above, this one is not real public data. It was authored, along with its own answer key, by the same process that built the pipeline fixes being measured against it. A score against a self-authored key is weaker evidence than a score against a corpus and key written independently, since the author of a test cannot be fully blind to what the test is designed to catch. It exists because, before it, this benchmark set had no corpus measuring the adjacent-neighbor mechanism or the long-range gap at all, and a self-authored measurement is worth more than no measurement, held to that lower standard explicitly rather than presented as independent verification. Its own answer key restates this same limitation for a reader who reaches the key without reading here first. **On 2026-09-12 that weakness showed itself concretely, and the record of it is kept here rather than resolved quietly.** CONV-D02 requires a calibration authority signature on every Class-A entry. UNIT-TEASEL is a Class-A entry stating a reading and carrying no signature, and the key listed it as clean, so a measurement run flagged it and the key scored that correct finding as a false positive. The rule, the entry that violates it, and the key that called it clean were all written by one party, and no reviewer independent of the author ever read the rule against every entry. The contradiction was found by the measurement, not by review. **It was resolved in favour of the rule: the KEY was corrected, not CONV-D02.** TEASEL is now a planted CONV-D02 flaw in the flawed twin and carries the signature in the clean twin, the way PINE does. Weakening the rule to match the key would have marked a correct finding as a false positive and moved the measurement in the direction that flatters the pipeline. Separately, CONV-D02 now declares the scope field "reading", so UNIT-CEDAR, a definitional note stating no reading, leaves the rule scope by the operator own declaration rather than by an inference written into code. Gate check 227 pins the corpus against its own rule so the contradiction cannot reappear unnoticed.

The two negotiation corpora carry their manifest (`_review_targets.json` with `prior`) inside
`context/`, so staging one declares the earlier version as well. The device corpus carries
none: its document's role then falls to the date cutoff, and since its file name carries no
year the date is resolved by a lookup a measurement should not depend on; write a tier-1
manifest naming `device_log_flawed.md` (or the clean twin) as the target before running it.

Stage one with `tools/stage_corpus.py`, which moves the current `input/` contents into a
timestamped holding directory first and restores them afterwards, and carries no domain
vocabulary of its own:

```
py -3.9 -X utf8 tools/stage_corpus.py --list
py -3.9 -X utf8 tools/stage_corpus.py --corpus clinical_reference
py -3.9 -X utf8 tools/stage_corpus.py --restore output/staged_inputs/<holding-dir>
```

A staged corpus needs two overrides to start: `--sensitivity-layer-inactive-override` (the
LAW-IV layer ships inactive and the run refuses to start without it, section F) and, because
no shipped corpus declares a confidentiality rule, `--no-redaction-override` to declare the
run redact-nothing; both are logged to the governance ledger.

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
fix had not reached. All eleven found by the first four corpora are fixed; nine have a gate
check, and the two Unicode label defects found in the parallel design review do not. That is
the argument for a second corpus, and a third.

**What the fifth corpus found** (`device_log_review`, 11 September 2026) in two runs that
were stopped before any deliverable: the convention parser minted the conventions file's own two
preamble paragraphs as rules, and they drew 25 of the model's 71 findings (fixed, check
197); a shorter label inside a longer named label was required of every unit, rejecting the
two signature rules on 14 of 19 units (fixed, check 208); a rule about a missing field could
never pair with the unit missing it, so the four rules that check the planted flaw kinds
paired with no unit at all (addressed by declared scope, check 209); rules assigned to the
editorial board alone were still judged by PRACTICE_AUDITOR as a fallback, and every rule was
shown to both convention-review agents in wide mode (fixed, check 206); and a rule the
registry section had clipped was recorded as shown (fixed, check 207). In the same runs, 57
of 101 pairs were made by the similarity fallback because the rules named no field the
entries carry, and the reference states its bands in prose, which `reference_tables.py` did
not read at the time (addressed, check 215: a labelled prose band, a class or label, a colon,
a range and a unit in one sentence, is read the same way a table cell is, with the same
refusal on two unrelated figures in one sentence). On `device_log_review` itself the band did
not mint end to end at first: the corpus's own three class labels, "Class-A sensor" /
"Class-B sensor" / "Class-C sensor", reduced to the identical word set under the label
tokenizer, which split the hyphen and then dropped the single letter by its `len(w) > 2`
filter, so `match_row` correctly refused the row as a tie rather than guessing which class a
reading belongs to. That was a limit of the SHARED tokenizer, reproduced identically by a real
markdown table carrying the same three labels, not something check 215 introduced. It is now
fixed at that shared layer ("Normalisation" below): the hyphen joins, the three classes are
distinguishable, and check 215 pins the band minting from the corpus's own prose, with a
Class-B unit taking the 20-to-60 row and a Class-C unit the 70-to-110 row.

**ROWAN now produces a computed finding, but still requests an explanation.** A current-tree
replay of the real source, convention and reference computes `above_band`: 61 units against the
Class-B upper bound of 60. Removing the reference reader's contribution changes that plan to
`uncomputable`. The real paired-review consumer, isolated to this one field-based pair with its
actual neighbours retained, makes one explanatory call and posts Python's typed finding even
when the mocked reply is empty or failed. No model was called in this measurement. The old
model miss no longer controls whether the arithmetic finding exists; this is not a claim of
zero-call review or a new end-to-end run. The explanatory policy remains unchanged.

Those historical runs also carried model items without unit ids and rejected some replies.
The current paired path mints computed findings with unit ids and stamps judged absence
findings. FIVE verified recovery of valid envelopes in prose and fences; the three saved
violations were incomplete or absent JSON. The historical false-negative classifier put all
nine misses of the second run in `UNKNOWN` because that run predates its saved rule-id mapping.
Fixture and saved-artifact measurements above do not replace a new end-to-end quality run.

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
# -> 202 {"run_id":"73b4674496704dad9617241b7884a6cc", "status":"queued",
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
such run". Three fields a finding can carry on the bus are not in this projection yet:
`absence_path` (`computed` when Python decided a declared absence with no call, `judged` when
a model answered the narrow question), `stamped_by: python` on a judged one, and
`conditional_on` on a qualified low-side band finding; read `logs/agent_bus.jsonl` for those
until the route carries them.

**Step 4, if you need to justify a finding, ask why those rules were applied.**

```
curl -s "$BASE/runs/<run_id>/pairs" -H "Authorization: Bearer $TOKEN"
```

Returns the pairing map: per document the counts, and per unit the rules paired and rejected,
each with the reason recorded before any verdict fired, plus the rule ids left undecided (ids
only, no reason), and per document the plans no convention-review agent judged
(`not_judged`) and the computed plans moved to a rule that has one (`reattributed`). Carries
no document text. The declared-absence record (`absence`, which path decided each) is on
disk in `audit/pairing_map.json` and not yet served here. This is the audit trail for "why
was this rule checked against this section, and why was that one not".

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
a `run_id` accepts the shared UUID format or a legacy timestamped server ID and answers
404 for any other syntax before constructing a path. An unknown valid ID also returns 404.

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
| `SHIMMER_AGENT_REGISTRY` | `config/agent_registry.json` | custom path to the agent registry `GET /runs/{run_id}/convention-assignment` reads for each agent's declared `subjects`, to compute `idle_agents`; same override reasoning as `SHIMMER_CONVENTION_REGISTRY` |
| `SHIMMER_AGENT_HARNESS` | `config/agent_harness.json` | custom path to the nine-part agent harness `GET /harness` serves to the console's Agents page (generated by `scripts/build_agent_harness.py`); same override reasoning as `SHIMMER_AGENT_REGISTRY` |
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
| `GET` | `/runs/{run_id}/pairs` | token | The run's **pairing map**: counts, and per unit the rules paired / rejected with the reason for each plus the undecided rule ids (ids only, no reason), and per unit `prior_hit_count`, `prior_check_count` and `prior_refused_count` (integers only). No document text. Each paired/rejected entry now also carries `source_rule_id` (the operator's own id for that rule, `finding_record.source_rule_id_for`, the same lookup a Finding record already uses), so a rule reads the same identifier here as it does in `/findings`, never the registry's bare number alone. Also (convention distribution step A) `not_judged` and `not_judged_count`, the plans phase 5.5 made no call for because their rule has no convention-review consumer (unit, rule and operator id, kind, the consumers it was assigned to, status; in wide mode one entry per such rule with no unit), and `reattributed`, the rule-independent computed plans moved to a paired rule that has a judging agent. The declared-absence record the map carries on disk (`absence`, `absence_computed_count`, `absence_judged_count`: which declared absences Python decided and which went to the model, with the judged call ids) is not yet served by this route, nor is `band_conditions`; read `audit/pairing_map.json` directly for them. |
| `GET` | `/runs/{run_id}/amendments` | token | console fresh-eyes addition: the run's proposed corrections, read from every DONE document's own `deliverables/<doc_id>/review_data.json` (BP-16), the same master file the archive's `review_findings.md`/`tracked_changes.docx` are pure renders of. Per amendment: `original_text` (the document's actual passage, since the source fix in `paired_review.py`'s `amendment_from_finding`; a run produced before that fix still carries the old shape, the bare unit id, on disk, flagged by `original_text_is_passage: false` rather than presented as the real passage), `proposed_text` (`null` unless a model or `--amendment-polish` supplied one), `source_rule_id` (the operator's own id, falling back to `convention_ref` only when absent, the same rule every rule id on this surface follows), `comment` (the reasoning, required by both the computed and model-drafted contracts), `unit_id_repaired_to` (`null` unless the boundary repair below fired), plus `finding_unit_id`/`finding_rule_id` to join back to the Finding it corrects. `200` with an empty list, not an error, when no document has finished yet or none produced an irregular finding. A real cloud run against a benchmark corpus found a second, real gap in the source fix itself: `unit_texts` is keyed by the pipeline's own `split_units` id (`u02-record-cat-birch`), but a WIDE-mode agent (`PRACTICE_AUDITOR`) was writing a Finding's `unit_id` as the document's own identifier for the record it described (`CAT-BIRCH`), never told which id space to use, so the lookup silently missed for every wide-mode finding. Closed at three layers: `pipeline.py`'s convention-review payload now carries `document_units` (the real id/title list) to both convention-review agents, `config/agent_contracts.json`'s `finding_record.says.unit_id` now tells them to copy from it verbatim, and `amendment_from_finding` still tries one narrow, structural second chance (`_repair_unit_id`) for whatever a model gets wrong anyway: the miss-shaped id found written inside exactly one unit's own text, case-insensitively. A single unambiguous match is used and recorded as `unit_id_repaired_to`; zero or multiple matches refuse, same honest fallback as before, never guessed. |
| `GET` | `/runs/{run_id}/amendment-refusals` | token | A real, irregular finding the pipeline could not turn into an amendment, named plainly rather than left to vanish. Found live: PRACTICE_AUDITOR wrote genuinely irregular findings (real `relation`, real `record_verdict: irregular`, a real explanation) whose rule id landed under a field name `amendment_from_finding` did not yet recognise, since `config/agent_contracts.json` used to declare a different rule-id field name per agent (`procedure_id`, `conv_id`, `rule_id`, `convention_ref`, four names for one concept); before this route and its underlying fix, every one of those findings was silently dropped, with nothing on the bus, in a deliverable, or here, saying it had ever existed. Fixed at the source (`finding_record.resolved_rule_id`, one shared resolver checking all four names). First wired into `amendment_from_finding` and its dedup key; a later pass (night chain W5) found and closed three more call sites reading a rule id under only one or two of the four names (`pipeline.py`'s `_category_for_conv` caller and `_stamp_source_rule_ids`, `finding_record.index_findings`, `server.py`'s `_project_finding`), plus a `KeyError` in `apply_typed_fields` that `index_findings`' own fix exposed (it matched a finding by any of the four names, then still read the amendment's copied `convention_ref` back off a bare `rule_id` key). All now resolve through the same one function, gate check 196. This route exists for whatever a future finding still cannot be built from: `paired_review.ensure_amendments_for_findings` takes an optional `refusal_sink`, and `pipeline.py` posts whatever lands in it as a distinct bus event (`AMENDMENT_REFUSED`), never Finding-shaped, so it is correctly invisible to `/findings` (a refusal is not a finding) while still reachable here. Per refusal: `doc_id`, `unit_id`, `rule_id` (the resolved value, if any), `reason`, and the source finding's own `relation`/`explanation`. `200` with an empty list, not an error, when nothing was refused, the common case. Rendered in the console as its own section, disappearing when empty, same discipline as every other content-dependent section on this surface. |
| `GET` | `/runs/{run_id}/contract-violations` | token | A call whose output did not match its agent's own contract at all, so nothing usable was produced, not even a thin finding. Found live: after `finding_record`'s fields were made required for PRACTICE_AUDITOR (`relation`, `record_verdict`, `explanation`, closing a different gap where most of its real output asserted a violation with no supporting content: a reviewer learns nothing from "CONV-005 was violated" alone), the honest next question is what a stricter contract costs, since some calls that used to pass a looser bar now genuinely fail it. This route, together with `/runs/{run_id}/amendment-refusals`, closes the last visibility gap: a call now produces exactly one of three outcomes a reader can see somewhere, a real amendment, a refused finding, or a failed contract, never silently absent from all three. Per violation: `agent`, `backend`, `model`, `missing_fields` (what the contract required and the reply lacked) and `timestamp`; no `doc_id`, since a call can fail before its output is attributed to a document. Returned as `violations` with a `count`. `200` with an empty list, not an error, when nothing failed its contract, the common, expected case. Rendered in the console as its own section, disappearing when empty. |
| `GET` | `/runs/{run_id}/convention-assignment` | token | The convention assignment computed once at this run's BOOT (`docs/api/CONVENTION_ASSIGNMENT_DESIGN.md`): a one-way subject label on each side, each agent's own declared `subjects` in `config/agent_registry.json`, each rule's own bracket tags read structurally off its heading by `convention_parser`, compared by `convention_assignment.assign_conventions`, code that names no subject itself. Per rule (`by_rule`): its `subjects`, the agent(s) matched, which of those have a live rule-consuming path today (`consumer_agents`), and `status` (`untagged`: no tag at all, today's routing is unchanged; `assigned`: matched an agent that can act on it; `assigned_no_consumer`: matched only an agent with no rule path today, for example a rule tagged for an agent that declares an empty `subjects` list; `unassigned`: no agent declares any of its tags at all). Per agent (`by_agent`): the rule ids it matched. Also `rule_count`, and `idle_agents`: every agent that declares a subject in the CURRENT `config/agent_registry.json` (or `SHIMMER_AGENT_REGISTRY`) but matched no rule this load, each entry naming the agent and the subjects it declares (`convention_assignment.idle_agents_summary`, read against the live registry, not the run, since agent declarations are not per-run data); the console renders these as the agents no tagged rule reached. A rule the assignment could not route anywhere is never dropped, the same discipline as `/amendment-refusals` and `/contract-violations`: it is also posted to the bus as `CONVENTION_UNASSIGNED` (computed, python, one item per unmatched or consumer-less rule, `rule_id`/`source_rule_id`/`subjects`/`reason`) when at least one such rule exists. Written once at BOOT to `audit/convention_assignment.json`; this route reads that file directly, not the bus, since the file is never rewritten mid-run. `200` with empty `by_rule`/`by_agent`, not an error, for a run that predates this route. Also (night W8) `untagged`, the count of rules with no tag, and `not_firing`, the convention-review agents the W3 firing gate kept from running on this assignment (`convention_assignment.not_firing_convention_review_agents`, the same function the pipeline's gate delegates to; empty for an assignment with no rules, where the gate decided nothing). |
| `GET` | `/runs/{run_id}/undated-documents` | token | The documents this run could not date, and which of those therefore went unreviewed. A document with no resolvable date fails the review cutoff (`review_scope.apply_cutoff` keeps dates at or after the cutoff, and `None` is never at or after anything), so it leaves the operational set: until this route that happened silently, and a document that was never reviewed was indistinguishable in the output from one that was reviewed and produced no findings. Same visibility discipline as `/runs/{run_id}/convention-assignment`, `/amendment-refusals` and `/contract-violations`. `undated` is every document the cascade could not date (`filename` and `date_source` only, structural, no content); `excluded` is the load-bearing list, the ones that are undated AND not under review; `reviewed_anyway` is an undated document an operator manifest still put under review, which is not a silent drop. Also `undated_count`, `excluded_count`, and `note`, which says how to review them anyway (name them in `input/context/_review_targets.json`, or set `cutoff_type` to `all` in `config/review_scope.json`). Written once at BOOT to `audit/undated_documents.json`; this route reads that file directly, never rewritten mid-run. `200` with empty lists, not an error, for a run that predates this route. |
| `GET` | `/harness` | token | The nine-part agent harness (night W4), one entry per agent, as `scripts/build_agent_harness.py` generated it into `config/agent_harness.json` (or `SHIMMER_AGENT_HARNESS`): `agents`, `shared_parts`, `part_names`, and `unresolved` (per agent, the parts still `decided: false`, each carrying its own `unresolved_because` in `agents`), so the console's Agents page shows an undecided part as undecided rather than omitting it. Also `agent_count` and `unresolved_part_count` (18 and 18 for the shipped harness: every agent's ontology part is undecided until an agent reads the store). Not run-scoped. `404` with a distinct detail when the harness has not been built on this server; `500` with detail "agent harness unreadable" when the file exists but does not parse. |
| `GET` | `/runs/{run_id}/references` | token | The passages a run's findings cite (console audit, finding 4, the most serious one it found). Every Finding and every amendment carries `source_refs`, and until this route nothing served the passages behind them: a reader could see that a finding cited something and not what, which leaves nothing to do but trust the sentence. Reads the run's own `audit/reference_index.json`; per entry `ref_id`, `document_id`, `document_name`, `location` and `text_excerpt`, the passage as the builder stored it. `ref_id` (optional) returns one, which is what a reader following a single citation asks for, and `404` when this run's index holds no such id, because "this run never cited that" and "that passage is empty" are different facts. A run with no index is a `200` with `index_present: false`, not a `404`. The passage text is content deliberately: showing the words a finding rests on is the point. |
| `POST` | `/runs/{run_id}/evidence` | token | Classify missed expected defects against a run's saved artifacts (console audit, the evidence screen). THE CALLER supplies the expected entries in the body (`{"expected": [{"unit": ..., "rule": ...}]}`), which is the only thing an answer key contributes; the classification reads nothing but this run's own pairing map, convention assignment, call evidence and bus, and **no key path is opened, named or accepted**. Per entry: one of the four classes, the unit ids it resolved to, the registry rule id, and `basis`, naming the artifact behind every step so a classification can be checked rather than believed, plus `counts` over the four. A POST because the expected entries are the request body; it writes nothing. `400` for an empty or unusable list. |
| `GET` | `/ontology/relations` | token | The relations between provisions the store holds (console audit, finding 6): `relation_summary` was a finished read path whose only callers were gate assertions. One row per unordered pair, each carrying `found_by`, `agreed` and `observations`, one per mechanism keeping the direction that mechanism reported. `by_method` counts observations while `relation_count` counts pairs, so the two do not sum once a pair is agreed; `agreed_count` is the figure the old concatenated form could not report at all. Ordering is the one declared rule: a pair found by both ranks above a pair found by one. Not run-scoped; an empty store is a `200` with an empty list. |
| `POST` | `/ontology/conflicts/{conflict_id}/answer` | token | Record the operator's answer to one ontology-versus-rule conflict, in the same file-backed pattern `POST /runs/{run_id}/approval` uses and with the same two constraints: it WRITES the answer and nothing else (the next run applies it, through `apply_resolutions`), and the response says the answer was RECORDED, never that anything was resolved. Body `{"answer": "rule"|"store"|"refuse", ...}` with the two sides optional and recorded when given, so a later reader sees what the conflict WAS. Three answers, not two: "refuse" is a real decision and is distinguishable from never having answered. An unrecognised answer is a `400` and is never written. Re-answering supersedes, by the storage layer's own rule: an operator may change their mind. |
| `GET` | `/ontology` | token | ontology chain job 1: the first read path the ontology store has ever had. The store under `ontology/stores/` has been written at the end of every run since build B1 and read back by nothing; this route answers the one question it can answer, which agent produced which provision under which rule, in which run, at which revision. Returns `scope`, `provision_count`, `stub_count`, `without_provenance`, `superseded_in_live`, `log_events`, counts by `agents` / `rules` / `runs` over the whole scope, and `provisions`, a per-provision list carrying identifiers and provenance ONLY, never a provision's own text (that boundary is `ontology_reader.SUMMARY_FIELDS`, not a convention this route applies by hand). Not run-scoped: the store is cross-run by construction, the same reasoning `/harness` and `/rules/{rule_id}` already use. An EMPTY store is `200` with zero counts and an empty list, not a `404` and not an error, which is the state of every store in this repository today. What this reading is good for, and what it is not, is in section G. |
| `GET` | `/ontology/provisions/{provision_id:path}` | token | One provision's every revision in the default scope, oldest first, as provenance summaries: what makes the storage layer's supersession (built at night W7, shown nowhere) legible to a human. The id is the capture hook's composite `<document_id>::<ref_id>`, so it carries a colon pair and is matched as a path parameter. `404`, not an empty list, when the scope holds no such id: "this store has never held that provision" and "that provision has one revision" are different facts and a caller must be able to tell them apart. |
| `GET` | `/ontology/gnn` | token | ontology chain job 4: the GNN's persisted state, structural metadata only (the state file holds weights and counts and no raw content by construction; this surfaces the counts, never the weights). Three fields are always present because they are the most important thing about this state and must not be a caveat a reader can skip: `tier2_signal` is `empty`, `learned_relevance` is `false`, and `ranked_on` says the ranking rests on graph structure alone. The engine persists and restores its weights across runs, so it does not forget; it has learned nothing because there is no signal yet to learn from, which is a different thing. Not run-scoped. A state never written is a `200` with `exists: false`, not a `404`, which is every installation today. |
| `GET` | `/ontology/candidates` | token | ontology chain job 4: candidate provision pairs the graph proposes, `top_k` per provision (1 to 50, an out-of-range value being a `400` rather than a silent default) and `min_score` to drop weak pairs. Decision 9's shape: the graph NARROWS here, a model DECIDES, and the reasoning stays in text. These are pairs that MAY relate; nothing here asserts that they do, no relation record is written from them, and the deterministic baseline stays beside this rather than being replaced. **Ranked on graph structure alone** (node type, degree, edges), with `ranked_on`, `learned_relevance` and `tier2_signal` travelling in the body beside every candidate. A graph with fewer than two provisions is a `200` with an empty list. |
| `GET` | `/ontology/conflicts` | token | ontology chain job 3: which ontology-versus-rule conflicts the operator has answered, how, and in which run, plus `override_rate`. A conflict is the narrow structural case where the store remembers one governing rule for a provision and the current run would apply another; in the run that meets it the pair is REFUSED and never guessed, the refusals are put to the operator together at the end, and the answer is written into the ontology so the same conflict is never put to them twice. `override_rate` is an object, not a bare number: `answered`, `overrode_store` (answers where the current rule won over the store's memory), `kept_store`, `kept_refusing`, a nested `override_rate`, and `caveat`, which carries its own qualifier in the response body rather than in documentation alone: at single-operator volume the rate is not statistically meaningful and must never be read as a quality measure. The NESTED `override_rate` is `null`, never `0.0`, when nothing has been answered, because "no answers yet" and "never overrode" are different facts; the object itself is always present, so a caller testing the top-level field for null never sees one. Not run-scoped; a store with no answers is a `200` with an empty list, which is every store today. |
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

Every route taking a `run_id` accepts the shared UUID format and legacy timestamped server
IDs, rejects other syntax with 404 before building a path, and `/runs/{run_id}/findings` and `/runs/{run_id}/pairs` return the
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

Each cost row carries `truncated`: `true` when the response hit its own output ceiling,
`false` when it came back short, and `null` when the backend reported no usage, because a
caller that did not say is not the same as one that said no. The wrapper computed this from
the start and it stopped there. On the 2026-09-12 runs every row read `null` while
PROCESSOR's extraction hit its 2048-token cap exactly and was cut off mid-string, so the run
recorded that the envelope was malformed and not that it had been cut, and the reason had to
be reconstructed by hand from the preserved raw text. A response that hit its ceiling and one
that came back short looked identical on disk.

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
The harness generator supplies reviewer summaries for when each agent runs and how its rule
assignment is tested. The descriptions distinguish testing the routing mechanism from testing
an individual agent's entire rule group. If a decided part lacks a reviewer summary, the console
says so explicitly; technical conditions and test details remain available in the developer view.
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
typography, layout, the dark masthead) in `docs/api/CONSOLE_PLAN.md`. The night chain (W8)
brought the console current with what the chain built, in both views, each section only to
the extent the mechanism behind it exists: on a run's page, beneath the findings, the
distribution from the convention assignment (which rules each agent handles, how many are
untagged and so go to every convention checker, `conventionDistributionHtml`), the rules no
agent handles (`conventionAssignmentHtml`), the convention checkers the W3 firing gate kept
from running on that assignment (`notFiringHtml`, the fourth visible state beside an
amendment, a refused finding and a failed contract, read from the same function the
pipeline's gate uses), and the agents no tagged rule reached (`idleAgentsHtml`, which now says
so rather than "nothing to check" while untagged rules still reach them); and a third masthead
tab, Agents (`#/agents`, `GET /harness`), one section per agent with its nine harness parts,
an undecided part shown as undecided with its recorded reason, never omitted. Every one of
these sections disappears when it has nothing true to say; none is a placeholder.
`tools/console_preview.py --screenshots DIR` captures both views of the run list, a run's
page and the Agents page through a headless browser (Edge or Chrome, its own throwaway
profile) into `DIR`, which is how the W8 report's screenshots were made. The access token is
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

**Every benchmark figure in the tables below and in section K was measured before 10
September 2026, on the code of the initial snapshot.** The only later numbers are the counts
from the two stopped device runs in this paragraph, which scored nothing.
The paired path changed in more than a dozen commits on
10 and 11 September (the adjacent-neighbour mechanism, unit order, the rule-id resolver, the
required Finding fields on PRACTICE_AUDITOR, the convention assignment and the per-plan
judging agent, the convention distribution, call evidence, the longest-match label fix and
the declared-scope absence path), each proved on fixtures by a gate check and none yet
scored by a run. No run has been scored since. The one corpus built to measure those
changes, `device_log_review`, was run twice on 11 September and stopped by the operator both
times before any deliverable: the first attempt planned 101 pairs, made 86 local calls and
scored 0 of 9, a void figure because no finding carried a unit id; the second planned 64
pairs and showed that the four rules checking the planted flaw kinds paired with no unit,
which is what the declared-scope fix addresses. The clean twin was never run. **That
measurement is owed**, and until it is made the figures below describe the code as it was,
not the code at HEAD.

From operator testing before productization (cloud profile, wide review, the redaction phase
active), on a five-document synthetic competition-law corpus (five regulations plus five
grounding cases), single Claude API key. **That corpus has since been removed from the
operator's working repository** (not published; this is a public snapshot of source only,
section G), so the figures in this block are historical and cannot be reproduced here; the
local-profile measurements below can be reproduced on any machine with the local models
cached and a free GPU (the corpora are in `benchmark/corpora/`); since 11 September the
operator starts no pipeline run on the development laptop, and the owed device-corpus
measurement is planned on a rented GPU:

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
Measured before 10 September 2026 on the snapshot's code, one draw, on the operator's laptop
(section K); the paired path has changed since (the opening of this section) and this figure
has not been re-measured. The corpus is not in this repository, so the number is a historical
baseline, not a reproducible one.

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

Both runs date from before 10 September 2026 and were not rerun after the fixes they
exposed, nor after the 11 September pairing changes (longest-match labels, declared scope),
one of which was traced to exactly the `Extent` header the clinical corpus carries; the
figures are the last measured state, not the state of the code at HEAD.

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

Both runs date from before 10 September 2026. The comparison counts rest on a path
(`reference_tables`, the `prior_*` comparison) that has not changed since; the pair counts,
judging-call counts and band attribution rest on the pairing map and the paired loop, which
changed on 11 September (longest-match labels, declared scope, the per-plan judging agent,
plans left unjudged for board-only rules) and have not been re-measured.

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
it refuses rather than fabricates when it cannot, is unproven and the one probe available, run
before the rename tolerance existed, said it fabricates. A rename whose value stays within 2%
is now refused rather than reported as withdrawn (check 185, section K); a rename whose value
also changes is still reported as withdrawn, so 5 of those 13 cases remain wrong.

Two further defects surfaced in the band pass around it, both since fixed with checks 183 and
184, and the rename case with check 185. The first cut run 1's judging calls from 25 to 17 on
identical input (its own saved pairing map, replayed) and removed five false band records.

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
of 41 pairs, clean records included) held out the true findings with them. Both conclusions
were recorded as open design decisions in the R5 report. The first is now addressed, on 11
September, by the declared-scope mechanism (section B, gate checks 208 and 209), built
without measurement: the catalogue corpus has not been rerun against it and its conventions
declare no scope, so the 0 of 5 above stands as the last measured figure. The typed-record
gate is unchanged.

---

## K. Known limitations

Stated honestly, from operator testing:

- **The scorer now checks a reason, not only a location, on any corpus whose key states one.**
  Until 2026-09-12 a planted entry scored FOUND when a typed finding named its unit and
  carried its relation, and nothing asked whether the stated reason was true. The device key
  now states each defect as a typed `claim` (relation, field_label, the two figures, in the
  Finding record's own vocabulary) and the scorer reports THREE outcomes: reason confirmed,
  **RIGHT PLACE WRONG REASON**, and unverifiable (located only through an amendment, which
  carries no typed reason). Recomputed on the 2026-09-11 flawed run: **6 of 10 located, but
  only 4 of 10 reason confirmed**, with UNIT-LARCH exposed as a wrong-reason match and
  UNIT-VETCH as unverifiable. **Every recall figure reported before that date is a location
  count, not a detection count, including the 6 of 9 below**, and the corpora other than
  device_log_review still have untyped keys, so their figures carry the same doubt and the
  scorer says so rather than passing silently.

- **A finding can be asked to show the words it rests on.** The Finding record contract now
  carries an OPTIONAL `quote` field: the exact words from the unit the finding relies on,
  copied verbatim. Python checks the quote appears in that unit (whitespace and case folded),
  and a finding quoting text the unit does not contain is refused the way an unnamed field is.
  Optional by measurement, not by preference: making it required would have turned all 62
  findings of the two saved runs into contract violations at once, which is a migration and
  not a measurement, and most relations are settled by arithmetic that needs no quote. It is
  asked for where it can actually check something, on absence claims. Cost, measured on the
  corpus: a field line is a median of 21 characters, about 6 tokens, 25 at the longest,
  against 461 tokens of unused paired-judging budget.
- **A quote is REQUIRED on an absence claim, from commit 9b4f027 forward.** An absence claim
  is the one claim the document itself can refute and the one the model invents most, so a
  missing_field answer with no quote is refused. The requirement lives at the point a reply is
  judged, deliberately NOT in the contract's required-field list: putting it there would mark
  every finding of every past run a violation, including the 62 published on 2026-09-11, of
  which 14 are absence claims. A contract applies from the commit that introduces it. Measured
  cost in the next run, from the saved pairing maps: 14 judged absences (5 flawed, 9 clean)
  are the claims now asked to carry a quote; the 7 computed absences are Python's own
  arithmetic and need none. A claim the model does not quote for is refused and recorded under
  `absence_refused`, not silently dropped.
- **The scorer reports a claim worded identically in both twins.** The twins differ exactly
  where the defects are, so a sentence the model produces against both was not read off
  either. This is the signal that exposed UNIT-VETCH, found by a person reading two logs side
  by side; the scorer now runs it. The twin is declared by the answer key (`twin_of`), never
  guessed from a filename, and a key with no twin or a twin with no scored run says
  unavailable rather than reporting a confident zero. The unit id is deliberately excluded
  from the comparison: the same hallucination lands on the same unit in both twins, so
  including it would make every pair match and prove nothing.
  The evidence that forced this: the model produced a `missing_field` claim on UNIT-SPRUCE
  and UNIT-VETCH in BOTH twins with near-identical wording, and on VETCH the claim is false
  in both, saying the document "does not mention the next calibration visit" when the entry
  states it plainly. Two of those wrong sentences landed on units the key calls flawed and
  were counted as catches. A coincidence that scores is worse than a miss, because it
  inflates the one number the project is judged on.

- **The D6 deepening pass is BOUNDED at 6 findings per document** (`DEEPEN_MAX_FINDINGS`).
  It used to make one LEGAL_ANALYST call per pass-one finding with no ceiling at all.
  Measured 2026-09-11: the flawed twin returned 1 finding and made 1 call (173 s); the clean
  twin returned 5 and made 5 (709 s, **27.7% of that run's whole wall clock**) at about 145 s
  each, so ten findings would have added roughly 24 minutes. The cap is one above the largest
  number a real run has produced, so **neither measured run changes**, and when it binds it
  says so on stderr and in the log rather than silently truncating: the undeepened findings
  keep their pass-one form and are still reported.
- **The clean twin produced five pass-one findings where the flawed twin produced one**, which
  is backwards: the document with its defects repaired yielded MORE observations than the one
  with defects in it. The two documents differ only in the repairs. Not explained by the
  corpus, and not explained here. Two candidates, neither verified: local model
  non-determinism between runs, or pass one responding to repaired text with more
  observations. Distinguishing them needs a repeat run. Recorded, not fixed.
- **Everything built on 10 and 11 September 2026 is unmeasured.** The last scored run
  predates all of it (section J opening); every mechanism from those two days is proved on
  gate fixtures only, the device-corpus measurement was stopped twice, and it is owed.
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
  repository. Cloud runs are unaffected. Since 11 September 2026 the working rule is that no
  pipeline run is started from that laptop at all; measurement moves to a rented GPU box.
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
- **A completeness rule whose scope is not declared is still rejected for exactly the unit
  that lacks its field.** The text-derived pairing rule "a rule pairs only with a unit
  carrying every field it names" is right for a computational rule and backwards for "every
  record must state a creator": measured on the catalogue corpus, 3 of 5 planted flaws were
  never asked about for this reason. Since 11 September 2026 the operator can declare the
  scope instead (`[scope: ...]` and `[requires: ...]` on the rule heading, sections B and
  E): a scoped rule pairs on its declared fields, a declared required field the unit lacks
  is a finding Python decides with no model call, and a scoped rule with no declared
  requirement is put to the model as one narrow question per unit in scope. The path each
  absence took is recorded in the pairing map. This is built and gate-proved (check 209) but
  has not been scored by a run. The device corpus's four absence rules now declare scopes
  (section E), and the first draft of those declarations (`docs/fix/STEP_DECL_REPORT.md`)
  showed two limits of the form: a scope value must be written as the document writes it,
  and a rule with a declared requirement never reaches the model, so a rule about a duration
  (a fault acknowledged within a window) cannot be expressed as a requirement, only as a
  scope with the question left to the model. **Python now computes a duration between two
  timestamps** (check 217, "Duration arithmetic" below), which narrows this limit to the
  scope-declaration mechanism specifically: it still cannot express "the gap must not
  exceed X" as a requirement, but the gap itself is no longer necessarily a model question.
  The round-N `absent_since_prior` path does not depend on pairing and is unaffected.
- **A renamed label whose value also changes is still reported as withdrawn.** A field
  label renamed between two versions, while its value stays within a tolerance (2% relative
  by default, `config/rename_tolerance.json`, operator-editable), is now refused rather than
  reported `absent_since_prior`: check 185 proves it, both directions, on the negotiation
  corpus and by neutralise-and-restore. What is still not solved is the harder case: when
  BOTH the label and the value change between versions, nothing corroborates that this is a
  rename rather than a withdrawal, so the field is still reported `absent_since_prior`,
  wrongly. On the negotiation corpus, measured once before 10 September 2026 and not
  re-derived since the 11 September pairing changes, this left **5 wrong cases out of 13**,
  down from **12 wrong out of 13** before the fix; check 185 proves the refusal itself, not
  these counts. A term that is new in the later version produces
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

### A change of working discipline, and where it starts

**From commit `9b4f027` onward the README is checked once at the end of a working run, not
before every commit.** Before that commit, every single commit was preceded by a full README
pass. The operator made this change on 2026-09-12 to cut repetition rather than rigour, and it
is recorded here so a reader can tell that a commit from last week and a commit from today
were made under different standards.

What did NOT change, and is not negotiable: every new behaviour is still gate-proved by
neutralise, fail, restore, pass, and every commit is still preceded by an adversarial read of
what it contains. Those two have earned their place. Between 10 and 12 September 2026 they
caught six wrongly-passing checks and ten real defects, including two checks of mine that
passed against a mock while the real code was broken.

A reader auditing a commit from before `9b4f027` can assume its README was current at that
commit. A reader auditing one after it should look to the end of that working run for the
README pass that covers it.

### A note on em dashes

The project rule is no em dashes: use commas, colons, periods, or parentheses. The rule
applies to **anything newly written from here on**, in code, comments, documentation and
commit messages.

It is not retroactive, and reading the existing text will not teach it to you. About 340 em
dashes are already in the tree, across roughly 31 files, and they are staying. Most of them
are in `genesis.md` (156) and `config/constitution.json` (21), which are append-only governed
files that must not be rewritten to satisfy a style rule, and the rest sit in module
docstrings written before the rule was adopted. Do not take any of them as permission, and do
not "fix" them in passing: a diff that rewrites an existing line for punctuation alone buries
the change that matters, and in the governed files it would trip the constitution guard.

New text, no em dashes. Existing text, left alone.

`scripts/verify_session1.py` is the standard health check. Its total is the length of its
CHECKS list (**248** at the time of writing), not a hardcoded number, so adding a check
raises the total by itself. Each check proves behavior with executed coverage on fixtures and
is non-mutating (it uses tempdirs and never writes the real durable, ontology, or config
stores). Run it every session and before every commit:

```
py -3.9 -X utf8 scripts/verify_session1.py
```

With `--offline` the two checks that touch the network (15, a live search, and 38, an
embedding-store build that downloads a model) are reported SKIP rather than run; the
container image runs the gate this way by default (`docker run --rm --gpus all shimmer:local
verify`, section G). The first offline gate inside the rebuilt image, with the network
blocked and the host model cache mounted, gave `PASS=204 SKIP=2 FAIL/ERROR=4` of the 210
checks the gate held at that commit, the four failures being the source-only ones in the
table below; checks 210 to 243 have since raised the total to 244. The host gate at the
recovery baseline at `64b83e0` is `PASS=242 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=244`, the two failures being
the known environment ones: check 01 (`prompts/` and `snapshots/` absent in this working
tree) and check 145 (the contamination-probe fixture is gitignored and absent).

**On a fresh clone of this snapshot, four checks fail, by design, before you have run
anything.** All four fail for the same reason: this repository ships source only, and each
of these checks proves something about a directory a tool or the pipeline creates later, not
something this repository carries.

| check | fails because |
|---|---|
| 01, directory structure | `input/`, `output/`, `durable/`, `prompts/`, `snapshots/` and their subdirectories are not shipped; the pipeline creates `output/` and `durable/` on first run, `input/` comes from the intake wizard or `tools/stage_corpus.py`, `snapshots/` is created by `--save-snapshot NAME` and `prompts/` by nothing, so those two are made by hand (or by saving one snapshot) for this check to pass |
| 28, `input/` exists and accepts documents | `input/` is not shipped; it is where the pipeline reads documents from, and it does not exist until you or the wizard create it |
| 31, `input/` has `context/`, `operational/`, `conventions/` | same root cause as check 28: no `input/` yet |
| 145, no planted benchmark figure in `config/`, `scripts/` or `tests/` | `tests/` is not shipped (see "Benchmarking" above); the contamination probe has nothing to scan, so it fails rather than passing silently |

A gate that passed every check on an empty checkout would be proving nothing about those
four; failing loudly is correct here; there is nothing to test, not something broken. Two
more checks depend on the machine rather than the tree: check 193 loads one of the
local-profile models with the network blocked at the socket and fails until the weights are
in the local Hugging Face cache (it also needs a CUDA device); checks 15 and 38 make network
calls and are skipped, not failed, only under `--offline`. Checks 28 and 31 pass once
`input/` and its three subdirectories exist. Check 01 additionally requires `prompts/` and
`snapshots/`, which no run creates for you (`--save-snapshot NAME` creates `snapshots/`;
nothing creates `prompts/`): on the operator's own machine it fails on exactly those two
directories after every run, and that is the expected state of a checkout that has never
saved a snapshot or held a job spec. Check 145 needs a `tests/` directory
with planted-figure fixtures, which this snapshot does not carry and an operator adds locally
if they want that specific check.

**The vocabulary probe (check 174) and `config/domain_vocabulary.json`.** A standing,
deterministic check that no operator-declared domain term appears in the code surface
(`config/`, `scripts/`, `tests/`, `tools/`). `input/` and `benchmark/` are never scanned:
they are operator material, and domain vocabulary is exactly what they are supposed to
contain. `config/convention_registry.json` is exempt for the same reason, being gitignored
and generated at BOOT from `input/conventions/`.

The term list lives in the JSON file and **nowhere in the check**, which is the whole point:
the previous guard (check 22) hardcoded its regex against the domain of the day and
therefore could never catch a leak from any other domain. Check 22's own terms belong in
that file too, under a `previous_domain` family. This public snapshot carries no such family
(there is no prior operator's domain to guard against here), and check 22 treats a missing
or empty family as nothing to guard, passing and saying so; adding a `previous_domain` family
with terms turns the guard back on without any edit to code.

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
prose carrying one incidental figure is not treated as a column of measurements. After those:
(185) a renamed label with the same value refuses rather than fabricating an absence; (186 to
190) the run resource, cancellation, approvals, per-document and partial deliverables and the
retired-route cleanup of the server; (191 to 194) unit order, the paired call's separation of
unit, neighbour and map, the real local loader with the network blocked, and contract field
names matching their readers; (195 to 199) the nine-part harness, the rule-id resolver,
bracket tags, the convention assignment with its route and console state, and the firing gate
with the per-plan judging agent; (200 to 202) the ontology store's scope, provenance and dual
track; (203) the console current with the chain; (204 and 205) call evidence reconstructed
from disk and the four-class false-negative classifier; (206 and 207) the convention
distribution on the paired path and the three recording gaps; (208 and 209) longest-match
labels and the declared-scope absence path; (210) the ontology store's first reader,
(211) the deterministic relation baseline, (212) ontology-versus-rule conflicts with the
operator's remembered answers, (213) the GNN candidate finder ranked on graph structure and
(214) the console's missing screens with the citation surface, all five proved on fixture
records because every store in this repository is empty. Everything from 186 on was built on 10 and 11 September 2026 and
is proved here on fixtures only.

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
