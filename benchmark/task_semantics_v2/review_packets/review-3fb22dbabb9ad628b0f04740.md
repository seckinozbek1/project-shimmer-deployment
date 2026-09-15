# Independent semantic review

Packet: review-3fb22dbabb9ad628b0f04740

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "RECORD{kind=primary; text=\"CLM-A: survey plot 86 recorded 152 quadrats (REF-1001).\"}\nRECORD{kind=secondary; text=\"CLM-B: survey plot 86 retained 157 quadrats (REF-1002).\"}\nRECORD{kind=qualification; text=\"The date is absent. When was this recorded? The recorder is unnamed. Who recorded it?\"}"
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
  "routed_rules": []
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-3fb22dbabb9ad628b0f04740",
  "input_sha256": "3fb22dbabb9ad628b0f04740f8f68a4f772e3589fbcb683bd5a25e242e3062c2",
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
