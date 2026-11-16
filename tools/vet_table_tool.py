"""Vet a table tool before the operator approves it (D-681 item 7, docs/loop/stages/TABLE_TOOL_DESIGN.md).

    py -3.12 -X utf8 tools/vet_table_tool.py                 vet every entry, print the results
    py -3.12 -X utf8 tools/vet_table_tool.py --name ratio    vet one entry
    py -3.12 -X utf8 tools/vet_table_tool.py --write         write each entry's `vetting` (operator only)

Each entry of config/table_tools.json is vetted as code, never by reading it:
  1. its license is on the operator's `license_allowlist`, and its source is `shimmer` or a
     package pinned by its wheel's SHA-256;
  2. it runs with no network, the product rule (D-694 item 3 a: when Shimmer runs as a product,
     no tool sends anything to the internet, no web search, no lookup, not even a masked or
     anonymised query; a tool computes only on what is already inside Shimmer's own run): in a
     fresh process an audit hook refuses every socket event, and any socket event the tool raises
     fails it, even one it catches;
  3. it writes no file: the same hook refuses an open for writing and every file-system change,
     and the process's empty working folder must stay empty;
  4. it is deterministic: two fresh processes with different hash seeds give the same output;
  5. every declared example passes (its expected output, or its declared refusal).
Passing writes `vetting` = {sha256 of the declaration and its source module (tool_registry.
vetted_sha256), result "passed"}. At boot, tool_registry.entry_refusals refuses an entry whose
digest does not match or that names no approving decision. Blocking sockets is not a sandbox:
a third-party tool is vetted at registration with its wheel pinned, and read before it is added.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import tool_registry  # noqa: E402
from cloud_run_common import no_window  # noqa: E402

SEEDS = ("1", "2")
# The child: one tool's examples under an audit hook that refuses the network and every write.
CHILD = r'''
import importlib, json, os, sys
job = json.loads(sys.stdin.read())
for p in job["paths"]:
    sys.path.insert(0, p)
blocked = []
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
CHANGES = ("os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.symlink", "os.link", "os.truncate", "os.chmod",
           "shutil.", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "subprocess.", "os.startfile")
def hook(event, args):
    if event.startswith("socket."):
        blocked.append("socket")
        raise PermissionError("vetting: no network")
    if event == "open":
        mode, flags = (args[1] if len(args) > 1 else None), (args[2] if len(args) > 2 else 0)
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & WRITE_FLAGS):
            blocked.append("write")
            raise PermissionError("vetting: no file written")
    if event.startswith(CHANGES):
        blocked.append("write")
        raise PermissionError("vetting: no file changed")
sys.addaudithook(hook)
out = []
try:
    module, function = job["entry"].split(":", 1)
    fn = getattr(importlib.import_module(module), function)
    for example in job["examples"]:
        try:
            out.append({"value": str(fn(example["context"], *example["args"]))})
        except Exception as exc:
            if type(exc).__name__ == "ToolRefused":
                out.append({"refused": str(exc)})
            else:
                out.append({"error": type(exc).__name__})
except Exception as exc:
    out = [{"error": "import_" + type(exc).__name__}]
sys.stdout.write(json.dumps({"results": out, "blocked": sorted(set(blocked))}, sort_keys=True))
'''


def _child(entry, paths, seed, runner=subprocess.run):
    """One fresh process running the entry's examples: (its parsed output or None, files it left)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env["PYTHONHASHSEED"] = seed
    with tempfile.TemporaryDirectory() as folder:
        job = json.dumps({"paths": [str(p) for p in paths], "entry": entry["entry"], "examples": entry["examples"]})
        done = runner([sys.executable, "-B", "-s", "-c", CHILD], input=job, capture_output=True, text=True,
                      cwd=folder, env=env, timeout=120, creationflags=no_window())
        left = sorted(os.listdir(folder))
    try:
        return json.loads(done.stdout), left
    except ValueError:
        return None, left


def vet(entry, registry, search=None, root=None, runner=subprocess.run):
    """(passed, reasons) for one entry. `search` is a folder a fixture's module lives in."""
    reasons = []
    if not tool_registry.license_allowed(entry, registry):
        reasons.append("license_not_allowed")
    if tool_registry._source_refusal(entry.get("source")):
        reasons.append("source_not_pinned")
    if not tool_registry.approved(entry, registry):
        reasons.append("not_approved")
    examples = entry.get("examples") or []
    if not examples:
        reasons.append("no_examples")
    paths = ([Path(search)] if search else []) + [Path(root or ROOT) / "scripts"]
    runs = [_child(entry, paths, seed, runner) for seed in SEEDS]
    first = runs[0][0]
    if first is None or runs[1][0] is None:
        reasons.append("did_not_run")
    else:
        blocked = set(first["blocked"]) | set(runs[1][0]["blocked"])
        if "socket" in blocked:
            reasons.append("opens_a_socket")
        if "write" in blocked or runs[0][1] or runs[1][1]:
            reasons.append("writes_a_file")
        if first != runs[1][0]:
            reasons.append("not_deterministic")
        for example, got in zip(examples, first["results"]):
            want = {"refused": example["refused"]} if "refused" in example else {"value": example.get("expected")}
            if got != want:
                reasons.append("example_failed")
                break
        if len(first["results"]) != len(examples):
            reasons.append("example_failed")
    return not reasons, sorted(set(reasons))


def vetting_of(entry, registry, search=None, root=None, runner=subprocess.run):
    """The `vetting` value vetting writes: the digest and "passed", or the failure's reasons."""
    passed, reasons = vet(entry, registry, search, root, runner)
    if passed:
        return {"sha256": tool_registry.vetted_sha256(entry, root, search), "result": tool_registry.PASSED,
                "by": "tools/vet_table_tool.py"}
    return {"sha256": None, "result": "failed", "reasons": reasons, "by": "tools/vet_table_tool.py"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vet the table tools of config/table_tools.json")
    parser.add_argument("--name", default=None, help="vet only this entry")
    parser.add_argument("--write", action="store_true", help="write each entry's vetting into the registry")
    args = parser.parse_args(argv)
    path = tool_registry.REGISTRY_PATH
    registry = tool_registry.load(path)
    failed = 0
    for entry in registry.get("tools") or []:
        if args.name and entry.get("name") != args.name:
            continue
        vetting = vetting_of(entry, registry)
        failed += vetting["result"] != tool_registry.PASSED
        print("%s %s %s" % (entry.get("name"), vetting["result"], ",".join(vetting.get("reasons") or [])))
        if args.write:
            entry["vetting"] = vetting
    if args.write:
        path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
