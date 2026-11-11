"""Proofs that the GNN never learns from runs (D-S112 item 1, D-417, D-432), on fixtures only.

Each proof runs the live code on a tempdir; each guarded rule is then neutralised in memory, the
proof must FAIL, the rule is restored and the proof must PASS. Never the real ontology/stores/.
Gate check 64 runs `main()`.

    py -3.12 -X utf8 scripts/ontology_gnn_rule_checks.py

The scan's scope, stated (D-432 item 3). It reads every Python file under scripts/, tools/,
benchmark/ and corpus_ingest/, and the launchers and container files (shimmer.sh, shimmer.bat,
start_shimmer.bat, tools/*.sh, tools/*.ps1, Dockerfile, compose.yaml). In Python it finds:
- a call of `gnn_update` by its name or any alias it is imported under;
- an attribute `gnn_update` or `main` taken from the module `ontology_gnn` under any alias
  (`import ontology_gnn as x`, `importlib.import_module("ontology_gnn")`, `__import__`);
- `getattr(<that module>, "gnn_update" or "main")`;
- any string naming the training command (`ontology_gnn.py`, or `-m ontology_gnn`).
In the other files it finds any line naming `ontology_gnn`.
It does NOT catch a name built at run time (a string assembled from parts, `eval`, `exec`).
Exempt, because they are the command itself or proofs of it: scripts/ontology_gnn.py,
scripts/verify_session1.py, every *_checks.py, and scripts/archived/.
"""
from __future__ import annotations

import ast
import contextlib
import json
import re
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ontology_gnn  # noqa: E402

PY_FOLDERS = ("scripts", "tools", "benchmark", "corpus_ingest")
OTHER_FILES = ("shimmer.sh", "shimmer.bat", "start_shimmer.bat", "Dockerfile", "compose.yaml")
OTHER_GLOBS = ("tools/*.sh", "tools/*.ps1")
EXEMPT = {"scripts/ontology_gnn.py", "scripts/verify_session1.py"}
COMMAND_TEXT = re.compile(r"ontology_gnn\.py|-m\s+ontology_gnn\b")
DECLARED_BY = "gate check fixture"


def _exempt(name):
    return name in EXEMPT or name.endswith("_checks.py") or name.startswith("scripts/archived/")


def read_sources():
    """({path: python source}, {path: other text}) of every file the scan reads."""
    py, other = {}, {}
    for folder in PY_FOLDERS:
        for path in sorted((ROOT / folder).rglob("*.py")):
            name = path.relative_to(ROOT).as_posix()
            if _exempt(name):
                continue
            try:
                py[name] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
    paths = [ROOT / n for n in OTHER_FILES] + [p for g in OTHER_GLOBS for p in sorted(ROOT.glob(g))]
    for path in paths:
        if path.is_file():
            try:
                other[path.relative_to(ROOT).as_posix()] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return py, other


def _module_aliases(tree):
    """Names bound to the module ontology_gnn, and names bound to its gnn_update or main."""
    modules, functions = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "ontology_gnn":
                    modules.add(a.asname or a.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "ontology_gnn":
            for a in node.names:
                if a.name in ("gnn_update", "main"):
                    functions.add(a.asname or a.name)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            f = node.value.func
            called = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            args = node.value.args
            if called in ("import_module", "__import__") and args and isinstance(args[0], ast.Constant) \
                    and args[0].value == "ontology_gnn":
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        modules.add(t.id)
    return modules, functions


def training_references(py, other):
    """[(file, line, what)] of every reference to the GNN's training a run path makes."""
    found = []
    for name, source in py.items():
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        modules, functions = _module_aliases(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name) and (f.id == "gnn_update" or f.id in functions - {"main"}):
                    found.append((name, node.lineno, "call of gnn_update"))
                if isinstance(f, ast.Name) and f.id in functions and f.id != "gnn_update":
                    found.append((name, node.lineno, "call of ontology_gnn.main"))
                if isinstance(f, ast.Attribute) and f.attr == "gnn_update":
                    found.append((name, node.lineno, "call of .gnn_update"))
                if isinstance(f, ast.Name) and f.id == "getattr" and len(node.args) >= 2 \
                        and isinstance(node.args[0], ast.Name) and node.args[0].id in modules \
                        and isinstance(node.args[1], ast.Constant) and node.args[1].value in ("gnn_update", "main"):
                    found.append((name, node.lineno, "getattr of ontology_gnn"))
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in modules \
                    and node.attr in ("gnn_update", "main"):
                found.append((name, node.lineno, "ontology_gnn.%s" % node.attr))
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and COMMAND_TEXT.search(node.value):
                found.append((name, node.lineno, "the training command named"))
    for name, text in other.items():
        for i, line in enumerate(text.splitlines(), 1):
            if "ontology_gnn" in line:
                found.append((name, i, "ontology_gnn named"))
    return sorted(set(found))


def _graph():
    nodes = [{"type": "Document", "id": "docA", "stub": False},
             {"type": "Provision", "id": "docA::REF-1", "finding_type": "factual", "action": "flag",
              "severity": "high", "context_refs": [], "stub": False},
             {"type": "Convention", "id": "CONV-001", "category": "review", "severity": "required"}]
    edges = [{"type": "HAS_PROVISION", "source": "docA", "target": "docA::REF-1"},
             {"type": "GOVERNED_BY", "source": "docA::REF-1", "target": "CONV-001"}]
    return {"scope": "default", "nodes": nodes, "edges": edges}


@contextlib.contextmanager
def _box(mod=ontology_gnn):
    """A tempdir with a declared training graph, and the module's run store pointed inside it."""
    with tempfile.TemporaryDirectory(prefix="shimmer_gnn_rule_") as tmp:
        tmp = Path(tmp)
        stores = tmp / "ontology" / "stores"
        stores.mkdir(parents=True)
        training = tmp / "training"
        training.mkdir()
        graph = training / "graph.json"
        graph.write_text(json.dumps(_graph()), encoding="utf-8")
        with patch.object(mod, "OGE_STORES_DIR", stores):
            yield types.SimpleNamespace(tmp=tmp, stores=stores, graph=graph)


def _declare(mod, path, graph, name="fixture"):
    return mod.declare_training_set(path, graph, name, "a fixture graph made for training",
                                    domain_agnostic=True, case_agnostic=True, declared_by=DECLARED_BY)


def _refused(call, mod=ontology_gnn):
    try:
        call()
    except mod.TrainingSetRefused as exc:
        return str(exc)
    return None


def proof_no_run_calls_gnn_update(sources=None):
    """No run path reaches the GNN's training, by any alias, main, getattr or the command line;
    the pipeline does not import ontology_gnn."""
    py, other = read_sources() if sources is None else sources
    refs = training_references(py, other)
    pipeline = py.get("scripts/pipeline.py", "")
    imported = any(isinstance(n, (ast.Import, ast.ImportFrom)) and (
        getattr(n, "module", None) == "ontology_gnn" or any(a.name == "ontology_gnn" for a in n.names))
        for n in ast.walk(ast.parse(pipeline))) if pipeline else True
    ok = not refs and not imported and bool(pipeline)
    return ok, "references to the GNN's training outside it: %s; the pipeline imports ontology_gnn %s; %d Python " \
               "and %d other files read" % (refs[:4] or "none", imported, len(py), len(other))


def proof_run_store_refused(mod=ontology_gnn):
    """The run store is refused by place, by content (its bytes copied elsewhere), and by the build
    provenance ontology_graph writes; no state is written."""
    with _box(mod) as box:
        state = box.tmp / "state.json"
        stored = box.stores / "graph.json"
        stored.write_text(json.dumps(_graph()), encoding="utf-8")
        in_place = box.tmp / "in_place.json"
        _declare(mod, in_place, stored, "the run store")
        place = _refused(lambda: mod.gnn_update(in_place, state, device="cpu", log=False), mod)
        copy = box.tmp / "elsewhere" / "graph.json"
        copy.parent.mkdir()
        copy.write_bytes(stored.read_bytes())
        copied = box.tmp / "copied.json"
        _declare(mod, copied, copy, "a copy of the run store")
        content = _refused(lambda: mod.gnn_update(copied, state, device="cpu", log=False), mod)
        built = box.tmp / "built" / "graph.json"
        built.parent.mkdir()
        built.write_text(json.dumps(dict(_graph(), built_from={"default_sources": ["provisions"],
                                                                "overridden_sources": []})), encoding="utf-8")
        from_store = box.tmp / "from_store.json"
        _declare(mod, from_store, built, "a graph built from the stores")
        provenance = _refused(lambda: mod.gnn_update(from_store, state, device="cpu", log=False), mod)
        written = state.exists()
    ok = bool(place and content and provenance) and "never a training set" in place and "byte for byte" in content \
        and "built from" in provenance and not written
    return ok, "in place: %r; a byte copy elsewhere: %r; built from the stores: %r; state written %s" % (
        place, content, provenance, written)


def proof_explicit_store_sources_refused(mod=ontology_gnn):
    """D-446: a graph build_graph made from the stores' own files, passed explicitly as its sources
    (so no source is a default), is refused by the source paths it records, whether the file sits
    under ontology/stores/ or under durable/; one built from files elsewhere is accepted."""
    import ontology_graph
    with _box(mod) as box:
        durable = box.tmp / "durable" / "learnings"
        durable.mkdir(parents=True)
        elsewhere = box.tmp / "material"
        elsewhere.mkdir()
        for folder in (box.stores, durable, elsewhere):
            (folder / "provisions.jsonl").write_text("", encoding="utf-8")
        others = {k: elsewhere / ("%s.json" % k) for k in ontology_graph.DEFAULT_SOURCES if k != "provisions"}
        state = box.tmp / "state.json"
        why = {}
        with patch.object(mod, "DURABLE_DIR", box.tmp / "durable"):
            for label, provisions in (("stores", box.stores), ("durable", durable), ("elsewhere", elsewhere)):
                out = box.tmp / ("graph_%s.json" % label)
                ontology_graph.build_graph(sources=dict(others, provisions=provisions / "provisions.jsonl"),
                                           out_path=str(out))
                decl = box.tmp / ("decl_%s.json" % label)
                _declare(mod, decl, out, "built from " + label)
                why[label] = _refused(lambda d=decl, l=label: mod.gnn_update(d, box.tmp / ("s_%s.json" % l),
                                                                            device="cpu", log=False), mod)
        recorded = json.loads((box.tmp / "graph_stores.json").read_text(encoding="utf-8"))["built_from"]
    ok = (bool(why["stores"]) and "provisions" in why["stores"] and bool(why["durable"]) and why["elsewhere"] is None
          and not recorded["default_sources"] and "provisions" in recorded.get("source_paths", {}))
    return ok, "stores' file passed explicitly: %r; a durable/ file: %r; files elsewhere: %r" % (
        why["stores"], why["durable"], why["elsewhere"] or "accepted")


def proof_each_refusal(mod=ontology_gnn):
    """Each declaration fault and a missing state path is refused, and no state is written (D-432 item 4)."""
    with _box(mod) as box:
        state = box.tmp / "state.json"
        decl = box.tmp / "set.json"
        _declare(mod, decl, box.graph)
        good = json.loads(decl.read_text(encoding="utf-8"))
        cases = {"no declaration": None, "wrong kind": dict(good, kind="other"),
                 "not domain-agnostic": dict(good, domain_agnostic=False),
                 "not case-agnostic": dict(good, case_agnostic=False), "no name": dict(good, name=""),
                 "no material": dict(good, material=""), "no one declared it": dict(good, declared_by="")}
        why = {}
        for label, value in cases.items():
            path = box.tmp / ("case_%d.json" % len(why))
            if value is not None:
                path.write_text(json.dumps(value), encoding="utf-8")
            why[label] = _refused(lambda p=path: mod.gnn_update(p, state, device="cpu", log=False), mod)
        why["no state path"] = _refused(lambda: mod.gnn_update(decl, None, device="cpu", log=False), mod)
        why["declared without the statement"] = _refused(lambda: mod.declare_training_set(
            box.tmp / "x.json", box.graph, "x", "y", domain_agnostic=None, case_agnostic=True,
            declared_by=DECLARED_BY), mod)
        box.graph.write_text(json.dumps(dict(_graph(), nodes=_graph()["nodes"][:2])), encoding="utf-8")
        why["the graph changed"] = _refused(lambda: mod.gnn_update(decl, state, device="cpu", log=False), mod)
        written = state.exists()
    missing = sorted(k for k, v in why.items() if not v)
    ok = not missing and not written
    return ok, "%d faults, refused: %s; not refused: %s; state written %s" % (
        len(why), ", ".join(sorted(why)), missing or "none", written)


def proof_state_without_provenance_refused():
    """A state with no training chain (as every run-trained state was) is refused by the reader,
    the candidate finder and the training command; a trained state keeps the whole chain."""
    import ontology_candidates
    import ontology_gnn_state
    with _box() as box:
        old = box.tmp / "old_state.json"
        old.write_text(json.dumps({"schema": ontology_gnn.STATE_SCHEMA, "feature_dim": ontology_gnn.FEATURE_DIM,
                                   "hidden": ontology_gnn.DEFAULT_HIDDEN, "encoder_weight": [[0.0]],
                                   "decoder_weight": [[0.0]], "trained_node_ids": []}), encoding="utf-8")
        summary = ontology_gnn_state.state_summary(old)
        finder = None
        try:
            ontology_candidates.find_candidates(_graph(), state_path=old, device="cpu")
        except ontology_gnn_state.StateRefused as exc:
            finder = str(exc)
        decl = box.tmp / "set.json"
        _declare(ontology_gnn, decl, box.graph, "first")
        command = _refused(lambda: ontology_gnn.gnn_update(decl, old, device="cpu", log=False))
        state = box.tmp / "state.json"
        ontology_gnn.gnn_update(decl, state, device="cpu", log=False)
        second = box.tmp / "training2" / "graph.json"
        second.parent.mkdir()
        second.write_text(json.dumps(dict(_graph(), nodes=_graph()["nodes"] + [{"type": "SpeechAct", "id": "s"}])),
                          encoding="utf-8")
        decl2 = box.tmp / "set2.json"
        _declare(ontology_gnn, decl2, second, "second")
        ontology_gnn.gnn_update(decl2, state, device="cpu", log=False)
        chain = [link["name"] for link in json.loads(state.read_text(encoding="utf-8"))["training_sets"]]
        usable = ontology_gnn_state.state_summary(state).get("usable")
    ok = (summary.get("usable") is False and summary.get("refused") and bool(finder) and bool(command)
          and chain == ["first", "second"] and usable is True)
    return ok, "reader: usable %s; finder: %r; training command: %r; a trained state's chain %s" % (
        summary.get("usable"), finder, command, chain)


def proof_run_end_never_trains():
    """The pipeline's own run-end block, run on a tempdir with gnn_update replaced by a recorder:
    capture and the graph rebuild happen, and gnn_update is never called."""
    import ontology_capture
    import ontology_graph
    import pipeline
    calls = []
    with tempfile.TemporaryDirectory(prefix="shimmer_run_end_") as tmp:
        d = Path(tmp)
        deliv = d / "deliv"
        doc_id = "docX"
        (deliv / doc_id).mkdir(parents=True)
        master = {"document_id": doc_id, "amendments": [
            {"location": "REF-1", "convention_ref": "CONV-001", "context_refs": [], "finding_type": "factual",
             "original_text": "some provision text", "proposed_text": None, "action": "flag", "comment": "c",
             "severity": "high"}]}
        (deliv / doc_id / "review_data.json").write_text(json.dumps(master), encoding="utf-8")
        (d / "delta_proposals.json").write_text(json.dumps({"generated_at": "t", "proposals": []}), encoding="utf-8")

        class RunContext:
            run_id = "RUN-RULE-CHECK"

            def deliverables_dir(self):
                return deliv

            def delta_proposals_path(self):
                return d / "delta_proposals.json"
        stores = d / "stores"
        real_capture, real_build = ontology_capture.capture_run, ontology_graph.build_graph

        def capture(*a, **k):
            k["stores_dir"] = str(stores)
            return real_capture(*a, **k)

        def build(*a, **k):
            k["sources"] = {"provisions": stores / "provisions.jsonl"}
            k["out_path"] = str(d / "graph.json")
            return real_build(*a, **k)
        with patch.object(ontology_capture, "capture_run", capture), patch.object(ontology_graph, "build_graph", build), \
                patch.object(ontology_gnn, "gnn_update", lambda *a, **k: calls.append(1)):
            run_end(pipeline)(RunContext(), [{"id": doc_id, "name": doc_id}],
                              {doc_id: {"amendments_json": str(deliv / doc_id / "review_data.json")}})
        built = (d / "graph.json").exists()
        captured = (stores / "provisions.jsonl").exists()
        trained = list(d.rglob("gnn_state.json"))
    ok = built and captured and not calls and not trained
    return ok, "the run end captured %s, rebuilt the graph %s, called gnn_update %d times, left a GNN state %s" % (
        captured, built, len(calls), bool(trained))


def run_end(pipeline):
    """The function proof_run_end_never_trains runs: the pipeline's own run-end block."""
    return pipeline._ontology_run_end


def _module_with(old, new):
    source = Path(ontology_gnn.__file__).read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise RuntimeError("the passage moved, so the neutralisation cannot be applied")
    mod = types.ModuleType("ontology_gnn_neutralised")
    mod.__file__ = ontology_gnn.__file__
    exec(compile(source.replace(old, new), ontology_gnn.__file__, "exec"), mod.__dict__)
    return mod


def _with(text):
    py, other = read_sources()
    py = dict(py)
    py["scripts/pipeline.py"] = py["scripts/pipeline.py"] + "\n\n" + text + "\n"
    return py, other


def _with_other(name, text):
    py, other = read_sources()
    return py, dict(other, **{name: other.get(name, "") + "\n" + text + "\n"})


@contextlib.contextmanager
def _training_run_end():
    """The run end with a GNN update put back, as it was before D-417."""
    original = globals()["run_end"]

    def trained(pipeline):
        def step(*a, **k):
            pipeline._ontology_run_end(*a, **k)
            ontology_gnn.gnn_update("declared", "state")
        return step
    globals()["run_end"] = trained
    try:
        yield
    finally:
        globals()["run_end"] = original


PROOFS = [
    ("no run path reaches the GNN's training (aliases, main, getattr, the command line, launchers)",
     proof_no_run_calls_gnn_update),
    ("the run store is refused by place, by content and by build provenance", proof_run_store_refused),
    ("a graph built from the stores' own files, passed explicitly, is refused", proof_explicit_store_sources_refused),
    ("every declaration fault and a missing state path are refused", proof_each_refusal),
    ("a state with no training chain is refused by the reader, the finder and the command",
     proof_state_without_provenance_refused),
    ("the pipeline's own run end captures and rebuilds, and never calls gnn_update", proof_run_end_never_trains),
]

NEUTRALISATIONS = [
    ("a run path calling gnn_update", "proof_no_run_calls_gnn_update",
     lambda: proof_no_run_calls_gnn_update(_with("def _x():\n    ontology_gnn.gnn_update('a', 'b')"))),
    ("an aliased import of gnn_update called", "proof_no_run_calls_gnn_update",
     lambda: proof_no_run_calls_gnn_update(_with("from ontology_gnn import gnn_update as _g\n_g('a', 'b')"))),
    ("the training command's main called", "proof_no_run_calls_gnn_update",
     lambda: proof_no_run_calls_gnn_update(_with("import ontology_gnn as _o\n_o.main(['train'])"))),
    ("the training command started as a child process", "proof_no_run_calls_gnn_update",
     lambda: proof_no_run_calls_gnn_update(_with(
         "import subprocess\nsubprocess.run(['python', 'scripts/ontology_gnn.py', 'train'])"))),
    ("a launcher starting the training", "proof_no_run_calls_gnn_update",
     lambda: proof_no_run_calls_gnn_update(_with_other("tools/entrypoint.sh", "python scripts/ontology_gnn.py train"))),
    ("the run store accepted in place", "proof_run_store_refused", lambda: proof_run_store_refused(_module_with(
        "    if graph.is_relative_to(OGE_STORES_DIR.resolve()):", "    if False:"))),
    ("a byte copy of the store accepted", "proof_run_store_refused", lambda: proof_run_store_refused(_module_with(
        "            if stored.is_file() and _sha(stored) == digest:", "            if False:"))),
    ("the build provenance not read", "proof_run_store_refused", lambda: proof_run_store_refused(_module_with(
        '    if isinstance(built, dict) and built.get("default_sources"):', "    if False:"))),
    ("the recorded source paths not read", "proof_explicit_store_sources_refused",
     lambda: proof_explicit_store_sources_refused(_module_with(
         "        if any(resolved == root or resolved.is_relative_to(root) for root in run_written):",
         "        if False:"))),
    ("durable/ not counted as run-written", "proof_explicit_store_sources_refused",
     lambda: proof_explicit_store_sources_refused(_module_with(
         "    run_written = (OGE_STORES_DIR.resolve(), DURABLE_DIR.resolve())",
         "    run_written = (OGE_STORES_DIR.resolve(),)"))),
    ("the digest not compared", "proof_each_refusal", lambda: proof_each_refusal(_module_with(
        '    if not graph.is_file() or _sha(graph) != declaration.get("graph_sha256"):', "    if not graph.is_file():"))),
    ("the kind not read", "proof_each_refusal", lambda: proof_each_refusal(_module_with(
        '    if not isinstance(declaration, dict) or declaration.get("kind") != TRAINING_SET_KIND:',
        "    if not isinstance(declaration, dict):"))),
    ("the agnostic statement not read", "proof_each_refusal", lambda: proof_each_refusal(_module_with(
        '    if declaration.get("domain_agnostic") is not True or declaration.get("case_agnostic") is not True:',
        "    if False:"))),
    ("the name not required", "proof_each_refusal", lambda: proof_each_refusal(_module_with(
        '    if not declaration.get("name"):', "    if False:"))),
    ("the material not required", "proof_each_refusal", lambda: proof_each_refusal(_module_with(
        '    if not declaration.get("material"):', "    if False:"))),
    ("the declaring person not required", "proof_each_refusal", lambda: proof_each_refusal(_module_with(
        '    if not (isinstance(declaration.get("declared_by"), str) and declaration["declared_by"].strip()):',
        "    if False:"))),
    ("a missing state path accepted", "proof_each_refusal", lambda: proof_each_refusal(_module_with(
        "    if not state_path:", "    if False:"))),
    ("the statement written by the tool", "proof_each_refusal", lambda: proof_each_refusal(_module_with(
        "    if domain_agnostic is not True or case_agnostic is not True:", "    if False:"))),
    ("a state without provenance used", "proof_state_without_provenance_refused",
     lambda: _run_patched("ontology_gnn_state", "provenance_refusal", lambda state: None,
                          proof_state_without_provenance_refused)),
    ("the run end training the GNN", "proof_run_end_never_trains", lambda: _in(_training_run_end,
                                                                             proof_run_end_never_trains)),
]


def _run_patched(module, attr, value, proof):
    with patch.object(__import__(module), attr, value):
        return proof()


def _in(context, proof):
    with context():
        return proof()


def run(call):
    try:
        return call()
    except Exception as exc:
        return False, "raised %s: %s" % (type(exc).__name__, str(exc)[:200])


def main():
    failures = 0
    for what, proof in PROOFS:
        ok, detail = run(proof)
        failures += not ok
        print("%s %s: %s" % ("PASS" if ok else "FAIL", what, detail))
    named = {p.__name__: p for _, p in PROOFS}
    for what, name, neutralised in NEUTRALISATIONS:
        ok, detail = run(neutralised)
        if ok:
            failures += 1
            print("FAIL neutralised (%s) and the proof still passes: %s" % (what, detail))
            continue
        ok, _ = run(named[name])
        if not ok:
            failures += 1
            print("FAIL restored (%s) and the proof fails" % what)
            continue
        print("PASS neutralised (%s): FAIL; restored: PASS" % what)
    total = len(PROOFS) + len(NEUTRALISATIONS)
    print("%s GNN rule: %d of %d proofs and neutralisations pass" % ("PASS" if not failures else "FAIL",
                                                                    total - failures, total))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
