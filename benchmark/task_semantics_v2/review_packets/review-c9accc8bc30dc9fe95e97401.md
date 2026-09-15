# Independent semantic review

Packet: review-c9accc8bc30dc9fe95e97401

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "Opening statement: Divider for delegation 75.\n\n| Supplement | Content |\n|---|---|\n"
    },
    {
      "alias": "s52",
      "text": "| Detail | No semantic entry. |"
    },
    {
      "alias": "s71",
      "text": "\n\nClosing qualification: End marker."
    }
  ],
  "context_only_spans": [],
  "supplied_refs": [],
  "required_refs": [],
  "routed_rules": []
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-c9accc8bc30dc9fe95e97401",
  "input_sha256": "c9accc8bc30dc9fe95e97401bd761d3fcdfb67bc800ccc879e8faaba03f3e0b3",
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
