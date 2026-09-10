# Fleet Monitoring Log, Quarterly Review

Log entries returned for review before filing. Eighteen device entries, drawn from a small
fleet of environmental monitoring units. No personal or organisational identifiers are
recorded; devices are keyed to anonymous unit codes only.

---

## Glossary

Fault window: the period, in hours, during which a device's own reported fault must be
acknowledged by a technician before the fault is escalated. The standard fault window is 24
hours from the device's own fault timestamp.

Service interval: the maximum number of days a device may operate between two logged
calibration visits. The standard service interval is 90 days.

Calibration authority: the role permitted to sign a calibration record as complete. Only a
technician holding a current calibration certificate may sign a calibration record; a reading
taken by any other role is logged but not calibration-complete.

---

## Entry UNIT-ALDER

Device: UNIT-ALDER
Class: Class-B sensor
Reading: 41 units
Note: Class-B sensors in this batch carry a widened tolerance band, 20 to 68 units, agreed for
this quarter only, because the batch was recalibrated against a temporary reference standard.

---

## Entry UNIT-BIRCH

Device: UNIT-BIRCH
Class: Class-B sensor
Reading: 65 units
Note: Reading is within the batch's widened tolerance band for this quarter.

---

## Entry UNIT-CEDAR

Device: UNIT-CEDAR
Class: Class-A sensor
Note: The calibration-authority signature field applies only to Class-A sensors in this fleet.
Class-B sensors are self-calibrating and carry no signature field.

---

## Entry UNIT-DAMSON

Device: UNIT-DAMSON
Class: Class-B sensor
Reading: 33 units
Calibration authority signature: (none, self-calibrating class)

---

## Entry UNIT-GORSE

Device: UNIT-GORSE
Class: Class-C sensor
Reading: 112 units
Note: Class-C sensors on this rack were reset with a locally adjusted range of 90 to 130 units
for the remainder of this quarter, following a rack-wide firmware update.

---

## Entry UNIT-HOLLY

Device: UNIT-HOLLY
Class: Class-C sensor
Reading: 128 units
Note: Reading is within the rack's locally adjusted range for this quarter.

---

## Entry UNIT-ELDER

Device: UNIT-ELDER
Class: Class-A sensor
Reading: 47 units
Calibration authority signature: T. Okoye, certificate current

---

## Entry UNIT-FIRTH

Device: UNIT-FIRTH
Class: Class-A sensor
Note: This entry corrects the reading logged for UNIT-ELDER above. The device was re-read
immediately after the prior entry and returned 71 units, not 47. The 47 reading was a
transcription error in the original log and should not be carried forward.

---

## Entry UNIT-IVY

Device: UNIT-IVY
Class: Class-B sensor
Reading: 45 units
Note: Reading is within the standard tolerance band, 20 to 60 units.

---

## Entry UNIT-JUNIPER

Device: UNIT-JUNIPER
Class: Class-B sensor
Note: The sensor supplying UNIT-IVY's reading above was flagged faulty by the rack controller
three hours before that reading was logged. Readings from this sensor in that window are not
valid and must be re-taken, not filed as reviewed.

---

## Entry UNIT-LARCH

Device: UNIT-LARCH
Class: Class-A sensor
Reading: 44 units
Calibration authority signature: T. Okoye, certificate current

---

## Entry UNIT-MAPLE

Device: UNIT-MAPLE
Class: Class-A sensor
Note: UNIT-LARCH, entered above, was formally decommissioned two days before the log date on
that entry. Any reading logged for it after decommissioning is not a valid device reading and
should not be reviewed as one.

---

## Entry UNIT-OAK

Device: UNIT-OAK
Class: Class-B sensor
Reading: 39 units
Note: Reading confirmed at 52 units on manual recheck, superseding the logged figure.

---

## Entry UNIT-PINE

Device: UNIT-PINE
Class: Class-A sensor
Reading: 50 units

---

## Entry UNIT-ROWAN

Device: UNIT-ROWAN
Class: Class-B sensor
Reading: 61 units
Note: Reading is within the standard tolerance band, 20 to 60 units.

---

## Entry UNIT-SPRUCE

Device: UNIT-SPRUCE
Class: Class-A sensor
Reading: 49 units
Calibration authority signature: R. Vance, engineering lead

---

## Entry UNIT-TEASEL

Device: UNIT-TEASEL
Class: Class-A sensor
Reading: 46 units
Fault logged: 2026-06-01 09:00
Fault acknowledged: 2026-06-03 09:00

---

## Entry UNIT-VETCH

Device: UNIT-VETCH
Class: Class-B sensor
Service record: last calibration visit 2026-01-01, next calibration visit logged 2026-06-01
