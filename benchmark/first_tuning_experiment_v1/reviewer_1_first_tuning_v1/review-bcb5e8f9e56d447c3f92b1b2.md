# Independent semantic review

Packet: review-bcb5e8f9e56d447c3f92b1b2

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "BEGIN REGISTER\nDEBIT OBSERVATION :: CLM-A: observing station 81 recorded 137 exposures (REF-1001).\nCREDIT OBSERVATION :: No second claim was submitted.\nMEMO ONLY :: The date is absent. When was this recorded? The interpretation remains uncertain.\nEND REGISTER"
    }
  ],
  "context_only_spans": [],
  "supplied_refs": [
    "REF-1001"
  ],
  "required_refs": [
    "REF-1001"
  ],
  "routed_rules": []
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-bcb5e8f9e56d447c3f92b1b2",
  "input_sha256": "bcb5e8f9e56d447c3f92b1b25a391ba13e17ae0f6d7c186eadda41bfdc311cf4",
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
