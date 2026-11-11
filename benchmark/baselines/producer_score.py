"""Scoring of the producer's candidate against checkpoint 168, and the held-out gate (D-S72, D-330).

docs/loop/PRODUCER_TRAINING_PLAN.md section 8 is the rule; this is the rule in code. Laptop-side, no
model, reading saved measurements only (replay_measurement.json and its prompts file).

  tuning   py -3.12 benchmark/baselines/producer_score.py tuning --attempt N --test-prompts T
               --measurement D/replay_measurement.json --roles-prompts O
               --roles-measurement D/passes/roles/replay_measurement.json --out R [--previous P]
      The tuning record: (a) no loss on DEV-84 (the invalid rows of the candidate are exactly 168's),
      (b-T) the 27 partitions unconstrained, (c-T) the 48 fresh rows equal to target on the
      constrained path, (d) no role worse, each sign test at TUNING_ALPHA; and real progress
      against the previous attempt's record. Counts only.

  heldout-assemble / heldout-score
      Refused unless docs/loop/HELDOUT_OPENINGS.md, as COMMITTED (git show <commit>:path), holds the
      line of this part and attempt with this held-out material's digests and a tuning record
      commit, and that commit's tuning record, as committed, passed and names this attempt. The
      opening's k gives alpha 0.05 / 2^k. A held-out score is pass or fail with its counts: no item
      is named (LESSONS L-4).
"""
import argparse
import base64
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PART = "producer PROCESSOR candidate"
OPENINGS = "docs/loop/HELDOUT_OPENINGS.md"
RECORDS = "docs/loop/producer_attempts"
TUNING_ALPHA = 0.0125
FAMILY_ALPHA = 0.05
PROGRESS_MIN = 3
HELDOUT_SCHEMA = "producer-heldout-v1"


def _sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def sign_p(wins, losses):
    """One-sided sign test: P(X >= wins) for X ~ Binomial(wins + losses, 1/2); 1.0 with no discordant row."""
    n = wins + losses
    if n == 0 or wins <= losses:
        return 1.0
    return math.fsum(math.comb(n, i) for i in range(wins, n + 1)) / 2 ** n


def smallest_passes(alpha, max_losses=3):
    """[(wins, losses)]: for each count of losses, the fewest wins whose sign test is at most alpha."""
    out = []
    for losses in range(max_losses + 1):
        wins = losses + 1
        while sign_p(wins, losses) > alpha:
            wins += 1
        out.append((wins, losses))
    return out


def heldout_alpha(k):
    return FAMILY_ALPHA / 2 ** int(k)


def _rows(prompts_path, measurement_path):
    """{pair: {checkpoint: {path: row}}} with each pair's set, from a prompts file and its measurement."""
    prompts = {p["prompt_id"]: p for p in json.loads(Path(prompts_path).read_text(encoding="utf-8"))["prompts"]}
    measured = json.loads(Path(measurement_path).read_text(encoding="utf-8"))
    pairs = {}
    for row in measured["rows"]:
        p = prompts[row["prompt_id"]]
        entry = pairs.setdefault(p["pair_of"], {"set": p.get("set"), "by": {}})
        entry["by"][p["checkpoint"]] = {k: v for k, v in row.items() if k != "prompt_id"}
    return pairs


def _valid(row):
    return bool((row or {}).get("contract", {}).get("valid")) and not (row or {}).get("failure")


def _right(row):
    return bool((row or {}).get("reference_identical")) and not (row or {}).get("failure")


def discordant(pairs, prefix, path, judge):
    wins = losses = n = 0
    for entry in pairs.values():
        if not str(entry["set"]).startswith(prefix):
            continue
        n += 1
        tuned, cand = (judge(entry["by"].get(c, {}).get(path)) for c in ("tuned", "candidate"))
        wins += int(cand and not tuned)
        losses += int(tuned and not cand)
    return {"rows": n, "candidate_only": wins, "tuned_only": losses, "net": wins - losses, "p": sign_p(wins, losses)}


def dev_check(pairs):
    invalid = {c: sorted(k for k, e in pairs.items() if str(e["set"]).startswith("dev")
                         and not _valid(e["by"].get(c, {}).get("sdpa_constrained"))) for c in ("tuned", "candidate")}
    return {"rows": sum(1 for e in pairs.values() if str(e["set"]).startswith("dev")),
            "tuned_invalid": len(invalid["tuned"]), "candidate_invalid": len(invalid["candidate"]),
            "same_rows": invalid["tuned"] == invalid["candidate"]}


def roles_check(roles_measurement_path):
    pairs = json.loads(Path(roles_measurement_path).read_text(encoding="utf-8")).get("pairs", {}).get("sdpa", {})
    worse = {}
    for role, c in pairs.items():
        names = c["checkpoints"]
        tuned_only = c["a_only_valid"] if names[0] == "tuned" else c["b_only_valid"]
        cand_only = c["b_only_valid"] if names[0] == "tuned" else c["a_only_valid"]
        worse[role] = {"tuned_only": tuned_only, "candidate_only": cand_only, "p_tuned_better": sign_p(tuned_only, cand_only)}
    return {"roles": worse, "none_worse": all(v["p_tuned_better"] > TUNING_ALPHA for v in worse.values()) and bool(worse)}


def tuning(attempt, test_prompts, measurement, roles_prompts, roles_measurement, previous=None):
    pairs = _rows(test_prompts, measurement)
    a = dev_check(pairs)
    b = discordant(pairs, "partitions_tune", "sdpa", _valid)
    c = discordant(pairs, "fresh_tune", "sdpa_constrained", _right)
    d = roles_check(roles_measurement)
    better = b["p"] <= TUNING_ALPHA or c["p"] <= TUNING_ALPHA
    record = {"schema": "producer-tuning-record-v1", "part": PART, "attempt": int(attempt), "alpha": TUNING_ALPHA,
              "a_no_dev_loss": a, "b_partitions_tune": b, "c_fresh_tune": c, "d_roles": d,
              "passed": bool(a["same_rows"] and d["none_worse"] and better),
              "smallest_passes": smallest_passes(TUNING_ALPHA),
              "test_prompts_sha256": _sha(Path(test_prompts).read_bytes()), "measurement_sha256": _sha(Path(measurement).read_bytes())}
    prior = json.loads(Path(previous).read_text(encoding="utf-8")) if previous else None
    base_b = prior["b_partitions_tune"]["net"] if prior else 0
    base_c = prior["c_fresh_tune"]["net"] if prior else 0
    record["real_progress"] = bool(a["same_rows"] and d["none_worse"]
                                   and (b["net"] - base_b >= PROGRESS_MIN or c["net"] - base_c >= PROGRESS_MIN))
    record["progress_against"] = "attempt %d" % prior["attempt"] if prior else "checkpoint 168"
    return record


# The held-out gate

def _git_show(commit, path, root=ROOT):
    done = subprocess.run(["git", "-C", str(root), "show", "%s:%s" % (commit, path)], capture_output=True, text=True,
                          encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if done.returncode != 0:
        raise ValueError("not committed: %s at %s" % (path, commit))
    return done.stdout


def openings(text):
    """The table rows of HELDOUT_OPENINGS.md, as dicts by column."""
    lines = [l for l in text.splitlines() if l.startswith("|")]
    if len(lines) < 2:
        return []
    head = [c.strip() for c in lines[0].strip("|").split("|")]
    return [dict(zip(head, (c.strip() for c in l.strip("|").split("|")))) for l in lines[2:]]


def gate(attempt, material, commit="HEAD", root=ROOT, show=_git_show):
    """(k, alpha) for this attempt's held-out opening, or ValueError: the committed openings file has
    this part's line for this attempt naming every held-out file's digest and a tuning record commit,
    and that commit's tuning record passed and names this attempt."""
    rows = [r for r in openings(show(commit, OPENINGS, root)) if r.get("Part") == PART and r.get("Attempt") == str(attempt)]
    if len(rows) != 1:
        raise ValueError("HELDOUT_OPENINGS.md, as committed, has no single line for %s attempt %s" % (PART, attempt))
    row = rows[0]
    named = row.get("Held-out material (file, digest)", "")
    for path in material:
        if _sha(Path(path).read_bytes()) not in named:
            raise ValueError("the opening does not name this held-out file's digest: " + Path(path).name)
    match = re.search(r"[0-9a-f]{7,40}", row.get("Tuning pass record (commit)", ""))
    if not match:
        raise ValueError("the opening names no tuning record commit")
    record = json.loads(show(match.group(0), "%s/attempt_%d_tuning.json" % (RECORDS, int(attempt)), root))
    if record.get("part") != PART or record.get("attempt") != int(attempt) or record.get("passed") is not True:
        raise ValueError("the committed tuning record did not pass for this attempt")
    k = int(row.get("k", "0") or 0)
    if k < 1 or abs(float(row.get("Alpha", "0") or 0) - heldout_alpha(k)) > 1e-9:
        raise ValueError("the opening's k and alpha disagree with 0.05 / 2^k")
    return k, heldout_alpha(k)


def heldout_assemble(attempt, adapter_dir, heldout_prompts, material, out, commit="HEAD", root=ROOT, show=_git_show):
    """The held-out test-only file (schema producer-heldout-v1): the paired held-out prompts and the
    candidate's saved adapter, base64, held to its digests. Refused unless the gate passes."""
    k, alpha = gate(attempt, material, commit, root, show)
    adapter = {}
    for name in ("adapter_model.safetensors", "adapter_config.json"):
        data = (Path(adapter_dir) / name).read_bytes()
        adapter[name] = {"sha256": _sha(data), "base64": base64.b64encode(data).decode("ascii")}
    text = Path(heldout_prompts).read_text(encoding="utf-8")
    value = {"schema": HELDOUT_SCHEMA, "part": PART, "attempt": int(attempt), "k": k, "alpha": alpha, "test_text": text,
             "test_sha256": _sha(text), "adapter": adapter}
    Path(out).write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8", newline="\n")
    return value


def heldout_score(attempt, test_prompts, measurement, material, commit="HEAD", root=ROOT, show=_git_show):
    """Pass or fail on the held-out part at its opening's alpha, counts only; refused unless the gate passes."""
    k, alpha = gate(attempt, material, commit, root, show)
    pairs = _rows(test_prompts, measurement)
    b = discordant(pairs, "partitions_heldout", "sdpa", _valid)
    c = discordant(pairs, "fresh_heldout", "sdpa_constrained", _right)
    keep = ("rows", "candidate_only", "tuned_only", "net", "p")
    return {"schema": "producer-heldout-result-v1", "part": PART, "attempt": int(attempt), "k": k, "alpha": alpha,
            "b": {x: b[x] for x in keep}, "c": {x: c[x] for x in keep}, "passed": b["p"] <= alpha or c["p"] <= alpha,
            "names_no_item": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("tuning")
    for name in ("--attempt", "--test-prompts", "--measurement", "--roles-prompts", "--roles-measurement", "--out"):
        t.add_argument(name, required=True)
    t.add_argument("--previous", default=None)
    s = sub.add_parser("passes")
    s.add_argument("--k", type=int, required=True)
    args = parser.parse_args(argv)
    if args.command == "passes":
        print(json.dumps({"k": args.k, "alpha": heldout_alpha(args.k), "smallest_passes": smallest_passes(heldout_alpha(args.k)),
                          "tuning": smallest_passes(TUNING_ALPHA)}))
        return 0
    record = tuning(args.attempt, args.test_prompts, args.measurement, args.roles_prompts, args.roles_measurement, args.previous)
    Path(args.out).write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: record[k] for k in ("attempt", "passed", "real_progress")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
