# Independent semantic review

Packet: review-b49ae4bc4ef9a4618a74b8fd

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "Question: What was entered first?\nAnswer: CLM-A: fictional case 59 recorded 71 recorded events (REF-1001).\nQuestion: What followed?\nAnswer: CLM-B: fictional case 59 retained 76 recorded events (REF-1002).\nClerk note: The date is absent. When was this recorded? The recorder is unnamed. Who recorded it? The interpretation remains uncertain."
    }
  ],
  "context_only_spans": [],
  "supplied_refs": [
    "REF-1001",
    "REF-1002"
  ],
  "required_refs": [
    "REF-1001",
    "REF-1002"
  ],
  "routed_rules": [],
  "extraction": "Question: What was entered first?\nAnswer: CLM-A: fictional case 59 recorded 72 recorded events (REF-1001).\nQuestion: What followed?\nAnswer: CLM-B: fictional case 59 retained 76 recorded events (REF-1002).\nClerk note: The date is absent. When was this recorded? The recorder is unnamed. Who recorded it? The interpretation remains uncertain."
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-b49ae4bc4ef9a4618a74b8fd",
  "input_sha256": "b49ae4bc4ef9a4618a74b8fd347014ba1af5764041e0c38589ca6d720ca7c79c",
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
