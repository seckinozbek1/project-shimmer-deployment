# Constrained labeller lane (D-799, 19 November 2026)

Branch `lane/label-constrained`, from `lead/night-20261119` at `5a5246ad`; code commit `96daf6c3`. Built from code
and invented fixtures only: no label, reply, sheet, benchmark key or role folder was read, no model loaded, nothing
sealed, launched, merged or pushed.

## In one sentence (for the operator)

While the labeller writes its answer, every next piece of text that would leave the one allowed answer form (the
four fields in order, each holding only one of its declared values, the wording only `whole` or a number up to the
chosen article's own count) is given zero probability, so the model cannot write anything else.

## What changed

- `benchmark/baselines/neg_synth_label_pass.py` (BOUND, in the sealed project archive):
  - New prompts file schema `neg-synth-label-pass-v2`; `SCHEMAS` admits v1 and v2. A v2 prompt carries one more
    key, `constraint` (`neg-synth-label-constraint-v1`: key order, article ids, stances, firm-limit values, and
    `wording: {whole, per_article: {article id: n}}`), checked by `check_constraint` against the prompt's declared
    answers. A v1 file is checked against the old key set, unchanged.
  - `LabelGrammar`: the language `{"article": "<id>", "wording": "<whole or 1..n of that article>", "stance":
    "<declared>", "firm_limit": "<declared>"}`, keys, order, `": "` and `", "` forced, nothing before or after; the
    wording list chosen from the article already decoded. It has DECODING-B's grammar interface, so the existing
    `scripts/contract_decoding.ContractProcessor` (unchanged) runs it as the one logits processor: tokens leaving
    the language set to -inf, the stop token admitted only once the object closes, interventions and dead ends
    counted.
  - `hf_generate` now loads and calls `make_generate(model, tok, decoding)`. v1 prompts: the same call as the first
    pass. v2 prompts: the processor beside the declared greedy values (read from the prompts file at call time;
    nothing typed), `output_logits=True` so the confidence record (`field_decisions`) still reads the model's raw
    logits, its wording answers narrowed to the decoded article's own list (`constrained_answers`).
  - `run`: each v2 reply's `outcome` decided in Python (`inside`, `dead_end`, `at_allowance`, `unfinished`,
    `left_language`); per row `constraint_outcome`, per reply record `decoding_constraint`, and in
    `replay_measurement.json` `constraint: {by_reason, outside, interventions}` plus `prompts_schema`
    (measurement schema unchanged). No reply is read there.
- `tools/neg_synth_label.py`: `constraint_of` builds the block (per-article counts by the same `_wordings` the
  reader uses; firm limit both values for the persona's statements, the false-mapped value for others);
  `build_pass` adds it, so build-pass now writes v2. `declared_answers` and `read_answer` unchanged. `read-pass`
  adds `constraint_by_reason` per set to its record and printed counts (None for a v1 pass).
- `tools/neg_synth_label_pass_checks.py` (check 520): fakes take `constraint=None`; four new proofs.
- `scripts/verify_session1.py`: check 520 docstring only. `docs/CLAUDE_REFERENCE.md` NEG-SYNTH-A: one paragraph.

## Bound files touched (re-seal needed)

- `benchmark/baselines/neg_synth_label_pass.py` changed; it now also imports `scripts/contract_decoding.py`
  (unchanged, already in the archive) and `transformers.LogitsProcessorList` (pinned 4.51.3 has it and
  `output_logits`).
- `scripts/verify_session1.py`, `tools/neg_synth_label.py` changed (archive members; the laptop side builds v2).
- Every bundle sealed before this commit must be re-sealed for the D-799 pass; the prompts file must be rebuilt
  with `build-pass` (v2). The saved first pass's v1 prompts file stays readable by `read-pass` as before.

## Proofs (each neutralise, fail, restore, pass; no model, no download)

- `py -3.12 -X utf8 tools/neg_synth_label_pass_checks.py 520` (with `KMP_DUPLICATE_LIB_OK=TRUE`): PASS 17 proofs.
  New: `constraint_impossible` (a fake model preferring a partial quote, a changed quote, free text, or prose around
  the object: refused by the reader unconstrained; under the constraint every reply inside the language and read,
  interventions counted; 20 random-score models all inside and read; neutralised: processor leaves scores
  unmasked), `per_article_count` (A1 has 3 wordings, A2 none, A3 five: wanting A1 "5" or A2 "2" gives a value of
  that article's own list; A1 "3" untouched; confidence answers per article; neutralised: sheet-wide list),
  `old_file_read` (a v1 file checked, run with the old two-argument generate, read again with kappa 1, no
  constraint recorded; neutralised: v2 only), `outside_counted` (fenced, cut at allowance, dead end counted
  1/1/1 in the measurement and per set; neutralised: all called inside).
- Check functions through the gate module, not the whole gate:
  `py -3.12 -X utf8 -c "import sys; sys.path[:0]=['scripts','tools']; import verify_session1 as v; print(v.check_520_role_v_labelling_rides_the_replay_pass_and_is_read_from_evidence()); print(v.check_522_the_labeller_confidence_is_read_at_the_deciding_token())"`:
  520 PASS 17, 522 PASS 2.
- `py -3.12 -X utf8 tools/neg_synth_review_checks.py`: 522 PASS 2, 523 PASS 7, 524 PASS 2.
- `py -3.12 -X utf8 -m unittest neg_synth_checks` (from tools/): 26 tests OK.

## Open points for the lead

- On the real OLMo tokenizer a character the vocabulary cannot spell after a given prefix would be a dead end; it
  is counted `dead_end`, never read. The fake tokenizer cannot show this; the first constrained pass's
  `constraint.by_reason` will.
- The prompt text and template are unchanged, so the model still reads "the number of the bracketed wording";
  under the constraint it can only write `whole` or a number.
