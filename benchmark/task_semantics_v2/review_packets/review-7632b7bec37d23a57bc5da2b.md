# Independent semantic review

Packet: review-7632b7bec37d23a57bc5da2b

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
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
  "routed_rules": [],
  "extraction": "| Field | Content |\n|---|---|\n| Primary | CLM-A: delegation 67 recorded 95 offered seats (REF-1001). |\n| Secondary | CLM-B: delegation 67 retained 100 offered seats (REF-1002). The date is absent. When was this recorded? The interpretation remains uncertain. | The entry was approved by an external director."
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-7632b7bec37d23a57bc5da2b",
  "input_sha256": "7632b7bec37d23a57bc5da2bb1ab6d7f08311ae1677432823a491713763329e1",
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
