"""Export the loop branch's tree as one public commit (D-488, D-487 item 3).

The local repository carries the history from before the 2 November rewrite (S13), so nothing is
pushed from it (D-192). This tool reads one commit's TREE from it, never its history, and writes that
tree into a clone of the public repository as one new commit on the clone's current branch. It never
pushes.

Deterministic, in this order, for every tracked file of the source commit:
1. Excluded classes are left out: any path with a segment run listed in EXCLUDED_SEGMENTS
   (the private loop records, seals, saved model replies, the external folder, prompts, the
   benchmark keys, run output), a model-weight file over WEIGHT_LIMIT_BYTES, and any binary file
   over BINARY_LIMIT_BYTES. A path matched by .gitignore cannot reach a tree unless force-added;
   force-added files are tracked content and are exported (they are counted in the report).
2. The rewrite expressions of S13 (`expressions.txt` in the rules folder, git-filter-repo's
   `--replace-text` format: `literal:A==>B` and `regex:A==>B`, applied in file order, literals
   first, then the regular expressions, as git-filter-repo applies them) are applied to every
   blob and to every path. The expression file is read at run time and never copied; the tool
   holds no pattern of its own, so it prints counts only.
3. `--public-ref REF --cutoff REV`: a path whose blob at the source commit equals its blob at the
   S13 cut-off, and which REF (a ref of the clone, for example the published `loop-v1`) holds, is
   taken from REF, so the edits S13 step 6 made in the mirror stay.
4. `--keep PATH=REF` (repeatable): PATH is taken from REF of the clone (files only the public
   branch holds, such as the Pages site, or the S13 commit map).
Every other path the clone's branch held is deleted. The blobs are written with
`git hash-object -w --no-filters`, the index is built with `git update-index --index-info` from the
source modes, and the commit with `git commit-tree`, so no line-ending or attribute filter alters a
byte. The working tree is then checked out to the commit.

Pinned content: for every file the transform changed, the tool looks for the SHA-256 of its source
bytes (as they are and with CRLF folded to LF) and for its git blob id in every other exported text file and lists the pinning files (the frozen records that would
no longer verify). It reports; it does not decide.

Usage:
  py -3.12 -X utf8 tools/loop/export_public_tree.py --source <local repo> --rev <commit>
      --clone <public clone> [--rules <folder>] [--public-ref loop-v1 --cutoff <commit>]
      [--keep PATH=REF ...] --message-file <file> --report <json> [--dry-run]
The rules folder defaults to `shimmer-rewrite-rules` beside the main checkout (git's common
directory), so it works from a worktree too.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloud_run_common import no_window  # noqa: E402  (HIDDEN-A: every tools/loop start has no window)

EXCLUDED_SEGMENTS = (
    "docs/loop/private",
    "seals",
    "audit/model_replies",
    "external",
    "prompts",
    "benchmark/keys",
    "output",
)
WEIGHT_SUFFIXES = (".safetensors", ".bin", ".pt", ".pth", ".ckpt", ".gguf", ".onnx", ".pkl",
                   ".npy", ".npz", ".h5")
WEIGHT_LIMIT_BYTES = 1 << 20
BINARY_LIMIT_BYTES = 10 << 20
_EXCLUDED = re.compile(r"(?i)(^|/)(" + "|".join(re.escape(s) for s in EXCLUDED_SEGMENTS) + r")(/|$)")


def git(repo, *args, data=None, env=None):
    return subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True,
                          check=True, env=env, creationflags=no_window()).stdout


def read_expressions(path):
    literal, regexes = [], []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        left, sep, right = line.partition("==>")
        if not sep:
            right = "***REMOVED***"
        if left.startswith("regex:"):
            regexes.append((re.compile(left[6:].encode()), right.encode()))
        elif left.startswith("literal:"):
            literal.append((left[8:].encode(), right.encode()))
        elif left.startswith("glob:"):
            raise SystemExit("export: glob expressions are not supported; refusing")
        else:
            literal.append((left.encode(), right.encode()))
    return literal, regexes


def transform(data, literal, regexes):
    """Return (new bytes, number of replacements)."""
    count = 0
    for a, b in literal:
        n = data.count(a)
        if n:
            count += n
            data = data.replace(a, b)
    for rx, b in regexes:
        data, n = rx.subn(b, data)
        count += n
    return data, count


def digests(data, blob_id):
    """The forms a record pins a file by: SHA-256 of its bytes, of its bytes with CRLF folded to
    LF, and its git blob id."""
    folded = data.replace(b"\r\n", b"\n")
    return {hashlib.sha256(data).hexdigest(), hashlib.sha256(folded).hexdigest(), blob_id}


def excluded(path, mode, size, data):
    if mode == "160000":
        return "submodule"
    if _EXCLUDED.search(path):
        return "excluded_folder"
    if path.lower().endswith(WEIGHT_SUFFIXES) and size > WEIGHT_LIMIT_BYTES:
        return "model_weight"
    if size > BINARY_LIMIT_BYTES and b"\0" in data[:8000]:
        return "large_binary"
    return None


class Blobs:
    """Read blobs through one `git cat-file --batch`."""

    def __init__(self, repo):
        self.p = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  creationflags=no_window())

    def read(self, sha):
        self.p.stdin.write(sha.encode() + b"\n")
        self.p.stdin.flush()
        header = self.p.stdout.readline().split()
        if header[1] == b"missing":
            raise SystemExit("export: a blob is missing")
        data = self.p.stdout.read(int(header[2]))
        self.p.stdout.read(1)
        return data

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def tree_entries(repo, rev):
    out = {}
    raw = git(repo, "ls-tree", "-r", "-l", "-z", rev)
    for row in raw.split(b"\0"):
        if not row:
            continue
        meta, path = row.split(b"\t", 1)
        mode, typ, sha, size = meta.decode().split()
        out[path.decode("utf-8")] = (mode, typ, sha, 0 if size == "-" else int(size))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--rev", required=True)
    ap.add_argument("--clone", required=True)
    ap.add_argument("--rules")
    ap.add_argument("--public-ref")
    ap.add_argument("--cutoff")
    ap.add_argument("--keep", action="append", default=[])
    ap.add_argument("--message-file")
    ap.add_argument("--report", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if bool(a.public_ref) != bool(a.cutoff):
        raise SystemExit("export: --public-ref and --cutoff go together")
    source, clone = Path(a.source), Path(a.clone)
    if a.rules:
        rules = Path(a.rules)
    else:  # beside the main checkout, found through git's common directory (works from a worktree)
        common = git(source, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()
        rules = Path(common).parent.parent / "shimmer-rewrite-rules"
    literal, regexes = read_expressions(rules / "expressions.txt")
    rev = git(source, "rev-parse", a.rev + "^{commit}").decode().strip()
    src = tree_entries(source, rev)
    cut = tree_entries(source, a.cutoff) if a.cutoff else {}
    pub = tree_entries(clone, a.public_ref) if a.public_ref else {}
    head = git(clone, "rev-parse", "HEAD").decode().strip()
    head_tree = tree_entries(clone, head)

    report = {"source_commit": rev, "parent": head, "source_files": len(src), "excluded": {},
              "force_added_tracked": 0, "files_transformed": 0, "replacements": 0,
              "paths_renamed": 0, "taken_from_public_ref": 0, "kept": {}, "pinned_changed": [],
              "deleted_from_parent": 0}
    ignored = set(git(source, "ls-files", "-ci", "--exclude-standard", "--with-tree", rev, "-z")
                  .decode("utf-8").split("\0")) - {""}
    blobs = Blobs(source)
    out = {}          # path -> (mode, bytes or ("ref", sha))
    changed_digests = {}
    for path in sorted(src):
        mode, typ, sha, size = src[path]
        if typ != "blob":
            report["excluded"]["submodule"] = report["excluded"].get("submodule", 0) + 1
            continue
        data = blobs.read(sha)
        why = excluded(path, mode, size, data)
        if why:
            report["excluded"][why] = report["excluded"].get(why, 0) + 1
            continue
        if path in ignored:
            report["force_added_tracked"] += 1
        if a.public_ref and path in pub and cut.get(path, (None, None, None))[2] == sha:
            out[path] = (mode, ("ref", pub[path][2]))
            report["taken_from_public_ref"] += 1
            if pub[path][2] != sha:  # the published copy differs: S13 rewrote it or step 6 edited it
                report["public_ref_differs_from_source"] = report.get("public_ref_differs_from_source", 0) + 1
                for d in digests(data, sha):
                    changed_digests[d] = path
            continue
        new, n = transform(data, literal, regexes)
        new_path, pn = transform(path.encode("utf-8"), literal, regexes)
        if pn:
            report["paths_renamed"] += 1
        if n:
            report["files_transformed"] += 1
            report["replacements"] += n
            for d in digests(data, sha):
                changed_digests[d] = path
        out[new_path.decode("utf-8")] = (mode, new)
    blobs.close()
    for item in a.keep:
        path, _, ref = item.partition("=")
        entries = tree_entries(clone, ref)
        if path not in entries:
            raise SystemExit(f"export: --keep {path}: not in {ref}")
        out[path] = (entries[path][0], ("ref", entries[path][2]))
        report["kept"][path] = ref
    report["deleted_from_parent"] = sum(1 for p in head_tree if p not in out)
    report["files_exported"] = len(out)

    # Pinned content: a changed file's source SHA-256 written in another exported text file.
    pins = {}
    if changed_digests:
        digest_rx = re.compile(rb"(?<![0-9a-fA-F])(?:[0-9a-f]{64}|[0-9a-f]{40})(?![0-9a-fA-F])")
        published = Blobs(clone)
        for path, (mode, body) in out.items():
            if isinstance(body, tuple):
                body = published.read(body[1])
            if b"\0" in body[:8000]:
                continue
            for m in set(digest_rx.findall(body)):
                hit = changed_digests.get(m.decode())
                if hit and hit != path:
                    pins.setdefault(hit, set()).add(path)
        published.close()
    report["pinned_changed"] = [{"file": f, "pinned_by": sorted(v)} for f, v in sorted(pins.items())]

    if not a.dry_run:
        if not a.message_file:
            raise SystemExit("export: --message-file is required unless --dry-run")
        index_lines = []
        work = clone
        to_hash = []
        for path, (mode, body) in sorted(out.items()):
            if isinstance(body, tuple):
                index_lines.append(f"{mode} {body[1]}\t{path}")
                continue
            target = work / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if mode == "120000":
                sha = git(clone, "hash-object", "-w", "--stdin", data=body).decode().strip()
                index_lines.append(f"{mode} {sha}\t{path}")
                continue
            target.write_bytes(body)
            to_hash.append(path)
        shas = git(clone, "hash-object", "-w", "--no-filters", "--stdin-paths",
                   data="\n".join(to_hash).encode("utf-8") + b"\n").decode().split()
        if len(shas) != len(to_hash):
            raise SystemExit("export: hash-object returned the wrong count")
        for path, sha in zip(to_hash, shas):
            index_lines.append(f"{out[path][0]} {sha}\t{path}")
        env = dict(os.environ, GIT_INDEX_FILE=str(clone / ".git" / "export_index"))
        index_file = Path(env["GIT_INDEX_FILE"])
        if index_file.exists():
            index_file.unlink()
        git(clone, "update-index", "--add", "--index-info",
            data="\n".join(sorted(index_lines, key=lambda l: l.split("\t", 1)[1])).encode("utf-8") + b"\n",
            env=env)
        tree = git(clone, "write-tree", env=env).decode().strip()
        index_file.unlink()
        commit = git(clone, "commit-tree", tree, "-p", head, "-F", a.message_file).decode().strip()
        branch = git(clone, "symbolic-ref", "--short", "HEAD").decode().strip()
        git(clone, "update-ref", f"refs/heads/{branch}", commit, head)
        git(clone, "reset", "-q", "--hard", commit)
        report.update({"tree": tree, "commit": commit, "branch": branch})
    Path(a.report).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "pinned_changed"}, indent=1))
    print("pinned changed files:", len(report["pinned_changed"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
