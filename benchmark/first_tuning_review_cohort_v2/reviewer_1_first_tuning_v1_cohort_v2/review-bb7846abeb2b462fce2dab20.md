# Independent semantic review

Packet: review-bb7846abeb2b462fce2dab20

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "| Sequence | Evidence |\n|---|---|\n"
    },
    {
      "alias": "s22",
      "text": "| 1 | Divider for survey plot 70. |\n"
    },
    {
      "alias": "s46",
      "text": "| 2 | No semantic entry. |\n"
    },
    {
      "alias": "s61",
      "text": "| 3 | End marker. |"
    }
  ],
  "context_only_spans": [],
  "supplied_refs": [],
  "required_refs": [],
  "routed_rules": []
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
    "packet_id": "review-bb7846abeb2b462fce2dab20",
    "input_sha256": "bb7846abeb2b462fce2dab2048e942faf369762b1864bb93f6c0b8a3a3e682a1",
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
