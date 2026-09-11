"""Convention assignment (docs/api/CONVENTION_ASSIGNMENT_DESIGN.md, operator-approved).

The comparison that closes W2's own stopped premise check: a one-way subject
label on each side (each agent's own `subjects` in config/agent_registry.json,
each convention's own `subjects` read from its heading's bracket tags by
convention_parser), compared by code that knows no subject name at all. This
module is the whole of that comparison and nothing else: it never names a
subject, never ranks, never infers a synonym.

    py -3.9 -X utf8 -c "import convention_assignment"   # importable, no side effect

Called once, at BOOT, on the freshly parsed convention registry and the
agent registry's own "agents" sub-dict already loaded for the run. Never
per call, never per document.
"""
from __future__ import annotations

import json
from pathlib import Path


def assign_conventions(conventions: list, agents: dict) -> dict:
    """The comparison. Any overlap between a rule's tags and an agent's
    declared subjects, exact token equality (already lowercased and
    stripped by both producers), no synonyms, no substrings, no ranking.

    `agents` is the agent registry's own "agents" sub-dict (name -> spec),
    the same shape pipeline.py already threads through as `resolved_agents`;
    callers never need to unwrap a further "agents" key.

    Returns {"by_rule": {conv_id: {...}}, "by_agent": {agent_name: [conv_id, ...]}}.

    by_rule[conv_id]:
      subjects   the rule's own tags, sorted, as parsed (possibly empty)
      agents     agent names matched, sorted
      consumer_agents   of those, the ones with a live rule-consuming path
                 today (see consumer_agent_names)
      status     "untagged"    the rule carries no subject tag at all
                 "assigned"    the rule matched at least one agent with a
                               consumer path
                 "assigned_no_consumer"   matched only agent(s) with no
                               consumer path today (a declared-but-idle
                               agent, e.g. PROCESSOR, or an orphaned
                               subject name like "extraction" that no
                               agent currently declares would ALSO be
                               unassigned, not this; this status is only
                               for a real agent match with no path)
                 "unassigned"  the rule carries tags but none matched any
                               agent's declared subjects at all

    by_agent[agent_name]: convention ids matched to that agent, in
    registry order.
    """
    agents = agents or {}
    declared: dict = {
        name: set(spec.get("subjects") or []) for name, spec in agents.items()
    }
    consumers = consumer_agent_names(agents)

    by_rule: dict[str, dict] = {}
    by_agent: dict[str, list] = {name: [] for name in declared}

    for c in conventions or []:
        conv_id = c.get("id")
        if not conv_id:
            continue
        tags = set(c.get("subjects") or [])
        matched = sorted(a for a, subs in declared.items() if tags & subs)
        consumer_matched = [a for a in matched if a in consumers]
        if not tags:
            status = "untagged"
        elif not matched:
            status = "unassigned"
        elif not consumer_matched:
            status = "assigned_no_consumer"
        else:
            status = "assigned"
        by_rule[conv_id] = {
            "subjects": sorted(tags),
            "agents": matched,
            "consumer_agents": consumer_matched,
            "status": status,
        }
        for a in matched:
            by_agent[a].append(conv_id)

    return {"by_rule": by_rule, "by_agent": by_agent}


# Every agent with SOME live rule-consuming path today, whatever its shape:
# the convention-review agents read a rule directly (wide mode's full-
# registry loop, or paired mode's per-pair dispatch); REDACTOR reads a rule
# that compiles as a redaction rule, by its own keyword sniff
# (sensitivity_layer/rules.py); the six EDITOR ranks read the whole
# registry, per rank, on escalation. This is a structural fact about which
# phase actually looks at a convention, not a subject name and not a
# domain word: it says which agent CAN act on a matched rule, never what
# the rule is about, and it is a wider question than answer 6's "does not
# run" firing-gate scope (convention-review agents only), which decides
# only whether phase 5.5 dispatches an agent, not whether some OTHER phase
# (9, 6.5) ever reads a rule at all. Kept here, not imported from
# pipeline.py, since pipeline.py imports THIS module; duplicated as a
# plain tuple, matched to the real fixed phase lists by gate check, so the
# two cannot silently drift.
CONVENTION_REVIEW_AGENT_NAMES = ("PRACTICE_AUDITOR", "STYLE_GUARDIAN")
REDACTION_AGENT_NAMES = ("REDACTOR",)
EDITORIAL_BOARD_AGENT_NAMES = (
    "EDITOR_CLERK", "EDITOR_HEAD_OF_UNIT", "EDITOR_HEAD_OF_SECTION",
    "EDITOR_HEAD_OF_DEPARTMENT", "EDITOR_DEPUTY_DG", "EDITOR_DG",
)
_CONSUMER_AGENT_NAMES = (CONVENTION_REVIEW_AGENT_NAMES + REDACTION_AGENT_NAMES
                        + EDITORIAL_BOARD_AGENT_NAMES)


def consumer_agent_names(agents: dict) -> set:
    """Which declared agent names have SOME live rule-consuming path today,
    across every phase that ever reads a convention (5.5, 9, 6.5), not only
    the phase 5.5 firing gate answer 6 scopes. An agent name not present in
    the registry at all is never a consumer."""
    return {name for name in _CONSUMER_AGENT_NAMES if name in agents}


def unassigned_summary(assignment: dict) -> list:
    """Every convention the assignment could not route anywhere an agent
    can act on it: unassigned (no agent declares its tag) or
    assigned_no_consumer (an agent declared it, but that agent has no rule
    path today). Never dropped: this is the list a caller posts to the bus,
    writes to the assignment file's own top level, and renders in the
    console, per the design document's "never dropped" requirement."""
    out = []
    for conv_id, row in (assignment.get("by_rule") or {}).items():
        if row["status"] in ("unassigned", "assigned_no_consumer"):
            out.append({"rule_id": conv_id, **row})
    return out


def idle_agents_summary(assignment: dict, agents: dict) -> list:
    """Every agent that declares at least one subject but matched zero
    conventions this load: the condition W3 was waiting on. An agent
    declaring an empty subjects list (with a subjects_note) is not idle in
    this sense; it was never expected to match anything."""
    by_agent = assignment.get("by_agent") or {}
    out = []
    for name, spec in (agents or {}).items():
        declared = spec.get("subjects") or []
        if declared and not by_agent.get(name):
            out.append({"agent": name, "subjects": list(declared)})
    return out


def untagged_count(assignment: dict) -> int:
    """How many rules carry no subject tag at all (answer 1: printed at
    BOOT beside the existing convention_registry rules=N line). Not the
    same thing as unassigned: an untagged rule keeps today's routing
    (every convention-review agent gets it, unchanged), it is only counted
    so the operator can see, at a glance, how many rules in the loaded set
    have not been tagged yet."""
    return sum(1 for row in (assignment.get("by_rule") or {}).values()
               if row["status"] == "untagged")


def write_assignment(run_context, assignment: dict) -> Path:
    """Write the assignment to <run>/audit/convention_assignment.json.
    Same directory and write idiom as pairing_map.write_pairing_map: once
    per run, at load, never rewritten mid-run (the assignment is computed
    once at BOOT and does not change while a run is in progress)."""
    audit_dir = Path(run_context.audit_dir())
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / "convention_assignment.json"
    path.write_text(json.dumps(assignment, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
