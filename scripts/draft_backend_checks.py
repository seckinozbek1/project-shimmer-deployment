"""Gate check: the draft memo goes through the drafter's own backend (INC-031).

pipeline._draft_generate_with_evidence used to call drafter.call_claude whatever
backend the drafter resolved, so a draft under the local backend profile went to
the Claude client (launch L14b: backend claude_api with a local model id, three
blocked connection attempts, exit 5). The memo now goes through dispatch, the one
place that picks the backend function.

No provider, no network, no weights: the model boundaries are the stand-ins of
scripts/reply_records_checks.py (a recording tokenizer and model for the local
backends, a recording SDK for the cloud ones), so the REAL backend functions run
and write their reply records. Two cases, each in its own temporary run folder:

  local   the drafter on local_producer, its call_claude replaced by one that
          raises: the memo must be the local stand-in's text, the Claude client
          must see nothing, and the call evidence, the activation row, the reply
          record and its free_text outcome must all name the local backend and
          the same call id;
  cloud   the drafter on claude_api, its call_local replaced by one that raises:
          the memo must be the Claude stand-in's text (the cloud path unchanged).

Neutralise, fail, restore, pass: the function's own source with the old line put
back (a direct call_claude) is compiled beside the pipeline and must fail the
local case; the shipped function must pass before and after.
"""
from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNCTION = "_draft_generate_with_evidence"
NEW_CALL = "lambda: drafter.dispatch(stable, dynamic, **budget),"
OLD_CALL = "lambda: drafter.call_claude(stable, dynamic, max_tokens=4096),"
LOCAL_MEMO = "LOCAL STAND-IN MEMO"
CLOUD_MEMO = "CLOUD STAND-IN MEMO"


def _neutralised_function():
    """The shipped function with its memo call put back to a direct call_claude,
    compiled in the pipeline's own namespace."""
    import pipeline
    source = (ROOT / "scripts" / "pipeline.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef) and n.name == FUNCTION)
    segment = ast.get_source_segment(source, node)
    if segment.count(NEW_CALL) != 1:
        raise AssertionError("cannot neutralise: the memo call is not written as %r" % NEW_CALL)
    namespace = dict(vars(pipeline))
    exec(compile(segment.replace(NEW_CALL, OLD_CALL), "pipeline_neutralised", "exec"), namespace)
    return namespace[FUNCTION]


def _case(function, backend):
    """Run FUNCTION once for a drafter on BACKEND. Returns (problems, summary)."""
    import agent_activation
    import call_evidence
    import reply_records
    import reply_records_checks as rrc
    problems = []
    with tempfile.TemporaryDirectory(prefix="shimmer_draft_backend_", ignore_cleanup_errors=True) as td:
        fx = rrc.Fixture(td)
        fx.registry["AMENDMENT_DRAFTER"] = dict(fx.registry["AMENDMENT_DRAFTER"], backend=backend)
        audit = agent_activation.initialize(fx.ctx, ["AMENDMENT_DRAFTER"])
        drafter = fx.wrapper("AMENDMENT_DRAFTER")
        refused = []
        other = "call_claude" if backend != "claude_api" else "call_local"

        def refuse(*args, **kwargs):
            refused.append(other)
            raise RuntimeError("the %s path was taken for a %s drafter" % (other, backend))
        setattr(drafter, other, refuse)
        seen = {"claude": [], "gpt": [], "local": []}
        memo, error = None, None
        with rrc.backends(claude=[CLOUD_MEMO], local=[LOCAL_MEMO], seen=seen):
            try:
                memo = function(drafter, "Draft a memo.", "## Question\nA question",
                                passages=[{"ref_id": "REF-0003", "text": "p"}], run_ctx=fx.ctx)
            except Exception as exc:  # the neutralised local case raises here
                error = "%s: %s" % (type(exc).__name__, exc)
        expected = LOCAL_MEMO if backend != "claude_api" else CLOUD_MEMO
        if error:
            problems.append("the call raised (%s)" % error)
        if refused:
            problems.append("the %s path was taken" % refused[0])
        if memo != expected:
            problems.append("memo %r, expected %r" % (memo, expected))
        if backend != "claude_api" and seen["claude"]:
            problems.append("the Claude client was sent %d request(s)" % len(seen["claude"]))
        if backend != "claude_api" and len(seen["local"]) != 1:
            problems.append("the local stand-in saw %d prompt(s), expected 1" % len(seen["local"]))
        if backend == "claude_api" and len(seen["claude"]) != 1:
            problems.append("the Claude stand-in saw %d request(s), expected 1" % len(seen["claude"]))
        evidence = call_evidence.load(fx.ctx.run_dir)
        call_id = evidence[0].get("call_id") if len(evidence) == 1 else None
        if len(evidence) != 1 or evidence[0].get("backend") != backend or evidence[0].get("task") != "draft_memo":
            problems.append("call evidence %r" % [(e.get("task"), e.get("backend")) for e in evidence])
        rows = [r for r in audit.data["decisions"] if r["agent"] == "AMENDMENT_DRAFTER"]
        if len(rows) != 1 or rows[0].get("state") != "completed" or rows[0].get("outcome") != "free_text" \
                or rows[0].get("call_id") != call_id:
            problems.append("activation rows %r" % [(r.get("state"), r.get("outcome")) for r in rows])
        records = [r for r in reply_records.records(fx.replies) if r.get("agent") == "AMENDMENT_DRAFTER"]
        if len(records) != 1 or records[0].get("backend") != backend or records[0].get("call_id") != call_id:
            problems.append("reply records %r" % [(r.get("backend"), r.get("call_id")) for r in records])
        elif reply_records.outcome_of(fx.replies, call_id) != "free_text":
            problems.append("outcome %r" % reply_records.outcome_of(fx.replies, call_id))
        if getattr(drafter, "_cost_call_id", "") != "":
            problems.append("the drafter's call id was not cleared")
    return problems, "%s: memo %r" % (backend, memo)


def check():
    """(status, detail) for the gate."""
    import pipeline
    shipped = getattr(pipeline, FUNCTION)
    local, local_summary = _case(shipped, "local_producer")
    if local:
        return "FAIL", "the shipped draft call on a local drafter: " + "; ".join(local)
    cloud, cloud_summary = _case(shipped, "claude_api")
    if cloud:
        return "FAIL", "the shipped draft call on a Claude drafter: " + "; ".join(cloud)
    try:
        neutralised = _neutralised_function()
    except AssertionError as exc:
        return "FAIL", str(exc)
    broken, _ = _case(neutralised, "local_producer")
    if not broken:
        return "FAIL", "with the old direct call_claude put back the local case still passed; the check proves nothing"
    again, _ = _case(shipped, "local_producer")
    if again:
        return "FAIL", "after restoring, the local case fails: " + "; ".join(again)
    return "PASS", ("%s, %s; the real local and Claude backend functions ran on stand-ins, evidence, "
                    "activation row, reply record and free_text outcome on one call id; neutralise (direct "
                    "call_claude) FAILS: %s; restore PASSES" % (local_summary, cloud_summary, "; ".join(broken)))


if __name__ == "__main__":
    print(json.dumps(check()))
