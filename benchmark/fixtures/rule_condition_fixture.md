# Rule-condition fixture (DECLARED FIXTURE, not a corpus)

This file is a FIXTURE and is not a corpus. It exists because no corpus on disk
holds a rule-to-rule condition, and adding one quietly to a real corpus would
change a measurement corpus to make a mechanism testable, which is the opposite
of measuring.

## What it represents, and why this shape

The field half of `[unless: ...]` has a real working case: CONV-D01 in
`benchmark/corpora/device_log_review/conventions/device_conventions.md` says a
reading must fall inside its class band "UNLESS a locally adjusted range for that
device's batch or rack has been stated in the entry immediately before it or in
the same entry". That is an operator's own exception, already written, that the
system discarded.

The rule half has no such case. So this fixture models the same shape one level
up: a general rule, and a second rule that suspends it. It is written the way an
operator would write it, in the same heading syntax, so what the parser is tested
against is what an operator would actually produce rather than a synthetic
construction shaped to pass.

The pairing is deliberately the one the device corpus would need if the operator
ever wrote it: a band rule, and an exemption to that band rule for a stated
condition. That is why it represents the real case and not merely a valid parse.

## The rules

## CONV-F01 , conv-band-standard [required] [conformance] [scope: reading]

Every entry stating a reading must fall inside the standard tolerance band,
20 to 60 units.

## CONV-F02 , conv-band-exempt [required] [conformance] [scope: reading] [unless: conv-f01]

An entry carrying a batch exemption is not assessed against the standard band.
This rule is suspended when CONV-F01 does not apply, since an exemption to a
rule that is not in force decides nothing.

## CONV-F03 , conv-field-condition [required] [conformance] [scope: reading] [unless: locally adjusted range]

A reading is assessed against the standard band unless the entry states a
locally adjusted range. This is the FIELD half, in the same syntax, so one file
exercises both target kinds and shows that the parser tells them apart from what
is written rather than from a second declaration form.
