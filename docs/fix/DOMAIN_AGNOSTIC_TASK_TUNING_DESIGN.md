# Future domain-agnostic semantic task tuning — design only

Triggered by [the bounded model A/B](REMOTE_CONTRACT_MODEL_AB.md):
`DOMAIN_AGNOSTIC_TUNING_RECOMMENDED=true`, roles **producer and auditor**.
No training, LoRA, model replacement or new cloud work is authorized or performed here.

## Objective and frozen contract

Learn **task semantics across domains**, not facts or vocabulary from any one domain.
Keep the established producer/auditor family separation and governance requirements.
The producer must preserve claims, information gaps and uncertainty while obeying source
ownership; the auditor must judge the requested fidelity relation and ground its response.

Before creating training targets, version and freeze the compact wire schemas, routing
identity rules, prompt versions and validators. Preserve explicit examined-empty versus
incomplete extraction. Freeze refusal treatment too: the current wire request permits
`items=[]` with `status=refused`, while the acceptance adapter rejects it as successful
extraction/fidelity. Future labeling must recognize that as semantic refusal, not confuse
it with malformed JSON or reward it as successful MATCH. Settle the result-status mapping
and test it before training; do not silently add an unsupported finding enum.

Do not train against moving schemas or teach validators to accept malformed model output.
Do not reward code fences, trailing prose, inconsistent status, invented citations or
unsupported rule attribution. Source reconstruction remains Python's job.

## Bounded data specification

Each example records:

- Stable example, document-family, template-family and derivation-group IDs; split assignment.
- Surface domain, document type, language/style, entity/unit substitutions and generation provenance.
- Original text, existing owned aliases, context-only spans, supplied refs and routed rules (if any).
- Task type and abstract relation: extraction, faithful preservation, omission, addition,
  divergence, ambiguity/insufficiency or correct refusal.
- Human-adjudicated semantic atoms, gaps, uncertainty, exact evidence refs and valid compact target.
- Negative candidates, precise error labels and independent adjudicator agreement/disagreement.
- Schema/prompt/version hashes and rights/privacy provenance. Use authored synthetic or
  permissioned material; exclude credentials, operator private state and hidden answer keys.

Maintain separate producer and auditor targets. Auditor training includes both authored
valid extraction and actual producer error patterns, without treating a producer answer as
gold simply because it parsed. Identity/provenance stamped by Python is not model output.
Evidence IDs must be selected from the supplied task, not automatically injected as answers.

## Domain diversity and abstract consistency

Use balanced families across unrelated surfaces: negotiation, contracts, regulation,
clinical/medical records, technical/device records, procurement, metadata/catalogues,
and synthetic nonsense domains. Clinical/legal surfaces are synthetic task fixtures,
not advice or domain knowledge tests. Cap any one surface domain's share before collection.

Express each abstract relation under varied entities, units, vocabulary, styles and document
types. Counterbalance surface cues so a familiar domain word, numeric difference or
institution name does not reveal the target class. Include unseen domain families at final
evaluation, not merely new entity names inside a familiar template.

For example, preservation of two differently labeled quantities should remain fidelity
under unrelated surface terms. Conversely, equal quantities with swapped semantic labels
must not become MATCH. Do not teach a special answer for the public capacity/date fixture.

## Split and leakage controls

Assign train/dev/test **by groups before creating variants**. Every source document family,
synthetic template family, paraphrase, near-duplicate, renamed version and derived variant
belongs on only one side. A renamed template is not independent held-out evidence.

Use separate held-out domain families and unseen template families, with a sealed final
adversarial test set. Audit exact and near-duplicate overlap across splits and investigate
shared derivation ancestry. Keep tuning/error-selection access restricted to train/dev.
Do not repeatedly inspect final-test answers to choose prompts, examples or checkpoints.

The current published A/B fixture is a regression/diagnostic case, not a blind held-out
test. Its renamed descendants cannot support a near-perfect generalization claim.

## Hard negatives and refusal

Include at least these independently labeled structures across multiple domains:

1. Different original numbers, faithfully preserved in extraction.
2. Matching numbers but changed/swapped labels, entities, dates or units.
3. Explicitly missing information correctly preserved and raised as a question.
4. Missing information wrongly presented as a known fact or silently omitted.
5. Complete source content with a newly introduced omission/addition/divergence.
6. Relevant and irrelevant refs mixed together, including plausible neighboring refs.
7. A rule ID existing elsewhere but not routed to this task; attribution must be refused.
8. Plausible unsupported conclusions or claims of absence contradicted by the source.
9. One owned span with multiple observations; context-only aliases and duplicate ownership traps.
10. Examined-empty, genuinely ambiguous and insufficient-evidence cases.
11. Surface vocabulary strongly suggesting the wrong relation.
12. Correct JSON prefix followed by persuasive extra prose, fences, or inconsistent status.

Correct refusal is part of quality. Distinguish semantic refusal from technical failure,
and insufficient evidence from simply needing clarification about an already-known gap.
Never force an unsupported answer to increase recall. Evidence IDs must remain exact;
targets cannot fabricate citations or rule IDs to appear complete.

## Evidence-driven ladder; no stage is automatic

| Stage | Candidate next action | Advancement evidence |
|---|---|---|
| 0 | Frozen prompt/contract baseline and grouped evaluation set | Reproducible strict validation, semantic rubric and error taxonomy |
| 1 | A small, token-efficient exemplar ablation if justified | Held-out dev improvement beyond current baseline without consuming bounded output margin |
| 2 | Separately authorized domain-agnostic SFT/LoRA | Sufficient independently labeled grouped data; stable schema; prespecified quality and governance thresholds |
| 3 | Hard-negative/error-driven refinement | Reproducible residual errors on dev families; no final-test leakage |
| 4 | Optional distillation or a smaller specialist model | Quality, calibration and evidence integrity preserved on unseen families, with measured efficiency benefit |
| 5 | Selective escalation to a stronger independent model | Reliable uncertainty/escalation policy and independently measured risk coverage |

Do not turn Stage 1 into indefinite prompt revision. Do not assume training will fix every
failure. Any future model or API change, paid inference, training or cloud allocation needs
its own authorization. Preserve cross-family auditing rather than tuning both roles into
an unexamined shared failure mode.

## Evaluation contract

Report separately, by role, domain family, template family and difficult relation:

- Precision, recall and F1 where applicable for claims, gaps and semantic changes.
- Typed relation/judgment correctness and independently adjudicated reason correctness.
- Evidence-reference precision and recall; exact citation/ownership validity.
- Hallucinated attribution rate, omission detection and addition detection.
- Refusal precision/recall, over-refusal and unsupported forced-answer rate.
- Contract-validity rate, truncation rate and output-length distribution at fixed ceilings.
- Calibration, escalation quality, coverage and error severity under the chosen escalation policy.
- Governance equivalence, uncertainty preservation and cross-family audit integrity.
- Latency and cost per **accepted** task, separated from setup and rejected responses.

Keep parser success separate from semantic success; both must pass. Evaluate source
reconstruction mechanically and reasons against original/extraction evidence, not verbal
fluency. Use independent review of ambiguous cases with adjudication rules fixed before
model comparison. Report confidence intervals and family-level variability, not only a
single aggregate score. Pre-register acceptance thresholds and leakage audits.

Near-perfect quality requires held-out domain families and adversarial examples. A single
deterministic fixture PASS is necessary for regression closure but insufficient for that
claim. This artifact defines the next data/evaluation task; it creates no dataset or training run.
