# DRAFT, NOT RATIFIED: a DELTA for INST_FINDER off by default, with the switch kept

Status: DRAFT. Nothing in this file is in force. It is not an amendment, it is
not in `config/constitution.json`, and no agent may apply it. Only the operator
can ratify it, through the verified no-gap DELTA path
(`constitution_guard.verify_amendment_append`), in an interactive session.

The operator's decision behind this text is D-570 (13 November 2026, 10:53):
INST_FINDER is off by default for the next attempt and every run after, and the
switch stays, so running it remains optional.

## What exists today

`scripts/pipeline.py` reads the environment variable `SHIMMER_INST_FINDER`
(`_inst_finder_switch`), trimmed and lower-cased. The value `off` asks for
INST_FINDER to be switched off and `on` for it to run; an empty value counts as
no value, and any other value refuses to start (exit code 9).

With no value, the pipeline takes the ratified default: off when an amendment
ratifies the switch and declares `"default": "off"` in its `change`, as the one
below does; otherwise on, as before any amendment.

Switching an agent off changes governed inter-agent structure: INST_FINDER is
one of the three corpus-level production agents in phase 3-4, and its
institution records reach the audit bus. Agents may not change that structure on
their own, so the code honours off, asked or by default, ONLY when
`config/constitution.json` holds an amendment with `operator_approved: true`
whose `change` text names both `INST_FINDER` and `SHIMMER_INST_FINDER`. No
amendment id is written in code.

Without such an amendment:
- a run started with `SHIMMER_INST_FINDER=off` refuses to start (exit code 9)
  with one line naming the missing DELTA. The setting is never ignored silently.
  The server and the console show such a run with the governance status
  `refused_inst_finder_unratified`, not as a failure;
- a run with no value runs INST_FINDER, as it always has.

The sealer evaluates the same function from the bound source, so a bundle sealed
with no value under the ratified default seals `SHIMMER_INST_FINDER=off`, and an
unratified `off` is refused at sealing.

## What the operator would ratify

One new amendment, appended at the end of `amendments[]`, with the next free id
at the time of ratification (never reused, never inserted, never renumbered):

```json
{
  "id": "<next free INFRA id>",
  "created": "<date of ratification>",
  "kind": "agent_switch",
  "title": "INST_FINDER is off by default; the operator may switch it on per run with SHIMMER_INST_FINDER",
  "genesis_part": "II",
  "operator_approved": true,
  "change": {
    "default": "off",
    "setting": "The environment variable SHIMMER_INST_FINDER, read by the pipeline. With no value INST_FINDER is off by default. The value on switches INST_FINDER on for that run; the value off keeps it off.",
    "effect_when_off": "INST_FINDER is not called in phase 3-4. It stays in config/agent_registry.json and in PRODUCTION_AGENTS_CORPUS_LEVEL. The run records it in audit/agent_activation.json as not called, state switched_off, reason 'switched off by operator setting', and states the setting and whether it was the default in the run summary and in audit/agent_switches.json.",
    "unchanged": "ARCHIVIST and CITATION_RESOLVER still run. No other agent, phase, contract or LAW changes. LAW-III family enforcement sees the same registry. The switch stays: SHIMMER_INST_FINDER=on runs INST_FINDER as before."
  },
  "reason": "It was meant to be inactive from the start. Its job (finding and routing the relevant institutions in correspondence) has no ground yet, and its outputs reach the bus with no downstream reader. The sealed manifest set SHIMMER_INST_FINDER=on, and it caused one incomplete entry in the quick read of 13 November 2026 (D-570)."
}
```

## Why it is a DELTA and not a configuration file

- The registry, the LAW-III checks and the harness all describe INST_FINDER as
  an agent that fires in phase 3-4. Turning it off by a setting or a default
  alone would let any process environment change the swarm's structure with no
  record in the constitution.
- The existing operator withholding for phase-5 auditors
  (`config/review_scope.json`, `withheld_audit_agents`) is a per-corpus review
  scope declaration for auditors; INST_FINDER is a production agent, and the
  spec for this switch asks for a ratified DELTA.

## What ratification does and does not do

- It makes INST_FINDER off for every run that sets no value, and lets the
  operator set `SHIMMER_INST_FINDER=on` to run it, per run.
- It does not remove INST_FINDER from any list, file or check.
- It does not change a run or a bundle made before it: their saved
  `audit/agent_switches.json` and sealed environment stand.

## How to check it after ratification

Gate check 277 (`scripts/inst_finder_switch_checks.py`) proves the cases on
copied configuration in a temporary directory, each with and without a fixture
ratifying amendment: no value (on without the amendment, off by default with
it), `on` (on either way), and `off` (refused without the amendment, not
dispatched with it, the activation record giving the reason).
