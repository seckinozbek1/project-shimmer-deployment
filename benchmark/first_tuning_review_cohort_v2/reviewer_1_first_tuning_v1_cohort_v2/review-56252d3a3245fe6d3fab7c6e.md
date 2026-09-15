# Independent semantic review

Packet: review-56252d3a3245fe6d3fab7c6e

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "RECORD{kind=primary; text=\"CLM-C: survey plot 86 is assigned 152 quadrats (REF-1003).\"}\nRECORD{kind=secondary; text=\"CLM-D: the same survey plot 86 is assigned 154 quadrats (REF-1004).\"}\nRECORD{kind=qualification; text=\"These statements conflict. The effective time is missing. When does it take effect? The interpretation remains uncertain.\"}\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s159",
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
    "payload_sha256": "5f64f06e23c69aaab87ed4f4f517471bf3d81387bb58f99c848d6077ecae37d6"
  },
  "review": {
    "packet_id": "review-56252d3a3245fe6d3fab7c6e",
    "input_sha256": "56252d3a3245fe6d3fab7c6efb4938d2a13dd62538659fef8ed376564271767c",
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
