# Independent semantic review

Packet: review-de35fc46f3dd960b1da1317a

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "Revision history maintained by Accord Office: CLM-A registers Leto proposed 14 delivery lots under REF-0001. The retained amendment, CLM-B, registers Mira amended 14 delivery lots under REF-0002. Both versions remain in the archive. It is unclear whether the amendment was ratified. No effective period is specified. When does the amendment take effect?\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s163",
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
  "extraction": "Revision history maintained by Accord Office: CLM-A registers Mira proposed 14 delivery lots under REF-0001. The retained amendment, CLM-B, registers Leto amended 14 delivery lots under REF-0002. Both versions remain in the archive. It is unclear whether the amendment was ratified. No effective period is specified. When does the amendment take effect?"
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-de35fc46f3dd960b1da1317a",
  "input_sha256": "de35fc46f3dd960b1da1317afc0ce3828c3ec0c02876ff66544c96d1e446d773",
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
