# Independent semantic review

Packet: review-2e9e21f03b9ec06e65ff55e4

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "RECORD{kind=primary; text=\"Unreadable entry for observing station 85.\"}\nRECORD{kind=secondary; text=\"[unrecoverable fragment]\"}\nRECORD{kind=qualification; text=\"The semantic content cannot be established.\"}"
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
  "binding": {
    "revision": "first-tuning-review-cohort-v2",
    "cohort_sha256": "7006edd3f293ca2a6cdcebe071a05d05ac02c9bd58259d7c07110de4bd45bb8d",
    "payload_sha256": "7acb192a6b5cbb3c046b4227154ea26db86b41e5e6f1be1bc556b8be1f850d69"
  },
  "review": {
    "packet_id": "review-2e9e21f03b9ec06e65ff55e4",
    "input_sha256": "2e9e21f03b9ec06e65ff55e48a60a890f52a116d82e5ff4386c8af4c99fca175",
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
