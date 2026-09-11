# STEP D1 REPORT: longest-match labels (D, option 1)

**This fix is built without measurement. The gap is real, because it was traced in code
and in the stopped run's saved map. The fix is not known to be correct until a run scores
it. Nothing here is described as working; the worst-case reading was taken.**

## The gap

`pairing_map.needed_fields` marked a document label as named by a rule when every word of
the label appeared in the rule's text. A label that is a shorter phrase inside a longer
label the rule also names therefore counted as a second required field. On the device
corpus the glossary unit carries `calibration authority`, and the entries that carry a
signature carry `calibration authority signature`; a rule saying "calibration authority
signature" was read as requiring both, so D02 and D03 were rejected for the very entries
that carried the signature (`unit lacks calibration authority` on 14 of 19 units of run
`d5728e4b`). The same containment made "extent" a requirement of any rule mentioning
"total declared extent" wherever a table header reads "Extent".

## The fix

`needed_fields` now keeps the longest matching label only: a named label whose words are a
proper subset of another named label's words is dropped. One function, no new concept, no
domain word. The worst case, stated: a rule that genuinely needs both a label and a longer
label containing it loses the shorter one; the map's reason line would show the shorter
label missing from every pairing reason, so it is visible, not silent.

What this does NOT do: the absence case. An entry that lacks the signature is still
rejected by the rule that requires it (the reason line now names the signature alone).
That is option 2, the next commit. D04 and D05 still name glossary labels (`fault window`,
`service interval`) that no entry carries, so they still pair with nothing until option 2's
declared scope takes over from text-derived requirements.

## Proof, on fixtures (check 208)

`needed_fields` on a synthetic vocabulary: a rule naming "calibration authority signature"
needs that label and `class`, not `calibration authority`; "total declared extent" not
`extent`; a rule naming only the short label still needs it. Through the real
`build_pairing_map` on a three-unit document: the entry carrying the signature pairs, with
a reason naming the long label once; the entry without it is rejected for the signature
alone; the glossary unit, carrying only the short label, does not pair.

Neutralised, with the word-subset test restored:

```
('FAIL', "a rule naming 'calibration authority signature' must need that label and 'class'
only, not also the shorter 'calibration authority': [('calibration', 'authority'),
('calibration', 'authority', 'signature'), ('class',)]")
```

Restored: `PASS`. Every check that touches the pairing map (153, 154, 159, 162, 163, 169,
177, 179, 180, 183, 185, 189, 191, 192, 199, 206) passes unchanged.

## What a run will have to show

On the device corpus, D02 and D03 should pair with the four entries carrying a signature
(and no others), D01 and D06 unchanged, D04 and D05 still unpaired. Whether the model then
finds anything under D03 is not known.

## Gate result

```
PASS=207  WARN=0  SKIP=0  FAIL/ERROR=2  TOTAL=209
```

`output/d1_gate1.log`, run once at this HEAD. One check added (208), one more pass, WARN 0,
the same two source-only failures (checks 01 and 145).

---

STEP D1 COMPLETE (built without measurement; proved on fixtures by check 208)
