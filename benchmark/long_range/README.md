# Long-range corpus

Tests from generator family 5 (regulation-style provisions) in its long-range layout,
generated from the fixed seeds in `SEEDS.json`, for scoring a candidate finder on one
question: is the related unit in the candidate set? (S3 item 12, used by S6c.)

## The layout

Every provision belongs to a track, `Ordinary` or `Expedited` (a `Track` line). The
units that decide a flaw are of two types and spread through the document among the
uses, at seeded positions:

- four window definitions, a notice window and an answer window for each track, each
  stating its `Window length`;
- two fee tables, one per track, each a table of `Fee class` and `Fee range (EUR)`.
  They are provisions of type `Fee table`, not definitions.

Two more definitions (the fee class and the appeal body) decide no flaw. So there are
six definitions for four kinds of use (filing, reply, fee, appeal), and a flaw is
decided by the deciding unit of the use's own track: the right definition among four
that carry the same label, or a fee table that is no definition at all.

## What holds, in every bundle (the test, its twin and the four probes)

The generator's validator checks each of these on the written files (D-042, revised in
S3 checker round 2):

- Every planted flaw is decided by a figure stated ONLY in its related unit: a window
  definition's `Window length`, or a fee table's range for the use's class. The
  reference file carries no figure at all. Python computes none of these flaws (no
  sentence it would read as a bound, no reference table), so they are keyed from the
  generator's ground truth and found again by its own scanner. One exception: probe 3
  (a term only in the later version) adds an earlier version of the document, which
  repeats the deciding figures.
- Every planted entry names that unit in `related_unit` and states `distance`, the
  true number of units between the two (the difference of their positions), which is
  at least `min_distance` (12). The reordered-sections probe moves blocks of units,
  retried until every distance stays at least twelve; its key states its own distances.
- `definitions_first` states whether the six definitions are the first six units; it
  is false in every bundle generated from the committed seeds.
- Among the planted entries, some related units are definitions and some are not.
- About half the uses carry a `Cross reference` line naming the related unit's heading
  (`cross_reference_share` in the key, between 0.3 and 0.7), and among the planted uses
  some do and some do not (`cross_reference_line` per entry). A baseline that follows
  cross-reference lines is therefore not perfect by construction.
- Three baselines that read no value score below 1 (the share of planted entries whose
  related unit they find): the first 4 units, or the first k (k the number of distinct
  related units in the test); the nearest unit carrying the deciding label
  (`Window length` for a window, the `Fee range` column for a fee); and the first unit
  carrying it. `decided_by_label` in the key names those labels.
  `py -3.12 scripts/generator_checks.py --baselines` prints every bundle's scores.

| Planted kind | `related_unit` |
|---|---|
| `notice_window_far`: a filing-to-notice gap over the notice window of the use's track | that track's notice-window definition |
| `answer_window_far`: a receipt-to-answer gap over the answer window of the use's track | that track's answer-window definition |
| `fee_above_band_far`, `fee_below_band_far`: a filing fee outside the range its track's fee table sets for its class | that track's fee table |

Each test plants 11 flaws of these 4 kinds, the window flaws of each kind on both
tracks. Clean distractors: a gap equal to its window, a fee on a bound, an `Ordinary`
filing whose gap the `Expedited` window would break, and an `Expedited` fee above the
`Ordinary` range for its class. The key has a top-level `long_range` field describing
the layout; the scorer ignores it, and it ignores `related_unit`, `distance` and
`cross_reference_line` too.

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
