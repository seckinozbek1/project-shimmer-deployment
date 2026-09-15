# Independent semantic review

Packet: review-cf08e08b69e5c2b7e0e99d79

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "auditor",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "BEGIN REGISTER\nDEBIT OBSERVATION :: CLM-A: service desk 83 recorded 143 delivery windows (REF-1001).\nCREDIT OBSERVATION :: CLM-B: service desk 83 retained 148 delivery windows (REF-1002).\nMEMO ONLY :: The date is absent. When was this recorded? The recorder is unnamed. Who recorded it? The interpretation remains uncertain.\nEND REGISTER"
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
  "routed_rules": [],
  "extraction": "BEGIN REGISTER\nDEBIT OBSERVATION :: CLM-A: service desk 83 recorded 143 delivery windows (REF-1001).\nCREDIT OBSERVATION :: CLM-B: service desk 83 retained 148 delivery windows (REF-1002).\nMEMO ONLY :: The date is absent. When was this recorded? The recorder is unnamed. Who recorded it? The interpretation remains uncertain.\nEND REGISTER"
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-cf08e08b69e5c2b7e0e99d79",
  "input_sha256": "cf08e08b69e5c2b7e0e99d79973ddb0f9da9044951a10adf2e258ceb0003d244",
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
