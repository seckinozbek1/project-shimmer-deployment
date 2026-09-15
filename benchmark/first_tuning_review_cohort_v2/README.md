# First tuning review cohort v2

Active review-selection revision: `first-tuning-review-cohort-v2`.
Acceptance profile remains the unchanged frozen `first-tuning-experiment-v1`.
Current status: **FIRST_TUNING_EXPERIMENT_REVIEW_PENDING**.

The operator approved 78 TRAIN + 40 DEV + 72 mandatory held-out examples + two
additional evaluation examples = 192. The two extras preserve `attributed_dialogue`
(TEST) and `scope_notice` (public adversarial), which do not exist in TRAIN/DEV or
the held-out domains. The earlier 80/40/72 request could cover only 14 templates.
No benchmark identity or threshold was changed to make the allocation fit.

The new cohort has 96 producer/96 auditor, all ten domains and 16 templates, 74
unseen-template evaluation rows, 54 document families (the allocation's maximum),
30 refusal/insufficiency cases, 72 gap cases and 60 uncertainty cases. All 48
TRAIN/DEV producer examples are substantive extraction. Exact administrative counts
and the 26 excluded families are in `cohort.json` and `selection_metadata.json`.

The double-review subset has 48 unique packets and 48 distinct families, balanced
24/24, all ten domains and 16 templates, 18 refusal/insufficiency cases, 19 gap cases
and 19 uncertainty cases. It prioritizes semantic disagreement risk before diversity
filling. The source difficulty features are administration proxies, not proof of
human difficulty or independent annotation reliability.

Use only the new `reviewer_1_first_tuning_v1_cohort_v2.zip` and
`reviewer_2_first_tuning_v1_cohort_v2.zip`. Old archives are preserved and marked
**SUPERSEDED_BEFORE_HUMAN_REVIEW** in `supersession.json`. The active pointer is
`benchmark/first_tuning_review_active.json`. Never give reviewers admin manifests.

[ADMIN_SUBMISSION.md](ADMIN_SUBMISSION.md) documents the bound-envelope adapter
around the unchanged v2 human journal. Plain legacy responses, stale hashes, wrong
assignment membership and unreceipted native journal entries fail closed. No real
or fake human submissions were executed during preparation.

Potential accepted tuning-access material rises from 78 to 118 (78 TRAIN/40 DEV).
Actual eligible count remains zero. All 74 evaluation-only examples stay excluded;
DEV stays distinct for validation. The remaining 544 packets remain preserved.
Final model acceptance is still false and requires genuine independently contributed
sealed material with an external account/ACL and stricter final criteria.

Local checks: run `gate.py` with the compatible local Python executable. This blocks
model/provider imports and network calls. No cloud, paid API, model generation,
training, LoRA/SFT, model/revision/quantization change, full pipeline or multi-round.
