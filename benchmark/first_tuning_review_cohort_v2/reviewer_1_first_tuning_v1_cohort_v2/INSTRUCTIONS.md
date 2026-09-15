# Independent evidence review

Please review each supplied packet using only its source and evidence. Do not look
up authored answers, other people's responses or external domain information.
These are synthetic examples, not medical, legal or other professional advice.

Open either the Markdown or JSON packet. They contain the same input. Complete the
blank response template in a separate JSON file. Keep the packet ID, input hash and
review version unchanged. Enter your reviewer ID, human reviewer kind, independence
attestation and review date with time zone. Only attest independence if you are a
human who did not author the example and have not consulted an answer key or another
reviewer's judgment. An AI system cannot supply an independent human review.

## Extraction packets (producer)

For each owned span, list its explicit claim IDs, information gaps/questions,
uncertainty and applicable supplied evidence references. A span can contain several
claims. Context-only spans are not yours to extract. Do not reconstruct or copy
source prose: the supplied span alias identifies it.

Use one item per owned alias with fields `span`, `claims`, `questions`, `uncertainty`,
`status`, `refs`. Use `extracted` when a semantic array is populated; use `empty`
when the span has been examined and genuinely has no semantic content. Missing a
span is not the same as examining it and finding it empty.

## Comparison packets (auditor)

Compare the owned original with the supplied extraction for faithful preservation:

- MATCH: the extraction preserves the original.
- DIVERGENCE: content, labels, quantities, entities or units changed.
- OMISSION: required source information was dropped.
- ADDITION: unsupported information was added.
- INSUFFICIENT_EVIDENCE: a determination is not supported; refuse rather than guess.

Select exact applicable references from the supplied set and give a concise reason.
The target item uses `finding`, `ref_ids`, `reasoning`, `severity`, `confidence`.
Severity is `low`, `medium` or `high`; MATCH uses `low`. Confidence is `CONFIDENT`
or `UNCERTAIN` about your comparison, not a claim that every source statement is certain.

Different numbers do not automatically mean DIVERGENCE. Equal numbers do not
automatically mean MATCH. Missing information already present in the source is not
automatically an extraction omission. Do not invent reference or rule IDs, attribute
an unrouted rule, or turn this into an assessment of regulatory compliance.

## Refusal, ambiguity and explanation

When evidence genuinely cannot support completion, set the semantic judgment to
INSUFFICIENT_EVIDENCE and use `{"items":[],"status":"refused"}` as the target.
Record ambiguity honestly. A missing datum can itself be faithfully preserved;
it does not always require refusing the entire task.

Identify the reason components that actually apply: preserved/missing/added claim;
changed label/quantity/unit; gap preserved/omitted; evidence insufficient;
unsupported attribution; ambiguity; uncertainty preserved/omitted. Use their
underscore spellings in `reason_components`. Explain your judgment in `rationale`.

Keep semantic judgment separate from `formatting_judgment` (`valid`, `invalid`, or
`not_assessed`). Do not let fluent prose substitute for evidence. A target should
contain one complete JSON object, without fences or trailing explanation.

Return completed response JSON files to the administrator. Do not overwrite the
blank packet or put responses into the packet export folder. No model execution,
training, cloud access or API use is needed to perform this review.

## Return the supplied envelope

Fill the `review` object in the packet response template. Preserve the surrounding
`binding` object exactly as supplied: its opaque revision and hashes identify the
material you received. Return the complete envelope. Do not copy an older response
template or remove the binding. These fields contain no semantic answers.
