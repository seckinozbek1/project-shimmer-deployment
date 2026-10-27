#!/usr/bin/env python3
"""Secret scanner. Walks the repository and flags potential API keys.

Exits 0 if clean, 1 if any potential secret is detected.
Run from project root:

    py -3.9 scripts/guard_secrets.py

With ``--staged`` it instead checks the paths staged for the next commit
(``git diff --cached --name-only``, which also lists force-added paths; staged
deletions are allowed) and refuses any path that must never be committed: a
``seals/`` segment (Annex B.3 of the 2026-10-27 loop) or an
``audit/model_replies/`` segment at any depth, case-insensitively. A staged
archive is read from the index, its reader chosen by suffix: a tar (.tar,
.tar.gz, .tgz, .tar.xz, .txz, .tar.bz2, .tbz2) is streamed from git and never
holds the archive's bytes in memory, a .zip is read whole only up to
ZIP_SIZE_CAP, and an archive or compressed suffix it cannot read (.7z, .rar,
.zst, .tzst, .lz4, a bare .gz, .bz2 or .xz) is refused unread. It is refused
when a member name carries a refused segment, when it is too large to inspect,
or when it cannot be read in full. It acts only when it is run.
"""
import bz2
import contextlib
import gzip
import io
import lzma
import re
import subprocess
import sys
import tarfile
import threading
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
EXCLUDE_SUFFIXES = {
    ".pdf", ".pkl", ".pyc",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp",
    ".so", ".dll", ".exe", ".bin",
    ".tar", ".zip", ".gz", ".7z", ".tgz", ".xz", ".bz2", ".txz", ".tbz2",
    ".woff", ".woff2", ".ttf", ".otf",
    ".docx", ".xlsx", ".pptx",
}

ANTHROPIC_RE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")
GENERIC_SK_RE = re.compile(r"sk-[A-Za-z0-9]{20,}")
AWS_RE = re.compile(r"AKIA[A-Z0-9]{16}")

# Group 1 is the keyword, group 2 is the opening quote if the value is a string
# LITERAL (empty otherwise), group 3 is the value. productization STEP B added
# group 2: a quoted value is always treated as a literal, so the
# expression-shaped exemption below can never apply to one.
KEYWORD_RE = re.compile(
    r"(api[_\-]?key|apikey|secret|password|token|credential)"
    r"\s*[=:]\s*"
    r"(['\"]?)([^\s'\"\n,;)\]}]{10,})",
    re.IGNORECASE,
)

# productization STEP B: an UNQUOTED value that begins as an identifier followed
# immediately by a subscript or a call is CODE that reads a value, not a key.
# The four false positives this scanner reported were all one shape:
#
#     token = authorization[len("Bearer "):].strip()
#
# The value capture stops at the first quote, yielding `authorization[len(`,
# which no other safe-value rule recognised. A real credential literal never
# begins with `identifier[` or `identifier(`: every provider key alphabet in use
# is letters, digits, `-` and `_`.
#
# This does NOT weaken key detection, for two independent reasons. First, it is
# applied ONLY when the value is unquoted, so a hardcoded string is never
# exempted. Second, the three literal patterns above (Anthropic, sk-prefixed,
# AWS) scan the WHOLE LINE independently of this heuristic, so an actual key
# appearing anywhere on the line is still flagged even if the assignment shape
# looks like code. Gate check 122 asserts both properties.
EXPRESSION_VALUE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*[\[(]")

# productization STEP B: a value delimited by MARKDOWN BACKTICKS is a code
# reference inside prose, not an assignment. The remaining false positive after
# the rule above was a sentence in an audit report describing this very
# scanner's own callers:
#
#     ... the token= check is `_check_token` ...
#
# This is a SYNTAX rule, not a file allowlist: it applies in every file type,
# and no path is exempted anywhere in this scanner. Its two safety properties
# are the same as EXPRESSION_VALUE_RE's: it is applied only to the keyword
# heuristic, and the three literal key patterns still scan the whole line
# independently, so a real key written inside backticks is still flagged.
MARKDOWN_CODE_VALUE_RE = re.compile(r"^`[^`]*`?$")

BASE64_RE = re.compile(r"[A-Za-z0-9+/=]{40,}")
KEY_OR_SECRET_RE = re.compile(r"(?i)\b(key|secret)\b")

SAFE_VALUE_RE = re.compile(
    r"^(YOUR[_A-Z]+|REPLACE[_A-Z]*|EXAMPLE[A-Z_]*|PLACEHOLDER[A-Z_]*|"
    r"TODO[A-Z_]*|FIXME[A-Z_]*|"
    r"None|null|true|false|[0-9]+|"
    r"<[^>]+>|\$\{[^}]+\}|\$[A-Z_]+|"
    r"os\.environ.*|os\.getenv.*|getenv\(.*|"
    r"self\..*|cls\..*|this\..*|"
    r"config\..*|cfg\..*|settings\..*|"
    r"\.\.+/.*|/.*|[A-Z]:.*|"
    r"[A-Za-z0-9_]+\(.*\)|"
    r"[\"']?[A-Z_][A-Z0-9_]*[\"']?|"
    r"array.*|string|integer|boolean|object|null|float[^,]*|"
    r"REF-[0-9]+.*|CONV-[0-9]+.*|LAW-[A-Z0-9]+.*|"
    r"DELTA-[0-9]+.*|TF-[0-9]+.*|PREC-[0-9]+.*)$"
)

HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def should_scan(path: Path) -> bool:
    if path == SELF:
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return False
    return True


def is_safe_value(value: str, *, quoted: bool = False) -> bool:
    """Whether `value` (the right-hand side of a credential-named assignment) is
    demonstrably not a secret.

    `quoted` says whether the value was introduced by a quote character, i.e.
    whether it is a string LITERAL. A literal never gets the expression-shaped
    exemption: only unquoted code does. Defaults to False so any caller that
    does not pass it gets the strictest behaviour."""
    v = value.strip("'\"")
    if not v:
        return True
    if SAFE_VALUE_RE.match(v):
        return True
    if not quoted and EXPRESSION_VALUE_RE.match(v):
        return True
    if MARKDOWN_CODE_VALUE_RE.match(value.strip()):
        return True
    if HEX_RE.match(v) and len(v) in (7, 8, 40, 64):
        return True
    if UUID_RE.match(v):
        return True
    return False


def scan_line(line: str):
    findings = []

    if ANTHROPIC_RE.search(line):
        findings.append("Anthropic key pattern (sk-ant-...)")
    if not ANTHROPIC_RE.search(line) and GENERIC_SK_RE.search(line):
        findings.append("sk-prefixed key pattern (sk-...)")
    if AWS_RE.search(line):
        findings.append("AWS access key pattern (AKIA...)")

    for kw_match in KEYWORD_RE.finditer(line):
        keyword = kw_match.group(1)
        quote = kw_match.group(2)
        value = kw_match.group(3)
        if is_safe_value(value, quoted=bool(quote)):
            continue
        snippet = value[:16] + ("..." if len(value) > 16 else "")
        findings.append(f"keyword assignment: {keyword}={snippet}")

    if KEY_OR_SECRET_RE.search(line):
        for b64_match in BASE64_RE.finditer(line):
            b64_val = b64_match.group(0)
            if HEX_RE.match(b64_val) and len(b64_val) in (40, 64):
                continue
            findings.append("long base64-like string near 'key' or 'secret'")
            break

    return findings


# Path segments refused at ANY depth, as plain strings (no regex: a module-level
# alternation of lowercase words would need gate check 242's list). `seals/` is a
# seal manifest folder (Annex B.3), refused wherever it sits, the same rule the
# unanchored `.gitignore` line `seals/` applies. A run folder's saved model
# replies (<run>/audit/model_replies/, scripts/reply_records.py) hold reply and
# payload text and are never committed, wherever the run folder sits.
REFUSED_STAGED_SEGMENTS = ("seals/", "audit/model_replies/")
# Staged files whose MEMBER names are read as well: the controller packs every
# file under project/output into collected_evidence.tar.gz, so a refused path can
# reach git inside an archive whose own name is harmless. The reader is chosen by
# the SUFFIX and never by sniffing the bytes: a plain tar whose last member is a
# small zip would otherwise be read as that zip and its tar members skipped. A
# tar (plain or compressed) is streamed from git and never holds the archive's
# bytes in memory (the member names still accumulate); a zip needs its central
# directory at the end, so it is read whole, and only up to ZIP_SIZE_CAP bytes (a
# larger one is refused, never inspected partly). A suffix that names an archive
# or a compression this guard cannot read is refused unread (fail closed); it is
# tested after the tar suffixes, so `.tar.gz` is read and a bare `.gz` is not.
# Archives nested inside archives are not opened.
TAR_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2")
ZIP_SUFFIXES = (".zip",)
UNREADABLE_SUFFIXES = (".7z", ".rar", ".zst", ".tzst", ".lz4", ".gz", ".bz2", ".xz")
ZIP_SIZE_CAP = 512 * 1024 * 1024
UNREADABLE = "unreadable archive"
GIT_TIMEOUT = 300
_CHUNK = 1024 * 1024


def is_refused_path(name):
    """Whether one path (a staged name or an archive member name) must never be
    committed. Compared with forward slashes and case-folded, because .gitignore
    matches case-insensitively on Windows: `Seals/x.json` is the same folder. A
    segment matches at the root or after any "/"."""
    normal = name.replace("\\", "/").casefold()
    return any(normal.startswith(segment) or ("/" + segment) in normal
               for segment in REFUSED_STAGED_SEGMENTS)


def refused_staged_paths(names):
    """Return the staged names that must never be committed.

    A pure function over git's own name list, so it can be tested without git.
    """
    return [name for name in names if is_refused_path(name)]


def archive_kind(name):
    """"zip", "tar" or "unreadable" from the name's suffix alone, None for a name
    that is not an archive. The tar suffixes are tested before the unreadable
    ones, so `.tar.gz` is a tar and a bare `.gz` is unreadable."""
    folded = name.casefold()
    if folded.endswith(ZIP_SUFFIXES):
        return "zip"
    if folded.endswith(TAR_SUFFIXES):
        return "tar"
    if folded.endswith(UNREADABLE_SUFFIXES):
        return "unreadable"
    return None


def is_archive_name(name):
    return archive_kind(name) is not None


def too_large():
    """The one-line refusal for a zip above ZIP_SIZE_CAP: the limit and a remedy."""
    cap = ZIP_SIZE_CAP
    limit = f"{cap // 2**20} MiB" if cap % 2**20 == 0 else f"{cap} bytes"
    return f"archive too large to inspect (over {limit}); repack as .tar.gz"


def _members_refusal(names):
    """The refusal for a sequence of member names, read one at a time so a
    streamed tar's bytes are never held. None when every member may be committed."""
    first, count = None, 0
    for member in names:
        if is_refused_path(member):
            count += 1
            first = first or member
    if count:
        return f"archive member {first} must never be committed ({count} refused member(s))"
    return None


def _decompressed(name, raw):
    """The tar stream inside `raw`, by suffix. GzipFile, BZ2File and LZMAFile read
    forward from a pipe and continue through every gzip member or bz2/xz stream,
    so a second member joined to the first is read, not dropped."""
    folded = name.casefold()
    if folded.endswith((".tar.gz", ".tgz")):
        return gzip.GzipFile(fileobj=raw, mode="rb")
    if folded.endswith((".tar.xz", ".txz")):
        return lzma.LZMAFile(raw)
    if folded.endswith((".tar.bz2", ".tbz2")):
        return bz2.BZ2File(raw)
    return raw


class _Counted:
    """A forward reader that counts the bytes it hands to the tar reader and keeps
    the last BLOCKSIZE of them, so the block that ended the tar can be checked."""

    def __init__(self, raw):
        self.raw, self.count, self.tail = raw, 0, b""

    def read(self, size=-1):
        data = self.raw.read(size)
        self.count += len(data)
        self.tail = (self.tail + data)[-tarfile.BLOCKSIZE:]
        return data


def tar_refusal(stream):
    """The refusal for an uncompressed tar stream, read forward ("r|"): one header
    at a time, member data skipped, nothing extracted. A directory member is
    reported with a trailing "/" so a bare refused folder entry is caught too.

    The tar reader stops at the first zero block or at a bad header, so what
    follows is checked here: the block that ended it and the whole rest of the
    stream must be zero bytes, or the archive is UNREADABLE. Two tars joined end
    to end, or a tar followed by anything else, are therefore never passed
    unread. The tar reader is given one block per read (bufsize BLOCKSIZE), so it
    holds nothing beyond the block that ended it."""
    counted = _Counted(stream)
    with tarfile.open(fileobj=counted, mode="r|", bufsize=tarfile.BLOCKSIZE) as archive:
        reason = _members_refusal(m.name + ("/" if m.isdir() else "") for m in archive)
        taken = counted.count - archive.offset
    if taken > len(counted.tail) or counted.tail[len(counted.tail) - taken:].strip(b"\0"):
        return UNREADABLE
    while True:
        chunk = stream.read(_CHUNK)
        if not chunk:
            return reason
        if chunk.strip(b"\0"):
            return UNREADABLE


def zip_refusal(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return _members_refusal(archive.namelist())


def refusal_for(name, size_of, open_raw):
    """THE dispatch, used for staged files and in-memory bytes alike: None when the
    name is not an archive or every member may be committed, otherwise the reason
    it is refused. The reader is chosen by `name`'s suffix (archive_kind).
    `size_of()` gives the archive's size in bytes and `open_raw()` a context
    manager over a forward-only binary stream of its bytes. A suffix the guard
    cannot read, and an archive its reader cannot read in full, are refused (fail
    closed): what cannot be read cannot be shown to be clean. Any failure (zlib,
    lzma, bz2, tarfile, zipfile, git, MemoryError, OSError) becomes the one line
    UNREADABLE, never a traceback."""
    kind = archive_kind(name)
    if kind is None:
        return None
    try:
        if kind == "zip":
            if size_of() > ZIP_SIZE_CAP:
                return too_large()
            with open_raw() as raw:
                return zip_refusal(raw.read())
        if kind == "tar":
            with open_raw() as raw:
                return tar_refusal(_decompressed(name, raw))
    except Exception:  # noqa: BLE001 - MemoryError and OSError are Exceptions too
        return UNREADABLE
    return UNREADABLE


def archive_refusal(name, data):
    """refusal_for over archive bytes held in memory (the no-git tests)."""
    return refusal_for(name, lambda: len(data), lambda: io.BytesIO(data))


def _index_path(name):
    """The revision for a path's STAGED blob: stage 0 and the literal path, so a
    name such as `1:x.tar` is not read as stage 1 of `x.tar`."""
    return ":0:" + name


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=str(root or ROOT), stdin=subprocess.DEVNULL,
                          capture_output=True, encoding="utf-8", timeout=GIT_TIMEOUT)


def staged_size(root, name):
    """The size in bytes of the STAGED blob, from git, without reading it."""
    result = _git(root, "cat-file", "-s", _index_path(name))
    if result.returncode != 0:
        raise RuntimeError("git cat-file failed")
    return int(result.stdout.strip())


@contextlib.contextmanager
def _staged_stream(root, name):
    """The STAGED blob (the index, not the working tree) as a forward-only pipe
    from git. On leaving, the rest of git's output is drained so git exits on its
    own; a non-zero exit is a failure. git is killed after GIT_TIMEOUT seconds,
    which ends the pipe and makes the exit non-zero."""
    proc = subprocess.Popen(["git", "show", _index_path(name)], cwd=str(root or ROOT),
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    timer = threading.Timer(GIT_TIMEOUT, proc.kill)
    timer.daemon = True
    timer.start()
    try:
        yield proc.stdout
        while proc.stdout.read(_CHUNK):
            pass
        if proc.wait() != 0:
            raise RuntimeError("git show failed or timed out")
    finally:
        timer.cancel()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()


def staged_archive_refusal(root, name):
    """refusal_for over one staged file, read from the index by git."""
    return refusal_for(name, lambda: staged_size(root, name),
                       lambda: _staged_stream(root, name))


def staged_names(root=None):
    """The paths staged for the next commit, force-added ones included. Staged
    DELETIONS are left out (`--diff-filter=d`): removing a file that was committed
    by mistake must be allowed. Names are decoded as UTF-8, as git writes them."""
    try:
        result = _git(root, "diff", "--cached", "--name-only", "--diff-filter=d", "-z")
    except subprocess.TimeoutExpired:
        raise RuntimeError("git diff --cached timed out") from None
    if result.returncode != 0:
        raise RuntimeError("git diff --cached failed")
    return [name for name in result.stdout.split("\0") if name]


def staged_refusals(root=None):
    """Every staged path that must not be committed, with its reason: a refused
    path, or an archive (by suffix) whose staged content holds a refused member,
    is too large, or cannot be read."""
    refusals = []
    for name in staged_names(root):
        if is_refused_path(name):
            refusals.append((name, "this path must never be committed"))
        else:
            reason = staged_archive_refusal(root, name)
            if reason:
                refusals.append((name, reason))
    return refusals


def _one_line(text):
    """A name or reason printed on one line: a newline in a path is shown escaped."""
    return text.replace("\r", "\\r").replace("\n", "\\n")


def main_staged(root=None):
    try:
        refused = staged_refusals(root)
    except (RuntimeError, OSError):
        print("guard_secrets --staged: could not list staged paths; refusing")
        return 1
    for name, reason in refused:
        print(f"BLOCKED {_one_line(name)}: {_one_line(reason)}")
    if refused:
        print(f"\nguard_secrets --staged: {len(refused)} refused path(s) staged.")
        return 1
    print("guard_secrets --staged: no refused path staged")
    return 0


def main():
    if "--staged" in sys.argv[1:]:
        sys.exit(main_staged())
    blocked = 0
    scanned = 0
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if not should_scan(path):
            continue
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for reason in scan_line(line):
                rel = path.relative_to(ROOT).as_posix()
                print(f"BLOCKED {rel}:{lineno} {reason}")
                blocked += 1

    if blocked:
        print(f"\nguard_secrets: {blocked} potential secret(s) detected across {scanned} file(s).")
        sys.exit(1)
    print(f"guard_secrets: clean ({scanned} file(s) scanned)")
    sys.exit(0)


if __name__ == "__main__":
    main()
