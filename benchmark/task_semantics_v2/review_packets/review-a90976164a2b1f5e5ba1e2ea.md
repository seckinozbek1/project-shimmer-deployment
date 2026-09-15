# Independent semantic review

Packet: review-a90976164a2b1f5e5ba1e2ea

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "Interview transcript, Archive Office. First speaker: \"CLM-A says Collection Haze accepted 24 catalogue entries; see REF-0001.\" Second speaker: \"CLM-B says Collection Iris declined 31 catalogue entries; see REF-0002.\" Recorder asks: \"The recorder is not identified. Who recorded this interview?\" An unsigned marginal note reads: \"The attribution of the marginal note is uncertain.\"\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s17e",
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
  "extraction": "Interview transcript, Archive Office. First speaker: \"CLM-A says Collection Haze declined 24 catalogue entries; see REF-0001.\" Second speaker: \"CLM-B says Collection Iris accepted 31 catalogue entries; see REF-0002.\" Recorder asks: \"The recorder is not identified. Who recorded this interview?\" An unsigned marginal note reads: \"The attribution of the marginal note is uncertain.\""
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-a90976164a2b1f5e5ba1e2ea",
  "input_sha256": "a90976164a2b1f5e5ba1e2eaaf9df8462e21bc93a992ec5af814c78e98aeb6b7",
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
