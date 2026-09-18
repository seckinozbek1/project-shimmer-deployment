"""Native chat interface for Project Shimmer (menu option [2]).

A lightweight standalone tkinter window where the operator types instructions and
the pipeline executes them. When the local Qwen model is available, plain-language
instructions are parsed into structured commands; otherwise the window falls back
to a simple command mode. Dark, minimal, functional. Stateless across sessions.

Design notes:
  - Qwen parsing reuses agent_wrapper._load_qwen directly with the REDACTOR's
    registry model id (no full AgentWrapper construction). The model load and the
    generate call run on a background thread so the UI never blocks.
  - The intake wizard (scripts/intake_wizard.py) is driven as a SUBPROCESS with a
    fed stdin answer sequence, so its input() prompts never block the GUI thread.
  - The pipeline (scripts/pipeline.py) is run as a subprocess; its stdout/stderr
    is streamed line by line into the chat via root.after() (thread-safe tkinter).
  - Post-run Q&A is a deterministic text search over the latest run's bus log at
    output/runs/<run_id>/logs/agent_bus.jsonl (no model call).

This module is domain-agnostic: no domain vocabulary, no hardcoded absolute paths,
no key values are ever displayed or logged.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import tkinter as tk

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PIPELINE = SCRIPTS / "pipeline.py"
WIZARD = SCRIPTS / "intake_wizard.py"
SCOPE_PATH = ROOT / "config" / "review_scope.json"
REGISTRY_PATH = ROOT / "config" / "agent_registry.json"
RUNS_ROOT = ROOT / "output" / "runs"

# Dark theme.
BG = "#1e1e1e"
FG = "#e0e0e0"
ENTRY_BG = "#2d2d2d"
BTN_BG = "#3a3a3a"
FONT = ("Consolas", 10)

CONVENTION_NAMES = {"review_conventions.md", "review_mandate.md"}

QWEN_SYSTEM_PROMPT = (
    "You are a command parser for a document review system. Parse the user's "
    "instruction into a JSON object. Valid actions: review, draft, import, "
    "set_cutoff, set_mode, status, help, quit. For 'draft' (the user asks you to "
    "write or draft a memo), put the topic in a 'question' field. Extract any paths, "
    "dates, mode (normal/sensitive), numbers. Return ONLY valid JSON, no other text."
)

HELP_TEXT = (
    "I can run and inspect document reviews. Things you can say:\n"
    "  review <folder>          set up the documents in <folder> and run a review\n"
    "  draft a memo on <topic>  generate a memo from the grounding, then review it\n"
    "  import <folder>          set up the documents only, no run\n"
    "  set cutoff <YYYY-MM-DD>  change the date cutoff\n"
    "  normal mode              redaction off for the next run (full output)\n"
    "  sensitive mode           redaction on for the next run\n"
    "  status                   show the current cutoff, mode, and documents\n"
    "  why did you flag <term>  search the latest run for a finding\n"
    "  help                     show this list\n"
    "  quit                     close the window\n"
    "When a local AI model is available you can also just describe what you want in\n"
    "plain language and I will work out the command."
)

_STOPWORDS = {
    "why", "did", "you", "flag", "flagged", "the", "a", "an", "is", "was", "for",
    "about", "me", "explain", "reason", "on", "in", "of", "to", "this", "that",
}


# --- pure helpers (no GUI; unit-testable) --------------------------------------

def redactor_model_id() -> "str | None":
    """The REDACTOR's model id from the registry (the qwen_local backend)."""
    try:
        reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    red = (reg.get("agents") or {}).get("REDACTOR") or {}
    return red.get("model")


def extract_json(s: str) -> "dict | None":
    """Pull the first balanced {...} object out of a string and parse it."""
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(s[start:i + 1])
                except json.JSONDecodeError:
                    return None
                return obj if isinstance(obj, dict) else None
    return None


def valid_date(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def _first_path(s: str) -> str:
    for tok in s.strip().split():
        if not tok.startswith("--"):
            return tok
    return ""


def _extract_mode(low: str) -> str:
    return "sensitive" if "sensitive" in low else "normal"


def _extract_flag_int(low: str, flag: str) -> "int | None":
    m = re.search(re.escape(flag) + r"\s+(\d+)", low)
    return int(m.group(1)) if m else None


def _extract_date(s: str) -> "str | None":
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    return m.group(0) if m else None


def _extract_question(text: str) -> str:
    """Strip a 'draft/write a memo on ...' lead-in, leaving the topic."""
    return re.sub(
        r"(?i)^\s*(please\s+)?(draft|write|prepare|compose)\s+(me\s+)?(a\s+)?"
        r"(memo|brief|note)?\s*(on|about|regarding|re)?\s*:?\s*",
        "", text.strip()).strip()


def command_mode_parse(text: str) -> dict:
    """Keyword parser used when Qwen is unavailable or its JSON did not parse."""
    t = text.strip()
    low = t.lower()
    if not low:
        return {"action": "unknown"}
    if low in ("quit", "exit", "q"):
        return {"action": "quit"}
    if low == "?" or low.startswith("help"):
        return {"action": "help"}
    if low.startswith("status"):
        return {"action": "status"}
    if low.startswith("why"):
        return {"action": "qa", "term": t}
    if low.startswith("draft") or ((low.startswith("write") or low.startswith("prepare")
                                    or low.startswith("compose")) and "memo" in low):
        return {"action": "draft", "question": _extract_question(t)}
    if low.startswith("import"):
        return {"action": "import", "docs_path": _first_path(t[len("import"):])}
    if low.startswith("review"):
        rest = t[len("review"):]
        cmd = {"action": "review", "docs_path": _first_path(rest), "mode": _extract_mode(low)}
        mc = _extract_flag_int(low, "--max-concurrent-docs")
        if mc:
            cmd["max_concurrent_docs"] = mc
        md = _extract_flag_int(low, "--max-docs")
        if md:
            cmd["max_docs"] = md
        return cmd
    if "cutoff" in low:
        d = _extract_date(t)
        return {"action": "set_cutoff", "date": d} if d else {"action": "unknown"}
    if "sensitive" in low:
        return {"action": "set_mode", "mode": "sensitive"}
    if "normal" in low or "mode" in low:
        return {"action": "set_mode", "mode": _extract_mode(low)}
    return {"action": "unknown"}


def parse_progress(line: str) -> "dict | None":
    """Parse a pipeline `[progress] key=value ...` line into a dict, or None if the
    line is not a progress line."""
    s = line.strip()
    if not s.startswith("[progress]"):
        return None
    d = {}
    for tok in s[len("[progress]"):].split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            d[k] = v
    return d


def _progress_bar(phase: str, width: int = 20) -> str:
    """A text bar from a `N/TOTAL` phase string, e.g. [=========>          ]."""
    try:
        n, t = phase.split("/")
        frac = max(0.0, min(1.0, float(n) / float(t)))
    except (ValueError, ZeroDivisionError, AttributeError):
        frac = 0.0
    filled = int(frac * width)
    if filled >= width:
        return "[" + "=" * width + "]"
    return "[" + "=" * filled + ">" + " " * (width - filled - 1) + "]"


def render_progress(d: dict) -> str:
    """Render a parsed progress dict into a single in-place status line."""
    event = d.get("event")
    if event == "start":
        return f"Starting review, {d.get('docs', '?')} documents..."
    if event == "complete":
        cost = d.get("cost", "?")
        return f"Complete. {d.get('amendments', '?')} amendments, ${cost}"
    if event in ("block", "warning"):
        return f"WARNING: {d.get('note', event)} (count {d.get('count', '?')})"
    phase = d.get("phase")
    bits = []
    if phase:
        bits.append(f"Phase {phase}")
    if d.get("doc"):
        bits.append(f"Doc {d['doc']}")
    if d.get("agent"):
        bits.append(d["agent"])
    bar = _progress_bar(phase) + " " if phase else ""
    return bar + " | ".join(bits)


def describe(cmd: dict) -> str:
    a = cmd.get("action")
    if a == "review":
        parts = ["run a review"]
        if cmd.get("docs_path"):
            parts.append(f"on {cmd['docs_path']}")
        parts.append(f"in {cmd.get('mode', 'normal')} mode")
        if cmd.get("max_concurrent_docs"):
            parts.append(f"{cmd['max_concurrent_docs']} in parallel")
        if cmd.get("max_docs"):
            parts.append(f"at most {cmd['max_docs']} documents")
        return ", ".join(parts)
    if a == "draft":
        return f"draft a memo on: {cmd.get('question') or '(no topic given)'}"
    if a == "import":
        return f"import documents from {cmd.get('docs_path') or '(no path given)'}"
    return str(a)


def read_cutoff() -> "str | None":
    if SCOPE_PATH.exists():
        try:
            return json.loads(SCOPE_PATH.read_text(encoding="utf-8")).get("cutoff_date")
        except json.JSONDecodeError:
            return None
    return None


def write_cutoff(date: str) -> None:
    scope = {}
    if SCOPE_PATH.exists():
        try:
            scope = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            scope = {}
    scope["cutoff_date"] = date
    scope["cutoff_type"] = "date"
    SCOPE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCOPE_PATH.write_text(json.dumps(scope, indent=2) + "\n", encoding="utf-8")


def _list_files(d: Path) -> "list[str]":
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_file() and p.name != ".gitkeep")


def conventions_present(docs_path: str) -> bool:
    if docs_path:
        p = Path(docs_path).expanduser()
        if p.is_dir():
            for f in p.iterdir():
                if f.is_file() and f.name in CONVENTION_NAMES:
                    return True
    cdir = ROOT / "input" / "conventions"
    if cdir.is_dir():
        for f in cdir.iterdir():
            if f.is_file() and f.name in CONVENTION_NAMES:
                return True
    return False


# The chat runs the pipeline as a subprocess with NO stdin connected, so every
# interactive input() in the pipeline would hang. These flags put the pipeline in
# log-and-proceed mode (the documented non-interactive LAW-0 path) and skip the
# "Proceed with live API calls?" gate. They are REQUIRED on every pipeline launch
# from chat. The override flags themselves (below) trigger confirm prompts unless
# --non-interactive is set, so these two must always accompany them.
PIPELINE_NONINTERACTIVE = ["--non-interactive", "--skip-confirmation"]


def mode_flags(mode: str, qwen_configured: bool) -> "list[str]":
    """Pipeline override flags for a run started WITHOUT the wizard (no docs path).
    Mirrors the wizard's mapping: Normal waives the layer AND redaction; Sensitive
    keeps redaction on and only clears the inactive-layer startup gate."""
    if mode == "sensitive":
        return ["--sensitivity-layer-inactive-override"]
    return ["--sensitivity-layer-inactive-override", "--no-redaction-override"]


def build_wizard_stdin(cmd: dict, *, import_only: bool, qwen_configured: bool,
                       conventions_will_exist: bool) -> str:
    """Build the exact stdin answer sequence the intake wizard expects, given the
    parsed command and the resolved branch state. The order mirrors the wizard's
    prompt order; optional prompts are included only when their branch fires."""
    answers = [cmd.get("docs_path", ""), ""]  # folder, then keep the cutoff
    if not import_only:
        answers.append("2" if cmd.get("mode") == "sensitive" else "1")
        if cmd.get("mode") == "sensitive" and not qwen_configured:
            answers.append("c")  # continue sensitive even though Qwen is absent
        mc = cmd.get("max_concurrent_docs")
        answers.append(str(mc) if mc else "")
        md = cmd.get("max_docs")
        answers.append(str(md) if md else "")
    if not conventions_will_exist:
        answers.append("P")  # proceed with default rules
    answers.append("Y")      # plan confirm
    return "\n".join(answers) + "\n"


def latest_run_dir() -> "Path | None":
    if not RUNS_ROOT.is_dir():
        return None
    dirs = [d for d in RUNS_ROOT.iterdir() if d.is_dir()]
    # Sort by mtime: human-readable <date>__<slug> run names are not chronologically
    # sortable by name (they carry no time of day).
    return max(dirs, key=lambda d: d.stat().st_mtime) if dirs else None


def _summarize_bus_line(line: str) -> str:
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return line.strip()[:160]
    agent = obj.get("agent", "?")
    items = obj.get("items") or []
    if items:
        it = items[0]
        bits = [str(it.get(k)) for k in ("ref", "verdict", "comment") if it.get(k)]
        return f"{agent}: " + " | ".join(bits)[:200]
    return f"{agent}: (no items)"


def search_bus(query: str) -> str:
    d = latest_run_dir()
    if d is None:
        return "No completed run found yet. Run a review first."
    bus = d / "logs" / "agent_bus.jsonl"
    if not bus.exists():
        return f"No bus log found for the latest run ({d.name})."
    terms = [t for t in re.findall(r"[A-Za-z0-9]+", query.lower())
             if t not in _STOPWORDS and len(t) > 1]
    if not terms:
        return "Tell me what to look up, for example: why did you flag <term>"
    hits = [ln for ln in bus.read_text(encoding="utf-8", errors="replace").splitlines()
            if any(t in ln.lower() for t in terms)]
    if not hits:
        return f"No findings mention {', '.join(terms)} in the latest run ({d.name})."
    out = [f"Found {len(hits)} matching entries in run {d.name}:"]
    out += ["  " + _summarize_bus_line(ln) for ln in hits[:5]]
    if len(hits) > 5:
        out.append(f"  ...and {len(hits) - 5} more.")
    return "\n".join(out)


def status_text(mode: str) -> str:
    ctx = _list_files(ROOT / "input" / "context")
    conv = _list_files(ROOT / "input" / "conventions")
    lines = [
        "Current settings:",
        f"  Date cutoff: {read_cutoff() or '(none set)'}",
        f"  Run mode (next run): {mode}",
        f"  Documents in input/context/: {len(ctx)}"
        + (" (" + ", ".join(ctx[:8]) + ("..." if len(ctx) > 8 else "") + ")" if ctx else ""),
        f"  Conventions loaded: {len(conv)}"
        + (" (" + ", ".join(conv) + ")" if conv else " (none)"),
    ]
    return "\n".join(lines)


# --- GUI -----------------------------------------------------------------------

class ChatApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.busy = False
        self.pending = None        # a parsed command awaiting y/n confirmation
        self.pending_mode = "normal"
        self.qwen_available = False

        root.title("Shimmer")
        root.geometry("700x500")
        root.configure(bg=BG)

        frame = tk.Frame(root, bg=BG)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        self.msg = tk.Text(frame, bg=BG, fg=FG, insertbackground=FG, font=FONT,
                           wrap="word", state="disabled", borderwidth=0,
                           highlightthickness=0)
        scroll = tk.Scrollbar(frame, command=self.msg.yview)
        self.msg.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.msg.pack(side="left", fill="both", expand=True)

        # In-place progress line (updated as [progress] lines stream in; not scrolled
        # away by the log above). Stays blank when idle.
        self.status = tk.Label(root, text="", bg=BG, fg=FG, font=FONT, anchor="w",
                               justify="left")
        self.status.pack(fill="x", padx=8, pady=(0, 2))

        bottom = tk.Frame(root, bg=BG)
        bottom.pack(fill="x", padx=8, pady=(0, 8))
        self.entry = tk.Entry(bottom, bg=ENTRY_BG, fg=FG, insertbackground=FG, font=FONT,
                              borderwidth=0, highlightthickness=1, highlightbackground=BTN_BG)
        self.entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.entry.bind("<Return>", self.on_send)
        self.entry.focus_set()
        send = tk.Button(bottom, text="Send", command=self.on_send, bg=BTN_BG, fg=FG,
                         activebackground=FG, activeforeground=BG, borderwidth=0, font=FONT)
        send.pack(side="left", padx=(8, 0))

        self.post("Welcome to Shimmer. Type 'help' for what I can do.")
        threading.Thread(target=self._check_qwen, daemon=True).start()

    # message helpers ----------------------------------------------------------

    def _append(self, s: str) -> None:
        self.msg.configure(state="normal")
        self.msg.insert("end", s)
        self.msg.configure(state="disabled")
        self.msg.see("end")

    def post(self, text: str) -> None:
        self._append("Shimmer: " + text + "\n\n")

    def post_raw(self, line: str) -> None:
        self._append(line + "\n")

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def ui(self, fn, *a) -> None:
        """Schedule a UI update on the main thread (safe from worker threads)."""
        self.root.after(0, lambda: fn(*a))

    # startup Qwen probe -------------------------------------------------------

    def _check_qwen(self) -> None:
        configured = False
        try:
            import redaction_gate
            configured = bool(redaction_gate.qwen_backend_status(ROOT).get("configured"))
        except Exception:
            configured = False
        self.qwen_available = configured
        if configured:
            self.ui(self.post, "Local AI model available. Describe what you want in plain language.")
        else:
            self.ui(self.post, "Local AI model not available. Using command mode. "
                               "Type 'help' for available commands.")

    # send + dispatch ----------------------------------------------------------

    def on_send(self, event=None):
        text = self.entry.get().strip()
        self.entry.delete(0, "end")
        if not text:
            return "break"
        self._append("You: " + text + "\n\n")
        if self.busy:
            self.post("Still working on the previous request. Please wait.")
            return "break"
        if self.pending is not None:
            self._handle_confirmation(text)
            return "break"
        if self.qwen_available:
            self.busy = True
            self.post("Thinking...")
            threading.Thread(target=self._qwen_parse, args=(text,), daemon=True).start()
        else:
            self._on_parsed(command_mode_parse(text), text)
        return "break"

    def _handle_confirmation(self, text: str) -> None:
        ans = text.strip().lower()
        cmd, self.pending = self.pending, None
        if ans in ("y", "yes"):
            self._execute(cmd)
        elif ans in ("n", "no"):
            self.post("Cancelled.")
        else:
            self.pending = cmd
            self.post("Please answer y or n.")

    def _qwen_parse(self, text: str) -> None:
        cmd = None
        try:
            from agent_wrapper import _load_qwen
            import decoding_policy
            import torch
            mid = redactor_model_id()
            # Same model and the same declared decoding policy as REDACTOR's own
            # call site (config/decoding_policy.json): greedy, single beam.
            decoding = decoding_policy.policy("qwen_local")
            tok, mdl = _load_qwen(mid)
            prompt = QWEN_SYSTEM_PROMPT + "\n\nUser: " + text + "\n\nJSON:"
            inputs = tok(prompt, return_tensors="pt").to(mdl.device)
            with torch.no_grad():
                out = mdl.generate(**inputs, max_new_tokens=256, **decoding["kwargs"])
            raw = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
            cmd = extract_json(raw)
        except Exception:
            cmd = None
        if not cmd or "action" not in cmd:
            cmd = command_mode_parse(text)  # graceful fallback for this input
        self.ui(self._after_parse, cmd, text)

    def _after_parse(self, cmd: dict, text: str) -> None:
        self.busy = False
        self._on_parsed(cmd, text)

    def _on_parsed(self, cmd: dict, text: str) -> None:
        action = cmd.get("action", "unknown")
        if action in ("review", "draft", "import"):
            if action == "review":
                cmd.setdefault("mode", self.pending_mode)
            self.pending = cmd
            self.post(f"Understood: {describe(cmd)}. Proceed? [y/n]")
        elif action == "set_cutoff":
            date = cmd.get("date")
            if date and valid_date(date):
                write_cutoff(date)
                self.post(f"Cutoff updated to {date}.")
            else:
                self.post("That date is not valid. Use YYYY-MM-DD, for example 2025-06-01.")
        elif action == "set_mode":
            self.pending_mode = "sensitive" if cmd.get("mode") == "sensitive" else "normal"
            self.post(f"Run mode set to {self.pending_mode} for the next review.")
        elif action == "status":
            self.post(status_text(self.pending_mode))
        elif action == "help":
            self.post(HELP_TEXT)
        elif action == "qa":
            self.post(search_bus(cmd.get("term", text)))
        elif action == "quit":
            self.post("Goodbye.")
            self.root.after(400, self.root.destroy)
        else:
            self.post("I did not understand that. Type 'help' for available commands.")

    # execution ----------------------------------------------------------------

    def _execute(self, cmd: dict) -> None:
        self.busy = True
        self.post("[running...]")
        action = cmd.get("action")
        target = (self._run_review if action == "review"
                  else self._run_draft if action == "draft"
                  else self._run_import)
        threading.Thread(target=target, args=(cmd,), daemon=True).start()

    def _stream_subprocess(self, argv: "list[str]", stdin_str: "str | None") -> int:
        try:
            proc = subprocess.Popen(
                argv, cwd=str(ROOT),
                stdin=subprocess.PIPE if stdin_str is not None else None,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1)
        except OSError as e:
            self.ui(self.post, f"Could not start the process: {e}")
            return 1
        if stdin_str is not None and proc.stdin is not None:
            try:
                proc.stdin.write(stdin_str)
                proc.stdin.flush()
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        if proc.stdout is not None:
            for line in proc.stdout:
                d = parse_progress(line)
                if d is not None:
                    # Update the in-place status line; do not scroll it into the log.
                    self.ui(self._set_status, render_progress(d))
                else:
                    self.ui(self.post_raw, line.rstrip("\n"))
        proc.wait()
        return proc.returncode

    def _run_review(self, cmd: dict) -> None:
        configured = self.qwen_available
        flags: "list[str]" = []
        docs = cmd.get("docs_path")
        if docs:
            conv = conventions_present(docs)
            stdin_str = build_wizard_stdin(cmd, import_only=False, qwen_configured=configured,
                                           conventions_will_exist=conv)
            flags_file = Path(tempfile.gettempdir()) / f"shimmer_chat_flags_{os.getpid()}.txt"
            try:
                flags_file.unlink()
            except OSError:
                pass
            rc = self._stream_subprocess(
                [sys.executable, "-X", "utf8", str(WIZARD), "--emit-flags", str(flags_file)],
                stdin_str)
            if rc != 0:
                self.ui(self.post, "Setup was cancelled or failed. No review run.")
                self.ui(self._finish_run)
                return
            if flags_file.exists():
                flags = flags_file.read_text(encoding="utf-8").split()
                try:
                    flags_file.unlink()
                except OSError:
                    pass
        else:
            flags = mode_flags(cmd.get("mode", "normal"), configured)
            if cmd.get("max_concurrent_docs"):
                flags += ["--max-concurrent-docs", str(cmd["max_concurrent_docs"])]
            if cmd.get("max_docs"):
                flags += ["--max-docs", str(cmd["max_docs"])]

        self.ui(self.post, "Running the review...")
        rc = self._stream_subprocess(
            [sys.executable, "-X", "utf8", str(PIPELINE)] + PIPELINE_NONINTERACTIVE + flags, None)
        if rc == 0:
            d = latest_run_dir()
            where = (f" Results in {d.relative_to(ROOT).as_posix()}/deliverables/ "
                     f"(start with _run_summary.md)") if d else ""
            self.ui(self.post, "Review complete." + where)
        else:
            self.ui(self.post, f"Review ended with exit code {rc}. See the messages above.")
        self.ui(self._finish_run)

    def _run_draft(self, cmd: dict) -> None:
        question = (cmd.get("question") or "").strip()
        if not question:
            self.ui(self.post, "Tell me what the memo should be about. Try: draft a memo on <topic>")
            self.ui(self._finish_run)
            return
        # The question is one argv element (not space-split), so spaces are fine.
        flags = mode_flags(self.pending_mode, self.qwen_available)
        argv = ([sys.executable, "-X", "utf8", str(PIPELINE),
                 "--task", "draft", "--question", question]
                + PIPELINE_NONINTERACTIVE + flags)
        self.ui(self.post, "Drafting a memo, then reviewing it...")
        rc = self._stream_subprocess(argv, None)
        if rc == 0:
            d = latest_run_dir()
            where = (f" Results in {d.relative_to(ROOT).as_posix()}/deliverables/ "
                     f"(start with _run_summary.md)") if d else ""
            self.ui(self.post, "Draft and review complete." + where)
        else:
            self.ui(self.post, f"Draft ended with exit code {rc}. See the messages above.")
        self.ui(self._finish_run)

    def _run_import(self, cmd: dict) -> None:
        docs = cmd.get("docs_path")
        if not docs:
            self.ui(self.post, "Import needs a folder. Try: import ./my_docs")
            self.ui(self._finish_run)
            return
        conv = conventions_present(docs)
        stdin_str = build_wizard_stdin(cmd, import_only=True, qwen_configured=False,
                                       conventions_will_exist=conv)
        rc = self._stream_subprocess(
            [sys.executable, "-X", "utf8", str(WIZARD), "--import-only"], stdin_str)
        self.ui(self.post, "Import complete." if rc == 0 else "Import was cancelled or failed.")
        self.ui(self._finish_run)

    def _finish_run(self) -> None:
        self.busy = False
        self.pending = None
        self._set_status("")
        self.entry.focus_set()


def main() -> int:
    root = tk.Tk()
    ChatApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
