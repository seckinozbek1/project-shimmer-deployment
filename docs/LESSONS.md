# Lessons that hold from now on

Each lesson below came from a real failure in this project and is a standing rule for this project and for any
project built from it (including the transfer to Silica). The private decision record holds the evidence; this file
holds the rule, what enforces it, and where.

Recorded 21 November 2026 (decisions D-868 to D-873).

## 1. Coverage gate before every score
Before any figure is written, count for every item whether the system itself answered it. If more than 5 percent of
the items are empty, filled with a default, or withheld, the figure is not written and the reason is.
Enforced by `tools/coverage_check.py` (exit 3 refuses). A document where a step ran and judged that nothing was
there (a judged absence) counts as an answer only when the run's own record shows the step was asked and nothing
failed.

## 2. Fail fast during a run
When a step gives no answer on the first items, when the empty or default share passes 5 percent, or when a form
condition fails, the run stops at that stage, the rented machine shuts down, the spend is recorded and the reason is
written. A run never goes to the end and is found broken afterwards.

## 3. Smoke test before every large measurement
Three to five items run end to end, and every step's output is shown working, before a large or costly
measurement starts.

## 4. Thresholds are fixed ex ante
A confidence threshold is written to the configuration and the decision record before the measurement it governs
and is never changed after it. A threshold chosen afterwards is chosen on development items only, by a rule written
before any figure, applied once, and labelled as chosen after the fact in every report.

## 5. Every published figure is the system's own output
Before a figure is published, check that it comes from the system's own answers. A proxy reading (for example
"the model's most likely answer read from saved probabilities") is labelled as such and never stands in for the
system's figure.

## 6. Answer options cover reality
For every closed question, check before the run that each real state of the world has an answer option (for
example "still open" beside "kept", "changed" and "removed").

## 7. Same-item re-measurement is labelled
A figure measured again on items already seen is labelled "on the same items, after the fix". It is reported beside
a very small untouched set and a permutation test (`tools/chance_test.py`, at least 10,000 shuffles, fixed seed).
The real evidence comes from unseen items.

## 8. Staged contribution
Fixes are measured in stages, each its own figure: the threshold alone, the root-cause fixes, then the further
fixes, so the contribution of each shows.

## 9. Fixes, not problem lists
What goes to the operator is what was fixed, its proof (a check, a commit) and the result, not a list of problems.

## 10. Skip redundant checks, never defensibility
Checks that repeat another check, whose result is unused, or that repeat needlessly may be skipped or thinned.
Never skipped: freeze and seal, the closed test set, the leakage check, the coverage gate, fail-fast, the spend cap,
the usage stop, the deletion and publishing rules, supervision and wake mechanisms.

## Transfer
A project that starts from this one (Silica, or any later one) copies this file, `tools/coverage_check.py` and
`tools/chance_test.py`, and wires lessons 1 to 4 into its scoring and run paths before its first measurement.
