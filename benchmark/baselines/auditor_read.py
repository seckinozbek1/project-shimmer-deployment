"""The auditor rule check's reads (docs/loop/stages/AUDITOR_RULE_CHECK_SUCCESS.md, D-S72, D-330).

    read-a  --session-out D --questions Q --attempt N --out R [--calibration prior_offset]
        Half A only: every candidate's macro-F1 on half A, the selected candidate (highest, a tie to
        permissive_mix, then the earlier checkpoint), its margin over the untrained form, and each
        not_met threshold of the grid. Writes the half-A record R. Half B's rows are skipped where
        the decision files are read, before any figure is formed. With --calibration prior_offset
        (attempt 2, docs/loop/stages/AUDITOR_RULE_CHECK_ATTEMPT_2.md), each arm's decision is the
        argmax of log probability plus a per-label offset fitted on that arm's own half-A rows
        (`fit_offsets`), the untrained form included; the offsets are frozen in the record and
        read-b applies them, unrefitted, to half B.

    read-b  --session-out D --questions Q --record R --attempt N --candidate MIX@CHECKPOINT --repo G --out S
        Half B, for one candidate, only when (1) the COMMITTED docs/loop/HELDOUT_OPENINGS.md at G's
        HEAD holds a row for this part, attempt and candidate naming half B's digest and the commit
        of the half-A record, and (2) that record, as committed there, shows half A passed for the
        same attempt, the same decisions and the same candidate. Otherwise it refuses before reading
        any half-B row. It tests half B at the row's alpha (0.05 / 2^k, one-sided) and writes S.

The decisions are the session's own decisions.jsonl files (benchmark/baselines/auditor_train.py):
labels, probabilities and ids, no text. No model, no network, no key.
"""
import argparse
import hashlib
import json
import math
import random
import re
import subprocess
import sys
from pathlib import Path

PART = "auditor_rule_check"
LABELS = ("met", "not_met", "cannot be settled")
MARGIN = 0.05
PRECISION_FLOOR = 0.80
MIN_SETTLED_NO = 10
GRID = tuple(round(0.50 + 0.05 * i, 2) for i in range(10))
BOOTSTRAP = 2000
SEED = 20261108
OPENINGS = "docs/loop/HELDOUT_OPENINGS.md"
RECORD_SCHEMA = "auditor-rule-check-half-a-v1"
MIXES = ("dev_mix", "permissive_mix")
CHECKPOINTS = ("trained_half", "trained_full")
CALIBRATIONS = ("prior_offset",)
# Offsets on log probability for not_met and cannot be settled (met is the reference at 0).
OFFSET_GRID = tuple(i / 4 for i in range(-12, 13))


class ReadRefused(ValueError):
    """A read the success rule does not allow."""


def _sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def decision_files(session_out):
    """{candidate: decisions.jsonl} as auditor_train.run lays them out: dev_mix's passes under
    passes/dev_mix/, permissive_mix's earlier passes under passes/permissive_mix/ and its last in D."""
    out = Path(session_out)
    files = {"base": out / "passes" / "dev_mix" / "base" / "decisions.jsonl"}
    for mix in MIXES:
        for name in CHECKPOINTS:
            files["%s@%s" % (mix, name)] = out / "passes" / mix / name / "decisions.jsonl"
    files["permissive_mix@trained_full"] = out / "decisions.jsonl"
    return files


def _rows(path, half, questions):
    """The rows of one half, joined to their gold answer from the questions file; rows of the other
    half are dropped as they are read."""
    gold = {q["question_id"]: q for q in questions if q["half"] == half}
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("half") != half:
            continue
        q = gold[row["question_id"]]
        out.append(dict(row, gold=q["answer"], document_id=q["document_id"]))
    if len(out) != len(gold):
        raise ReadRefused("a decisions file does not hold every question of half %s" % half)
    return out


def _top(row):
    probs = row.get("probabilities") or {}
    return row.get("top") or (max(probs, key=probs.get) if probs else None)


def macro_f1(rows):
    scores = []
    for label in LABELS:
        tp = sum(1 for r in rows if _top(r) == label and r["gold"] == label)
        fp = sum(1 for r in rows if _top(r) == label and r["gold"] != label)
        fn = sum(1 for r in rows if _top(r) != label and r["gold"] == label)
        scores.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return sum(scores) / len(scores)


def precision_at(rows, threshold):
    """(not_met precision, settled No count) at `threshold`: a settled No is a top answer not_met
    whose probability is at least the threshold."""
    settled = [r for r in rows if _top(r) == "not_met" and (r.get("probabilities") or {}).get("not_met", 0) >= threshold]
    right = sum(1 for r in settled if r["gold"] == "not_met")
    return (right / len(settled) if settled else None), len(settled)


def threshold(rows):
    """The lowest grid value with not_met precision at least the floor on at least MIN_SETTLED_NO
    settled No answers; None means no usable threshold."""
    for t in GRID:
        p, n = precision_at(rows, t)
        if n >= MIN_SETTLED_NO and p is not None and p >= PRECISION_FLOOR:
            return t
    return None


def _digests(files):
    return {name: _sha(Path(path).read_bytes()) for name, path in sorted(files.items())}


def _select(scores):
    """Highest half-A macro-F1; a tie to permissive_mix, then the earlier checkpoint."""
    order = {"permissive_mix@trained_half": 0, "permissive_mix@trained_full": 1,
             "dev_mix@trained_half": 2, "dev_mix@trained_full": 3}
    return max(order, key=lambda c: (round(scores[c], 12), -order[c]))


def calibrated(rows, offsets):
    """The rows with `top` set to the argmax of log probability plus each label's offset."""
    out = []
    for row in rows:
        probs = row.get("probabilities") or {}
        score = {label: math.log(max(float(probs.get(label, 0.0)), 1e-12)) + float(offsets.get(label, 0.0))
                 for label in LABELS}
        out.append(dict(row, top=max(LABELS, key=lambda label: (score[label], -LABELS.index(label)))))
    return out


def fit_offsets(rows):
    """The offsets (not_met, cannot be settled) on OFFSET_GRID with the highest macro-F1 on `rows`;
    a tie to the smallest total offset, then the lower not_met, then the lower cannot offset."""
    best = max((macro_f1(calibrated(rows, {"not_met": a, "cannot be settled": b})), -(abs(a) + abs(b)), -a, -b)
               for a in OFFSET_GRID for b in OFFSET_GRID)
    return {"not_met": -best[2], "cannot be settled": -best[3]}


def read_a(session_out, questions_path, attempt, out, calibration=None):
    if calibration is not None and calibration not in CALIBRATIONS:
        raise ReadRefused("an unknown calibration")
    questions = json.loads(Path(questions_path).read_text(encoding="utf-8"))["questions"]
    files = decision_files(session_out)
    rows = {name: _rows(path, "A", questions) for name, path in files.items()}
    offsets = None
    if calibration == "prior_offset":
        offsets = {name: fit_offsets(r) for name, r in rows.items()}
        rows = {name: calibrated(r, offsets[name]) for name, r in rows.items()}
    scores = {name: macro_f1(r) for name, r in rows.items()}
    selected = _select({c: scores[c] for c in files if c != "base"})
    record = {"schema": RECORD_SCHEMA, "part": PART, "attempt": int(attempt),
              "questions_sha256": _sha(Path(questions_path).read_bytes()), "decisions_sha256": _digests(files),
              "half_a_macro_f1": scores, "selected": selected,
              "margin": scores[selected] - scores["base"], "margin_required": MARGIN,
              "thresholds": {name: threshold(r) for name, r in rows.items()}}
    if calibration is not None:
        record["calibration"] = calibration
        record["offsets"] = offsets
    record["passed_half_a"] = record["margin"] >= MARGIN
    Path(out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return record


def _git_show(repo, rev, path):
    done = subprocess.run(["git", "-C", str(repo), "show", "%s:%s" % (rev, path)], capture_output=True)
    if done.returncode != 0:
        raise ReadRefused("%s is not committed at %s" % (path, rev))
    return done.stdout.decode("utf-8")


def opening_row(repo, attempt, candidate, material_sha256):
    """The committed HELDOUT_OPENINGS.md row for this part, attempt and candidate: (k, alpha, the
    tuning record's commit). Columns: Part | k | Alpha | Attempt | Held-out material | Tuning pass
    record (commit) | Written | Result; the Attempt cell is `<n> <mix>@<checkpoint>`."""
    text = _git_show(repo, "HEAD", OPENINGS)
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else []
        if len(cells) < 6 or cells[0] != PART:
            continue
        if cells[3] != "%d %s" % (int(attempt), candidate) or material_sha256 not in cells[4]:
            continue
        k = int(cells[1])
        alpha = 0.05 / 2 ** k
        if abs(float(cells[2]) - alpha) > 1e-12:
            raise ReadRefused("the row's alpha is not 0.05 / 2^k")
        commit = re.search(r"\b[0-9a-f]{7,40}\b", cells[5])
        if not commit:
            raise ReadRefused("the row names no commit of the half-A record")
        return k, alpha, commit.group(0)
    raise ReadRefused("no committed opening of half B for attempt %s, candidate %s" % (attempt, candidate))


def _gain_bootstrap(trained, base, alpha):
    by_doc = {}
    for t, b in zip(trained, base):
        by_doc.setdefault(t["document_id"], []).append((t, b))
    docs = sorted(by_doc)
    rng = random.Random(SEED)
    gains = []
    for _ in range(BOOTSTRAP):
        pick = [d for d in (rng.choice(docs) for _ in docs)]
        t = [x for d in pick for x, _ in by_doc[d]]
        b = [y for d in pick for _, y in by_doc[d]]
        gains.append(macro_f1(t) - macro_f1(b))
    gains.sort()
    return gains[max(0, int(alpha * BOOTSTRAP) - 1)]


def read_b(session_out, questions_path, record_path, attempt, candidate, repo, out):
    questions_raw = Path(questions_path).read_bytes()
    questions = json.loads(questions_raw)["questions"]
    material = _sha(json.dumps(sorted((q["question_id"], q["user_sha256"], q["answer"])
                                      for q in questions if q["half"] == "B"), separators=(",", ":")))
    k, alpha, commit = opening_row(repo, attempt, candidate, material)
    committed = json.loads(_git_show(repo, commit, Path(record_path).as_posix()))
    files = decision_files(session_out)
    if committed.get("schema") != RECORD_SCHEMA or committed.get("part") != PART or committed.get("attempt") != int(attempt):
        raise ReadRefused("the committed half-A record is not this part's record for this attempt")
    if committed.get("passed_half_a") is not True:
        raise ReadRefused("the committed half-A record does not show half A passed")
    if committed.get("decisions_sha256") != _digests(files) or committed.get("questions_sha256") != _sha(questions_raw):
        raise ReadRefused("the decisions or questions are not the ones the half-A record read")
    if candidate != committed["selected"] and not (candidate.startswith("permissive_mix@")
                                                   and committed["selected"].startswith("dev_mix@")):
        raise ReadRefused("half B is opened for the selected candidate, or permissive_mix after a dev_mix selection")
    trained = _rows(files[candidate], "B", questions)
    base = _rows(files["base"], "B", questions)
    if committed.get("calibration") is not None:
        # Attempt 2's decision rule: half A's offsets, frozen in the committed record, never refitted.
        if committed["calibration"] not in CALIBRATIONS or not isinstance(committed.get("offsets"), dict):
            raise ReadRefused("the committed record names a calibration it does not carry")
        trained = calibrated(trained, committed["offsets"][candidate])
        base = calibrated(base, committed["offsets"]["base"])
    gain = macro_f1(trained) - macro_f1(base)
    lower = _gain_bootstrap(trained, base, alpha)
    t_threshold = committed["thresholds"].get(candidate)
    b_threshold = committed["thresholds"].get("base")
    t_prec, t_n = precision_at(trained, t_threshold) if t_threshold is not None else (None, 0)
    b_prec, b_n = precision_at(base, b_threshold) if b_threshold is not None else (None, 0)
    floor = t_prec is not None and t_n >= MIN_SETTLED_NO and t_prec >= PRECISION_FLOOR
    # Criterion 3: not below the untrained form's precision at its own half-A threshold; with no
    # usable untrained threshold that comparison is empty, and the floor alone decides.
    not_below = b_threshold is None or b_prec is None or (t_prec is not None and t_prec >= b_prec)
    result = {"part": PART, "attempt": int(attempt), "candidate": candidate, "opening_k": k, "alpha": alpha,
              "half_b_gain": gain, "gain_lower_bound": lower, "threshold": t_threshold,
              "not_met_precision": t_prec, "settled_no": t_n, "base_threshold": b_threshold,
              "base_not_met_precision": b_prec, "base_settled_no": b_n,
              "untrained_threshold_usable": b_threshold is not None,
              "criteria": {"gain": gain >= MARGIN, "lower_bound": lower > 0, "precision_floor": floor,
                           "not_below_untrained": not_below}}
    result["passed"] = all(result["criteria"].values())
    # A held-out part tells the next recipe pass or fail only (LESSONS L-4): no item, no per-row figure.
    Path(out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("read-a")
    for name in ("--session-out", "--questions", "--attempt", "--out"):
        a.add_argument(name, required=True)
    a.add_argument("--calibration", choices=CALIBRATIONS, default=None)
    b = sub.add_parser("read-b")
    for name in ("--session-out", "--questions", "--record", "--attempt", "--candidate", "--repo", "--out"):
        b.add_argument(name, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "read-a":
            value = read_a(args.session_out, args.questions, args.attempt, args.out, args.calibration)
            print(json.dumps({"selected": value["selected"], "margin": value["margin"], "passed_half_a": value["passed_half_a"]}))
        else:
            value = read_b(args.session_out, args.questions, args.record, args.attempt, args.candidate, args.repo, args.out)
            print(json.dumps({"passed": value["passed"]}))
    except ReadRefused as exc:
        print("read refused: %s" % exc, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
