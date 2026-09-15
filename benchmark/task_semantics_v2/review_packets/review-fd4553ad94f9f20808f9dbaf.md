# Independent semantic review

Packet: review-fd4553ad94f9f20808f9dbaf

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "1. Scope\n  1(a) CLM-A: service desk 79 recorded 131 delivery windows (REF-1001).\n  1(b) Exceptions\n    (i) CLM-B: service desk 79 retained 136 delivery windows (REF-1002).\n    (ii) The date is absent. When was this recorded? The interpretation remains uncertain."
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
  "routed_rules": [],
  "extraction": "1. Scope\n  1(a) CLM-A: service desk 79 recorded 131 delivery windows (REF-1001).\n  1(b) Exceptions\n    (i) CLM-B: service desk 79 retained 136 delivery windows (REF-1002).\n    (ii) The date is absent. When was this recorded? The interpretation remains uncertain."
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-fd4553ad94f9f20808f9dbaf",
  "input_sha256": "fd4553ad94f9f20808f9dbaf43cfdc9abd275024b7280acb641949e1385c0326",
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
