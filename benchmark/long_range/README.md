# Long-range corpus

Tests from generator family 5 (regulation-style provisions) in its long-range layout,
generated from the fixed seeds in `SEEDS.json`, for scoring a candidate finder on one
question: is the related unit in the candidate set? (S3 item 12, used by S6c.)

## The layout

Every provision belongs to a track, `Ordinary` or `Expedited` (a `Track` line, or a
`Procedure` line on a unit written in other words, below). The
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

Two of the six deciding units (seeded, about a third) are written in other words: they
name their track as a procedure (`Procedure: Standard` for the `Ordinary` track,
`Procedure: Accelerated` for `Expedited`), and their figure as a `Period allowed` (a
window length) or a `Charge range (EUR)` column (a fee range). The reference file says
so in two sentences with no figure. Such a unit matches its uses on neither the deciding
label nor the `Track` line; `deciding_units_in_other_words` in the key gives the count.

## What holds, in every bundle (the test, its twin and the four probes)

The generator's validator checks each of these on the written files (D-042, revised in
S3 checker round 2):

- Every planted flaw is decided by a figure stated ONLY in its related unit: a window
  definition's `Window length` (or `Period allowed`), or a fee table's range for the
  use's class. The
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
- Four baselines that read no figure score below 1 (the share of planted entries whose
  related unit they find): the first 4 units, or the first k (k the number of distinct
  related units in the test); the nearest unit carrying the deciding label
  (`Window length` for a window, the `Fee range` column for a fee); the first unit
  carrying it; and the **track-and-term** baseline, the nearest unit that states the
  term the use's provision type needs (a `Defined term` of `Notice window` for a filing,
  `Answer window` for a reply, a `Provision type` of `Fee table` for a fee) with the
  use's own `Track` value. `decided_by_label` and `decided_by_term` in the key name what
  they look for. The track-and-term baseline finds every deciding unit written in the
  plain words and none written in other words, so it scores below 1 because at least one
  planted entry is decided by a unit written in other words; S6c reports against it.
  Over every bundle of the committed seeds and the gate's fixed seed it scores 0.545 to
  0.818 (the others: first 4 and first k 0 to 0.273, nearest label 0 to 0.364, first
  label 0.182 to 0.455). `py -3.12 scripts/generator_checks.py --baselines` prints every
  bundle's scores and the range.

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
