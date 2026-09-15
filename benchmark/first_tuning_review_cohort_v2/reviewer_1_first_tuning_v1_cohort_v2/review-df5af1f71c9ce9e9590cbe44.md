# Independent semantic review

Packet: review-df5af1f71c9ce9e9590cbe44

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "MEMORANDUM\nSubject: retained observations\nDecision recorded: CLM-C: vraxlet 64 is assigned 86 flomquils (REF-1003).\nSupporting entry: CLM-D: the same vraxlet 64 is assigned 88 flomquils (REF-1004).\nUnresolved matters: These statements conflict. The effective time is missing. When does it take effect? The interpretation remains uncertain.\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s155",
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
    "packet_id": "review-df5af1f71c9ce9e9590cbe44",
    "input_sha256": "df5af1f71c9ce9e9590cbe44176f5ca098290e910eb1b36a054a985c887c2b60",
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
