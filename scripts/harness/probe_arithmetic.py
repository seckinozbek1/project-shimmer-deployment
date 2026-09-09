"""Can the model do the arithmetic at all, with no review framing whatsoever.

The wide review asked a model to read a document, hold twelve rules in mind, do
the arithmetic and produce a verdict, all in one call, and it found nothing. That
failure has at least three candidate causes and they need separating. This probe
removes every one of them except the arithmetic: no agent identity, no
constitution, no conventions, no document, no output contract. Only figures and a
question, with the answer constrained to one JSON field.

If accuracy here is high, arithmetic is not the bottleneck and the fix belongs in
framing and output format. If it is low, no amount of prompt work will save it and
the arithmetic has to move into Python. Either answer is worth having before the
review path is rebuilt around a guess.

Numbers are generated here from a seeded random source. Nothing is read from the
operator's corpus, so a probe case can never be a figure under review.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from harness.run_agent import API, LOCAL, apply_profile, build_orchestrator  # noqa: E402

KINDS = ("sum", "ratio", "product")
DEFAULT_CASES = 10
# Two decimal places is the tolerance for a ratio; a sum and a product are exact.
RATIO_TOLERANCE = 0.011


def _fmt(x):
    """Plain decimal, no thousands separators, so the prompt cannot be blamed for
    a separator misreading. Separator handling is a different question."""
    if isinstance(x, int) or float(x).is_integer():
        return str(int(x))
    return ("%.2f" % x).rstrip("0").rstrip(".")


def make_cases(kind, n=DEFAULT_CASES, seed=20260907):
    """Synthetic cases. Same seed gives the same cases on every backend, so the
    two backends are compared on identical arithmetic."""
    rng = random.Random(seed + KINDS.index(kind))
    cases = []
    for i in range(n):
        if kind == "sum":
            parts = [round(rng.uniform(1, 400), 1) for _ in range(rng.randint(3, 5))]
            expected = round(sum(parts), 1)
            prompt = ("Add these numbers.\n"
                      + "\n".join("x%d = %s" % (j + 1, _fmt(p)) for j, p in enumerate(parts))
                      + '\n\nReply with JSON only, no words: {"answer": <the total>}')
        elif kind == "ratio":
            a = round(rng.uniform(50, 900), 1)
            b = round(rng.uniform(2, 60), 1)
            expected = round(a / b, 2)
            prompt = ("Divide the first number by the second.\n"
                      "a = %s\nb = %s\n\n"
                      'Reply with JSON only, no words: {"answer": <a divided by b, '
                      'two decimal places>}' % (_fmt(a), _fmt(b)))
        else:
            a = round(rng.uniform(20, 500), 1)
            b = rng.randrange(400, 40000, 50)
            c = rng.randrange(4000, 4000000, 500)
            expected = "product" if a * b > c else "c"
            prompt = ("Compare two quantities.\n"
                      "a = %s\nb = %s\nc = %s\n\n"
                      'Which is larger, a times b, or c? Reply with JSON only, no '
                      'words: {"answer": "product"} if a times b is larger, '
                      '{"answer": "c"} otherwise.' % (_fmt(a), _fmt(b), _fmt(c)))
        cases.append({"kind": kind, "index": i, "prompt": prompt, "expected": expected})
    return cases


def _answer_of(raw):
    """Pull the answer field out of whatever came back, tolerantly."""
    for m in re.finditer(r"\{[^{}]*\}", raw or "", re.DOTALL):
        try:
            obj = json.loads(m.group(0))
        except Exception:
            continue
        if isinstance(obj, dict) and "answer" in obj:
            return obj["answer"]
    return None


def _correct(kind, expected, got):
    if got is None:
        return False
    if kind == "product":
        return str(got).strip().lower() == expected
    try:
        got_f = float(str(got).replace(",", "").replace(" ", ""))
    except ValueError:
        return False
    if kind == "ratio":
        return abs(got_f - float(expected)) <= RATIO_TOLERANCE
    return abs(got_f - float(expected)) <= 0.051


def probe(agent, *, profile=LOCAL, kinds=KINDS, n=DEFAULT_CASES, seed=20260907,
          orch=None, keys=None, api_backend=None, api_model=None,
          dispatch=None, max_new_tokens=96, cost_tracker=None):
    """Run every case and return one record per case plus a per-kind summary.

    `dispatch` is an injection point for the gate: pass a callable taking the
    prompt and returning raw text, and no model is contacted.
    """
    from agent_wrapper import load_api_keys
    import pipeline

    if dispatch is None:
        if orch is None:
            orch = build_orchestrator(cost_tracker=cost_tracker)
        if keys is None:
            keys = load_api_keys()
        backend, model = apply_profile(orch.registry, agent, profile,
                                       api_backend=api_backend, api_model=api_model)
        wrapper = pipeline._build_wrapper(agent, orch, keys)

        def dispatch(prompt):
            if wrapper.backend in ("qwen_local", "local_producer", "local_auditor"):
                r = wrapper.dispatch(prompt, "", max_new_tokens=max_new_tokens)
            else:
                r = wrapper.dispatch(prompt, "", max_tokens=max_new_tokens)
            return r.raw_text if r.ok else ""
    else:
        backend, model = "stub", "stub"

    records = []
    for kind in kinds:
        for case in make_cases(kind, n=n, seed=seed):
            t0 = time.monotonic()
            raw = dispatch(case["prompt"])
            elapsed = time.monotonic() - t0
            got = _answer_of(raw)
            records.append({
                "agent": agent, "profile": profile, "backend": backend, "model": model,
                "kind": kind, "index": case["index"],
                "parsed_an_answer": got is not None,
                "correct": _correct(kind, case["expected"], got),
                "latency_s": round(elapsed, 3),
                "raw_len": len(raw or ""),
            })
    return records, summarize(records)


def summarize(records):
    out = {}
    for kind in KINDS:
        rows = [r for r in records if r["kind"] == kind]
        if not rows:
            continue
        out[kind] = {
            "cases": len(rows),
            "answered": sum(1 for r in rows if r["parsed_an_answer"]),
            "correct": sum(1 for r in rows if r["correct"]),
            "accuracy": round(sum(1 for r in rows if r["correct"]) / len(rows), 3),
            "median_latency_s": round(statistics.median(r["latency_s"] for r in rows), 3),
        }
    rows = records
    if rows:
        out["overall"] = {
            "cases": len(rows),
            "correct": sum(1 for r in rows if r["correct"]),
            "accuracy": round(sum(1 for r in rows if r["correct"]) / len(rows), 3),
            "median_latency_s": round(statistics.median(r["latency_s"] for r in rows), 3),
        }
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--agent", required=True,
                   help="whose backend and model to borrow; the probe sends no agent framing")
    p.add_argument("--profile", choices=(LOCAL, API), default=LOCAL)
    p.add_argument("--cases", type=int, default=DEFAULT_CASES)
    p.add_argument("--seed", type=int, default=20260907)
    p.add_argument("--api-backend", default=None)
    p.add_argument("--api-model", default=None)
    p.add_argument("--max-new-tokens", type=int, default=96)
    p.add_argument("--cost-dir", default=None,
                   help="meter every call into a CostTracker here; required "
                        "discipline for any run that costs the operator money")
    p.add_argument("--out", default=None)
    a = p.parse_args(argv)

    tracker = None
    if a.cost_dir:
        from cost_tracker import CostTracker
        tracker = CostTracker.open(Path(a.cost_dir), print_live=False)
    records, summary = probe(a.agent, profile=a.profile, n=a.cases, seed=a.seed,
                             api_backend=a.api_backend, api_model=a.api_model,
                             max_new_tokens=a.max_new_tokens, cost_tracker=tracker)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"records": records, "summary": summary},
                                          indent=2) + "\n", encoding="utf-8")
    for kind, s in summary.items():
        print("%-8s cases=%-3d correct=%-3d accuracy=%.2f median=%.1fs" % (
            kind, s["cases"], s["correct"], s["accuracy"], s["median_latency_s"]))
    if tracker is not None:
        state = tracker.get_live_state()
        print("calls=%d failures=%d spent=$%.4f"
              % (state["total_calls"], state["total_failures"], state["total_cost_usd"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
