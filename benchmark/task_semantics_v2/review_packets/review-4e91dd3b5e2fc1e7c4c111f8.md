# Independent semantic review

Packet: review-4e91dd3b5e2fc1e7c4c111f8

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "08:10 event opened: CLM-A: filing office 54 recorded 56 notices (REF-1001).\n09:25 event amended: CLM-B: filing office 54 retained 61 notices (REF-1002).\n11:40 follow-up: The date is absent. When was this recorded?"
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
  "extraction": "08:10 event opened: CLM-A: filing office 54 recorded 56 notices (REF-1001).\n09:25 event amended: CLM-B: filing office 54 retained 61 notices (REF-1002).\n11:40 follow-up: "
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-4e91dd3b5e2fc1e7c4c111f8",
  "input_sha256": "4e91dd3b5e2fc1e7c4c111f80bc8c72142ae6f736083791e28e17472e30809bc",
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
