"""Gate check: the draft memo goes through the drafter's own backend (INC-031).

pipeline._draft_generate_with_evidence used to call drafter.call_claude whatever
backend the drafter resolved, so a draft under the local backend profile went to
the Claude client (launch L14b: backend claude_api with a local model id, three
blocked connection attempts, exit 5). The memo now goes through dispatch, the one
place that picks the backend function.

No provider, no network, no weights: the model boundaries are the stand-ins of
scripts/reply_records_checks.py (a recording tokenizer and model for the local
backends, a recording SDK for the cloud ones), so the REAL backend functions run
and write their reply records. One case per backend (local_producer, qwen_local,
claude_api, openai_api), each in its own temporary run folder, with every backend
function but the drafter's own replaced by one that raises: the memo must be that
backend's stand-in text, no other stand-in may be sent anything, and the call
evidence, the activation row, the reply record and its free_text outcome must all
name the drafter's backend and the same call id. The reply record must state the
requested output allowance, 4096, under the key that backend takes (max_new_tokens
for a local backend, max_tokens for a provider; S10 adversarial MINOR 4).

Neutralise, fail, restore, pass: the function's own source with the memo call put
back to a direct call_claude, and with its budget emptied, is compiled beside the
pipeline and must fail the local case; the shipped function must pass before and
after.
"""
from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FUNCTION = "_draft_generate_with_evidence"
NEW_CALL = "lambda: drafter.dispatch(stable, dynamic, **budget),"
OLD_CALL = "lambda: drafter.call_claude(stable, dynamic, max_tokens=4096),"
LOCAL_MEMO = "LOCAL STAND-IN MEMO"
CLOUD_MEMO = "CLOUD STAND-IN MEMO"


EMPTY_BUDGET_CALL = "lambda: drafter.dispatch(stable, dynamic, **{}),"
# The memo's output allowance, as the reply record states it (S10 adversarial MINOR 4).
BUDGET = 4096
# backend -> (the backend function dispatch must reach, the stand-in it talks to, the memo
# that stand-in answers, the decoding key the reply record carries the allowance under)
BACKENDS = {
    "local_producer": ("call_local", "local", LOCAL_MEMO, "max_new_tokens"),
    "qwen_local": ("call_qwen", "local", LOCAL_MEMO, "max_new_tokens"),
    "claude_api": ("call_claude", "claude", CLOUD_MEMO, "max_tokens"),
    "openai_api": ("call_gpt", "gpt", CLOUD_MEMO, "max_tokens"),
}
FUNCTIONS = ("call_claude", "call_gpt", "call_qwen", "call_local")


def _neutralised_function(new=OLD_CALL, old=NEW_CALL):
    """The shipped function with its memo call replaced by NEW (by default the old direct
    call_claude), compiled in the pipeline's own namespace."""
    import pipeline
    source = (ROOT / "scripts" / "pipeline.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef) and n.name == FUNCTION)
    segment = ast.get_source_segment(source, node)
    if segment.count(old) != 1:
        raise AssertionError("cannot neutralise: the memo call is not written as %r" % old)
    namespace = dict(vars(pipeline))
    exec(compile(segment.replace(old, new), "pipeline_neutralised", "exec"), namespace)
    return namespace[FUNCTION]


def _case(function, backend):
    """Run FUNCTION once for a drafter on BACKEND, every other backend function replaced by
    one that raises. Returns (problems, summary)."""
    import agent_activation
    import call_evidence
    import reply_records
    import reply_records_checks as rrc
    own, stand_in, expected, budget_key = BACKENDS[backend]
    problems = []
    with tempfile.TemporaryDirectory(prefix="shimmer_draft_backend_", ignore_cleanup_errors=True) as td:
        fx = rrc.Fixture(td)
        fx.registry["AMENDMENT_DRAFTER"] = dict(fx.registry["AMENDMENT_DRAFTER"], backend=backend)
        audit = agent_activation.initialize(fx.ctx, ["AMENDMENT_DRAFTER"])
        drafter = fx.wrapper("AMENDMENT_DRAFTER")
        refused = []

        def refuser(name):
            def refuse(*args, **kwargs):
                refused.append(name)
                raise RuntimeError("the %s path was taken for a %s drafter" % (name, backend))
            return refuse
        for name in FUNCTIONS:
            if name != own:
                setattr(drafter, name, refuser(name))
        seen = {"claude": [], "gpt": [], "local": []}
        memo, error = None, None
        with rrc.backends(claude=[CLOUD_MEMO], gpt=[CLOUD_MEMO], local=[LOCAL_MEMO], seen=seen):
            try:
                memo = function(drafter, "Draft a memo.", "## Question\nA question",
                                passages=[{"ref_id": "REF-0003", "text": "p"}], run_ctx=fx.ctx)
            except Exception as exc:  # the neutralised local case raises here
                error = "%s: %s" % (type(exc).__name__, exc)
        if error:
            problems.append("the call raised (%s)" % error)
        if refused:
            problems.append("the %s path was taken" % refused[0])
        if memo != expected:
            problems.append("memo %r, expected %r" % (memo, expected))
        for other, sent in seen.items():
            if other != stand_in and sent:
                problems.append("the %s stand-in was sent %d request(s)" % (other, len(sent)))
        if len(seen[stand_in]) != 1:
            problems.append("the %s stand-in saw %d request(s), expected 1" % (stand_in, len(seen[stand_in])))
        evidence = call_evidence.load(fx.ctx.run_dir)
        call_id = evidence[0].get("call_id") if len(evidence) == 1 else None
        if len(evidence) != 1 or evidence[0].get("backend") != backend or evidence[0].get("task") != "draft_memo":
            problems.append("call evidence %r" % [(e.get("task"), e.get("backend")) for e in evidence])
        rows = [r for r in audit.data["decisions"] if r["agent"] == "AMENDMENT_DRAFTER"]
        if len(rows) != 1 or rows[0].get("state") != "completed" or rows[0].get("outcome") != "free_text" \
                or rows[0].get("call_id") != call_id:
            problems.append("activation rows %r" % [(r.get("state"), r.get("outcome")) for r in rows])
        records = [r for r in reply_records.records(fx.replies) if r.get("agent") == "AMENDMENT_DRAFTER"]
        allowance = None
        if len(records) != 1 or records[0].get("backend") != backend or records[0].get("call_id") != call_id:
            problems.append("reply records %r" % [(r.get("backend"), r.get("call_id")) for r in records])
        else:
            allowance = (records[0].get("decoding") or {}).get(budget_key)
            if allowance != BUDGET:
                problems.append("the reply record's requested output allowance (decoding.%s) is %r, expected %d"
                                % (budget_key, allowance, BUDGET))
            if reply_records.outcome_of(fx.replies, call_id) != "free_text":
                problems.append("outcome %r" % reply_records.outcome_of(fx.replies, call_id))
        if getattr(drafter, "_cost_call_id", "") != "":
            problems.append("the drafter's call id was not cleared")
    return problems, "%s: memo %r, allowance %r" % (backend, memo, allowance)


CUT_MARK = "- draft memo: it reached its output limit, so its text may be cut off"
CUT_DETAIL = """truncated=(getattr(r, "usage", None) or {}).get("truncated"))"""
NOT_MARKED = "a memo at its output limit is not marked"


def _memo_marked(function, backend, stops, task="draft"):
    """Open item 67, on the real dispatch, backend and direct_call: the run summary says the
    memo was cut, and the shipped copy says so too. Returns (summary marked, memo marked)."""
    import agent_activation
    import pipeline
    import reply_records
    import reply_records_checks as rrc
    with tempfile.TemporaryDirectory(prefix="shimmer_draft_cut_", ignore_cleanup_errors=True) as td:
        fx = rrc.Fixture(td)
        fx.registry["AMENDMENT_DRAFTER"] = dict(fx.registry["AMENDMENT_DRAFTER"], backend=backend)
        agent_activation.initialize(fx.ctx, ["AMENDMENT_DRAFTER"])
        drafter = fx.wrapper("AMENDMENT_DRAFTER")
        with rrc.backends(claude=[CLOUD_MEMO], gpt=[CLOUD_MEMO], **stops):
            function(drafter, "Draft a memo.", "## Question\nA question", passages=[], run_ctx=fx.ctx)
        summary = pipeline.write_deliverables_run_summary(Path(fx.ctx.run_dir) / "deliverables", [], {},
                                                          total_cost_usd=0.0, task=task)
        memo = Path(td) / "memo.md"
        memo.write_text("Memo text", encoding="utf-8")
        reply_records.note_cut_memo(memo, reply_records.folder(fx.ctx))
        return (CUT_MARK in Path(summary).read_text(encoding="utf-8"),
                reply_records.MEMO_CUT_NOTE in memo.read_text(encoding="utf-8"))


def _cut_problems(function):
    problems = []
    for backend, stops in (("claude_api", {"claude_stop": "max_tokens"}), ("openai_api", {"gpt_stop": "length"})):
        if _memo_marked(function, backend, stops) != (True, True):
            problems.append(NOT_MARKED)
    for backend, stops in (("claude_api", {}), ("openai_api", {}), ("claude_api", {"claude_stop": None})):
        if _memo_marked(function, backend, stops) != (False, False):
            problems.append("a memo with stops %r on %s is marked" % (stops, backend))
    if _memo_marked(function, "claude_api", {"claude_stop": "max_tokens"}, task="review")[0]:
        problems.append("a review run's summary reads a draft row")
    return problems


def _reader_cases():
    """{case: draft_memo_cut} over written files, so a damaged record is really read."""
    import reply_records
    cut = '{"source": "draft_memo", "truncated": true, "call_id": "a", "outcome": "free_text"}'
    uncut = '{"source": "draft_memo", "truncated": false, "call_id": "b", "outcome": "free_text"}'
    other = '{"source": "agent", "truncated": true, "call_id": "c", "outcome": "free_text"}'
    word = '{"source": "draft_memo", "truncated": "yes", "call_id": "d", "outcome": "free_text"}'
    files = {"cut": cut.encode(), "damaged line": (cut + "\n{half").encode(), "not an object": (cut + "\n[1]").encode(),
             "later uncut": (cut + "\n" + uncut).encode(), "other source": other.encode(), "a word": word.encode(),
             "bad bytes": b"\xff\xfe" + cut.encode()}
    out = {}
    with tempfile.TemporaryDirectory(prefix="shimmer_draft_rows_", ignore_cleanup_errors=True) as td:
        for name, data in files.items():
            (Path(td) / reply_records.OUTCOMES_NAME).write_bytes(data)
            out[name] = reply_records.draft_memo_cut(td)
        (Path(td) / reply_records.OUTCOMES_NAME).unlink()
        out["no file"] = reply_records.draft_memo_cut(td)
    return out


READER_EXPECTED = {"cut": True, "damaged line": True, "not an object": True, "later uncut": False,
                   "other source": False, "a word": False, "bad bytes": False, "no file": False}


def _turkish_rows():
    import localization
    import reply_records
    return all(localization.message(t, "tr") != t for t in (CUT_MARK, reply_records.MEMO_CUT_NOTE))


def check():
    """(status, detail) for the gate."""
    import pipeline
    import reply_records
    shipped = getattr(pipeline, FUNCTION)
    cut = _cut_problems(shipped)
    if cut:
        return "FAIL", "; ".join(cut)
    rows = _reader_cases()
    if rows != READER_EXPECTED:
        return "FAIL", "draft_memo_cut read %r" % rows
    if not _turkish_rows():
        return "FAIL", "a memo mark has no Turkish row"
    try:
        no_detail = _neutralised_function('truncated=None)', CUT_DETAIL)
    except AssertionError as exc:
        return "FAIL", str(exc)
    if NOT_MARKED not in _cut_problems(no_detail):
        return "FAIL", "with the outcome's stop reason neutralised the memo is still marked; the check proves nothing"
    with patch.object(reply_records, "draft_memo_cut", lambda path: False):
        if NOT_MARKED not in _cut_problems(shipped):
            return "FAIL", "with the reader neutralised the memo is still marked; the check proves nothing"
    if _cut_problems(shipped):
        return "FAIL", "after restoring, the memo mark fails"
    summaries = []
    for backend in BACKENDS:
        problems, summary = _case(shipped, backend)
        if problems:
            return "FAIL", "the shipped draft call on a %s drafter: %s" % (backend, "; ".join(problems))
        summaries.append(summary)
    proofs = []
    for label, new in (("direct call_claude", OLD_CALL), ("budget empty", EMPTY_BUDGET_CALL)):
        try:
            neutralised = _neutralised_function(new)
        except AssertionError as exc:
            return "FAIL", str(exc)
        broken, _ = _case(neutralised, "local_producer")
        if not broken:
            return "FAIL", "with the memo call neutralised (%s) the local case still passed; the check proves nothing" % label
        again, _ = _case(shipped, "local_producer")
        if again:
            return "FAIL", "after restoring (%s), the local case fails: %s" % (label, "; ".join(again))
        proofs.append("%s FAILS: %s" % (label, "; ".join(broken)))
    return "PASS", ("%s; the real backend functions ran on stand-ins, every other backend function raising, evidence, "
                    "activation row, reply record (allowance %d) and free_text outcome on one call id; on both cloud "
                    "backends a memo at its output limit is marked in the run summary and the shipped copy, and no "
                    "other is; a damaged record is skipped; neutralise: %s; "
                    "restore PASSES" % ("; ".join(summaries), BUDGET, " | ".join(proofs)))


if __name__ == "__main__":
    print(json.dumps(check()))
