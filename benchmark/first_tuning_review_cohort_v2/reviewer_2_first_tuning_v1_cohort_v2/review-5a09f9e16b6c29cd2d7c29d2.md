# Independent semantic review

Packet: review-5a09f9e16b6c29cd2d7c29d2

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "MEMORANDUM\nSubject: retained observations\nDecision recorded: CLM-A: filing office 62 recorded 80 notices (REF-1001).\nSupporting entry: CLM-B: filing office 62 retained 85 notices (REF-1002).\nUnresolved matters: The date is absent. When was this recorded? The recorder is unnamed. Who recorded it?"
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
  "extraction": "MEMORANDUM\nSubject: retained observations\nDecision recorded: CLM-A: filing office 62 recorded 81 notices (REF-1001).\nSupporting entry: CLM-B: filing office 62 retained 85 notices (REF-1002).\nUnresolved matters: The date is absent. When was this recorded? The recorder is unnamed. Who recorded it?"
}
```

## Response template (pending, not a submitted review)

```json
{
  "binding": {
    "revision": "first-tuning-review-cohort-v2",
    "cohort_sha256": "7006edd3f293ca2a6cdcebe071a05d05ac02c9bd58259d7c07110de4bd45bb8d",
    "payload_sha256": "7acb192a6b5cbb3c046b4227154ea26db86b41e5e6f1be1bc556b8be1f850d69"
  },
  "review": {
    "packet_id": "review-5a09f9e16b6c29cd2d7c29d2",
    "input_sha256": "5a09f9e16b6c29cd2d7c29d235d4e9a0ab1ba6a155ceffb7b872e9695561e603",
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
