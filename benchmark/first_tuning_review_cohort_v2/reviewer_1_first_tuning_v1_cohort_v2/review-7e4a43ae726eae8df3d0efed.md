# Independent semantic review

Packet: review-7e4a43ae726eae8df3d0efed

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "MEMORANDUM\nSubject: retained observations\nDecision recorded: CLM-A: vraxlet 64 recorded 86 flomquils (REF-1001).\nSupporting entry: CLM-B: vraxlet 64 retained 91 flomquils (REF-1002).\nUnresolved matters: The date is absent. When was this recorded?"
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
  "extraction": "MEMORANDUM\nSubject: retained observations\nDecision recorded: CLM-A: vraxlet 64 recorded 86 flomquils (REF-1001).\nSupporting entry: CLM-B: vraxlet 64 retained 91 flomquils (REF-1002).\nUnresolved matters: The date is absent. When was this recorded? The entry was approved by an external director."
}
```

## Response template (pending, not a submitted review)

```json
{
  "binding": {
    "revision": "first-tuning-review-cohort-v2",
    "cohort_sha256": "7006edd3f293ca2a6cdcebe071a05d05ac02c9bd58259d7c07110de4bd45bb8d",
    "payload_sha256": "5f64f06e23c69aaab87ed4f4f517471bf3d81387bb58f99c848d6077ecae37d6"
  },
  "review": {
    "packet_id": "review-7e4a43ae726eae8df3d0efed",
    "input_sha256": "7e4a43ae726eae8df3d0efed21fadcd71830a0be2c0c929974deec18e18545e4",
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
}
```
