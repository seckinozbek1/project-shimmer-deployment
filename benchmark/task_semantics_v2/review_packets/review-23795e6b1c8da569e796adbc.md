# Independent semantic review

Packet: review-23795e6b1c8da569e796adbc

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "| Sequence | Evidence |\n|---|---|\n| 1 | CLM-C: sensor bank 72 is assigned 110 pulses (REF-1003). |\n| 2 | CLM-D: the same sensor bank 72 is assigned 112 pulses (REF-1004). |\n| 3 | These statements conflict. The effective time is missing. When does it take effect? The interpretation remains uncertain. |\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s130",
      "text": "| External | Content |\n|---|---|\n| CONTEXT ONLY | CLM-Z: an unrelated neighbor lists a separate observation (REF-9999). |"
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
  "packet_id": "review-23795e6b1c8da569e796adbc",
  "input_sha256": "23795e6b1c8da569e796adbc9974ac378da917efe80aeb0fd93a9417e3a1092f",
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
