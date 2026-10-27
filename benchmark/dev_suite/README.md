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
two-version review of a bundle; a multi-round run is told each term's identity by the
case manifest and writes no change records.

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

The repository scorer, `tools/score_corpus.py`, reads keys only from
`benchmark/corpora/<bundle>/` today (open item 17), so it does not score this suite
where it lies. The suite lives outside `benchmark/corpora/`, so the corpus checks
(236, 239, 241, 243, 273) do not apply to it.
