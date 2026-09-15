# Domain-agnostic tuning benchmark hardening

Implementation commit: `fee042af676e2818ec6f7a7589deff0950e1f4fe`.

15 September 2026. Baseline commits: `090b3d5`, `cab07cd`.
Dataset/evaluation: **semantic-benchmark-v2**. Production contract: **semantic-task-v1**, unchanged.

[Validation artifacts and hashes](domain_agnostic_hardening_20260915/).

## 1. Starting limitations

The original 448-row corpus had 96 producer/352 auditor examples, eight domains,
32 document families and four structural templates. It was entirely single-authored,
English, public and correlated within families. Its adversarial partition was not
blind and all domains appeared in tuning-access data. Infrastructure readiness did
not authorize training or establish model quality.

## 2. Dataset versioning

The v1 source, dataset, hashes, split manifests and retained evaluation artifacts
are unchanged. [baseline_reference.json](../../benchmark/task_semantics_v2/baseline_reference.json)
binds 30 original files by hash. The expanded release references the original 448
records and stores **288 new records** separately in `extension.json`.

[freeze.json](../../benchmark/task_semantics_v2/freeze.json) binds the new code,
metadata, data, review packets, manifests, rubric and acceptance specification.
Rebuilding verifies the old baseline and existing release freeze; it cannot silently
bless a modified v1 or modified same-version release. The existing compact producer/
auditor adapters and validators are imported. No fake production-contract v2 exists.

## 3. Independent adjudication workflow

The workflow now supports packet creation, first review, independent second review,
explicit disagreement and later resolution. Submissions bind exact input hash,
packet ID, review version, reviewer ID, human/independence attestation, date, semantic
target/judgment, typed reason components, rationale, ambiguity and separate formatting
judgment. Self-review, machine review, duplicate reviewers and inconsistent role/
target judgments are rejected. Reviewer identity is an operator-verified attestation;
software does not prove a person's independence.

`submit_review.py` writes exclusive-created submission files to a separate admin
journal. It supports later `--resolve-packet` with an explicit human resolution.
Final targets remain separate from frozen authored labels. The second reviewer
receives the original blank packet rather than the first judgment. The journal
cannot be placed inside the reviewer packet export.

## 4. Independent-review coverage

| State | Count |
|---|---:|
| Independently reviewed examples | **0** |
| Pending independent review | **736** |
| Blinded packet IDs ready | **736** |
| Actual disagreements | **0** |
| Final human adjudications | **0** |

Each packet has human-readable Markdown and machine-readable JSON. Inputs are
allowlisted: owned/context spans, role, refs, routed rules and auditor extraction.
Gold relation/target, transformation tag, family/split identity and irrelevant model
answers are excluded. A deterministic administrator mapping is kept outside packet
exports. Source formatting remains visible because reviewers need the actual input.

All records remain honestly `authored_single`. Synthetic tests exercise human-review
interfaces; they are not independent reviews and never change these counts.

## 5. Expanded template families

**12 new structural templates; 16 versioned template families including the four
unchanged legacy templates.** New structures are:

| Split | New structural templates |
|---|---|
| train | paragraph prose, bullet list, form-like fields |
| dev | chronological events, Q/A record, memo sections |
| test | compact table, multi-row table, mixed prose/table |
| public adversarial | nested provisions, transaction register, machine-like records |

These change layout/ownership structure rather than merely vocabulary. Table rows
exercise actual ledger boundaries; mixed material contains multiple source spans.
Within-template domain variants are grouped in one split and are not represented
as additional independent structural samples. The legacy structural naming remains
preserved; 16 labels do not imply 16 randomly sampled population clusters.

## 6. Expanded document families

There are **48 new document families, 80 total**. Each new family has distinct
entity instances, quantities and domain vocabulary, with one/two claims, differing
gaps and uncertainty combinations. A second explicit scenario preserves conflicting
statements about the same entity instead of resolving them. Derived semantic tasks,
empty/refusal variants and negative candidates keep parent and family links.

The allocation is written before variants. Raw row counts are reported separately
from document and template counts. Shared construction still limits independence:
these are authored seed families, not 80 independently sampled real-world documents.

## 7. Producer/auditor distribution

| | Preserved v1 | New | Total |
|---|---:|---:|---:|
| Producer | 96 | 192 | **288** |
| Auditor | 352 | 96 | **448** |
| All examples | 448 | 288 | **736** |

Producer share improves from **21.4% to 39.1%**. The expansion adds **96 substantive
extraction cases**, doubling the new producer semantic scenarios relative to its
48 empty and 48 refusal examples. There are 128 substantive producer examples in
the combined release. Coverage includes one/multiple claims, claim+gap, simultaneous
gaps, uncertainty, explicit contradictions, multi-span tables and 48 new context-only
source-boundary cases. Duplicate-ownership traps remain in the preserved negatives.
Exact 50/50 is not forced; the auditor's existing relation variants are retained.

## 8. Domain distribution

**Ten domains.** The original eight remain, with astronomy and ecology added as
held-out surfaces. Domain counts are:

| Domain | Examples |
|---|---:|
| negotiation | 92 |
| contracts | 92 |
| procurement | 74 |
| device | 92 |
| catalogue | 74 |
| regulation | 74 |
| clinical | 74 |
| nonsense | 92 |
| astronomy | 36 |
| ecology | 36 |

All sources remain synthetic, English and non-advisory. Domain names/units are
data, never evaluator decision rules. No multilingual performance is claimed.

## 9. Held-out-domain design

[domain_holdout.json](../../benchmark/task_semantics_v2/domain_holdout.json) adds a
second axis without changing ordinary splits. Astronomy and ecology total **72
examples** and are completely absent from tuning-access data. Their table/nested/
register/machine templates occur only in test/public-adversarial data, not as renamed
training templates. A separate sealed-domain reservation remains unpopulated pending
independent contribution. Held-out-domain performance has infrastructure and authored
baselines, not a new measured model result.

## 10. Unseen-template design

Ordinary train/dev/test/public-adversarial splits contain **184 examples each**.
All **368 test/adversarial examples** use template-family IDs absent from train,
including genuinely different tabular, nested and machine structures. The explicit
unseen-template manifest supports separate reporting. Document, template and domain
holdout are separate claims; the 72 domain-held-out examples are a subset of these
368 examples, not an extra population.

## 11. Blind/sealed final-set state

**Zero genuinely blind examples populated.** The public adversarial set is still
public. The final manifest records pending independent contribution and no label hash.

Sealing accepts only independently reviewed, independently contributed synthetic
material, with human/authorization attestations and exclusive-created label/hash
files in an external vault. Public authored and operator-private material are
rejected. Development/training access does not open the vault. Explicit final mode
requires a permit binding labels, saved candidate outputs and acceptance registration.
Final evaluation checks full unique coverage and records aggregate counts only.
Results are append-only through exclusive creation, duplicate-run rejection, a write
lock and hash-chain verification. Protected answer hashes can audit public output
without reading the vault's labels.

**Application controls are not OS isolation.** Real labels require a separate
operator-controlled account/ACL outside this repository. That boundary and real
independent material have not been provisioned. An unrestricted same-account process
could bypass Python interfaces or remove log files; retention and external log
anchoring remain operator responsibilities. Synthetic temporary vault tests do not
constitute real population or independent review.

## 12. Compound hard negatives

The **576 existing candidates across 18 transformations** remain unchanged. The
expansion adds **432 candidates: 48 each for nine compound cases**:

- Wrong relation plus irrelevant ref.
- Preserved claims with a missing information gap omitted.
- Correct content plus invented rule attribution.
- MATCH with incomplete evidence.
- Insufficient evidence with a forced answer.
- Omission combined with unsupported addition.
- Context-only claim plus a valid owned claim.
- Removed uncertainty with factual atoms retained.
- Semantic content paired with empty status in valid JSON.

All **1,008** candidates are rejected. These are authored, defensible corruptions
relative to explicit targets, with ancestry and rationale; independent adjudication
is still pending. They are not mislabeled as generated-model measurements.

## 13. Reason-correctness rubric

Thirteen typed components cover preserved/missing/added claim, changed label,
quantity or unit, gap preserved/omitted, insufficient evidence, unsupported attribution,
ambiguity and uncertainty preserved/omitted. Reviewers assess these against source,
extraction and exact evidence, separately from formatting.

Canonical authored reasons remain regression targets. Independently reviewed
paraphrases can pass with reviewer identity, human attestation, date, input hash,
raw-output hash, components, truth judgment and rationale. Unreviewed alternate
wording remains unassessed; generic similarity never establishes reason truth.

## 14. Pre-registered acceptance criteria

[acceptance_specification.json](../../benchmark/task_semantics_v2/acceptance_specification.json)
is frozen before any training run. It explicitly registers **six zero catastrophic
limits**: invented evidence, unrouted rules, confident semantic reversals, truncation,
producer source copying and governance violations. These follow existing evidence,
governance, no-copy and zero-truncation requirements rather than fitted model results.

**27 numeric quality/coverage/family thresholds remain
`REQUIRES_OPERATOR_REGISTRATION`.** They cover producer claims/gaps/evidence/refusal/
completeness/contract/uncertainty, auditor relation/per-class/refusal/reason/evidence/
contract/uncertainty, and independent-review coverage, document/template sample size,
held-out-domain and unseen-template floors and family variability.

There is no basis to invent near-perfect percentages or sample adequacy from these
authored examples. The acceptance function reports catastrophic counts but fails
closed on unregistered criteria. A new prospective registration must bind and implement
the operator's quantitative rules before any acceptance decision; no aggregate-F1
shortcut or post-hoc threshold fitting is allowed.

## 15. Family-aware statistics

The implementation reports existing metrics per document family, template family
and domain, with equal-weight metric macros and accepted-outcome ranges. Empty
precision/recall classes are excluded from macro denominators rather than counted
as perfect observations. Group counts accompany each macro.

A deterministic 1,000-draw group bootstrap supplies **exploratory** intervals;
intervals are withheld below eight groups. It resamples groups, not correlated rows.
Document families still share templates, and authored gold is not a model sample;
neither row-level intervals nor degenerate all-gold intervals establish generalization.
The original v1 descriptive row intervals remain preserved, with explicit warnings.

## 16. Leakage audit

Zero detected family, ancestry, exact-duplicate, domain-holdout, training-access or
blinded-packet findings. Existing regression hashes/ancestry and v1 leakage checks
remain active. New effect proofs neutralise and restore the packet input allowlist,
domain exclusion and training-file allowlist, observing failure under neutralisation.
Sealed-answer exposure is tested with synthetic protected hashes; no real inaccessible
answers were opened. A zero-population sealed audit is not a claim about unseen labels.

## 17. Training-access boundary

[training_view/manifest.json](../../benchmark/task_semantics_v2/training_view/manifest.json)
contains **368 allowed IDs**, split into 184 train and 184 dev rows, with exact file
hashes. The supplied reader verifies release/baseline hashes, file-name allowlists,
resolved paths, symlinks, IDs, splits and domains. It rejects test/sealed/regression
paths, path traversal, modified content and injected held-out rows.

A future job should receive this directory alone, under constrained filesystem
permissions. It must not receive the full repository, operator/durable data or an
external vault. This manifest is selection infrastructure, not training authorization.

## 18. Historical reproduction

The frozen v1 gate reruns into a fresh output directory: **42 tests**, 448 authored
outcomes and 576 negative rejections pass. The new combined baseline accepts all
736 authored gold outcomes and rejects all 1,008 negatives. All **four historical
model A/B failures** reproduce without prefix recovery or citation repair. All
**106** original A/B evidence hashes verify. No historical evidence is overwritten,
and no authored counts are represented as generated-model quality or latency.

## 19. Governance/evidence checks

**35 new hardening tests + 42 preserved dataset tests + 85 production checks = 162
passing checks**, zero failures; one pre-existing optional fixture-directory skip.
There are three new and seven preserved effect proofs. New tests cover blinded
packets, human/self/machine review distinctions, later disagreement resolution,
typed reason paraphrases, domain/template holdout, training file access, sealed-mode
denial, synthetic sealing/final evaluation, append-only output, protected-answer
exposure, family weighting and acceptance registration.

Existing no-self-audit/family separation, privacy, operator authority, provenance,
refusal, incomplete output and exact evidence checks remain in force. Production
validators and model pins are unchanged. The local gates block model/provider
imports and network connections. All new files are scanned for credentials before
commit; safe counts and artifact hashes are retained with the evidence.

## 20. Readiness verdict

**DOMAIN_AGNOSTIC_TRAINING_EXPERIMENT_NOT_READY**

The expanded benchmark, blinded review workflow, access controls, rubric, prospective
acceptance specification and statistics are implemented and tested. Concrete blockers:

1. **No independent human review: 736 examples pending.**
2. Operator registration and implementation of the unresolved quantitative acceptance
   rules, including review/sample adequacy and family/domain requirements.
3. Genuine independent sealed content and an external account/ACL boundary.

Workflow existence is not independent evidence. None of these gaps is concealed by
the larger row count or by self-approving authored labels.

## 21. Exact next action

Give an independent human reviewer only the blinded packet export and collect
hash-bound responses through the submission journal. Arrange an independent second
review/resolution where required. In parallel, have the operator prospectively
register the unresolved acceptance rules and commission independently held final
material in a separately protected vault. Freeze a reviewed release before seeking
separate authorization for any bounded tuning experiment.

**No cloud, paid API, training, LoRA/SFT, model/revision/quantization change, model
workload, full pipeline, multi-round or push.** User-owned root handoff and durable
state are unchanged.
