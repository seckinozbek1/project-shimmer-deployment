# Development suite

Two tests per generator family (f1 to f6), generated from the fixed seeds in
`SEEDS.json`. Each test is six bundles: the test, its clean twin and the four
perturbation probes (see `benchmark/generators/README.md`).

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
