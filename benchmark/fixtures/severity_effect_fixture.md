# Severity effect fixture

DECLARED FIXTURE, not a corpus. It exists because the shipped corpus cannot
prove this behaviour: all eight of its rules declare `required`, so a hardcoded
`"required"` at the amendment site is indistinguishable from the real value on
every rule that exists. That is precisely how the defect survived (see
docs/fix/READING_NOT_EFFECT.md).

Checked before writing this, rather than assumed: no rule in the real device
corpus ought to be advisory. Two rules (CONV-003, CONV-008) classify as
`advisory` from their PROSE, because the keyword table finds no must/shall in
them, and both are genuinely `required` (a validity rule and a prohibition on
reviewer speculation). The heading brackets are right and the prose classifier
is wrong. Nothing in the real corpus was changed to make a test pass.

## CONV-S01 , conv-s01 [required]

A reading outside the adjacent range is an irregularity. State the reading, the
range, and the difference.

## CONV-S02 , conv-s02 [advisory]

A reading may be accompanied by the ambient temperature where the operator
considers it relevant. Consider noting it when the reading sits near a band
edge.

## CONV-S03 , conv-s03 [recommended]

A calibration date should be recorded for each entry.
