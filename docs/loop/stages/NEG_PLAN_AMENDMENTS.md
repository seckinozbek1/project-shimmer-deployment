# Amendments to the negotiation plans (NEG_ADVISOR_PLAN.md, the pilot; NEG_DRAFT_BENCH_PLAN.md, the benchmark)

Each amendment is written here before any score that uses it, with its date and decision. They bind both plans and are
folded into the plan files when the lanes merge. No amendment is applied to a score read before its date.

## AM-1 (D-662, 15 November 2026, 18:35 +0300): a checker field of one class

When the key and the checker both give the same single class on a field, kappa is undefined. The raw agreement is
reported, and at 100 percent the field counts as at the bar, labelled "single class, kappa undefined". Below 100 percent
on a single-class field, the field is below the bar. Applies to the bar's line 4 and to M9's validation alike.

## AM-2 (D-665, 15 November 2026, 18:39 +0300): red lines measured two ways

- **Declared red line:** the party says so in the record ("cannot accept" and the like). The system's extraction is
  scored against the labels, as now (`red_line` per proposal).
- **Held red line:** did it hold in the next round? Computed in Python from the fate the scorer already computes: a
  proposal resting on a declared red line that the party later accepts, or lets through (its fate `kept` or `changed`
  toward the proposal with no recorded objection of that party), counts as not held; one the party keeps opposing, or
  that is removed, counts as held. Reported as the held share: a finding on which declared red lines were real and which
  were bargaining positions. It is a property of the record, the same for every arm; beside it, each arm's agreement
  with "held" on the red lines it extracted.
- **Arms and items:** the system, B1 and the cloud reference, on development and track A items. The frozen pilot is
  only re-scored with it, never tuned on.
- **Source:** every red line carries its source field, for now only "from the document" (D-664).
