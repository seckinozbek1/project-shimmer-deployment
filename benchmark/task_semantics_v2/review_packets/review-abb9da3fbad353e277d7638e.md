# Independent semantic review

Packet: review-abb9da3fbad353e277d7638e

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "RECORD{kind=primary; text=\"CLM-C: vraxlet 88 is assigned 158 flomquils (REF-1003).\"}\nRECORD{kind=secondary; text=\"CLM-D: the same vraxlet 88 is assigned 160 flomquils (REF-1004).\"}\nRECORD{kind=qualification; text=\"These statements conflict. The effective time is missing. When does it take effect? The interpretation remains uncertain.\"}\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s153",
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
  "packet_id": "review-abb9da3fbad353e277d7638e",
  "input_sha256": "abb9da3fbad353e277d7638e33e026422d9480dd792237ed4db05de4ede2e971",
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
