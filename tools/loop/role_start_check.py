"""Role start check (Seckin 18 November 2026 21:46, SUPERVISOR_INBOX: nothing silently waits): before the lead asks
Seckin to start a role session, it runs the start .cmd's guards here and pastes the output into the "Lutfen baslat"
entry.

    py -3.12 -X utf8 tools/loop/role_start_check.py START_CMD
    py -3.12 -X utf8 tools/loop/role_start_check.py START_CMD --print-patterns

`--print-patterns` prints only the --settings file's permissions allow, ask and deny Bash rules (no other content).

It parses the .cmd's `cd /d DIR`, every `if not exist PATH (...)` (the path must exist), every `if exist PATH (...)`
(the path must not exist), every `findstr ... FILE` guard (the file must exist; its content is not read and the line
is listed as not evaluated), the request files named in its claude -p prompt and the --append-system-prompt-file and
--settings files, and evaluates each with Test-Path semantics: existence only. It prints PASS, or FAIL with each
failing guard and its own stop message, and exits 0 on PASS, 1 on FAIL, 3 when the .cmd cannot be read or holds no
claude -p line (an unforeseen state: nothing is evaluated).

Allowlist (lead 18 November 2026, after role V SYNLAB1b..d ended at a command its settings deny): the tool also opens
exactly two kinds of file, both the lead's own placed files: the `--settings FILE` of the claude -p line (relative to
the .cmd's `cd /d` folder) and the request files, that is every REQUEST_*.md the claude -p prompt names (an absolute
path, or a bare name found in the `cd /d` folder, a `folder X` it names, the folder of an absolute request, or the
path of a guard with that name) and every REQUEST_*.md such a request names that exists in the same folder as that
request. No other file (role notes, findstr files, outputs) is opened.

Extraction rule: a command is a backtick span of a request, `inline` or each non-empty line of a ``` fenced block,
whose first word (after an optional leading `$ ` or `> `) is one of COMMAND_WORDS (py, python, git, the shell and
file commands listed there), and (lead 19 November 2026, after role N S41b ended at a copy named in prose) every line
outside fenced blocks whose first word, after an optional list marker, `$ `, `> `, bold or backtick, is one of
LINE_VERBS (cp, copy, Copy-Item, xcopy, robocopy, mv, move, mkdir, New-Item, rm, del, tar, py, python, git, cd and
the like, any case), taken whole with its backticks removed. Each command is split at `&&`, `||`, `;` and `|` outside quotes, and every part must be
allowed. A part is matched against the settings' permissions.deny, permissions.ask and permissions.allow `Bash(...)`
rules with Claude Code's semantics: `Bash` or `Bash(*)` matches every command, `Bash(P:*)` matches a command that
starts with P, a `*` elsewhere matches any run of characters (a trailing ` *` also matches the bare command), and
anything else matches exactly. Deny wins, then ask (reported as NOT ALLOWED, a -p session cannot answer it), then
allow; a part no allow rule matches is NOT ALLOWED. Each command prints ALLOWED, DENIED or NOT ALLOWED; any DENIED or
NOT ALLOWED makes the result FAIL. The claude line's --allowedTools is not read (the settings file is the record the
lead keeps). A start with no --settings file prints that the allowlist was not evaluated.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

COMMAND_WORDS = ('py', 'python', 'python3', 'git', 'gh', 'claude', 'powershell', 'pwsh', 'cmd', 'bash', 'sh', 'wsl',
                 'cd', 'dir', 'ls', 'cat', 'type', 'copy', 'xcopy', 'robocopy', 'move', 'mv', 'cp', 'del', 'rm',
                 'mkdir', 'rmdir', 'rd', 'findstr', 'grep', 'find', 'curl', 'ssh', 'scp', 'rsync', 'pip', 'npm',
                 'node', 'tar', 'echo', 'set', 'start', 'timeout', 'sleep', 'tasklist', 'taskkill', 'schtasks',
                 'copy-item', 'new-item', 'move-item', 'remove-item')
# Lead 19 November 2026 (role N S41b ended at a copy its request named in prose, "Copy the folder into work\s41"):
# a request line outside fenced blocks whose first word (after an optional list marker, `$ ` or `> `, bold or
# backtick) is one of these shell verbs, in any case, is a command too, the whole line with its backticks removed.
LINE_VERBS = frozenset(('cp', 'copy', 'copy-item', 'xcopy', 'robocopy', 'mv', 'move', 'move-item', 'mkdir',
                        'new-item', 'rm', 'del', 'remove-item', 'tar', 'py', 'python', 'python3', 'git', 'cd'))
LINE_LEAD_RE = re.compile(r'^\s*(?:(?:[-*+]|\d+[.)])\s+)?(?:[$>]\s+)?(?:\*\*)?`?')
FENCE_RE = re.compile(r'```[^\n]*\n(.*?)```', re.S)
TICK_RE = re.compile(r'`([^`\n]+)`')
REQ_NAME_RE = re.compile(r'\bREQUEST_[A-Za-z0-9_]+\.md\b')
BASH_RULE_RE = re.compile(r'^Bash(?:\((.*)\))?$', re.S)

IF_RE = re.compile(r'^\s*if\s+(not\s+)?exist\s+("[^"]+"|\S+)\s*(\((.*)\))?', re.I)
FINDSTR_RE = re.compile(r'^\s*findstr\b.*?\s("[^"]+"|[^\s"]+)\s*>\s*nul', re.I)
CD_RE = re.compile(r'^\s*cd\s+(/d\s+)?("[^"]+"|.+?)\s*$', re.I)
PROMPT_RE = re.compile(r'claude\s+-p\s+"([^"]*)"', re.I)
ABS_MD_RE = re.compile(r'[A-Za-z]:\\[^\s"]+?\.md\b' if os.name == 'nt'      # POSIX: its own absolute form too
                       else r'(?:[A-Za-z]:\\|(?<![^\s"\'])/)[^\s"]+?\.md\b')
NAME_MD_RE = re.compile(r'\bREQUEST_ROLE_[A-Za-z0-9_]+\.md\b')
FOLDER_RE = re.compile(r'\bfolder\s+([A-Za-z0-9_]+)\b')
FILE_FLAG_RE =re.compile(r'--(append-system-prompt-file|settings)\s+("[^"]+"|\S+)', re.I)


def unquote(text):
    return text.strip().strip('"')


def cmd_path(text):
    """A path as a .cmd file writes it, in this system's form: cmd separates with a backslash, which POSIX reads as
    part of a name (the Linux gate of 0acab665 found `inputs_N\\REQUEST_...md` missing beside an existing file)."""
    return text if os.name == 'nt' else text.replace('\\', '/')


def message(tail):
    m = re.search(r'echo\s+(.*?)\s*&', tail or '', re.I)
    return m.group(1) if m else (tail or '').strip()


def guards(text):
    """(base dir or None, [(kind, path, must_exist, message)], prompt line or None)."""
    base, rows, prompt = None, [], None
    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()
        if low.startswith('rem ') or low.startswith('echo ') or low.startswith('@echo') or low.startswith('set '):
            continue
        m = CD_RE.match(line)
        if m and low.startswith('cd'):
            base = cmd_path(unquote(m.group(2)))
            continue
        m = IF_RE.match(line)
        if m:
            rows.append(('if not exist' if m.group(1) else 'if exist', cmd_path(unquote(m.group(2))),
                         bool(m.group(1)), message(m.group(4))))
            continue
        m = FINDSTR_RE.match(line)
        if m:
            tail = line.split('||', 1)[1] if '||' in line else ''
            rows.append(('findstr', cmd_path(unquote(m.group(1))), True, message(tail.strip().strip('()'))))
            continue
        if PROMPT_RE.search(line):
            prompt = line
    return base, rows, prompt


def resolve(path, base):
    p = Path(cmd_path(str(path)))
    if p.is_absolute() or base is None:
        return p
    return Path(cmd_path(str(base))) / p


def line_commands(text):
    """The request lines outside fenced blocks that start with a shell verb (LINE_VERBS), backticks removed."""
    out = []
    for raw in FENCE_RE.sub('', text).splitlines():
        rest = raw[LINE_LEAD_RE.match(raw).end():]
        words = rest.split()
        if words and words[0].strip('`*,.:;').lower() in LINE_VERBS:
            out.append(rest.replace('**', '').replace('`', '').strip())
    return out


def commands_in(text):
    """Every command a request tells the role to run, in order, by the extraction rule above: fenced lines, inline
    backtick spans starting with a command word, and lines starting with a shell verb."""
    spans = []
    for block in FENCE_RE.findall(text):
        spans.extend(block.splitlines())
    spans.extend(TICK_RE.findall(FENCE_RE.sub('', text)))
    spans.extend(line_commands(text))
    out = []
    for span in spans:
        cmd = span.strip()
        if cmd.startswith('$ ') or cmd.startswith('> '):
            cmd = cmd[2:].strip()
        words = cmd.split()
        if words and words[0].lower() in COMMAND_WORDS and cmd not in out:
            out.append(cmd)
    return out


def split_parts(cmd):
    """A command split at &&, ||, ; and | outside quotes, as Claude Code judges each part."""
    parts, cur, quote, i = [], '', None, 0
    while i < len(cmd):
        ch = cmd[i]
        if quote:
            quote = None if ch == quote else quote
            cur += ch
        elif ch in '"\'':
            quote = ch
            cur += ch
        elif cmd[i:i + 2] in ('&&', '||'):
            parts.append(cur)
            cur, i = '', i + 1
        elif ch in ';|':
            parts.append(cur)
            cur = ''
        else:
            cur += ch
        i += 1
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def rule_matches(rule, cmd):
    """True when one permission rule string matches one command part (Claude Code prefix-and-* semantics)."""
    m = BASH_RULE_RE.match(str(rule).strip())
    if not m:
        return False
    inner = (m.group(1) or '*').strip()
    if inner.endswith(':*'):
        return cmd.startswith(inner[:-2])
    if '*' in inner:
        if inner.endswith(' *') and cmd == inner[:-2]:
            return True
        return re.fullmatch('.*'.join(re.escape(x) for x in inner.split('*')), cmd, re.S) is not None
    return cmd == inner


def judge(cmd, perms):
    """ALLOWED, DENIED or NOT ALLOWED (with the reason) for one command under one permissions block."""
    worst = 'ALLOWED', ''
    for part in split_parts(cmd):
        if any(rule_matches(r, part) for r in perms.get('deny') or []):
            return 'DENIED', 'deny rule matches: %s' % part
        if any(rule_matches(r, part) for r in perms.get('ask') or []):
            worst = 'NOT ALLOWED', 'ask rule matches, a -p session cannot answer: %s' % part
        elif not any(rule_matches(r, part) for r in perms.get('allow') or []) and worst[0] == 'ALLOWED':
            worst = 'NOT ALLOWED', 'no allow rule matches: %s' % part
    return worst


def request_files(body, base, rows):
    """The REQUEST_*.md files the prompt names (existing paths), then those they name in their own folder."""
    folders = FOLDER_RE.findall(body)
    absolute = [Path(p) for p in ABS_MD_RE.findall(body) if REQ_NAME_RE.fullmatch(Path(p).name)]
    homes = {Path(p).parent for p in absolute}
    found = [p for p in absolute if p.exists()]
    for name in REQ_NAME_RE.findall(body):
        if any(p.name.lower() == name.lower() for p in absolute):
            continue
        tries = [resolve(name, base)] + [resolve(str(Path(d) / name), base) for d in folders]
        tries += [h / name for h in homes]
        tries += [resolve(p, base) for _, p, must, _ in rows if must and Path(p).name.lower() == name.lower()]
        hit = next((t for t in tries if t.exists()), None)
        if hit is not None:
            found.append(hit)
    queue, seen = list(found), []
    while queue:
        path = queue.pop(0)
        key = os.path.normcase(os.path.abspath(path))
        if key in [os.path.normcase(os.path.abspath(s)) for s in seen]:
            continue
        seen.append(path)
        try:
            text = Path(path).read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        for name in REQ_NAME_RE.findall(text):
            sibling = Path(path).parent / name
            if sibling.exists():
                queue.append(sibling)
    return seen


def allowlist(prompt, base, rows):
    """(lines, failed count) for the commands the requests name against the --settings permissions."""
    flags = {m.group(1).lower(): unquote(m.group(2)) for m in FILE_FLAG_RE.finditer(prompt)}
    if 'settings' not in flags:
        return ['  allowlist not evaluated: the claude -p line has no --settings file'], 0
    settings = resolve(flags['settings'], base)
    try:
        perms = json.loads(Path(settings).read_text(encoding='utf-8-sig')).get('permissions') or {}
        if not isinstance(perms, dict):
            raise ValueError('permissions is not an object')
    except OSError:
        return ['  allowlist not evaluated: %s cannot be read (its existence is checked above)' % flags['settings']], 0
    except ValueError as exc:
        return ['  FAILED   allowlist: %s is not valid settings JSON (%s)' % (flags['settings'], str(exc)[:80])], 1
    body = PROMPT_RE.search(prompt).group(1)
    lines, failed = [], 0
    for path in request_files(body, base, rows):
        try:
            text = Path(path).read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        cmds = commands_in(text)
        lines.append('  allowlist %s: %d command%s' % (Path(path).name, len(cmds), '' if len(cmds) == 1 else 's'))
        for cmd in cmds:
            verdict, why = judge(cmd, perms)
            lines.append('    %-11s %s%s' % (verdict, cmd, '' if verdict == 'ALLOWED' else '  (%s)' % why))
            failed += verdict != 'ALLOWED'
    if not lines:
        lines.append('  allowlist: no request file found to read; no command evaluated')
    return lines, failed


def print_patterns(cmd_path):
    """(status, lines): the --settings file's permissions allow, ask and deny Bash rules, nothing else of its content."""
    try:
        text = Path(cmd_path).read_text(encoding='utf-8', errors='replace')
    except OSError as exc:
        return 'STOPPED', ['cannot read %s (%s)' % (cmd_path, type(exc).__name__)]
    base, _rows, prompt = guards(text)
    flags = {m.group(1).lower(): unquote(m.group(2)) for m in FILE_FLAG_RE.finditer(prompt or '')}
    if 'settings' not in flags:
        return 'STOPPED', ['no --settings file on the claude -p line of %s' % Path(cmd_path).name]
    try:
        perms = json.loads(resolve(flags['settings'], base).read_text(encoding='utf-8-sig')).get('permissions') or {}
        if not isinstance(perms, dict):
            raise ValueError('permissions is not an object')
    except (OSError, ValueError) as exc:
        return 'STOPPED', ['%s cannot be read as settings (%s)' % (flags['settings'], type(exc).__name__)]
    lines = []
    for kind in ('allow', 'ask', 'deny'):
        rules = [str(r) for r in perms.get(kind) or [] if BASH_RULE_RE.match(str(r).strip())]
        lines.append('%s (%d Bash rules)' % (kind, len(rules)))
        lines.extend('  ' + r for r in rules)
    return 'PATTERNS', lines


def evaluate(cmd_path):
    """(status, lines): status PASS, FAIL or STOPPED."""
    try:
        text = Path(cmd_path).read_text(encoding='utf-8', errors='replace')
    except OSError as exc:
        return 'STOPPED', ['cannot read %s (%s); nothing evaluated' % (cmd_path, type(exc).__name__)]
    base, rows, prompt = guards(text)
    if prompt is None:
        return 'STOPPED', ['no claude -p line in %s; nothing evaluated' % Path(cmd_path).name]
    lines, failed = [], 0
    for kind, path, must_exist, msg in rows:
        if '%' in path:
            lines.append('  skipped  %s %s (a cmd variable)' % (kind, path))
            continue
        there = os.path.exists(resolve(path, base))
        ok = there == must_exist
        note = ' (content not read, not evaluated)' if kind == 'findstr' and ok else ''
        lines.append('  %s %s %s%s%s' % ('ok      ' if ok else 'FAILED  ', kind, path,
                                         '' if ok else ': %s' % (msg or ('exists' if there else 'missing')), note))
        failed += not ok
    named = set()
    body = PROMPT_RE.search(prompt).group(1)
    for path in ABS_MD_RE.findall(body):
        named.add(path)
    guarded = {Path(p).name.lower() for _, p, must, _ in rows if must}
    folders = FOLDER_RE.findall(body)
    for name in NAME_MD_RE.findall(body):
        if name.lower() in guarded or any(Path(p).name.lower() == name.lower() for p in named):
            continue                       # already evaluated as a guard or an absolute path
        homes = [name] + [str(Path(d) / name) for d in folders]
        named.add(next((h for h in homes if os.path.exists(resolve(h, base))), name))
    for m in FILE_FLAG_RE.finditer(prompt):
        named.add(unquote(m.group(2)))
    for path in sorted(named):
        there = os.path.exists(resolve(path, base))
        lines.append('  %s claude -p file %s%s' % ('ok      ' if there else 'FAILED  ', path, '' if there else ': missing'))
        failed += not there
    for path in old_handbacks(cmd_path, base, body):
        lines.append('  FAILED   old hand-back present: %s' % path)
        failed += 1
    more, bad = allowlist(prompt, base, rows)
    lines.extend(more)
    failed += bad
    return ('FAIL' if failed else 'PASS'), lines


HANDBACK_NAME_RE = re.compile(r'\b([A-Za-z0-9]+)_(?:HANDBACK|DONE)\.json\b', re.I)
HANDBACK_DIR_RE = re.compile(r'([A-Za-z0-9]+)[\\/](?:result\.json|STOP\.txt)\b', re.I)


def old_handbacks(cmd_path, base, body):
    """Paths in the role's to-lead folder (<roles>/_xfer/<ROLE>_to_lead, found from the .cmd's `cd /d <roles>/<ROLE>`
    or its start_<role>_<step>.cmd name) of a <step>_HANDBACK.json, <step>_DONE.json, <step>\\result.json or
    <step>\\STOP.txt that already exists, for the step the start file runs (from its file name and from the hand-back
    paths its claude -p line names). Names and existence only; no content is read."""
    parts = Path(cmd_path).stem.split('_', 2)
    steps = {parts[2].lower()} if len(parts) == 3 and parts[0].lower() == 'start' else set()
    steps |= {m.lower() for m in HANDBACK_NAME_RE.findall(body)} | {m.lower() for m in HANDBACK_DIR_RE.findall(body)}
    if not steps or base is None:
        return []
    role = Path(base).name
    folder = Path(base).parent / '_xfer' / ('%s_to_lead' % role)
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    found = []
    for name in sorted(names):
        low = name.lower()
        for step in sorted(steps):
            if low in ('%s_handback.json' % step, '%s_done.json' % step):
                found.append(folder / name)
            elif low == step and (folder / name).is_dir():
                try:
                    inner = os.listdir(folder / name)
                except OSError:
                    continue
                found.extend(folder / name / i for i in sorted(inner) if i.lower() in ('result.json', 'stop.txt'))
    return found


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 2 and argv[1] == '--print-patterns':
        status, lines = print_patterns(argv[0])
        print('%s %s' % (status, Path(argv[0]).name))
        for line in lines:
            print(line)
        return 0 if status == 'PATTERNS' else 3
    if len(argv) != 1:
        print('usage: role_start_check.py START_CMD [--print-patterns]')
        return 3
    status, lines = evaluate(argv[0])
    print('%s %s' % (status, Path(argv[0]).name))
    for line in lines:
        print(line)
    return {'PASS': 0, 'FAIL': 1}.get(status, 3)


if __name__ == '__main__':
    raise SystemExit(main())
