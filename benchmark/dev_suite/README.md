# Development suite

Two tests per generator family (f1 to f6), and four for family 4 (two with two
rounds, two with three), generated from the fixed seeds in `SEEDS.json`: fourteen
tests. Each test is six bundles: the test, its clean twin and the four perturbation
probes (see `benchmark/generators/README.md`).

Every family 4 bundle is also a declared multi-round case: `case_manifest.json` beside
its key, the live case manifest (`fixture` false) the controller seals and the pipeline
runs with `--multi-round --multi-round-manifest case_manifest.json`, and its `context/`
holds only the case documents. Its key carries the rename probes (`rename_probes`:
renamed with the value kept, renamed with the value moved, renamed and moved to another
section, withdrawn, withdrawn beside an unrelated new term in the same measure, new in
the later version, sections reordered, a value in another format), each with its
ground-truth expectation, the renamed terms in `expected_refusals`, the rounds
(`rounds`, `round_reuse`, `round_changes`), and the multi-round key (`multi_round`:
planted and clean entries scoped by `round_id` and `document_id`, every round keyed;
`docs/INPUT_FORMAT.md` section 9). The rename probes are measured in the ordinary
two-version review of a bundle (the same files run without `case_manifest.json`,
section 12 of the format); a multi-round run is told each term's identity by the case
manifest and writes no change records.

Every key states the ground truth the generator planted, never what Shimmer computes
(D-042). `generated/suite_listing.json` records the input-format draft hash the suite
was generated against.

**Exposed by construction.** The generators, the seeds and therefore every answer key
are in this repository, so anything that reads the repository can read the answers.
The suite is used only for development and regression. It is never a held-out
measurement and no result on it is evidence of recall on unseen material.

## Regenerate

```
py -3.12 benchmark/generators/generate.py suite dev
py -3.12 benchmark/generators/generate.py check benchmark/dev_suite/generated
```

The first command validates every test in memory and only then replaces
`generated/`; a failure writes nothing. `generated/` is ignored by git and by the
container build (`.gitignore`, `.dockerignore`), keys included. Regenerate after every
change to `docs/INPUT_FORMAT.md` before its freeze (S3 plan item 3).

## Scoring

The repository scorer, `tools/score_corpus.py`, scores a bundle of this suite where it
lies by its key path, and compares it with its twin by the twin's key and a run of the
twin (loop S5, R21):

```
py -3.12 -X utf8 tools/score_corpus.py --key generated/<test>/<bundle>/answer_key.json --run <run-dir> \
    --twin-key generated/<test>/<twin-bundle>/answer_key.json --twin-run <twin-run-dir>
```

It refuses a twin key that is not the one the key's `twin_of` names, and a twin run
that is not a run of the twin's document. It reads the key parts D-042 added to
`docs/INPUT_FORMAT.md` section 9: a family 4 bundle's ordinary two-version run is scored
on `prior_records`, `band_irregularities` and `expected_refusals` (by refusal kind; a
rename Python matched is no false positive), its multi-round run (a run folder holding
`audit/multi_round.json`, same command) on the key's `multi_round` entries, round by
round, and an entry of one of the four relations Python never writes is reported in a
section of its own (check 293). The
suite lives outside `benchmark/corpora/`, so the corpus checks (236, 239, 241, 243,
273) do not apply to it.
