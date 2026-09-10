# STEP W1 REPORT: the measurement corpus

## Scorer compatibility, checked before building

`tools/score_corpus.py`'s `score()` function reads a corpus's `answer_key.json` with two
lists, `planted` (units the pipeline should flag) and `clean` (units an amendment against is
a false positive), and scores ONE run's `deliverables/*/review_data.json` and
`logs/agent_bus.jsonl` against it. No changes were needed to `tools/score_corpus.py`: the
corpus below (`device_log_review`) uses this exact shape, confirmed by a real dry run of the
scorer against a synthetic fixture before any real pipeline run (see "Dry-run verification"
below). No second scorer was written.

## A real design ambiguity found and resolved

The operator's own three flaw kinds include "a provision that reads wrong alone but is sound
because the provision immediately before it creates an exception." The scorer's `planted`
list means "the pipeline should find this as a violation." For a flaw that is genuinely
sound once its neighbor is read, the CORRECT pipeline behavior is to find NOTHING there;
putting it in `planted` would score the pipeline as correct only if it incorrectly flags a
sound entry, which inverts what "correct" means for that half of the design.

Flagged to the operator before proceeding (this chain's own C5 rule: "where a choice needs
the operator's authority, stop the step"). Decision: move these three (`UNIT-BIRCH`,
`UNIT-HOLLY`, `UNIT-DAMSON`) out of `planted` into a `precision_test` key, a human-readable
label the scorer does not read directly; they still fall through to the scorer's existing
`false_pos` computation correctly (`false_pos` is defined as "any amendment not against a
planted unit," so removing them from `planted` is sufficient on its own, no scorer change
needed for this either). The other three neighbor-dependent flaws (reads sound alone,
contradicted by the entry after) fit `planted` cleanly with no ambiguity, since the pipeline
genuinely should flag them.

## The corpus: `device_log_review` (flawed) and `device_log_review_clean` (clean twin)

Domain: a fleet monitoring device log (technical/industrial, neutral per S5). No legal,
agricultural, medical or financial vocabulary; checked by direct scan against a domain-term
list, one incidental hit ("diagnosis," in a no-speculation rule about equipment diagnosis, the
same construction the existing `clinical_reference` corpus's own no-diagnosis rule uses for a
different domain, not a leak). Person names used (T. Okoye, R. Vance) are individual staff
names, not organisation names.

`benchmark/corpora/device_log_review/`:
- `context/device_log_flawed.md`: 18 device entries plus a glossary unit (19 units total,
  confirmed by running `pairing_map.split_units()` directly, `u01` through `u19`).
- `context/device_class_reference.md`: reference material (standard tolerance bands per
  device class, the calibration-authority rule), separate from the glossary embedded in the
  document itself (the glossary is intra-document by design, since the long-range test is
  specifically "a term defined near the start... used near the end" of the SAME document).
- `conventions/device_conventions.md`: 8 rules (`CONV-D01` through `CONV-D08`).
- `answer_key.json`.

`benchmark/corpora/device_log_review_clean/`: the clean twin, same conventions and reference
material, `context/device_log_clean.md` with every flaw repaired and nothing else changed, its
own `answer_key.json` with an empty `planted` list and all 18 entries in `clean`.

### The 12 planted flaws, verified by construction (not intuition), each with a short Python check before writing the key

**Neighbor-dependent, reads sound alone but contradicted by the neighbor after (3, in `planted`):**
- `UNIT-ELDER` (depends on `UNIT-FIRTH`): 47 units, no note; `FIRTH` states the device was
  re-read and returned 71, the 47 was a transcription error. `CONV-D06`.
- `UNIT-IVY` (depends on `UNIT-JUNIPER`): 45 units, in band; `JUNIPER` states the sensor was
  flagged faulty 3 hours before this reading. `CONV-D06`.
- `UNIT-LARCH` (depends on `UNIT-MAPLE`): 44 units, signed; `MAPLE` states the device was
  decommissioned 2 days before this entry's log date. `CONV-D06`.

**Neighbor-dependent, reads wrong alone but sound with the neighbor before (3, in `precision_test`, scored as false-positive risk via the existing `clean`-adjacent mechanism):**
- `UNIT-BIRCH` (depends on `UNIT-ALDER`): 65 units, outside the standard Class-B band
  (20-60), but `ALDER` states a widened batch band (20-68) that 65 falls inside. Verified: 65
  is outside 20-60, inside 20-68.
- `UNIT-HOLLY` (depends on `UNIT-GORSE`): 128 units, outside the standard Class-C band
  (70-110), but `GORSE` states a locally adjusted rack range (90-130) that 128 falls inside.
  Verified: 128 is outside 70-110, inside 90-130.
- `UNIT-DAMSON` (depends on `UNIT-CEDAR`): no signature field, which would look missing for a
  signed class, but `CEDAR` states the signature field applies only to Class-A, and `DAMSON`
  is Class-B. Verified: `DAMSON`'s own `Class:` field reads Class-B.

**Long-range, glossary (unit `u01`) conflicts with a distant unit (3, in `planted`):**
- `UNIT-TEASEL` (16 of 19 units from the glossary): fault logged 2026-06-01 09:00,
  acknowledged 2026-06-03 09:00, a 48-hour gap against the glossary's stated 24-hour fault
  window. Verified with `datetime` arithmetic: gap = 48.0 hours.
- `UNIT-VETCH` (18 of 19 units from the glossary, the last unit in the document): calibration
  visits 2026-01-01 and 2026-06-01, a 151-day gap against the glossary's stated 90-day
  service interval. Verified: gap = 151 days.
- `UNIT-SPRUCE` (16 of 19 units from the glossary): signed by "R. Vance, engineering lead,"
  no certificate stated, against the glossary's rule that only a technician holding a current
  calibration certificate may sign a calibration record as complete.

**Self-contained, visible in one unit alone (3, in `planted`):**
- `UNIT-OAK`: states a reading of 39 units and, in the same entry, a note that a recheck
  found 52, superseding it. Two values for the same field within one unit.
- `UNIT-PINE`: Class-A sensor, no calibration authority signature field at all. `CONV-D02`
  requires it for Class-A. Visible from `PINE` alone against the rule.
- `UNIT-ROWAN`: states a reading of 61 units and, in the same entry, a note claiming it is
  within the standard band, 20 to 60. 61 is outside the range its own note claims.

### The clean twin, verified by construction

Every flaw above repaired in `device_log_clean.md`: `BIRCH` to 45 (in band regardless of
which band applies), `HOLLY` to 105 (in both the standard and the locally adjusted Class-C
band), `DAMSON` unchanged (already correctly exempt), `ELDER`/`FIRTH` both given real,
non-contradictory readings, `IVY`/`JUNIPER` both given real, valid readings with no
invalidation note, `LARCH`/`MAPLE` both given real, valid readings with no decommission note,
`OAK` reduced to a single value (52, no contradiction), `PINE` given the required signature,
`ROWAN` corrected to 51 (matching its own claimed band), `SPRUCE` signed by a qualifying
authority (T. Okoye, certificate current), `TEASEL`'s gap reduced to 9 hours (within 24),
`VETCH`'s gap reduced to 73 days (within 90). Every value checked with the same arithmetic
used to verify the flawed document's own planted defects.

### Dry-run verification (before any real pipeline run)

Two synthetic fixtures (hand-built `review_data.json`, no model call) run through the real,
unmodified `tools/score_corpus.py`:

1. Against `device_log_review`: 8 of the 9 `planted` entries marked found (one deliberate
   miss), one deliberate false positive on `UNIT-ALDER`. Scorer output: `recall: 8/9`,
   `false positives: 1`, `distractor hits: 1`, `attribution: 8 of 8`, matching the deliberate
   fixture exactly.
2. Against `device_log_review_clean`: zero amendments. Scorer output: `recall: 0/0` (no
   crash), `false positives: 0`, `distractor hits: 0`.

Both fixtures deleted after the dry run; nothing from this step remains outside the corpus
files and this report.

## Corpus size, recorded for W6/W2

- `device_log_review` (flawed): **19 units**, **8 conventions** (corrected from an
  earlier miscount of the rule file's own heading count: `device_conventions.md` declares 8
  rules, `CONV-D01` through `CONV-D08`, confirmed by direct count).

## README updated

`README.md`'s corpus table extended with `device_log_review` (and its clean twin), including
the limitation stated plainly: this corpus and its key are self-authored by the same process
that built the pipeline fixes being measured, weaker evidence than an independently-written
corpus, included because no corpus measuring the adjacent-neighbor mechanism or the
long-range gap existed before it.

## Gate

```
PASS=193  WARN=0  SKIP=0  FAIL/ERROR=2  TOTAL=195
```

Identical to the W0 baseline. Same two pre-existing failures (checks 01, 145). check 145's
contamination probe scans `config/`, `scripts/`, `tests/` only, not `benchmark/`, so this new
corpus does not interact with it.

---

STEP W1 COMPLETE
