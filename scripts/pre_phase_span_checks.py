"""Gate check: the pipeline's time before phase 3 is in phase_latencies (open item 38).

phase_latencies used to start at phase 3: only the five decorated phase functions emit
phase_enter/phase_exit, and main's work before phase 3-4 (startup gates, ingestion and
role resolution, orchestrator boot and reference index, phase 1's situation assessment)
is inline. main now marks it with execution_topology.pre_phase_span, contiguous spans
from argument parsing to phase 3-4's own boundary. Genesis phase 2 (task force
emergence) has no code of its own in main, so no span is invented for it.

Two legs, each proven by neutralise, fail, restore, pass:

1. main's spans: read from scripts/pipeline.py's AST, in order, each before the
   statement it names (the role-resolution call, the orchestrator boot, the phase 1
   deliberation round) and the closing call before phase 3-4 is reached; neutralised by
   removing the span calls from the source.
2. the spans reach the summary: the span names read in leg 1 are driven through a real
   topology Runtime on a temporary run folder, followed by a phase_boundary-decorated
   fixture phase 3-4, and model_telemetry.recompute's phase_latencies carry every span
   before phase 3-4, with consumer_barriers unchanged (one row, phase 3-4's); a span
   left open when main returns is closed by Runtime.close with state run_ended.
   Neutralised by making pre_phase_span a no-op, and by dropping the pre_phase_3 mark
   from the events (the spans then add barrier rows).

No model, no pipeline run, no network.
"""
import ast
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import execution_topology as topology  # noqa: E402
import model_telemetry  # noqa: E402
from execution_scheduler import Lane  # noqa: E402

CALL = "execution_topology.pre_phase_span"
# Each opened span must come before the statement whose work it times.
ANCHORS = {"phase_0_ingestion_and_roles": "_populate_operational(",
           "phase_0_boot_and_index": "TopOrchestrator.boot(",
           "phase_1_situation_assessment": "orch.deliberation_round("}


def main_spans(source):
    """(span names in order, problems) for main's top-level body."""
    tree = ast.parse(source)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    body = [ast.unparse(s) for s in main.body]
    marks = []
    for index, text in enumerate(body):
        if text.startswith(CALL + "("):
            call = main.body[index].value
            marks.append((index, call.args[0].value if isinstance(call.args[0], ast.Constant) else "?"))
    names = [name for _, name in marks]
    problems = []
    if not marks:
        return names, ["main carries no pre-phase-3 span"]
    if not body[marks[0][0] - 1].startswith("args = parser.parse_args("):
        problems.append("the first span does not open right after argument parsing")
    if names[-1] is not None:
        problems.append("the last span call does not close (None)")
    phase3 = next((i for i, t in enumerate(body) if "phase_3_4_content_production(" in t), None)
    if phase3 is None or marks[-1][0] > phase3:
        problems.append("the closing span call is not before phase 3-4")
    for position, (index, name) in enumerate(marks):
        anchor = ANCHORS.get(name)
        if anchor is None:
            continue
        following = marks[position + 1][0] if position + 1 < len(marks) else len(body)
        if not any(anchor in t for t in body[index + 1:following]):
            problems.append("span %s does not time %s" % (name, anchor.rstrip("(")))
    missing = sorted(set(ANCHORS) - set(names))
    if missing:
        problems.append("spans missing: " + ", ".join(missing))
    return names, problems


class _Run:
    def __init__(self, directory):
        self.run_dir = Path(directory)
        self.run_id = "fixture-run"

    def audit_dir(self):
        return self.run_dir / "audit"

    def logs_dir(self):
        return self.run_dir / "logs"


def drive(names, leave_open=False):
    """The telemetry summary after the spans and a fixture phase 3-4 ran."""
    with tempfile.TemporaryDirectory() as directory:
        runtime = topology.Runtime([Lane("fixture")])
        runtime.run_context = _Run(directory)
        token = topology.ACTIVE.set(runtime)
        try:
            for name in names:
                topology.pre_phase_span(name)

            @topology.phase_boundary
            def phase_3_4_content_production():
                return None
            phase_3_4_content_production()
            if leave_open:
                topology.pre_phase_span("phase_left_open")
        finally:
            topology.ACTIVE.reset(token)
            runtime.close()
        summary = json.loads((Path(directory) / "audit" / "model_telemetry_summary.json").read_text(encoding="utf-8"))
        events = [json.loads(line) for line in
                  (Path(directory) / "audit" / "execution_topology.jsonl").read_text(encoding="utf-8").splitlines()]
    return summary, events


def summary_problems(names):
    opened = [n for n in names if n is not None]
    summary, events = drive(names, leave_open=True)
    phases = [p["phase"] for p in summary["phase_latencies"]]
    problems = []
    expected = opened + ["phase_3_4_content_production", "phase_left_open"]
    if phases != expected:
        problems.append("phase_latencies %s, expected %s" % (phases, expected))
    if any(p["seconds"] < 0 for p in summary["phase_latencies"]):
        problems.append("a negative span")
    barriers = [b["consumer_phase"] for b in summary["consumer_barriers"]]
    if barriers != ["phase_3_4_content_production"]:
        problems.append("consumer_barriers %s, expected phase 3-4 alone" % barriers)
    left = [e for e in events if e["event"] == "phase_exit" and e["phase"] == "phase_left_open"]
    if [e.get("state") for e in left] != ["run_ended"]:
        problems.append("a span open at return is not closed as run_ended")
    return problems


def _drop_mark(emit):
    def emit_unmarked(event, **fields):
        fields.pop("pre_phase_3", None)
        return emit(event, **fields)
    return emit_unmarked


def legs(source):
    names, problems = main_spans(source)
    if problems:
        return names, problems
    return names, summary_problems(names)


def check():
    source = (SCRIPTS / "pipeline.py").read_text(encoding="utf-8")
    names, problems = legs(source)
    if problems:
        return "FAIL", "; ".join(problems[:4])
    stripped = "\n".join(line for line in source.splitlines() if CALL not in line)
    original_init = topology.Runtime.__init__

    def unmarked_init(self, lanes):
        original_init(self, lanes)
        self.scheduler.emit = _drop_mark(self.scheduler.emit)
    proofs = []
    for label, mutate in (
            ("span calls removed from main", lambda: legs(stripped)[1]),
            ("pre_phase_span a no-op", lambda: _patched(topology, "pre_phase_span", lambda name: None,
                                                         lambda: summary_problems(names))),
            ("pre_phase_3 mark dropped", lambda: _patched(topology.Runtime, "__init__", unmarked_init,
                                                           lambda: summary_problems(names)))):
        failed = bool(mutate())
        restored = not legs(source)[1]
        if not (failed and restored):
            return "FAIL", "%s: failed=%s, restored pass=%s" % (label, failed, restored)
        proofs.append(label)
    return "PASS", ("main times %d pre-phase-3 spans (%s), contiguous from argument parsing to phase 3-4, "
                    "and they reach phase_latencies before phase 3-4 with consumer_barriers unchanged; a span "
                    "open at return closes as run_ended; neutralised, failed, restored, passed: %s"
                    % (len([n for n in names if n]), ", ".join(n for n in names if n), "; ".join(proofs)))


def _patched(owner, attribute, value, run):
    with patch.object(owner, attribute, value):
        return run()


if __name__ == "__main__":
    print(*check())
