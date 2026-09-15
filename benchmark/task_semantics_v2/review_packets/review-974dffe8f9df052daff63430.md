# Independent semantic review

Packet: review-974dffe8f9df052daff63430

Review independently without consulting authored labels, split files, or transformation metadata. Return semantic judgment, exact evidence, concise reason and ambiguity/refusal separately from formatting judgment. Producer item fields: span, claims, questions, uncertainty, status, refs; one per owned alias. Auditor item fields: finding, ref_ids, reasoning, severity, confidence. Use MATCH/DIVERGENCE/OMISSION/ADDITION for fidelity; refuse with items=[] and status=refused for insufficient evidence.

```json
{
  "role": "producer",
  "production_contract": "semantic-task-v1",
  "source_spans": [
    {
      "alias": "s0",
      "text": "Interview transcript, Council of Talks. First speaker: \"CLM-A says Orin accepted 12 concessions; see REF-0001.\" Second speaker: \"CLM-B says Vela declined 19 concessions; see REF-0002.\" Recorder asks: \"The recorder is not identified. Who recorded this interview?\" An unsigned marginal note reads: \"The attribution of the marginal note is uncertain.\"\n\n"
    }
  ],
  "context_only_spans": [
    {
      "alias": "s15e",
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
  "routed_rules": []
}
```

## Response template (pending, not a submitted review)

```json
{
  "packet_id": "review-974dffe8f9df052daff63430",
  "input_sha256": "974dffe8f9df052daff63430dfdba798dfad9cd9185928d851971d905786ccb8",
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
