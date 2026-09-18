# Frozen decoding policy restored at every local generate site

Status: **DECODING_POLICY_RESTORED_NEW_EXECUTION_SEALED**. Local deterministic validation only.
**No cloud execution is authorized or performed by this work.** The next run needs separate
operator authorization. Nothing was pushed.

## What was wrong

`scripts/final_models.py` `verify_runtime` turns on `torch.use_deterministic_algorithms(True)`
for the whole process. Both local generate call sites passed no decoding arguments, so each
checkpoint's own generation config governed `generate()`. The Producer checkpoint's config
samples with top-p, so transformers 4.51.3 built a top-p warper, whose float32 CUDA `cumsum`
torch 2.5.1 rejects under strict determinism. Every local call raised `RuntimeError` at its
first sampling step, after prefill and before its first token (run `88323b86`, 2026-09-17).

Two facts widened the correction beyond the failed run's three agents:

- There are two local generate sites, not one. `agent_wrapper.call_local` serves all seventeen
  local agents in `_LOCAL_PROFILE` (eleven Producer-backed, six Auditor-backed); the final
  Producer branch differs only in how the model is loaded. `agent_wrapper.call_qwen` serves
  REDACTOR. A third site, the chat parser, loads the same REDACTOR model.
- The measurement below shows two of the three pinned families would have raised. Correcting
  the final-Producer branch alone would have moved the failure, not removed it.

## The kwargs now passed, and where each value comes from

No decoding value is typed into a wrapper. `scripts/decoding_policy.py` reads each backend's
kwargs from the file `config/decoding_policy.json` names, at call time, before the model loads.

| Site | Backend | Kwargs passed | Source of every value |
|---|---|---|---|
| `agent_wrapper.call_local` | `local_producer` | `do_sample=False`, `num_beams=1`, `use_cache=True`, `eos_token_id=[151645]`, `pad_token_id=151654` | `tuning/producer_v3/evaluation_protocol.json`, `generation_kwargs`, line 436 |
| `agent_wrapper.call_local` | `local_auditor` | `do_sample=False`, `num_beams=1`, `use_cache=True`, `eos_token_id=[32000, 32007]`, `pad_token_id=32009` | `tuning/auditor_canonical_execution/evaluation_protocol.json`, `generation_kwargs`, line 73 |
| `agent_wrapper.call_qwen`, chat parser | `qwen_local` | `do_sample=False`, `num_beams=1`, `use_cache=True` | `config/decoding_policy.json`, declared **new** for REDACTOR |

Every site also passes its own `max_new_tokens`, which is the pipeline's per-agent budget and
never the protocol's. The protocols' `max_new_tokens` (288 and 192) are evaluation caps; they
are listed in `evaluation_only_keys` and withheld. Everything a protocol does not name stays
with the checkpoint, exactly as during evaluation: the measured `repetition_penalty` of 1.05
is still applied on both Qwen families, and is inert once `do_sample` is false.

**Drift is detectable.** Each restored backend's declaration pins the protocol's SHA-256 with
CRLF normalised to LF, so a checkout's line endings are not drift but a changed decoding value
is. A drifted protocol raises before any weights load, and `final_models.admit_ordinary` calls
`decoding_policy.summary()` so a drifted or unsound declaration refuses the whole run before
`verify_runtime` turns determinism on. The sealed manifest records the resolved policy, and
the protocol files now travel inside the project archive and the container image.

**On eos and pad, my decision: pass them.** The protocols fix them, they are part of what the
checkpoints were validated under, and the Producer's protocol deliberately narrows the stop set
from the checkpoint's `[151645, 151643]` to `[151645]`. Leaving them out would have decoded
under a stop set no evaluation ever used. Because they are passed, the stop-reason logic at
`agent_wrapper.py:852` and `:920` must no longer read the model's own config, or it would score
against a set `generate()` did not use, so both sites now call `decoding_policy.effective_eos`:
the policy's stop set when it names one, the model's own otherwise. For REDACTOR, which has no
protocol, nothing is passed and the model's own config still governs, unchanged.

**REDACTOR is new, not restored.** No frozen protocol exists for that role, so its greedy policy
is recorded with `status: "new"` and a stated reason, it is reported as new on every call and in
the sealed manifest, and it carries no eos or pad, because no evaluation fixed those for it.

## Both generation configs, as measured

Read from the local Hub cache by `tools/ordinary_final_decoding_gate.py`. The Producer and
Auditor digests match the pins in `config/final_models.json`.

| Family | Model | `do_sample` | `temperature` | `top_k` | `top_p` | `repetition_penalty` |
|---|---|---|---|---|---|---|
| Producer | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` | true | 0.7 | 20 | 0.8 | 1.05 |
| Auditor | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` | absent | absent | absent | absent | absent |
| REDACTOR | `Qwen/Qwen2.5-7B-Instruct` | true | 0.7 | 20 | 0.8 | 1.05 |

The Auditor family never sampled, so it would not have raised. The Producer and REDACTOR
families both would have. This is why the correction covers all three sites rather than one.

## What the gate proves

`tools/ordinary_final_decoding_gate.py` imports torch and transformers for real processor
construction, denies weight loading and the network, and calls no `generate()`. For each family
it reads the cached generation config, captures the kwargs the live call site hands `generate()`
through a recording stand-in model, builds the chain transformers itself would build from that
config plus those kwargs, and applies it to random logits with `torch.cumsum` instrumented.

| Family | Chain under the restored kwargs | Float cumsum | The checkpoint's own config, same instrument |
|---|---|---|---|
| Producer | `RepetitionPenaltyLogitsProcessor` | 0 | 4 processors ending in top-p, 1 float cumsum |
| Auditor | empty | 0 | empty, 0 |
| REDACTOR | `RepetitionPenaltyLogitsProcessor` | 0 | 4 processors ending in top-p, 1 float cumsum |

On CUDA under `torch.use_deterministic_algorithms(True)`, the mode `verify_runtime` sets, the
restored chain passes for all three families, and the raw chain raises `cumsum_cuda_kernel` for
the two sampling families. That raw-config run is a positive control: it proves the instrument
is live rather than silently observing nothing, which is the failure mode a green check would
otherwise hide. A separate probe confirmed that every other op on the greedy path (argmax, the
repetition penalty's gather and scatter, the KV-cache concatenation, index_select, softmax,
embedding, matmul) passes under the same mode, and that the pinned peft strips only
`adapter_names` before forwarding, so the kwargs reach the real `generate()` unchanged.

## Gate results

| Gate | Result |
|---|---|
| Decoding gate, three families | PASS, 3 tests, 5 neutralize/fail/restore/pass proofs |
| `scripts/decoding_policy_checks.py` | PASS, 8 checks |
| Integration no-generation gate | PASS, 112 tests, 11 proofs, activation PASS |
| Startup and preparation gate | PASS, 18 tests, 3 proofs |
| Report-recommendations mutation gate | PASS, 15 of 15 |
| Main gate, check 262 | PASS |

Every proof records how many times the neutralised branch actually ran, so a neutralisation that
changes nothing is counted as a failed proof rather than a passed one (THIRTEEN-B).

**The main gate is not green in this environment, and was not green before this change.** To
separate the two, the same gate was run on a clean worktree of the parent commit `09aa90f` with
the same interpreter and host. Receipt: `main_gate_comparison.json`, logs
`baseline_gate_at_HEAD.log` and `main_gate.log`.

| | Parent commit | Working tree |
|---|---|---|
| Total checks | 262 | 263 |
| Failures | 30 | 28 |
| New failures introduced | | **none** |

The 28 failures are identical in both and all environment-caused: 17 are
`ModuleNotFoundError: No module named 'fastapi'`, the rest follow from that and from an absent
`pypdf`, in an interpreter that lacks both. Checks 28 and 31 fail only at the baseline because a
fresh worktree has no gitignored `input/` directory; that is a worktree artifact, not a fix.
The total grew by one because check 262 was added, and it passes.

One existing check needed a fixture correction, not a code change:
`report_recommendations_checks.test_native_template_and_eos_telemetry_on_local_call` ended its
stand-in generation on token 9, which the stand-in model calls EOS but the Producer protocol
does not. Under the restored policy that is correctly no longer EOS. The fixture now ends on
the protocol's own stop token, read from the policy rather than typed, and asserts the same
behaviour it always did. Its existing mutation proof still passes.

## What did not change

Deterministic mode, model weights, adapters, HPO settings, the pairing contract, the telemetry
architecture, the workload, routing, budgets and the review flags are untouched. No new
telemetry file, event or schema version exists.

## Failure identity on the receipts

The retry recorded `RuntimeError` six times and nothing else, and the cause had to be re-derived
from source and a local probe. Failed local calls now also record the exception's class module,
the raising frame and the innermost project frame, as `file:line:function` basenames. That is
identifiers only, never message text, so it carries no document content and no credential, which
is why it fits the existing type-only design rather than conflicting with it. It is added on the
three receipts that already record a failure type, on failure only: a successful receipt carries
no failure fields at all. The same identity is written to the runner's `terminal_error.json`.

## Sealed identity

Directory: `docs/fix/ordinary_final_cloud_run_v3`. Classification `PREPARED_NOT_AUTHORIZED`.
It contains no operator authorization, launch intent or execution claim. The old controller
stays bound to the consumed identity and cannot be used for this bundle.

| Item | SHA-256 |
|---|---|
| Execution manifest | `a2a8be14f3d9822fcf5dd2b5beb50bfd6e6586f78d5c1dc0aa219534a3d88bd7` |
| Seal | `7638c3503f82607747cc744af27f8dc245f950a181d31afc42ef558409aeb8fc` |
| Project archive | `b70cbded794a9ad97dbc50f84db996fec4f50706df43ae69c7d5389f2b28879d` |
| Assets archive (rebound, unchanged) | `8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6` |

Bound source commit `e4b52e6`. The manifest records the resolved decoding policy per backend,
with each source path, digest and kwargs. The archive carries `config/decoding_policy.json`,
`scripts/decoding_policy.py` and both protocol files, and excludes the checks module, which the
runtime never imports. Asset verification passed independently against the new manifest: 122
members, all three refs resolving to their pinned snapshots at exactly 40 bytes, no model loads
and no network.

The asset archive is bound again rather than rebuilt: its recorded inventory is compared member
by member and hash by hash against what the builder would produce now, its bytes are re-hashed,
and it is hard-linked into the new bundle. This avoids writing a second 13 GB copy on a volume
with 20 GB free, and it is admitted only on exact equality.

Known Auditor limitations are unchanged and were not measured here: external macro F1 about
0.8010, historical about 0.4576, historical OMISSION recall 1 of 12. This work measured no
inference quality. It proves that the decoding policy the evaluations used is now the policy the
pipeline uses, and that the op which stopped the last run is no longer on the path. It does not
prove the run will complete.
