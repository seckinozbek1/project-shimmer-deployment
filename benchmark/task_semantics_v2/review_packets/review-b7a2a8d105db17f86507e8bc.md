# Independent semantic review

Packet: review-b7a2a8d105db17f86507e8bc

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "CLM-A: Module Cedar planned 20 signal cycles (REF-0001); CLM-B: Module Elm reported 27 signal cycles (REF-0002). The observation date is unavailable. What is the observation date? The interpretation of the second entry remains unresolved.\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "sf0",
      "text": "CONTEXT ONLY: neighboring record has REF-9999 and CONV-DISTRACTOR; neither is routed evidence or a policy for this task."
    }
  ],
  "supplied_refs": [
    "REF-0001",
    "REF-0002",
    "REF-9999"
  ],
  "required_refs": [],
  "routed_rules": [],
  "extraction": "paired_register / Test Lab: [extraction incomplete]"
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-b7a2a8d105db17f86507e8bc",
  "input_sha256": "b7a2a8d105db17f86507e8bc66315694b6c5142e322685b3a4cda148a3518308",
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
