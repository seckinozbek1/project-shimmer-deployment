# Independent semantic review

Packet: review-822bffb7dbde687a4fc3115b

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "RECORD{kind=primary; text=\"Unreadable entry for survey plot 86.\"}\nRECORD{kind=secondary; text=\"[unrecoverable fragment]\"}\nRECORD{kind=qualification; text=\"The semantic content cannot be established.\"}"
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
  "packet_id": "review-822bffb7dbde687a4fc3115b",
  "input_sha256": "822bffb7dbde687a4fc3115bd3e21dcef9af8925b1e759678d3cd9c85adf70a4",
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
