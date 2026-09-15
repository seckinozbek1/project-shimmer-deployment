# Domain-agnostic tuning dataset and frozen evaluation

15 September 2026. Implementation commit: `090b3d50129a71a6ad9bfe703464ea8120b17d91`.
Parent: `8752da6d1010a578e9a518eb38fb85db232fb522`.

## 1. Why tuning was triggered

The preserved bounded A/B returned `REMOTE_CONTRACT_MODEL_AB_FAIL` and recommended
task tuning for both roles. The NEW producer reached EOS with shorter output but
omitted the missing-information gap, contradicted its populated claims with empty
status, and emitted fences. The NEW auditor produced MATCH and both refs, but its
reason partly misread a pre-existing absence and it appended unsolicited prose.
All four historical outputs remain rejected. There was no new model execution.

## 2. Frozen contracts

Schema, prompt/task, adapter and validator version: **`semantic-task-v1`**.
[Config manifest](../../config/semantic_task_contract_v1.json) records field
semantics, statuses, routing, ownership, exact reconstruction, prompt hashes and
the production authority hashes. It points to the existing compact contracts,
bounded ledger/hydration, AgentWrapper and agent-contract config. Those production
files were not changed. The benchmark imports their live adapters.

[Frozen dataset manifest](../../benchmark/task_semantics/frozen_dataset.json)
hashes the evaluator, builder, schema, data, negatives and split/ancestry manifests,
and binds the config manifest. A changed frozen file cannot be rebuilt into the
same version without the guard rejecting it. The task-input renderer uses frozen
production builders; gold/adjudication are excluded. Auditor ORIGINAL contains
owned source only; neighboring context and unrouted rules are marked distractors.

Python retains source text, offsets, ordering, provenance, agent/document identity
and paragraph routing. The producer emits aliases, explicit claim IDs, questions,
uncertainty, status and refs. The auditor emits the existing four finding values,
reason, exact refs, severity and confidence. No new production finding enum exists.

## 3. Refusal/status mapping

| Evaluation state | Required interpretation | Production acceptance |
|---|---|---|
| extracted | Every owned alias exactly once; populated semantic arrays use extracted | Yes, if existing adapter passes |
| examined_empty | Owned producer span examined with empty semantic arrays; auditor zero items only when both inputs empty | Yes |
| semantic_refusal | Exactly `{"items":[],"status":"refused"}`; insufficiency or inability to complete | No; recognized evaluation outcome only |
| incomplete | Truncated output or otherwise-valid partial producer ownership coverage | No |
| malformed | Invalid JSON, extra prose/fences, contradictory status, invalid fields/evidence | No |
| fidelity | Existing MATCH/DIVERGENCE/OMISSION/ADDITION comparison | Yes, if existing adapter passes |

`accepted_outcome` may recognize a correct refusal. `semantic_accepted` and
`production_accepted` exclude it. Incomplete evidence never becomes an empty
success or MATCH. Transport failure independently prevents acceptance even if
the parsed contract is valid. Confidence in a fidelity finding is distinct from
uncertainty expressed in the source: preserving uncertainty can be confidently MATCH.

## 4. Dataset schema

[Record schema](../../benchmark/task_semantics/record.schema.json) plus executed
semantic validation requires stable IDs, role/task/relation, domain/document type,
language/style, six family identities, parent ancestry, split and allocation ID,
source/rights/privacy provenance, source/extraction inputs, ledger size, owned and
context aliases, supplied/required refs, routed and distractor rules, gold target,
refusal/uncertainty expectations, negative tags, version IDs and adjudication.

The adjudication structure includes first/second IDs and judgments, agreement,
final target, rationale and ambiguity. All **448** seeds honestly say
`authored_single`; there is no claimed human agreement. The workflow rejects
self-review and unresolved disagreement. Independent reviews in unit tests are
explicitly synthetic interface tests and do not update corpus review status.

All material is newly authored public synthetic content. Clinical/legal surfaces
are fixtures, not advice. No private benchmark keys, operator documents or durable
state were opened for labels. Seed labels live under `benchmark/task_semantics/`,
outside production source-layer roots and operational/durable input.

## 5. Domain distribution

| Domain | Examples | Document families |
|---|---:|---:|
| negotiation | 56 | 4 |
| contracts | 56 | 4 |
| regulation | 56 | 4 |
| clinical | 56 | 4 |
| device | 56 | 4 |
| procurement | 56 | 4 |
| catalogue | 56 | 4 |
| nonsense | 56 | 4 |
| **Total** | **448** | **32** |

Eight document types; four structural template/style families. Nonsense uses
invented entities, quavel units, blenket objects and an invented institution.
Vocabulary is data in the builder, never an evaluator decision rule. All 448 rows
are English; the schema supports other languages without claiming measured ability.

## 6. Abstract-task distribution

| Role/relation | Count |
|---|---:|
| Producer extracted | 32 |
| Producer examined empty | 32 |
| Producer insufficient evidence/refusal | 32 |
| Auditor MATCH | 32 |
| Auditor DIVERGENCE | 160 |
| Auditor OMISSION | 96 |
| Auditor ADDITION | 32 |
| Auditor insufficient evidence/refusal | 32 |
| **Producer / auditor** | **96 / 352** |

There are **64 refusals**, 32 producer uncertainty-preservation examples and
32 multiple-claim producer examples. Auditor inputs include both faithful unequal
values and equal-valued statements with swapped labels/entities. Fidelity never
reduces to numeric equality. Missing information and its question are explicitly
preserved in MATCH and removed in the corresponding OMISSION variants.

## 7. Hard negatives

There are **576 rejected candidate outputs: 32 for each of 18 transformations**.
These cover all 16 requested categories, with formatting split into copied prose,
trailing prose and fences:

- Number change; label swap; unit change; entity swap.
- Explicit claim omission; gap omission; unsupported addition.
- Irrelevant supplied ref; missing required ref; unrouted rule attribution.
- Duplicate ownership; context-only alias claimed.
- Removed uncertainty; unsupported certainty; contradictory status.
- Copied prose; trailing prose; code fence.

Separately, **288 gold auditor examples** carry transformed extraction inputs
(nine semantic transformations, 32 each). Their gold is the correct judgment of
the changed input, not the negative answer. Every generated input/output variant
retains parent ID, derivation group and the preassigned split.

## 8. Split construction

| Split | Rows | Structural template |
|---|---:|---|
| train | 112 | paired register |
| dev | 112 | retained revision log |
| test | 112 | attributed interview |
| sealed_adversarial | 112 | authorization/storage exception notice |

The allocation is persisted before any variants. All domains sharing one template
remain in its one split. Source-document, template, derivation, paraphrase,
renaming and near-duplicate family links are checked, along with transitive parent
ancestry. Split and ancestry manifests are checked against records and allocation.
Tuning selection permits only train/dev (**224 rows**); test/adversarial/regression
requests are rejected. Negative candidates cannot drift from their parents.

**The adversarial seed is public and not independently blind.** Its partition
exercises the future sealing workflow; it must be replaced by independently held
material before final model acceptance. All eight surface domains occur in each
split; there is no held-out-domain generalization claim. The original public A/B
fixture is regression-only, excluded from the 448 seed rows and from blind counts.

## 9. Leakage audit

**Zero** cross-split family findings, broken ancestry findings, exact duplicate
crossings or public-regression contamination findings. The family gate checks 108
distinct family-field groups. Exact normalized source/extraction hashes are checked
across roles and splits. Regression source hashes and ancestry flags fail closed.
The lightweight cross-split document similarity audit has **zero warnings at 0.70**;
that threshold is a warning heuristic, not evidence of statistical independence.

The data gate rejects missing/unknown schema fields, duplicate IDs, broken/cyclic
ancestry, changed allocations, malformed/inconsistent targets, missing/invented
evidence, unrouted gold rules, false refusal/uncertainty state, missing provenance
and invalid privacy/rights. Freeze hashes protect the curated labels; deterministic
syntax checks cannot independently prove every authored semantic label is true.

## 10. Evaluation metrics

**Producer:** strict contract, transport/truncation, exact aliases and ownership,
claim precision/recall, gap precision/recall, uncertainty preservation, exact refs
precision/recall, invented refs, examined-empty/refusal correctness, semantic
completeness and copied-source violations. Atom comparisons include owned alias.

**Auditor:** strict contract, relation accuracy and per-class precision/recall,
refusal/insufficiency precision/recall, over-/under-refusal, unsupported forced
answers, reason correctness, confidence preservation, evidence precision/recall,
invented refs and unrouted rules, truncation and confident wrong judgments.

Both retain separate completion, parser and semantic layers, plus aggregate,
per-role and per-document-family results. Missing refs are never repaired.
Whole-response JSON parsing rejects fences/trailing prose and duplicate keys;
no suggestive prefix is promoted. Parsed-but-invalid fields may supply diagnostic
metrics, while acceptance remains false. Historical raw-only observations are
explicitly separate from accepted metrics.

Canonical reason text is an authored rubric, not automatic language understanding.
Alternate rationale requires hash-bound independent adjudication; otherwise reason
correctness is unassessed. Exact canonical gap/uncertainty scoring is conservative
and does not establish paraphrase equivalence. Wilson intervals are descriptive;
the report warns that related authored rows are not independent model trials.
Catastrophic invented evidence/rules, confident wrong MATCH/DIVERGENCE and silent
gap omission remain separate counts. The seven prior structured error classes
are preserved, including `model_semantic_capability_error`.

The acceptance template has no fitted thresholds. A future registration must bind
the dataset and run, verified governance, independent labels and blind evaluation.
The public seed cannot approve a model even if every authored target scores perfectly.

## 11. Historical baseline reproduction

All **106** entries in the prior A/B artifact hash manifest verify unchanged.
The four raw hashes match their preserved adjudications. Baseline outputs retain
original source commit, usage and single-review provenance, separately from authored
targets. OLD controls are also marked as rejected by their original adapters.

| Historical output | Complete generation | Strict accepted contract | Semantic acceptance |
|---|---|---|---|
| producer OLD | Yes | No | No |
| producer NEW | Yes | No | No |
| auditor OLD | No; capped | No | No |
| auditor NEW | Yes | No | No |

Both NEW responses visibly contained the two refs; parser rejection does not erase
that preserved raw diagnostic fact. NEW auditor's MATCH did not establish correct
reasoning or contract validity. No authored token counts are represented as generated
measurements. There were no new generation or latency measurements.

## 12. Governance/evidence checks

**42 new deterministic tests pass**, including **448 gold outcomes** and **576
negative rejections**. Three new executed neutralise/fail/restore/pass proofs cover
whole-response parsing, exact evidence scoring and family isolation. The existing
no-generation compact gate passes **85 checks** with four existing effect proofs;
one pre-existing optional fixture-directory skip remains. Total: **127 passing
checks**, zero failures, seven effect proofs across the two gates.

Direct new regressions cover distinct producer/auditor families, no self-audit,
public synthetic privacy, operator authorization, provenance, no training/paid API/
multi-round, refusal versus production acceptance, incomplete transport and source
reconstruction. The existing gate additionally exercises live family-configuration
separation, typed rule/evidence governance and strict production wrapper behavior.
No production validator was weakened. The new gate blocks network and model/provider
imports. New file credential scan: zero findings; see the retained safe scan artifact.

Evidence: [domain_agnostic_tuning_20260915](domain_agnostic_tuning_20260915/), containing
statistics, leakage audit, gold/negative/historical baselines, both validation logs,
security scan and artifact hashes.

## 13. Dataset limitations

The largest weakness is **only four public, single-authored structural templates**.
448 rows are correlated descendants, not 448 independent generalization trials.
The auditor-heavy balance (352 versus 96 producer) and 32 non-refusal, non-empty
producer examples need expansion. No independent human adjudication, private final
test, held-out surface domain or multilingual model measurement exists. Rationale
and paraphrase scoring needs independently reviewed alternatives. Zero similarity
warnings do not cure these limitations. Gold self-consistency is not model quality.

## 14. Readiness verdict

**DOMAIN_AGNOSTIC_TUNING_DATA_READY**

The requested contracts/status mapping, populated cross-domain seed, transformation
helpers, frozen evaluators, leakage controls, historical reproduction, evidence and
governance gates are implemented and pass. This is infrastructure/seed readiness;
it neither authorizes training nor accepts a checkpoint.

## 15. Next step

Independently review labels/reasons and expand producer, document and template
families; establish a genuinely blind final/adversarial set and pre-register model
acceptance criteria with family-aware uncertainty reporting. Then seek separate
authorization for a bounded domain-agnostic LoRA/SFT experiment using the unchanged
Qwen/Phi pins and family separation.

The future ladder remains conditional: Stage 0 frozen baseline; Stage 1 justified
few-shot ablation; Stage 2 separately authorized LoRA/SFT; Stage 3 error-driven hard
negatives; Stage 4 optional specialist/distillation; Stage 5 selective independent
stronger-model escalation. No stage is automatic or executed here.

**No cloud, paid API, training, LoRA/SFT, new model/download/revision/quantization,
full pipeline, full model workload, multi-round or push.** Historical evidence and
user-owned `SHIMMER_HANDOFF.md`/`durable/` were preserved.
