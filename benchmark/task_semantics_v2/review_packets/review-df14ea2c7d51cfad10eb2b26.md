# Independent semantic review

Packet: review-df14ea2c7d51cfad10eb2b26

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "Opening statement: CLM-C: sensor bank 76 is assigned 122 pulses (REF-1003).\n\n"
    },
    {
      "alias": "s4d",
      "text": "| Supplement | Content |\n|---|---|\n| Detail | CLM-D: the same sensor bank 76 is assigned 124 pulses (REF-1004). |"
    },
    {
      "alias": "sbe",
      "text": "\n\nClosing qualification: These statements conflict. The effective time is missing. When does it take effect? The interpretation remains uncertain.\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s152",
      "text": "| External | Content |\n|---|---|\n| CONTEXT ONLY | CLM-Z: an unrelated neighbor lists a separate observation (REF-9999). |"
    }
  ],
  "supplied_refs": [
    "REF-1003",
    "REF-1004",
    "REF-9999"
  ],
  "required_refs": [
    "REF-1003",
    "REF-1004"
  ],
  "routed_rules": []
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-df14ea2c7d51cfad10eb2b26",
  "input_sha256": "df14ea2c7d51cfad10eb2b2632bdd1b374a53bc4f14e12256c149265ac1b9fea",
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
