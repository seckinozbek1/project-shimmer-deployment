# Evaluation runtime nullability fix

**EVALUATION_RUNTIME_NULLABILITY_FIX_READY**

New prospective release: **second-tuning-eval-runtime-v2_1**. READY authorizes no cloud or model execution. The failed V2 release remains byte-for-byte historical evidence.

## Exact failure and attribution limits

The cloud run tested `bee77af` and recorded evidence in `5bb23f1`. Its result remains `PRODUCER_CHECKPOINT120_INDETERMINATE` / `CHECKPOINT120_EVALUATION_NO_GO`. Verified base/adapter identities, zero generation, empty cache/control/DEV output, termination proof and the runtime V2 freeze are unchanged.

Call path:

```text
tools/checkpoint120_remote.py:execute
  -> run('cache_reference', first fixed control, probe=True)
  -> eval_runtime.evaluate_records
  -> evaluation_state.__enter__
  -> saved = {identity: deepcopy(vars(obj)) ...}  [old eval_runtime.py:89]
  -> TypeError: vars() argument must have __dict__ attribute
```

The nullable attribute is **generation_config**, with supported value **None / NoneType** on a non-generating module. The pinned source-supported owner is the nested **Qwen2Model**, below Qwen2ForCausalLM/PEFT. Transformers 4.51.3 `modeling_utils.py:1884` assigns `GenerationConfig.from_model_config(config) if self.can_generate() else None`. Qwen2Model does not directly inherit GenerationMixin, whereas Qwen2ForCausalLM does.

The cloud traceback directly records the failing expression and exception; it did **not** log the offending object/value. The specific nullable owner is therefore established from pinned source and deterministic local reproduction, not retroactively claimed as a captured remote object dump. The exact pinned assignment is also executed as an isolated AST effect test and produces None without importing a model runtime.

The old code enumerated owned config attributes across every submodule, then applied `vars()` unconditionally. Attribute existence does not imply a dictionary-backed config object. The old restore path repeated this assumption through `vars(obj).clear()`, `vars(obj).update(...)` and `vars(obj) == saved`; merely catching the initial TypeError would leave the abstraction unsafe. Deepcopy-based restoration also replaced nested config identities.

## Audit scope

`configuration_audit.json` records 76 static occurrences of `vars`, `__dict__`, `dict`, deepcopy and attribute operations across the old core, corrected core, snapshot helper, remote preflight handoff and tested cloud integration. It records source hashes and classifies each relevant path.

- All generic config capture/restore now uses **ConfigSnapshot**. There is no `vars(config)` or config deepcopy/asdict conversion in the new abstraction.
- Module attribute dictionaries are accessed only by `owned_dict`, which validates that the module actually owns a dictionary. It never calls through PEFT attribute delegation.
- Class dictionaries are inspected only for declared slots, to detect hidden unsupported state.
- Remaining deepcopy calls handle bound JSON protocol/generation kwargs, receipt copies and adapter-name comparison; they are not nullable config conversion paths.
- Ordinary `dict(...)` calls construct evidence/authorization records, rather than coercing arbitrary configuration values.

## Type-safe state graph

The helper captures an explicit graph of references and immutable leaf values without mutating the source. Restoration updates supported containers/objects in place, retaining root and nested identity, aliases, cycles and mapping order. Nullable values stay None; absent owned attributes remain absent.

| Form | Supported behavior / proof |
|---|---|
| None | Recorded and restored as None; no introspection or invented attributes |
| Empty/populated dict | Exact items/order/reference restoration; existing use_cache key enabled temporarily |
| OrderedDict | Same identity and original order restored |
| Namespace / ordinary dictionary-backed config object | Owned attributes restored in place, including nested None |
| Real pinned Qwen2Config / GenerationConfig | Constructed from local config metadata only and exercised through the corrected context |
| Dataclass | Fields and owned extra attributes restored without asdict serialization |
| Slotted dataclass | Declared fields supported; unregistered hidden slots rejected |
| Frozen dataclass | Identity/state preserved; immutable cache field not rewritten; explicit frozen generation kwargs remain authoritative |
| Immutable scalar / tuple | Same reference retained; mutable descendants of tuples restored separately |
| Lists | Supported as configuration data, including nested shared/cyclic lists; no claim that a list is a valid Transformers generation_config |
| torch.dtype | Explicit immutable identity leaf in the future pinned runtime; Torch was not imported locally |
| Unsupported mutable/opaque form | set, bytearray, arbitrary Mapping/read-only proxy, container subclass, callable and non-dataclass hidden slots fail closed before eval transition |

A top-level causal LM still needs its architecture-appropriate configuration for actual generation. Lifecycle acceptance of None/scalars does not assert that arbitrary replacement configs are valid model inputs. None is legitimate for the non-generating submodules that triggered this defect.

## Restoration invariants

The corrected context captures owned config roots plus nested state, each module's mixed training flag, checkpoint flags/functions, owned adapter activation fields, parameter identity/dtype/device/requires_grad/version, and gradient-buffer identity/version. It restores state in finally on normal, setup-exception, generation-exception and early-termination paths. Added owned attributes are removed, prior attribute identities rebound, nested config identities preserved, adapter activation and requires_grad flags restored.

Checkpointing remains enabled as in V2 but inactive in eval; no hooks are disabled/re-enabled. Explicit use_cache=True remains unchanged. Parameters are never cast, copied, merged or updated by this context. An unexpected weight version, dtype/device or parameter-identity change fails closed rather than attempting to reverse tensor mutations. Restoration attempts for other state still occur when an invariant is violated.

Nested contexts preserve the outer eval state and restore the original mixed flags at final exit. A setup exception after partial flag/config mutation restores the initial state. A stand-in generation exception with child generation_config=None restores state, as does KeyboardInterrupt.

## Deterministic validation and effect proof

**92 tests pass; 11 named effect proofs are retained.** The prior 50-test suite is carried forward against the new runtime, with explicit adaptations for mandatory context preflight and the no-weight-access constraint. Forty-two tests cover the new type/restoration/preflight cases.

The exact nullable regression follows:

1. **Neutralise:** substitute the historical V2 context with child generation_config=None.
2. **Fail:** obtain the same `TypeError: vars() argument must have __dict__ attribute` before entry/generation.
3. **Restore:** reinstate the corrected context.
4. **Pass:** entry/exit succeeds and all observed state/identity matches the initial state.

Named effects additionally prove unsupported-type rejection before transition; setup exception restoration; stand-in generation exception restoration; early-termination restoration; nested mixed flags; missing context-preflight denial; failed-preflight/no-retry denial; actual pinned-source nullable assignment; three preserved optimizer/backward guard denials; and NO_GO evidence-before-teardown handoff.

Checks also cover fresh guarded prompt/token identity for all 60 rows, adapter evidence binding, fixed six control IDs, exact speed thresholds, authorization rejection, cache lifecycle stand-ins and cache source guards, raw-output durability before scoring, separate telemetry process, no-stitch, no-resume, protected/Auditor/network/weight denial and exact semantic-protocol comparison.

All lifecycle/model calls use explicitly named stand-ins. Actual Qwen2Config and GenerationConfig objects and pinned source AST are exercised without importing Torch/PEFT, creating a neural model, opening weights, or invoking real generation. No CUDA/cache/throughput equivalence is claimed.

## Mandatory future REAL_RUNTIME_CONTEXT_PREFLIGHT

After the separately authorized loader verifies the exact pinned base and saved adapter, the future controller must call `remote_preflight.run(session, model, torch_api, persist, collect_and_terminate)` before cache probes.

This inventories each owned config field's module index, attribute name, Python type, None status and shared-root identity grouping, then enters/exits the actual evaluation context **once without generation** and verifies restoration. It returns `REAL_RUNTIME_CONTEXT_PREFLIGHT` evidence only on success.

The generation mechanism rejects a model without a successful in-process receipt. Cache admission requires context preflight; full DEV additionally requires the same resident model, passing cache/six-control gates and unchanged protocol. Failed attempts cannot be retried in the same session/model registry. Old V2 authorizations cannot authorize V2.1.

Failure records NO_GO and invokes the controller's collection/termination callback; that callback runs even if evidence persistence raises. The callbacks are injected operational interfaces, not a new provider launcher. Tests execute their ordering with spies; no cloud operation occurs locally. A future cloud integration must supply the established evidence collection/termination implementation and bind the new freeze, rather than invoke the historical V2 controller unchanged.

## Semantics and prospective freeze

Exactly unchanged: model ID/revision/base hash; adapter/config hashes; prompts/tokenizer/token IDs; canonical 60 DEV membership/order; greedy decoding; cap 288; EOS [151645]; pad 151654; BF16/eager/quantization constraints; contracts/scoring/selection gates; six fixed controls; cache probe requirements; no-stitch/no-resume rules.

Speed gates remain **>=4.438538339317307 prefill-inclusive output tok/s** and **>=2.0 paired optimized/reference ratio**. Controls remain positions **0,10,20,30,40,50**: Producer documents **045,055,140,150,160,275**. No thresholds, sample substitutions, or semantic acceptance rules changed.

Only protocol additions are the new release identity/parent binding and mandatory real-runtime context preflight. The protocol equality test removes precisely these metadata/preflight keys and requires everything else to equal V2.

Adapter SHA-256 binding remains `3f1e12d107f1206641902565b28ea6217d70ff2768c321a216227dbc21b702a6`; base-weight binding remains `99b85155b7bb40344d8c3938c8ec1147b27028804bca5d2e5559cb8e6533747d`. Their bytes were not reopened in this task. The preserved successful cloud hash/tensor-verification evidence is bound instead.

The new `freeze.json` binds the corrected runtime/helper, protocol, tests/results/effect proofs, configuration audit, this report, exact reused prompt tokens and relevant source/config dependencies. It has no execution authorization and refuses automatic replacement. Its SHA-256 is emitted by `release.py verify` and reported in the completion message; no self-referential hash is embedded in this bound report.

## Preservation and limitations

**217 historical files are byte-verified.** Ten weight/archive/Auditor artifacts are checked through prior hash bindings and unchanged size/mtime metadata only, honoring the explicit no-weight-access/Auditor boundary. This is not represented as a fresh byte-level proof of those excluded artifacts. The failed cloud archive is weight-free and remains hash-verified.

Full PEFT 0.15.2 package source is still unavailable locally. The failed cloud evidence does preserve the actual preparation-helper source and its source hashes; this task uses that evidence and does not infer broader wrapper API guarantees. Actual loaded model/PEFT hierarchy validation remains mandatory in the future context preflight.

Historical statuses remain `PRODUCER_CHECKPOINT120_INDETERMINATE` and `CHECKPOINT120_EVALUATION_NO_GO`. The original pilot remains `SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE` with `FULL_GROUPED_CV_CONTINUATION_RECOMMENDED=false`. No new checkpoint-quality result is inferred.

Protected receipts remain unconsumed; Auditor remains untouched. No cloud, model generation, model-weight access, training, protected-target access, Auditor execution, folds 1-4, paid API, full pipeline, multi-round or push occurred.
