"""Gate check: the judge as a registered agent (D-S55 items 1, 2, 4 and 5; D-S56 item 1). No model,
no provider, no key: a fixture registry and contract beside the shipped ones, an invented decision.

Each proof is neutralise, fail, restore, pass (scripts/effect_proof.py):
1. the agent whose contract declares a task takes it, on the real phase 5.5, and no other task:
   an undeclared task, a task asked in a written reply and a roster with no judge keep the route
   they had; two agents declaring one task are refused;
2. no question is asked without the rule's declaration, whoever the judge is;
3. the question the judge is asked is the replay's byte for byte, the `{tools}` slot included, and
   with no shown tool declared it is the measured question unchanged;
4. a checking role on the backend or the model of the role it checks stops boot, as does a task
   two agents declare or a tool Python does not run for it;
5. each declared tool call is one record in `audit/judge_tools.jsonl`, joined to its call, with
   indexes and counts and no text; a tool the task does not declare writes none.
"""
import contextlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import cell_selection  # noqa: E402
import judge_agent  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

JUDGE = "FIXTURE_JUDGE"
JUDGE_SPEC = {"does": ["Answer one narrow question"], "does_not": ["Write text"], "model": "fixture-judge",
              "backend": "local_auditor", "category": "verification", "may_use_web": False, "may_handle_sensitive": False}
TOOLS = [judge_agent.FIND_CELLS, judge_agent.LOCATE_FIGURES, judge_agent.CHECK_QUOTE]
JUDGE_CONTRACT = {"item_kind": "decision", "fields": {"decided": "string"}, "required": ["decided"], "checks": [],
                  "judge": {"tasks": {"cell_claim": {"tools": TOOLS}}}}
RULE = {"id": "CONV-021", "category": "conv-h21", "severity": "required", "compare": "cells",
        "rule": "The Northern quay has dues of 61.5 and a depth of 15."}
PLAIN_RULE = dict(RULE, compare=None)


@contextlib.contextmanager
def patched(owner, name, value):
    old = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, old)


def _decision():
    return {"decided": "not met", "settled": True, "why": None, "confidence": .9, "threshold": .7, "declared_mass": .95,
            "top": "not met", "answers": [{"label": a, "probability": p}
                                          for a, p in (("holds", .05), ("not met", .9), ("cannot be settled", .05))]}


def _phase(with_judge=True, rules=None):
    """The real phase 5.5 on a mocked run, a fixture judge registered beside the shipped roster:
    (the cell claim rows, what each call was sent and by whom, the tool records)."""
    import agent_wrapper
    import cell_selection_checks as csc
    import harness.run_agent as run_agent
    import honest_output_checks as hoc
    import passage_pairs
    from unittest.mock import patch
    sent = []

    def call_choice(self, prompt, answers, value):
        sent.append({"agent": self.name, "prompt": prompt})
        return agent_wrapper.CallResult(self.backend, "fixture-judge", "", parsed=_decision())
    real = run_agent.build_orchestrator

    def orchestrator(**kwargs):
        orch = real(**kwargs)
        # The shipped judge, if the roster holds one, stands aside: the fixture is the only judge.
        shipped = [n for n, c in orch.contracts.items() if judge_agent._judge(c)]
        orch.registry = {n: s for n, s in orch.registry.items() if n not in shipped}
        orch.contracts = {n: c for n, c in orch.contracts.items() if n not in shipped}
        if with_judge:
            orch.registry = dict(orch.registry, **{JUDGE: dict(JUDGE_SPEC)})
            orch.contracts = dict(orch.contracts, **{JUDGE: JUDGE_CONTRACT})
        return orch
    text = chr(10).join((hoc.DOC_TEXT, csc.QUAY_UNIT))
    with tempfile.TemporaryDirectory() as td, patch.object(agent_wrapper.AgentWrapper, "call_choice", call_choice), \
            patched(cell_selection, "threshold_of", lambda config: .7), patch.object(passage_pairs, "embed", lambda items: None), \
            patch.object(run_agent, "build_orchestrator", orchestrator):
        folder = Path(hoc.mocked_run(Path(td), style_guardian=False, text=text, rules=rules or (hoc.RULES + [RULE]))["run_dir"])
        document = json.loads(next(folder.rglob("pairing_map.json")).read_text(encoding="utf-8"))["batch_sheet"]
        path = folder / "audit" / judge_agent.TOOL_RECORDS
        tools = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []
        calls = {c.get("call_id"): c.get("agent") for c in document.get("judging_calls") or []
                 if c.get("plan_kind") == "cell_claim"}
        data = json.loads(next(folder.rglob("review_data.json")).read_text(encoding="utf-8"))
        shown = [(f.get("agent"), f.get("relation")) for f in data.get("model_findings_not_promoted") or []
                 if f.get("rule_id") == RULE["id"]]
    return {"rows": document.get("cell_claims") or [], "sent": sent, "tools": tools, "calls": calls, "shown": shown}


def observe_route():
    """Who is asked the cell claim with a judge registered and with none, and what the roster says
    of tasks it does not declare."""
    run, plain = _phase(), _phase(with_judge=False)
    registry, contracts = {JUDGE: JUDGE_SPEC, "OTHER": JUDGE_SPEC}, {JUDGE: JUDGE_CONTRACT}
    try:
        judge_agent.role_for("cell_claim", registry, dict(contracts, OTHER=JUDGE_CONTRACT))
        twice = "taken"
    except judge_agent.ContractRefused:
        twice = "refused"
    return {"asked": [s["agent"] for s in run["sent"]], "row": [r["agent"] for r in run["rows"]],
            "without": [s["agent"] for s in plain["sent"]],
            "pair": judge_agent.role_for("passage_pair", registry, contracts),
            "reply form": judge_agent.role_for("cell_claim", registry, contracts, deciding=False),
            "unregistered": judge_agent.role_for("cell_claim", {}, contracts), "twice": twice}


def expected_route():
    return {"asked": [JUDGE], "row": [JUDGE], "without": ["PRACTICE_AUDITOR"], "pair": None, "reply form": None,
            "unregistered": None, "twice": "refused"}


def observe_declared_only():
    """A rule without `[compare: cells]` is asked nothing, judge or not."""
    import honest_output_checks as hoc
    run = _phase(rules=hoc.RULES + [PLAIN_RULE])
    return {"sent": len(run["sent"]), "rows": len(run["rows"]), "tools": len(run["tools"])}


def observe_same_question():
    """The judge's question, as sent on the real phase, against the replay's own rendering of the same
    cells and claim, and against the measured question with no tool declared."""
    import cell_selection_checks as csc
    _, doc_judge = csc._baselines()
    run = _phase()
    sent = run["sent"][0]["prompt"] if run["sent"] else ""
    measured = json.loads((ROOT / "benchmark" / "baselines" / "choice_judge_prompt.json").read_text(encoding="utf-8"))
    form = measured["choice"]["forms"]["claim"]
    cells = cell_selection.select(csc.QUAY_UNIT, RULE["rule"], cell_selection.load_config())["cells"]
    replay = doc_judge.render_choice(measured, "claim", {"cells": cells, "claim": RULE["rule"],
                                                         "tools": judge_agent.claim_tools(cells, RULE["rule"], {JUDGE: JUDGE_CONTRACT})})
    replay_default = doc_judge.render_choice(measured, "claim", {"cells": cells, "claim": RULE["rule"]})
    bare = cell_selection.question(cell_selection.load_config(), cells, RULE["rule"], {})
    return {"same": sent == replay, "figures": [line for line in sent.split("\n") if line.startswith(("61.5:", "15:"))],
            "templates": form["template"] == cell_selection.load_config()["decision"]["template"],
            "no tool declared": bare == form["template"].replace("{cells}", cells).replace("{claim}", RULE["rule"]).replace("{tools}", ""),
            "shipped default": replay_default == bare if not judge_agent.declared_tools("cell_claim", judge_agent.shipped_contracts()) else replay_default == replay}


def expected_same_question():
    return {"same": True, "figures": ['61.5: row "Northern", column "Dues"', "15: in no cell shown"], "templates": True,
            "no tool declared": True, "shipped default": True}


def observe_family():
    """Boot on a roster whose checking role shares the backend or the model of what it checks, or
    whose judge declares a tool Python does not run for its task."""
    import harness.run_agent as run_agent

    def boot(registry, contracts):
        from unittest.mock import patch
        import orchestrator
        real = orchestrator.json.load

        def load(fh):
            value = real(fh)
            if isinstance(value, dict) and "contracts" in value:
                kept = {n: c for n, c in value["contracts"].items() if not judge_agent._judge(c)}
                value = dict(value, contracts=dict(kept, **contracts))
            return value
        with tempfile.TemporaryDirectory() as td, patch.object(orchestrator.json, "load", load):
            try:
                run_agent.build_orchestrator(root=ROOT, out_root=Path(td), registry=registry)
                return "booted"
            except ValueError as exc:
                return "refused" if "cannot run as declared" in str(exc) else "other"
    shipped = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
    checker = dict(JUDGE_CONTRACT, checks=["PROCESSOR"])
    same_backend = dict(shipped, **{JUDGE: dict(JUDGE_SPEC, backend=shipped["PROCESSOR"]["backend"])})
    same_model = dict(shipped, **{JUDGE: dict(JUDGE_SPEC, model=shipped["PROCESSOR"]["model"])})
    other = dict(shipped, **{JUDGE: dict(JUDGE_SPEC)})
    bad_tool = dict(JUDGE_CONTRACT, judge={"tasks": {"passage_pair": {"tools": [judge_agent.LOCATE_FIGURES]}}})
    return {"same backend": boot(same_backend, {JUDGE: checker}), "same model": boot(same_model, {JUDGE: checker}),
            "other model": boot(other, {JUDGE: checker}), "unknown tool": boot(other, {JUDGE: bad_tool}),
            "shipped": judge_agent.refusals(shipped, judge_agent.shipped_contracts())}


def expected_family():
    return {"same backend": "refused", "same model": "refused", "other model": "booted", "unknown tool": "refused",
            "shipped": []}


def observe_records():
    """The tool records of one judged claim: which tools, joined to which call, and no text."""
    run = _phase()
    joined = [run["calls"].get(r["call_id"]) for r in run["tools"] if r["prompt_sha256"]]
    text = json.dumps(run["tools"])
    return {"tools": [r["tool"] for r in run["tools"]], "joined": joined, "shown": run["shown"],
            "located": [(r["figures"], r["located"], r["at"]) for r in run["tools"] if r["tool"] == judge_agent.LOCATE_FIGURES],
            "no text": not any(w in text for w in ("Northern", "61.5", "Dues")),
            "undeclared": judge_agent.tool_rows("passage_pair", {JUDGE: JUDGE_CONTRACT}, "R", "u", "q",
                                                [judge_agent.check_quote_row(None)])}


def expected_records():
    return {"tools": [judge_agent.FIND_CELLS, judge_agent.LOCATE_FIGURES, judge_agent.CHECK_QUOTE],
            "joined": [JUDGE, JUDGE, JUDGE], "shown": [(JUDGE, "claim_not_met")], "located": [(2, 1, [[[0, 1]], []])], "no text": True, "undeclared": []}


def observe_own_model():
    """A local profile entry with no model runs the agent's own spec.model, never the auditor's
    checkpoint beside it; the shipped judge's local model is its registry model (D-313)."""
    import pipeline
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "config").mkdir()
        (root / "config" / "agent_registry.json").write_text(json.dumps({"agents": {"J": {"model": "own/model"}}}), encoding="utf-8")
        (root / "config" / "local_models.json").write_text(json.dumps({"active_auditor": "auditor/model"}), encoding="utf-8")
        resolved = pipeline._resolve_local_models({"J": ("local_auditor", None), "A": ("local_auditor", "x")}, root)
    shipped = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
    judges = judge_agent.judges(shipped, judge_agent.shipped_contracts())
    return {"resolved": resolved,
            "shipped": [pipeline._LOCAL_PROFILE.get(n, (None, None))[1] == shipped[n]["model"] for n in judges]}


def expected_own_model():
    shipped = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
    return {"resolved": {"J": ("local_auditor", "own/model"), "A": ("local_auditor", "auditor/model")},
            "shipped": [True] * len(judge_agent.judges(shipped, judge_agent.shipped_contracts()))}


def run_checks():
    import pipeline
    proofs = [
        ("the declaring agent takes its task", observe_route, expected_route,
         lambda: patched(pipeline, "_judging_role",
                         lambda task, rule, ca, orch, deciding=True: (pipeline._paired_judging_agent(rule, ca), {}))),
        ("an undeclared task keeps its route", observe_route, expected_route,
         lambda: patched(judge_agent, "declaring", lambda task, registry, contracts: sorted(
             n for n, c in (contracts or {}).items() if n in (registry or {}) and judge_agent._judge(c)))),
        ("two declaring agents are refused", observe_route, expected_route,
         lambda: patched(judge_agent, "declaring", lambda task, registry, contracts: sorted(
             n for n, c in (contracts or {}).items() if n in (registry or {}) and task in ((judge_agent._judge(c) or {}).get("tasks") or {}))[:1])),
        ("no question without the declaration", observe_declared_only, lambda: {"sent": 0, "rows": 0, "tools": 0},
         lambda: patched(cell_selection, "declared", lambda rules: [r for r in rules or [] if r.get("id") == RULE["id"]])),
        ("the replay's question is the judge's", observe_same_question, expected_same_question,
         lambda: patched(judge_agent, "figures_block", lambda cells, claim: "")),
        ("the tools slot is filled on both sides", observe_same_question, expected_same_question,
         lambda: patched(cell_selection, "question", lambda config, cells, claim, contracts=None: config["decision"]["template"]
                         .replace("{cells}", cells).replace("{claim}", claim).replace("{tools}", ""))),
        ("a checking role on the model it checks stops boot", observe_family, expected_family,
         lambda: patched(judge_agent, "family_violations", lambda registry, contracts: [])),
        ("a tool Python does not run stops boot", observe_family, expected_family,
         lambda: patched(judge_agent, "KNOWN_TOOLS", dict(judge_agent.KNOWN_TOOLS, **{judge_agent.LOCATE_FIGURES: ("cell_claim", "passage_pair")}))),
        ("each tool call is one record", observe_records, expected_records,
         lambda: patched(pipeline, "_write_tool_rows", lambda orch, calls, call_of: calls.pop("tool_rows", None) and 0)),
        ("the judge runs its own model", observe_own_model, expected_own_model,
         lambda: patched(pipeline, "_resolve_local_models", lambda profile, root: {
             a: (b, m or "auditor/model") for a, (b, m) in profile.items()})),
        ("phase 6 reads the judge's records", observe_records, expected_records,
         lambda: patched(judge_agent, "judges", lambda registry, contracts: [])),
        ("a record joins its call", observe_records, expected_records,
         lambda: patched(pipeline, "_write_tool_rows", lambda orch, calls, call_of, real=pipeline._write_tool_rows: real(orch, calls, {}))),
    ]
    for name, observe, expected, neutralise in proofs:
        prove_effect(name=name, validate=lambda: judge_agent.CONTRACTS_PATH.is_file() and cell_selection.CONFIG_PATH.is_file(),
                     observe=observe, check=lambda observe=observe, expected=expected, name=name:
                     ("PASS" if observe() == expected() else "FAIL", name), neutralise=neutralise)
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: the agent whose contract declares a task takes it and "
                    "no other, two declaring are refused, nothing is asked without the rule's declaration, the judge's "
                    "question is the replay's byte for byte with its tools slot, a checking role on the model it checks "
                    "or an unknown tool stops boot, and each tool call is one record joined to its call" % len(proofs))


if __name__ == "__main__":
    print(json.dumps(run_checks()))
