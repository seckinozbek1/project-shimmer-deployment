# Independent semantic review

Packet: review-da3e305bdd181a4c3036c9b8

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "08:10 event opened: CLM-A: vraxlet 56 recorded 62 flomquils (REF-1001).\n09:25 event amended: CLM-B: vraxlet 56 retained 67 flomquils (REF-1002).\n11:40 follow-up: The date is absent. When was this recorded? The recorder is unnamed. Who recorded it?"
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
  "extraction": "08:10 event opened: CLM-A: vraxlet 56 recorded 63 flomquils (REF-1001).\n09:25 event amended: CLM-B: vraxlet 56 retained 67 flomquils (REF-1002).\n11:40 follow-up: The date is absent. When was this recorded? The recorder is unnamed. Who recorded it?"
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-da3e305bdd181a4c3036c9b8",
  "input_sha256": "da3e305bdd181a4c3036c9b857b7f05cbe008f22cb99a5182f24c0223570acaf",
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
