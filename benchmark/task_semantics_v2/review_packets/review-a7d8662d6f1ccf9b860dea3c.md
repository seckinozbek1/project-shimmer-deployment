# Independent semantic review

Packet: review-a7d8662d6f1ccf9b860dea3c

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "- CLM-A: service desk 46 recorded 32 delivery windows (REF-1001).\n- CLM-B: service desk 46 retained 37 delivery windows (REF-1002).\n- The date is absent. When was this recorded?"
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
  "extraction": "- CLM-A: service desk 46 recorded 32 delivery windows (REF-1001).\n- CLM-B: service desk 46 retained 37 delivery windows (REF-1002).\n- The date is absent. When was this recorded? The entry was approved by an external director."
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-a7d8662d6f1ccf9b860dea3c",
  "input_sha256": "a7d8662d6f1ccf9b860dea3cafec02ece15df16e51b2f4548603b95380259414",
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
