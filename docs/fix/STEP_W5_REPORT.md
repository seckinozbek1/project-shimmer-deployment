# STEP W5 REPORT: the remaining name mismatches

## The list, found in commit 91ba603's own message

The original rule-id name-mismatch fix (`91ba603`, "Close the rule-id name mismatch, never
drop a finding silently, enumerate the pattern") fixed one live instance (`amendment_from_
finding` dropping 5 real PRACTICE_AUDITOR findings because it read only `rule_id`, never
`procedure_id`, the agent's own contract field) and, per the operator's own instruction at the
time, enumerated three more without fixing them: "three more real instances of the same shape...
found in pipeline.py's category classification (`_category_for_conv`, no fallback),
pipeline.py's `_stamp_source_rule_ids` and finding_record.py's `index_findings` (an existing
2-name fallback missing `procedure_id`, and a related lookup with no fallback at all), and
server.py's `_project_finding` (an existing fallback naming the wrong two of the now four known
names). None touched." This step closes all three.

## Traced against the live code before touching anything (Wa)

**Instance 1: `pipeline.py`'s `_category_for_conv` caller.** `_process_doc`'s finding loop
(line ~1986) read `f.get("conv_id")` directly, no fallback. A PRACTICE_AUDITOR finding carries
`procedure_id`, never `conv_id`, so this call always returned `None`/`"unclassified"` for it.

**Instance 2: `_stamp_source_rule_ids` + `index_findings`.** `_stamp_source_rule_ids`
(`pipeline.py` line ~294) read `item.get("rule_id") or item.get("conv_id")`, a two-name
fallback missing `procedure_id` and `convention_ref`. `finding_record.index_findings`
(line ~295) read `item.get("rule_id")` alone, no fallback at all, used by `apply_typed_fields`
to look an amendment's source finding up by rule id.

**Instance 3: `server.py`'s `_project_finding`.** Read `item.get("rule_id") or
item.get("claim_id")` (line ~880), the wrong two of the four real names: `claim_id` is a
legacy pre-settlement name, never `procedure_id` or `conv_id`.

**A fourth, sharper bug found while fixing instance 2, not in the original list.**
`apply_typed_fields` (`finding_record.py` line ~342) copies a matched finding's rule id onto
an amendment with `amended["convention_ref"] = source["rule_id"]`, a bare bracket access, not
`.get()`. Before this step, `index_findings` never matched a `procedure_id`-only finding at
all, so this line was never reached for one; fixing `index_findings` to actually match such a
finding would have made this line `KeyError` the next time it ran against real
PRACTICE_AUDITOR output, a crash, not the silent drop the rest of this pattern produces.
Closed in the same commit, same resolver.

## The fix

All four sites now call `finding_record.resolved_rule_id(item)`, the same shared resolver
check 194 already holds in place for the original instance, instead of an ad hoc `.get()`
chain of their own:

- `pipeline.py`, `_process_doc`'s loop: `_category_for_conv(finding_record.resolved_rule_id(f), ...)`.
- `pipeline.py`, `_stamp_source_rule_ids`: `rule = finding_record.resolved_rule_id(item)`.
- `finding_record.py`, `index_findings`: `rule = str(resolved_rule_id(item) or "")`.
- `finding_record.py`, `apply_typed_fields`: `amended["convention_ref"] = resolved_rule_id(source)`.
- `server.py`, `_project_finding`: `"rule_id": _fr.resolved_rule_id(item) or item.get("claim_id") or ""`
  (the `claim_id` fallback kept, since `resolved_rule_id`'s alias list intentionally does not
  carry that legacy name; the function's own docstring already explained why it stays).

## Full shape search, re-run per this step's own final instruction

Searched every `.get("rule_id")` / `.get("conv_id")` / `.get("procedure_id")` /
`.get("convention_ref")` / `.get("claim_id")` in `scripts/*.py` outside `finding_record.py`
itself. Every remaining hit was checked against where its data actually comes from:

- `docx_builder.py`, `ontology_capture.py`, `ontology_graph.py`, `paired_review.py` (lines
  1671, 1725), `server.py` (lines 1448-1449): all read `convention_ref` off an **amendment**,
  not a raw agent finding; amendments carry that field by contract under one name always, not
  one of the four rule-id variants. Out of scope.
- `pipeline.py` (line 1312) and `paired_review.py` (line 1385): read `rule_id` off the pairing
  map's own `paired` list entries (`pairing_map.py` mints these with the literal key `rid`
  directly from the convention registry, confirmed at `pairing_map.py` lines 271/277/285).
  Never agent-produced. Out of scope.
- `server.py` (line 1006): reads a Python-constructed `AMENDMENT_REFUSED` refusal record,
  which already carries `"rule_id": resolved_rule` from `paired_review.py`'s own
  `ensure_amendments_for_findings` (part of the original `91ba603` fix, already correct).
  Out of scope.
- `server.py` (line 1130): reads the pairing map's own `paired`/`rejected` entries again (same
  Python-minted structure as above). Out of scope.
- `verify_session1.py` (multiple lines): all test fixtures, either exercising `_category_for_
  conv` directly with hand-built `conv_id`-shaped dicts (a different function than the one
  fixed here) or asserting against amendment/pairing-map structures. None call the four fixed
  sites with a field-name variant that would be affected by this step.

No further instance found. The pattern search comes back empty.

## Never silently discarded

`apply_typed_fields` already had its "cannot match, return untouched" path (`if source is
None: out.append(amendment); continue`); fixing `index_findings` only widens what it CAN
match, it does not change what happens when it cannot. `AMENDMENT_REFUSED` (from the original
fix) remains the visible refusal channel for a finding that truly cannot be turned into an
amendment at all; nothing in this step's four fixes needed a new refusal path of its own, since
none of the four sites drops a record today, they under-recognise it, which resolving through
the shared resolver corrects directly.

## Gate check 196

`check_196_every_remaining_rule_id_consumer_reads_the_real_field_name`, added to
`scripts/verify_session1.py`. Drives all four fixed sites with a single `procedure_id`-only,
no-`rule_id`-key finding (the exact shape that exposed all four gaps live) and confirms each
now resolves it correctly: classification, `source_rule_id` stamping, `index_findings`
matching plus `apply_typed_fields` copying (the former-`KeyError` site), and the `/findings`
API projection.

Neutralise and restore: `finding_record.RULE_ID_FIELD_ALIASES` has `procedure_id` stripped,
and all four sites are shown to lose the finding identically (proving each depends on the one
shared resolver, not a private duplicate list that could drift independently); restored, all
four recover.

## Gate result

`PASS=195 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=197`, up from W4's `PASS=194 TOTAL=196` by exactly
one check (196), zero regressions. The same two pre-existing failures as every step this chain:
check 01 (`missing dirs: ['prompts', 'snapshots']`) and check 145 (`tests/fixtures/
planted_figure_hashes.json is missing`).

## README

Section documenting `GET /runs/{run_id}/amendment-refusals` (route table) updated to describe
the wider fix: the original single-site resolver wiring, this step's three further sites, and
the `apply_typed_fields` `KeyError` this step's own fix exposed and closed alongside them.

---

STEP W5 COMPLETE (fixed: 3 enumerated instances + 1 newly-found `KeyError`, all four through
`finding_record.resolved_rule_id`; gate check 196; README updated; shape search re-run, none
remain)
