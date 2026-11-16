"""Attribute a cloud launch's billed time to its parts, from the saved run records alone.

Speed plan v1 (docs/loop/stages/SPEED_PLAN_V1.md). The tool reads a collected session folder the
controller wrote (``launch.json``, ``TERMINATION_VERIFIED.json`` or ``cost.json``, every
``*_timing.json`` at the session root and under ``batch/<entry>/``) and, per entry, the workload's own
records (``model_telemetry_summary.json``, ``generation_observation.jsonl``, ``prompt_structure.jsonl``
and the reply records' ``prefill`` block). It writes where the seconds went:

- the session: provider boot (launch request to the first remote phase), setup phases, the phases
  between entries, the workloads, the tail phases, the controller's time between phases, the wait for
  termination, and what is left of the billed time (``unattributed``);
- each workload: time outside the pipeline (process start, admission, model hashing), model loads,
  generation (with its prefill share), and the rest of the pipeline (Python, embedding, scheduling);
- each agent: calls, service seconds, generation and prefill seconds, tokens, cap hits, and the static
  and dynamic prompt characters (the prefix share a prefix cache could reuse).

It changes nothing it reads and runs no model. It prints counts, seconds and US dollars only: no entry
folder name, document id, instance id, call id, prompt or reply text (entries are numbered in folder
order). ``compare`` reads two splits and refuses any pair on different machine types (FACTORS-A,
D-389 ruling 2), so a before and after figure is always one machine type.

    py -3.12 -X utf8 tools/launch_time_split.py split SESSION [SESSION ...] [--out FILE]
    py -3.12 -X utf8 tools/launch_time_split.py compare BEFORE.json AFTER.json [--out FILE]

Proofs: tools/launch_time_split_checks.py (fixtures only; check 445).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = 1
TIMING_SUFFIX = "_timing.json"
# A detached remote phase also writes the timing of its own start and collect steps; they lie inside
# the phase's own interval, so counting them again would count the same seconds twice.
SUB_STEP_ENDINGS = ("_start", "_collect")
WORKLOAD_PHASES = ("batch_workload", "ordinary_workload", "workload")
CATEGORIES = ("provider_boot", "setup", "between_entries", "workload", "tail", "controller_gaps",
              "termination_wait", "unattributed")
WORKLOAD_PARTS = ("outside_pipeline", "model_load", "generation", "pipeline_other")
TELEMETRY = ("analysis/model_telemetry_summary.json",
             "downloaded/evidence/run/audit/model_telemetry_summary.json")
RUN_LOGS = "downloaded/evidence/run/logs"
REPLIES = "downloaded/evidence/run/audit/model_replies"


class SplitError(ValueError):
    """The records cannot be split as asked (a missing record, or a refused comparison)."""


def _load(path: Path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _jsonl(path: Path):
    if not path.is_file():
        return []
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    return rows


def _num(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def phase_base(file_name: str):
    """The phase a timing file times, without its entry index: ('batch_workload', False) for
    'batch_workload_0_timing.json'. The second value is True for a start or collect sub-step."""
    stem = file_name[:-len(TIMING_SUFFIX)] if file_name.endswith(TIMING_SUFFIX) else file_name
    base = re.sub(r"_\d+$", "", stem)
    return base, base.endswith(SUB_STEP_ENDINGS)


def read_phases(session: Path):
    """Every top-level phase of the session in start order: dicts with base, seconds, start, entry."""
    phases = []
    folders = [(None, session)]
    batch = session / "batch"
    if batch.is_dir():
        folders += [(index, folder) for index, folder in
                    enumerate(sorted(p for p in batch.iterdir() if p.is_dir()))]
    for entry, folder in folders:
        for path in sorted(folder.glob("*" + TIMING_SUFFIX)):
            base, sub_step = phase_base(path.name)
            if sub_step:
                continue
            record = _load(path)
            seconds = _num(record.get("seconds"))
            if seconds is None:
                continue
            phases.append({"base": base, "seconds": seconds, "start": _num(record.get("start_epoch")),
                           "entry": entry})
    placed = sorted((p for p in phases if p["start"] is not None), key=lambda p: p["start"])
    unplaced = [p for p in phases if p["start"] is None]
    return placed, unplaced


def _union(intervals):
    total, end = 0.0, None
    for start, stop in sorted(intervals):
        if end is None or start > end:
            total += stop - start
            end = stop
        elif stop > end:
            total += stop - end
            end = stop
    return total


def session_frame(session: Path):
    """Launch epoch, end epoch, billed seconds, machine type and hourly rate from the controller's records."""
    launch = _load(session / "launch.json") if (session / "launch.json").is_file() else {}
    cost = _load(session / "cost.json") if (session / "cost.json").is_file() else {}
    verified = (_load(session / "TERMINATION_VERIFIED.json")
                if (session / "TERMINATION_VERIFIED.json").is_file() else {})
    start = _num(launch.get("epoch")) or _num(cost.get("active_start_epoch"))
    end = _num(verified.get("epoch")) or _num(cost.get("observed_epoch"))
    billed = _num(verified.get("billable_duration_upper_bound_seconds"))
    if billed is None and start is not None and end is not None:
        billed = end - start
    machine = launch.get("instance_type")
    if not machine:
        machine_file = session / "batch_machine_types.json"
        kinds = set(_load(machine_file).values()) if machine_file.is_file() else set()
        machine = kinds.pop() if len(kinds) == 1 else None
    rate = _num(launch.get("hourly_rate")) or _num(cost.get("hourly_rate"))
    if start is None or billed is None or not machine or rate is None:
        raise SplitError("session records incomplete: launch epoch, billed time, machine type and hourly "
                         "rate are all needed")
    return {"start": start, "end": end, "billed": billed, "machine_type": machine, "hourly_rate": rate}


def _telemetry(folder: Path):
    for name in TELEMETRY:
        if (folder / name).is_file():
            return _load(folder / name)
    return None


def model_loads(lifecycle):
    """(seconds, count) of model loads, each load_start paired with the next load_end of its model."""
    opened, seconds, count = {}, 0.0, 0
    for event in sorted(lifecycle or [], key=lambda e: _num(e.get("monotonic_s")) or 0.0):
        name, at = event.get("model"), _num(event.get("monotonic_s"))
        if at is None:
            continue
        if event.get("event") == "model_load_start":
            opened[name] = at
        elif event.get("event") == "model_load_end" and name in opened:
            seconds += at - opened.pop(name)
            count += 1
    return seconds, count


def _agent_row():
    return {"calls": 0, "service_seconds": 0.0, "generation_seconds": 0.0, "prefill_seconds": 0.0,
            "input_tokens": 0, "output_tokens": 0, "cap_hits": 0, "retries": 0, "static_chars": 0,
            "dynamic_chars": 0, "replies": 0, "reply_bytes": 0, "tail_bytes_after_close": 0}


def tail_after_close(text):
    """Bytes after the first complete JSON object of a reply, outer spaces aside; None when no object
    closes. What an early stop on a closed reply could save, counted, never shown."""
    if not isinstance(text, str):
        return None
    start = text.find("{")
    if start < 0:
        return None
    depth, in_string, escaped = 0, False, False
    for position in range(start, len(text)):
        char = text[position]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return len(text[position + 1:].strip().encode("utf-8"))
    return None


def entry_agents(folder: Path, telemetry):
    """Per agent aggregates of one workload, numbers only."""
    agents = {}

    def row(name):
        return agents.setdefault(str(name or "unknown"), _agent_row())

    for name, seconds in ((telemetry or {}).get("per_agent_service") or {}).items():
        if _num(seconds) is not None:
            row(name)["service_seconds"] += _num(seconds)
    for record in _jsonl(folder / RUN_LOGS / "generation_observation.jsonl"):
        generation = _num(record.get("generation_seconds"))
        if generation is None:
            continue
        target = row(record.get("agent"))
        target["calls"] += 1
        target["generation_seconds"] += generation
        target["input_tokens"] += int(_num(record.get("input_tokens")) or 0)
        target["output_tokens"] += int(_num(record.get("output_tokens")) or 0)
        target["cap_hits"] += 1 if record.get("cap_hit") is True else 0
        target["retries"] += int(_num(record.get("retry_count")) or 0)
    for record in _jsonl(folder / RUN_LOGS / "prompt_structure.jsonl"):
        target = row(record.get("agent"))
        target["static_chars"] += int(_num(record.get("static_chars")) or 0)
        target["dynamic_chars"] += int(_num(record.get("dynamic_chars")) or 0)
    replies = folder / REPLIES
    if replies.is_dir():
        for path in sorted(replies.glob("*.json")):
            record = _load(path)
            if not isinstance(record, dict):
                continue
            target = row(record.get("agent"))
            seconds = _num((record.get("prefill") or {}).get("prefill_seconds"))
            if seconds is not None:
                target["prefill_seconds"] += seconds
            text = (record.get("reply") or {}).get("text")
            if isinstance(text, str):
                target["replies"] += 1
                target["reply_bytes"] += len(text.encode("utf-8"))
                target["tail_bytes_after_close"] += tail_after_close(text) or 0
    return agents


def entry_split(index, folder: Path, workload_seconds):
    telemetry = _telemetry(folder)
    if telemetry is None:
        return {"index": index, "workload_seconds": workload_seconds, "telemetry": False}
    wall = _num(telemetry.get("pipeline_wall_seconds")) or 0.0
    load_seconds, load_count = model_loads(telemetry.get("model_lifecycle"))
    generation = _num(telemetry.get("generation_wall_union_seconds")) or 0.0
    outside = max(0.0, (workload_seconds or wall) - wall)
    phases = {}
    for item in telemetry.get("phase_latencies") or []:
        if isinstance(item, dict) and _num(item.get("seconds")) is not None:
            phases[str(item.get("phase"))] = phases.get(str(item.get("phase")), 0.0) + _num(item["seconds"])
    return {
        "index": index, "telemetry": True, "workload_seconds": workload_seconds,
        "pipeline_wall_seconds": wall,
        "parts": {"outside_pipeline": outside, "model_load": load_seconds, "generation": generation,
                  "pipeline_other": max(0.0, wall - load_seconds - generation)},
        "model_loads": load_count, "scheduler_wait_seconds": _num(telemetry.get("scheduler_wait_seconds")),
        "maximum_concurrency": telemetry.get("maximum_concurrency"),
        "pipeline_phases": phases, "agents": entry_agents(folder, telemetry),
    }


def _add_into(total: dict, part: dict):
    for key, value in part.items():
        if isinstance(value, dict):
            _add_into(total.setdefault(key, {}), value)
        elif _num(value) is not None:
            total[key] = total.get(key, 0) + value


def _cat(seconds, billed, rate):
    return {"seconds": round(seconds, 3), "share": round(seconds / billed, 4) if billed else None,
            "usd": round(seconds / 3600.0 * rate, 4)}


def split(session) -> dict:
    """The time split of one collected session folder."""
    session = Path(session)
    frame = session_frame(session)
    placed, unplaced = read_phases(session)
    workloads = [i for i, p in enumerate(placed) if p["base"] in WORKLOAD_PHASES]
    groups = {"setup": [], "between_entries": [], "workload": [], "tail": []}
    for i, phase in enumerate(placed):
        if phase["base"] in WORKLOAD_PHASES:
            groups["workload"].append(phase)
        elif not workloads or i < workloads[0]:
            groups["setup"].append(phase)
        elif i > workloads[-1]:
            groups["tail"].append(phase)
        else:
            groups["between_entries"].append(phase)
    seconds = {name: sum(p["seconds"] for p in group) for name, group in groups.items()}
    if placed:
        first = placed[0]["start"]
        last = max(p["start"] + p["seconds"] for p in placed)
        covered = _union([(p["start"], p["start"] + p["seconds"]) for p in placed])
        seconds["provider_boot"] = max(0.0, first - frame["start"])
        seconds["controller_gaps"] = max(0.0, (last - first) - covered)
        seconds["termination_wait"] = max(0.0, frame["end"] - last) if frame["end"] is not None else 0.0
        overlap = sum(p["seconds"] for p in placed) - covered
    else:
        seconds.update(provider_boot=0.0, controller_gaps=0.0, termination_wait=0.0)
        overlap = 0.0
    seconds["unattributed"] = frame["billed"] - sum(seconds[c] for c in CATEGORIES if c != "unattributed")
    billed, rate = frame["billed"], frame["hourly_rate"]

    def by_base(group):
        out = {}
        for phase in group:
            out[phase["base"]] = round(out.get(phase["base"], 0.0) + phase["seconds"], 3)
        return out

    entry_folders = sorted(p for p in (session / "batch").iterdir() if p.is_dir()) \
        if (session / "batch").is_dir() else [session]
    workload_by_entry = {}
    for phase in groups["workload"]:
        key = phase["entry"] if phase["entry"] is not None else 0
        workload_by_entry[key] = workload_by_entry.get(key, 0.0) + phase["seconds"]
    entries = [entry_split(i, folder, workload_by_entry.get(i)) for i, folder in enumerate(entry_folders)]
    parts, agents = {}, {}
    for entry in entries:
        if entry.get("telemetry"):
            _add_into(parts, entry["parts"])
            _add_into(agents, entry["agents"])
    return {
        "schema": SCHEMA, "sessions": 1, "machine_type": frame["machine_type"], "hourly_rate": rate,
        "billed_seconds": round(billed, 3), "usd": round(billed / 3600.0 * rate, 4),
        "categories": {c: _cat(seconds[c], billed, rate) for c in CATEGORIES},
        "setup_phases": by_base(groups["setup"]), "between_entry_phases": by_base(groups["between_entries"]),
        "tail_phases": by_base(groups["tail"]),
        "unplaced_phases": by_base(unplaced), "phase_overlap_seconds": round(max(0.0, overlap), 3),
        "entries": entries, "entry_count": len(entries),
        "workload_parts": {k: round(parts.get(k, 0.0), 3) for k in WORKLOAD_PARTS},
        "agents": agents,
    }


def same_machine(first: dict, second: dict) -> bool:
    """FACTORS-A: two figures are put side by side only when they ran on one machine type."""
    return bool(first.get("machine_type")) and first.get("machine_type") == second.get("machine_type")


def aggregate(splits) -> dict:
    """Several sessions' splits summed; every one on one machine type, or refused (FACTORS-A)."""
    splits = list(splits)
    if not splits:
        raise SplitError("nothing to aggregate")
    if not all(same_machine(splits[0], s) for s in splits):
        raise SplitError("refused: sessions on different machine types are never summed (FACTORS-A)")
    if len(splits) == 1:
        return splits[0]
    billed = sum(s["billed_seconds"] for s in splits)
    usd = sum(s["usd"] for s in splits)
    rate = usd * 3600.0 / billed if billed else splits[0]["hourly_rate"]
    total = {"schema": SCHEMA, "sessions": len(splits), "machine_type": splits[0]["machine_type"], "hourly_rate": round(rate, 4),
             "billed_seconds": round(billed, 3), "usd": round(usd, 4), "entry_count": 0, "categories": {},
             "setup_phases": {}, "between_entry_phases": {}, "tail_phases": {}, "unplaced_phases": {},
             "phase_overlap_seconds": 0.0, "workload_parts": {}, "agents": {}, "entries": []}
    for s in splits:
        total["entry_count"] += s["entry_count"]
        total["phase_overlap_seconds"] += s["phase_overlap_seconds"]
        for key in ("setup_phases", "between_entry_phases", "tail_phases", "unplaced_phases",
                    "workload_parts", "agents"):
            _add_into(total[key], s[key])
        for name, cat in s["categories"].items():
            total["categories"].setdefault(name, {"seconds": 0.0, "usd": 0.0})
            total["categories"][name]["seconds"] += cat["seconds"]
            total["categories"][name]["usd"] += cat["usd"]
        offset = len(total["entries"])
        total["entries"] += [dict(e, index=offset + e["index"]) for e in s["entries"]]
    for cat in total["categories"].values():
        cat["share"] = round(cat["seconds"] / billed, 4) if billed else None
    return total


def compare(before: dict, after: dict) -> dict:
    """After minus before, per category, workload part and agent; refused across machine types."""
    if not same_machine(before, after):
        raise SplitError("refused: a before and after pair on different machine types is never compared "
                         "(FACTORS-A, D-389 ruling 2)")
    out = {"schema": SCHEMA, "machine_type": before["machine_type"],
           "entry_count": [before.get("entry_count"), after.get("entry_count")],
           "billed_seconds": round(after["billed_seconds"] - before["billed_seconds"], 3),
           "usd": round(after["usd"] - before["usd"], 4), "categories": {}, "workload_parts": {}, "agents": {}}
    for name in CATEGORIES:
        a = (after["categories"].get(name) or {}).get("seconds", 0.0)
        b = (before["categories"].get(name) or {}).get("seconds", 0.0)
        out["categories"][name] = round(a - b, 3)
    for name in WORKLOAD_PARTS:
        out["workload_parts"][name] = round(after["workload_parts"].get(name, 0.0)
                                            - before["workload_parts"].get(name, 0.0), 3)
    for name in sorted(set(before["agents"]) | set(after["agents"])):
        a, b = after["agents"].get(name, {}), before["agents"].get(name, {})
        out["agents"][name] = {k: round(a.get(k, 0) - b.get(k, 0), 3)
                               for k in ("calls", "service_seconds", "generation_seconds", "prefill_seconds")}
    if before.get("entry_count") != after.get("entry_count"):
        out["note"] = "entry counts differ; per-entry figures are not comparable"
    return out


def render(result: dict) -> str:
    """A plain table of a split (or an aggregate): category, seconds, share, USD; then the workload parts."""
    lines = ["machine %s, %d session(s), %d entries, billed %.0f s, %.2f USD" % (
        result["machine_type"], result.get("sessions", 1), result.get("entry_count", 0),
        result["billed_seconds"], result["usd"])]
    for name in CATEGORIES:
        cat = result["categories"].get(name, {})
        lines.append("  %-18s %9.1f s  %5.1f%%  %6.3f USD" % (
            name, cat.get("seconds", 0.0), 100.0 * (cat.get("share") or 0.0), cat.get("usd", 0.0)))
    parts = result.get("workload_parts", {})
    lines.append("  workload parts: " + ", ".join("%s %.1f s" % (k, parts.get(k, 0.0)) for k in WORKLOAD_PARTS))
    agents = result.get("agents", {})
    for name in sorted(agents, key=lambda n: -agents[n].get("service_seconds", 0.0)):
        a = agents[name]
        out_tokens = a.get("output_tokens", 0)
        decode = a.get("generation_seconds", 0.0) - a.get("prefill_seconds", 0.0)
        lines.append("    %-18s service %7.1f s, calls %3d, generation %7.1f s, prefill %6.1f s, "
                     "in %7d tok, out %6d tok (%s tok/s decode), cap %d, static %d of %d chars, "
                     "tail after close %d of %d bytes" % (
                         name, a.get("service_seconds", 0.0), a.get("calls", 0), a.get("generation_seconds", 0.0),
                         a.get("prefill_seconds", 0.0), a.get("input_tokens", 0), out_tokens,
                         "%.1f" % (out_tokens / decode) if decode > 0 and out_tokens else "-",
                         a.get("cap_hits", 0), a.get("static_chars", 0),
                         a.get("static_chars", 0) + a.get("dynamic_chars", 0),
                         a.get("tail_bytes_after_close", 0), a.get("reply_bytes", 0)))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("split", help="split one or more collected session folders")
    one.add_argument("sessions", nargs="+")
    one.add_argument("--out")
    two = sub.add_parser("compare", help="after minus before, one machine type only")
    two.add_argument("before")
    two.add_argument("after")
    two.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        if args.command == "split":
            result = aggregate(split(s) for s in args.sessions)
            text = render(result)
        else:
            result = compare(_load(Path(args.before)), _load(Path(args.after)))
            text = json.dumps(result, indent=1, sort_keys=True)
    except SplitError as exc:
        print(str(exc))
        return 2
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
