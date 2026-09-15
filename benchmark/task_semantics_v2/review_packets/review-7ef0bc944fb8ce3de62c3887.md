# Independent semantic review

Packet: review-7ef0bc944fb8ce3de62c3887

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "CLM-A: Case Alder planned 18 recorded observations (REF-0001); CLM-B: Case Birch reported 18 recorded observations (REF-0002). The observation date is unavailable. What is the observation date? The interpretation of the second entry remains unresolved.\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "sfe",
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
  "extraction": "CLM-A: Case Alder planned 18 recorded observations (REF-0001); CLM-B: Case Birch reported 18 recorded observations (REF-0002). The observation date is unavailable. What is the observation date? The interpretation of the second entry remains unresolved. A supervisor approved both entries."
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-7ef0bc944fb8ce3de62c3887",
  "input_sha256": "7ef0bc944fb8ce3de62c38870cec25a35ab92e09609cd841563e3f2effe53a76",
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
