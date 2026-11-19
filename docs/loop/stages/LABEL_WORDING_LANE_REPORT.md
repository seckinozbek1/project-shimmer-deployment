# Label wording reader lane (role A, 19 November 2026)

Branch `lane/label-wording-reader`, fix commit `10008109` (full id in the launch template). Built from code and
invented fixtures only; no label, reply, sheet or confidence value was read.

## What changed

- `tools/neg_synth_label.py`: `read_answer` reads `wording` through `read_wording`, form only (WORDS-A,
  ANSWER-FORM-A), against the chosen article's own bracketed wordings. After `af.match` (`whole`, 1..n): a whole
  number bare or in one matched pair of marks (`[2]`, `(2)`, `<2>`) is read; above n it is refused
  `wording:number_above_article`; a value whose `af.key` equals exactly one span's key (with or without the
  article's own `[...]`) is read as that span's number; several spans, or a number and a quote that disagree:
  `wording:quote_ambiguous`; a value that only overlaps a span: `wording:quote_not_exact`. Everything else unchanged.
- `read-pass` refuses any output that exists (`refuse_existing`), so a second reading needs new names.
- `tools/neg_synth_review.py`: `labels_<set>_r<k>.json` is read as `<set>` (before, `labels_dev_1_r2.json` would
  have matched no set and been silently empty); a labels file naming no sheets set, or two of one set, is refused.
- Secondary defect recorded, not changed: `declared_answers` uses the sheet-wide `most`. The set is fixed at
  build time, before the model names its article, and the bound pass module takes one flat list per field; a
  per-article set needs a re-seal and a new paid pass, and changing it alone would break re-reading the saved pass.
  It affects the confidence record only, never a label.

## Proofs (each neutralise, fail, restore, pass)

- `py -3.12 -X utf8 tools/neg_synth_label_pass_checks.py`: PASS 13 proofs (check 520; new: wording_quote_exact,
  wording_quote_ambiguous, wording_quote_not_exact, wording_marked_number, wording_number_above_article,
  reread_quotes, reread_new_names).
- `py -3.12 -X utf8 tools/neg_synth_review_checks.py`: 522 PASS 2, 523 PASS 7 (new: reading_tag), 524 PASS 2.
- `py -3.12 -X utf8 -m unittest neg_synth_checks` (from tools/): 26 tests OK.
- The launch template's `reread` step was run on an invented fixture with every path patched into a temporary
  folder: pilot 11 to 26 of 26 labelled, dev 10 to 17 of 17, hand-back identical in both folders, a second run
  refused on every existing output.

## Launch template (not a git file)

`_xfer/lead_to_V/syn_label/V_SYNLAB1/`: `launch.py.pre_reread` (byte copy), `wording_probe.py` (the diagnosis
probe, verbatim), and a new step `reread` (existing steps unchanged). It probes each set with the code at COMMIT
(before) and COMMIT_R2 (after), runs read-pass into `labels_<set>_r2.json` / `LABELLER_<set>_r2.json`,
`neg_synth_review.py read` into `review_counts_r2.json` and `reviewed_r2/`, and writes `V_SYNLAB1_HANDBACK_R2.json`
(counts only) to V_to_lead and V_to_S. No model, no Lambda, no spend.

## Commands role V's request must allow

With `<WT>` role V's review-provenance worktree, `<B>` the bundle `_xfer/lead_to_V/label_wording_reader.bundle`
the lead writes, `<WT2>` the new worktree `.claude/worktrees/label-wording-reader` (exact text in the step's
docstring):

    git -C <WT> bundle verify <B>
    git -C <WT> fetch <B> lane/label-wording-reader
    git -C <WT> worktree add --detach <WT2> 100081094b8ed2f1a277b5e6c4a1a44d26e902c0
    py -3.12 -X utf8 launch.py reread        (from the launch folder)

## Seal-bound files

None. `tools/neg_synth_label.py`, `tools/neg_synth_review.py` and the checks are not in the sealer's
CONTROL_FILES; `benchmark/baselines/neg_synth_label_pass.py`, the template and `render` are untouched, so the
prompts digest holds and read-pass accepts the saved pass.
