# Independent semantic review

Packet: review-a3e8aa85f45fae8216e0de2e

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
      "text": "| Primary | CLM-A: delegation 67 recorded 95 offered seats (REF-1001). |\n"
    },
    {
      "alias": "s67",
      "text": "| Secondary | CLM-B: delegation 67 retained 100 offered seats (REF-1002). The date is absent. When was this recorded? The interpretation remains uncertain. |"
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
  "packet_id": "review-a3e8aa85f45fae8216e0de2e",
  "input_sha256": "a3e8aa85f45fae8216e0de2e28e5843a64e4c74f1ce6fc2655d08f8365acab99",
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
