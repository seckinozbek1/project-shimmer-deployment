# INFRA-055 (draft, NOT applied): a "does not contradict" answer is kept as that answer

Status: draft for the operator's ratification (D-652, D-657). Nothing below is applied; `config/constitution.json`
is unchanged. On a yes it is appended as one new amendment through the verified no-gap path (INFRA-029). INFRA-046
is never edited: this amendment states that its `verdict` clause is read as narrowed from the date of this one.

## The amendment

- **id:** INFRA-055
- **kind:** relation verdict (appended; amends the reading of INFRA-046's `verdict` clause, never its text)
- **title:** A well-formed "does not contradict" answer is kept as a model's `ok` contradiction record, never a finding
- **genesis_part:** as INFRA-046
- **operator_approved:** pending (the operator's words and time are recorded here on his yes)

**change.verdict (supersedes the reading of INFRA-046 `verdict` from this amendment on):**
"A contradiction record is irregular (two passages that cannot both be true) or ok (the model answers that the unit
does not contradict itself under the rule). An irregular record is held to every refusal INFRA-046 and INFRA-047
list, unchanged. An ok record is kept as that answer when it is well formed: relation contradiction,
record_verdict ok, and any quote or quote_b it writes stands in the unit (quote_not_in_unit, unchanged). It needs
no second quote, since it names no pair. It is the model's (written_by model), marked wherever shown, never a
finding (finding_record.is_finding counts an irregular contradiction only), never promoted, never an amendment.
Python checks only that its words stand in the unit, never that the unit does not contradict."

**change.refusals:** `paired_review.judged_item_refusal` refuses `CONTRADICTION_NOT_IRREGULAR` only for a record whose
`record_verdict` is neither irregular nor ok (for example a missing or unknown verdict). Every other contradiction
refusal applies to irregular records exactly as now.

**change.phrase:** `finding_record` relation phrases: `contradiction` keeps "two passages contradict each other" for
irregular, and gets "the passages do not contradict each other" for ok (the two are distinct; English and the
operator language through `localization`).

**change.agent_instructions (the two sentences the agents read):**
- `config/agent_contracts.json` `quote_b`, old: "... a contradiction with one quote, or not marked irregular, is
  refused. Leave it out for every other relation."
  new: "... a contradiction marked irregular with one quote is refused. When the unit does not contradict itself,
  answer relation contradiction with record_verdict ok and no quote_b. Leave it out for every other relation."
- `scripts/agent_wrapper.py` typed-record section, old: "Two passages that cannot both be true are the one
  exception: relation contradiction, record_verdict irregular, each passage copied word for word into quote and
  quote_b, no figures."
  new: "Two passages that cannot both be true are the one exception: relation contradiction, record_verdict
  irregular, each passage copied word for word into quote and quote_b, no figures. When no two passages of the unit
  contradict each other, say so: relation contradiction, record_verdict ok, no quote_b."
  (A change to the agent-facing text is a change to a measured prompt: the decoding constraint and every pinned
  prompt digest that holds these sentences are re-pinned in the same commit, and listed.)

**change.checks:** `scripts/judged_unchecked_claims_checks.py` group D is inverted: it proves that an ok
contradiction is kept, screened and not a finding (neutralised by restoring the old `!= "irregular"` line, which
must then fail), and that a contradiction with no or an unknown verdict is still refused (neutralised by removing
that refusal). `tools/judged_rescreen.py` and `scripts/reviewed_document.py` keep the reason for the narrowed case.

**change.scoring:** none in code. `benchmark/adapters/common/detection.py` already reads any kept ok record as `holds`.
So a unit answered "does not contradict" now holds. Under ContraDoc's `each` reading, a document whose every unit
holds becomes CLEAR where it was ABSTAIN, and a unit carrying both an ok and an irregular record is a conflict.

**reason:** the authority audit's checker (D-643, D-647): a "does not contradict" answer was always refused, so a
document could never be CLEAR from the model's own answer. D-652 (Seckin 16:03): fixed, its effect reported.

**effect on record (half A, records only, D-652 trace at 16:54):** 12 saved half A maps (8 of 30 documents): 0
refusals of this kind and 0 ok answers among 22 judged answers, since the agents are told never to write one. The
code change alone moves no saved decision; its effect needs the instruction change and a run (Lambda, seal route,
forecast first), and the half A showing waits for the parse sweep (D-663).
