# The cloud reference run: plan (D-S70 item 5, D-S35, D-S33 item 1)

Written 2026-11-08 at about 21:00 +0300, before any paid call. Nothing below has been run, and no
provider call of any kind (not even token counting) was made to write it. Development, exposed. It
is a REFERENCE: its figures are reported beside B1 and the system, labelled as a paid cloud model's,
and never as Shimmer's performance (D-S35 items 2 and 3).

## (a) Items: already read, half A only

Everything here was already read by J1 (D-261 to D-263) and G1 (D-241 to D-248). None of it is the
fresh set.

| File | SHA-256 | What it holds |
|---|---|---|
| `external/s05/J1/j1_prompts.json` | `5e59766d8a054b1a66db112bf9d7bb110c7a4f31e7693e487731c9327ef857f2` | J1's 498 prompts over 89 documents: `b1` form (B1's own two turns) and `agent` form (the judging calls the saved B3 runs made, the pipeline's own prompt bytes), groups `judge_direct` and `judge_reason` |
| `external/s05/J1/j1_bar.json` | `c16014535f5444b9fc8c48f7ccb777a6472e4eb05e08366db639538ec83f0054` | J1's bar: the prompts and keys digests, and the two SciTab items left out |
| `benchmark/baselines/g1_bar_items.json` | `e460abea5820405b1c0046c5a453364e96ef5ad8ffff6d813873a7f4e59a67c9` | G1's items: 60 ContraDoc documents and 93 SciTab claims (2 left out); keys digest `86d318f991b749a48d499b158fc1eb913feb2c8fea72d8f6c05b1f3e6aca3238` |
| `external/s05/G1/g1_prompts.json` | `baa76827ad1f2643b58b41c594b96d7debb8538a71726bcf8756b282b3a43c04` | G1's prompts (the digest the bar items name); not sent, since J1's file carries the same items in both forms |

**Half A only.** The documents are split by C's own function, `choice_read.split` (SHA-256 of
`20261106:` plus the document id, the lower half A), over C's universe: the items of the pinned
`g1_bar_items.json`. The run refuses unless, for each benchmark, the prompts' items are exactly
that file's (its left-out ones included, as J1's are). Half B is reserved for C and T's one read
(`docs/loop/stages/C_BAR.md`). A paid reference on half B would be a look at half B, so it is not
taken. Counted on J1's file by `cloud_reference.py plan`, half A holds:

- ContraDoc: 30 documents, 30 items;
- SciTab: 15 documents, 45 claims sent, since the two left-out claims are dropped before sending,
  as J1 dropped them at reading;
- per group: 75 `b1` prompts and 33 `agent` prompts, 108 in all. An earlier count here said 112,
  counted before the left-out claims were dropped.

An item that has no `agent` call is silence and so ABSTAIN, exactly as in J1's local agent arm, so
the two stay comparable.

## (b) Arms

1. **B1, the bare model.** J1's `b1` prompts, byte for byte: the system turn as the system prompt
   and the user turn as the one user message. `bare_model.py` cannot carry this: `resolve_reader`
   refuses any backend that is not local (`the reading agent's backend ... is not a local
   backend`). So a small new runner is needed (below). Its labels are read the way J1 read B1's.
2. **The system's judging step, with the cloud model in the judge's seat.** J1's `agent` prompts:
   the pipeline's own PRACTICE_AUDITOR prompts, built by Python from saved B3 runs, with Python's
   selection of units and rules already applied. The replies are read by J1's reader
   (`judge_read.py`): the `strict` view is what the pipeline would keep (the one refusal test the
   judged paths use), and the `judge` view is what the model said. This is not the whole system.
   The producer's work and every Python step upstream are the saved ones, and nothing downstream of
   the judging call is re-run. It is labelled so.
3. **The whole system on the cloud profile cannot run under the rules.**
   - It is the pipeline, and no pipeline runs on this laptop.
   - On a rented instance it would need the Anthropic key on the instance, which is a stop under
     (d).
   - The sealed ordinary final path also runs final-mode local models with the network denied, so
     it has no cloud profile to run.

   This arm is not run, and the report says why.

**What the reference is compared with, on the same half A items:**

- J1's local B1 (`external/s05/J1/read/labels/judge_direct_b1`);
- J1's local judging step (`judge_direct_judge`, `judge_direct_strict`), Phi-4
  (`unsloth/phi-4-bnb-4bit`).

## (c) The model

- **Read live, never typed.** At run start the runner lists the provider's models
  (`model_registry.list_available_models("claude_api", keys)`, the Models API) and resolves the
  registry's id with the repository's one rule, `model_registry.resolve_model_id`. A model that is
  GONE from the list, more than one snapshot matching, or a list that cannot be read STOPS the run
  for the operator, with no swap (INFRA-026, CLAUDE.md).
- **What that cannot catch, said plainly.** A model still listed but announced as deprecated
  passes the list: the Models API carries no deprecation field. The run adds two things, and
  neither proves the model is not deprecated:
  - it reads the model's own record (`models.retrieve`) and stops if any field naming a
    deprecation has a value;
  - it requires `--deprecation-checked`, the operator's reading of the provider's deprecations
    page (the page, the date, the result), and records it.
- **Which id.** `config/agent_registry.json` names two Anthropic models: `claude-opus-4-8`
  (LEGAL_ANALYST, AMENDMENT_DRAFTER) and `claude-sonnet-4-6` (PROCESSOR). D-S35 asks for "a strong
  model" as the reference, so the plan takes `claude-opus-4-8`.
- **A conflict, stated, not papered over.** The registry gives the judging agent PRACTICE_AUDITOR
  the OpenAI backend (`gpt-4o`) under the cloud profile. D-S35 permits Anthropic only. So the
  reference puts the registry's Anthropic model in the judge's seat for this measurement, without
  changing the registry. Whether Opus or Sonnet, and whether that is acceptable, is the lead's
  decision; Sonnet would cost about 40 percent less (see (e)).
- **Decoding.** `AgentWrapper.call_claude` sends one user turn and no system turn, so B1's two
  turns cannot pass through it unchanged. The runner calls the SDK's `messages.create` itself, as
  call_claude does: `model`, `max_tokens`, the system turn where the prompt has one, and the
  messages, nothing else. So `claude-opus-4-8` runs without thinking (its default) at the
  provider's sampling defaults. The client is built with `max_retries=0`, so a request the
  provider billed is never sent a second time. Each prompt keeps J1's allowance (2048 for `b1`; 768 for
  `judge_direct` agent calls; 1536 for `judge_reason`). The run is a single draw, not
  deterministic; it says so.

## (d) The key

**Where it is read.** The key is read on this machine only:

- `agent_wrapper.load_api_keys()` reads `ANTHROPIC_API_KEY` from the credential file outside the
  repository (`SHIMMER_CONFIG_PATH`, the sibling `../api_keys/config.py`, or `.env_path`);
- the value is handed only to the `anthropic` client the runner builds (`make_client`);
- errors pass through `agent_wrapper._scrub_error` and a replace of the key itself.

**What the run writes and prints.**

- The runner prints counts, tokens and dollars only, never a reply text, a path to the key or the
  key itself.
- Reply records go through `reply_records.write` into the run's own folder under the gitignored
  `output/`, as every model call's do.
- Before the first call the runner scans every prompt it will send for the key patterns of
  `scripts/guard_secrets.py` and for the loaded key itself, and refuses on a hit. (An earlier text
  here also promised a scan for paths outside the benchmark texts; none is built.) Only
  public development benchmark texts and the repository's own prompt text are sent (D-S35 item 1).
- Before any commit, the precommit scan and `guard_secrets --staged` run as always.
  `guard_secrets` refuses `audit/model_replies/` at any depth.

**No key leaves this machine except in the request header to the provider itself.** Nothing runs on
an instance, so no key is copied anywhere. Arm 3 would have needed one on an instance; that is why
it is not run, and it is the stop the lead asked to be told about. It is not triggered by arms 1
and 2.

## (e) Calls, tokens, price and the stop at the cap

**Calls.**

| Group | Prompts | Characters sent | Most output tokens allowed |
|---|---|---|---|
| `judge_direct` (75 B1, 33 agent) | 108 | 1,124,224 | 178,944 |
| `judge_reason` (75 B1, 33 agent) | 108 | 1,141,384 | 204,288 |

Run order: `judge_direct` first, `judge_reason` only if the worst case still fits under the cap
(below).

**Tokens.** No token figure here is the provider's yet. As an estimate, about 4 characters a token,
times up to 1.35 for the newer tokenizer, gives at most about 400,000 input tokens a group. The run
measures with the provider's own figures:

- `messages.count_tokens` for each prompt before it is sent (free, but a provider call, so it
  belongs to the run, not to this plan);
- `response.usage` (`input_tokens`, `output_tokens`, the cache fields) after each call.

**Price.** The provider's API returns no price. The lead reads Anthropic's pricing page and records
the row for the model id in `benchmark/baselines/cloud_reference_prices.json` (input and output per
million tokens, the page, the date read). The run refuses prices given on the command line that
differ from that row for the id it resolved live, and refuses a model with no row. The table ships
empty, so no run can start before the row is written. For planning only, the price
cached in this session's reference (2026-10-06) is 5 USD per million input tokens and 25 per
million output tokens for `claude-opus-4-8`, and 3 and 15 for `claude-sonnet-4-6`.

**Worst case**, every reply at its allowance:

| Model | `judge_direct` | `judge_reason` | Both |
|---|---|---|---|
| `claude-opus-4-8` | about 6.6 USD | about 7.2 USD | about 13.8 USD (`plan`, on 108 prompts a group, with the 10 percent count margin) |
| `claude-sonnet-4-6` | about 4.0 USD | about 4.4 USD | about 8.4 USD |

J1's local replies mostly ended well short of their allowance, so the expected cost is lower. That
is unmeasured for this model.

**The stop.** The cap (`--cap-usd`) must not pass what is left of the permission's total
(`--total-usd`, 15 USD under D-S35) after the spend every earlier cloud-reference run recorded in
its measurement under `output/cloud_reference/`. Then:

- a group starts only if spend so far plus the group's whole worst case (its counted input
  tokens and its full output allowance at the price) fits under the cap. So `judge_reason` runs
  only if it still fits after `judge_direct` (D-326), and no group is left half done by the cap;
- each call is checked again on its own the same way, the second net when the provider reports
  more than was counted;
- a failed call, or a reply whose usage cannot be read, is counted at its worst case;
- `count_tokens` failing stops the run before any billed call;
- the measurement, with `spent_usd`, is written on any exit, an interruption included;
- otherwise the run stops and writes what it has. The runner writes no operator file: the lead
  reads the measurement and writes FOR_SECKIN (D-S35 item 1).
- the worst case counts the input 10 percent above `count_tokens`' figure (`COUNT_MARGIN`), since
  the provider calls that figure an estimate and may bill slightly more; the measurement records
  the margin.
- a billed reply the code cannot read is counted once, from its usage, before anything reads it.

After the run, the provider console's usage is read against the run's own sum. A difference is
reported.

**In the ledger: a gap, and a choice for the lead.** The budget ledger counts spend only from
`shimmer-loop-` launches (`instance_reaper.ledger_view`), and its writer admits only the declared
events and fields (`loop_budget_guard.LEDGER_FIELDS`). An API spend line would be ignored by the
guard and the reaper. There are two ways to count it:

1. A ledger event for API spend, counted by `ledger_view`. This changes `tools/loop/instance_reaper.py`
   and `tools/loop_budget_guard.py`, two bound controller files, so every bundle sealed before it
   (the running cases batch's included) refuses with `Controller source changed` and must be
   sealed again.
2. Before the run, the lead writes a `budget_change` line lowering `hard_stop_usd` by the cap
   (15 USD), source D-S35, so the guard and the reaper treat the cap as spent. After the run, a
   second line raises it again by the part not spent. The actual figure goes into
   `docs/loop/BUDGET.md`.

Recommended: 2. It changes no code and reserves the whole cap, which is the safe side. The earlier
`budget_change` lines are all the operator's own figures, though, so whether the loop may write
this kind is the lead's call under D-S35.

## (f) What is reported

One table per benchmark, half A only, each row its source:

| Row | Source |
|---|---|
| B1, local (Phi-4) | J1's labels |
| Judging step, local (Phi-4), `judge` and `strict` | J1's labels |
| B1, reference (paid Anthropic model, its id as resolved live) | this run |
| Judging step, reference, `judge` and `strict` | this run |

Each row reports:

- right and false flags;
- ABSTAIN and silence;
- unreadable replies and replies that reached their allowance;
- ContraDoc accuracy (ABSTAIN wrong) and net;
- SciTab macro-F1;
- seconds per prompt and per document;
- input and output tokens;
- dollars (D-S33 item 2 (d): time and cost per document).

Labels go through `tools/score_corpus.py` only, as J1's did. Every reference row and the report's
title say: "Reference: a paid cloud model on development items already read. Not Shimmer's
performance." The report also says what the reference cannot show:

- half A is small (30 and 15 documents);
- these items were read before, and Phi-4 was chosen on them;
- a single draw;
- the judging step is not the whole system, and the whole system was not run.

## Built, and what changed (D-326, the checker's findings on 1d40a5da)

Built as `benchmark/baselines/cloud_reference.py` (`plan`, `run`, `read`), with
`benchmark/baselines/cloud_reference_prices.json` (empty until the lead records the row) and
`benchmark/baselines/cloud_reference_checks.py`, gate check 339. Its proofs run on fakes only; each
guarded rule is neutralised, shown to fail, restored and shown to pass. The lead decided (D-326):
Opus, ledger way 2 (the lead lowers the hard stop by 15 before the run and restores it less the
actual spend after), and `judge_reason` if it still fits.

Changed from the text above, now aligned with the code:

- half A comes from `choice_read.split` over C's universe, not from `choice_read.halves` over
  the prompts' own documents, and the universe is checked against the pinned items file;
- 108 prompts a group, not 112 (the left-out claims dropped before sending);
- the call is the SDK's own, not `AgentWrapper.call_claude`, with `max_retries=0`, and it writes no
  cost-log rows: the spend is the measurement's `spent_usd` and each row's `cost_usd`;
- the prices are checked against a recorded table, and the cap against what is left of the total;
- the deprecation test catches gone or ambiguous models only, plus a record field and the
  operator's page reading, as (c) now says;
- the run folder must be a new folder directly under `output/cloud_reference/`;
- no scan for paths is built.

Round 2 of the check (on d3e83080), all in the code and proved:

- C's universe is read by `choice_read.universe` from the pinned items file and the answer keys
  (`--key`, through the scorer), each item's document from its key, documents whose items are all
  left out dropped;
- `--total-usd` is held to `benchmark/baselines/cloud_reference_budget.json` (15, D-S35), and earlier
  spend is read from one store every checkout shares, `docs/loop/private/cloud_reference_spend.jsonl`
  of the main checkout, found from git's common directory; each run appends its spend line there on
  any exit, and an unreadable store refuses;
- each call's worst case is counted before the request and replaced by the reported cost only on a
  completed reply with usage; a usage reporting cache writes stops the run;
- the provider record is turned with `to_dict(mode="json")` and json writes any other value as text;
- a run folder holding `audit/` with no measurement is refused; the price table's digest is recorded;
  `--deprecation-checked` must read `<url>, <YYYY-MM-DD>, not deprecated`.

Not proved before the first paid call:

- `read` end to end with the real scorer and keys;
- the real SDK's shapes for `count_tokens`, `models.retrieve` and a reply's `usage`.

## The run

On this machine, with no pipeline and no instance, after the lead's `budget_change` line and the
price row:

```
py -3.12 -X utf8 benchmark/baselines/cloud_reference.py run --prompts external/s05/J1/j1_prompts.json --bar external/s05/J1/j1_bar.json --items benchmark/baselines/g1_bar_items.json --key <each answer key> --out output/cloud_reference/<name> --cap-usd <USD> --price-input-per-mtok <row> --price-output-per-mtok <row> --price-source "<page, date>" --deprecation-checked "<url>, <YYYY-MM-DD>, not deprecated"
```

## D-S102 item 12: the 15 USD cap lifted (D-384)

The cloud reference has no cap of its own any more. D-S102 item 12 lifts D-S35's 15 USD (and
D-S70 item 5's); it runs as gate bar (b) and D-S98 item 8 need, within the total budget, which is the
only limit (D-S95 item 4). In the code:

- `--total-usd` and `benchmark/baselines/cloud_reference_budget.json` are gone;
- `--cap-usd` must fit what is left of the TOTAL budget, read the way the guard reads it: the cap
  ceiling of the latest budget line (`loop_budget_guard.cap_ceiling`) less the instances' spend and
  the caps of running instances (`loop_budget_guard.ledger_state`), less every earlier
  cloud-reference run's spend in the shared store. The ledger does not count the store's spend, so
  the store is added. Where the operator also lowers the hard stop for a reference run, that spend
  is counted twice, the safe side;
- with no readable budget line the run refuses;
- every run still appends its spend line to `docs/loop/private/cloud_reference_spend.jsonl` on
  any exit, and an absent or unreadable store refuses.

Earlier text in this plan that names a 15 USD total or `--total-usd` describes the run of
9 November (7.07 USD), made under D-S35's cap.

## D-S106: Seckin's key, his yes, his credit (D-391, D-393)

Both paid runners (`cloud_reference.py run` on J1's prompts and `cloud_reference_b1.py` on a B1
build) hold these; the subscription steering runner bills nothing and needs none of them.

- The key is only the one `agent_wrapper`'s rule resolves (`SHIMMER_CONFIG_PATH`, then the sibling
  `../api_keys/config.py`, then the `.env_path` pointer), recorded as `key_source` by name. The
  environment's `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_BASE_URL` are removed
  before the client is built, never read and never sent.
- `--seckin-approved "<FOR_SECKIN entry heading time>"` is required, passed by the lead only after
  Seckin's evet, and written into the measurement and the spend line.
- `--credit-usd` is the API credit left; nothing starts whose worst case passes the lower of the cap
  and the credit. A provider refusal (no credit is a 400) stops the run at once, with its spend line
  written; nothing is retried. `--max-calls N` ends a chunk cleanly. `--resume-from <folder>`
  reuses every reply that folder recorded, keyed by the prompt's SHA-256, and sends none of those
  prompts again; the reused answers are counted apart (`reused_answers`) and cost nothing in the
  new spend line, their spend being in the earlier run's line.

## D-401: the cloud-check's twelve gaps on fad0f075

1. The environment's `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_BASE_URL` are removed at the start of a paid run, before any client is built; the live model list is read through a client built like the run's own, with the provider's base URL (`cloud_reference.provider_models`), never the registry helper's.
2. `--resume-from` is refused unless the earlier folder's measurement is a paid run of the same kind, carries no steering stamp, read the same inputs (J1: prompts and config digests; B1: items and parts digests) on the same model, and every reply record is a `claude_api` call on that model with no steering stamp, each reused one with the settings this run sends.
3. `--seckin-approved` names one heading of `FOR_SECKIN.md` beside the store; a line under it, before the next heading, must read exactly `Seckin: evet (<time>)`. The lead writes that line only after Seckin's answer. This is lead-attested: the runner checks that the line is there, it cannot check who wrote it, and the measurement and spend line say so. Role C's form reads a copy the lead hands it (`--for-seckin`).
4. `tools/loop/cloud_reference_spend.py` is the one reader of the store, importable by the guard (judge-product's lane wires it in): `store_path(root)`, `state(store)` (closed spend and open intents' caps), `lead_may_spend(store)`.
5. A paid run writes an `intent` line holding its limit under the store's lock (`<store>.lock`, never broken by a tool), after the budget decision and before its first request; the limit counts as running until its `close` line.
6. The steering runner takes only a (prompts file, subset) pair listed by digest in `benchmark/baselines/cloud_reference_steering_sets.json`; the fresh set's digest (that file's refused list and `system_test.py`'s `FRESH_PROMPTS_SHA256` where present) is refused. The list ships empty: the gate set's quick subset, PUBHEALTH development and the development benchmarks are added by a recorded edit once their digests are recorded.
7. The steering child's environment loses every `ANTHROPIC_` variable, the Bedrock, Vertex and Foundry switches and their settings; before the first call `claude auth status --json` must report `loggedIn` true, `authMethod` `claude.ai` and `apiProvider` `firstParty`, and those fields with `subscriptionType` are recorded (not the account's name or address).
8. The B1 path reads the side from role B's build record (`parts.json`'s declared side and each document's), takes no `--side`, and refuses a build not in `benchmark/baselines/cloud_reference_builds.json` (which ships empty; `cloud_reference_b1.py record-build` prints an entry for the lead to commit). A holdout build needs the row of `HELDOUT_OPENINGS.md` committed at HEAD (`git show`) whose first cell is the opening exactly and which writes the full items digest.
9. Every bundle file the run reads must have the digest the allowed list records for it.
10. The resume loop no longer overwrites the provider's model record (proved on a resumed run's measurement).
11. A role C spend file dropped into `docs/loop/private/cloud_reference_handed_back/` and not yet appended (`cloud_reference_spend.py append-handed-back`) refuses the lead's next paid run, and through `lead_may_spend` the guard's next launch; role C's form runs only under `SHIMMER_ROLE=C`, where the lead's form refuses.
12. Each resumed chunk's limit is the lower of the cap and the credit less the chain's earlier spend (`chain_spent_before_usd`); a cache-write halt stops the B1 path at its next call; the store is found by one path rule, `cloud_reference_spend.store_path`, for the runners and the guard. With no ledgers given, `check_cap` reads the budget ledger beside the store (the main checkout's `docs/loop/private/`, by the same rule) and role R's, never a worktree's own copy (`cloud_reference.loop_ledgers`).

### D-401 recheck: items 3a and 11

- 3a. One evet approves one run. Under the store's lock, before its intent line, a paid run is refused when an intent or close line already names its FOR_SECKIN heading for a run outside its own chain (`cloud_reference.approval_unused`). A resume may use the heading again: each measurement records `chain_run_ids_before`, the runs it resumes, and the intent line names the heading (`seckin_approved_heading`).
- 11. Before role C runs, the lead runs `cloud_reference_b1.py open-role-c --cap-usd <USD> --seckin-approved "<heading time>" [--resumes <role C run ids>]`. Under the lock it holds the cap to the total budget, uses the evet once, and writes an intent of kind `cloud-reference-b1-role-c` that counts as running. It prints the run id and the budget figure to hand role C. Role C passes `--role-c-run-id`, and its spend line carries that id. `append-handed-back` closes the intent, and refuses a line whose run id names no such intent (`unplanned_runs`). Role C's form refuses in the lead's checkout: wherever the lead's spend store is reachable through git's common directory.
- 11, the last point. `open-role-c` hands role C the intent's own cap as its budget figure (`budget_left_usd` equals `cap_usd`; what the total keeps besides is `total_left_after_usd`). Role C's form refuses a cap above that figure. `append-handed-back` refuses a spend line above its intent's cap (`spend.over_cap`), does not append it, and writes a FLAG section at the top of FOR_SECKIN.md naming the run, the spend, the held cap and the file's digest (`spend.flag_for_seckin`).

