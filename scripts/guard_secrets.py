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
.tar.gz, .tgz, .tar.xz, .txz, .tar.bz2, .tbz2) is streamed from git with constant
memory, a .zip is read whole only up to ZIP_SIZE_CAP. It is refused when a member
name carries a refused segment, when it is too large to inspect, or when it
cannot be read. It acts only when it is run.
"""
import io
import re
import subprocess
import sys
import tarfile
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
# tar (plain or compressed) is streamed from git with constant memory; a zip
# needs its central directory at the end, so it is read whole, and only up to
# ZIP_SIZE_CAP bytes (a larger one is refused, never inspected partly).
TAR_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2")
ZIP_SUFFIXES = (".zip",)
ARCHIVE_SUFFIXES = TAR_SUFFIXES + ZIP_SUFFIXES
ZIP_SIZE_CAP = 512 * 1024 * 1024
UNREADABLE = "unreadable archive"
TOO_LARGE = "archive too large to inspect"
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


def is_archive_name(name):
    return name.casefold().endswith(ARCHIVE_SUFFIXES)


def archive_kind(name):
    """"tar" or "zip" from the name's suffix alone, None for any other name."""
    folded = name.casefold()
    if folded.endswith(ZIP_SUFFIXES):
        return "zip"
    if folded.endswith(TAR_SUFFIXES):
        return "tar"
    return None


def _members_refusal(names):
    """The refusal for a sequence of member names, read one at a time so a
    streamed tar is never held whole. None when every member may be committed."""
    first, count = None, 0
    for member in names:
        if is_refused_path(member):
            count += 1
            first = first or member
    if count:
        return f"archive member {first} must never be committed ({count} refused member(s))"
    return None


def _tar_names(stream):
    """Member names of a tar (plain, gz, xz or bz2) read from a forward-only
    stream ("r|*"): one header at a time, member data skipped, nothing extracted.
    A directory member is reported with a trailing "/" so a bare refused folder
    entry is caught as well."""
    with tarfile.open(fileobj=stream, mode="r|*") as archive:
        for member in archive:
            yield member.name + ("/" if member.isdir() else "")


def tar_refusal(stream):
    return _members_refusal(_tar_names(stream))


def zip_refusal(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return _members_refusal(archive.namelist())


def archive_refusal(name, data):
    """None when every member of the archive bytes may be committed, otherwise the
    reason it is refused. The reader is chosen by `name`'s suffix. An archive that
    cannot be opened by that reader is refused (fail closed): what cannot be read
    cannot be shown to be clean. Any failure (zlib, lzma, bz2, tarfile, zipfile,
    MemoryError, OSError) becomes the one line UNREADABLE, never a traceback."""
    kind = archive_kind(name)
    try:
        if kind == "zip":
            if len(data) > ZIP_SIZE_CAP:
                return TOO_LARGE
            return zip_refusal(data)
        if kind == "tar":
            return tar_refusal(io.BytesIO(data))
    except Exception:  # noqa: BLE001 - MemoryError and OSError are Exceptions too
        return UNREADABLE
    return UNREADABLE


def staged_size(root, name):
    """The size in bytes of the STAGED blob, from git, without reading it."""
    result = subprocess.run(["git", "cat-file", "-s", ":" + name], cwd=str(root or ROOT),
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("git cat-file failed")
    return int(result.stdout.strip())


def staged_blob(root, name):
    """The STAGED content of a path (the index, not the working tree), as bytes.
    Used for a zip only, after its size has been checked against ZIP_SIZE_CAP."""
    result = subprocess.run(["git", "show", ":" + name], cwd=str(root or ROOT),
                            capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("git show failed")
    return result.stdout


def staged_tar_refusal(root, name):
    """Stream a staged tar from git into the tar reader with constant memory.
    The rest of git's output is drained after the last header, so git exits on
    its own and a non-zero exit is a real failure (refused as unreadable)."""
    proc = subprocess.Popen(["git", "show", ":" + name], cwd=str(root or ROOT),
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        reason = tar_refusal(proc.stdout)
        while proc.stdout.read(_CHUNK):
            pass
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    finally:
        proc.stdout.close()
    if proc.wait() != 0:
        raise RuntimeError("git show failed")
    return reason


def staged_archive_refusal(root, name):
    """The refusal for one staged archive, by its suffix: a tar is streamed, a zip
    above ZIP_SIZE_CAP is refused unread. Every failure is UNREADABLE."""
    try:
        size = staged_size(root, name)
        kind = archive_kind(name)
        if kind == "zip":
            if size > ZIP_SIZE_CAP:
                return TOO_LARGE
            return zip_refusal(staged_blob(root, name))
        if kind == "tar":
            return staged_tar_refusal(root, name)
    except Exception:  # noqa: BLE001 - MemoryError and OSError are Exceptions too
        return UNREADABLE
    return UNREADABLE


def staged_names(root=None):
    """The paths staged for the next commit, force-added ones included. Staged
    DELETIONS are left out (`--diff-filter=d`): removing a file that was committed
    by mistake must be allowed."""
    result = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=d", "-z"],
                            cwd=str(root or ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("git diff --cached failed")
    return [name for name in result.stdout.split("\0") if name]


def staged_refusals(root=None):
    """Every staged path that must not be committed, with its reason: a refused
    path, or an archive (by name) whose staged content holds a refused member or
    cannot be read."""
    refusals = []
    for name in staged_names(root):
        if is_refused_path(name):
            refusals.append((name, "this path must never be committed"))
        elif is_archive_name(name):
            reason = staged_archive_refusal(root, name)
            if reason:
                refusals.append((name, reason))
    return refusals


def main_staged(root=None):
    refused = staged_refusals(root)
    for name, reason in refused:
        print(f"BLOCKED {name}: {reason}")
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
