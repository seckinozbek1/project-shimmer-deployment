# Independent semantic review

Packet: review-a5b3647ec31b0ec905c59d1d

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "| Sequence | Evidence |\n|---|---|\n"
    },
    {
      "alias": "s22",
      "text": "| 1 | CLM-A: observing station 69 recorded 101 exposures (REF-1001). |\n"
    },
    {
      "alias": "s69",
      "text": "| 2 | No second claim was submitted. |\n"
    },
    {
      "alias": "s90",
      "text": "| 3 | The date is absent. When was this recorded? The interpretation remains uncertain. |"
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
  "extraction": "| Sequence | Evidence |\n|---|---|\n| 1 | CLM-A: observing station 69 recorded 101 exposures (REF-1001). |\n| 2 | No second claim was submitted. |\n| 3 |  |"
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
    "packet_id": "review-a5b3647ec31b0ec905c59d1d",
    "input_sha256": "a5b3647ec31b0ec905c59d1d56df013cf5c56f0e866c15adea74718b1dbddb9a",
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
