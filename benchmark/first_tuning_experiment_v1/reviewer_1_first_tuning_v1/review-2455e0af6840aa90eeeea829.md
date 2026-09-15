# Independent semantic review

Packet: review-2455e0af6840aa90eeeea829

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "Opening statement: CLM-A: survey plot 74 recorded 116 quadrats (REF-1001).\n\n| Supplement | Content |\n|---|---|\n"
    },
    {
      "alias": "s6f",
      "text": "| Detail | CLM-B: survey plot 74 retained 121 quadrats (REF-1002). |"
    },
    {
      "alias": "sb3",
      "text": "\n\nClosing qualification: The date is absent. When was this recorded? The recorder is unnamed. Who recorded it?"
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
  "packet_id": "review-2455e0af6840aa90eeeea829",
  "input_sha256": "2455e0af6840aa90eeeea82932132576ddc7c3f613f72ef20af9a5a3d3cb23fa",
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
