# Independent semantic review

Packet: review-2b1ea6e0084fa32dbf5467e9

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
      "text": "| 1 | Divider for sensor bank 72. |\n"
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
  "packet_id": "review-2b1ea6e0084fa32dbf5467e9",
  "input_sha256": "2b1ea6e0084fa32dbf5467e9924ddf1d4137444861f01987effbeefd8b4c7931",
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
