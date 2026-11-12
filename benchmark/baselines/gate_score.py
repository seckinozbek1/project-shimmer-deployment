"""The D-S92 gate's figures in each paper's metric (D-S99, D-376, D-380, GATE_SET.md section 7).

Pure functions over scored rows `{item_id, cluster, label, gold}` per arm (the system, B1, the cloud
reference), labels and gold in the adapter's own label space, as the scorer gives them. `cluster` is
the bootstrap's unit: the document for ContraDoc, the table for SciTab (a cluster bootstrap, D-S102
item 14). Every figure carries its item count and a 95 percent interval; a difference is resampled
paired, the same clusters for both arms.

  bar (a): the system at least 10 points above B1, and the interval of the difference above zero;
  bar (b): the system at most 5 points below the cloud reference, read on the point difference with
           its interval beside it (this set cannot prove non-inferiority, GATE_SET.md section 5).
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "benchmark" / "adapters") not in sys.path:
    sys.path.insert(0, str(ROOT / "benchmark" / "adapters"))

from common import metrics  # noqa: E402

BAR_ABOVE_B1 = 0.10
BAR_BELOW_CLOUD = 0.05
CONFIDENCE = 0.95        # a quick-subset read, steering only
FAMILY_ALPHA = 0.05      # the k-th claim read is judged at FAMILY_ALPHA / 2^k (D-403, D-373, D-330)
BOOTSTRAP_DRAWS = 2000
SEED = 20261109


def _adapter(benchmark):
    if benchmark == "contradoc":
        from contradoc import adapter
    elif benchmark == "scitab":
        from scitab import adapter
    else:
        raise ValueError("the gate scores contradoc and scitab, not %r" % benchmark)
    return adapter


def measure(benchmark, pairs, setting=None) -> float:
    """The paper's primary metric on (label, gold) pairs: ContraDoc binary judgment accuracy with
    ABSTAIN wrong; SciTab macro-F1 in the declared class setting (required, never read off the gold)."""
    adapter = _adapter(benchmark)
    if benchmark == "contradoc":
        if setting is not None:
            raise ValueError("ContraDoc declares no class setting")
        return metrics.accuracy(pairs)["accuracy"]
    return adapter.headline(pairs, setting=setting)["macro_f1"]


def _check(arms):
    names = sorted(arms)
    keys = {n: sorted(r["item_id"] for r in arms[n]) for n in names}
    first = keys[names[0]]
    for n in names:
        if len(set(keys[n])) != len(keys[n]):
            raise ValueError("arm %s scores an item twice" % n)
        if keys[n] != first:
            raise ValueError("arm %s does not score the same items as arm %s" % (n, names[0]))
    golds = {r["item_id"]: (r["gold"], r["cluster"]) for r in arms[names[0]]}
    for n in names:
        for r in arms[n]:
            if golds[r["item_id"]] != (r["gold"], r["cluster"]):
                raise ValueError("arm %s gives item %s another gold or cluster" % (n, r["item_id"]))


def level(claim_read=None) -> float:
    """The interval's level: 95 percent on a quick-subset read; 1 - .05 / 2^k on the k-th claim read."""
    if claim_read is None:
        return CONFIDENCE
    if not (isinstance(claim_read, int) and not isinstance(claim_read, bool) and claim_read >= 1):
        raise ValueError("a claim read is numbered from 1 (its opening in HELDOUT_OPENINGS.md)")
    return 1 - FAMILY_ALPHA / 2 ** claim_read


LOOP_REF = "refs/heads/loop/2026-10-27"
DECISIONS = "docs/loop/DECISIONS.md"
QUICK_EVIDENCE_MARK = "**Quick-subset evidence.**"   # D-422: the declared marker line of a decision
TAIL_DRAWS = 20                                      # bootstrap draws in each tail at least


OPENINGS = "docs/loop/HELDOUT_OPENINGS.md"
# The frozen gate set's two digests, pinned here when GATE_SET.md section 10 is committed: the SHA-256 of
# `claim_set_ids.json` and of `quick_set_ids.json`, two separate files `gate_set.py freeze` writes (never
# the ids files of the draw, which hold both sets). Until then no gate read is possible: `figures`
# refuses any other set. Only `figures`' output may be recorded as a gate figure.
CLAIM_SET_SHA256 = "b0a942ad5dd3ba9a544beb4296056d030b73a8e8a18dd0e98e39ecee66d2357e"   # D-543
QUICK_SET_SHA256 = "0127b0809d762fcd4d33602e54cb4ef39a9e727442fcccbdf541104e3283a1f1"   # D-543


def _loop_text(path) -> str:
    """A file as the loop branch holds it, by git; refused when git cannot say."""
    shown = subprocess.run(["git", "-C", str(ROOT), "show", "%s:%s" % (LOOP_REF, path)], capture_output=True, text=True,
                           encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if shown.returncode != 0:
        raise ValueError("git cannot read %s on the loop branch: no gate read" % path)
    return shown.stdout


def decision_names_quick_evidence(decision) -> bool:
    """Whether `decision` (D-NNN) is on the loop branch's DECISIONS.md and its entry carries the
    declared marker line naming the quick-subset evidence that motivated the change (D-422)."""
    if not re.fullmatch(r"D-\d+", str(decision or "")):
        return False
    text = _loop_text(DECISIONS)
    entry = re.search(r"^## %s\.(.*?)(?=^## D-\d+\.|\Z)" % re.escape(decision), text, re.M | re.S)
    return bool(entry) and any(line.strip().lstrip("- ").startswith(QUICK_EVIDENCE_MARK) for line in entry.group(1).splitlines())


def draws_for(confidence, draws=None) -> int:
    """At least TAIL_DRAWS draws in each tail at this level (audit item 14)."""
    base = BOOTSTRAP_DRAWS if draws is None else draws
    return max(base, math.ceil(TAIL_DRAWS / ((1 - confidence) / 2)))


def _interval(values, confidence=CONFIDENCE):
    values = sorted(values)
    lo = values[int((1 - confidence) / 2 * len(values))]
    hi = values[min(len(values) - 1, int((1 + confidence) / 2 * len(values)))]
    return [round(lo, 6), round(hi, 6)]


CLAIM_PART = "gate-claim-set"   # the Part column of the claim set's opening rows in HELDOUT_OPENINGS.md


def claim_read_number(set_sha256) -> int:
    """The read's number (D-444): the rows of HELDOUT_OPENINGS.md's table on the loop branch whose Part
    column is exactly CLAIM_PART and whose cells carry the claim set's digest written in full, as its own
    64-hex token, the current read's own opening included (committed before the read, D-330). A freeze
    line, a steering row (another Part) and a row giving the digest as a prefix are not counted; the rows
    must be numbered 1, 2, ... in their k column, in order."""
    count, wanted = 0, set_sha256.lower()
    for line in _loop_text(OPENINGS).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.lstrip().startswith("|") else []
        if len(cells) < 2 or cells[0] != CLAIM_PART:
            continue
        tokens = re.findall(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", " ".join(cells[2:]).lower())
        if not tokens:
            raise ValueError("a %s row gives no full digest: no claim read" % CLAIM_PART)
        if wanted not in tokens:
            continue
        count += 1
        if cells[1] != str(count):
            raise ValueError("the claim set's opening rows are not numbered in order: row %d says k %s" % (count, cells[1]))
    return count


def set_items(set_file, benchmark):
    """(digest, {item id: document id}) of a frozen set file for one benchmark, its opaque ids."""
    raw = Path(set_file).read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if benchmark == "contradoc":
        items = {r["item_id"]: r["document_id"] for r in value.get("contradoc") or []}
    else:
        items = {i: r["document_id"] for r in value.get("scitab") or [] for i in r["item_ids"]}
    return hashlib.sha256(raw).hexdigest(), items


def system_arm(benchmark, runs, by_key, set_file) -> list:
    """The system's arm for `figures`: one row {item_id, cluster, label, gold} per item of the runs
    (`runs` {document id: run folder}, `by_key` {document id: its key file}), labelled by the adapter's
    own labeller through the scorer in the mode declared for THIS benchmark (system_test.SCORING,
    D-476: ContraDoc v2_primary, SciTab detection_dev), in the adapter's own label space, each item's
    cluster the document the set file lists it under. The key is read by the scorer alone."""
    import system_test
    spec = _adapter(benchmark).SPEC
    _sha, listed = set_items(set_file, benchmark)
    rows = []
    for row in system_test.system_rows(runs, by_key, benchmark):
        if row["item_id"] not in listed:
            raise ValueError("item %s is not in the set file" % row["item_id"])
        rows.append({"item_id": row["item_id"], "cluster": listed[row["item_id"]],
                     "label": spec.label(row["cls"]), "gold": spec.label(row["gold"])})
    return rows


def figures(benchmark, arms, set_file, setting=None, decision=None, seed=SEED) -> dict:
    """The one way a gate figure is made (audit gap 2): bound to the frozen set FILE, whose digest must
    be one of the two pins, and whose items the arms must score exactly, each under its own document. The
    quick subset is a steering read at 95 percent; the claim set is read at the k-th claim read's level,
    k counted from the committed openings that name it, never supplied; a k above 1 needs a committed
    decision carrying the quick-subset evidence marker (D-422)."""
    set_sha256, listed = set_items(set_file, benchmark) if set_file else (None, {})
    if not set_sha256 or set_sha256 not in {CLAIM_SET_SHA256, QUICK_SET_SHA256} - {None}:
        raise ValueError("not the frozen gate set's claim set or quick subset: no gate read")
    for name, rows in arms.items():
        scored = {r["item_id"]: r["cluster"] for r in rows}
        if scored != listed:
            raise ValueError("arm %s does not score exactly the items of the set file it names" % name)
    if set_sha256 == QUICK_SET_SHA256:
        out = compute(benchmark, arms, setting, seed=seed)
        out.update(read="steering only", set_sha256=set_sha256)
        return out
    k = claim_read_number(set_sha256)
    if k < 1:
        raise ValueError("no opening for this claim read is committed in %s: no claim read" % OPENINGS)
    if k > 1 and not decision_names_quick_evidence(decision):
        raise ValueError("a claim read after the first needs a committed decision naming its quick-subset evidence (D-422)")
    confidence = level(k)
    out = compute(benchmark, arms, setting, draws=draws_for(confidence), seed=seed, confidence=confidence)
    out.update(read="claim read %d" % k, claim_read=k, set_sha256=set_sha256, decision=decision)
    return out


def compute(benchmark, arms, setting=None, draws=BOOTSTRAP_DRAWS, seed=SEED, confidence=CONFIDENCE) -> dict:
    """The computation behind a gate read: each arm's metric with its interval, and the system's
    differences from B1 and from the cloud reference with theirs, by one paired cluster bootstrap.
    `arms` holds `system` and `b1`, and `cloud` when the cloud reference was run. Its output is not a
    gate figure; `figures` is."""
    if "system" not in arms or "b1" not in arms:
        raise ValueError("the gate needs the system and B1 on the same items")
    _check(arms)
    by_cluster = {n: {} for n in arms}
    for n, rows in arms.items():
        for r in rows:
            by_cluster[n].setdefault(r["cluster"], []).append((r["label"], r["gold"]))
    clusters = sorted(by_cluster["system"])
    point = {n: measure(benchmark, [p for c in clusters for p in by_cluster[n][c]], setting) for n in arms}
    rng = random.Random(seed)
    samples = {n: [] for n in arms}
    for _ in range(draws):
        pick = [clusters[rng.randrange(len(clusters))] for _c in clusters]
        for n in arms:
            samples[n].append(measure(benchmark, [p for c in pick for p in by_cluster[n][c]], setting))
    items = len(arms["system"])
    out = {"benchmark": benchmark, "class_setting": setting, "items": items, "clusters": len(clusters),
           "cluster": "document" if benchmark == "contradoc" else "table", "draws": draws, "seed": seed,
           "measure": "binary judgment accuracy, ABSTAIN wrong" if benchmark == "contradoc"
           else "%s macro-F1 (declared, D-380)" % setting,
           "arms": {n: {"value": round(point[n], 6), "interval": _interval(samples[n], confidence), "items": items} for n in sorted(arms)},
           "level": confidence, "read": "computation, not a gate read"}
    diff_b1 = [s - b for s, b in zip(samples["system"], samples["b1"])]
    a_point = point["system"] - point["b1"]
    a_int = _interval(diff_b1, confidence)
    out["above_b1"] = {"value": round(a_point, 6), "interval": a_int, "items": items,
                       "bar_a": round(a_point, 9) >= BAR_ABOVE_B1 and a_int[0] > 0,
                       "gain_called": a_int[0] > 0}
    if "cloud" in arms:
        diff_c = [s - c for s, c in zip(samples["system"], samples["cloud"])]
        b_point = point["system"] - point["cloud"]
        out["against_cloud"] = {"value": round(b_point, 6), "interval": _interval(diff_c, confidence), "items": items,
                                "bar_b": round(b_point, 9) >= -BAR_BELOW_CLOUD,
                                "note": "read on the point difference; this set cannot prove non-inferiority (GATE_SET.md section 5)"}
    else:
        out["against_cloud"] = {"bar_b": None, "note": "the cloud reference was not run on these items"}
    return out
