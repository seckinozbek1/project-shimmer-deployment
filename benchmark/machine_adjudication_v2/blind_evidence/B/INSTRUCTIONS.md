# Independent machine semantic review V2

Use ONLY your assigned packet source/extraction. No authored targets, V1 reviews,
other primary reviews, mappings, external knowledge or repository search. This is
machine reasoning, never human review. Produce exactly one output per packet.

## Output and evidence

Use MACHINE_SCHEMA.json. Preserve packet ID, active binding and input hash. All
producer judgments are EXTRACTED, EMPTY or INSUFFICIENT_EVIDENCE, never MATCH.
Auditor judgments are MATCH/DIVERGENCE/OMISSION/ADDITION/INSUFFICIENT_EVIDENCE.
Refusal target is {"items":[],"status":"refused"}. A confident refusal can be an
unambiguous annotation. Source uncertainty does not imply review ambiguity.

Producer targets have one item per owned source alias: span, claims, questions,
uncertainty, status, refs. Claims are explicit CLM IDs. Questions and uncertainty
retain concise readable wording, but typed atoms carry comparison semantics. Do not
copy/reconstruct whole source prose. Empty spans have empty arrays and status empty.
All refs explicitly cited in that owned span belong in its refs; context-only refs
are never owned. Each atom uses its item's exact refs and span (possibly no refs
on a standalone qualification span); source alias itself binds the observation.

Auditor target has one item: finding, ref_ids, reasoning, severity, confidence.
Return ALL packet input.required_refs in ref_ids, even if the change described in
your reasoning concerns only one claim. These are response/item-level obligations,
not a list of only the changed claim's citation. Every returned ref must be available
and owned; never cite context-only references. Additional applicable owned refs may
be included. MATCH severity low; other severities low/medium/high. Confidence is
CONFIDENT or UNCERTAIN about the comparison, separate from uncertainty in the source.
Refusal items=[] has no item refs; do not fabricate citations/rules to fill a refusal.

Different quantities alone do not mean divergence; labels/entities/units and source
relations matter. A source gap faithfully preserved is not an omission. Do not invent
facts or governance rule IDs. Never assume unseen continuation of an incomplete artifact.
If the correct annotation itself cannot be determined, set review_ambiguity=true.

## Producer typed atoms

Provide flat gap_atoms and uncertainty_atoms arrays tied to owned aliases. Each atom:
{type, subject, target, scope, span, refs, origin, unit, wording(optional)}.
Use scope=owned_record, origin=source_explicit, unit=null for the current packet gap/
uncertainty categories. Wording is explanatory only. Exact typed fields carry meaning.
Do not infer an atom without explicit source support. Each question has one gap atom
and each uncertainty phrase one uncertainty atom; do not duplicate a single gap simply
because it appears as both a statement and a question.

Supported minimal gap ontology: type=missing_information. Targets:
- observation_date: explicitly unavailable observation date;
- recording_date: absent date/when the described record was recorded;
- reporting_date: explicitly missing reporting date/date of report;
- effective_time: missing effective time/period or unresolved when something takes effect;
- recorder: unnamed recorder/who recorded it.
Subject is owned_record unless the effective-time gap explicitly concerns an amendment,
then subject=amendment. Preserve distinct date referents; do not map date to quantity,
recorder, uncertain date or conflicting values. Unsupported meanings must not be guessed.

Supported source uncertainty ontology:
- type=unknown, target=interpretation, subject=owned_record for explicitly uncertain
  interpretation; subject=second_entry when explicitly limited to the second entry;
- type=unknown, target=ratification, subject=amendment for explicit uncertainty whether
  an amendment was ratified;
- type=conflicting, target=assertions, subject=owned_record for explicit conflicting
  source statements. Preserve both conflicting claim IDs; do not resolve the conflict.
These are generic semantic types, not packet-specific labels. Source uncertainty types
not supported by your evidence must not be added. Auditor gap_atoms/uncertainty_atoms
may be empty: the existing auditor typed relation/reason task is preserved.

## Two separate flags

source_uncertainty_present=true when the owned SOURCE explicitly contains uncertainty
or conflict. A missing information gap alone is not an uncertainty assertion.
review_ambiguity=true only when you cannot determine the appropriate annotation.
You may correctly annotate uncertain/conflicting source content with review_ambiguity=false.
Do not emit the legacy conflated ambiguity field.

Typed auditor reason_components use only: preserved_claim, missing_claim, added_claim,
changed_label, changed_quantity, changed_unit, gap_preserved, gap_omitted,
evidence_insufficient, unsupported_attribution, ambiguity, uncertainty_preserved,
uncertainty_omitted. Select supported components; rationale wording is not consensus.
