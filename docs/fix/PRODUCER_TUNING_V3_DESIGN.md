# Producer targeted failure audit and V3 design

**PRODUCER_TUNING_V3_DESIGN_READY**. This is a local design/curation/tokenizer dry-run verdict, not permission to train or a quality result. The completed V2.1 checkpoint-120 result remains **PRODUCER_CHECKPOINT120_FAIL**. This is the last automatic Producer redesign cycle.

V2 saved measurements: fresh 60/60; 35 accepted and complete; contract/claims/evidence 1.0; uncertainty F1 0.909090909; gap F1 0.760180995; refusal precision 0.571428571, recall 1.0, over-refusal 0.053571429. Seven refusals comprise four correct and three false. All six catastrophic categories are zero. The audit reads saved verdicts/metrics and compares raw atoms; it never calls the historical scorer or changes prior labels, outputs, verdicts, releases or Auditor design.

Every failed row is listed below. Full owned source, expected/observed structures, saved metrics and every diagnostic atom pairing are retained in [failure_audit.json](../../tuning/producer_v3/failure_audit.json). All IDs have prefix `shimmer2-producer-document-`.

| Failed ID | Rendering | Diagnostic tags | Atom corrections |
|---|---|---|---:|
| 050 | timeline | missing_gap, partially_missing_gap_set, wrong_gap_attribute | 1 |
| 051 | timeline | missing_gap, partially_missing_gap_set, wrong_gap_referent | 1 |
| 052 | timeline | missing_gap, partially_missing_gap_set, wrong_gap_referent | 1 |
| 053 | timeline | missing_gap, partially_missing_gap_set, wrong_gap_referent | 1 |
| 054 | timeline | missing_gap, refusal_when_substantive_required, status_inconsistency | 2 |
| 055 | timeline | missing_gap, partially_missing_gap_set, wrong_gap_referent | 1 |
| 056 | timeline | missing_gap, partially_missing_gap_set, wrong_gap_referent | 1 |
| 057 | timeline | missing_gap, partially_missing_gap_set, wrong_gap_referent | 1 |
| 135 | register | missing_gap, partially_missing_gap_set, wrong_gap_referent | 1 |
| 136 | register | extra_uncertainty, missing_uncertainty | 1 |
| 138 | register | missing_gap, refusal_when_substantive_required, status_inconsistency | 2 |
| 139 | register | missing_gap, wrong_gap_referent | 2 |
| 142 | register | missing_gap, missing_uncertainty, partially_missing_gap_set, wrong_gap_referent | 2 |
| 145 | register | missing_gap, missing_uncertainty, partially_missing_gap_set | 2 |
| 152 | machine_log | missing_gap, refusal_when_substantive_required, status_inconsistency | 2 |
| 157 | machine_log | missing_gap, partially_missing_gap_set, wrong_gap_attribute, wrong_gap_referent, wrong_gap_state_type | 1 |
| 270 | footnoted_record | extra_uncertainty, missing_gap, partially_missing_gap_set, wrong_gap_attribute, wrong_gap_state_type | 2 |
| 272 | footnoted_record | missing_gap, partially_missing_gap_set | 1 |
| 273 | footnoted_record | missing_gap, wrong_gap_attribute, wrong_gap_state_type | 3 |
| 274 | footnoted_record | missing_gap, partially_missing_gap_set, wrong_gap_attribute | 2 |
| 275 | footnoted_record | missing_gap, partially_missing_gap_set, wrong_gap_attribute, wrong_gap_state_type | 2 |
| 276 | footnoted_record | extra_uncertainty, missing_gap, partially_missing_gap_set, wrong_gap_state_type | 1 |
| 277 | footnoted_record | missing_gap, partially_missing_gap_set | 1 |
| 279 | footnoted_record | missing_gap, partially_missing_gap_set | 1 |
| 280 | footnoted_record | missing_gap, partially_missing_gap_set | 1 |

Tags are multi-label. `missing_gap` means an exact required gap atom is absent, including a mislabelled replacement; it does not imply pure omission. `partially_missing_gap_set` means at least one exact gap survives and at least one is absent. `status_inconsistency` includes a whole-packet false refusal.

| Error tag | Failed rows |
|---|---:|
| refusal_when_substantive_required | 3 |
| missing_gap | 24 |
| partially_missing_gap_set | 19 |
| wrong_gap_referent | 10 |
| wrong_gap_attribute | 6 |
| wrong_gap_state_type | 5 |
| missing_uncertainty | 3 |
| extra_uncertainty | 3 |
| claim_failure | 0 |
| evidence_failure | 0 |
| status_inconsistency | 3 |
| contract_failure | 0 |
| other_semantic_incompleteness | 0 |

Of 22 failed non-refusal outputs, 21 preserve all claims but have a gap deficit; one fails only uncertainty referent assignment. Across all failures, 24 preserve all claims yet lack at least one exact gap. Three fail through refusal. Three miss uncertainty and three contain extra uncertainty (including cross-kind substitutions). Nineteen have partially correct gap sets. **15/25 (60%) are one-atom corrections away; nine require two and one requires three.** A substitution is one correction despite contributing both FP and FN; moving gap/uncertainty kind is also one correction. This is diagnostic edit distance, not predicted V3 performance. No hypothetical repaired output is scored or accepted.

**Gap decomposition: TP=84, FP=20, FN=33**, giving 168/221 = 0.760180995 F1. Each FN and FP receives exactly one primary class below. Minimum-field-distance pairing is an explicit diagnostic convention; a compound replacement can carry several row tags. Pairing does not change frozen exact-string counts.

| Primary class | FN | FP |
|---|---:|---:|
| omission | 13 | 0 |
| referent | 10 | 10 |
| attribute | 4 | 4 |
| state_type | 0 | 2 |
| ordinal_order_content | 3 | 3 |
| temporal_role | 1 | 1 |
| absence_vs_unknown | 2 | 0 |
| other | 0 | 0 |

FN attributes: recording_time=9, event_time=7, entry_order=4, recording_occurrence=4, observation_time=3, reporting_time=2, submission_occurrence=2, recorder=1, entry_presence=1.

The deficit is concentrated: recording-time (9), event-time (7), order (4) and recording-occurrence (4) account for 24/33 FN. Ten paired referent errors include six event-time atoms changed from the frozen `owned_record` referent to `event`, plus observation, recorder and submission referents. Thirteen pure omissions include six atoms lost to the three refusals and seven omissions in extracted outputs. Errors also mix recording occurrence with entry presence, recording time or submission occurrence, and move atoms between gap and uncertainty. No broad claim/evidence/contract degradation is observed. The representational convention for an event date is preserved even though ordinary English could suggest an event referent; this design does not silently change the ontology.

**Three over-refusals, inspected individually:**

| ID | Source-visible supported content | Length (characters) | Existing TRAIN occurrences of exact typed gap |
|---|---|---:|---|
| 054 | event time missing + reporting time unspecified | 114 | event_time=16, reporting_time=5 |
| 138 | observation time missing + later-entry order question | 131 | observation_time=16, entry_order=13 |
| 152 | reporting time unspecified + first-entry explicit absence | 134 | reporting_time=5, entry_presence=21 |

All three have one owned span, two supported gaps, no uncertainty, no CLM claims, no refs, and the regulation domain. Their renderings are timeline, register and machine-log. None needs an unknown gap type or outside knowledge; all required atom types already occur in TRAIN. Explicit missingness/order/absence is extractable information. These cases do not justify packet-specific or regulation-specific exceptions.

The four correct refusals (059, 149, 164, 284) explicitly state an unavailable quantitative value outside the finite ontology, alongside a supported gap. They also have one span and no claims/refs/uncertainty. Lengths are 130, 135, 137 and 147 characters; the false-refusal lengths are 114, 131 and 134. Thus absent refs, missingness words, and short sources cannot define the refusal rule. A supported clause elsewhere does not authorize dropping an unrepresentable owned proposition.

Among the 49 substantive non-refusals: nine have no claims/refs, 16 have no uncertainty, 36 have two gaps, 13 have three, 23 have two spans, and five contain conflicting claims. Two are regulation examples; five regulation substantive rows total give 3/5 false refusals versus 0/47 elsewhere. This is a small, confounded correlation, not evidence of a domain cause. Their source lengths range 165–432 characters. The three false refusals are shorter than this cohort, but length is confounded with absent claims/refs/uncertainty. All 60 DEV rows belong to the anchored structural superfamily, so family-specific causation cannot be estimated from this evaluation. Multiple gaps are common in both success and failure; uncertainty and multiple/conflicting claims are absent from these three false refusals.

Domain-agnostic diagnosis: distinguish source insufficiency/unrepresentable semantic content from explicit supported missingness. Preserve every supported gap even with zero claims/refs; refuse only when the full owned proposition/referent cannot be represented or resolved under the unchanged policy. The observed concentration motivates data contrasts, not a causal claim about weights or a new inference-time exception.

**Targeted data:** retain all 300 Producer V2 rows unchanged (260 substantive, 20 refusal controls, 20 empty controls). Add 100 substantive rows and 20 genuine refusal controls. There are 360 unique substantive atom sets after removing names, quantities, claims, refs, surface wording and owner aliases; expansion credit is not assigned for domain/template renaming. All additions have new document families, entities, domains, wording and source organization. Authoring uses abstract error classes and checks old signatures for exclusion; no failed DEV packet is a training parent.

Twenty hard contrast pairs share document/derivation ancestry: five unavailable-magnitude vs supported-missingness pairs; five unknown-temperature vs supported uncertainty/gaps pairs; ten ambiguous two-antecedent vs uniquely bound one-antecedent recording-relation pairs. The negative differs in semantic sufficiency, not the presence of generic missing/unknown words. Positive examples include 20 missingness-only cases without uncertainty; the other 80 combine gaps and uncertainty. Ten unsupported-content refusals and ten deictic-ambiguity refusals supplement the existing 20 genuine refusals. All pair siblings stay in one split.

The 100 new substantive examples combine two or three gaps with temporal-role/referent/nonoccurrence/order distinctions; varied claim/ref burdens and multiple ownership spans preserve completeness pressure. Twenty authored same-batch conflicting-claim cases retain both claim IDs instead of refusing. Two repeated source clauses are intentionally deduplicated into one target atom, as independently flagged by review. Every distinct required atom is retained; deleting one fails local label validation. The production contract, compact rendering and finite ontology are unchanged.

| Corpus quantity | V3 total | TRAIN | DEV |
|---|---:|---:|---:|
| rows | 420 | 336 | 84 |
| substantive | 360 | 288 | 72 |
| document_families | 400 | 320 | 80 |
| template_families | 5 | 4 | 1 |
| refusals | 40 | 32 | 8 |
| gap_bearing | 360 | 288 | 72 |
| uncertainty_bearing | 253 | 204 | 49 |
| multi_span | 128 | 101 | 27 |
| multi_claim | 170 | 135 | 35 |

Non-refusals: 380 total / 304 TRAIN / 76 DEV. Twenty domains: ten unchanged V2 domains and railway, theatre, horticulture, geology, manufacturing, navigation, textiles, acoustics, ceramics and cartography. Five conservative structural superfamilies are retained; new sectioned packet organizations inherit the existing sectioned TRAIN group and explicitly anchored envelope faces inherit the anchored DEV group. There are25 rendering layouts total (20 retained +5 new); renamed layouts do not earn new structural independence. There are 400 document families because each new contrast pair shares a family. Document IDs do not establish statistical independence.

| Gap attribute | Atoms |
|---|---:|
| recording_time | 122 |
| event_time | 63 |
| submission_time | 33 |
| authorization_time | 32 |
| observation_time | 38 |
| reporting_time | 34 |
| effective_time | 32 |
| recorder | 33 |
| entry_content | 84 |
| entry_order | 87 |
| submission_occurrence | 54 |
| recording_occurrence | 35 |
| event_occurrence | 38 |
| entry_presence | 31 |
| ratification_status | 35 |
| date_unspecified | 29 |

Grouped canonical split: **336/84 (80/20)**. Keep all old 240 TRAIN/60 DEV memberships. The original conservative group assignments place all24 new anchored `specimen_envelopes` rows in DEV and all96 new sectioned rows in TRAIN. We do not call five framing variants independent structural superfamilies. All document/template/derivation/paraphrase/renaming/leakage-group intersections are empty, all 20 contrast pairs remain together, and normalized substantive semantic signatures do not cross the split. Maximum new-to-old-DEV normalized source five-gram Jaccard is 0.059701. This lexical screen is descriptive, not proof of independence. V3 DEV is a development set after failure-informed design, not an untouched final benchmark. No folds1–4 are built or run.

| Target token lengths, including native assistant termination | Count | Min | Median | Mean | p95 | Max |
|---|---:|---:|---:|---:|---:|---:|
| refusal_targets | 40.000000 | 11.000000 | 11.000000 | 11.000000 | 11.000000 | 11.000000 |
| substantive_targets | 360.000000 | 71.000000 | 176.000000 | 172.816667 | 233.050000 | 263.000000 |

TRAIN contains 32 genuine refusals and 304 non-refusals (288 substantive plus16 empty), so refusal learning is retained. Balanced hard cases teach why similar absence/uncertainty surface cues can demand extraction. Target-length accounting is for the local training tokenizer and includes native termination; it is not measured generated-output efficiency.

**Machine curation:** a fresh input-only agent reviewed all120 opaque-ID packets, independently specified a 29-clause atom mapping, and preserved every owned claim/ref/atom without calling the author interpreter as an oracle. Final authored labels and independent predictions agree on all120 statuses and owned atoms, claims and refs. Exact supports pass the established frozen finite-policy validator. A separate initial curation saw status-bearing IDs before they were replaced, so it is explicitly not called fully blind; only the fresh opaque-ID review satisfies the blindness check. Review files, scripts, input hashes and adjudication are retained.

**Machine curated; not human reviewed; not independent final benchmark evidence.** Synthetic repeated English clauses and five new framing patterns provide targeted compositional diversity, not broad natural-language generalization. Reviewers share the frozen ontology and filesystem; there is no OS isolation or independent ontology-validation claim. No protected data were used.

**Exactly one configuration: DATA-ONLY.** Claims/evidence and contract already pass, uncertainty is strong, and gap/refusal errors concentrate in interpretable structures. Nothing measured isolates rank, LR or objective as the cause. Therefore retain rank/LR/objective, not a sweep. Fresh base + fresh adapter initialization; the failed V2 adapter is preserved and is not a V3 initializer.

| Configuration | Frozen value |
|---|---|
| Model | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` |
| Revision | `bdd404162d94997f390efbfa660eb3f21cbbc81d` |
| Dataset | `producer-targeted-v3.0`, SHA256 `b036707820a1851e94432319cc340cafec10a1b6093fab39b573cc4a47b9ecf0` |
| LoRA | rank8, alpha16, dropout0.05, bias none, CAUSAL_LM |
| Target modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| LR / optimizer | 0.0001 / AdamW, betas0.9/0.999, epsilon1e-8, weight decay0 |
| Objective | Per-example mean assistant-target plus native termination cross entropy; equal example weights |
| Passes / updates | 2 full TRAIN passes /168 optimizer updates |
| Microbatch / accumulation | 1 /4; effective batch4, no remainder |
| Scheduler | linear, warmup1 update; seed7; max gradient norm1 |
| Checkpoints | 84 and168; one complete DEV evaluation per pass |
| Training runtime | gradient checkpointing; BF16; eager attention; deterministic algorithms; TF32 disabled |
| Quantization | existing pinned NF4 4-bit with double quantization and BF16 compute |
| Sequence ceiling | 992, unchanged; observed local maximum988; no truncation |
| Generation | greedy, batch1, no sampling, one beam, cache true, max_new_tokens288; EOS[151645], pad151654 |
| Base weight SHA256 | `99b85155b7bb40344d8c3938c8ec1147b27028804bca5d2e5559cb8e6533747d` (historical binding; no weights read) |
| Authorization | false; local design and dry-run only |

Only data population and its mechanical schedule bindings change: 240->336 TRAIN, 60->84 DEV, 60->84 updates/pass, 120->168 total updates, checkpoints[60,120]->[84,168]. All mathematical optimization hyperparameters and the two-pass exposure remain unchanged. The scheduler horizon follows the unchanged two-pass rule. Generation/prompt/tokenizer/contract/quality thresholds are unchanged.

| Quality gate | Required |
|---|---|
| contract_validity | >= 1.0 |
| typed_gaps_f1 | >= 0.8 |
| semantic_completeness | >= 0.75 |
| claims_f1 | >= 0.95 |
| evidence_f1 | >= 0.95 |
| typed_uncertainty_f1 | >= 0.8 |
| refusal_precision | >= 0.9 |
| refusal_recall | >= 0.8 |
| accepted_semantic_outcomes | >= 0.75 |
| over_refusal_rate | <= 0.05 |
| Six catastrophic categories | each zero |

Undefined or nonfinite required metrics fail closed. Both checkpoints must have complete84-row evidence before selection. Among passing checkpoints, prefer completeness, then gap F1, then earlier step and adapter hash. If neither passes, stop the Producer LoRA branch; do not create V4 automatically. Token efficiency never overrides a quality failure. Future observations retain output median/p95, correct semantic atoms/token (claims/gaps/uncertainty/evidence separately), EOS-before-cap, duplicates, trailing prose and accepted-output token cost separated into correct refusal/empty versus substantive successes. No shortening objective or cap reduction is introduced.

**Runtime integration:** [runtime_binding.py](../../tuning/producer_v3/runtime_binding.py) pins unchanged runtime V2.1 SHA256 `8d1fd41d1ab059e47b1297c1c39cd29711acd8fa5446a60780f9a97faef1d1fa`. Prepared84-row prompts/IDs/masks are bound and validated with its exact record/generation validators. State-only local preflight exercises its actual corrected context, including generation_config=None and exact restoration, without any generation. Future execution must repeat real-object context preflight after adapter load, then cache probes before controls and full DEV.

The historical V2.1 authorization/session harness hardcodes checkpoint120 and60 rows; it is not reused as a V3 harness. V3 specifies steps84/168 and84 rows and implements a tested metadata sink that assigns correct V3 checkpoint/adapter/prompt identities before durable raw persistence. Generation mechanism remains the frozen low-level evaluate_records context with reference_trace=None; scoring follows raw persistence. A future training/cloud executor is intentionally absent and requires separate authorization and integration review. Design readiness does not claim deployment readiness.

Cost-sensitive controls use two optimized passes on six prospectively fixed IDs at each checkpoint, requiring exact tokens/decoded text/semantic results/stop reasons, positive finite timing and the retained4.438538339317307 tok/s floor. No global sys.settrace, profiling or in-process telemetry is introduced. The historical six reference-vs-optimized controls and4.629896x observer-removal proof remain unchanged evidence; a second paired2x test between two optimized passes would be logically inapplicable. Future telemetry is separate-process. Any context/cache/control/speed failure is NO_GO with collection/teardown, not retraining or a retry.

**Future runtime/cost projection, not a current price quote or authorization:** retain both full per-pass DEV checks. The first can detect refusal collapse while the final enables overfit/collapse comparison; removing it would materially reduce diagnostic evidence. There is no additional post-training full re-evaluation of the same saved outputs.

Historical training:118 clean inter-update intervals (exclude the first unanchored warmup timer and step61's embedded DEV pause), median 8.076018s and p95 8.590153s per four-example update. Training sequence-length ratio V3/V2=0.990607. Projected168-update training=22.40min. Measured V2.1 prefill-inclusive throughput=8.969012 output tok/s. V3 DEV target lengths mean 154.488, median 166.5, p95 232.85; these are output-length proxies, not generated predictions.

Two full DEV evaluations (168 outputs),24 control outputs and a four-probe cap allowance project 56.11min evaluation. Including15min setup/collection/teardown reserve: **93.51min, $2.0104 at the historical $1.29/hour A10 rate**. A deliberately conservative bound using training p95, all196 generations at288 tokens and the4.438538 floor is **251.01min / $5.3968**. Neither is a guarantee; initialization, new output lengths, hardware and training throughput may differ. The conservative case exceeds the prior $3 run cap, so that old authorization cannot be carried forward. Any future run needs a fresh price/capacity/budget decision and hard watchdog, with no automatic instance launch.

Local validation passed:420 tokenizer encodings, exact target-only masking/native termination, maximum target263<=288 and sequence988<=992, semantic labels, complete grouped split, every TRAIN example exactly twice across168 planned updates, no DEV in gradients, all120 fresh-review matches, runtime record/generation binding and context restoration. 10 named invalid fixtures rejected, plus all quality-threshold/catastrophic/nonfinite selection fixtures. These are no-model checks, not training or performance tests.

Preservation: 436 prior tracked files byte-verified; two preserved adapter files checked by size/mtime only, with zero weight bytes opened. Protected receipt remains UNCONSUMED. A local import-name collision attempted a historical dry_run module; the guard blocked its protected-evaluator import before that file could be opened. Local module resolution was corrected. The initial read-only preservation inventory byte-hashed the historical protected-evaluator wrapper, protected_population manifest and not-admitted receipt without parsing them or executing the wrapper; subsequent preservation checks use metadata only. No protected target data were opened, and no protected evaluation ran.

**Prospective final stop rule:** if a future valid V3 training/evaluation has no checkpoint passing every frozen quality gate, stop Producer LoRA. No automatic V4, additional data cycle, sweep or retraining. Return to architecture/model choice only under a separate task. An invalid infrastructure run does not become a quality pass and must not consume this rule as an excuse to alter gates.

No cloud, real/model generation, training, weight update, Auditor execution/design change, folds1–4, protected access, paid API, full pipeline, multi-round execution or push occurred. This release does not authorize any of them.

Reproduce local checks: `python -B tuning/producer_v3/dry_run.py`, `python -B tuning/producer_v3/leakage.py`, then `python -B tuning/producer_v3/release.py`. Authoring and sealing are one-time pre-freeze operations. Frozen outputs must not be edited after sealing. The dry-run is deterministic and must leave all bound hashes unchanged.

Artifacts: [V3 directory](../../tuning/producer_v3/), [configuration](../../tuning/producer_v3/experiment.json), [split](../../tuning/producer_v3/split.json), [review](../../tuning/producer_v3/blind_review/fresh_review.json), [local verification](../../tuning/producer_v3/dry_run_evidence.json), [freeze](../../tuning/producer_v3/freeze.json).
