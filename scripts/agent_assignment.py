"""The per-document agent-assignment layer (D-571, D-572, D-575), structural conditions only.

Python reads a document's structural conditions (`conditions`: tables, numeric cells, prose lines,
citation markers in declared syntax, size), applies the skip rules declared in
config/agent_assignment.json (`skip_rules`, each naming the built rule it rests on), and refuses any
assignment below the floor (`floor()`, the mandatory compositions, read as data from the same file).
Nothing rests on what words mean (WORDS-A): a condition of that kind is not read here, so the agent
it would concern stays assigned. With no skip rule declared every agent is assigned, exactly the
dispatch before the layer. Every decision is recorded: one row per document in
audit/agent_assignment.json, and each skip through agent_activation.not_called (state `unassigned`).
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

import pairing_map

ROOT = Path(__file__).resolve().parents[1]
DECLARATION = ROOT / "config" / "agent_assignment.json"
PATTERNS = ROOT / "config" / "relation_patterns.json"
RECORD = "agent_assignment.json"
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
NUMBER = re.compile(r"^[-+]?\(?\d[\d,]*(\.\d+)?\)?%?$")
REF_ID = re.compile(r"\bREF-\d{4,}\b")


class AssignmentRefused(ValueError):
    """An assignment below the floor, or a skip rule the layer cannot read."""


def declaration(path=DECLARATION):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema") != "agent-assignment-v1" or not isinstance(value.get("skip_rules"), list) \
            or not isinstance(value.get("floor"), list):
        raise AssignmentRefused("config/agent_assignment.json is not an agent-assignment-v1 declaration")
    return value


def floor(path=DECLARATION):
    """The floor's items as declared: [{id, rule, agents, when_assigned, ...}], each naming its rule."""
    items = declaration(path)["floor"]
    for item in items:
        if not item.get("id") or not item.get("rule") or not isinstance(item.get("agents"), list):
            raise AssignmentRefused("a floor item names no id, rule or agent list: %r" % (item.get("id"),))
    return items


def _reference_patterns(path=PATTERNS):
    try:
        refs = json.loads(Path(path).read_text(encoding="utf-8")).get("numbered_references", {}).get("references", [])
    except (OSError, ValueError):
        return []
    return [re.compile(r["regex"], re.IGNORECASE) for r in refs if isinstance(r, dict) and r.get("regex")]


def _captions(lines):
    """The line indexes that caption a table: the nearest line above a table's header that is neither
    blank nor a heading (cell_selection._caption's rule), when it is not itself a table row."""
    out = set()
    for at in range(1, len(lines)):
        if not (TABLE_RULE.match(lines[at]) and TABLE_ROW.match(lines[at - 1])):
            continue
        for k in range(at - 2, -1, -1):
            if lines[k].strip():
                if not lines[k].lstrip().startswith("#") and not TABLE_ROW.match(lines[k]):
                    out.add(k)
                break
    return out


def conditions(text):
    """The document's structural conditions, read from its own text only. `running_prose_lines`
    (D-652) counts the prose lines that are neither a `label: value` field line (the one field-line
    syntax, pairing_map._LABEL_LINE) nor a table's caption (_captions): a document of tables, captions
    and field lines has none, which no word's meaning decides (WORDS-A)."""
    lines = str(text or "").splitlines()
    rows = [l for l in lines if TABLE_ROW.match(l) and not TABLE_RULE.match(l)]
    cells = [c.strip() for l in rows for c in l.strip().strip("|").split("|")]
    prose_at = [i for i, l in enumerate(lines) if l.strip() and not TABLE_ROW.match(l) and not l.lstrip().startswith("#")]
    captions = _captions(lines)
    running = [i for i in prose_at if i not in captions and not pairing_map._LABEL_LINE.match(lines[i])]
    markers = len(REF_ID.findall(text or "")) + sum(len(p.findall(text or "")) for p in _reference_patterns())
    return {"has_table": any(TABLE_RULE.match(l) for l in lines) and bool(rows), "table_rows": len(rows),
            "numeric_cells": sum(1 for c in cells if NUMBER.match(c)), "prose_lines": len(prose_at),
            "running_prose_lines": len(running), "citation_markers": markers, "characters": len(text or "")}


def assign(agents, found, rules=None, floor_items=None, switched_off=()):
    """{agent: {assigned, reason, rule}} for `agents` under the declared skip rules and the floor.
    A rule skips its agent when every condition it lists equals the document's. The floor then
    refuses (AssignmentRefused) any skip of a required agent, so a rule below it never reaches a
    call; an agent the operator's ratified switch turns off is the switch's, not the layer's."""
    rules = declaration()["skip_rules"] if rules is None else rules
    floor_items = floor() if floor_items is None else floor_items
    out = {a: {"assigned": True, "reason": "no skip rule applies", "rule": None} for a in agents}
    for rule in rules:
        if not isinstance(rule, dict) or not rule.get("agent") or not rule.get("rule") or not isinstance(rule.get("when"), dict):
            raise AssignmentRefused("a skip rule names no agent, condition set or built rule")
        if "replacement" in rule or "route_to" in rule:
            raise AssignmentRefused("a skip rule may not route an agent's work to another (LAW-II, F7)")
        unknown = set(rule["when"]) - set(found)
        if unknown:
            raise AssignmentRefused("a skip rule reads a condition the layer does not read: " + ", ".join(sorted(unknown)))
        if rule["agent"] in out and all(found[k] == v for k, v in rule["when"].items()):
            out[rule["agent"]] = {"assigned": False, "reason": "skip rule: " + json.dumps(rule["when"], sort_keys=True),
                                  "rule": rule["rule"]}
    refuse_below_floor(out, floor_items, switched_off)
    return out


def refuse_below_floor(assignment, floor_items, switched_off=()):
    """Raise AssignmentRefused when an agent the floor requires is unassigned (F2-type items), or
    unassigned while the agent it audits is assigned (F1-type `when_assigned`)."""
    for item in floor_items:
        trigger = item.get("when_assigned")
        if trigger and not (assignment.get(trigger) or {}).get("assigned", trigger not in assignment):
            continue
        for agent in item["agents"]:
            if item.get("unless_switched_off") and agent in switched_off:
                continue
            row = assignment.get(agent)
            if row is not None and not row["assigned"]:
                raise AssignmentRefused("%s may not be unassigned: floor %s (%s)" % (agent, item["id"], item["rule"]))


def dispatch(run_context, doc_id, agents, text, *, scope="document", switched_off=()):
    """The assigned agents of `agents`, in their order, for one document (or the corpus): the
    decision is computed, refused below the floor, recorded, and each skip is recorded as not
    called. With no skip rule declared it returns `agents` unchanged."""
    found = conditions(text)
    decided = assign(list(agents), found, switched_off=switched_off)
    _record(run_context, dict(doc_id=doc_id, scope=scope, conditions=found, decisions=decided))
    if any(not d["assigned"] for d in decided.values()):
        import agent_activation
        for agent, d in decided.items():
            if not d["assigned"]:
                agent_activation.not_called(run_context, agent, reason=d["reason"], source_phase="3-4", doc_id=doc_id,
                                            state="unassigned", trigger_source="assignment",
                                            evidence={"conditions": found, "rule": d["rule"]})
    return [a for a in agents if decided[a]["assigned"]]


_LOCK = threading.Lock()


def _record(run_context, row):
    audit = getattr(run_context, "audit_dir", None)
    if not callable(audit):
        return
    path = Path(audit()) / RECORD
    with _LOCK:
        rows = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
        rows.append(row)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n", encoding="utf-8")
