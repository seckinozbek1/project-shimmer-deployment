"""The GPU-release development run, read (#297, D-694 item 1): did the resident vLLM server hand the card back
before every transformers load, and did every entry reach its end? Counts, seconds and bytes only, from each run
folder's saved telemetry and completion record; no text. No model and no provider.

    py -3.12 -X utf8 tools/gpu_release_read.py --out OUT.json RUN_DIR [RUN_DIR ...]

RUN_DIR is one entry's run folder (audit/run_completion.json, logs/model_telemetry.jsonl). Per entry:
- the end: state, reached_end, exit_code (audit/run_completion.json);
- the calls: backend invocations by engine (`usage.engine` "vllm" for a routed call, else transformers), each
  engine's failures by category;
- the hand-backs: `vllm_server_yield` events (scripts/vllm_link.YIELD_EVENT), their requests and close seconds;
- the loads: every model_load_start and whether a model_load_end followed it; a load that started after a
  routed call with no hand-back between them is counted (`load_without_handback`);
- the server starts: the distinct `attention.server_start` numbers on routed reply records (audit/model_replies)
  and their `start_seconds` (OPEN_ITEMS 115: each change back to a routed agent costs one start);
- the card: the highest memory any GPU showed in resource_sample, in MiB.
The run's bar, written before it: every entry completed with reached_end true and exit 0; no failed routed
call; at least one hand-back in an entry that routed a call and then loaded a model; no load without its end
and no load without a hand-back. A line not met is named, with its count. Standard library only.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

SCHEMA = "gpu-release-read-v1"
YIELD_EVENT = "vllm_server_yield"   # scripts/vllm_link.YIELD_EVENT, held equal by check 488
VLLM = "vllm"


def _events(run_dir):
    path = Path(run_dir) / "logs" / "model_telemetry.jsonl"
    rows = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    rows.append({"event": "unreadable_line"})
    return rows


def server_starts(run_dir):
    """{start number: start seconds} over the routed reply records of a run folder."""
    starts = {}
    folder = Path(run_dir) / "audit" / "model_replies"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            attention = json.loads(path.read_text(encoding="utf-8")).get("attention") or {}
        except (OSError, ValueError):
            continue
        if attention.get("engine") == VLLM and attention.get("server_start") is not None:
            starts[str(attention["server_start"])] = attention.get("start_seconds")
    return starts


def read_entry(run_dir):
    run_dir = Path(run_dir)
    completion_path = run_dir / "audit" / "run_completion.json"
    completion = json.loads(completion_path.read_text(encoding="utf-8")) if completion_path.is_file() else {}
    calls = {"vllm": Counter(), "transformers": Counter()}
    failures = {"vllm": Counter(), "transformers": Counter()}
    yields, loads_open, loads, ended, without = [], {}, 0, 0, 0
    routed_since_yield, routed_any, loaded_after_route = False, False, False
    peak = 0.0
    starts = server_starts(run_dir)
    for e in _events(run_dir):
        kind = e.get("event")
        if kind == "backend_invocation":
            engine = VLLM if ((e.get("usage") or {}).get("engine") == VLLM) else "transformers"
            calls[engine][e.get("agent") or "?"] += 1
            if not e.get("backend_success", False):
                failures[engine][e.get("failure_category") or "unknown"] += 1
            if engine == VLLM:
                routed_since_yield = routed_any = True
        elif kind == YIELD_EVENT:
            yields.append({"requests": e.get("requests"), "close_seconds": e.get("close_seconds"),
                           "start_number": e.get("start_number")})
            routed_since_yield = False
        elif kind == "model_load_start":
            loads += 1
            loads_open[e.get("model")] = loads_open.get(e.get("model"), 0) + 1
            if routed_since_yield:
                without += 1
            if routed_any:
                loaded_after_route = True
        elif kind == "model_load_end":
            if loads_open.get(e.get("model")):
                loads_open[e.get("model")] -= 1
                ended += 1
        elif kind == "resource_sample":
            for gpu in e.get("gpus") or []:
                peak = max(peak, float(gpu.get("memory_mib") or 0))
    return {"state": completion.get("state"), "reached_end": completion.get("reached_end"),
            "exit_code": completion.get("exit_code"),
            "calls": {k: sum(v.values()) for k, v in calls.items()},
            "calls_by_agent": {k: dict(v) for k, v in calls.items()},
            "failures": {k: dict(v) for k, v in failures.items()},
            "handbacks": len(yields), "handback_requests": sum(int(y["requests"] or 0) for y in yields),
            "handback_close_seconds_max": max([float(y["close_seconds"] or 0) for y in yields], default=None),
            "loads": loads, "loads_ended": ended, "load_without_end": loads - ended,
            "load_without_handback": without, "loaded_after_route": loaded_after_route,
            "peak_gpu_memory_mib": peak, "server_starts": len(starts),
            "server_start_seconds_sum": round(sum(float(v or 0) for v in starts.values()), 3) if starts else None}


def completed(entry):
    """An entry that ran to its end: state completed, reached_end true, exit code 0."""
    return entry["state"] == "completed" and entry["reached_end"] is True and entry["exit_code"] == 0


def bar(entries):
    def line(text, count):
        return {"line": text, "count": count, "met": count == 0}
    return [
        line("every entry completed, reached its end, exit 0",
             sum(1 for e in entries if not completed(e))),
        line("no failed routed call", sum(sum(e["failures"]["vllm"].values()) for e in entries)),
        line("a hand-back in every entry that routed a call and then loaded a model",
             sum(1 for e in entries if e["loaded_after_route"] and e["handbacks"] == 0)),
        line("no load without its end", sum(e["load_without_end"] for e in entries)),
        line("no load after a routed call without a hand-back between", sum(e["load_without_handback"] for e in entries)),
        line("at least one routed call in the run", 0 if any(e["calls"]["vllm"] for e in entries) else 1),
    ]


def read(run_dirs):
    entries = [read_entry(r) for r in run_dirs]
    lines = bar(entries)
    return {"schema": SCHEMA, "entries": len(entries), "per_entry": entries, "bar": {"lines": lines,
            "met": all(l["met"] for l in lines)},
            "peak_gpu_memory_mib": max([e["peak_gpu_memory_mib"] for e in entries], default=None),
            "reads": "telemetry and completion records only; counts, seconds and bytes"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("runs", nargs="+", type=Path)
    args = parser.parse_args(argv)
    value = read(args.runs)
    args.out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"entries": value["entries"], "bar_met": value["bar"]["met"]}))
    return 0 if value["bar"]["met"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
