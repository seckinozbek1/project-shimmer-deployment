# Active administrative workflow: review cohort v2

The old first-tuning-experiment-v1 exports are **SUPERSEDED_BEFORE_HUMAN_REVIEW**.
Their bytes remain preserved for provenance. Do not distribute them or use their
legacy submission/status commands for this cohort. No human work was discarded.
Use only the ZIPs ending `_cohort_v2.zip` from this directory. Never distribute
this document, selection manifests, registry, administrative mappings or receipts.

## Human verification

Populate a separate copy of `reviewer_registry.template.json` with actual human
IDs and operator attestations: `human: true`, `operator_verified: true`,
`independent_of_authorship: true`, `is_operator: false`. Neither self-review nor
LLMs/automated judges/authored-gold comparisons satisfy independence. Verify any
adjudicator in the same registry. No identities or submissions are supplied here.

## Distribute blank packets and collect complete envelopes

Each response template now contains `binding` and `review`. The binding includes
the cohort revision, SHA-256 of the cohort manifest and the export payload digest.
The payload digest covers its complete frozen base packets and reviewer instructions,
before inserting the binding (avoiding self-referential hashing). The administrative
export manifest separately binds every final file and the actual ZIP archive bytes;
the active freeze verifies those hashes before intake/status. Reviewer 2 receives
only original blank inputs and its own opaque binding, never another answer.

Reviewers fill only `review` and return the complete envelope. No split/family/answer
metadata is added. Do not retrofit old returns with a new binding. Matching packet
IDs cannot substitute for the current revision and exact export digest.

## Submit either export's returned response

From the repository root, use a separate administrative directory outside `benchmark/`:

```powershell
& 'C:\Users\secki\anaconda3\python.exe' benchmark/first_tuning_review_cohort_v2/workflow.py submit --response RESPONSE.json --journal ADMIN_JOURNAL --reviewers REVIEWER_REGISTRY.json
```

This validates binding and human attestation before invoking the unchanged v2
submission validator/journal. Native v2 records live in `ADMIN_JOURNAL/native`;
append-only envelope receipts bind their exact content to an export slot. The two
slots must use different verified humans. Duplicate slot submissions are rejected.
Using the old CLI directly creates an unreceipted native entry: coverage rejects
the entire journal and emits no new training labels. A partial write also fails
closed. Preserve evidence and repair such administration explicitly; never infer
binding from a coincident packet ID or silently promote a legacy return.

## Disagreements and adjudication

The unchanged journal reports agreement or material disagreement in semantic atoms,
relations, evidence, refusal/ambiguity or typed reason components. Two incompatible
labels are never averaged. Obtain an explicit independent human resolution using
the frozen v2 resolution fields, wrapped in:

```json
{
  "binding": {
    "revision": "first-tuning-review-cohort-v2",
    "cohort_sha256": "COPY_FROM_ADMIN_RESOLUTION_TEMPLATE",
    "exports_sha256": "COPY_FROM_ADMIN_RESOLUTION_TEMPLATE"
  },
  "packet_id": "PACKET_ID",
  "resolution": {}
}
```

Copy hashes from `resolution_envelope.template.json`. Fill `resolution` with
`final_target`, `rationale`, `adjudicator_id`, `adjudicator_kind: human`,
`independence_attestation: true`, timezone-aware `adjudicated_at`,
`review_version: semantic-benchmark-v2`, and the packet's exact `input_sha256`.

```powershell
& 'C:\Users\secki\anaconda3\python.exe' benchmark/first_tuning_review_cohort_v2/workflow.py resolve --response RESOLUTION_ENVELOPE.json --journal ADMIN_JOURNAL --reviewers REVIEWER_REGISTRY.json
```

## Rebuild coverage and training-access labels

```powershell
& 'C:\Users\secki\anaconda3\python.exe' benchmark/first_tuning_review_cohort_v2/workflow.py status --journal ADMIN_JOURNAL --reviewers REVIEWER_REGISTRY.json --out ADMIN_STATUS
```

All 192 need a valid bound first review; the designated 48 need two different
independent humans and adjudication of material disagreements. Old/unbound journal
content is an error, not zero-cost grandfathered review. Keep each rebuild in a
fresh output directory so an earlier result cannot be mistaken for a failed refresh.

Only accepted selected TRAIN/DEV can appear in `ADMIN_STATUS/training_access/`:
at most 78 TRAIN and 40 DEV. DEV remains for validation/tuning decisions; do not
automatically merge it into gradient training. All 72 held-out and the two extra
evaluation rows are excluded. Give a future authorized job only this child directory,
never surrounding admin targets/receipts or held-out labels. Current labels are empty.

All 27 criteria, R07, six catastrophic zeros and final acceptance requirements remain
unchanged. Review readiness is not training authorization. Independent sealed material
under an external account/ACL remains mandatory for final model acceptance.
