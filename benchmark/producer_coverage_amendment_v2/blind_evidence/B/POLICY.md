# producer-semantic-policy-v2

Amendment: producer-coverage-amendment-v2. Renderer: producer-target-renderer-v2.
Evidence kind: training_label_curation_evidence. Use: curation_only.
NOT independent_generalization_evidence; NOT blind_final_evaluation. This policy is informed by prior aggregate diagnostic categories on previously inspected TRAIN/DEV material. Agreement is not model quality, final acceptance, or protected-test performance.

## Ownership and contract
Python owns exact source, offsets, identity, order and reconstruction. Return every explicit CLM ID in each owned alias, including conflicting assertions; never reconcile contradictions. Context-only spans are not owned. Contradiction alone does not imply epistemic uncertainty. Refusal only for unusable source; never merely uncertain content. Preserve explicit source questions and qualifiers. Exactly one semantic item per owned alias in source order. No new production fields.

## Atom fields and finite ontology
Each atom has exactly kind, category, subject, attribute, ordinal, relation, state, scope, unit, span, refs, support, origin. Optional wording is ignored. support is an exact source substring, preferably a complete sentence/clause including negation and modifiers; it need not equal the canonical output. origin=source_explicit, scope=owned_record, unit=null, relation=null (unsupported before/after relations are not admitted). Material identity includes every field except support/wording. Distinct refs, subject, ordinal, category/state/time role must never collapse.

kind gap categories:
- missing_information, state unspecified: explicit missing date/identity/status information, or unanswered temporal/recorder questions.
- explicit_nonoccurrence: explicit record/entry/submission nonoccurrence; see states below.
- explicit_question, state requested: explicit entry-order or entry-content inquiries, including answered questions. They are preserved as questions, not claims that their answers are unknown.
kind uncertainty: category unknown, state unknown. Only explicit epistemic uncertainty; no invented categories.

Subjects: owned_record normally; entry for ordinal entries/claims; submission for explicitly named submission referents; amendment for its state/effective time; event for underlying event occurrence. Ordinal is null, integer1/2/3, or next/previous/later. first=1, second=2, third=3; following=next, prior=previous. Explicit noun type takes precedence: second submission is subject submission/ordinal2; second claim is subject entry/ordinal2.

Attributes:
- recording_time, event_time, submission_time, authorization_time, observation_time, reporting_time, effective_time;
- date_unspecified when the source does not bind a date to a unique role;
- recorder, interpretation, ratification_status;
- entry_order, entry_content, entry_presence;
- recording_occurrence, submission_occurrence, event_occurrence.
Aliases only pair each supported *_date role with its *_time role; no cross-role equivalence.

## Source-span grammar
The maintained finite interpreter recognizes complete explicit absence/nonoccurrence, epistemic and interrogative constructions. Support must be exact in the owned alias, have exact owned refs and interpret to the submitted atom. The whole containing source clause must support the same atom: stripping negation or embedding context must not reverse it. Known negation-of-absence/uncertainty and false/denied embedding constructions are excluded. Unsupported semantics stay unresolved, never inferred with similarity.

Date/time/period absent, missing, unavailable, not supplied/provided, or unspecified -> missing_information for that temporal role. Generic date is NOT automatically recording_time. It can inherit only a unique role from an immediately following temporal question about the same owned record; an intervening unrelated sentence or conflicting temporal roles prevents inheritance.

No X recorded / X not recorded -> explicit_nonoccurrence, recording_occurrence, state not_recorded. This does not establish the underlying event did not happen. No X submitted / X not submitted -> submission_occurrence, state not_submitted. No entry/claim appears, or entry absent -> entry_presence, state absent. No event occurred / event did not occur -> event_occurrence, state did_not_occur. Missing information, explicit nonoccurrence and unknown whether occurrence happened remain distinct.

Epistemic clauses (unknown, unclear, uncertain, unresolved, undetermined, not known) bind first to a temporal role if date/time/when is explicit; otherwise interpretation, ratification status or occurrence/presence. Unknown WHEN submitted is submission_time; unknown WHETHER submitted is submission_occurrence. Explicit uncertainty in the interpretation of second entry is subject entry, ordinal2, attribute interpretation. Ordinary interpretation is owned_record. Unclear ratification of an amendment is amendment/ratification_status. Conflict of two certain assertions alone emits no uncertainty.

Temporal roles follow the verb/noun being asked about: recording, event/happening, submission, authorization/approval, observation, reporting, effective time. Multiple temporal roles in one support clause are not guessed; use a complete specific clause or mark genuine review ambiguity.

## Deictics and order/content
Bare this/it in a recording question denotes the owned record as a whole, not an arbitrarily selected claim. This/that entry or submission requires one unambiguous local antecedent; competing ordinal/named entries or explicit plurality rejects resolution. Explicit noun identity is preserved. Context outside the owned alias cannot resolve it.

What came next / what followed -> entry_order, subject entry, ordinal next, category explicit_question, state requested.
What did the second entry contain/say -> entry_content, subject entry, ordinal2.
What was entered first -> entry_content, subject entry, ordinal1: requested CONTENT plus ordinal referent, not pure order.
First/next and previous/later remain distinct. A temporal order of events must not be substituted for entry position. Missing ratification status is not content; content is not occurrence status.

## Evidence, completeness and canonical output
Every item's refs are all REF IDs supplied in that owned span; each atom uses that same exact ref set. Packet allowed/required evidence boundaries are checked. No context-only or invented refs. Every recognized finite source semantic atom must be represented exactly once; this guard checks completeness as well as submitted-atom grounding. Unsupported source meaning still requires reviewer judgment/ambiguity, not automatic gap invention.

Canonical producer output uses only span, claims, questions, uncertainty, status, refs. Questions and uncertainty contain stable strings encoding normalized category, subject, attribute, ordinal, relation, state, scope and unit. Claims/refs and atom strings are sorted. Equivalent atom support/rationale wording produces identical target bytes; different semantics produce different output. Source prose is never reconstructed by the model. Explicit nonoccurrence is represented within existing questions, not a new wire field.

source_uncertainty_present equals presence of explicit uncertainty atoms. review_ambiguity means inability to determine annotation, not uncertainty present in the source. Refused output has no items/atoms; examined-empty remains distinct, but this population is substantive only.

## Population, isolation and gates
Exactly the entire substantive producer inventory:32 TRAIN/32 DEV; no reserve/fallback. Only source-only packet files and administrative split/family maps are used for selection. Exclude TEST, adversarial, astronomy/ecology, sealed/final and regression. Before review freeze population, method and at least16 hard audits (eight per split), stratified by source semantic features/domain/template. Each fresh A/B/C reviews all64 once; at most one schema-only repair, no semantic retries. Fresh D receives only packet and A/B/C, and adjudicates hard16 plus every invalid/no-majority case. Shared model/filesystem limitations are explicit.

Freeze and commit all labels/canonical targets BEFORE legacy target comparison. Legacy projection uses this same finite interpreter with owned source context; no post-gold synonyms. Compare typed semantics, claims, refs and refusal. Agreement is curation_only. A strict subset legacy omission may be classified source-proven under-specification only if all machine extras pass finite exact-support grounding, all primaries/final labels validate, and consensus/adjudication is valid. Different meanings or unresolved projection stay excluded; neither source of labels is automatically privileged. Preserve diagnostics, never retrofit historical evidence.

Eligibility requires all three primaries valid, valid consensus/adjudication/support/canonical target, no review ambiguity, no unresolved material dispute, correct access and governance. TRAIN>=32, DEV>=16; all attainable structural templates; eight domains if available; gaps and uncertainty in both splits, multi-claim/evidence selection, zero evaluation leakage. Auditor46 TRAIN/24 DEV remains unchanged. Human PENDING; training_authorized=false; final_model_acceptance=false.
