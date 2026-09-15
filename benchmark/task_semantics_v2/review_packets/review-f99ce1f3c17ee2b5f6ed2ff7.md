# Independent semantic review

Packet: review-f99ce1f3c17ee2b5f6ed2ff7

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "Interview transcript, Test Lab. First speaker: \"CLM-A says Module Cedar accepted 20 signal cycles; see REF-0001.\" Second speaker: \"CLM-B says Module Elm declined 27 signal cycles; see REF-0002.\" Recorder asks: \"The recorder is not identified. Who recorded this interview?\" An unsigned marginal note reads: \"The attribution of the marginal note is uncertain.\"\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s168",
      "text": "CONTEXT ONLY: neighboring record has REF-9999 and CONV-DISTRACTOR; neither is routed evidence or a policy for this task."
    }
  ],
  "supplied_refs": [
    "REF-0001",
    "REF-0002",
    "REF-9999"
  ],
  "required_refs": [
    "REF-0001",
    "REF-0002"
  ],
  "routed_rules": [],
  "extraction": "Interview transcript, Test Lab. First speaker: \"CLM-A says Module Cedar accepted 20 signal cycles; see REF-0001.\" Second speaker: \"CLM-B says Module Elm declined 27 signal cycles; see REF-0002.\" Recorder asks: \"\" An unsigned marginal note reads: \"The attribution of the marginal note is uncertain.\""
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-f99ce1f3c17ee2b5f6ed2ff7",
  "input_sha256": "f99ce1f3c17ee2b5f6ed2ff7e9352554376351e3484fb6d65495320d68a6d6c4",
  "review_version": "semantic-benchmark-v2",
  "reviewer_id": null,
  "reviewer_kind": null,
  "independence_attestation": false,
  "reviewed_at": null,
  "semantic_target": null,
  "semantic_judgment": null,
  "reason_components": [],
  "rationale": null,
  "ambiguity": null,
  "formatting_judgment": "not_assessed"
}
```
