# The parser sweep (D-663, standing order 82, issue #279)

Lane parse-sweep, branch `lane/parse-sweep` (from lane/speed-lookback 2051aeba, merged with lane/neg-score-fix
cdd28544). The rule: no answer is dropped for its form alone (leading or trailing spaces, case, quotes, a number
written for a string, a list for a single value or the reverse, stray punctuation, code fences); every remaining drop
is counted with its reason, and every score report prints the drop counts. Normalisation is of form only, never of
content (WORDS-A: no fuzzy matching, no synonym table, no meaning decision).

## 1. Inventory (15 November 2026, written 18:52 to 19:10 from date)

Found with the Grep tool on scripts/, benchmark/baselines/, benchmark/adapters/ and tools/ only. Form columns:
S spaces, C case, Q surrounding quotes, N number for a string, L list for one value or the reverse, P stray
punctuation, F code fences. "yes" = tolerated, "DROP" = the answer is lost for that form, "n/a" = the form cannot
reach the parser.

### 1.1 The JSON extractors (four copies of one idea)

| Where | What it does | Fences | Prose around | Shared by |
|---|---|---|---|---|
| benchmark/baselines/bare_model.py `_without_fences`, `_last_balanced_object`, `_loads` | fence lines dropped, last balanced `{...}`, invalid backslash escapes doubled | yes | yes | bare_model, doc_judge |
| scripts/passage_pairs.py `_without_fences`, `_last_balanced_object`, `_loads` | the same, rewritten because scripts/ cannot import benchmark/ (check 324 holds the two equal) | yes | yes | passage_pairs, case_questions |
| benchmark/baselines/neg_advisor.py `_json_object` | FIRST `{` that raw-decodes to an object | yes | yes | parse_advice, parse_validate |
| scripts/agent_wrapper.py `parse_contract_output` + `_iter_balanced_json` | strict whole-reply parse after stripping a LEADING fence; then balanced candidates, first populated valid wrapper wins; `last_parse_trace` records the path | leading only on the strict path; yes in recovery | yes in recovery | every envelope agent |
| scripts/claim_classifier.py `_parse_claims_json` | leading fence stripped, first `[` to last `]` | leading only | yes | claim extraction |

Note: first object (neg_advisor) against last object (bare_model, passage_pairs) is a difference in rule between
parsers; for a reply holding an example object and then the answer, the advisor reads the example. Recorded, not
changed by the sweep without a decision (it is content position, not form).

### 1.2 Answer readers

| # | File and function | Fields read | S | C | Q | N | L | P | F | Drops counted? |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | benchmark/baselines/bare_model.py `_frozen_parse`, `_read_label`, `parse_reply` (B1; the cloud B1 label files; doc_judge's B1 path line 898) | label (evidence, reason, item_id kept) | yes | yes | DROP (`'"Entailment"'` is label_not_in_list) | DROP (`isinstance(obj.get("label"), str)` else no_label) | DROP (`["Entailment"]` is no_label) | DROP (`Entailment.`, `**Entailment**`: label_not_in_list); a `:` suffix and `(undecided)` are cut | yes | per row: `failure` in empty_reply, no_json_object, json_invalid, no_label, label_not_in_list. FROZEN parser (version 2): a tolerant reading goes in as a declared addition beside it, as `parse_truncated_label` did, never by editing `_frozen_parse` |
| 2 | benchmark/adapters/common/mapping.py `b1_class`, `normalise_b1_label` | B1 label file `label` | yes | yes | DROP | DROP | DROP | DROP | n/a | counted, one bucket `b1_parse_failures`; the parser's reason name is not carried into the count |
| 3 | benchmark/baselines/doc_judge.py `parse_reply`, `screen` | outcome, quote, reason | yes | yes | DROP | DROP (`isinstance(obj.get("outcome"), str)` else no_outcome) | DROP | DROP (`contradicts.`) | yes | per row: empty_reply, no_json_object, json_invalid, no_outcome, outcome_not_declared; screen adds the quote refusals |
| 4 | benchmark/baselines/pair_judge.py `read_calls` | through doc_judge.parse_reply | as 3 | | | | | | | as 3 |
| 5 | scripts/passage_pairs.py `read_reply` | outcome, reason | yes | yes | DROP | DROP | DROP | DROP | yes | NOT counted: returns (None, None) for every failure, no reason name |
| 6 | scripts/passage_pairs.py `read_decision` (CHOICE-A) | decided, settled | n/a | n/a | n/a | n/a | n/a | n/a | n/a | form-free by construction: the label is one of the declared answers, chosen from logits |
| 7 | benchmark/baselines/negotiation_b1.py `parse_movement` | whole reply text, one of four movement labels | yes | yes | DROP (`"toward"`) | n/a | n/a | one trailing `.` only; DROP `toward,` `**toward**` `toward!` | DROP (fenced word, or `{"movement": "toward"}`) | NOT counted with a reason: NO_ANSWER only |
| 8 | scripts/case_questions.py `_answer_in` | whole reply or object `answer` | yes | yes on the bare text; DROP inside the object (`answer in options`, case-sensitive) | strips `"` and `.` at the ends | n/a | DROP | only `.` and `"` | yes (object path) | NOT counted: None |
| 9 | scripts/case_questions.py `_read_decision` | answer, settled, confidence | n/a | exact `answer in options` | | | | | | None, no reason |
| 10 | scripts/case_questions.py `read_suggestion` | suggested_wording, why, cites, quote | wording stripped | | | | | | yes | counted with names: not_an_object, wording_missing_or_too_long, reason_missing_or_too_long, citation_not_given, quote_missing ... |
| 11 | benchmark/baselines/neg_advisor.py `parse_advice` | proposals[].id/conflict/stance/wording/reasons, trades, approach, alignment, state, game deal | ids: DROP (`" A1"`) | ids: DROP; enums (conflict, stance, state): DROP (`"Bracketed"`) | enums DROP | ids: yes since cdd28544 (`_one_id`); reasons yes (`_ids`) | DROP (`"state": ["closed"]`, a single id where a list is asked is read as no list) | enums DROP (`closed.`) | yes | unknown ids counted, one total `unknown_ids`, no reason per kind; an enum outside its values is left out SILENTLY and scores no_answer |
| 12 | neg_advisor.py `parse_audit` | first line, audit label | yes | yes | DROP | n/a | n/a | `.` only (to a space) | DROP | None, no reason |
| 13 | neg_advisor.py `parse_judge` | leading digit 0, 1, 2 | yes | n/a | DROP (`"2"`) | n/a | n/a | DROP (`**2**`, `Grade: 2`) | DROP | None, no reason |
| 14 | neg_advisor.py `parse_validate` | article, proposal, stance | n/a | stance DROP | | DROP both ways: `article` must be str (an int is dropped), `proposal` must be int (`"3"` is dropped) | | | yes | None, no reason |
| 15 | tools/score_neg_advisor.py (M1 to M3, checker fields) | parsed rows | | | | | | | | no_answer counted per arm; the reason of each no_answer is not reported |
| 16 | tools/score_negotiation.py `reply_answers`, `system_label` | label (from 7), Python gap outcome | | | | | | | | `label if label in LABELS else NO_ANSWER`; no_answer counted, no reason |
| 17 | scripts/agent_wrapper.py `parse_contract_output` (envelope, INFRA-037) | agent, doc_id, items[] | yes | | | | | | leading only, strict path; trailing text after a fence goes to recovery | reason list (`missing`) and `last_parse_trace` on the bus |
| 18 | agent_wrapper.py compact path (`_compact_contract`) | the compact producer response | yes (json) | | | | | | DROP (`Complete compact JSON response required`) | named reason. Under DECODING-B the local constrained producer cannot emit a fence; an unconstrained path (cloud, constraint off) loses the whole reply for a fence |
| 19 | agent_wrapper.py `normalize_core_aliases`, `core_field_value` (ENVELOPE-A) | aliased `confidence` | yes | yes | DROP | bool yes | DROP | DROP | | recorded in `last_contract_normalizations` |
| 20 | scripts/multi_round.py:173, scripts/multi_round_phase.py:395, scripts/strategic_support.py:45 and :112 | confidence, state | DROP | DROP (`confidence in {"CONFIDENT","UNCERTAIN"}` exact; `"confident"` refuses the record) | DROP | | | DROP | | refused with a named `require` reason |
| 21 | scripts/pipeline.py `_confidence_value` | confidence | yes | yes | n/a | yes (numeric string) | | | | unknown read as 1.0, not counted |
| 22 | scripts/auditor_pairs.py `compare` | VERIFIER items[].finding, status | | DROP (`item.get('finding') in RELATIONS`, exact upper case) | DROP | | | DROP (`MATCH.`) | via parsed | contract failures named (reply_not_object, items_not_list, item_not_object); a relation outside RELATIONS is written as `verifier_relation` but not comparable, not counted as a drop |
| 23 | scripts/claim_classifier.py `_parse_claims_json` | claims[].text/type/entities | text stripped | | | type `str()` | DROP (an object where a list is asked returns []) | | leading only | NOT counted: [] for every failure, items without `text` skipped silently |
| 24 | benchmark/baselines/judge_read.py `answer` | record_verdict, verdict | yes | yes | DROP | | | DROP | n/a | None, no reason |
| 25 | benchmark/adapters/common/mapping.py `verdict`, `is_refusal` | record_verdict, uncertain flag | yes | yes (casefold) | | | | | n/a | these read Python-stamped records (WRITTEN-BY-A); out of the sweep's reach except as noted |
| 26 | benchmark/baselines/vllm_replay.py `labels`, `pairs_of` | per item label field, as `json.dumps` | | DROP as a disagreement (`"MATCH"` and `"match"` differ) | | | | | | `<unparsed>`, `<absent>` counted. Replay agreement measures identity of two outputs, so exactness may be intended: decision needed |
| 27 | benchmark/baselines/choice_read.py, scripts/agent_wrapper.py `call_choice`, scripts/choice_decision.py | decision over declared answers | n/a | n/a | n/a | n/a | n/a | n/a | n/a | form-free by construction (CHOICE-A); refusals named (`choice_refused`) |
| 28 | scripts/semantic_ensemble.py `vote_*`, `decide` | no model text (embeddings, tf-idf, overlap) | | | | | | | | out of scope |
| 29 | benchmark/baselines/instruction_opt.py `read_proposals` | text between `<<<` and `>>>` | | | | | | | | proposer text, not an answer scored against a key; out of scope |

Read and found not to parse a model answer (they read their own records, tables or keys, or Python-computed rows):
auditor_read.py, producer_score.py, gate_score.py (delegates to the adapters), judge_success.py,
judge_calibration.py, fresh_test.py, fresh_once.py, either_test.py, system_test.py (all through choice_read),
cloud_reference.py `read_reply` (text and stop reason only; the labels go through 1), cloud_reference_b1.py,
tools/score_case_movement.py, tools/score_corpus.py (Python-written findings and amendments; its unit matching is
substring-on-lowercase), tools/judged_rescreen.py. scripts/chat.py `extract_json` is the interactive chat, not scored.

### 1.3 Added to the inventory (lead 18:55, the capability audit D-666)

- benchmark/baselines/choice_judge.py `decisions`: the decision a reply record saved (CHOICE-A, logits over
  declared answers): form-free by construction.
- benchmark/baselines/doc_judge.py `parse_reply` and pair_judge.py `read_calls`: rows 3 and 4 above.
- scripts/convention_parser.py: reads the operator's convention files (structure only, WORDS-A), never a
  model's reply: out of scope.
- scripts/cell_selection.py `class_of`: a CHOICE-A decision, form-free. scripts/case_questions.py
  `_read_decision`: the structured return of a decide callable, never model text.
- The audit's advisor gaps (parse_audit first line and exact spelling, cannot_tell's underscore, parse_judge's
  "Grade: 2", parse_validate's "1", parse_advice's exact lowercase enums, integer reason 3 for PAR-3, all
  reasons lost on one bad item, first object against last) and case_questions `_answer_in` (case on the JSON
  path): the advisor's are read at scoring (section 3); case_questions is a bound runtime parser (section 5).

## 2. The rule as the lead set it (18:57), and where the reading lives

1. One JSON rule everywhere: the LAST top-level object of a reply that parses; a reply holding several is
   counted `several_objects_last_read` and read, never dropped.
2. vllm_replay's exact comparison stays: it is a determinism check (two passes byte for byte), not an
   answer reader.
3. Bound files are not changed now. Every file under scripts/, config/, corpus_ingest/,
   benchmark/adapters/ and benchmark/baselines/ travels in the sealed source archive
   (tools/prepare_ordinary_final_run.py RUNTIME_PREFIXES and ARCHIVE_EXTRAS; `*_checks.py`, `verify_*` and
   fixtures excepted), so a change there forces a re-seal. The tolerant reading lives in tools/, at scoring,
   on the replies every pass saved; no sealed bundle needs a re-seal for it.

The first pass of this lane (commits 8eddaa5e to e6480153) had changed bound files; commit de578403 puts
every bound file back to its text at cfcaa0b9 and moves the reading to tools/.

`tools/answer_form.py` (standard library only): `unfence`, `bare`, `key`, `integer_text`, `single`,
`as_list`, `one_value`, `match`, `match_all`, `last_object`, `leading`, `Drops`; reasons empty, not_text,
list_not_one, not_declared, ambiguous, no_json_object, json_invalid, not_an_object, duplicate, not_asked, and
the note several_objects_last_read. `tools/reread_replies.py`: the score-time re-readers.

## 3. Each reader at scoring

| Arm or reader | How a score gets it | Now read | Still dropped, counted as | Report prints | Proof |
|---|---|---|---|---|---|
| Negotiation advisor, system and B1 | `tools/reread_replies.py advisor --prompts P --run PASS --out F` | ids and enums by form, the last object, an integer reason as its one known id, one bad entry costing only itself; audit and movement-style leading answers ("Supported, because ...", "Cannot_Tell"); judge "Grade: 2", `"2"`, `**2**`; validator article as a number, proposal "1", "none" | `drops` per row by field and reason; an audited piece the run's strict parser never put to the auditor counted `not_asked` | score_neg_advisor: `drops` per arm and the judge, validation `drops`; answers not of schema neg-advisor-answers-v2 refused | neg_advisor_checks test_18d (also first object neutralised), 18e, 18f |
| Negotiation advisor, cloud | `advisor --prompts P --texts T --out F` | the same | the same | the same | the same readers |
| Negotiation movement, B1 and cloud | `tools/reread_replies.py negotiation --run PASS` or `--texts T --model-id M` | fence, quotes, emphasis, punctuation, case, the whole declared line, a leading answer with words after it | `drop` per movement row | score_negotiation: `positions.drops` per arm; answers not of schema negotiation-answers-v2 refused | negotiation_measure_checks test_09b |
| B1 labels (all benchmarks) | `tools/reread_replies.py b1 --run PASS --out NEW` | the frozen parser first; where it read no label, the last object's label by form (list of one, number, quotes, emphasis, punctuation) and the frozen label rule, marked `parse_form_read` | the frozen failure plus `parse_form_drop`; counts by reason in `b1_relabel.json`; a sensitive pass (no reply text) copied and counted `reply_not_kept` | the adapters score the new labels folder; `b1_relabel.json` carries the counts | answer_form_checks test_15 |
| The form rules | | | | | answer_form_checks test_01 to test_14 (15 proofs) |

Proofs use committed fixtures and invented replies in the dropped forms; output/runs/ here holds only
September pipeline runs. No benchmark key, answer_key.json or item was opened. Before a score: every arm's
saved replies are read again with the commands above, and each scorer's power record (bound to its
code_sha256) is made again, both scorers having changed (D-662).

## 4. Output side

**Built for Shimmer's own advisor groups (D-672, Seckin 20:07), commit 4e33a1d2:** (a) the judge's grade and
the system auditor's answer as CHOICE-A decisions over the declared `choice_answers` (threshold 0); (b) the
system's advice and the validator's mapping under a schema constraint (scripts/schema_decoding.py, the item's
ids and the declared enums). New runs only; the measurement plan is PARSE_SWEEP_DEV_MEASUREMENT.md. The
cloud and bare-model parts and (c), (d) below wait for after v1.1 (V1_1_PLAN A2).

Already tightened, no change here: the compact producer (config/contract_decoding.json) and five envelope
agents (config/envelope_decoding.json) decode under DECODING-B on transformers and vLLM; every CHOICE-A
question (passage pairs when deciding, cell selection, case questions through call_choice, choice_judge)
answers from logits over the declared answers.

Can be tightened, each a change to a bound file and a measured arm's decoding, so with the next re-seal and a
decision: (1) the advisor judge grade and audit, and the negotiation movement, as CHOICE-A over the declared
answers; (2) advisor advice and validator JSON under a DECODING-B style declaration locally and the cloud API's
structured output (a JSON schema) for the cloud arm, the prompt text unchanged; (3) the B1 label under an
enumerated-label constraint (B1-ARM-A: it changes what the baseline is); (4) the cloud reference arms' label
through structured output. Cannot be tightened: free-text fields beyond being a JSON string.

## 5. Bound runtime parsers left strict, for the change that goes with the next re-seal

| File and function | Strict on | Change to make with the re-seal |
|---|---|---|
| benchmark/baselines/bare_model.py `_frozen_parse`, `_read_label` | quotes, trailing punctuation, a list of one, a number for the label | the form reading of `reread_replies.b1_label` beside the frozen parser |
| benchmark/baselines/neg_advisor.py `_json_object` (FIRST object), `parse_advice`, `parse_audit`, `parse_judge`, `parse_validate` | the audit's list above | `reread_replies.advice`, `audit`, `judge`, `validate` |
| benchmark/baselines/negotiation_b1.py `parse_movement` | quotes, emphasis, punctuation but one point, fences, words after the answer | `reread_replies.movement` |
| benchmark/baselines/doc_judge.py `parse_reply`, pair_judge.py `read_calls`, scripts/passage_pairs.py `read_reply` | an outcome as a list or number, quotes, punctuation; passage_pairs names no reason | the outcome by form, a reason per drop (kept equal by check 324). Development measures only (DOCJUDGE-A); no scored measurement reads them now |
| benchmark/baselines/judge_read.py `answer` | verdict quotes, punctuation | the verdict by form |
| benchmark/adapters/common/mapping.py `b1_class` | one `b1_parse_failures` bucket | the failure reason per row and by reason (the relabel counts carry it until then) |
| scripts/case_questions.py `_answer_in` | the JSON path's answer compared case-sensitively ("Toward" dropped) | the option by form, its drop on the row |
| scripts/auditor_pairs.py `compare` | the VERIFIER relation exact upper case | the relation by form, `relation_drop` on the join |
| scripts/agent_wrapper.py compact path | a complete reply inside fence lines refused | fence lines dropped, still a complete response |
| scripts/claim_classifier.py `_parse_claims_json` | one object for a list, a fence not at the start | as_list and unfence; also names its model in code (`gpt-4o`), against the live-model rule |
| scripts/multi_round.py:173, multi_round_phase.py:395, strategic_support.py:45 and :112 | `confidence` and `state` exact, a whole layer refused | a form pass where producer and reviewer output becomes records (MULTI-ROUND-A) |

The first pass's versions of most of these are in this branch's history (commits 43b037b8 to 78dfcb5f) and
can be taken back with the re-seal.

### 5.1 What the merge of lane/neg-score-fix (cdd28544, merge cfcaa0b9) brought in (lead, after 19:50, item 6)

The merge brought every commit of lane/neg-score-fix not on lane/speed-lookback 2051aeba. `git cherry`
marks four of the seven as already on the lead branch under other shas (the same patch), and three as new:

| Sha | Subject | On the lead branch already? |
|---|---|---|
| 3bd20cb9 | bge-m3 loaded with the low host peak; corpus walks skip __pycache__ (#262) | yes, same patch (6a519ae1) |
| 37ae1dfa | Check 174: the advisor's terms-of-use field named through one constant under benchmark/ (#262) | yes, same patch (305429ad) |
| 68b7537c | The negotiation freeze's embedding on a rented machine: export, embed_records, --vectors (#262) | NO: new |
| 98cb597e | Advisor scorer: a game reply passes the withholding untouched (KeyError 'proposals', role N session 18) | yes, same patch (2631c7c3) |
| 4e0fcc91 | Advisor judge: the grade is the reply's leading digit 0, 1 or 2 (all 12 Phi-4 replies went on after the digit, role N session 19) | yes, same patch (30a3f232) |
| 9af437a7 | Negotiation advisor pilot: the power record for this scorer and the first opening line (k=1), before any score (D-647, #262) | NO: new |
| cdd28544 | Advisor parser: a numeric id is read as its text, as _ids reads a list (role N session 23); proof test_18c (D-661) | NO: new (the one asked for) |

The two check-file conflicts of the merge (tools/negotiation_measure_checks.py, tools/neg_advisor_checks.py)
were additions on the incoming side only (68b7537c's vectors-route tests, cdd28544's test_18c).

## 6. Notes

- Check 387 is a new gate check; the full gate goes to Lambda as arm G before any merge.
- Pre-existing failures on this laptop, the same on the lead's tree: doc_judge_checks
  test_scores_through_the_scorer (OBSERVATION_ERROR), auditor_pair_checks
  test_startup_requires_runtime_artifacts_and_contract (missing frozen producer adapter).
