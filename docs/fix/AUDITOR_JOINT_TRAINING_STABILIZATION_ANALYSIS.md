# Saved-state update1 transition analysis

**AUDITOR_JOINT_TRAINING_STABILIZATION_UNISOLATED**

One local numerical analysis of the completed `ceabb0afda9c87812e2461fd70c505fb6f9e4b9a` run. No model forward, optimizer execution, training, cloud query, retry or historical-evidence modification. Reproducible calculations and input SHA-256 bindings are in `auditor_classifier_lora_current_runtime_run/local_transition_analysis/results.json`; implementation: `tools/analyze_auditor_joint_transition.py`.

The current-runtime rebase succeeded. The remaining failure is representation-side after the first joint update, with a classifier-LoRA AdamW first-step overshoot the leading hypothesis. The saved evidence cannot isolate that update from training-mode/dropout effects. The historical execution verdict remains INDETERMINATE, V2 remains NOT_READY, and HOLDOUT remains unconsumed.

## Observed transition

Each microbatch contains one row. Update1 rows differ from the attempted update2 row; these are not paired causal comparisons. Gradients below are accumulated through each update1 microbatch. All recorded classifier-boundary tensors are finite FP32.

| State | Raw hidden L2 | Standardized L2 | Max absolute standardized | Logits min / max | CE |
|---|---:|---:|---:|---:|---:|
| Update1 micro1, pre-step | 89.3906443 | 52.8902928 | 3.1450653 | -3.9612291 / 8.9459600 | .0020290280 |
| Update1 micro2, pre-step | 89.6346765 | 52.4871663 | 3.6501560 | -5.9171915 / 4.1812048 | .0031689210 |
| Update1 micro3, pre-step | 89.7568103 | 95.0948638 | 4.2853537 | 7.3141956 / 13.1176996 | .0106253373 |
| Update1 micro4, pre-step | 87.4180194 | 48.9072606 | 2.8133297 | -4.3349929 / 3.7895713 | .0083428919 |
| Attempted update2 micro1 | 90.5614721 | 128.4170702 | 7.5984044 | -40.2182007 / 94.3595200 | 134.5777283 |

Logit max-absolute values are respectively 8.9459600, 5.9171915, 13.1176996, 4.3349929 and 94.3595200. Update1 mean CE = .00604154455. Update2 stopped before backward; no update2 gradient or optimizer step exists. No immediate post-step forward exists between these rows.

| Accumulated gradients | Head L2 | LoRA L2 | Combined L2 |
|---|---:|---:|---:|
| Update1 micro1 | .03738518 | .61460672 | .61574270 |
| Update1 micro2 | .06041185 | .96818967 | .97007259 |
| Update1 micro3 | .29089567 | 2.25411735 | 2.27281001 |
| Update1 micro4, before clip | .27418018 | 3.68805440 | 3.69823202 |
| After clip | .07413816 | .99724778 | .99999980 |

| Saved parameter comparison | Head | Classifier LoRA |
|---|---:|---:|
| Actual optimizer-group LR | .001 | .0001 |
| Initial parameter L2 | 5.915768375 | 25.406508052 |
| Post-update1 parameter L2 | 5.917491085 | 25.414635365 |
| Difference of norms | .001722710 | .008127313 |
| Actual delta-vector L2 | .110850664 | .385228587 |
| Delta / initial L2 | 1.87382% | 1.51626% |
| Maximum absolute coordinate delta | .00100000203 | .000100000063 |
| Coordinates changing by at least 99% of LR | 99.7803% | 94.7750% |

Combined parameter delta L2 is .400860242. Some small LoRA B matrices changed much more relatively: layer0 k_proj 10.3398%, layer0 q_proj 9.9297%, layer5 v_proj 9.5417%. Tiny changes in aggregate parameter norm conceal substantial directional changes.

Executed code sets model/head to train mode for joint updates, with LoRA dropout .05; feature extraction and parity controls use eval/inference mode. Actual dropout masks and per-call module mode flags were not saved. Base forward uses BF16 autocast, followed by explicit FP32 hidden conversion; normalization, head, loss and trainable parameters are FP32. Recorded hidden dtype is after conversion, not a direct measurement of every internal activation dtype.

## AdamW and clipping

Fresh AdamW uses betas (.9,.999), epsilon 1e-8, zero weight decay and no scheduler. For the first step with zero moments, bias correction gives `delta = -LR * clipped_gradient / (abs(clipped_gradient) + epsilon)`. Thus even a small gradient can yield approximately one LR per coordinate. The observed deltas nearly saturate this scale: LoRA L2 .38523 versus LR*sqrt(N) .38655.

Clipping worked: gradient norm fell from 3.69823 to .9999998 (scale .2703994). It did not impose a parameter-step trust region. A hypothetical SGD step using the same clipped gradients and group LRs has L2 .000124264; the actual AdamW delta is about 3225.88 times that comparison. This is not an optimizer replay. Per-coordinate gradients and Adam moments were not saved, so the exact difference from an unclipped AdamW step cannot be reconstructed.

## Normalization

TRAIN population std: min **.154221818**, p1 **.185460404**, p5 **.208628768**, median **.314133823**. Zero dimensions are at/below 1e-6, 1.01e-6, 2e-6, 1e-5, 1e-4, .001, .01 or .1. There is no clamp-driven amplification pathology.

Largest inverse-std multipliers: dimension2555 = 6.484167; 2683 = 6.461074; 1540 = 6.227270; 2315 = 6.065070; 1506 = 5.986094. Median inverse std = 3.183357. Ordinary fixed scaling can amplify a representation shift, but post-step hidden coordinates were not retained, so alignment with these dimensions is unavailable.

## Saved-feature counterfactuals and bounds

Failing row `shimmer2-auditor-document-236`, DIVERGENCE, has saved initial **eval-mode** hidden L2 90.0141086, standardized L2 92.6041901 and max absolute standardized 4.2402196. Its initial logits in MATCH/DIVERGENCE/OMISSION/ADDITION order are [6.8186474, 11.4557505, 7.5136447, 7.6048317], CE .04912646.

Applying only the saved post-update1 head to that same saved vector gives logits [10.3252754, 9.5723305, 4.0199542, 3.9784436], CE **1.14130211**, maximum logit change 3.6263881. Across all saved TRAIN vectors the head-only counterfactual mean CE is .21269076, accuracy .93973214, maximum CE 5.99848080; 104 predictions change. These are affine calculations, not observed post-update model performance.

For any unknown post-update standardized vector z and true class y, the absolute CE change due to the head alone is bounded by `max_k(||deltaW_k-deltaW_y|| * ||z|| + |deltab_k-deltab_y|)`. Using the actual recorded post-update norm 128.4170702 gives **12.687737**. Consequently the old head on the actual post-update vector would still have CE at least **121.889991**, allowing normal FP32 rounding. The head change is harmful but cannot be the principal explanation of 134.58. The standardized representation changed by at least **35.812880** in L2 relative to the saved eval vector; this includes any mode/dropout contribution.

## Instability classification

| Candidate | Evidence assessment |
|---|---|
| HEAD_UPDATE_DOMINANT | Ruled out as the main explanation by saved-feature calculations and the post-vector norm bound; non-negligible contribution remains. |
| LORA_UPDATE_DOMINANT | Leading causal hypothesis, not isolated from mode/dropout. Substantial measured first-step adapter deltas precede failure. |
| FIXED_NORMALIZATION_AMPLIFICATION | No tiny-std/clamp pathology. Ordinary scaling of a changed representation remains possible. |
| TRAIN_MODE_DROPOUT_INSTABILITY | Unresolved. The failing row has no pre-step train-mode counterpart and no post-step eval counterpart. |
| OPTIMIZER_FIRST_STEP_OVERSHOOT | Strongly localized hypothesis, especially for LoRA; near-LR coordinate steps measured despite clipping. |
| MIXED_OR_UNISOLATED | Final classification. Representation-side failure established, exact LoRA-versus-dropout mechanism unavailable. |

Unavailable: post-step full hidden vectors, matched train/eval forwards for the failing row, dropout masks, per-coordinate gradients, Adam moments, an immediate post-step forward, and final full base-state hash. No unavailable tensor is inferred as an observation.

## Exactly one stabilization design — hypothesis only

**Change classifier-LoRA LR from 1e-4 to 1e-5.** Keep head LR .001, dropout .05, optimizer otherwise unchanged, rank8, target modules, base model, data, normalization, head initialization, quality gates, DEV/HOLDOUT boundaries and update schedule unchanged. No warmup, head freeze or dropout removal is combined with this proposal. No runnable paid-run package or new authorization is prepared.

For identical first-step gradients and moments, this scales the LoRA delta approximately tenfold to L2 .0385229, maximum coordinate step 1e-5, global relative delta .151626%. This is an analytic first-step estimate, not a prediction of later gradients or guaranteed stability. It directly reduces the measured suspect transition while changing one scalar.

## Conditional reuse of successful current-runtime artifacts

Preserve head-200, current mean/std, current TRAIN features and checkpoint0; **do not initialize from the failed post-update partial state**. SHA-256 identities:

- head-200: `027c880e6c10a13f3e7354d12665ffacca5f7d68836291feaf195c167c13f915`
- mean: `370b185841099279202b09540b45231f70fc1b109795faf520369964831678f5`
- std: `1221aff7ce64f090635267884183baabbd521e9a1738221555f074b4478f304a`
- current TRAIN features: `06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287`

Reuse is **conditionally possible, not presently certified for an uncreated runtime**. Bind this run's source, pinned base revision, initial adapter/config, token/prompt hashes, row order, package versions, quantization, k-bit preparation, dtypes and eval mode from its execution evidence. Artifact hashes alone do not prove function compatibility.

A future authorized implementation must fail closed unless live reference/fork controls reproduce this current cache, followed by **one full TRAIN inference pass** checking saved features/logits/predictions/metrics/CE with fixed mean/std/head. That pass also supplies the joint-training baseline; do not perform a second 1792-row feature extraction or refit normalization/head. Sixteen controls alone do not certify every row. Any mismatch is NO_GO, without silent cache fallback or refit. This avoids importing the old incompatible cache while retaining a full binding check.

LR reduction alone has no material runtime/cost benefit. Reuse can avoid this run's 386.592469-second extraction plus 1.586669-second head fit: about **6.47 minutes / $0.1391** at the recorded $1.29/hour, before transfer/check overhead. One full TRAIN consistency pass remains. These are historical-rate estimates, not a current cloud quote or future-run preflight.

## Local validation before any future authorization

Local numerical tests cover parameter deltas versus differences of norms, the CE bound, first-step clipping behavior and preserved input hashes. Before any future cloud authorization, implement and locally test the single LR change, unchanged groups/scope/gates, exact-runtime reuse identities and fail-closed mismatch cases, and ensure only one full TRAIN verification pass is scheduled. Test explicit mode/dtype reporting and preservation of matched control hidden vectors around the first step so future evidence can separate train/eval effects. Live compatibility remains an admission gate, not something local algebra can certify. No such future cloud work is authorized by this analysis.
