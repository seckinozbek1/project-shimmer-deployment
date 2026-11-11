"""The roles of a run as a declared dependency graph (D-S59; D-S55 item 5, D-S57 item 2, D-S58).

config/role_graph.json declares each role and the roles whose output it reads. This module:

    load(path)              the graph, refused for an unknown role in an edge, a role needing
                            itself, or a cycle (the cycle is named)
    order(graph)            the topological order, ties broken by name, so it is the same every time
    layers(graph)           the same order cut into layers: every role of a layer depends only on
                            roles of earlier layers, so the roles of one layer may run at once
    check_order(graph, seq) refused when a role in `seq` comes before a role it needs
    tasks(graph, actions, document, model_of)
                            execution_scheduler Tasks for one document, one per role given, each
                            with an Edge to every role it needs (reason `role_graph:<role>`) and a
                            sequence in topological order, so the existing Scheduler runs a role only
                            after what it needs and independent roles at once on their models' lanes
    as_run(graph, tasks, events)
                            the graph that ran, from the scheduler's own tasks and events: each
                            role's tasks with their measured start, end and service seconds, the
                            declared edges among the roles that ran, and every task that started
                            before a task of a role it needs had ended (`violations`)

No new library: execution_scheduler already takes tasks with edges, refuses a cycle and an order
against its edges, and runs ready tasks on free compatible lanes. Which model a role runs on is
config/agent_registry.json's; this module never reads or sets one. No model, no network.
"""
import json
from pathlib import Path

from execution_scheduler import Edge, Task

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "role_graph.json"
SCHEMA = "role-graph-v1"
SCOPES = ("document", "corpus")
EDGE_REASON = "role_graph:%s"


class GraphRefused(ValueError):
    """A graph or an order that cannot be run as declared."""


def load(path=CONFIG_PATH):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return check(value)


def check(value):
    if not isinstance(value, dict) or value.get("schema") != SCHEMA or not isinstance(value.get("roles"), dict) \
            or not value["roles"]:
        raise GraphRefused("not a role graph (%s)" % SCHEMA)
    roles = value["roles"]
    for name, role in roles.items():
        needs = role.get("needs")
        if not isinstance(needs, list) or len(set(needs)) != len(needs):
            raise GraphRefused("%s lists what it needs once each" % name)
        if role.get("scope") not in SCOPES:
            raise GraphRefused("%s has a scope of %s" % (name, " or ".join(SCOPES)))
        for need in needs:
            if need == name:
                raise GraphRefused("%s needs itself" % name)
            if need not in roles:
                raise GraphRefused("%s needs %s, which the graph does not declare" % (name, need))
    order(value)          # refuses a cycle
    return value


def needs(graph, role):
    return list(graph["roles"][role]["needs"])


def order(graph):
    """Kahn's order, the ready roles taken by name: one fixed order for one graph."""
    remaining = {name: set(role["needs"]) for name, role in graph["roles"].items()}
    out = []
    while remaining:
        ready = sorted(name for name, parents in remaining.items() if not parents)
        if not ready:
            raise GraphRefused("a dependency cycle among: " + ", ".join(sorted(remaining)))
        out.extend(ready)
        remaining = {name: parents - set(ready) for name, parents in remaining.items() if name not in ready}
    return out


def layers(graph):
    remaining = {name: set(role["needs"]) for name, role in graph["roles"].items()}
    out = []
    while remaining:
        ready = sorted(name for name, parents in remaining.items() if not parents)
        if not ready:
            raise GraphRefused("a dependency cycle among: " + ", ".join(sorted(remaining)))
        out.append(ready)
        remaining = {name: parents - set(ready) for name, parents in remaining.items() if name not in ready}
    return out


def check_order(graph, sequence):
    """`sequence` (role names, in the order they would run), or GraphRefused naming the first role
    that comes before one it needs. A role the sequence leaves out constrains nothing."""
    seen, present = set(), set(sequence)
    for role in sequence:
        if role not in graph["roles"]:
            raise GraphRefused("%s is not a role of the graph" % role)
        early = [n for n in needs(graph, role) if n in present and n not in seen]
        if early:
            raise GraphRefused("%s would run before %s, which it needs" % (role, ", ".join(early)))
        seen.add(role)
    return list(sequence)


def tasks(graph, actions, document, model_of, family_of=None, start=0):
    """Scheduler tasks for one document: `actions` maps a role to its action(context); only those
    roles get a task. Each task's edges name the tasks of the roles it needs that are given here."""
    family_of = family_of or (lambda role: "")
    given = [r for r in order(graph) if r in actions]
    ids = {role: "role-%s-%s" % (document, role) for role in given}
    out = []
    for number, role in enumerate(given):
        edges = tuple(Edge(ids[n], EDGE_REASON % n, True) for n in needs(graph, role) if n in ids)
        out.append(Task(ids[role], actions[role], sequence=start + number, agent=role, document=str(document),
                        model=model_of(role), family=family_of(role), edges=edges))
    return out


def _times(events):
    start, end = {}, {}
    for event in events:
        if event.get("event") == "task_start":
            start[event["task"]] = event["monotonic_s"]
        elif event.get("event") == "task_end":
            end[event["task"]] = event["monotonic_s"]
    return start, end


def as_run(graph, tasks_by_id, events):
    """The graph that ran (see the module text). `tasks_by_id` is the scheduler's own task table, so
    nothing here is reconstructed from a plan: a role is in it only if a task of it ran."""
    start, end = _times(events)
    nodes = {}
    for task in sorted(tasks_by_id.values(), key=lambda t: (t.sequence, t.id)):
        if task.id not in start:
            continue
        nodes.setdefault(task.agent, []).append(
            {"task": task.id, "document": task.document, "model": task.model,
             "start_monotonic_s": start[task.id], "end_monotonic_s": end.get(task.id),
             "service_s": (end[task.id] - start[task.id]) if task.id in end else None})
    roles = graph["roles"]
    declared = sorted({(need, role) for role in nodes if role in roles for need in roles[role]["needs"] if need in nodes})
    violations = []
    for role, ran in nodes.items():
        if role not in roles:
            continue
        for need in roles[role]["needs"]:
            for task in ran:
                for dep in nodes.get(need, ()):
                    same = roles[role]["scope"] == "corpus" or roles[need]["scope"] == "corpus" \
                        or dep["document"] == task["document"]
                    if same and (dep["end_monotonic_s"] is None or dep["end_monotonic_s"] > task["start_monotonic_s"]):
                        violations.append({"task": task["task"], "role": role, "needs": need, "dependency_task": dep["task"]})
    return {"schema": "role-graph-run-v1", "declared_sha256": digest(graph),
            "roles": {role: ran for role, ran in sorted(nodes.items())},
            "undeclared_roles": sorted(r for r in nodes if r not in roles),
            "edges": [{"from": a, "to": b} for a, b in declared],
            "violations": violations, "kept_declared_order": not violations}


def digest(graph):
    import hashlib
    return hashlib.sha256(json.dumps(graph, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
