# Independent semantic review

Packet: review-cbc27d1040376cacb0c49c8b

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "1. Scope\n  1(a) CLM-A: observing station 77 recorded 125 exposures (REF-1001).\n  1(b) Exceptions\n    (i) No second claim was submitted.\n    (ii) The date is absent. When was this recorded? The recorder is unnamed. Who recorded it? The interpretation remains uncertain."
    }
  ],
  "context_only_spans": [],
  "supplied_refs": [
    "REF-1001"
  ],
  "required_refs": [
    "REF-1001"
  ],
  "routed_rules": [],
  "extraction": "1. Scope\n  1(a) CLM-A: observing station 77 recorded 125 exposures (REF-1001).\n  1(b) Exceptions\n    (i) No second claim was submitted.\n    (ii) The date is absent. When was this recorded? The recorder is unnamed. Who recorded it? The interpretation remains uncertain."
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
    "packet_id": "review-cbc27d1040376cacb0c49c8b",
    "input_sha256": "cbc27d1040376cacb0c49c8bd7a2dfcf9d09d7e240029cbc32301aef03a6edde",
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
