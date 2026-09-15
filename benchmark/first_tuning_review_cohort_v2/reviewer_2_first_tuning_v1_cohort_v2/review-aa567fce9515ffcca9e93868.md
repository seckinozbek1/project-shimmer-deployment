# Independent semantic review

Packet: review-aa567fce9515ffcca9e93868

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "08:10 event opened: CLM-C: collection 53 is assigned 53 entries (REF-1003).\n09:25 event amended: CLM-D: the same collection 53 is assigned 55 entries (REF-1004).\n11:40 follow-up: These statements conflict. The effective time is missing. When does it take effect? The interpretation remains uncertain.\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s12e",
      "text": "CONTEXT ONLY: CLM-Z: an unrelated neighbor lists a separate observation (REF-9999)."
    }
  ],
  "supplied_refs": [
    "REF-1003",
    "REF-1004",
    "REF-9999"
  ],
  "required_refs": [
    "REF-1003",
    "REF-1004"
  ],
  "routed_rules": []
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
    "packet_id": "review-aa567fce9515ffcca9e93868",
    "input_sha256": "aa567fce9515ffcca9e9386812b2bb54352171e34782bb8796dcdb1e48feea29",
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
