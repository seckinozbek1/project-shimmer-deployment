# Machine agent review V2 ? completed 15 September 2026

**AGENT_ADJUDICATED_TUNING_EXPERIMENT_READY**

**FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING**

Protocol: `machine-agent-review-v2`. This is machine review readiness under the prospectively registered M01?M07 and pool definition. It is not human review, model acceptance, or permission to train.

## Scope and chronology

Base: `4b570fc210f0bbf5bb8b636041a62922114536cd`, following V1 pre-gold commit `d151ae7a8b54e380cb528eefbc286be2a3ea93d9`.

1. Before fresh reviewers started, 12 deterministic normalizer tests and seven neutralise ? fail ? restore ? pass effect proofs passed. `PRE_REVIEW_METHOD_FREEZE.json` records 2026-09-15T17:05:01.987387+00:00 and method hashes. Registration committed as `9b0086e4a463cc40e90507d65f041385fee43fa1`.
2. Fresh isolated-context A/B/C sessions reviewed all 192 clean packet-only inputs each. No V1 answers, gold, other-primary answers or post-freeze diagnostics were provided. Three distinct sessions are not three model families; shared filesystem and parent model family limit independence. Isolation is procedural, with exact packet hashes and agent attestations, not OS ACL enforcement.
3. A separate finite legacy-wording adapter was tested and hash-registered before authored comparison. It rejects unknown qualifiers and distinguishes recorder from recording date. It does not change the pre-review typed normalizer or reviewer outputs.
4. Fresh adjudicator D reviewed the union of all no-majority, invalid-primary and designated hard cases. All 576 primaries, zero repairs, 56 adjudications, 192 labels, consensus and method/config hashes were frozen and committed as `b22c8566a16e0930a3ccb8cf941e3b0fc689cb8d` before V2 authored comparison.
5. The first comparison launch encountered a Python import-name collision and OpenMP initialization error before its checkpoint or authored-target reads. The comparison entry point was made to resolve the local V2 pipeline explicitly; a no-model-import regression test now executes that import. No Shimmer generation or pipeline execution occurred. Frozen semantics/projection were not changed.
6. Authored comparison and separate candidate manifests were generated once after the committed freeze. Actual start time/hash are in `post_freeze/GOLD_COMPARISON_STARTED.json`.

## Method

Producer material comparison uses exact claims, typed gaps, typed uncertainty, owned alias/span, exact evidence refs and refusal/empty state. Atoms retain type, subject, target, scope, span, refs, source-explicit origin and unit. The finite ontology supports missing information, unknown interpretation/ratification, and conflicting assertions. Unsupported vocabulary or reviewer inference fails closed. No embeddings or fuzzy string threshold are used.

`source_uncertainty_present` and `review_ambiguity` are distinct. An explicit uncertain source may yield an unambiguous review. Only genuine review ambiguity excludes a candidate for that reason. Auditor relation, refs, refusal, confidence and typed reason components remain material for machine consensus.

The V1 evidence failure analysis found 35 omitted-required-ref failures across 17 packets: A=9, B=9, C=17. They reflected returning changed-claim subsets instead of all mandatory supplied refs; no context-only/unowned refs were found in this failure class. V2 instructions explicitly require all response-level auditor refs and each producer item's owned refs, with atoms bound to that item's alias and refs. Refused/empty outputs retain the contract's empty-item behavior.

## Fresh review results

| Measure | V2 result |
|---|---:|
| Packets / primary slots | 192 / 576 |
| Effective valid primaries | 576/576 |
| Evidence-invalid primaries | 0 |
| Schema repairs / semantic retries | 0 / 0 |
| Unanimous typed material agreement | 154/192 (80.2083%) |
| Exact 2/3 majority only | 29/192 (15.1042%) |
| No majority | 9/192 (4.6875%) |
| Evidence-valid triples / evidence-unanimous triples | 192/192 / 192/192 |
| Producer typed-gap unanimity | 96/96 |
| Producer typed-uncertainty unanimity | 96/96 |
| Auditor relation unanimity | 96/96 |
| Required adjudications | 56/56 |
| Designated hard adjudications | 48/48 |
| Adjudicator selections | A:38; C:18 |
| Majority overturns | 0/47 majority-bearing adjudications |
| Unresolved review ambiguities | 0 |
| Final labels preserving source uncertainty | 126/192 |

Detailed agreement breakdowns by role, domain, template, relation, held-out, unseen, refusal, gap and source uncertainty are in `post_freeze/agreement_statistics.json`. Nine no-majority cases were resolved by the fresh adjudicator; source uncertainty alone did not cause an unresolved annotation.

## Post-freeze authored comparison

| Producer measure | Agreement |
|---|---:|
| Claims | 96/96 |
| Typed gaps | 92/96 |
| Typed uncertainty | 48/96 |
| Evidence | 96/96 |
| Refusal | 96/96 |
| Complete structured semantic agreement | 48/96 |
| Wording-only disagreements accepted as equivalent | 0 |

There are 48 cautious producer disputes. Twelve have identical readable machine/authored wording but the frozen adapter cannot project the authored ratification or second-entry qualifiers. Thirty-two have a fully projectable difference: machine uncertainty includes explicit conflicting assertions in addition to uncertain interpretation; authored targets include only the latter. Four more combine that conflict difference with unprojected question-answer wording ("What was entered first?" / "What followed?"). Thus 16 packets have unresolved legacy projection, overlapping four of the 36 conflict-atom disputes. These are preserved as `LABEL_DISPUTE_REQUIRING_CAUTION`, not silently called model errors or normalized away. No synonyms were added after gold.

| Auditor measure | Agreement |
|---|---:|
| Relation | 96/96 |
| Evidence | 96/96 |
| Refusal | 96/96 |
| Confidence | 96/96 |
| Typed authored reason components | Not measurable: absent in authored records |

V1 exact producer agreement was 24/96; V2 structured agreement is 48/96. The fresh reviewers often used the same concise wording as authored records, so this run does **not** demonstrate a nonzero wording-only collapse in final authored comparison. The positive generic fixtures demonstrate supported paraphrase equivalence. Typed normalization and clarified instructions improve the review methodology; there is no evidence here of an improved model. V1 remains intact and is not rescored.

## Candidate access and readiness

| Access | Eligible | Roles |
|---|---:|---|
| TRAIN | 58 | 12 extracted producer; 46 auditor |
| DEV | 24 | 24 auditor; 0 producer |
| Total | 82 | 12 producer; 70 auditor |
| Excluded TRAIN/DEV disputes | 36 | Material or unprojectable comparison |
| Excluded genuine review ambiguity | 0 | None |
| Eligible with source uncertainty | 58 | Uncertainty does not itself exclude |

All 72 mandatory held-out examples were reviewed and excluded from tuning access. Both additional evaluation examples are also excluded: all 74 evaluation labels remain outside the separate machine candidate directory. Original cohort allocation is unchanged: 78 TRAIN, 40 DEV, 72 held-out, two coverage-preserving evaluation examples, total192. No human namespace was changed; human first/second/adjudication counts remain 0/0/0.

M01=576/576; M02=576/576; M03=48/48; M04=56/56 and zero ambiguous candidates; M05=72/72 with zero evaluation leakage; M06=zero detected isolation violations; M07=frozen benchmark/acceptance/history unchanged. All pass. The pre-review meaningful-pool definition (nonempty TRAIN and DEV, both roles represented overall) passes. The pool is narrower than a balanced producer tuning experiment: **there are no producer DEV candidates**. READY must not be read as removing this limitation or authorizing training.

## Validation and preservation

- V2: 29 deterministic tests, seven effect proofs. Positive and negative typed semantics, real evidence mutation rejection, consensus/adjudication recomputation, hash/order/commit proof, access isolation, provenance and R06 are checked.
- Preserved cohort: 30 tests, four effect proofs, 482 export files/archive members, status remains human REVIEW_PENDING.
- Production contracts: 85 passed checks, four effect proofs, one existing optional skip; no generation.
- V1: all 961 release-bound files unchanged. Historical A/B evidence: all 106 hashes unchanged and all four rejections reproduced.
- Frozen semantic-benchmark-v2, semantic-task-v1, 27 criteria, derived R07, six catastrophic zero limits, 16/16 template coverage and unseen-template requirement remain unchanged.
- R06 retains >=0.80, minimum four samples, and the registered non-TRAIN population. The real population remains 114 (40 DEV, 37 TEST, 37 public-adversarial), with 12 held-out families and 22 sparse families. Both the synthetic effect proof and actual-population injection test show TRAIN rows cannot change sample accounting or outcomes. No new checkpoint predictions were produced.
- Credential scans return zero findings. Exact synthetic packet hashes and access attestations support privacy/isolation; this is not a claim of OS-enforced isolation. Final release scan and file/hash evidence are recorded alongside this report and under V2 validation.

## Next step and boundaries

Keep this V2 release immutable. Separately address the 36 excluded tuning-access disputes and absent producer DEV coverage through a prospectively specified review/projection amendment or human adjudication, before proposing a producer tuning experiment. Do not silently extend this frozen normalizer using observed gold. Human review remains pending.

No human review falsely claimed. No cloud, paid API, Shimmer model execution, training, LoRA/SFT, model/revision/quantization change, full pipeline, multi-round or push. All changes are local.
