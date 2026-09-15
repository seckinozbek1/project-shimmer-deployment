# Independent semantic review

Packet: review-4a85ff36b5e8decdd5ffc954

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
      "text": "| 1 | CLM-A: sensor bank 72 recorded 110 pulses (REF-1001). |\n"
    },
    {
      "alias": "s60",
      "text": "| 2 | CLM-B: sensor bank 72 retained 115 pulses (REF-1002). |\n"
    },
    {
      "alias": "s9e",
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
  "routed_rules": [],
  "extraction": "| Sequence | Evidence |\n|---|---|\n| 1 | CLM-A: sensor bank 72 recorded 110 pulses (REF-1001). |\n| 2 | CLM-B: sensor bank 72 retained 115 pulses (REF-1002). |\n| 3 |  |"
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-4a85ff36b5e8decdd5ffc954",
  "input_sha256": "4a85ff36b5e8decdd5ffc95462c18d6e49c4af953d06bb44ab8d5bd05f203472",
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
