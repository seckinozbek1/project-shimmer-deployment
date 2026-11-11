"""Proofs of the judge's success rule in code (benchmark/baselines/judge_success.py), on stand-ins only.

    py -3.12 -X utf8 tools/judge_success_checks.py

The gate reads committed text through an injected `show`, so the proofs need no repository state; one
proof runs it on a real temporary git repository. Neutralised proofs must fail. Exit 1 on any failure.
"""
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark" / "baselines"))
import judge_success as s  # noqa: E402

FAILED, PASSED = [], []


def proof(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    (PASSED if ok else FAILED).append(name)


def raises(fn, text):
    try:
        fn()
    except ValueError as exc:
        return text in str(exc)
    return False


LEDGER = """| Part | k | Alpha | Attempt | Held-out material (file, digest) | Tuning pass record (commit) | Written | Result |
|---|---|---|---|---|---|---|---|
| judge | 1 | 0.025 | 2e | reserve.json abc | rec.json | now | |
"""
PASSED_RECORD = json.dumps({"part": "judge", "attempt": "2e", "passed": True})


def shows(files):
    return lambda path: files.get(path)


def main():
    committed = shows({s.LEDGER: LEDGER, "rec.json": PASSED_RECORD})
    row = s.require_opening("judge", "2e", "rec.json", show=committed)
    proof("a committed opening and a committed passed tuning record admit the held-out score", row["k"] == 1)
    proof("refused: no ledger row for the attempt", raises(lambda: s.require_opening("judge", "2f", "rec.json", show=committed), "no committed held-out"))
    proof("refused: the ledger not committed", raises(lambda: s.require_opening("judge", "2e", "rec.json", show=shows({"rec.json": PASSED_RECORD})),
                                                      "no committed held-out"))
    proof("refused: no committed tuning record", raises(lambda: s.require_opening("judge", "2e", "rec.json", show=shows({s.LEDGER: LEDGER})),
                                                        "not committed"))
    failed = json.dumps({"part": "judge", "attempt": "2e", "passed": False})
    proof("refused: a tuning record that did not pass", raises(lambda: s.require_opening("judge", "2e", "rec.json",
                                                                                         show=shows({s.LEDGER: LEDGER, "rec.json": failed})), "does not show"))
    result = s.heldout_sign_test("judge", "2e", "rec.json", 9, 1, "scitab", show=committed)
    proof("the k-th opening is tested at 0.05 / 2^k", result["alpha"] == 0.025 and result["passed"] == (result["p"] <= 0.025))
    proof("refused: a held-out test on another benchmark than the one named", raises(
        lambda: s.heldout_sign_test("judge", "2e", "rec.json", 9, 1, "contradoc", show=committed), "named in advance"))
    proof("B1 and the D-S73 bars stand beside the result", result["beside"]["bars"]["scitab"]["macro_f1"] == 0.65
          and result["beside"]["bars"]["contradoc"]["accuracy"] == 0.681 and result["beside"]["b1"]["scitab"]["macro_f1"] == 0.838)
    proof("the sign test", abs(s.sign_test(9, 1) - 11 / 1024) < 1e-12 and s.sign_test(0, 0) == 1.0)
    # Neutralised: a gate that admits anything must let the uncommitted case through, and so fail the proof.
    real = s.require_opening
    s.require_opening = lambda *a, **k: {"k": 1}
    try:
        leaked = not raises(lambda: s.heldout_sign_test("judge", "2f", "rec.json", 9, 1, "scitab", show=shows({})), "no committed")
    finally:
        s.require_opening = real
    proof("neutralised: a gate that admits anything is caught", leaked)
    # The real git path: committed text is read from HEAD, not the working tree.
    with tempfile.TemporaryDirectory() as folder:
        repo = Path(folder)
        run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, check=True)
        run("init", "-q")
        run("config", "user.email", "p@example.invalid")
        run("config", "user.name", "proof")
        (repo / "docs" / "loop").mkdir(parents=True)
        (repo / s.LEDGER).write_text(LEDGER, encoding="utf-8")
        (repo / "rec.json").write_text(PASSED_RECORD, encoding="utf-8")
        proof("refused: a ledger written but not committed", raises(lambda: s.require_opening("judge", "2e", "rec.json", repo=repo), "no committed"))
        run("add", "-A")
        run("commit", "-q", "-m", "opening")
        proof("admitted once committed", s.require_opening("judge", "2e", "rec.json", repo=repo)["k"] == 1)
    # One threshold rule for both judges: each judge's rows go through the same choose_threshold.
    calls = []
    cr = types.SimpleNamespace(choose_threshold=lambda b, d, rows, f, k, o, l, b1, tag: calls.append((b, tuple(rows), tag)) or (0.7, {"rows": len(rows)}))
    got = s.tuning_thresholds("scitab", {}, {"base": [1, 2], "trained": [3]}, {}, [], "out", set(), {}, cr)
    proof("both judges take their threshold by the one rule on half A", sorted(got) == ["base", "trained"]
          and [c[0] for c in calls] == ["scitab", "scitab"] and got["trained"] == (0.7, {"rows": 1}))
    print("judge success checks: %d proofs passed%s" % (len(PASSED), ", FAILED %d" % len(FAILED) if FAILED else ", all passed"))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
