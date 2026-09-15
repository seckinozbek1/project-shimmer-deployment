# Independent semantic review

Packet: review-85218b2bac49fd06e75fb4f5

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "| Sequence | Evidence |\n|---|---|\n"
    },
    {
      "alias": "s22",
      "text": "| 1 | CLM-A: survey plot 70 recorded 104 quadrats (REF-1001). |\n"
    },
    {
      "alias": "s62",
      "text": "| 2 | CLM-B: survey plot 70 retained 109 quadrats (REF-1002). |\n"
    },
    {
      "alias": "sa2",
      "text": "| 3 | The date is absent. When was this recorded? |"
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
  "routed_rules": []
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-85218b2bac49fd06e75fb4f5",
  "input_sha256": "85218b2bac49fd06e75fb4f5c7a6551acc3df7c9414c10ccd516e3670c1191d4",
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
