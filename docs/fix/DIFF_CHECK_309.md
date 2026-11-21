# #309: the difference check between a source text and a proposed text (D-847, D-848)

Operator decisions: D-847 (Seckin, 20 November 2026 14:44): GitHub #309 enters the alpha, a difference
check that flags legally significant changes between a source text and the text proposed for it (a dropped
condition, a ban that becomes one-way, a widened scope, an obligation that becomes a statement). D-848
(Seckin 14:46, through the lead): the same check also flags a change that breaks the ADVISED party's red
line, from the party's recorded positions and from the red lines the user declares (#278).

## 1. Feasibility (written first, 20 November 2026, before anything else was built)

### 1.1 Where a proposed text stands next to its source

| Place | Source text | Proposed text | Files and functions |
|---|---|---|---|
| Rendered amendment | the amendment's `original_text` (the unit's own text, `paired_review` amendment builder, line about 2954) | `proposed_text`, set only by the optional `--amendment-polish` pass (`paired_review.apply_polish`, `POLISHABLE_FIELDS`); OFF by default, so a shipped run's amendments carry `proposed_text: null` | `scripts/paired_review.py` (amendment dict, `apply_polish`), carried into `review_data.json` `amendments[]` (`reviewed_document.master_lists`), shown by `reviewed_document.py` and `docx_builder.py` |
| Version changes (multi-round) | the earlier version's sentence | the later version's sentence | `scripts/version_changes.py` `sentence_changes` (aligned by Python, `_paired`, tie refused), record `audit/version_changes.json` `comparisons[].sentences[]` with `change` changed, removed or added |
| Negotiation counter wording (advisor) | the proposal's text (`neg_advisor.proposal_text(item, id)`) | the counter's `wording` (`neg_advisor.parse_advice`, entry `wording` when the stance is counter) | `benchmark/baselines/neg_advisor.py` |
| Negotiation suggested wording (case questions, M6) | the cited passage of the last round (`case_questions.read_suggestion`, its `quote`) | `suggested_wording` | `scripts/case_questions.py` `read_suggestion`, `ask_suggestions` (agent null as shipped: nothing is asked) |
| Draft mode | none: the memo is written from `--question` and has no source text | the memo | `pipeline` phase 0, `role_resolution`; out of scope: there is nothing to compare it with |

### 1.2 Can #309 be added after the output, changing no prompt, answer, finding or score?

Yes. It is additive, and the ContraDoc, SciTab and negotiation round 1 figures stay valid. Evidence:

1. Where the code lives. Everything new is in `tools/diff_check.py`, `tools/diff_check.json`,
   `tools/diff_check_checks.py`, `benchmark/fixtures/diff_check_309/` and one new check (689) in
   `scripts/verify_session1.py`. A sealed bundle's source archive takes `scripts/`, `config/`,
   `corpus_ingest/`, six named files and the extras `benchmark/adapters/` and `benchmark/baselines/`
   (`tools/prepare_ordinary_final_run.py` `RUNTIME_PREFIXES`, `RUNTIME_FILES`, `ARCHIVE_EXTRAS`), and leaves
   out every `*_checks.py`, every `scripts/verify_*` and every `/fixtures/` path (`archive_closure.gate_check_file`).
   None of the new files is in any of those sets, so no bound runtime hash, no controller hash and no source
   archive of a bundle sealed at or after this commit changes. CONTROLLER-BINDING forces no re-seal.
2. What the measured runs execute. ContraDoc and SciTab figures come from exposed B3 bundles
   (`pipeline.py` phase 5.5, the passage pair and cell claim steps) and from the replay passes of
   `benchmark/baselines/doc_judge.py` and `choice_judge.py`; negotiation round 1 from
   `benchmark/baselines/neg_advisor.py` replays. None of them imports or calls `tools/diff_check.py`; no file
   they import is edited here (`git diff --stat` of this commit names no file under `scripts/` except the
   gate, none under `config/` or `benchmark/baselines/`).
3. What the check writes. On a finished run folder it writes `audit/diff_check.json`, one
   `deliverables/<doc>/diff_check.md`, and appends ONE marked line at the end of `reviewed_document.md` and of
   `_run_summary.md`, after everything the renderers wrote (the bytes before it are kept, proven in check 689).
   It writes no finding, no amendment and no field of `review_data.json`, the pairing map, the bus or a reply
   of another agent; every record it keeps is marked "Written by a model. Not promoted to an amendment. Not
   checked by Python." (`finding_record.MODEL_FINDING_MARK`), `promoted: false`, `checked_by_python: false`.
   The scorers (`tools/score_corpus.py`, `doc_judge.py score`, `score_neg_advisor.py`) never read it.
4. Off as shipped: `tools/diff_check.json` `enabled: false`; nothing in the pipeline calls it. With it on,
   and with no measured threshold (`threshold: null`, CHOICE-A), every question is recorded with its
   probabilities and decides `cannot be settled`: nothing is flagged until a threshold is measured. (Since
   D-855 the shipped threshold is 0.999, section 5; the switch stays off.)

Nothing to measure again: no ContraDoc, SciTab or negotiation figure needs a new run (0 minutes, 0 USD, no
weekly usage). The only new spend is the judge's own accuracy pass (section 4), a separate development
reading.

A stated limit, not a hidden one: wiring the check into the pipeline's end (so a review run calls it by
itself) WOULD touch `scripts/pipeline.py`, a bound runtime file, and so a re-seal of every later bundle. It is
not done here; for the alpha the check runs as a post step on a run folder (by hand, by the desk or on the
instance after the run), and the wiring is a separate decision after the alpha measurements.

### 1.3 Design under WORDS-A, CHOICE-A, JUDGE-AGENT-A and HONEST-OUTPUT-A

- Python locates the changed spans by structure only: both texts are split into sentences by the project's
  one splitter (`passage_pairs.passages_read`, sentence ends by form); a sentence standing in both texts is no
  change; the leftovers are paired by word similarity (`version_changes._paired`, ties refused, the same rule
  as VERSION-CHANGES-A), giving changed, removed and added sentences; inside a changed pair the removed and
  added words are listed by `difflib` (structure, no meaning). No keyword table: nothing in code reads what a
  word means.
- The meaning decision goes to the registered JUDGE agent as narrow fixed-answer questions decided from its
  probabilities (CHOICE-A, `choice_decision.decide`), one question per change kind and change: the change
  (SOURCE TEXT, PROPOSED TEXT) and one statement (the kind, written in `tools/diff_check.json`, the
  operator's four kinds of D-847), answers Yes, No, Unclear. One question per kind, not one question over
  four kinds, because one change can be two kinds at once (a dropped condition that also widens the scope).
- The red line (D-848): for each red line of the advised party, one more question on each changed or added
  proposed sentence: the statement "the proposed text breaks this red line of party P: <quote>". The red
  lines come from declared sources only, read by the negotiation advisor's one reader
  `neg_advisor.party_red_lines` (merged by the round 2 lane at 9b6e0400; `diff_check.red_lines_from_item`
  calls it): the party's red-line positions on the record (`persona.red_lines`, its own positions only) and
  the operator's red lines (#278, `persona.operator_red_lines`, from `neg_advisor.py rebuild
  --operator-red-lines`). Outside a negotiation item (an amendment, a version change, the accuracy set) the
  input is a declared list `[{party, quote}]` (`diff_check.declared_red_lines`), nothing read from words.
- Quote check: the judge writes no text. Every quote on a record is Python's span, and before a record is
  kept Python checks that each quoted span stands, as written, in the source or proposed text it names
  (and a red line's quote in its declared source); a span that does not is refused on the record.
- The question form is byte-compatible with `doc_judge.py`'s choice `pair` form (passage_a the statement,
  passage_b the change), so the accuracy pass rides the existing replay with no bound controller file
  changed.
- Default: OFF (`enabled: false`) and no threshold. Proposed: keep it off in the alpha's measured runs, run
  the accuracy pass (section 4), set the threshold from its probabilities with the error rate beside it
  (CHOICE-A), and only then let the operator switch it on for the alpha user path (a change to
  `tools/diff_check.json` alone, no re-seal). Switching it on before a threshold exists would show only
  "cannot be settled" lines.

## 2. What was built

- `tools/diff_check.py`: `align` (sentence alignment), `amendment_pairs`, `version_change_pairs`,
  `negotiation_pairs` and `red_lines_from_item` (collectors), `questions`, `check` (the judge injected:
  `judge(question_text, answers) -> choice decision`), `render_md`, `write_run` (the post step on a run
  folder), `replay_prompts` (the accuracy set as a doc_judge choice prompts file) and a CLI.
- `tools/diff_check.json`: switch, similarity threshold, kinds and their statements, the red-line statement,
  the template and answers, the threshold (`null` as built, 0.999 since D-855), the JUDGE model group of the
  replay.
- `benchmark/fixtures/diff_check_309/accuracy_set.json`: the accuracy set (section 3), expected kinds
  declared before any run.
- `tools/diff_check_checks.py` and gate check 689.

## 3. The accuracy set

`benchmark/fixtures/diff_check_309/accuracy_set.json`, 24 pairs written by the lane from synthetic clause
text (no real agreement quoted): 5 per change kind, 2 red-line pairs and 2 no-change pairs (one a pure
rewording, one an identical text with a new sentence of no legal effect). Each pair declares
`expected` (the kinds that must be flagged) before any run. A pair is scored per kind question: a flag is a
settled Yes. The set is development material, never a bar reading.

## 4. The held launch

`external/s05/DIFF309_ACC` (outside the repository, main checkout): the replay prompts file built from the
set by `tools/diff_check.py replay`, one exposed replay bundle on one A10, held on LEAD_GO.txt, armed by
renaming `chain.json.ready`, bound to c09ba309. Forecast by tools/loop/step_cost.py (A10 1.29 USD an hour,
x1.3): seal 25 min 0.70 USD; pass 30 min 0.84 USD with the asset copy (94 min 2.63 USD without); 1.54 USD in all,
each step under the 5 USD pre-approval; no Claude usage on the instance. Open before a request: the bound worktree
and LEAD_GO.txt (launch.py preflight lists both). Scoring after the pass: `tools/diff_check.py score` (no model).

## 5. Accuracy pass and threshold (D-855)

The pass ran on 20 November 2026, 15:54 to 16:30 (seal 0.473 USD, pass 0.323 USD): 98 CHOICE-A questions to
the JUDGE agent's model, all 98 answered. With `threshold: null` every decision was `cannot be settled`, so
the tool as built flagged nothing (`external/s05/DIFF309_ACC/DIFF309_SCORES.json`). The sweep reads the saved
probabilities again with no model (`DIFF309_SWEEP.json`; a pair is flagged for a kind when any of its changes
has P(yes) at or above the threshold); 22 real changes and 68 clean questions:

| Threshold | Real changes flagged (of 22) | False flags (of 68 clean) |
|---|---|---|
| 0.5 | 20 | 22 |
| 0.9 | 20 | 14 |
| 0.99 | 20 | 7 |
| 0.999 | 20 | 2 |
| 0.9995 | 18 | 2 |
| 0.9999 | 16 | 1 |
| 0.99999 | 13 | 0 |

Rows up to 0.999 are in `DIFF309_SWEEP.json`; the three higher rows are the lead's reading of the same saved
probabilities recorded in D-855.

Chosen (D-855): 0.999, written to `tools/diff_check.json` `threshold`. Recall 20 of 22, false flags 2 of 68
(2.9 percent). Misses at 0.999 by kind: widened_scope 2 of 6; dropped_condition, one_way_ban,
obligation_to_statement and red_line none. False flags at 0.999: dropped_condition 1, obligation_to_statement 1.

Caveat: the threshold is read in-sample, on the lane's own 24-pair accuracy set that the same figures are
counted on, so the figures above overstate what an unseen text would give. It is a development threshold,
never a bar, and every report that quotes it says so. The switch stays off (`enabled: false`); the check stays
additive, marked as a model's and never promoted; the pipeline does not call it (OPEN_ITEMS 179).
