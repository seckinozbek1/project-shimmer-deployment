# STEP CONVASSIGN 4 REPORT: the harness regenerated

The fourth and last of the commits the operator ordered with the ten answers: regenerate
the nine-part agent harness (`config/agent_harness.json`, night chain W4) for the three
parts the convention assignment decides or changes, and shrink the gate's unresolved set to
the one part that genuinely remains, ontology, which waits on W7.

## What changed

**`scripts/build_agent_harness.py`**, the only writer of the harness file (it reads
`config/agent_registry.json` and `config/agent_contracts.json` and nothing else, so the
harness cannot drift from the registry it describes):

- **Part 3, the rule cluster assigned to it: closes.** The module constant
  `RULE_CLUSTER_PART` (decided false, "W2 stopped at its own premise check") is replaced
  by `_rule_cluster_part(name, reg)`: decided true, `declared_subjects` read from the
  agent's own `subjects` in the registry, and `where` naming both the declaration and the
  per-run cluster (`by_agent[<name>]` in `<run>/audit/convention_assignment.json`,
  computed once at BOOT). For the six agents that declare an empty list by the operator's
  decision (PROCESSOR, ARCHIVIST, INST_FINDER, CITATION_RESOLVER, SPEECH_ACT_TAGGER,
  AMENDMENT_DRAFTER), the part carries `empty_by_decision: true` and the registry's own
  `subjects_note`, so an empty cluster reads as a decision with a reason, never as a part
  nobody wrote.
- **Part 4, testing against that cluster: closes.** `TESTING_AGAINST_CLUSTER_PART`
  ("depends directly on rule_cluster") is replaced by `_testing_against_cluster_part(name,
  reg)`: decided true, `how` naming gate check 198 (the comparison, its route, the console
  state, on fixture registries) and gate check 199 (the firing gate and the subject-chosen
  paired judging agent, executed against the real `_paired_convention_review`, neutralised
  and restored), both stated as tests of the mechanism rather than of this agent in
  particular; it says plainly that `scripts/harness/run_agent.py` runs the agent against
  one rule the OPERATOR names (`--rule-file`, `--rule-id`) and does not select by subject,
  so it exercises the agent, not the cluster, and that no other per-agent cluster test
  exists. An agent with no subjects gets the added sentence that there is no cluster to
  test against. `cluster_is_empty_by_decision` mirrors part 3.
- **Part 8, fires at all: regenerated for three shapes that changed or were incomplete.**
  `FIRES_UNCONDITIONALLY` no longer claims "no per-agent rule-cluster gate exists (W2
  stopped before one could)", which commit 3 made false; it now covers the production and
  audit lists only, with the reason they carry no gate (they produce what the review
  consumes). New `FIRES_CONVENTION_REVIEW` for PRACTICE_AUDITOR and STYLE_GUARDIAN states
  the W3 firing gate (wide mode) and the subject-chosen judging agent with its
  PRACTICE_AUDITOR fallback (paired mode), citing `_convention_review_firing_agents`,
  `_paired_judging_agent` and gate check 199. New `FIRES_LEGAL_ANALYST` records the D6
  two-pass split the W6 report found and owed to this file: once in phase 3, then once per
  pass-one finding under the local profile, serial, bounded, not a retry (observed 1 + 5
  calls on run 3d3142c8). The comment that counted "four" firing shapes now counts six.
- **Part 5, ontology: unchanged, still unresolved**, until W7 runs. Parts 1, 2, 6, 7 and 9
  unchanged.

**`config/agent_harness.json`** regenerated from the edited builder: 18 agents, every
`rule_cluster` and `testing_against_cluster` decided, six clusters empty by decision with
their notes, `ontology` unresolved on all 18, the two convention-review agents and
LEGAL_ANALYST carrying their new part-8 text. Confirmed by direct read after the build,
not assumed.

**`scripts/verify_session1.py`, check 195.** `KNOWN_UNRESOLVED_PARTS` shrinks from
`{rule_cluster, testing_against_cluster, ontology}` to `{ontology}` in both places the
check carries it (its body and `_run_195_body`, the copy the neutralisations re-run).
Parts 3 and 4 must now be `decided: true`. Assertions added: every agent's
`rule_cluster.declared_subjects` must equal the live registry's `subjects` for that agent
(a drift check, the whole point of building the harness from the registry); an empty
cluster must carry `empty_by_decision: true` and a `subjects_note` equal to the registry's
own non-empty note; a non-empty cluster must not carry `empty_by_decision`; part 4 must
carry a non-empty `how` and a `cluster_is_empty_by_decision` that agrees with the registry.
A second neutralisation joins the existing one (stripping `PROCESSOR.rule_cluster.decided`):
a copy of the harness with the first subject-carrying agent's `declared_subjects` emptied
(EDITOR_CLERK, chosen dynamically) must fail the body on the drift, and the live file must
pass.

What the rewrite turned up, and changed: the check's neutralise-and-restore had been
WRITING the live `config/agent_harness.json` (mutate it, run the body, restore it verbatim),
which the gate rule in CLAUDE.md forbids (checks use tempdirs and never write the real
`config/` stores). Both neutralisations now run on a tempdir copy, `_run_195_body` takes
the path to check (default the live file), and the check ends by asserting the live file is
byte-identical to what it read, so a crash mid-check can no longer leave a mutated harness
behind. The drift agent is chosen dynamically (the first agent, alphabetically, whose
registry entry declares a subject: EDITOR_CLERK today) rather than hardcoding one; a
registry in which no agent declares any subject fails the check outright, since the
convention assignment would then have no consumer. The two `KNOWN_UNRESOLVED_PARTS`
copies carry a comment naming the commit that shrank them and the step (W7) that empties
them. A part 4 record must also carry a non-empty `how` and a `cluster_is_empty_by_decision`
that agrees with the registry.

Single-check result on the regenerated harness (before the full gate):

```
('PASS', "all 18 registry agents have a harness entry with all nine parts present;
rule_cluster and testing_against_cluster are decided:true for every agent,
declared_subjects equal the registry's subjects, and 6 empty clusters (AMENDMENT_DRAFTER,
ARCHIVIST, CITATION_RESOLVER, INST_FINDER, PROCESSOR, SPEECH_ACT_TAGGER) carry
empty_by_decision with a note; ontology is explicitly decided:false with a stated reason
for every agent (W7); ... neutralise-and-restore on a tempdir copy (a stripped 'decided'
field, then EDITOR_CLERK's declared_subjects emptied against the registry) proves the
check reads the file's structure and the drift check is live; the live config/ file was
not written")
```

The old check against the new harness fails mechanically (it required `rule_cluster` and
`testing_against_cluster` to be `decided: false`, which the regenerated file no longer
says), and the new check against the old harness fails on the same two parts in the other
direction; the two files change together, in this commit.

**`README.md`, section 4a** (the nine-part harness): the six firing shapes, parts 3 and 4
decided by the convention assignment (declared subjects; empty by decision for six agents
with a note; per-run cluster in `audit/convention_assignment.json`; proved by checks 198
and 199), ontology the one part still undecided, and check 195's three failure conditions
(a missing part, a cluster that drifts from the registry, the unresolved part marked
decided).

## Gate result

```
PASS=198  WARN=0  SKIP=0  FAIL/ERROR=2  TOTAL=200
```

Identical to the baseline after commit 3, on both full runs (`output/convassign4_gate1.log`
before the pre-commit review, `output/convassign4_gate2.log` after its fixes); the two failures
are the pre-existing checks 01 (missing `prompts/` and `snapshots/` directories) and 145
(missing `tests/fixtures/planted_figure_hashes.json`), unchanged by this commit. Check 195
passes with the message quoted above. No check was added; the check that changed proves
strictly more than before (three assertions added, two neutralisations instead of one, and
the live `config/` file no longer written).

## What this closes and what it leaves

Closes the W4 harness correction owed since the W6 report (the LEGAL_ANALYST D6 clause) and
the two harness parts the convention assignment design said it would close. Leaves
ontology, correctly, for W7. With this commit the four commits the operator ordered are
done; what follows in the recorded order is the W6 rerun (blocked on the operator tagging
the eight device rules), W7, W8 and W9.

## Things found on the way, not fixed here (per the operator's own instruction)

Unchanged and still recorded: two em dashes in `config/agent_registry.json:144` (EDITOR_DG's
first `does` entry; earlier reports cited line 127, its line before commit 2 moved it),
copied verbatim by the builder into `config/agent_harness.json:1041`, present at HEAD before
this commit and not introduced here; the missing `previous_domain` vocabulary family; the
unkept genesis Section C promise.

## Reviewed before commit

An adversarial review of the staged diff (three lenses, every finding independently
refuted or confirmed twice) confirmed four defects, all fixed before the commit: part 4's
`how` claimed `run_agent.py` draws a rule from the agent's declared subjects, which it has
never done (reworded as above, and the harness regenerated); the check's "byte-identical"
assertion compared text after newline translation (now `read_bytes`); the check accepted
any non-empty `subjects_note` while its message said "the registry's" (now equality with
the registry's note, in both copies); and this report's first draft described the drift
neutralisation as a live-file rewrite of PRACTICE_AUDITOR, which the code never did
(corrected). Refuted and left alone: the em dashes and a domain-vocabulary hit in the
harness (both inherited verbatim from registry entries this commit does not touch, both
present at HEAD). From
commit 3, still open for the operator: the device corpus's date rides on a web lookup
(ship its manifest, or make `stage_corpus.py` refuse a network-dependent target); a local
run commits ~12 GB and this machine pages below ~3 GB available; an uncomputable paired
plan's model judgment is never captured into a Finding.

---

STEP CONVASSIGN 4 COMPLETE (harness parts 3, 4 and 8 regenerated from the registry; check
195's unresolved set is {ontology}; README current)
