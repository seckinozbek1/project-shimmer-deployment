# Run languages, briefs and strategic support

Implementation only. Model-backed language and recommendation quality are
unverified. See the [implementation report](../fix/BRIEFS_LANGUAGE_STRATEGY_IMPLEMENTATION.md).

`POST /submit` accepts optional multipart string fields:

| Field | Values | Missing default |
| --- | --- | --- |
| `input_language` | `auto`, `en`, `tr` | `auto` |
| `output_language` | `en`, `tr` | `en` |
| `agent_briefs` | `enabled`, `disabled` | `enabled` |

Explicit empty/unknown values return HTTP 400. Input auto passes multilingual text
through to the model; it does not guess output language. Output auto is unsupported.
The console supplies input auto and the selected English/Türkçe output. These
values persist with job status and are forwarded to matching CLI flags:

```text
--input-language auto --output-language tr --agent-briefs enabled
```

Language does not activate multi-round, strategy, sparse routing or DAG execution.
Existing task, privacy, confirmation and authentication gates are unchanged.
The per-run saved contract is `audit/run_options.json` with schema_version 1.
`logs/prompt_structure.jsonl` contains prefix identity/length metadata, not prompts
or measured cache-hit claims. The same call ID joins existing call/cost evidence.

For a valid explicitly requested multi-round manifest, optional fields select
decision support. This fragment is added to the existing case identity/source schema:

```json
{
  "decision_support_mode": "recommendation",
  "allow_recommendations": true
}
```

Other modes are `trajectory_only` (default), `decision_support` (non-prescriptive),
and `strategic_options` (no recommendation type). `allow_recommendations` alone
does not start the new strategy phase. A malformed mode refuses before execution.
The console's existing manifest field carries this explicit selection; its output
language control does not alter the case manifest or create strategic intent.

`GET /runs/{run_id}/multi-round` retains `view` and adds `strategic_support` when
case evidence is available. Its schema_version 1 projection has `mode`, `state`,
`state_label`, `output_language`, `quality: UNVERIFIED` and typed `layers`.
Layer types are `OBSERVED`, `INTERPRETED`, `DERIVED`, `STRATEGIC_OPTION`, and
`RECOMMENDATION`. `display_label`, `display_state` and `movement_label` are localized;
underlying fields, IDs, enums, numeric values and provenance are not translated.

Options carry proposed `action`, `upside`, `risk`, `assumptions`, `uncertainty`,
`confidence`, `state`, and actor/issue/round/source/interpretation/trajectory ID
arrays. Recommendations additionally link `option_ids`. Reviewed records contain
case and REF bindings plus producer/reviewer call identity. Unreviewed or invalid
advice is unavailable; malformed advice does not suppress a valid legacy `view`.
Rejected proposals retain their states and are not presented as accepted advice.

This is additive saved evidence, not a new unauthenticated or live-generation
endpoint. English/Turkish prose is model-instructed, not translated by a heuristic.
Turkish mode now covers supported console, CLI, report and DOCX structural text
through a shared catalog at presentation boundaries. Canonical API/schema fields,
enums, IDs, provenance and exact source quotations remain unchanged. Reopened runs
use persisted `output_language`; older runs fall back to English. Existing saved
source/model prose and raw diagnostic evidence retain their original language.
See [localization closure](../fix/BRIEFS_LANGUAGE_STRATEGY_IMPLEMENTATION.md#localization-completion-2026-09-14)
for the supported surfaces, intentional exceptions and deterministic validation.
