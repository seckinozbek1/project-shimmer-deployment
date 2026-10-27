# Long-range corpus

Tests from generator family 5 (regulation-style provisions) in its long-range layout,
generated from the fixed seeds in `SEEDS.json`, for scoring a candidate finder on one
question: is the related unit in the candidate set? (S3 item 12, used by S6c.)

## What holds, in every bundle (the test, its twin and the four probes)

The generator's validator checks each of these on the written files (D-042):

- The four definition provisions are the first four units (`definitions_first: true`).
- Every planted flaw is decided by a figure stated ONLY in its definition: the notice
  and answer definitions state their `Window length`, the fee-class definition holds the
  `Allowed fee` for each class, and the reference file carries no figure at all. Python
  computes none of these flaws (there is no bound sentence and no reference table for
  them), so they are keyed from the generator's ground truth and found again by its own
  scanner. One exception: probe 3 (a term only in the later version) adds an earlier
  version of the document, which repeats the definitions' figures.
- Every planted entry names that definition in `related_unit` and states `distance`,
  the true number of units between the two (the difference of their positions), which
  is at least `min_distance` (12). The reordered-sections probe moves only units more
  than twelve places past the last definition, so its distances, restated in its own
  key, stay at least twelve and the definitions stay first.
- About half the uses carry a `Cross reference` line naming the definition's heading
  (`cross_reference_share` in the key, between 0.3 and 0.7), and among the planted uses
  some do and some do not (`cross_reference_line` per entry). A baseline that follows
  cross-reference lines is therefore not perfect by construction.

| Planted kind | `related_unit` |
|---|---|
| `notice_window_far`: a filing-to-notice gap over the notice window | the provision defining the notice window |
| `answer_window_far`: a receipt-to-answer gap over the answer window | the provision defining the answer window |
| `fee_above_band_far`, `fee_below_band_far`: a filing fee outside the allowed fee for its class | the provision defining the fee class |

Each test plants 11 flaws of these 4 kinds. The key has a top-level `long_range` field
describing the layout; the scorer ignores it, and it ignores `related_unit`,
`distance` and `cross_reference_line` too.

**Exposed by construction**, like the development suite: for development and
regression only.

## Regenerate

```
py -3.12 benchmark/generators/generate.py suite long_range
py -3.12 benchmark/generators/generate.py check benchmark/long_range/generated
```

`generated/` is ignored by git and by the container build, keys included.
`generated/suite_listing.json` records the input-format draft hash it was generated
against.
