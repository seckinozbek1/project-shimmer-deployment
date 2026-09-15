# Independent semantic review

Packet: review-fbdef51d9cc9e837c1bf87c1

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "MEMORANDUM\nSubject: retained observations\nDecision recorded: CLM-A: collection 61 recorded 77 entries (REF-1001).\nSupporting entry: No second claim was submitted.\nUnresolved matters: The date is absent. When was this recorded? The interpretation remains uncertain."
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
  "packet_id": "review-fbdef51d9cc9e837c1bf87c1",
  "input_sha256": "fbdef51d9cc9e837c1bf87c103bc2ae045de5ebd083c0e238941480c3cc34758",
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
