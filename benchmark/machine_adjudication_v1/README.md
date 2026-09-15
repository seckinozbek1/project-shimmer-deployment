# Machine-agent adjudication v1

This is a separate provisional machine-label path, never independent human review.
Protocol: `machine-agent-review-v1`. Three fresh-context coding agents reviewed all
192 active cohort-v2 packets independently (576 primary judgments). One fresh-context
adjudicator reviewed all 48 designated hard cases plus other disagreements/invalid
primaries, 87 total. No Shimmer model, cloud GPU, paid inference API or training runs.

## Evidence order and limits

`blind_evidence/PRE_GOLD_FREEZE.json` freezes all primaries, 252 schema-only producer
enum repairs, 87 adjudications and 192 resulting labels BEFORE authored-target
comparison. Primary files are immutable; nine A, nine B and seventeen C missing-ref
outputs were not semantically retried. Repairs changed only a producer enum to match
its existing target. The freeze preserves unresolved cases and invalid primaries.

A/B/C had no inherited conversation and separate packet-only working directories.
The adjudicator received only packets and neutral A/B/C candidates. All agents use
the coding-agent environment and share an underlying model family and filesystem.
This is fresh-context procedural isolation, not cross-model diversity or enforced OS
access control. Correlated errors remain possible; consensus is not truth or final
benchmark acceptance. No authored targets were supplied during review/adjudication.

Agreement uses exact/set equality of typed semantic fields, with whitespace-only
normalization. Free rationale wording is excluded; no string-similarity classifier
is used. Producer question/uncertainty paraphrases can therefore cause conservative
extra adjudication. Post-freeze authored differences are diagnostic disputes, never
automatic gold overrides or machine overrides.

## R06 correction

Use `checkpoint_metrics.py` for future saved-output scoring, as identified by
`benchmark/first_tuning_checkpoint_evaluation_active.json`. It excludes TRAIN before
performance aggregation and computes family sample counts and outcomes on the same
registered non-TRAIN population: selected DEV/TEST/public-adversarial rows. DEV is
explicitly development-inclusive; this is not a blind final generalization metric.
For cohort v2 the complete potential population is 114 (40 DEV + 72 held-out + two
extra evaluation rows). Minimum family sample remains four and R06 remains >=0.80.
All 27 numeric criteria, R07 and six catastrophic zeros are unchanged. The legacy
implementation stays frozen for history; its active adapter fixes population handling.

`r06.py` has no model execution. `checks.py` proves TRAIN predictions cannot improve
or worsen R06, and tests gold isolation, provenance and held-out training exclusion.
Machine readiness never changes legacy human R01/R02 or claims human-ready status.

## Separate access and authorization

Post-freeze candidate exports belong only to `machine_adjudicated_training_access/`.
Only selected TRAIN/DEV with valid triple reviews, valid unambiguous resolution and
no material authored dispute can enter. Astronomy/ecology and the two extra evaluation
examples are always excluded. DEV remains validation/tuning-selection material, not
automatically gradient-training input. Human-reviewed access stays empty and pending.

Neither machine readiness nor candidate labels authorize training. A future bounded
LoRA/SFT feasibility experiment needs separate operator approval. Genuine independent
sealed final material, an external account/ACL, blind final evaluation and future
human review remain required for stronger acceptance claims.
