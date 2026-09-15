# Independent semantic review

Packet: review-8ea6604004ebf13f495decef

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "CLM-A: Orin planned 12 concessions (REF-0001); CLM-B: Vela reported 19 concessions (REF-0002). The observation date is unavailable. What is the observation date? The interpretation of the second entry remains unresolved.\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "sde",
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
  "extraction": "CLM-A: Orin planned 12 concessions (REF-0001); CLM-B: Vela reported 19 concessions (REF-0002). The observation date is unavailable. What is the observation date? The interpretation of the second entry remains unresolved. A supervisor approved both entries."
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
    "packet_id": "review-8ea6604004ebf13f495decef",
    "input_sha256": "8ea6604004ebf13f495decef0a56a4d7bd7de2a11b751771b25a44a1a1cf1f53",
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
