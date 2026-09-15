# Independent semantic review

Packet: review-d682ecdc79dae5ad3054a67d

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "Exception notice: the Test Lab inventory separates authorization from storage. CLM-A assigns Module Cedar authorized 20 signal cycles [REF-0001]; CLM-B assigns Module Elm stored 27 signal cycles [REF-0002]. Neither classification implies the other. The storage location has not been supplied. Where are these objects located? The scope of the authorization is ambiguous.\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s174",
      "text": "CONTEXT ONLY: neighboring record has REF-9999 and CONV-DISTRACTOR; neither is routed evidence or a policy for this task."
    }
  ],
  "supplied_refs": [
    "REF-0001",
    "REF-0002",
    "REF-9999"
  ],
  "required_refs": [
    "REF-0001",
    "REF-0002"
  ],
  "routed_rules": [],
  "extraction": "Exception notice: the Test Lab inventory separates authorization from storage. CLM-A assigns Module Cedar authorized 20 unrelated units [REF-0001]; CLM-B assigns Module Elm stored 27 signal cycles [REF-0002]. Neither classification implies the other. The storage location has not been supplied. Where are these objects located? The scope of the authorization is ambiguous."
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-d682ecdc79dae5ad3054a67d",
  "input_sha256": "d682ecdc79dae5ad3054a67df157556c4d266383198ff1bbd2619cb8dde953ee",
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
