# Independent semantic review

Packet: review-c73a3ad1c3a6300de6fee92c

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "| Field | Content |\n|---|---|\n| Primary | CLM-C: delegation 67 is assigned 95 offered seats (REF-1003). |\n| Secondary | CLM-D: the same delegation 67 is assigned 97 offered seats (REF-1004). These statements conflict. The effective time is missing. When does it take effect? The interpretation remains uncertain. |\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s13c",
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
  "packet_id": "review-c73a3ad1c3a6300de6fee92c",
  "input_sha256": "c73a3ad1c3a6300de6fee92cd52669dbb938e3d0ab21720ac39b28ba16b1646e",
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
