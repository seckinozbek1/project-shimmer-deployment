# Independent semantic review

Packet: review-5b9b92ec688ad4c9ca7b01a8

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "Exception notice: the Accord Office inventory separates authorization from storage. CLM-A assigns Leto authorized 14 delivery lots [REF-0001]; CLM-B assigns Mira stored 14 delivery lots [REF-0002]. Neither classification implies the other. The storage location has not been supplied. Where are these objects located? The scope of the authorization is ambiguous.\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s16b",
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
  "extraction": "Exception notice: the Accord Office inventory separates authorization from storage. CLM-A assigns Leto authorized 14 delivery lots [REF-0001]; CLM-B assigns Mira stored 14 delivery lots [REF-0002]. Neither classification implies the other. The storage location has not been supplied. Where are these objects located? The scope of the authorization is ambiguous."
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-5b9b92ec688ad4c9ca7b01a8",
  "input_sha256": "5b9b92ec688ad4c9ca7b01a8f617798fd96cb207166b42e5b84ed88eb31dc8d1",
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
