# Independent semantic review

Packet: review-eb3a399eceda8ef53b4aaf96

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "| Field | Content |\n|---|---|\n"
    },
    {
      "alias": "s1e",
      "text": "| Primary | Divider for survey plot 66. |\n"
    },
    {
      "alias": "s48",
      "text": "| Secondary | No semantic entry. End marker. |"
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
  "packet_id": "review-eb3a399eceda8ef53b4aaf96",
  "input_sha256": "eb3a399eceda8ef53b4aaf963518f19a359a6b54dfdf9f8f53c9b3124c45dd6d",
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
