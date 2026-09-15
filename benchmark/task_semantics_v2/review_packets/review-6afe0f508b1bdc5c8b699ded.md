# Independent semantic review

Packet: review-6afe0f508b1bdc5c8b699ded

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "| Sequence | Evidence |\n|---|---|\n"
    },
    {
      "alias": "s22",
      "text": "| 1 | CLM-A: delegation 71 recorded 107 offered seats (REF-1001). |\n"
    },
    {
      "alias": "s66",
      "text": "| 2 | CLM-B: delegation 71 retained 112 offered seats (REF-1002). |\n"
    },
    {
      "alias": "saa",
      "text": "| 3 | The date is absent. When was this recorded? The recorder is unnamed. Who recorded it? The interpretation remains uncertain. |"
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
  "extraction": "| Sequence | Evidence |\n|---|---|\n| 1 | CLM-A: delegation 71 recorded 108 offered seats (REF-1001). |\n| 2 | CLM-B: delegation 71 retained 112 offered seats (REF-1002). |\n| 3 | The date is absent. When was this recorded? The recorder is unnamed. Who recorded it? The interpretation remains uncertain. |"
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-6afe0f508b1bdc5c8b699ded",
  "input_sha256": "6afe0f508b1bdc5c8b699ded2d0c06ca31d09aa5b15ec9a2c5f375f67e3dc415",
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
