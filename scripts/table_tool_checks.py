"""Gate checks 388 to 394: the table tool request (D-681, docs/loop/stages/TABLE_TOOL_DESIGN.md
section 2, checks A to G). No model, no provider, no key: fixture tables, a fixture judge beside
the shipped roster, invented replies and decisions, fixture tool modules in a temporary folder.

Each proof is neutralise, fail, restore, pass (scripts/effect_proof.py):
  A (388) start-up refuses a license off the allowlist, a tool that opens a socket, a tool that
      writes a file, a non-deterministic tool, an entry no decision approves, an entry changed
      after vetting, and a declared request with no ratified amendment (also on the real boot, which
      reads the shipped constitution without INFRA-056 for that case);
  B (389) each of the six tools is right on a fixture, refuses a zero divisor and a percent
      against a plain number, and every shipped entry is vetted as declared;
  C (390) one request per question, never a second round; lines above max_calls are refused,
      by the parser and by the decoding grammar;
  D (391) a tool not shown, an id the table does not hold and a typed number are refused, each
      recorded as a tool row, and the grammar admits none of them;
  E (392) a table with no numbers is shown no arithmetic tool, and nothing is asked when no
      tool applies;
  F (393) on the real phase 5.5 each request is one reply record with outcome free_text, its
      judging call is counted apart, and its tool rows equal the reply's lines, joined to its
      call id, digests only;
  G (394) with no request_tools declared (as shipped) the question sent is byte for byte the
      measured one, no request call is made, and the tool records, pairing-map row keys and judging
      calls carry nothing of the request; the whole run is not compared with a run without the lane.
"""
import contextlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import cell_selection  # noqa: E402
import contract_decoding  # noqa: E402
import judge_agent  # noqa: E402
import table_tools  # noqa: E402
import tool_registry  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

JUDGE = "FIXTURE_JUDGE"
JUDGE_SPEC = {"does": ["Answer one narrow question"], "does_not": ["Write text"], "model": "fixture-judge",
              "backend": "local_auditor", "category": "verification", "may_use_web": False, "may_handle_sensitive": False}
TOOLS = [judge_agent.FIND_CELLS, judge_agent.LOCATE_FIGURES, judge_agent.CHECK_QUOTE]
SIX = ["get_cells", "difference", "ratio", "find_figure", "compare", "column_extreme"]
# The tool audit's additions (D-694 item 4, scripts/table_tools_extra.py; their own proofs are checks 420 to 424).
EXTRA = ["figure_step", "rounds_to", "percent_change", "sum_cells", "mean_cells", "rank_in_column"]
CONTRACT_OFF = {"item_kind": "decision", "fields": {"decided": "string"}, "required": ["decided"], "checks": [],
                "judge": {"tasks": {"cell_claim": {"tools": TOOLS}}}}
CONTRACT_ON = {"item_kind": "decision", "fields": {"decided": "string"}, "required": ["decided"], "checks": [],
               "judge": {"tasks": {"cell_claim": {"tools": TOOLS, "request_tools": SIX}}}}
RULE = {"id": "CONV-021", "category": "conv-h21", "severity": "required", "compare": "cells",
        "rule": "The Northern quay has dues of 61.5 and a depth of 15."}
QUAY = "\n".join(("## Entry Quays", "", "Table 2: Harbour dues by quay.", "", "| Quay | Dues | Depth |", "|---|---|---|",
                  "| Northern | 61.5 | 12 |", "| Southern | 44.0 | 9 |", "| Eastern | 70.25 | 14 |", ""))
ARITHMETIC = ["difference", "ratio", "find_figure", "compare", "column_extreme"]
FIXTURE_AMENDMENT = "INFRA-FIXTURE"
CONTEXT = {"cells": {"r1c1": "A", "r1c2": "12.5", "r1c3": "40%", "r2c1": "B", "r2c2": "10", "r2c3": "25%",
                     "r3c1": "C", "r3c2": "0", "r3c3": "25%"},
           "columns": {"c1": "Item", "c2": "X", "c3": "Y"}, "rows": 3, "figures": {"f1": "12.5", "f2": "15%"}}


@contextlib.contextmanager
def patched(owner, name, value):
    old = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, old)


def with_source(module, name, old, new):
    import cell_selection_checks
    return cell_selection_checks.with_source(module, name, old, new)


@contextlib.contextmanager
def both(*managers):
    with contextlib.ExitStack() as stack:
        for manager in managers:
            stack.enter_context(manager)
        yield


def _decision():
    return {"decided": "not met", "settled": True, "why": None, "confidence": .9, "threshold": .7, "declared_mass": .95,
            "top": "not met", "answers": [{"label": a, "probability": p}
                                          for a, p in (("holds", .05), ("not met", .9), ("cannot be settled", .05))]}


def _vetted_registry():
    """The shipped registry with each entry's vetting computed as it stands (the shipped vetting is
    proven against the same digest in B)."""
    registry = tool_registry.load()
    for entry in registry["tools"]:
        entry["vetting"] = {"sha256": tool_registry.vetted_sha256(entry), "result": tool_registry.PASSED}
    return registry


# ---------- A: start-up refusals -----------------------------------------------------------

FIXTURE_MODULE = '''
import os, socket, tempfile
def ok_tool(context, a):
    return context["cells"][a]
def net_tool(context, a):
    try:
        socket.socket().close()
    except Exception:
        pass
    return context["cells"][a]
def write_tool(context, a):
    try:
        path = os.path.join(tempfile.gettempdir(), "shimmer_vet_fixture_%d.txt" % os.getpid())
        with open(path, "w") as fh:
            fh.write("x")
        os.remove(path)
    except Exception:
        pass
    return context["cells"][a]
def seed_tool(context, a):
    return str(hash(a) % 1000003)
'''


def _fixture_entry(function, **fields):
    entry = {"name": function, "does": "A fixture tool.", "inputs": [{"name": "a", "type": "cell"}], "outputs": "a cell's text",
             "license": "MIT", "source": "shimmer", "entry": "fixture_vet_tools:" + function, "tasks": ["cell_claim"],
             "applies_when": {}, "examples": [{"context": CONTEXT, "args": ["r1c1"], "expected": "A"}],
             "approved_by": "D-681", "vetting": {}}
    entry.update(fields)
    return entry


def observe_vetting():
    """What vetting says of a clean tool and of four bad ones, each in two fresh processes."""
    import vet_table_tool
    registry = {"license_allowlist": ["MIT"], "approving_decisions": ["D-681"]}
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "fixture_vet_tools.py").write_text(FIXTURE_MODULE, encoding="utf-8")
        cases = {"clean": _fixture_entry("ok_tool"), "license": _fixture_entry("ok_tool", license="Unlisted-1.0"),
                 "socket": _fixture_entry("net_tool"), "write": _fixture_entry("write_tool"),
                 "random": _fixture_entry("seed_tool", examples=[{"context": CONTEXT, "args": ["r1c1"], "expected": None}])}
        out = {}
        for name, entry in cases.items():
            passed, reasons = vet_table_tool.vet(entry, registry, search=folder)
            # the seed tool's expected output cannot be declared: only its determinism is read
            out[name] = [r for r in reasons if not (name == "random" and r == "example_failed")]
    return out


def expected_vetting():
    return {"clean": [], "license": ["license_not_allowed"], "socket": ["opens_a_socket"], "write": ["writes_a_file"],
            "random": ["not_deterministic"]}


def observe_startup():
    """Boot's reasons on registry entries and on a declared request, ratified or not, and the real
    boot of a roster whose judge declares request_tools under the shipped constitution."""
    registry = _vetted_registry()
    vetted = tool_registry.entry(registry, "ratio")
    unapproved = dict(vetted, approved_by="D-1")   # well formed, but not on approving_decisions
    changed = dict(vetted, does="Divide the second figure by the first.")
    off_list = dict(vetted, license="Unlisted-1.0")
    with tempfile.TemporaryDirectory() as td:
        bare, ratified = Path(td) / "bare", Path(td) / "ratified"
        for root in (bare, ratified):
            (root / "config").mkdir(parents=True)
            (root / "scripts").mkdir()
            (root / "scripts" / "table_tools.py").write_bytes((ROOT / "scripts" / "table_tools.py").read_bytes())
            (root / "config" / "table_tools.json").write_text(json.dumps(registry), encoding="utf-8")
        (bare / "config" / "constitution.json").write_text(json.dumps({"amendments": []}), encoding="utf-8")
        (ratified / "config" / "constitution.json").write_text(json.dumps({"amendments": [
            {"id": FIXTURE_AMENDMENT, "operator_approved": True,
             "change": {"setting": "request_tools on the cell_claim task", "task": "cell_claim_request"}},
            {"id": "INFRA-UNAPPROVED", "operator_approved": False, "change": "cell_claim_request request_tools"}]}),
            encoding="utf-8")
        unratified = tool_registry.startup_refusals("cell_claim", ["ratio"], root=bare)
        accepted = tool_registry.startup_refusals("cell_claim", ["ratio"], root=ratified)
        unknown = tool_registry.startup_refusals("cell_claim", ["ratio", "no_such_tool"], root=ratified)
    return {"vetted": tool_registry.entry_refusals(vetted, registry),
            "unapproved": any("approved by no operator decision" in r for r in tool_registry.entry_refusals(unapproved, registry)),
            "changed": any("not vetted as declared" in r for r in tool_registry.entry_refusals(changed, registry)),
            "off list": any("license off" in r for r in tool_registry.entry_refusals(off_list, registry)),
            "unratified": [r.split(":")[0] for r in unratified], "ratified": accepted, "unknown": len(unknown),
            "boot": _boot({JUDGE: CONTRACT_ON}), "boot off": _boot({JUDGE: CONTRACT_OFF}),
            "boot unratified": _boot({JUDGE: CONTRACT_ON}, unratified=True)}


def expected_startup():
    return {"vetted": [], "unapproved": True, "changed": True, "off list": True, "unratified": ["[table-tool-request] STOP"],
            # INFRA-056 (D-705) ratifies the request on the real tree, so the real boot with the request
            # declared boots; the same real boot reading the shipped constitution without the ratifying
            # amendment still refuses ("boot unratified").
            "ratified": [], "unknown": 1, "boot": "booted", "boot off": "booted", "boot unratified": "refused"}


class _Unratified:
    """tool_registry's json as the real boot sees it with the shipped constitution minus `dropped`
    (the amendment that ratifies the request): the file is never written, every other read is untouched."""

    def __init__(self, dropped):
        self.dropped = dropped

    def __getattr__(self, name):
        return getattr(json, name)

    def loads(self, text, *args, **kwargs):
        value = json.loads(text, *args, **kwargs)
        if isinstance(value, dict) and isinstance(value.get("amendments"), list):
            value = dict(value, amendments=[a for a in value["amendments"]
                                            if not (isinstance(a, dict) and a.get("id") == self.dropped)])
        return value


def _boot(contracts, unratified=False):
    """The real boot (orchestrator.build) on the shipped roster with `contracts` in place of the
    shipped judge's: booted, or refused with the roster's own reason. With `unratified` the boot
    reads the shipped constitution without the amendment that ratifies the request today."""
    import harness.run_agent as run_agent
    import orchestrator
    from unittest.mock import patch
    real = orchestrator.json.load

    def load(fh):
        value = real(fh)
        if isinstance(value, dict) and "contracts" in value:
            kept = {n: c for n, c in value["contracts"].items() if not judge_agent._judge(c)}
            value = dict(value, contracts=dict(kept, **contracts))
        return value
    shipped = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
    registry = dict(shipped, **{JUDGE: dict(JUDGE_SPEC)})
    view = contextlib.nullcontext()
    if unratified:
        view = patch.object(tool_registry, "json", _Unratified(tool_registry.request_ratified(ROOT)))
    with tempfile.TemporaryDirectory() as td, patch.object(orchestrator.json, "load", load), view:
        try:
            run_agent.build_orchestrator(root=ROOT, out_root=Path(td), registry=registry)
            return "booted"
        except ValueError as exc:
            return "refused" if "[table-tool-request] STOP" in str(exc) else "other"


def proofs_a():
    import vet_table_tool
    child = vet_table_tool.CHILD
    return [
        ("a tool that opens a socket is refused", observe_vetting, expected_vetting,
         lambda: patched(vet_table_tool, "CHILD", child.replace('event.startswith("socket.")', 'event.startswith("no_such.")'))),
        ("a tool that writes a file is refused", observe_vetting, expected_vetting,
         lambda: patched(vet_table_tool, "CHILD", child.replace('if event == "open":', "if False:")
                         .replace("if event.startswith(CHANGES):", "if False:"))),
        ("a non-deterministic tool is refused", observe_vetting, expected_vetting,
         lambda: patched(vet_table_tool, "SEEDS", ("1", "1"))),
        ("a license off the allowlist is refused", observe_vetting, expected_vetting,
         lambda: patched(tool_registry, "license_allowed", lambda entry, registry: True)),
        ("an entry no decision approves is refused at start-up", observe_startup, expected_startup,
         lambda: patched(tool_registry, "approved", lambda entry, registry: True)),
        ("an entry changed after vetting is refused at start-up", observe_startup, expected_startup,
         lambda: patched(tool_registry, "vetted_sha256", lambda entry, root=None, search=None: (entry.get("vetting") or {}).get("sha256"))),
        ("a request with no ratified amendment is refused", observe_startup, expected_startup,
         lambda: patched(tool_registry, "request_ratified", lambda root=None: FIXTURE_AMENDMENT)),
        ("the real boot reads the declared request", observe_startup, expected_startup,
         lambda: patched(judge_agent, "request_tools", lambda task, contracts: [])),
    ]


# ---------- B: the tools themselves ------------------------------------------------------------

def observe_tools():
    """Each tool on the fixture context, through the one batch executor, and the shipped vetting."""
    calls = [("get_cells", ["r1c2", "r2c1"]), ("difference", ["r1c2", "r2c2"]), ("difference", ["r2c2", "f1"]),
             ("ratio", ["r1c2", "r2c2"]), ("ratio", ["r1c2", "r3c2"]), ("ratio", ["r1c3", "r2c3"]),
             ("difference", ["r1c2", "r1c3"]), ("compare", ["r1c3", "f2"]), ("compare", ["r2c3", "r3c3"]),
             ("find_figure", ["f1"]), ("find_figure", ["f2"]), ("column_extreme", ["c2"]), ("column_extreme", ["c1"])]
    rows = [{"line": i, "tool": name, "args": args, "refused": None} for i, (name, args) in enumerate(calls)]
    registry = tool_registry.load()
    table_tools.execute(rows, json.loads(json.dumps(CONTEXT)),
                        lambda name: tool_registry.resolve(tool_registry.entry(registry, name)))
    return {"results": [row["value"] if row["ok"] else row["refused"] for row in rows],
            "shipped": {e["name"]: tool_registry.entry_refusals(e, registry) for e in registry["tools"]}}


def expected_tools():
    return {"results": ["r1c2 = 12.5; r2c1 = B", "2.5", "-2.5", "1.25", "zero_divisor", "1.6", "percent_against_plain",
                        "greater", "equal", "r1c2", "in no cell", "highest r1c2 = 12.5; lowest r3c2 = 0", "no_numbers"],
            "shipped": {name: [] for name in SIX + EXTRA}}


def proofs_b():
    return [
        ("a zero divisor is refused", observe_tools, expected_tools,
         lambda: with_source(table_tools, "ratio", "if y == 0:", "if False:")),
        ("a percent against a plain number is refused", observe_tools, expected_tools,
         lambda: with_source(table_tools, "_pair", "if px != py:", "if False:")),
        ("the difference is the first minus the second", observe_tools, expected_tools,
         lambda: with_source(table_tools, "difference", "fmt(x - y)", "fmt(y - x)")),
        ("a tool runs the registry's entry", observe_tools, expected_tools,
         lambda: patched(tool_registry, "resolve", lambda entry: table_tools.get_cells)),
    ]


# ---------- C, D, E: the round on the real review ------------------------------------------------

def _review(units_text, reply, contracts=None, rule=None):
    """cell_selection.review on one unit, a fixed decision and a request answered by `reply`:
    (calls, the specs and prompts of each request, the questions asked)."""
    rule = rule or RULE
    asked, requests = [], []

    def ask(prompt):
        asked.append(prompt)
        return _decision()

    def ask_request(spec):
        def run(prompt):
            requests.append({"spec": spec, "prompt": prompt})
            return reply
        return run
    units = [{"unit_id": "u01", "index": 0, "text": units_text}]
    with patched(cell_selection, "threshold_of", lambda config: .7):
        _, calls = cell_selection.review(units, rule, None, ask, cell_selection.load_config(),
                                         contracts={JUDGE: contracts or CONTRACT_ON}, ask_request=ask_request)
    return calls, requests, asked


SIX_LINES = "\n".join(["difference(r1c2, r2c2)", "ratio(r1c2, r3c2)", "compare(r1c2, f1)", "find_figure(f2)",
                       "column_extreme(c2)", "difference(r2c2, r3c2)"])


def observe_round():
    calls, requests, asked = _review(QUAY, SIX_LINES)
    spec = requests[0]["spec"] if requests else None
    rows = [r for r in calls["tool_rows"] if r.get("request_call")]
    four = "\n".join(SIX_LINES.split("\n")[:4])
    return {"requests": len(requests), "questions": len(asked), "counted": calls.get("requests"),
            "refused": [r["refused"] for r in rows], "results in question": "RESULTS\n" in (asked[0] if asked else ""),
            "grammar four": bool(spec) and contract_decoding.request_accepts(spec, four),
            "grammar five": bool(spec) and contract_decoding.request_accepts(spec, four + "\ncompare(r1c2, f1)")}


def expected_round():
    return {"requests": 1, "questions": 1, "counted": 1, "refused": [None, None, None, None, "above_max_calls", "above_max_calls"],
            "results in question": True, "grammar four": True, "grammar five": False}


def proofs_c():
    real_round = table_tools.request_round

    def twice(*args, **kwargs):
        real_round(*args, **kwargs)
        return real_round(*args, **kwargs)
    return [
        ("lines above max_calls are refused", observe_round, expected_round,
         lambda: with_source(table_tools, "parse", "if at >= max_calls:", "if False:")),
        ("the grammar admits no line above max_calls", observe_round, expected_round,
         lambda: with_source(contract_decoding, "RequestGrammar", "state[1] < self.contract.max_calls else None", "True else None")),
        ("one request per question, never a second round", observe_round, expected_round,
         lambda: patched(table_tools, "request_round", twice)),
    ]


BAD_LINES = "\n".join(["get_cells(r1c1)", "difference(r9c9, r1c2)", "difference(61.5, r1c2)", "ratio(r1c2, r2c2)"])


def observe_refusals():
    calls, requests, asked = _review(QUAY, BAD_LINES)
    spec = requests[0]["spec"]
    rows = [r for r in calls["tool_rows"] if r.get("request_call")]
    return {"rows": [(r["tool"], r["args"], r["refused"]) for r in rows],
            "grammar": [contract_decoding.request_accepts(spec, line) for line in BAD_LINES.split("\n")],
            "stamped": all(r.get("prompt_sha256") == judge_agent.sha256(requests[0]["prompt"]) for r in rows)}


def expected_refusals():
    return {"rows": [(None, [], "tool_not_shown"), ("difference", ["r9c9", "r1c2"], "id_not_valid"),
                     ("difference", ["r1c2"], "literal_number"), ("ratio", ["r1c2", "r2c2"], None)],
            "grammar": [False, False, False, True], "stamped": True}


def proofs_d():
    real_rows = judge_agent.tool_rows
    return [
        ("a tool not shown is refused", observe_refusals, expected_refusals,
         lambda: with_source(table_tools, "parse", "if name not in by_name:\n", "if False:\n")),
        ("an id the table does not hold is refused", observe_refusals, expected_refusals,
         # the parser refuses it and, behind it, the tool's own reading of the id: both are removed
         lambda: both(with_source(table_tools, "parse", "if any(a not in ids[t] for a, t in zip(args, types)):", "if False:"),
                      with_source(table_tools, "value_of", "if ref not in context[\"cells\"]:", "if False:"))),
        ("a typed number is refused", observe_refusals, expected_refusals,
         lambda: with_source(table_tools, "parse", "if any(_LITERAL.fullmatch(a) for a in args):", "if False:")),
        ("every refused line is recorded", observe_refusals, expected_refusals,
         lambda: patched(judge_agent, "tool_rows", lambda task, contracts, rule_id, unit_id, prompt, rows: real_rows(
             task, contracts, rule_id, unit_id, prompt, [r for r in rows if not r.get("refused")]))),
        ("the grammar admits no unshown tool, bad id or number", observe_refusals, expected_refusals,
         lambda: with_source(contract_decoding, "RequestContract",
                             "self.ids = {kind: tuple(values) for kind, values in spec['ids'].items()}",
                             "self.ids = {kind: tuple(values) + ('r9c9', '61.5') for kind, values in spec['ids'].items()}")),
    ]


WORDS = "\n".join(("## Roles", "", "Table 4: Roles by team.", "", "| Team | Lead | Region |", "|---|---|---|",
                   "| Northern | Avery | Coast |", "| Southern | Blake | Inland |", ""))
WORDS_LONG = "\n".join(("## Roles", "", "Table 5: Roles by team.", "", "| Team | Lead | Region |", "|---|---|---|")
                       + tuple("| Team%s | Lead%s | Region%s |" % (chr(65 + i), chr(65 + i), chr(65 + i)) for i in range(15)) + ("",))
WORDS_RULE = dict(RULE, rule="The Northern team is led by Avery.")
WORDS_LONG_RULE = dict(RULE, rule="TeamA is led by LeadA on RegionA.")


def observe_shown():
    out = {}
    for name, text, rule in (("words", WORDS, WORDS_RULE), ("words cut", WORDS_LONG, WORDS_LONG_RULE), ("numbers", QUAY, RULE)):
        calls, requests, _ = _review(text, "NONE", rule=rule)
        out[name] = {"tools": [t[0] for t in requests[0]["spec"]["tools"]] if requests else [],
                     "skipped": calls.get("requests_skipped")}
    return out


def expected_shown():
    return {"words": {"tools": [], "skipped": 1}, "words cut": {"tools": ["get_cells"], "skipped": 0},
            "numbers": {"tools": ARITHMETIC, "skipped": 0}}


def proofs_e():
    return [
        ("a table with no numbers is shown no arithmetic tool", observe_shown, expected_shown,
         lambda: patched(tool_registry, "applies", lambda entry, facts: True)),
        ("the shown numbers are counted on the cells shown", observe_shown, expected_shown,
         lambda: with_source(table_tools, "facts_of", '"shown_numbers": shown', '"shown_numbers": len(context["cells"])')),
        ("nothing is asked when no tool applies", observe_shown, expected_shown,
         lambda: with_source(table_tools, "request_round", "if not shown:", "if False:")),
    ]


# ---------- F, G: the real phase 5.5 -------------------------------------------------------------

def _phase(contract, reply="difference(r1c2, r2c2)\nratio(r1c2, f1)\nget_cells(r1c1)"):
    """The real phase 5.5 on a mocked run, a fixture judge beside the shipped roster, its choice and
    its request answered by fixtures that each write one reply record, as a backend function does."""
    import agent_wrapper
    import cell_selection_checks as csc
    import harness.run_agent as run_agent
    import honest_output_checks as hoc
    import passage_pairs
    from unittest.mock import patch
    sent, generated = [], []

    def call_choice(self, prompt, answers, value):
        sent.append(prompt)
        r = agent_wrapper.CallResult(self.backend, "fixture-judge", "", parsed=_decision())
        self._write_reply(r, {"payload": prompt, "form": "rendered_prompt", "no_reply": True, "decision": _decision()})
        return r

    def call_local(self, prompt, *, max_new_tokens=1024, system=None):
        spec = getattr(self, "_tool_request", None)
        if self.name != JUDGE:
            raise AssertionError("only the fixture judge generates here")
        generated.append({"spec": bool(spec), "max_new_tokens": max_new_tokens,
                          "admitted": bool(spec) and contract_decoding.request_accepts(spec, reply)})
        r = agent_wrapper.CallResult(self.backend, "fixture-judge", reply, usage={"truncated": False})
        self._write_reply(r, {"payload": prompt, "form": "rendered_prompt"})
        return r
    real = run_agent.build_orchestrator

    def orchestrator(**kwargs):
        orch = real(**kwargs)
        shipped = [n for n, c in orch.contracts.items() if judge_agent._judge(c)]
        orch.registry = dict({n: s for n, s in orch.registry.items() if n not in shipped}, **{JUDGE: dict(JUDGE_SPEC)})
        orch.contracts = dict({n: c for n, c in orch.contracts.items() if n not in shipped}, **{JUDGE: contract})
        return orch
    text = chr(10).join((hoc.DOC_TEXT, csc.QUAY_UNIT))
    with tempfile.TemporaryDirectory() as td, patch.object(agent_wrapper.AgentWrapper, "call_choice", call_choice), \
            patch.object(agent_wrapper.AgentWrapper, "call_local", call_local), \
            patched(cell_selection, "threshold_of", lambda config: .7), patch.object(passage_pairs, "embed", lambda items: None), \
            patch.object(run_agent, "build_orchestrator", orchestrator):
        folder = Path(hoc.mocked_run(Path(td), style_guardian=False, text=text, rules=hoc.RULES + [RULE])["run_dir"])
        document = json.loads(next(folder.rglob("pairing_map.json")).read_text(encoding="utf-8"))["batch_sheet"]
        tools_path = folder / "audit" / judge_agent.TOOL_RECORDS
        tools = [json.loads(line) for line in tools_path.read_text(encoding="utf-8").splitlines()] if tools_path.is_file() else []
        replies = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((folder / "audit" / "model_replies").glob("*.json"))]
        outcomes_path = folder / "audit" / "model_replies" / "outcomes.jsonl"
        outcomes = [json.loads(line) for line in outcomes_path.read_text(encoding="utf-8").splitlines()] if outcomes_path.is_file() else []
    judge_replies = [r for r in replies if r.get("agent") == JUDGE]
    return {"sent": sent, "generated": generated, "tools": tools, "document": document,
            "judge replies": judge_replies, "outcomes": outcomes}


def observe_records():
    run = _phase(CONTRACT_ON)
    request_ids = [c["call_id"] for c in run["document"].get("judging_calls") or [] if c.get("plan_kind") == table_tools.REQUEST_PLAN]
    request_records = [r for r in run["judge replies"] if r["call_id"] in request_ids]
    rows = [r for r in run["tools"] if r.get("request_call")]
    text = json.dumps(rows)
    return {"requests": len(request_ids), "request records": len(request_records),
            "outcomes": sorted(o.get("outcome") for o in run["outcomes"] if o.get("call_id") in request_ids),
            "rows": [(r["tool"], r["args"], r["ok"], r["refused"]) for r in rows],
            "joined": all(r.get("call_id") in request_ids for r in rows) and bool(rows),
            "digests only": all(set(r) >= {"result_sha256"} and "value" not in r for r in rows)
            and not any(v in text for v in ("17.5", "Northern", "61.5")),
            "constrained": [g["spec"] for g in run["generated"]],
            "results in question": any("RESULTS\n" in s for s in run["sent"])}


def expected_records():
    return {"requests": 1, "request records": 1, "outcomes": ["free_text"],
            "rows": [("difference", ["r1c2", "r2c2"], True, None), ("ratio", ["r1c2", "f1"], True, None),
                     (None, [], False, "tool_not_shown")],
            "joined": True, "digests only": True, "constrained": [True], "results in question": True}


def proofs_f():
    import pipeline
    real_send = table_tools.send

    def send_twice(wrapper, stable, dynamic, spec):
        real_send(wrapper, stable, dynamic, spec)
        return real_send(wrapper, stable, dynamic, spec)
    return [
        ("each request line is one tool row", observe_records, expected_records,
         lambda: patched(pipeline, "_write_tool_rows", lambda orch, calls, call_of, real=pipeline._write_tool_rows: real(
             orch, dict(calls, tool_rows=[r for r in calls.get("tool_rows") or [] if not r.get("request_call")]), call_of))),
        ("one reply record per request", observe_records, expected_records,
         lambda: patched(table_tools, "send", send_twice)),
        ("the audit keeps digests only", observe_records, expected_records,
         lambda: patched(table_tools, "audit_rows", lambda calls, real=table_tools.audit_rows: [
             dict(r, value=c.get("value")) for r, c in zip(real(calls), calls)])),
        ("the request decodes under its grammar", observe_records, expected_records,
         lambda: with_source(table_tools, "send", "wrapper._tool_request = spec\n", "wrapper._tool_request = None\n")),
    ]


def observe_off():
    """The shipped state: no request_tools declared. The question sent, what was generated, the tool
    records, the row keys, against the measured question and the shipped contracts."""
    import cell_selection_checks as csc
    run = _phase(CONTRACT_OFF)
    measured = json.loads((ROOT / "benchmark" / "baselines" / "choice_judge_prompt.json").read_text(encoding="utf-8"))
    cells = cell_selection.select(csc.QUAY_UNIT, RULE["rule"], cell_selection.load_config())["cells"]
    figures = judge_agent.figures_block(cells, RULE["rule"])
    question = measured["choice"]["forms"]["claim"]["template"].replace("{cells}", cells).replace(
        "{claim}", RULE["rule"]).replace("{tools}", figures)
    row = (run["document"].get("cell_claims") or [{}])[0]
    return {"same question": run["sent"] == [question], "generated": len(run["generated"]),
            "tools": [r["tool"] for r in run["tools"]], "request keys": sorted(k for k in row if k.startswith("request")),
            "request plans": [c for c in run["document"].get("judging_calls") or [] if c.get("plan_kind") == table_tools.REQUEST_PLAN],
            "shipped request_tools": judge_agent.request_tools("cell_claim", judge_agent.shipped_contracts()),
            "question unchanged": cell_selection.question(cell_selection.load_config(), cells, RULE["rule"], {}) ==
            cell_selection.question(cell_selection.load_config(), cells, RULE["rule"], {}, "")}


def expected_off():
    return {"same question": True, "generated": 0, "tools": TOOLS, "request keys": [], "request plans": [],
            "shipped request_tools": [], "question unchanged": True}


def proofs_g():
    return [
        ("with nothing declared no request is made", observe_off, expected_off,
         lambda: both(patched(judge_agent, "request_tools", lambda task, contracts: list(SIX) if task == "cell_claim" else []),
                      patched(tool_registry, "request_ratified", lambda root=None: FIXTURE_AMENDMENT))),
        ("with nothing declared the question is the measured one", observe_off, expected_off,
         lambda: with_source(cell_selection, "question", "judge_agent.claim_tools(cells, claim, contracts) + results",
                             "judge_agent.claim_tools(cells, claim, contracts) + (results or 'RESULTS\\n\\n')")),
        ("with nothing declared the review adds no key", observe_off, expected_off,
         lambda: with_source(cell_selection, "review", "if requested:\n        calls.update", "if True:\n        calls.update")),
    ]


# ---------- running ---------------------------------------------------------------------------

PROOFS = {"A": proofs_a, "B": proofs_b, "C": proofs_c, "D": proofs_d, "E": proofs_e, "F": proofs_f, "G": proofs_g}
SAYS = {"A": "start-up refuses a license off the allowlist, a socket, a file write, a non-deterministic tool, an "
             "unapproved or changed entry and an unratified request, on the real boot too",
        "B": "each of the six tools is right on a fixture, refuses a zero divisor and a percent against a plain "
             "number, and every shipped entry is vetted as declared",
        "C": "one request per question, never a second round, and lines above max_calls are refused by the parser "
             "and the grammar",
        "D": "a tool not shown, an id the table does not hold and a typed number are refused and recorded, and the "
             "grammar admits none",
        "E": "a table with no numbers is shown no arithmetic tool, and nothing is asked when no tool applies",
        "F": "on the real phase each request is one reply record (free_text), its lines are its tool rows joined "
             "to its call, digests only, decoded under its grammar",
        "G": "with no request_tools declared, as shipped, the question sent is byte for byte the measured one, no request call is made, and the tool records, pairing-map row keys and judging calls carry nothing of the request (the whole run is not compared)"}


def run_check(letter):
    proofs = PROOFS[letter]()
    for name, observe, expected, neutralise in proofs:
        prove_effect(name=name, validate=lambda: cell_selection.CONFIG_PATH.is_file() and tool_registry.REGISTRY_PATH.is_file(),
                     observe=observe, check=lambda observe=observe, expected=expected, name=name:
                     ("PASS" if observe() == expected() else "FAIL", name), neutralise=neutralise)
    return "PASS", "%d proofs, each neutralise, fail, restore, pass: %s" % (len(proofs), SAYS[letter])


if __name__ == "__main__":
    letters = sys.argv[1:] or sorted(PROOFS)
    for letter in letters:
        print(letter, json.dumps(run_check(letter)))
