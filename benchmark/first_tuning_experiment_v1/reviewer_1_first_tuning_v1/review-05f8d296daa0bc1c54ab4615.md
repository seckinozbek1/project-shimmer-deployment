# Independent semantic review

Packet: review-05f8d296daa0bc1c54ab4615

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "MEMORANDUM\nSubject: retained observations\nDecision recorded: CLM-A: fictional case 63 recorded 83 recorded events (REF-1001).\nSupporting entry: CLM-B: fictional case 63 retained 88 recorded events (REF-1002).\nUnresolved matters: The date is absent. When was this recorded? The interpretation remains uncertain."
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
  "extraction": "MEMORANDUM\nSubject: retained observations\nDecision recorded: CLM-A: fictional case 63 recorded 83 recorded events (REF-1001).\nSupporting entry: CLM-B: fictional case 63 retained 88 recorded events (REF-1002).\nUnresolved matters: The date is absent. When was this recorded? The interpretation remains uncertain."
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-05f8d296daa0bc1c54ab4615",
  "input_sha256": "05f8d296daa0bc1c54ab46152d297ffa098ffb22b41c9110893ac8003bcf0bbb",
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
