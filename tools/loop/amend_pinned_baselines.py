"""Compute pipeline.py function hashes with each pinned-baseline file's own method and append one
amendment per file (benchmark/fixtures/topology_reference_contract.json and
multi_round_baseline_contract.json). Used by the 27 October 2026 loop lead for every
pinned-baseline amendment; the reason starts "Operator-directed, <date>, loop stage SNN:".

Usage: py -3.12 tools/loop/amend_pinned_baselines.py "<reason>" <document> [--dry]
"""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from execution_topology_checks import reference_tree  # noqa: E402


def norm(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).replace(", type_params=[]", "").encode()).hexdigest()


def topology_digests(src):
    tree = reference_tree(src)
    return {n.name: norm(n) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def multi_round_digests(src):
    tree = reference_tree(src)
    out = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == "main":
            removed, body = [], []
            for s in node.body:
                if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name) and s.targets[0].id in {"multi_record", "multi_manifest"}:
                    removed.append(s)
                elif isinstance(s, ast.If) and ast.unparse(s.test) in {"args.multi_round or args.multi_round_manifest", "multi_manifest is not None", "multi_record is not None"}:
                    removed.append(s)
                else:
                    body.append(s)
            assert len(removed) == 5, len(removed)
            node.body = body
        if node.name == "_build_arg_parser":
            node.body = [s for s in node.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
                         and s.value.args and isinstance(s.value.args[0], ast.Constant)
                         and s.value.args[0].value in {"--multi-round", "--multi-round-manifest"})]
        out[node.name] = norm(node)
    return out


def main(reason, document, dry):
    src = (ROOT / "scripts/pipeline.py").read_text(encoding="utf-8")
    plan = {"benchmark/fixtures/multi_round_baseline_contract.json": multi_round_digests(src),
            "benchmark/fixtures/topology_reference_contract.json": topology_digests(src)}
    for rel, actual in plan.items():
        p = ROOT / rel
        raw = p.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        data = json.loads(raw)
        pins = data["function_ast_sha256"]
        functions = {}
        for name in sorted(set(pins) | set(actual)):
            if pins.get(name) != actual.get(name):
                functions[name] = {"from": pins.get(name), "to": actual.get(name)}
        print(rel, json.dumps({k: (v["from"] and v["from"][:8], v["to"] and v["to"][:8]) for k, v in functions.items()}))
        if dry or not functions:
            continue
        for name, ch in functions.items():
            if ch["to"] is None:
                pins.pop(name)
            else:
                pins[name] = ch["to"]
        data["reference_amendments"].append({"date": "2026-10-27", "reason": reason, "document": document, "functions": functions})
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if crlf:
            text = text.replace("\n", "\r\n")
        p.write_bytes(text.encode("utf-8"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], "--dry" in sys.argv)
