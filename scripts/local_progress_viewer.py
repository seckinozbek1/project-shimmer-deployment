"""Live progress display for local-profile Shimmer runs.

Reads the [progress] and [local-progress] lines pipeline.py already emits to stderr
(nothing here changes what pipeline.py writes; see pipeline.py's local-progress-display
block for the emission side) and renders a redrawing terminal table: one row per agent
(phase, elapsed seconds, which model it uses, whether that call needs a model swap, and
its contract outcome once it lands), a completed/expected total, and the running peak
RAM/VRAM. Read-only: this process never loads a model, never touches CUDA, never imports
torch. It only parses text.

Usage:
    py -3.9 -X utf8 scripts\\local_progress_viewer.py --file <path to a run's stderr log>
    py -3.9 -X utf8 scripts\\pipeline.py ... 2>&1 | py -3.9 -X utf8 scripts\\local_progress_viewer.py

With --file, follows the file like `tail -f`, starting from its CURRENT end (use
--from-start to replay everything already in the file). With no --file, reads stdin.

Scope: shows every agent call pipeline.py's _run_one emits local-progress events for
(corpus-level and per-doc production, the D6 two-pass split, audit, convention review,
AMENDMENT_DRAFTER). The editorial review board and REDACTOR use separate call paths that
do not emit these events yet (stated in pipeline.py's own local-progress block); this
viewer will simply show nothing for them, not a wrong number.
"""
from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import time

if os.name == "nt":
    os.system("")  # enables ANSI escape processing in the Windows console (no-op call)

_PROGRESS_PREFIX = "[progress]"
_LOCAL_PREFIX = "[local-progress]"


def _parse_kv_line(line: str, prefix: str) -> dict | None:
    s = line.strip()
    if not s.startswith(prefix):
        return None
    d = {}
    for tok in s[len(prefix):].split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            d[k] = v
    return d


class RunState:
    def __init__(self):
        self.agents_order: list[str] = []       # stable row order, first-seen
        self.agents: dict[str, dict] = {}        # agent -> row state
        self.completed = 0
        self.expected = 0
        self.peak_ram_gb = 0.0
        self.peak_vram_mb = 0.0
        self.last_event_wall = time.time()
        self.phase_line = ""                     # latest raw [progress] phase/status text

    def apply(self, line: str) -> None:
        local = _parse_kv_line(line, _LOCAL_PREFIX)
        if local is not None:
            self._apply_local(local)
            self.last_event_wall = time.time()
            return
        prog = _parse_kv_line(line, _PROGRESS_PREFIX)
        if prog is not None:
            self.phase_line = " ".join(f"{k}={v}" for k, v in prog.items())
            self.last_event_wall = time.time()

    def _apply_local(self, d: dict) -> None:
        event = d.get("event")
        if "completed" in d and "/" in d["completed"]:
            c, e = d["completed"].split("/", 1)
            try:
                self.completed, self.expected = int(c), int(e)
            except ValueError:
                pass
        if event == "memory":
            try:
                self.peak_ram_gb = float(d.get("peak_ram_gb", self.peak_ram_gb))
            except ValueError:
                pass
            try:
                self.peak_vram_mb = float(d.get("peak_vram_mb", self.peak_vram_mb))
            except ValueError:
                pass
            return
        agent = d.get("agent")
        if not agent:
            return
        if agent not in self.agents:
            self.agents_order.append(agent)
            self.agents[agent] = {}
        row = self.agents[agent]
        if event == "agent_start":
            row["status"] = "running"
            row["phase"] = d.get("phase", "-")
            row["model"] = d.get("model", "-")
            row["swap"] = d.get("swap", "no")
            row["start_monotonic"] = time.monotonic()
            row["outcome"] = ""
            row["items"] = ""
            row["elapsed_s"] = None
        elif event == "agent_done":
            row["status"] = "done"
            row["phase"] = d.get("phase", row.get("phase", "-"))
            row["outcome"] = d.get("outcome", "")
            row["items"] = d.get("items", "")
            try:
                row["elapsed_s"] = float(d.get("elapsed_s", "0"))
            except ValueError:
                row["elapsed_s"] = None

    def row_elapsed(self, agent: str) -> float:
        row = self.agents[agent]
        if row.get("status") == "done" and row.get("elapsed_s") is not None:
            return row["elapsed_s"]
        start = row.get("start_monotonic")
        return (time.monotonic() - start) if start else 0.0


_OUTCOME_LABEL = {
    "violated": "VIOLATED",
    "backend_error": "BACKEND ERROR",
    "held_empty": "held, 0 items",
    "held_n": "held",
    "": "running" ,
}


def _render(state: RunState) -> str:
    lines = []
    lines.append(f"Completed: {state.completed}/{state.expected or '?'}   "
                 f"Peak RAM: {state.peak_ram_gb:.2f} GB   "
                 f"Peak VRAM: {state.peak_vram_mb:.1f} MB")
    if state.phase_line:
        lines.append(f"[progress] {state.phase_line}")
    lines.append("")
    header = f"{'AGENT':<22} {'PHASE':<8} {'ELAPSED':>8}  {'MODEL':<38} {'SWAP':<5} OUTCOME"
    lines.append(header)
    lines.append("-" * len(header))
    if not state.agents_order:
        lines.append("(waiting for the first agent to start...)")
    for agent in state.agents_order:
        row = state.agents[agent]
        elapsed = state.row_elapsed(agent)
        status = row.get("status", "")
        swap_flag = "SWAP" if row.get("swap") == "yes" else "-"
        if status == "running":
            outcome_txt = "running"
        else:
            label = _OUTCOME_LABEL.get(row.get("outcome", ""), row.get("outcome", ""))
            items = row.get("items", "")
            outcome_txt = f"{label} ({items} items)" if row.get("outcome") == "held_n" else label
        model = (row.get("model") or "-")
        if len(model) > 38:
            model = model[:35] + "..."
        lines.append(f"{agent:<22} {row.get('phase', '-'):<8} {elapsed:>7.1f}s  "
                     f"{model:<38} {swap_flag:<5} {outcome_txt}")
    return "\n".join(lines)


def _reader_thread(fh, q: "queue.Queue[str]", follow: bool) -> None:
    while True:
        line = fh.readline()
        if line:
            q.put(line)
            continue
        if not follow:
            q.put(None)  # sentinel: EOF, not following
            return
        time.sleep(0.3)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", help="path to a run's stderr log to follow (like tail -f). "
                                   "Omit to read from stdin instead.")
    ap.add_argument("--from-start", action="store_true",
                    help="with --file, replay the whole file instead of starting at its end")
    ap.add_argument("--refresh", type=float, default=1.0,
                    help="redraw interval in seconds (default 1.0)")
    args = ap.parse_args(argv)

    follow = bool(args.file)
    if args.file:
        fh = open(args.file, "r", encoding="utf-8", errors="replace")
        if not args.from_start:
            fh.seek(0, os.SEEK_END)
    else:
        fh = sys.stdin

    q: "queue.Queue[str | None]" = queue.Queue()
    threading.Thread(target=_reader_thread, args=(fh, q, follow), daemon=True).start()

    state = RunState()
    last_line_count = 0
    stdin_done = False
    try:
        while True:
            drained_any = False
            try:
                while True:
                    item = q.get_nowait()
                    if item is None:
                        stdin_done = True
                        break
                    state.apply(item)
                    drained_any = True
            except queue.Empty:
                pass
            frame = _render(state)
            if last_line_count:
                sys.stdout.write(f"\x1b[{last_line_count}A\x1b[J")
            sys.stdout.write(frame + "\n")
            sys.stdout.flush()
            last_line_count = frame.count("\n") + 1
            if stdin_done and not follow:
                break
            time.sleep(args.refresh)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
