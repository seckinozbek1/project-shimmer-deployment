# Independent semantic review

Packet: review-af8b0e9ecbfb49fdfe4a63ef

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
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
  "routed_rules": []
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-af8b0e9ecbfb49fdfe4a63ef",
  "input_sha256": "af8b0e9ecbfb49fdfe4a63ef9b18934c661a7c5fc53a901e3528d55c3dcc54d4",
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
