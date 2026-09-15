# Administrator: collect actual independent human reviews

Keep this document, cohort/admin manifests, selection rationale, registration and
training views OUT of both reviewer exports. Give each reviewer only the applicable
packet-only ZIP. Both exports contain original blank packets, without prior responses.
The reviewer instructions are identical and do not disclose a double-review assignment.

## Verify people first

Do not count the operator, source authors, ChatGPT, Claude, other LLMs, automated
judges or authored-gold comparisons as independent humans. Verify each person's
identity and independence. In a separate admin directory, populate a copy of
`reviewer_registry.template.json` keyed by their actual pseudonymous reviewer IDs.
Each entry must attest `human: true`, `operator_verified: true`,
`independent_of_authorship: true`, `is_operator: false`. The distributed response
templates remain blank. No registry entries or human submissions are supplied here.

## Import returned response files

Use the existing immutable v2 journal command, from the repository root, with the
local Python 3.12 executable:

```powershell
& 'C:\Users\secki\anaconda3\python.exe' benchmark/task_semantics_v2/submit_review.py RESPONSE.json --journal ADMIN_DIRECTORY
```

Use the same command for either export's returned responses. IDs and input hashes
route them automatically. Do not give the journal or a submitted response to another
reviewer. A repeated reviewer ID cannot substitute for two independent people.
Machine-provided or self-authored responses must not be entered as human reviews.

## Disagreement and resolution

The journal reports first review, agreement or disagreement. For disagreement on
semantic atoms, relation, refs, refusal/ambiguity or typed reason truth, obtain an
explicit independent-human resolution. Do not average the labels. Use:

```powershell
& 'C:\Users\secki\anaconda3\python.exe' benchmark/task_semantics_v2/submit_review.py --resolve-packet PACKET_ID --resolution RESOLUTION.json --journal ADMIN_DIRECTORY
```

The resolution supplies `final_target`, `rationale`, `adjudicator_id`,
`adjudicator_kind: human`, `independence_attestation: true`, timezone-aware
`adjudicated_at`, `review_version: semantic-benchmark-v2`, and the packet's
`input_sha256`. V2 independently validates identity, binding and target contract.
Verify the resolver is also an independent human. Authored labels remain frozen.

## Rebuild coverage and eligible training selection

```powershell
& 'C:\Users\secki\anaconda3\python.exe' benchmark/first_tuning_experiment_v1/review_status.py --journal ADMIN_DIRECTORY --reviewers REVIEWER_REGISTRY.json --out ADMIN_STATUS_DIRECTORY
```

This reads actual submissions and writes counts plus a separate admin target map.
All 192 cohort examples need a valid independent first review. Each designated 48
needs two, and material disagreements need explicit resolution. The other 544
packets remain available but are not required for this first review-readiness gate.

Only independently reviewed/accepted TRAIN and DEV examples can appear under the
generated `training_access/` directory. Give a future authorized job that directory
alone. Never give it the surrounding admin target map, held-out/domain/test/public
adversarial labels, sealed vault, operator documents or durable state. Astronomy and
ecology remain held out. Initially the eligible files are empty.

REVIEW_READY does not authorize training and is not model acceptance. A future
bounded run still needs separate operator authorization. Genuine independent sealed
material, an external account/ACL and stricter final criteria remain mandatory for
FINAL_MODEL_ACCEPTANCE; they are not prerequisites to this 192-example review gate.
