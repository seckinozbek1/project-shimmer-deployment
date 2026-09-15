# Independent semantic review

Packet: review-ff767eaad52ea4394e71c6fd

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "| Field | Content |\n|---|---|\n"
    },
    {
      "alias": "s1e",
      "text": "| Primary | CLM-A: sensor bank 68 recorded 98 pulses (REF-1001). |\n"
    },
    {
      "alias": "s61",
      "text": "| Secondary | CLM-B: sensor bank 68 retained 103 pulses (REF-1002). The date is absent. When was this recorded? The recorder is unnamed. Who recorded it? |"
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
  "routed_rules": []
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-ff767eaad52ea4394e71c6fd",
  "input_sha256": "ff767eaad52ea4394e71c6fd61602ba69e4962298e7db44dc9dc8ef34a701dab",
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
