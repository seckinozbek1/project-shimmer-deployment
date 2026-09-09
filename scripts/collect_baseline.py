"""Collect a performance and cost baseline from a COMPLETED run (STEP C).

WHY THIS EXISTS. The operator has to run one paid review to establish the
baseline, and the numbers that matter are spread across five files in the run
folder. Gathering them by hand after the fact invites transcription errors and
missed WARNs. This tool reads what a run already wrote and emits one markdown
section, so the baseline is captured correctly the first time.

READ ONLY, ALWAYS. It never starts a run, never deletes anything, and never
writes inside a run directory. Output goes to stdout, and with --write to
docs/PRODUCTIZATION_BASELINE.md. Nothing here calls a provider, loads a model
or spends money.

WHAT IT READS, and what it does when something is absent (it says so, it never
invents a number):

  <run>/status.json                 wall clock, status, exit code (server runs)
  <run>/logs/cost_tracker.json      the aggregate snapshot, quoted in full
  <run>/logs/cost_tracker.jsonl     the per-call event master (call count,
                                    first and last timestamp, failures)
  <run>/logs/*.log                  the captured stderr stream: per-phase
                                    durations come from the structured
                                    JSON-lines events phase_done phase=X
                                    duration_ms=N, and WARN lines come from the
                                    same stream
  <run>/logs/agent_bus.jsonl        bus message count
  <run>/deliverables/               the deliverable inventory with file sizes

USAGE

    python scripts/collect_baseline.py                       # the most recent run
    python scripts/collect_baseline.py --run <run_dir>
    python scripts/collect_baseline.py --run <dir_a> --compare <dir_b>
    python scripts/collect_baseline.py --run <dir_a> --compare <dir_b> --write

The comparison form is the point of the exercise: the baseline is TWO runs, one
at --max-concurrent-docs 4 and one at 1 (see docs/BASELINE_INSTRUCTIONS.md).

Exit codes: 0 a section was produced, 2 the run directory is missing or
unreadable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_context as run_context_mod  # noqa: E402  (after the sys.path insert)

BASELINE_DOC = ROOT / "docs" / "PRODUCTIZATION_BASELINE.md"

# The structured logging events this tool reads (scripts/shimmer_logging.py).
_PHASE_DONE_RE = re.compile(r"phase_done phase=(?P<phase>\S+) duration_ms=(?P<ms>\d+)")
# Peak memory is NOT emitted by any current code path. If a future log line
# carries it, these are the shapes this tool will pick up; until then it says so
# out loud rather than guessing (see _memory_section).
_PEAK_RAM_RE = re.compile(r"peak_ram_mb=(?P<mb>[0-9.]+)")
_PEAK_VRAM_RE = re.compile(r"peak_vram_mb=(?P<mb>[0-9.]+)")

_WARN_RE = re.compile(r"\bWARN(?:ING)?\b|\"level\": \"WARNING\"")
_FAIL_RE = re.compile(r"\bBLOCK(?:ED)?\b|\bSTOP\b|\bfailed\b|\bFAILED\b|\berror\b|\bERROR\b")

_MEMORY_CAPTURE_HINT = (
    "nvidia-smi --query-gpu=memory.used --format=csv -l 5 > <run>/logs/vram.csv\n"
    "typeperf \"\\Process(python)\\Working Set Peak\" -si 5 -o <run>/logs/ram.csv"
)


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n / 1.0:.1f} {unit}"
        n = n / 1024.0
    return f"{n} B"


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _iter_jsonl(path: Path):
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _log_files(run_dir: Path):
    logs = run_dir / "logs"
    if not logs.is_dir():
        return []
    return sorted(p for p in logs.glob("*.log") if p.is_file())


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def gather(run_dir) -> dict:
    """Every number this tool reports, gathered from one run directory. Pure
    read: the returned dict is the only thing produced."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise NotADirectoryError(f"run directory not found: {run_dir}")

    status = _read_json(run_dir / "status.json") or {}
    cost = _read_json(run_dir / "logs" / "cost_tracker.json") or {}
    events = list(_iter_jsonl(run_dir / "logs" / "cost_tracker.jsonl"))

    # Wall clock, best available source, named so the reader knows which.
    started = _parse_iso(status.get("started_at"))
    completed = _parse_iso(status.get("completed_at"))
    wall_source = "status.json (started_at to completed_at)"
    if not (started and completed) and events:
        started = _parse_iso(events[0].get("timestamp"))
        completed = _parse_iso(events[-1].get("timestamp"))
        wall_source = "cost_tracker.jsonl (first to last call timestamp)"
    wall_seconds = (completed - started).total_seconds() if (started and completed) else None
    if wall_seconds is None:
        wall_source = "NOT CAPTURED"

    # Per-phase durations from the structured log, plus WARN and failure lines.
    phases, warns, failures = [], [], []
    peak_ram = peak_vram = None
    for log_path in _log_files(run_dir):
        text = log_path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            m = _PHASE_DONE_RE.search(line)
            if m:
                phases.append((m.group("phase"), int(m.group("ms"))))
            if _PEAK_RAM_RE.search(line):
                peak_ram = float(_PEAK_RAM_RE.search(line).group("mb"))
            if _PEAK_VRAM_RE.search(line):
                peak_vram = float(_PEAK_VRAM_RE.search(line).group("mb"))
            if _WARN_RE.search(line):
                warns.append(f"{log_path.name}: {line.strip()[:220]}")
            elif _FAIL_RE.search(line):
                failures.append(f"{log_path.name}: {line.strip()[:220]}")

    bus_lines = sum(1 for _ in _iter_jsonl(run_dir / "logs" / "agent_bus.jsonl"))

    deliverables = []
    deliv_dir = run_dir / "deliverables"
    if deliv_dir.is_dir():
        for path in sorted(p for p in deliv_dir.rglob("*") if p.is_file()):
            deliverables.append((path.relative_to(deliv_dir).as_posix(),
                                 path.stat().st_size))

    return {
        "run_dir": str(run_dir),
        "run_name": run_dir.name,
        "status": status.get("status", "not recorded (no status.json; a CLI run)"),
        "exit_code": status.get("exit_code", "not recorded"),
        "task": status.get("task", "not recorded"),
        "wall_seconds": wall_seconds,
        "wall_source": wall_source,
        "phases": phases,
        "cost": cost,
        "call_count": len(events),
        "call_failures": sum(1 for e in events if e.get("ok") is False),
        "bus_lines": bus_lines,
        "deliverables": deliverables,
        "warns": warns,
        "failures": failures,
        "peak_ram_mb": peak_ram,
        "peak_vram_mb": peak_vram,
        "log_files": [p.name for p in _log_files(run_dir)],
    }


def _memory_section(data: dict) -> str:
    if data["peak_ram_mb"] is None and data["peak_vram_mb"] is None:
        return ("**Peak RAM and VRAM: NOT CAPTURED.** No log line in this run carries "
                "them, and this tool does NOT sample the current machine, which is not "
                "the machine state that ran the review. Capture them by running these "
                "two samplers in their own terminals ALONGSIDE the review, then re-read "
                "the CSVs (see docs/BASELINE_INSTRUCTIONS.md section 1):\n\n"
                "```\n" + _MEMORY_CAPTURE_HINT + "\n```\n")
    parts = []
    if data["peak_ram_mb"] is not None:
        parts.append(f"peak RAM {data['peak_ram_mb']:.1f} MB")
    else:
        parts.append("peak RAM NOT CAPTURED")
    if data["peak_vram_mb"] is not None:
        parts.append(f"peak VRAM {data['peak_vram_mb']:.1f} MB")
    else:
        parts.append("peak VRAM NOT CAPTURED")
    return "**Memory:** " + ", ".join(parts) + " (read from this run's own logs).\n"


def render(data: dict) -> str:
    """One markdown section for one run."""
    out = []
    a = out.append
    a(f"## Baseline: `{data['run_name']}`")
    a("")
    a(f"- Run directory: `{data['run_dir']}`")
    a(f"- Task: {data['task']}    Status: {data['status']}    "
      f"Exit code: {data['exit_code']}")
    if data["wall_seconds"] is None:
        a("- **Wall clock: NOT CAPTURED** (no status.json timestamps and no cost events)")
    else:
        a(f"- Wall clock: **{data['wall_seconds']:.1f} s** "
          f"({data['wall_seconds'] / 60.0:.1f} min), source: {data['wall_source']}")
    a(f"- Model calls: {data['call_count']}    Failed calls: {data['call_failures']}")
    a(f"- Bus messages: {data['bus_lines']}")
    a(f"- Log files read: {', '.join(data['log_files']) or 'NONE FOUND'}")
    a("")

    a("### Per-phase durations")
    a("")
    if data["phases"]:
        total_ms = sum(ms for _, ms in data["phases"])
        a("| phase | duration (s) | share of phase time |")
        a("|---|---|---|")
        for phase, ms in data["phases"]:
            share = (ms / total_ms * 100.0) if total_ms else 0.0
            a(f"| {phase} | {ms / 1000.0:.1f} | {share:.1f}% |")
        a(f"| **total** | **{total_ms / 1000.0:.1f}** | 100.0% |")
    else:
        a("**NOT CAPTURED.** No `phase_done` event was found in any "
          "`<run>/logs/*.log`. The structured log goes to stderr: a server-driven run "
          "captures it to `pipeline_stdout.log`, and a CLI run captures it only if the "
          "operator redirects stderr into the run folder "
          "(see docs/BASELINE_INSTRUCTIONS.md).")
    a("")

    a("### Cost")
    a("")
    cost = data["cost"]
    if not cost:
        a("**NOT CAPTURED.** No `<run>/logs/cost_tracker.json`.")
    else:
        a(f"- Total: **${cost.get('total_cost_usd', 0):.4f}** over "
          f"{cost.get('total_calls', 0)} call(s), "
          f"{cost.get('total_failures', 0)} failure(s)")
        for label, key in (("family", "by_family"), ("agent", "by_agent"),
                           ("phase", "by_phase"), ("document", "by_doc")):
            table = cost.get(key) or {}
            if not table:
                continue
            a("")
            a(f"Cost by {label}:")
            a("")
            a(f"| {label} | calls | input tokens | output tokens | cost (USD) |")
            a("|---|---|---|---|---|")
            for name, row in sorted(table.items(),
                                    key=lambda kv: -float(kv[1].get("cost_usd", 0) or 0)):
                shown = name if name else "(unattributed)"
                a(f"| {shown} | {row.get('calls', 0)} | {row.get('input_tokens', 0)} | "
                  f"{row.get('output_tokens', 0)} | {float(row.get('cost_usd', 0) or 0):.4f} |")
        a("")
        a("<details><summary>cost_tracker.json in full</summary>")
        a("")
        a("```json")
        a(json.dumps(cost, indent=2, ensure_ascii=False))
        a("```")
        a("")
        a("</details>")
    a("")

    a("### Memory")
    a("")
    a(_memory_section(data))

    a("### Deliverables")
    a("")
    if data["deliverables"]:
        a("| file | size |")
        a("|---|---|")
        for rel, size in data["deliverables"]:
            a(f"| `{rel}` | {_human_bytes(size)} |")
        total = sum(size for _, size in data["deliverables"])
        a(f"| **{len(data['deliverables'])} file(s)** | **{_human_bytes(total)}** |")
    else:
        a("**NONE FOUND** under `<run>/deliverables/`.")
    a("")

    a("### WARN and failure lines")
    a("")
    if not data["warns"] and not data["failures"]:
        a("None found in the captured logs.")
    for line in data["warns"]:
        a(f"- WARN: `{line}`")
    for line in data["failures"]:
        a(f"- FAILURE-SHAPED: `{line}`")
    a("")
    return "\n".join(out)


def render_comparison(a_data: dict, b_data: dict) -> str:
    """Side by side, because the baseline is two runs (concurrency 4 versus 1)."""
    def cell(data, key, fmt="{}"):
        value = data.get(key)
        return "NOT CAPTURED" if value is None else fmt.format(value)

    rows = [
        ("run", f"`{a_data['run_name']}`", f"`{b_data['run_name']}`"),
        ("wall clock (s)", cell(a_data, "wall_seconds", "{:.1f}"),
         cell(b_data, "wall_seconds", "{:.1f}")),
        ("model calls", str(a_data["call_count"]), str(b_data["call_count"])),
        ("failed calls", str(a_data["call_failures"]), str(b_data["call_failures"])),
        ("total cost (USD)",
         f"{float(a_data['cost'].get('total_cost_usd', 0) or 0):.4f}",
         f"{float(b_data['cost'].get('total_cost_usd', 0) or 0):.4f}"),
        ("bus messages", str(a_data["bus_lines"]), str(b_data["bus_lines"])),
        ("deliverable files", str(len(a_data["deliverables"])),
         str(len(b_data["deliverables"]))),
        ("phase events", str(len(a_data["phases"])), str(len(b_data["phases"]))),
        ("WARN lines", str(len(a_data["warns"])), str(len(b_data["warns"]))),
    ]
    out = ["## Comparison", "", "| metric | run A | run B |", "|---|---|---|"]
    for name, av, bv in rows:
        out.append(f"| {name} | {av} | {bv} |")

    aw, bw = a_data["wall_seconds"], b_data["wall_seconds"]
    ac = float(a_data["cost"].get("total_cost_usd", 0) or 0)
    bc = float(b_data["cost"].get("total_cost_usd", 0) or 0)
    out.append("")
    if aw and bw:
        out.append(f"- Wall clock: run B is {bw / aw:.2f}x run A "
                   f"({bw - aw:+.1f} s).")
    else:
        out.append("- Wall clock: NOT CAPTURED for at least one run, so no ratio.")
    if ac and bc:
        out.append(f"- Cost: run B is {bc / ac:.2f}x run A (${bc - ac:+.4f}).")
    else:
        out.append("- Cost: NOT CAPTURED for at least one run, so no ratio.")
    out.append("")
    return "\n".join(out)


def build_report(run_dir, compare_dir=None) -> str:
    a_data = gather(run_dir)
    sections = [f"# Productization baseline\n",
                f"Collected {datetime.now().isoformat(timespec='seconds')} by "
                f"`scripts/collect_baseline.py` (read only).\n",
                render(a_data)]
    if compare_dir:
        b_data = gather(compare_dir)
        sections.append(render(b_data))
        sections.append(render_comparison(a_data, b_data))
    return "\n".join(sections)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect a performance and cost baseline from a completed run. "
                    "Reads only; never starts a run and never writes inside one.")
    parser.add_argument("--run", metavar="RUN_DIR", default=None,
                        help="the run directory. Defaults to the most recent run under "
                             "output/runs/.")
    parser.add_argument("--compare", metavar="RUN_DIR", default=None,
                        help="a second run directory, for the side-by-side comparison "
                             "(the baseline is two runs: --max-concurrent-docs 4 and 1).")
    parser.add_argument("--write", action="store_true",
                        help=f"also write the report to {BASELINE_DOC.relative_to(ROOT).as_posix()}")
    parser.add_argument("--project-root", default=str(ROOT),
                        help="the repository whose output/runs/ to search when --run is "
                             "omitted. The gate check points this at a temp tree.")
    return parser


def main(argv=None) -> int:
    args = _build_arg_parser().parse_args(argv)
    run_dir = args.run
    if run_dir is None:
        ctx = run_context_mod.latest_run(Path(args.project_root))
        if ctx is None:
            print("No run found under output/runs/ and no --run given.", file=sys.stderr)
            return 2
        run_dir = ctx.run_dir
        print(f"[baseline] using the most recent run: {run_dir}", file=sys.stderr)
    try:
        report = build_report(run_dir, args.compare)
    except (NotADirectoryError, OSError) as e:
        print(f"[baseline] cannot read the run: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    print(report)
    if args.write:
        BASELINE_DOC.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_DOC.write_text(report, encoding="utf-8")
        print(f"[baseline] written to {BASELINE_DOC}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
