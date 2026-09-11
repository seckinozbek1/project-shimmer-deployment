# Review conventions: fleet monitoring log entries

Operator-authored rules for reviewing device log entries returned before filing. Each finding
must cite the convention it rests on and at least one reference into the context corpus.

The reviewer is a quality function. The review checks log entries against the fleet's own
standing rules and the entries around them. It does not decide fleet policy.

---

## CONV-D01 , conv-value-in-range [required] [conformance]

The reading stated for a device must fall inside its class's standard tolerance band, 20 to 60
units, UNLESS a locally adjusted range for that device's batch or rack has been stated in the
entry immediately before it or in the same entry. A reading outside the range that actually
applies is an irregularity. State the reading, its class, and the range it falls outside.

## CONV-D02 , conv-calibration-signature [required] [conformance] [scope: class=Class-A sensor] [requires: calibration authority signature]

Every Class-A sensor entry must state a calibration authority signature. Class-B and Class-C
sensors are self-calibrating and carry no signature field. A missing signature on a Class-A
entry is an irregularity. State which entry is missing the field.

## CONV-D03 , conv-calibration-authority [required] [conformance] [scope: calibration authority signature]

A calibration authority signature is only valid when the signing role holds a current
calibration certificate, as defined in the glossary's calibration authority entry. A signature
by any other role is not calibration-complete. State the entry, the signing role, and why it
does not qualify.

## CONV-D04 , conv-fault-window [required] [conformance] [scope: fault logged]

A device's own logged fault must be acknowledged within the standard fault window stated in
the glossary. An entry recording a longer gap between a logged fault and its acknowledgement is
an irregularity. State the two timestamps and the gap between them.

## CONV-D05 , conv-service-interval [required] [conformance] [scope: service record]

The gap between a device's two most recently logged calibration visits must not exceed the
standard service interval stated in the glossary. An entry recording a longer gap is an
irregularity. State the two dates and the gap between them.

## CONV-D06 , conv-neighbouring-entry [required] [editorial]

A finding about one entry must take into account anything the entry immediately before or
immediately after it states about the same device or the same reading. An entry that corrects,
exempts, or invalidates the entry beside it must be read together with it, not reviewed as if
it stood alone.

## CONV-D07 , conv-grounding [required] [editorial]

Every finding must cite one convention and at least one reference into the context corpus. A
finding must state the specific entry and figures it concerns. Vague findings such as "this
entry looks wrong" are not acceptable.

## CONV-D08 , conv-no-speculation [required] [editorial]

Findings record what conflicts with a stated rule or a neighbouring entry, never a guess about
equipment condition, cause of fault, or maintenance priority. Diagnosis is the fleet
engineer's task, not the reviewer's.
