#!/usr/bin/env python3
"""Secret scanner. Walks the repository and flags potential API keys.

Exits 0 if clean, 1 if any potential secret is detected.
Run from project root:

    py -3.9 scripts/guard_secrets.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
EXCLUDE_SUFFIXES = {
    ".pdf", ".pkl", ".pyc",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp",
    ".so", ".dll", ".exe", ".bin",
    ".tar", ".zip", ".gz", ".7z",
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


def main():
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
