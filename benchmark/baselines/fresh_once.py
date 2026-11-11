"""The fresh ContraDoc set is opened once, whatever reads it (D-316, D-326).

One layer shared by every read of the set (benchmark/baselines/system_test.py; fresh_test.py's
judge-alone read refuses outright):

- the KEY is the set alone: the sorted source ids of the ids file and each key's content digest.
  No adapter, no prompts file, no bar design enters it, so a second bar of any design is refused;
- the COUNT is the marker committed on the loop branch (round 3 ruling): only after it is READS_FILE,
  fixed in code, written as a second record, under an exclusive lock, before the scorer reads gold;
- the MARKER: the read writes its key into MARKER_FILE, a tracked file, and the procedure commits it
  on the loop branch before any result is reported. A read is refused when the key stands in any
  tracked file of any ref (git grep over every ref, no path filter) or in the marker file as it
  stands; git that cannot answer refuses;
- the GROUPS are pinned: D-S45's fresh groups file and role B's moved assignment, by digest;
- the ATTEMPT is read from ATTEMPTS_FILE as the LOOP branch holds it (never another checkout's
  HEAD), refused when the working copy differs, and tied to the marker: every key the loop branch's
  marker file names has its ledger row (carrying `set_key`), and every row its key;
- the MARKER COMMIT (lead's ruling on round 1 item 5): inside the opening, after the count and before
  the scorer reads any gold, the read writes its key into the marker file of the loop branch's own
  worktree and commits it there (index clean before, the precommit scan CLEAN and guard_secrets
  passing on the staged marker, the attribution lines); only once that commit exists on the loop
  branch does the caller read and report. The reads file stays a second record.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import subprocess
import time
from pathlib import Path

import choice_read as cr
import doc_judge

READS_FILE = "external/s05/D-S56/fresh_set_reads.jsonl"
MARKER_FILE = "docs/loop/FRESH_READS.md"
ATTEMPTS_FILE = "docs/loop/FRESH_ATTEMPTS.json"
LOOP_REF = "refs/heads/loop/2026-10-27"
ATTRIBUTION = ("Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
               "Claude-Session: https://claude.ai/code/session_01MCweyesS9qu8d2ZXoBLNzy")
PRECOMMIT_SCAN = "docs/loop/private/lead_tools/precommit_scan.py"
GROUP_FILES = {"unread": ("external/s05/D-S45/contradoc_unread_fresh_groups.json",
                          "8b6d8fd13832c4592981cf9c8627d71823971900b1c8cd731e01249de6c3f143"),
               "moved": ("external/contradoc/dev_moved/assignment_moved.json",
                         "1419ad7ed9d1cbb19fb5bc25a3cff99b9833abeed65b42c7e05ecd2c0a45d398")}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def set_key(ids_path, keys):
    """The set's key: its source ids and each key's content, nothing else."""
    sc = doc_judge._score_corpus()
    sources = sorted(json.loads(Path(ids_path).read_text(encoding="utf-8"))["documents"])
    return doc_judge._sha(json.dumps({"set": sources, "keys": sorted(sc.key_content_digest(k) for k in keys)}, sort_keys=True))


def groups(root=None):
    """{group key: [source ids]} from the two pinned files, each held to its digest."""
    root = Path(root or cr.repository_root())
    out = {}
    for name, (path, digest) in GROUP_FILES.items():
        path = root / path
        if _sha(path) != digest:
            raise ValueError("the %s groups file is not the pinned one" % name)
        value = json.loads(path.read_text(encoding="utf-8"))
        if name == "unread":
            out.update({g: list(m) for g, m in value["fresh_groups"].items()})
        else:
            for sid, row in value["assignments"].items():
                out.setdefault(row["group"], []).append(sid)
    return out


def _git(root, *args, timeout=600):
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=timeout,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None


def loop_worktree():
    """The worktree that has the loop branch checked out; refused when none has."""
    listed = _git(cr.repository_root(), "worktree", "list", "--porcelain", timeout=60)
    if listed is None or listed.returncode != 0:
        raise ValueError("git cannot list the worktrees: no read")
    path = None
    for line in listed.stdout.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):].strip()
        elif line.strip() == "branch " + LOOP_REF and path:
            return Path(path)
    raise ValueError("no worktree has the loop branch checked out: " + LOOP_REF)


def marker_named(key):
    """Whether `key` stands in any tracked file of any ref, or in a marker file as it stands (this
    checkout's or the loop worktree's)."""
    root = cr.repository_root()
    for marker in {root / MARKER_FILE, loop_worktree() / MARKER_FILE}:
        if marker.is_file() and key in marker.read_text(encoding="utf-8"):
            return True
    refs = _git(root, "for-each-ref", "--format=%(objectname)")
    if refs is None or refs.returncode != 0:
        raise ValueError("git cannot list the refs: no read")
    tips = sorted(set(refs.stdout.split()))
    if not tips:
        raise ValueError("git lists no ref: no read")
    found = _git(root, "grep", "-F", "-q", "-e", key, *tips)
    if found is None or found.returncode not in (0, 1):
        raise ValueError("git cannot say whether a commit names this read: no read")
    return found.returncode == 0


def write_marker(key, what, worktree):
    """Append the read's key to the marker file of `worktree` (the loop branch's)."""
    path = Path(worktree) / MARKER_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    head = "" if path.is_file() else "# Reads of the fresh ContraDoc set\n\nEach line is one read's key; commit it on the loop branch before reporting.\n\n"
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(head + "- %s %s %s\n" % (key, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), what))


def _loop_file(root, path):
    """A file as the loop branch holds it, or None when the branch has no such file; refused when git
    cannot say."""
    shown = _git(root, "show", "%s:%s" % (LOOP_REF, path), timeout=60)
    if shown is None:
        raise ValueError("git cannot read the loop branch: no read")
    if shown.returncode != 0:
        exists = _git(root, "rev-parse", "--verify", "-q", LOOP_REF, timeout=60)
        if exists is None or exists.returncode != 0:
            raise ValueError("the loop branch is not here: " + LOOP_REF)
        return None
    return shown.stdout


def attempt():
    """{number, earlier, ledger_sha256}: this attempt's number, one past the loop branch's ledger rows.
    Refused when the loop branch holds no ledger, when the working copy differs from it, or when the
    ledger and the loop branch's marker file do not name the same keys."""
    root = cr.repository_root()
    text = _loop_file(root, ATTEMPTS_FILE)
    if text is None:
        raise ValueError("the loop branch holds no attempts ledger: " + ATTEMPTS_FILE)
    working = loop_worktree() / ATTEMPTS_FILE
    if working.is_file() and working.read_text(encoding="utf-8").replace("\r\n", "\n") != text.replace("\r\n", "\n"):
        raise ValueError("the attempts ledger here differs from the loop branch's: " + ATTEMPTS_FILE)
    rows = json.loads(text)["attempts"]
    marker = _loop_file(root, MARKER_FILE) or ""
    marked = {line.split()[1] for line in marker.splitlines() if line.startswith("- ") and len(line.split()) > 1}
    if marked != {r.get("set_key") for r in rows}:
        raise ValueError("the attempts ledger and the reads marker name different reads")
    return {"number": len(rows) + 1, "earlier": rows, "ledger_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def committed_on_loop(key):
    """Whether the loop branch's marker file (MARKER_FILE, nowhere else) carries `key`."""
    root = cr.repository_root()
    found = _git(root, "grep", "-F", "-q", "-e", key, LOOP_REF, "--", MARKER_FILE)
    if found is None or found.returncode not in (0, 1):
        raise ValueError("git cannot say whether the loop branch names this read")
    return found.returncode == 0


def reads_path():
    return cr.repository_root() / READS_FILE


def index_clean(worktree):
    clean = _git(worktree, "diff", "--cached", "--quiet", timeout=60)
    if clean is None or clean.returncode not in (0, 1):
        raise ValueError("git cannot read the loop worktree's index: no read")
    return clean.returncode == 0


def precommit(worktree):
    """The scans every commit passes: the precommit scan prints CLEAN, guard_secrets passes on the
    staged diff. True when both pass."""
    import sys as _sys
    scan = cr.repository_root() / PRECOMMIT_SCAN
    try:
        first = subprocess.run([_sys.executable, "-X", "utf8", str(scan), "."], cwd=str(worktree), capture_output=True, text=True, timeout=600,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        second = subprocess.run([_sys.executable, "scripts/guard_secrets.py", "--staged"], cwd=str(worktree), capture_output=True, text=True,
                                timeout=600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return False
    return "CLEAN" in first.stdout and second.returncode == 0


def commit_marker(key, what):
    """THE COUNT (the lead's ruling on round 3 item 1): write the key into the loop worktree's marker
    file, run the scans on it, commit that path alone on the loop branch and confirm the key is there.
    A failure before the commit takes the marker back (its file as it was, nothing staged of it): no
    marker, no count, the read may be tried again. Once committed, the set is spent."""
    worktree = loop_worktree()
    path = Path(worktree) / MARKER_FILE
    before = path.read_bytes() if path.is_file() else None
    try:
        write_marker(key, what, worktree)
        added = _git(worktree, "add", "--", MARKER_FILE, timeout=60)
        if added is None or added.returncode != 0:
            raise ValueError("the marker could not be staged: no read")
        if not precommit(worktree):
            raise ValueError("the marker's scan failed: no read")
        message = "Fresh set read: %s\n\n%s\n\n%s\n" % (key, what, ATTRIBUTION)
        done = _git(worktree, "commit", "-q", "-m", message, "--", MARKER_FILE, timeout=120)
        if done is None or done.returncode != 0:
            raise ValueError("the marker commit failed: no read")
    except ValueError:
        _git(worktree, "reset", "-q", "--", MARKER_FILE, timeout=60)
        if before is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(before)
        raise
    if not committed_on_loop(key):
        raise ValueError("the marker commit is not on the loop branch: the set is spent, no figure is read")


@contextlib.contextmanager
def opened(key, line):
    """The one opening of the set: refused when counted or marked, or when the loop worktree's index
    is not clean; else the marker committed on the loop branch (the count itself), then the reads file
    written as the second record, then the caller reads. Inside the lock throughout."""
    with cr.ReadsLock(reads_path()):
        if cr.reads_of(reads_path(), key) or marker_named(key):
            raise ValueError("the fresh set has been read: it is read once")
        if not index_clean(loop_worktree()):
            raise ValueError("the loop worktree's index is not clean: no read")
        commit_marker(key, line.get("what", "read"))
        cr.count_read(reads_path(), key, dict(line, inputs_sha256=key), True)
        yield
