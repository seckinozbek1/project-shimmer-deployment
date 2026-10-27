# DRAFT, NOT RATIFIED: a DELTA for switching INST_FINDER off

Status: DRAFT. Nothing in this file is in force. It is not an amendment, it is
not in `config/constitution.json`, and no agent may apply it. Only the operator
can ratify it, through the verified no-gap DELTA path
(`constitution_guard.verify_amendment_append`).

## What exists today

`scripts/pipeline.py` reads the environment variable `SHIMMER_INST_FINDER`.
The value `off` asks for INST_FINDER to be switched off; any other value, or no
value, means on, and on is the default.

Switching an agent off changes governed inter-agent structure: INST_FINDER is
one of the three corpus-level production agents in phase 3-4, and its
institution records reach the audit bus. Agents may not change that structure on
their own, so the code honours `off` ONLY when `config/constitution.json` holds
an amendment with `operator_approved: true` whose `change` text names both
`INST_FINDER` and `SHIMMER_INST_FINDER`. No amendment id is written in code.

Without such an amendment, a run started with `SHIMMER_INST_FINDER=off` refuses
to start (exit code 9) with one line naming the missing DELTA. The setting is
never ignored silently.

## What the operator would ratify

One new amendment, appended at the end of `amendments[]`, with the next free id
at the time of ratification (never reused, never inserted, never renumbered),
for example:

```json
{
  "id": "<next free INFRA id>",
  "created": "<date of ratification>",
  "kind": "agent_switch",
  "title": "The operator may switch INST_FINDER off per run with SHIMMER_INST_FINDER",
  "genesis_part": "II",
  "operator_approved": true,
  "change": {
    "setting": "The environment variable SHIMMER_INST_FINDER, read by the pipeline. The value off switches INST_FINDER off for that run; any other value, or no value, keeps it on. On is the default.",
    "effect_when_off": "INST_FINDER is not called in phase 3-4. It stays in config/agent_registry.json and in PRODUCTION_AGENTS_CORPUS_LEVEL. The run records it in audit/agent_activation.json as not called, state switched_off, reason 'switched off by operator setting', and states the setting in the run summary and in audit/agent_switches.json.",
    "unchanged": "ARCHIVIST and CITATION_RESOLVER still run. No other agent, phase, contract or LAW changes. LAW-III family enforcement sees the same registry."
  },
  "reason": "<the operator's own reason, for example the measured evidence that INST_FINDER's institution records have no consumer on the corpora in use>"
}
```

## Why it is a DELTA and not a configuration file

- The registry, the LAW-III checks and the harness all describe INST_FINDER as
  an agent that fires in phase 3-4. Turning it off by a setting alone would let
  any process environment change the swarm's structure with no record in the
  constitution.
- The existing operator withholding for phase-5 auditors
  (`config/review_scope.json`, `withheld_audit_agents`) is a per-corpus review
  scope declaration for auditors; INST_FINDER is a production agent, and the
  spec for this switch asks for a ratified DELTA.

## What ratification does not do

- It does not switch the agent off. It only allows the operator to do so per run
  by setting `SHIMMER_INST_FINDER=off`. With the variable absent, behaviour is
  exactly as before.
- It does not remove INST_FINDER from any list, file or check.

## How to check it after ratification

Gate check 277 (`scripts/inst_finder_switch_checks.py`) proves three cases on
copied configuration in a temporary directory: the variable absent (dispatched
as before), `off` with no ratified amendment (the run refuses with the message),
and `off` with a fixture constitution carrying a ratified amendment (not
dispatched, the activation record gives the reason).
