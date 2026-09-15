# Agent-adjudicated first tuning review

Date: 15 September 2026. Base: `befb468` / `d9ddc07`.
Pre-gold checkpoint commit: **`d151ae7a8b54e380cb528eefbc286be2a3ea93d9`**.
Protocol: **machine-agent-review-v1**. Active cohort: **first-tuning-review-cohort-v2**.

## Result

**AGENT_ADJUDICATED_TUNING_EXPERIMENT_NOT_READY**.

**FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING**.
Human first reviews = 0; human second reviews = 0; human adjudications = 0.
The existing human review readiness and training-access namespaces were not modified.

The requested machine review was actually performed: **192 packets ? three separate
machine-agent sessions = 576 primary judgments**. A fourth fresh-context agent made
**87 adjudications**, including **48/48 designated hard packets**. Machine labels were
frozen and committed before authored comparison. This task did not stop at orchestration.

The blocking evidence is **35 effective primary judgments across 17 packets that fail
required-evidence constraints**. The all-valid triple-review criterion M02 is therefore
541/576, not 1.0. Subsequent adjudication does not erase those original failures.
Of 118 potential TRAIN/DEV examples, 79 are excluded and only **28 TRAIN + 11 DEV = 39**
remain provisional machine candidates. They are not human-validated labels, final gold,
training authorization or evidence of checkpoint performance.

## Isolation and provenance

A/B/C were spawned with no inherited conversation and separate packet-only workspaces.
Each received the same 192 active blinded JSON packets, generic semantic instructions
and the existing typed reason ontology. No agent received authored targets, mappings,
split/family assignments, historical answers or another primary pass. The adjudicator
received only 87 original packets and neutrally labelled A/B/C candidate reviews.

Sessions: `/root/machine_a`, `/root/machine_b`, `/root/machine_c`, and
`/root/machine_adjudicator`. Each independently read all assigned cases before serializing
its per-packet judgments. Batch reading and serialization scripts were used; this was
not one agent generating three personas. No primary output was overwritten.

Isolation is procedural: fresh contexts, separate input folders, exact original packet
hash checks, explicit access restrictions and agent attestations. The environment still
has a shared filesystem and the agents share the parent model family. It does not provide
an enforced per-agent OS/account boundary or cross-model diversity. The orchestrator had
prior project context but did not generate or adjudicate labels; the review agents did
not inherit that context. **Zero gold-isolation violations were detected**, with these
limits on what can be verified. Correlated machine errors remain possible.

Provenance uses `independent_machine_agent_review`, `machine_agent_consensus`,
`machine_agent_adjudication` and `machine_adjudicated_training_candidate`. None implies
human independence. The original frozen human submission mechanisms remain unchanged.

## Primary outputs and bounded repairs

All 576 primary files are retained with slot, run/timestamp, packet/input binding,
semantic target/judgment, evidence, reason components, ambiguity and rationale.
Initial validation found 287 invalid outputs: 252 producer top-level enum mismatches
plus 35 missing-required-evidence outputs. The substantive producer arrays were already
present; a single schema-only pass changed MATCH to EXTRACTED/EMPTY according to those
existing items. It did not change claims, gaps, uncertainty, references or reasoning.

Exactly **252 repair files** (84 per agent: 72 EXTRACTED, 12 EMPTY) bind to original
hashes and record attempt 1. Originals remain byte-identical. No semantic retries were
performed. The remaining invalid count is A=9, B=9, C=17 (35 total across 17 unique
packets), all for missing required evidence. Effective valid count is **541/576**.
This formatting defect is recorded as part of the review protocol's operational quality,
not hidden by presenting repaired files as original primary outputs.

## Consensus and adjudication

Material consensus uses exact/set agreement of typed semantics after whitespace-only
normalization. Auditor comparison includes relation, refs, refusal/ambiguity, confidence
and typed reason components; producer comparison includes owned aliases, claim IDs,
gaps, uncertainty, refs and empty/refusal state. Free rationale wording is excluded.
No text-similarity score is used. Conservative exact question/uncertainty strings can
cause extra disagreement for paraphrases; they are not automatically semantic errors.

| Primary structured agreement | Count / 192 | Rate |
|---|---:|---:|
| Unanimous 3/3 | 81 | 42.19% |
| Exactly 2/3 majority | 48 | 25.00% |
| No material majority | 63 | 32.81% |

These describe primary judgments after schema repair, including invalid-evidence
judgments. Only 120 packets had a clean majority supported by two valid responses.
All no-clean-majority packets, all packets with invalid primaries, and the designated
48 hard packets entered adjudication: **87 unique packets**.

Adjudicator decisions: **40 candidate C, 20 candidate A, nine corrected, 18 unresolved**.
All 87 adjudicator outputs pass structural/evidence validation. Of the 24 adjudicated
packets with a pre-existing material majority, 11 changed materially: **45.83% overturn**.
This denominator excludes 63 cases that had no majority to overturn. Selection of a
candidate is not a preference for that agent globally. No gold was available to the
adjudicator and there were no post-gold label-generation passes.

The adjudicator explicitly left **18 incomplete-extraction cases unresolved**. Across
all 192 final records, **90 carry an ambiguity flag (46.88%)**: the 18 explicit unresolved
cases plus 72 other ambiguity-flagged labels. Flags sometimes reflect uncertainty in
the source rather than proven disagreement about the annotation. The eligibility policy
conservatively excludes them instead of silently clearing flags after gold comparison.
These two counts must not be conflated.

Auditor relation-only Fleiss kappa: **0.8367**, across 96 packets and three ratings.
This is categorical same-model machine agreement, not human reliability or correctness.
No producer kappa is reported for structured claims/gaps/uncertainty.

## Agreement breakdowns

Counts below are primary agreement and final ambiguity flags. Domain/template/relation
strata were attached administratively only after the label freeze. Full rates and
adjudicator-overturn denominators are in `post_freeze/agreement_statistics.json`.

### Producer / auditor

| Stratum | N | 3/3 | 2/3 only | No majority | Adjudicated | Ambiguity flagged |
|---|---:|---:|---:|---:|---:|---:|
| auditor | 96 | 57 | 16 | 23 | 42 | 18 |
| producer | 96 | 24 | 32 | 40 | 45 | 72 |

### Domains

| Stratum | N | 3/3 | 2/3 only | No majority | Adjudicated | Ambiguity flagged |
|---|---:|---:|---:|---:|---:|---:|
| astronomy | 36 | 22 | 8 | 6 | 9 | 18 |
| catalogue | 12 | 3 | 3 | 6 | 8 | 7 |
| clinical | 12 | 4 | 2 | 6 | 8 | 7 |
| contracts | 18 | 5 | 6 | 7 | 9 | 7 |
| device | 18 | 6 | 6 | 6 | 10 | 6 |
| ecology | 36 | 22 | 8 | 6 | 12 | 12 |
| negotiation | 17 | 5 | 5 | 7 | 7 | 9 |
| nonsense | 14 | 4 | 2 | 8 | 10 | 8 |
| procurement | 17 | 6 | 5 | 6 | 7 | 10 |
| regulation | 12 | 4 | 3 | 5 | 7 | 6 |

### Structural templates

| Stratum | N | 3/3 | 2/3 only | No majority | Adjudicated | Ambiguity flagged |
|---|---:|---:|---:|---:|---:|---:|
| attributed_dialogue | 1 | 0 | 0 | 1 | 1 | 1 |
| paired_register | 32 | 9 | 11 | 12 | 16 | 16 |
| revision_log | 16 | 2 | 1 | 13 | 15 | 12 |
| scope_notice | 1 | 0 | 0 | 1 | 1 | 1 |
| v2-bullet_list | 15 | 5 | 6 | 4 | 6 | 6 |
| v2-chronological_events | 8 | 3 | 1 | 4 | 5 | 4 |
| v2-compact_table | 12 | 7 | 3 | 2 | 4 | 5 |
| v2-form_fields | 16 | 7 | 5 | 4 | 6 | 6 |
| v2-machine_records | 12 | 8 | 2 | 2 | 4 | 5 |
| v2-memo_sections | 8 | 3 | 1 | 4 | 6 | 4 |
| v2-mixed_prose_table | 12 | 8 | 2 | 2 | 4 | 5 |
| v2-multirow_table | 12 | 7 | 3 | 2 | 4 | 5 |
| v2-nested_provisions | 12 | 7 | 3 | 2 | 3 | 5 |
| v2-paragraph | 15 | 6 | 5 | 4 | 5 | 6 |
| v2-question_answer | 8 | 2 | 2 | 4 | 5 | 4 |
| v2-transaction_register | 12 | 7 | 3 | 2 | 2 | 5 |

### Authored relation strata (diagnostic, attached after freeze)

| Stratum | N | 3/3 | 2/3 only | No majority | Adjudicated | Ambiguity flagged |
|---|---:|---:|---:|---:|---:|---:|
| ADDITION | 18 | 18 | 0 | 0 | 3 | 0 |
| DIVERGENCE | 18 | 15 | 3 | 0 | 13 | 0 |
| EMPTY | 12 | 12 | 0 | 0 | 1 | 0 |
| EXTRACTED | 72 | 0 | 32 | 40 | 40 | 60 |
| INSUFFICIENT_EVIDENCE | 30 | 12 | 0 | 18 | 22 | 30 |
| MATCH | 24 | 24 | 0 | 0 | 1 | 0 |
| OMISSION | 18 | 0 | 13 | 5 | 7 | 0 |

### Refusal cases

| Stratum | N | 3/3 | 2/3 only | No majority | Adjudicated | Ambiguity flagged |
|---|---:|---:|---:|---:|---:|---:|
| False | 162 | 69 | 48 | 45 | 65 | 60 |
| True | 30 | 12 | 0 | 18 | 22 | 30 |

### Information-gap cases

| Stratum | N | 3/3 | 2/3 only | No majority | Adjudicated | Ambiguity flagged |
|---|---:|---:|---:|---:|---:|---:|
| False | 120 | 81 | 16 | 23 | 47 | 30 |
| True | 72 | 0 | 32 | 40 | 40 | 60 |

### Uncertainty cases

| Stratum | N | 3/3 | 2/3 only | No majority | Adjudicated | Ambiguity flagged |
|---|---:|---:|---:|---:|---:|---:|
| False | 132 | 81 | 28 | 23 | 47 | 30 |
| True | 60 | 0 | 20 | 40 | 40 | 60 |

### Held-out domains

| Stratum | N | 3/3 | 2/3 only | No majority | Adjudicated | Ambiguity flagged |
|---|---:|---:|---:|---:|---:|---:|
| False | 120 | 37 | 32 | 51 | 66 | 60 |
| True | 72 | 44 | 16 | 12 | 21 | 30 |

### Unseen templates

| Stratum | N | 3/3 | 2/3 only | No majority | Adjudicated | Ambiguity flagged |
|---|---:|---:|---:|---:|---:|---:|
| False | 118 | 37 | 32 | 49 | 64 | 58 |
| True | 74 | 44 | 16 | 14 | 23 | 32 |

## Pre-gold checkpoint and diagnostic authored comparison

`blind_evidence/PRE_GOLD_FREEZE.json` binds all 576 primaries, 252 repairs, 87
adjudications, 192 final machine labels, input/candidate hashes and review controls.
The freeze timestamp and complete hashes were committed in `d151ae7` before
`post_freeze/GOLD_COMPARISON_STARTED.json` was written and before this task's authored
comparison opened `seed.json` and `extension.json`. Verification rejects changed
labels or a missing pre-gold checkpoint. Both machine and authored targets are retained
in the separate post-freeze diagnostic artifact; neither source is automatically made
correct. The frozen machine labels remain unchanged after comparison.

Producer comparison (96 packets):

| Field | Result |
|---|---:|
| Complete structured agreement | 24/96 (25.00%) |
| Claim-set disagreement | 0 |
| Gap/question-set disagreement | 72 |
| Uncertainty-set disagreement | 60 |
| Evidence-set disagreement | 0 |
| Refusal disagreement | 0 |

All 72 substantive producer outputs differ in gap/question wording from authored
semantic fields, with 60 also differing in uncertainty wording. Exact set comparison
is deliberately conservative: these are **LABEL_DISPUTE_REQUIRING_CAUTION**, not proof
that the agents misunderstood all 72 cases. No post-hoc paraphrase mapping was invented
to make them pass. Empty/refusal cases account for the 24 exact agreements.

Auditor comparison (96 packets): relation agreement **96/96**, evidence disagreement
**0**, refusal disagreement **0**, confidence disagreement **0**. Relation-disagreement
counts for MATCH, DIVERGENCE, OMISSION, ADDITION and INSUFFICIENT_EVIDENCE are all zero.
This does not remove the 18 unresolved-input ambiguities or the invalid primary evidence.
Canonical rationale text matches on 18/96, which is not semantic reason correctness.

Machine-versus-authored **typed reason-component agreement is unavailable**: the frozen
authored records have canonical prose rationale but no typed reason-component annotations.
No false numeric rate or invented gold component annotation was created. Among the three
machine passes, 60/96 auditor packets have unanimous typed reason-component sets.

## Separate machine candidate access

`machine_adjudicated_training_access/train.json`: **28** candidates.
`machine_adjudicated_training_access/dev.json`: **11** candidates.
The manifest explicitly states `machine_adjudicated_training_candidate`,
`human_reviewed=false`, provenance hashes and `training_authorized=false`.

Of 118 tuning-access candidates, **79 are excluded**. Overlapping exclusion flags are:
48 disputed, 58 ambiguity-flagged and 15 with at least one evidence-invalid primary.
A candidate requires all three effective primaries valid, a valid unambiguous final
label, no material diagnostic dispute, and current selected TRAIN/DEV access. It never
enters the human-reviewed namespace. DEV remains for validation/tuning decisions and
is not automatically merged into gradient training.

All **72/72 astronomy/ecology examples** received three primary machine reviews and
are represented in the machine reference manifest. Together with the two extra
evaluation examples, all **74 evaluation-only labels remain excluded** from the machine
training-access directory. A future separately authorized job receives only that child
directory, never the surrounding blind evidence, gold comparison or evaluation reference.

## R06 population consistency fix

The maintained adapter is `benchmark/machine_adjudication_v1/checkpoint_metrics.py`,
identified by `benchmark/first_tuning_checkpoint_evaluation_active.json`. The legacy
frozen evaluator remains preserved for history. The adapter excludes TRAIN before
performance aggregation and uses the same non-TRAIN population for family sample counts
and observed outcomes. It never uses TRAIN predictions as generalization evidence.

The frozen profile explicitly registers **selected DEV/TEST/public-adversarial outputs,
excluding TRAIN**. Therefore DEV is included here as registered development-inclusive
first-experiment evaluation, not rebranded as independent blind final generalization.
The potential cohort-v2 scoring population is **114 = 40 DEV + 72 mandatory held-out +
two extra evaluation** (37 TEST / 37 public adversarial by ordinary split). Actual scoring
also requires eligible labels and complete unique saved outputs from that population.

R06 remains **>=0.80** with a minimum of **four** eligible reviewed examples per family.
The 114-row potential population has 34 families: 12 held-out families with six examples
and 22 sparse families (20 DEV families with two each and two extra families with one).
Sparse families are explicitly insufficient; missing measured outputs never pass.
No checkpoint outputs or performance scores were generated in this task.

Regression/effect tests prove TRAIN rows cannot alter the sample denominator or improve
or worsen R06, including adversarial same-family TRAIN rows. The integration adapter
replaces only the population bug and preserves human R01/R02 failure/pending status.
All **27 thresholds, derived R07 and six catastrophic zero limits remain unchanged**.

## Machine criteria and current readiness

| Criterion | Observed | Result |
|---|---|---|
| M01 primary slot coverage | 576/576, 192 packets | Pass |
| M02 valid triple-review coverage | 541/576 | **Fail** |
| M03 designated hard adjudication | 48/48 | Pass |
| M04 required adjudications and safe used labels | 87/87 valid; no ambiguity used | Pass with exclusions |
| M05 held-out coverage/access protection | 72/72 reviewed; excluded from training | Pass |

The readiness verdict remains **AGENT_ADJUDICATED_TUNING_EXPERIMENT_NOT_READY**.
Machine candidate existence does not override M02. Human status remains
**FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING**, with all three human counts zero.
Final benchmark/model acceptance remains not ready; machine consensus cannot replace
future humans, genuine independent sealed material, external ACLs or blind final evaluation.

## Validation, security and preservation

**22 machine control tests + 30 preserved cohort tests + 85 production checks = 137
passing local checks**, with **12 effect proofs** and one pre-existing optional fixture
skip. Four new proofs cover gold isolation, held-out exclusion, R06 TRAIN exclusion and
human/machine provenance separation. These control passes do not turn failed review
outputs into valid judgments or satisfy M02.

Frozen benchmark/cohort/acceptance hashes verify unchanged. **106 historical A/B evidence
entries** verify; all **four historical invalid outputs** remain rejected. Obsolete
cohort submission rejection still passes. No production validator or model pin changed.

Credential/privacy findings: **zero detected** in scanned new artifacts. Evaluation
labels in machine training-access files: **zero**. Gold-isolation violations detected:
**zero**, subject to the shared-filesystem/procedural isolation limitation above. No
operator-private documents or durable state were read or altered. Full test/scan evidence
is retained in [agent_adjudicated_tuning_20260915](agent_adjudicated_tuning_20260915/).

## Next step and explicit boundaries

Do not train. The current protocol does not meet the operator's all-valid triple-review
rule. Preserve the disputed/ambiguous labels and invalid primaries. A future separately
authorized methodology correction can make evidence requirements clearer and register
semantic atom normalization before another blinded review; it must not retrofit this
frozen run or retry until agreement. Independent human review remains desirable when
available. Any eventual bounded LoRA/SFT feasibility run needs separate approval.

No human review was falsely claimed. No cloud GPU instance, paid inference API, Shimmer
model execution, training, LoRA/SFT, model/revision/quantization change, full pipeline,
Shimmer multi-round or push occurred. User-owned root `SHIMMER_HANDOFF.md` and `durable/`
remain untouched.
