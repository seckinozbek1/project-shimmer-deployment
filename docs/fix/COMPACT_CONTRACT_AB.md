# Compact extraction and auditor contract A/B — local only

## Decision

**REMOTE_CONTRACT_AB_READY** — deterministic source/contract readiness only.

The [secure remote feasibility stage](REMOTE_SHORT_BURST_SECURE_FEASIBILITY.md)
remains closed with `CLOUD_FULL_RUN_NOT_ELIGIBLE`. This local correction does not
change its measurements or establish model reliability. No generation was run.
The next step requires separately authorized bounded remote measurement.

Starting HEAD: `1aa4696ab2ea95c6757db0eb18d94cd0c0ba6662`.
Historical executed source: `c342033e5d09654cdbaaf283879a9ee37764146b`.
Implementation and evidence commit: `19910604c00b7d132ae04cad492a8320dd6a73c3`.

Evidence: [readiness](compact_contract_ab/readiness.json),
[validation](compact_contract_ab/validation.json),
[token budget](compact_contract_ab/token_budget.json), and exact prompt files in
[the artifact directory](compact_contract_ab/).

## What the remote models actually received

The maintained probe called `wrapper.dispatch(prompt, max_new_tokens=384)`
directly. It did not call `run_task`, `prompt_template`, `_stable_agent_block`,
or `_role_anchor_text`. Normal Shimmer identity, constitution and generic
DO/DO-NOT blocks therefore were **not** additional system messages in these calls.
The optimized loader rendered one user message through the configured tokenizer,
with `add_generation_prompt=True`, then tokenized with `add_special_tokens=False`.

The preserved rendered hashes are reproduced exactly with the pinned cached
tokenizers, including whitespace, Python schema representation and JSON spacing:

| Call | Input tokens | Rendered SHA-256 |
|---|---:|---|
| compact_processor; serial_producer | 610 | `8e9e24361119625e6dad41616c38d8371794a1d79dfbd23ed5d49f64856d155e` |
| source_copy_reference | 482 | `dea857a71db6db817dce4af130762405a19858e6a2bda813d59cd3c0c17f4cb2` |
| independent_auditor | 1,875 | `9a77d7299564580be380f2b823bdde6f2b4413e2e3694bba128eb57dcc0ce57e` |

Each old user prompt and rendered prompt is retained byte-for-byte. Separate
`old_*_contract.txt` files preserve the schema text. `fixture.json` preserves
the dynamic original/extraction inputs. The serial producer reused the compact
prompt; no serial auditor ran because its producer failed.

Producer user content was extraction instruction → generic PROCESSOR contract →
bounded payload. The payload carried one `s0` owned span, ledger metadata and full
source, with both claim IDs, both REF IDs and the missing-date sentence. There was
no boundary context for this fixture. Qwen's native template inserted its default
“You are Qwen, created by Alibaba Cloud. You are a helpful assistant.” system text,
then `<|im_start|>user` content and an assistant generation prefix.

Auditor user content was fidelity instruction → generic VERIFIER contract,
including the entire typed numeric Finding-record instruction/example → document
ID → original source → authored producer extraction. Both refs and the missing-date
question were present. No applicable convention rule was supplied. The template
rendered `<|user|>\n…<|end|>\n<|assistant|>\n`, with no system message.

Stop policy was seed 7, `do_sample=False`, 384 new tokens, model generation
`max_time=25.0`, and the checkpoint's configured EOS IDs. There was no custom stop
string. TTFT was unavailable. The ceiling and timeout remain unchanged.

## Failure mechanisms and correction

### Producer

The old output schema described `section_id` and `draft_text` merely as strings,
offered a generic finding example, and said to express structure as more items.
The later payload instead required exactly one item per owned span, with the
same short alias in two fields, including the source-copying name `draft_text`.
It supplied no complete compact worked shape. Missing-information fields appeared
in instructions but not in the generic example or required PROCESSOR fields.

The remote answer followed the generic finding/copying shape: two prose-bearing
items for one alias, no date question, 259 tokens, EOS-complete but hydration-invalid.
There was no hidden Shimmer source-copying system prompt in this dispatch; the
separate source-copy control explicitly requested copying and also omitted content.
Native Qwen rendering is reproduced and is not evidence of a template failure.

The correction is a task-specific contract, shared by optimized ordinary extraction
and the maintained probes. One `span` alias owns arrays of `claims`, `questions`,
`uncertainty`, selected `refs`, and explicit `status`. Multiple observations stay
in their owner's arrays. An examined span without semantics is `empty`; omitted
ownership or `refused` cannot become a successful extraction. The model never
emits source text, offsets, unit identity or ordering fields.

Python maps this shape into the existing canonical PROCESSOR item, then calls
the original hydration validator. The existing ledger/aliases, exact source bytes,
coverage checks, ordering, hashes and provenance remain authoritative. There is no
second source index. Unknown fields, copied prose fields, duplicate ownership,
duplicate semantic strings, ungrounded claim/ref IDs and invalid status are refused.

The normal optimized wrapper also uses the scoped contract and role anchor, so its
legacy drafting description cannot reintroduce a source-copy instruction. Generic
unbound contracts and ordinary 1536-token partition budgets are unchanged.

### Auditor

The old instruction said to compare original and extraction, but also said “verify
both figures.” Before the actual data, the generic contract asked for numeric
relations, record verdicts, quantities, units and rule IDs. Its worked example
contained `CONV-001`, one ref and numerous redundant fields. No rule required the
original's planned and reported quantities to equal one another.

The observed answer compared those two original quantities, invented a convention
attribution, omitted required evidence and duplicated a Finding record before
truncating at 384 tokens. These are demonstrated prompt defects consistent with
the failure; the causal improvement in model behavior is still unmeasured.

The scoped fidelity contract defines MATCH as faithful preservation of the original,
including each quantity's label and information gaps. DIVERGENCE, ADDITION and
OMISSION describe changes introduced by extraction. It contains no numeric equality
rule and no example teaching a special answer for the fixture's two numbers.

Generated fields are ordered `finding`, `ref_ids`, concise `reasoning`, `severity`,
`confidence`. Python stamps only routed identity, paragraph and item kind. Selected
refs must include every required ref and belong to the available set; missing or
invented refs and rule attribution are refused. Rule IDs in the reason and unselected
REF citations in the reason are also rejected. Insufficient evidence means refusal;
an ordinary empty result is valid only for an explicitly empty comparison.

This is an existing typed VERIFIER fidelity item, not a numeric-governance Finding
record. `relation`, `record_verdict`, numeric values/units and rule attribution are
inapplicable without a routed numeric rule, so no values are fabricated. The
general Finding-record schema and validators remain unchanged and regression-tested.

Both scoped wire formats require a complete JSON response before adaptation and
the usual canonical validation. No recovery from a complete prefix plus a truncated
suffix is permitted. Moving critical fields earlier does not authorize partial JSON.
The separate backend truncation check continues to prevent acceptance at the cap.

## Actual checkpoint facts

| Role | Fixed repository / revision | Cached configuration / tokenizer |
|---|---|---|
| Producer | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` / `bdd404162d94997f390efbfa660eb3f21cbbc81d` | `Qwen2Config`, model_type `qwen2`, architecture `Qwen2ForCausalLM`, `Qwen2TokenizerFast` |
| Auditor | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` / `5c20803aa197416f43fb455e55c85178775320cb` | `LlamaConfig`, model_type `llama`, architecture `LlamaForCausalLM`, `LlamaTokenizerFast` |

These are cached AutoConfig/tokenizer facts, consistent with the remote recorded
model types; no model object or weights were initialized locally. Architecture
selection follows configuration, not repository branding. Neither checkpoint
declares a config `auto_map`. The auditor retains Phi-style chat markers despite
its Llama architecture. The current `apply_chat_template` path uses those actual
markers correctly; scoped role/task instructions appear first in the user content.

Auditor metadata has BOS 1, EOS/PAD 32000 (`<|endoftext|>`), `add_bos_token=False`.
Its chat turn separator `<|end|>` is token 32007, distinct from configured EOS.
That distinction is recorded, not silently changed: the old response truncated
inside JSON and does not demonstrate an erroneous turn-end stop. A future model
probe must retain terminal-token/EOS evidence. Qwen uses EOS IDs 151645 and 151643;
its cached sampling default is overridden by the existing deterministic probe policy.
Pinned revisions, quantization and family separation are unchanged.

## Field allocation

| Fields | Owner / treatment |
|---|---|
| Producer alias | Model selects an existing owned alias; strict membership/coverage |
| Claim IDs, questions/gaps, uncertainty, extraction status | Model semantics; preserved and validated, never inferred by adapter |
| Source text, offsets, span hash, unit identity/order | Existing Python ledger and hydration |
| Producer extraction method | Python `source_span`, describing the actual reconstruction mechanism |
| Producer core confidence | Conservative `UNCERTAIN`; Python does not invent positive certainty |
| Auditor finding, selected refs, severity, confidence | Model semantics; validated and preserved |
| Auditor reason | Model evidence explanation for human review; nonempty and citation/rule checks, not an automated truth oracle |
| Agent/doc ID, routed paragraph, item kind | Python routing facts |
| Core `ref` | First model-selected ref, or existing document-level sentinel; no new citation |
| Item ID, revision, source provenance | Existing deterministic runtime/hydration stamps |
| Numeric relation/verdict/rule/values, original/output copies | Not applicable/redundant for scoped fidelity; no fabricated Finding record |

## Token capacity evidence

Counts use the pinned locally cached tokenizers, with networking disabled and
`USE_TORCH=0`. Local Transformers 4.51.3 / tokenizers 0.21.1 reproduce the exact
remote 4.52.3 rendered hashes and input counts. Outputs below are compact JSON
serializations of **authored valid answers**, using the same semantics before/after.
They are not measurements of generated answers; EOS itself is not included.

| Tokens | Producer old | Producer new | Auditor old | Auditor new |
|---|---:|---:|---:|---:|
| Rendered prompt | 610 | 333 | 1,875 | 488 |
| Minimal valid output | 65 | 26 | 23 | 5 |
| Representative complete output | 101 | 59 | 107 | 71 |
| Representative margin below 384 | 283 | 325 | 277 | 313 |

Producer minimal means an examined span with empty semantic arrays. Auditor minimal
means genuinely empty original/extraction; it is invalid for the populated remote
fixture. The representative answers include both claims/date gap or MATCH reason
and both refs. Old representative answers were also checked against the old canonical
validator, and old producer hydration reconstructs exactly. No optional numeric
Finding record was added to inflate the old auditor count.

The separately authored verbose auditor stress answer is 335 tokens and remains
contract-valid. It is not the representative target. The actual old failed remote
answers were 259 and 384 generated tokens. None of these counts establish that the
models will choose the intended fields, reason correctly or reach EOS within 25 s.

## Validation and limits

**85 passing checks**, plus **4 executed neutralise → fail → restore → pass proofs**
and two pinned-tokenizer profiles. One pre-existing optional local-directory coverage
check is skipped because `prompts/` and `snapshots/` are absent.

- 29 new checks: at least ten producer and ten auditor cases, plus live wrapper and
  maintained probe-builder integration. Exact reconstruction/order, explicit date gap,
  empty versus incomplete, context ownership, duplicate observations, source copying,
  MATCH, real authored divergence, refusal, both refs, invalid refs/rules, malformed
  and truncated envelopes, concise and verbose outputs all exercised.
- 40 existing Report Recommendations/topology fixture tests, with real wrapper,
  hydration, evidence, family-separation and completion paths but mocked inference.
- 9 existing safe baseline checks and 7 selected legacy contract/Finding-record,
  role-anchor, field-form, consumer and governance checks. The live
  `_typed_for_agent` function is source-isolated for check 151 so unrelated GNN/model
  imports are unnecessary. Full pipeline-dependent legacy checks were not run.
- Mutation proofs cover exact reconstruction, mandatory refs, strict completeness
  and isolation from the generic numeric-rule prompt. Restored outcomes equal baseline.
- Both failed remote outputs remain refused. No validator accepts their content by
  guessing a missing identity, repairing source prose, adding citations or completing JSON.

Reproduce with `python scripts/compact_contract_no_generation_gate.py` and
`python tools/compact_contract_budget.py`. The first blocks model/provider imports
and network access. The second allows only local tokenizer/configuration loading.
All changed/new Python sources compile. The artifact manifest and credential scan
are recorded alongside readiness; no credential matches were retained.

Optional generation was skipped given established laptop resource limits. An initial
tokenizer import encountered the local duplicate OpenMP runtime; disabling model
framework imports for tokenizer-only analysis resolved it without the unsafe duplicate
runtime override or loading a model. No cloud preparation work was reopened.

## Next bounded measurement

After separate authorization, compare the retained old and revised prompts at the
same fixed model pins and 384-token / 25-second ceiling. Measure producer alias
compliance, exact reconstruction and missing-information extraction; independently
measure auditor MATCH, both refs, reason correctness, complete JSON and terminal token.
Only accepted producer output may enter the required independent serial audit.
Record latency, EOS/truncation, output tokens and semantic adjudication separately.
The probe's nonempty-reason check is only syntactic; a human must assess actual reason
correctness before treating a new model answer as semantically accepted. No concurrency
or serving work is justified until producer, auditor and mandatory serial quality pass.

**No cloud, paid API, full pipeline, multi-round, model/revision/quantization change,
ceiling increase, serving-engine change, hidden benchmark key access or push occurred.**
Historical remote evidence and operator-owned `SHIMMER_HANDOFF.md` / `durable/` are preserved.


## Subsequent real-model A/B ? 15 September 2026

The separately authorized measurement at `54df6a4` is complete:
[REMOTE_CONTRACT_MODEL_AB.md](REMOTE_CONTRACT_MODEL_AB.md).
**REMOTE_CONTRACT_MODEL_AB_FAIL**; both revised responses reached EOS but failed
strict contracts and semantic acceptance. The serial handoff was withheld.
**DOMAIN_AGNOSTIC_TUNING_RECOMMENDED=true** for both roles; see the bounded
[future task-data/evaluation design](DOMAIN_AGNOSTIC_TASK_TUNING_DESIGN.md).
One A10 was provider-confirmed terminated, cost upper estimate $0.20671457.
No concurrency, model training, full pipeline, multi-round, paid inference API or push.
This new evidence layer does not alter the historical results above.
