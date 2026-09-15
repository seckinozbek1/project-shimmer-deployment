# Fresh producer V3 curation review
Read POLICY.md and SCHEMA.json, then every assigned packet. Only your assigned workspace may be read/written. No gold, prior outputs, other reviewers, admin maps, splits, model tools, network, git or delegation. This is fresh-context label curation, not independent test evidence.

Write exactly one reviews/<packet_id>.json per packet, once. Do not overwrite or semantically retry. You may write a local serializer after actually reading every packet and deciding its annotation independently; it must serialize your per-packet judgments, not use prior answers or replace your reading with a source-answer algorithm.

Outer keys: protocol="producer-coverage-amendment-v3", policy="producer-semantic-policy-v3", evidence_kind="training_label_curation_evidence", use="curation_only", packet_id, input_sha256 (copy exact packet binding), slot A/B/C, provenance="machine_agent_primary", reviewed_at ISO UTC, label, rationale.
label keys: status examined/refused; items; source_uncertainty_present boolean; review_ambiguity boolean.
Each examined item: span, claims, refs, gap_atoms, uncertainty_atoms. One per owned alias in input order; all explicit CLM IDs and owned refs. No context extraction. Empty/refusal semantics per policy.

Each atom has exactly the fields in SCHEMA.json. support is an exact owned source substring including all necessary negation/ordinal/modality. Prefer the complete qualifying sentence/question. Atom refs equal all owned item's refs. origin source_explicit, scope owned_record, relation null, unit null. Subject/ordinal/attribute/category/state must follow POLICY.md.

Important distinctions: no submitted entry is explicit_nonoccurrence/submission_occurrence/not_submitted; missing date is missing_information/(the correct time-role)/unspecified. Unknown whether an occurrence happened is uncertainty/unknown, not absence. Conflict alone adds no uncertainty. A recording question is recording_time, not event_time. What was entered first asks entry_content with ordinal1. What followed asks entry_order with ordinal next. Explicit question category/state is explicit_question/requested for order/content inquiries. An unqualified absent date resolves to recording_time only with an immediately following unambiguous recording-time question about the same owned record. Preserve both source claims even if contradictory.

source_uncertainty_present reflects actual uncertainty atoms. Review ambiguity is only unresolved annotation semantics; it is not automatically caused by source uncertainty.

On completion report count, ambiguity count and isolation attestation. No access to parent code or other directories for validation. Do not copy code from outside. Use only assigned packet sources and policy. The parent validates bindings, exact support, finite semantics and canonical wire output separately.

## Structural headings
Standalone titles, section labels, table headings and non-propositional prefixes before a colon do not create semantic atoms from their wording. Examples: Pending issues; Outstanding items; Unknowns; Open questions; Results; Status. Preserve the body independently. A heading-position segment with a finite proposition remains content: The status is unknown; No further submission was recorded; The event date remains unavailable; Three matters remain unresolved. Preserve negation/modality. Do not infer content from neighboring text. Finite copulas/verbs, explicit questions and CLM assertions distinguish content from labels; participles alone are not finite propositions. If a content-bearing proposition cannot be represented by the frozen ontology, mark review ambiguity rather than pretending it is structural or inventing an attribute. No phrase-specific exceptions.
