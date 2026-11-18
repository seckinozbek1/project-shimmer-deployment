"""PreToolUse guard for the Shimmer loop (Seckin, SUPERVISOR_INBOX 2026-11-18 12:24 item 2).

Claude Code runs this before every Bash, PowerShell, Read, Grep, Glob, Edit and Write call
(the project's .claude/settings.json). It reads the hook JSON on stdin and refuses the call
by printing a PreToolUse "deny" decision when one of four rules matches:

  delete                deletion commands (rm, rmdir, del, erase, rd, ri, Remove-Item,
                        Clear-Content, git clean, git worktree remove, git reset --hard,
                        git push --force / -f / --force-with-lease / --delete / +refspec,
                        git branch -D, robocopy /MIR /PURGE /MOVE, find -delete, Python
                        rmtree / unlink calls, .NET Delete calls, encoded PowerShell) unless
                        the program is tools/loop/safe_delete.py
  safe_delete_approval  safe_delete.py --execute (or --allow-under-protected) needs a line
                        in docs/loop/private/DELETE_APPROVALS.txt naming the exact path, the
                        word Seckin, the word yes and a date-time reference; the dry run is
                        always allowed
  protected_read        any tool or command that reaches benchmark/keys/ or a role folder
                        under <home>/local/shimmer-roles/ (B, V, R, C, S, N, _seckin, every
                        _xfer subfolder except B_to_lead_dev, N_to_lead, S_to_lead,
                        B_to_seals); writes into _xfer/lead_to_* and running the approved
                        start files docs/loop/private/role_starts/start_*.cmd are allowed;
                        in a Bash or PowerShell command only a reading position counts (a
                        reading or listing program's path argument, an interpreter's
                        arguments or heredoc program, a redirect source, a cd target, a
                        recursive read over a folder holding them), never a literal string
                        or here-string written to a file (lead, 18 Nov 14:34)
  push_hook             git push when the pre-push hook (core.hooksPath, file pre-push) is
                        missing or empty, and git push --no-verify

Every block is logged as one JSON line in docs/loop/private/command_guard_log.jsonl of the
main checkout (time, tool, rule, the first 200 characters with the home folder replaced by
<USER_HOME>). An internal error of the guard itself is logged and lets the call through, so a
bug never stalls the loop; a matched rule always denies, even when its log line fails.
Checks: tools/loop/command_guard_checks.py (fixture JSON only, nothing is run).
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]

RULES = ('delete', 'safe_delete_approval', 'protected_read', 'push_hook')

ROLES_NAME = 'shimmer-roles'
ROLE_DIRS = frozenset(('b', 'v', 'r', 'c', 's', 'n', '_seckin'))
XFER_ALLOWED = frozenset(('b_to_lead_dev', 'n_to_lead', 's_to_lead', 'b_to_seals'))
WILD = re.compile(r'[*?\[\]]')

DELETE_PROGRAMS = frozenset((
    'rm', 'rmdir', 'del', 'erase', 'rd', 'ri', 'remove-item', 'unlink', 'shred', 'sdelete',
    'clear-content', 'clc', 'clear-item', 'cli', 'clear-recyclebin', 'format-volume',
    'clear-disk', 'remove-partition', 'trash', 'trash-put',
))
WRITE_PROGRAMS = frozenset((
    'cp', 'copy', 'copy-item', 'cpi', 'set-content', 'sc', 'add-content', 'ac', 'out-file',
    'new-item', 'ni', 'mkdir', 'md', 'move-item', 'mv', 'move', 'mi', 'tee', 'tee-object',
))
CD_PROGRAMS = frozenset(('cd', 'chdir', 'set-location', 'sl', 'pushd', 'push-location'))
RECURSIVE_PROGRAMS = frozenset((
    'find', 'tree', 'tar', 'zip', '7z', 'compress-archive', 'robocopy', 'xcopy', 'rsync', 'du',
))
ARCHIVERS = frozenset(('tar', 'zip', '7z', 'compress-archive', 'robocopy', 'xcopy', 'rsync'))
# programs that read file contents; with recursion they read everything below their root
READERS = frozenset((
    'grep', 'egrep', 'fgrep', 'findstr', 'select-string', 'sls', 'cat', 'type', 'gc',
    'get-content', 'copy-item', 'cpi', 'cp', 'scp',
)) | ARCHIVERS
LISTERS = frozenset(('get-childitem', 'gci', 'ls', 'dir'))
RECURSION_FLAG = re.compile(r'(?:^|\s)(?:-r|-rf|-fr|-rl|-rn|-ri|-ril|-recurse|--recursive|/s|-depth)(?=\s|$|:)')
PREFIX_SKIP = frozenset((
    'sudo', 'env', 'time', 'nohup', 'command', 'builtin', 'exec', 'call', '.', 'then', 'else',
    'elif', 'do', 'if', 'while', 'until', '!', 'try', 'finally', 'foreach', 'for', 'nice',
))
WRAPPERS = frozenset((
    'cmd', 'powershell', 'pwsh', 'bash', 'sh', 'zsh', 'dash', 'wsl', 'iex', 'invoke-expression',
    'start-process', 'saps', 'start', 'xargs', 'invoke-command', 'icm', 'watch', 'runas', 'su',
    'timeout',
))
WRAPPER_VALUE_OPTS = frozenset((
    '-executionpolicy', '-ep', '-ex', '-windowstyle', '-w', '-workingdirectory', '-wd',
    '-configurationname', '-i', '-n', '-p', '-d', '-l', '-s', '-a', '-argumentlist',
    '-computername', '-credential', '-u', '--user',
))
ENCODED_OPT = re.compile(r'^-(e|ec|en|enc|enco|encod|encode|encoded|encodedc\w*|encodedcommand)$')
PY_PROGRAM = re.compile(r'^(python|pythonw|py)(\d+(\.\d+)*)?$')
PY_DELETE = re.compile(
    r'shutil\.rmtree|\brmtree\s*\(|\bos\.(remove|unlink|rmdir|removedirs)\s*\(|\.unlink\s*\('
    r'|\.rmdir\s*\(|send2trash|\bos\.truncate\s*\(')
DOTNET_DELETE = re.compile(r'\[(system\.)?io\.(file|directory|fileinfo|directoryinfo)\]::delete'
                           r'|\.delete\s*\(\s*(\$true|true)?\s*\)', re.I)
GIT_GLOBAL_VALUE = frozenset(('-c', '-C', '--git-dir', '--work-tree', '--namespace',
                              '--exec-path', '--config-env'))
STAMP = re.compile(r'\d{4}-\d{2}-\d{2}[ t]\d{2}:\d{2}')
START_FILE = re.compile(r'(^|/)docs/loop/private/role_starts/start_[a-z0-9_]+\.cmd$')
HEREDOC = re.compile(r'<<-?\s*([\'"]?)([A-Za-z_][A-Za-z0-9_]*)\1')
HERESTRING = re.compile(r'@([\'"])[ \t]*\r?\n(.*?)\r?\n\1@', re.S)
SHELL_FEEDS = frozenset(('bash', 'sh', 'zsh', 'dash', 'powershell', 'pwsh', 'cmd', 'wsl', 'iex',
                         'invoke-expression'))


class Deny(Exception):
    def __init__(self, rule, detail):
        super().__init__(detail)
        self.rule = rule
        self.detail = detail


# ----------------------------------------------------------------------------- context

def no_window():
    """The child's creation flags through cloud_run_common.no_window (HIDDEN-A); the Windows no-window flag itself
    when tools/ cannot be imported, so the guard never fails open on a start."""
    try:
        sys.path.insert(0, str(REPO / 'tools'))
        import cloud_run_common
        return cloud_run_common.no_window()
    except Exception:
        return 0x08000000 if os.name == 'nt' else 0
    finally:
        if sys.path and sys.path[0] == str(REPO / 'tools'):
            sys.path.pop(0)


def _git(cwd, *args):
    r = subprocess.run(['git', '-C', str(cwd)] + list(args), capture_output=True, text=True,
                       timeout=15, creationflags=no_window())
    return r.returncode, r.stdout.strip()


def default_prepush(cwd):
    """(present, where) for the pre-push hook git would run in `cwd`."""
    code, hp = _git(cwd, 'config', '--get', 'core.hooksPath')
    if code == 0 and hp:
        base = Path(hp)
        if not base.is_absolute():
            _, top = _git(cwd, 'rev-parse', '--show-toplevel')
            base = Path(top or cwd) / hp
    else:
        code, common = _git(cwd, 'rev-parse', '--git-common-dir')
        if code != 0 or not common:
            return False, 'not a git repository: ' + str(cwd)
        c = Path(common)
        base = (c if c.is_absolute() else Path(cwd) / c) / 'hooks'
    hook = base / 'pre-push'
    try:
        ok = hook.is_file() and hook.stat().st_size > 0
    except OSError:
        ok = False
    return ok, str(hook)


class Context:
    """Everything the rules read from the machine, injectable for the checks."""

    def __init__(self, home=None, main=None, approvals=None, prepush=None, exists=None,
                 disabled=()):
        self.home = Path(home) if home else Path.home()
        env_main = os.environ.get('SHIMMER_MAIN_CHECKOUT', '').strip()
        self.main = Path(main) if main else (Path(env_main) if env_main else REPO)
        self.private = self.main / 'docs' / 'loop' / 'private'
        self._approvals = approvals
        self.prepush = prepush or default_prepush
        self.exists = exists or (lambda p: os.path.exists(p))
        self.disabled = frozenset(disabled)
        self.roles_root = norm(str(self.home / 'local' / ROLES_NAME))
        self.xfer_root = self.roles_root + '/_xfer'

    def approvals(self):
        if self._approvals is not None:
            return self._approvals
        try:
            return (self.private / 'DELETE_APPROVALS.txt').read_text(encoding='utf-8')
        except OSError:
            return ''

    def on(self, rule):
        return rule not in self.disabled


# ----------------------------------------------------------------------------- text helpers

def norm(s):
    s = s.replace('\\', '/').lower()
    s = re.sub(r'(?<!^)/{2,}', '/', s)
    return s.rstrip('/') if len(s) > 1 else s


def expand_home(s, home):
    h = str(home)
    for var in ('$env:userprofile', '$home', '%userprofile%', '${home}'):
        s = re.sub(re.escape(var), h.replace('\\', '\\\\'), s, flags=re.I)
    if s.startswith('~'):
        s = h + s[1:]
    return s


def resolve(p, cwd, home):
    p = expand_home(p.strip().strip('"\''), home)
    m = re.match(r'^/(?:mnt/)?([a-zA-Z])(/.*)?$', p.replace('\\', '/'))
    if m and os.name == 'nt':
        p = m.group(1) + ':' + (m.group(2) or '/')
    path = Path(p)
    if not path.is_absolute() and cwd:
        path = Path(cwd) / path
    return norm(os.path.normpath(str(path)))


def home_pattern(home):
    h = str(home)
    m = re.match(r'^([A-Za-z]):[\\/]*(.*)$', h)
    if m:
        d, rest = m.group(1), m.group(2)
        head = r'(?:%s:|/%s|/mnt/%s)' % (d, d, d)
    else:
        head, rest = '', h.lstrip('/')
        head = r'/' if h.startswith('/') else ''
    parts = [re.escape(x) for x in re.split(r'[\\/]+', rest) if x]
    return re.compile(head + r'[\\/]+' + r'[\\/]+'.join(parts) if parts else re.escape(h), re.I)


def redact(text, home):
    try:
        return home_pattern(home).sub('<USER_HOME>', text)
    except Exception:
        return text.replace(str(home), '<USER_HOME>')


def split_segments(text, fine=True):
    """Command segments split on unquoted separators; quotes kept inside segments."""
    seps = ';&|\n\r(){}`' if fine else ';&|\n\r'
    for attempt in (True, False):
        segs, cur, q = [], [], None
        for ch in text:
            if attempt and q:
                cur.append(ch)
                if ch == q:
                    q = None
                continue
            if attempt and ch in '"\'':
                q = ch
                cur.append(ch)
                continue
            if ch in seps:
                segs.append(''.join(cur))
                cur = []
                continue
            cur.append(ch)
        segs.append(''.join(cur))
        if q is None or not attempt:
            break  # unbalanced quotes: split again ignoring quotes
    return [s.strip() for s in segs if s.strip()]


def tokens(segment):
    out, cur, q, has = [], [], None, False
    for ch in segment:
        if q:
            if ch == q:
                q = None
            else:
                cur.append(ch)
            continue
        if ch in '"\'':
            q, has = ch, True
            continue
        if ch.isspace():
            if cur or has:
                out.append(''.join(cur))
            cur, has = [], False
            continue
        cur.append(ch)
    if cur or has:
        out.append(''.join(cur))
    return out


def base(tok):
    b = re.split(r'[\\/]', tok)[-1].lower()
    return re.sub(r'\.(exe|cmd|bat|com|ps1)$', '', b)


def strip_prefix(toks):
    """Drop leading call operators, environment assignments and shell keywords."""
    i = 0
    while i < len(toks):
        t = toks[i]
        tl = t.lower()
        if tl in PREFIX_SKIP or tl in ('&', '@'):
            i += 1
            continue
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', t):
            i += 1
            continue
        if t.startswith('$') and i + 1 < len(toks) and toks[i + 1] in ('=', '+=', '-='):
            i += 2
            continue
        if re.match(r'^\$[\w:]+=$', t):
            i += 1
            continue
        break
    return toks[i:]


def heredoc_split(text):
    """(command text with literal bodies removed, literal bodies, shell bodies, code bodies).

    A body fed to a shell is a command; one fed to an interpreter (python, node...) is a
    program, read as code; every other body (written to a file, a commit message) is a
    literal. Code bodies are also listed among the literals."""
    data, shell, code = [], [], []

    def herestring(m):
        start = text.rfind('\n', 0, m.start()) + 1
        before = text[start:m.start()].lower()
        if re.search(r'\b(iex|invoke-expression|powershell|pwsh)\b|-command', before):
            shell.append(m.group(2))
        else:
            data.append(m.group(2))
        return ' HEREDATA '
    text = HERESTRING.sub(herestring, text)
    lines = text.split('\n')
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = HEREDOC.search(line)
        i += 1
        if not m:
            continue
        word = m.group(2)
        body = []
        while i < len(lines) and lines[i].strip() != word:
            body.append(lines[i])
            i += 1
        i += 1
        prog = strip_prefix(tokens(split_segments(line[:m.start()])[-1]))[:1] if \
            split_segments(line[:m.start()]) else []
        if prog and base(prog[0]) in SHELL_FEEDS:
            shell.append('\n'.join(body))
        else:
            data.append('\n'.join(body))
            if prog and (PY_PROGRAM.match(base(prog[0])) or base(prog[0]) in INTERPRETERS):
                code.append('\n'.join(body))
    return '\n'.join(out), data, shell, code


# ----------------------------------------------------------------------------- rule: protected paths

def role_hits(ntext):
    """[(kind, component)] for every shimmer-roles mention in normalised text."""
    hits = []
    for m in re.finditer(r'(?<![a-z0-9_.\-])' + re.escape(ROLES_NAME)
                         + r'((?:/[^/\s"\'`;|&<>(){},=]*)*)', ntext):
        comps = [c.rstrip('.,:') for c in m.group(1).split('/') if c.rstrip('.,:')]
        if not comps:
            hits.append(('root', ROLES_NAME))
            continue
        c0 = comps[0]
        if WILD.search(c0):
            hits.append(('blocked', c0))
        elif c0 in ROLE_DIRS:
            hits.append(('blocked', c0))
        elif c0 == '_xfer':
            if len(comps) == 1:
                hits.append(('xfer_root', '_xfer'))
            elif WILD.search(comps[1]):
                hits.append(('blocked', '_xfer/' + comps[1]))
            elif comps[1] in XFER_ALLOWED:
                continue
            elif comps[1].startswith('lead_to_'):
                hits.append(('lead_to', '_xfer/' + comps[1]))
            else:
                hits.append(('blocked', '_xfer/' + comps[1]))
    return hits


def key_hit(ntext):
    if re.search(r'(?<![a-z0-9_\-])benchmark/+keys(?![a-z0-9_\-])', ntext):
        return 'benchmark/keys'
    m = re.search(r'(?<![a-z0-9_\-])benchmark/+([^/\s"\'`;|&<>]*[*?\[][^/\s"\'`;|&<>]*)', ntext)
    if m:
        return 'benchmark/' + m.group(1)
    return None


def covers_protected(npath, ctx, gitignore_aware=False):
    """True when a directory search rooted at `npath` would reach a protected folder.

    gitignore_aware: the search honours .gitignore (the Grep and Glob tools, rg), so a
    checkout root is not counted for benchmark/keys/, which .gitignore excludes."""
    if not npath:
        return False
    for root in (ctx.roles_root, ctx.xfer_root):
        if npath == root or root.startswith(npath.rstrip('/') + '/'):
            return True
    if npath.endswith('/benchmark') or npath == 'benchmark':
        return True
    return (not gitignore_aware) and ctx.exists(npath + '/benchmark/keys')


def check_tool_path(tool, raw_path, cwd, ctx, write=False, search_root=False):
    if not raw_path:
        return
    np = resolve(raw_path, cwd, ctx.home)
    k = key_hit(np + '/') or key_hit(norm(raw_path))
    if k:
        raise Deny('protected_read', '%s reaches the answer keys (%s)' % (tool, k))
    for kind, comp in role_hits(np) + role_hits(norm(raw_path)):
        if kind == 'blocked':
            raise Deny('protected_read', '%s reaches role folder %s' % (tool, comp))
        if kind == 'lead_to' and not write:
            raise Deny('protected_read', '%s reads %s (only writes are allowed there)' % (tool, comp))
        if kind in ('root', 'xfer_root') and (search_root or write):
            raise Deny('protected_read', '%s searches or writes the role folders root' % tool)
    if search_root and covers_protected(np, ctx, gitignore_aware=True):
        raise Deny('protected_read', '%s searches a folder that holds protected folders' % tool)


def is_start_file(tok, cwd, ctx):
    np = resolve(tok, cwd, ctx.home)
    if not START_FILE.search(np):
        return False
    main_starts = norm(str(ctx.main / 'docs' / 'loop' / 'private' / 'role_starts'))
    return np.startswith(main_starts + '/') and ctx.exists(np)


def path_args(toks, cwd, ctx):
    args = [t for t in toks[1:] if t and not t.startswith('-') and not
            (t.startswith('/') and len(t) <= 3)]
    paths = [resolve(a, cwd, ctx.home) for a in args]
    real = [p for p in paths if ctx.exists(p)]
    # no folder named: the program reads its working folder (a grep's one argument is its pattern)
    implicit = not real and (len(args) == 0 or (base(toks[0]) in PATTERN_FIRST and len(args) <= 1))
    return real, implicit


PATTERN_FIRST = frozenset(('grep', 'egrep', 'fgrep', 'findstr', 'select-string', 'sls', 'rg'))


def check_recursive_read(found, cwd, ctx, aware):
    real, implicit = found
    for p in real:
        if covers_protected(p, ctx, aware):
            raise Deny('protected_read', 'recursive read over a folder that holds protected folders')
    if implicit and cwd and covers_protected(norm(str(cwd)), ctx, aware):
        raise Deny('protected_read', 'recursive read over the working folder, which holds '
                   'protected folders')


def read_tokens(prog, toks):
    """The argument tokens a command reads or lists (lead review, 18 Nov 14:34).

    Only these are checked for protected paths: the path arguments of a reading or listing
    program (a grep's pattern and a copy's destination excluded), every argument of an
    interpreter (its code or script arguments), and a redirect source. A protected path that
    appears only in a literal (a string or here-string written to a file, a commit message,
    an echo) is not a read."""
    out = []
    args = toks[1:]
    for j, t in enumerate(args):  # redirect sources, for any program
        if t == '<' and j + 1 < len(args):
            out.append(args[j + 1])
        elif t.startswith('<') and not t.startswith('<<') and len(t) > 1:
            out.append(t[1:])
    if PY_PROGRAM.match(prog) or prog in INTERPRETERS:
        return out + list(args)
    if prog not in READ_PROGRAMS:
        return out
    positional, pattern_given, dest_given = [], False, False
    j = 0
    while j < len(args):
        t = args[j]
        tl = t.lower()
        if tl.startswith('-') and ':' in tl and not tl.startswith('--'):
            name, value = tl.split(':', 1)[0], t.split(':', 1)[1]
            if name in PATH_PARAMS:
                out.append(value)
            pattern_given |= name in PATTERN_PARAMS
            dest_given |= name in DEST_PARAMS
            j += 1
            continue
        if tl.startswith('--') and '=' in tl:
            name, value = tl.split('=', 1)[0], t.split('=', 1)[1]
            if name in PATH_PARAMS:
                out.append(value)
            pattern_given |= name in PATTERN_PARAMS
            j += 1
            continue
        if tl in PATH_PARAMS:
            if j + 1 < len(args):
                out.append(args[j + 1])
            j += 2
            continue
        if tl in PATTERN_PARAMS or tl in DEST_PARAMS or tl in LITERAL_PARAMS or tl in VALUE_PARAMS:
            pattern_given |= tl in PATTERN_PARAMS
            dest_given |= tl in DEST_PARAMS
            j += 2
            continue
        if tl.startswith('-') or tl in ('<', '>', '>>', '2>', '2>>') or tl.startswith(('>', '2>')):
            if tl in ('>', '>>', '2>', '2>>'):
                j += 1  # the redirect target is written, not read
            j += 1
            continue
        if prog == 'cmd' or (tl.startswith('/') and len(tl) <= 3 and prog in WIN_SWITCH_PROGRAMS):
            j += 1
            continue
        positional.append(t)
        j += 1
    if prog in PATTERN_FIRST and not pattern_given and positional:
        positional = positional[1:]
    if prog in COPY_PROGRAMS and not dest_given and len(positional) > 1:
        positional = positional[:-1]
    return out + positional


INTERPRETERS = frozenset(('node', 'perl', 'ruby', 'deno', 'bun', 'php', 'lua', 'rscript'))
COPY_PROGRAMS = frozenset(('cp', 'copy', 'copy-item', 'cpi', 'scp', 'rsync', 'robocopy', 'xcopy',
                           'mv', 'move', 'move-item', 'mi'))
READ_PROGRAMS = frozenset((
    'cat', 'type', 'gc', 'get-content', 'head', 'tail', 'less', 'more', 'wc', 'sort', 'uniq',
    'diff', 'fc', 'comp', 'cmp', 'strings', 'xxd', 'od', 'hexdump', 'base64', 'certutil', 'jq',
    'awk', 'sed', 'cut', 'tr', 'nl', 'tac', 'bat', 'import-csv', 'import-clixml',
    'get-filehash', 'get-item', 'gi', 'get-itemproperty', 'gp', 'select-string', 'sls', 'rg',
    'grep', 'egrep', 'fgrep', 'findstr', 'ls', 'dir', 'get-childitem', 'gci', 'tree', 'find',
    'du', 'stat', 'file', 'tar', 'zip', 'unzip', '7z', 'compress-archive', 'expand-archive',
    'notepad', 'code', 'start', 'invoke-item', 'ii', 'explorer',
)) | COPY_PROGRAMS
PATH_PARAMS = frozenset(('-path', '-literalpath', '-lp', '-pspath', '-filepath', '-file',
                         '-sourcepath', '--file'))
PATTERN_PARAMS = frozenset(('-pattern', '-e', '--regexp', '-simplematch'))
DEST_PARAMS = frozenset(('-destination', '-destinationpath', '-target', '-t', '--target-directory'))
LITERAL_PARAMS = frozenset(('-value', '-inputobject', '-message', '-m'))
VALUE_PARAMS = frozenset((
    '-encoding', '-tail', '-totalcount', '-head', '-first', '-last', '-context', '-depth',
    '-filter', '-include', '-exclude', '-delimiter', '-readcount', '-name', '-algorithm',
    '--max-count', '-maxdepth', '-type', '-iname', '--glob', '-g', '--type', '--include',
    '--exclude', '-erroraction', '-ea',
))
WIN_SWITCH_PROGRAMS = frozenset(('dir', 'type', 'findstr', 'robocopy', 'xcopy', 'copy', 'fc',
                                 'comp', 'sort', 'more', 'tree', 'certutil', 'move'))


def check_read_token(tok, prog, recursive, cwd, ctx):
    nt = norm(expand_home(tok, ctx.home))
    k = key_hit(nt) or key_hit(resolve(tok, cwd, ctx.home) + '/') if not re.search(r'\s', tok) \
        else key_hit(nt)
    if k:
        raise Deny('protected_read', '%s reads the answer keys (%s)' % (prog, k))
    hits = role_hits(nt)
    if not re.search(r'\s', tok):
        hits += role_hits(resolve(tok, cwd, ctx.home))
    for kind, comp in hits:
        if kind == 'blocked':
            raise Deny('protected_read', '%s reads role folder %s' % (prog, comp))
        if kind == 'lead_to':
            raise Deny('protected_read', '%s reads %s (only writes are allowed there)' % (prog, comp))
        if kind in ('root', 'xfer_root') and recursive:
            raise Deny('protected_read', 'recursive %s over the role folders root' % prog)


def check_command_paths(text, cwd, ctx, depth=0):
    if depth > 5:
        return
    body, data, shell, code = heredoc_split(text)
    for c in code:  # a program fed to an interpreter: every protected path in it is read
        check_read_token(c, 'interpreter', False, cwd, ctx)
    for lit in data + [text]:  # $( ) inside strings and expandable here-strings runs
        for m in re.finditer(r'\$\(([^()]*)\)', lit):
            check_command_paths(m.group(1), cwd, ctx, depth + 1)
    for sh in shell:
        check_command_paths(sh, cwd, ctx, depth + 1)
    listing = None  # paths of a recursive listing whose output a later reader consumes
    for seg in split_segments(body, fine=False):
        toks = strip_prefix(tokens(seg))
        prog = base(toks[0]) if toks else ''
        # running an approved role start file is allowed whatever it does
        run = toks
        if prog in ('cmd',) and len(toks) > 2 and toks[1].lower() in ('/c', '/k'):
            run = toks[2:]
        elif prog in ('start', 'start-process', 'saps') and len(toks) > 1:
            run = [t for t in toks[1:] if not t.startswith('-') and t != '""']
        if run and is_start_file(run[0], cwd, ctx) and len(run) <= 2:
            continue
        nseg = norm(expand_home(seg, ctx.home))
        opts = ' ' + ' '.join(t.lower() for t in toks[1:] if t.startswith(('-', '/')))
        recursive = prog in RECURSIVE_PROGRAMS or bool(RECURSION_FLAG.search(opts))
        if prog == 'rg' and re.search(r'(?:^|\s)(--no-ignore\S*|-uu+)(?=\s|$)', opts):
            recursive = True
        for tok in read_tokens(prog, toks):
            check_read_token(tok, prog, recursive, cwd, ctx)
        if prog in WRAPPERS:  # the inner command of cmd /c, powershell -Command, bash -c ...
            inner = [t for t in toks[1:] if not (t.startswith('-') or
                     (prog == 'cmd' and re.match(r'^/[a-z]$', t.lower())))]
            if inner:
                check_command_paths(' '.join(inner), cwd, ctx, depth + 1)
            for t in toks[1:]:
                if re.search(r'\s', t):
                    check_command_paths(t, cwd, ctx, depth + 1)
        raw = tokens(seg)
        if (len(raw) == 3 and raw[0].startswith('$') and raw[1] == '=') or \
                (prog in ('set', 'export', 'set-variable', 'new-variable', 'sv') and len(toks) >= 2):
            value = raw[2] if raw[1:2] == ['='] else toks[-1].split('=', 1)[-1]
            if not re.search(r'\s', value):
                nv = norm(expand_home(value, ctx.home))
                if key_hit(nv) or any(k != 'lead_to' for k, _ in role_hits(nv)):
                    raise Deny('protected_read', 'a protected folder path stored in a variable')
        if prog in CD_PROGRAMS and len(toks) > 1:
            target = resolve(toks[1], cwd, ctx.home)
            if key_hit(target + '/') or target.endswith('/benchmark'):
                raise Deny('protected_read', 'changing directory into the answer keys')
            if role_hits(target) + role_hits(norm(expand_home(toks[1], ctx.home))):
                raise Deny('protected_read', 'changing directory into the role folders')
        reader = prog in ARCHIVERS or (recursive and prog in READERS) or \
            (prog == 'rg') or (prog == 'find' and re.search(r'\s-(exec|execdir|ok)\b', nseg))
        if reader:
            aware = prog == 'rg' and not re.search(r'(?:^|\s)(--no-ignore\S*|-uu+)(?=\s|$)', nseg)
            check_recursive_read(path_args(toks, cwd, ctx), cwd, ctx, aware)
        elif prog in READERS and listing is not None:
            check_recursive_read(listing, cwd, ctx, False)
        if prog in LISTERS and recursive:
            listing = path_args(toks, cwd, ctx)


# ----------------------------------------------------------------------------- rule: deletion and push

def git_parts(toks):
    """(sub, args, cwd_override) for a git command's tokens after the program."""
    i, cdir = 0, None
    while i < len(toks):
        t = toks[i]
        if t in GIT_GLOBAL_VALUE:
            if t == '-C' and i + 1 < len(toks):
                cdir = toks[i + 1]
            i += 2
            continue
        if t.startswith('--') and '=' in t:
            if t.startswith('--work-tree='):
                cdir = t.split('=', 1)[1]
            i += 1
            continue
        if t.startswith('-'):
            i += 1
            continue
        return t.lower(), toks[i + 1:], cdir
    return '', [], cdir


def short_has(args, letters):
    for a in args:
        if re.match(r'^-[A-Za-z]+$', a) and any(ch in a[1:] for ch in letters):
            return True
    return False


def check_git(args, cwd, ctx):
    sub, rest, cdir = git_parts(args)
    low = [a.lower() for a in rest]
    gitcwd = resolve(cdir, cwd, ctx.home) if cdir else (cwd or str(ctx.main))
    if ctx.on('delete'):
        if sub == 'clean':
            raise Deny('delete', 'git clean deletes files; use tools/loop/safe_delete.py')
        if sub == 'worktree' and low[:1] == ['remove']:
            raise Deny('delete', 'git worktree remove deletes a folder; use tools/loop/safe_delete.py')
        if sub == 'reset' and '--hard' in low:
            raise Deny('delete', 'git reset --hard discards work')
        if sub == 'branch' and ('-D' in rest or short_has(rest, 'D') or
                                ('--delete' in low or short_has(rest, 'd')) and
                                ('--force' in low or short_has(rest, 'f'))):
            raise Deny('delete', 'git branch -D deletes an unmerged branch')
        if sub == 'push':
            if (any(a.startswith('--force') for a in low) or '--mirror' in low or '--delete' in low
                    or '--prune' in low or short_has(rest, 'fd')
                    or any(a.startswith('+') or (a.startswith(':') and len(a) > 1)
                           for a in rest)):
                raise Deny('delete', 'forced or deleting git push')
        if sub == 'rm' and '--cached' not in low:
            raise Deny('delete', 'git rm deletes files from the working tree')
        if sub == 'stash' and low[:1] and low[0] in ('drop', 'clear'):
            raise Deny('delete', 'git stash %s discards saved work' % low[0])
        if sub == 'tag' and ('-d' in rest or '--delete' in low):
            raise Deny('delete', 'git tag -d deletes a tag')
        if sub == 'update-ref' and ('-d' in rest or '--delete' in low):
            raise Deny('delete', 'git update-ref -d deletes a ref')
        if sub == 'reflog' and low[:1] and low[0] in ('expire', 'delete'):
            raise Deny('delete', 'git reflog %s removes history' % low[0])
        if sub == 'gc' and any(a.startswith('--prune') for a in low):
            raise Deny('delete', 'git gc --prune removes objects')
        if sub in ('filter-branch', 'filter-repo'):
            raise Deny('delete', 'git %s rewrites history' % sub)
    if sub == 'push' and ctx.on('push_hook'):
        if '--no-verify' in low:
            raise Deny('push_hook', 'git push --no-verify skips the pre-push scan')
        ok, where = ctx.prepush(gitcwd)
        if not ok:
            raise Deny('push_hook', 'the pre-push scan hook is missing (%s)' % redact(where, ctx.home))


def approved(path_tok, cwd, ctx):
    cands = {norm(path_tok.strip('"\'')), resolve(path_tok, cwd, ctx.home)}
    for line in ctx.approvals().splitlines():
        nl = norm(line)
        if 'seckin' not in nl or not re.search(r'\byes\b', nl) or not STAMP.search(nl):
            continue
        words = set(w.strip('"\'') .rstrip('/') for w in re.split(r'[\s|,;]+', nl))
        if cands & words:
            return True
    return False


def check_python(toks, seg, cwd, ctx):
    i, script, module = 1, None, None
    while i < len(toks):
        t = toks[i]
        if t in ('-X', '-W', '-Q'):
            i += 2
            continue
        if t == '-m' and i + 1 < len(toks):
            module, i = toks[i + 1], i + 2
            break
        if t == '-c':
            return
        if t.startswith('-'):
            i += 1
            continue
        script, i = t, i + 1
        break
    rest = toks[i:]
    is_sd = (module == 'tools.loop.safe_delete' or
             (script is not None and norm(script).split('/')[-1] == 'safe_delete.py'))
    if not is_sd or not ctx.on('safe_delete_approval'):
        return
    low = [a.lower() for a in rest]
    if '--execute' not in low and '--allow-under-protected' not in low:
        return  # the dry run is always allowed
    paths = [a for a in rest if not a.startswith('--')]
    missing = [p for p in paths if not approved(p, cwd, ctx)]
    if missing or not paths:
        raise Deny('safe_delete_approval', 'safe_delete --execute without a DELETE_APPROVALS.txt '
                   'line (path, Seckin yes, date-time) for: %s' % ', '.join(missing or ['(no path)']))


def check_segment(seg, cwd, ctx, depth):
    toks = strip_prefix(tokens(seg))
    if not toks:
        return
    prog = base(toks[0])
    args = toks[1:]
    low = [a.lower() for a in args]
    if prog in DELETE_PROGRAMS and ctx.on('delete'):
        raise Deny('delete', '%s deletes; use tools/loop/safe_delete.py (dry run first)' % prog)
    if prog == 'robocopy' and ctx.on('delete') and \
            any(a in ('/mir', '/purge', '/move', '/mov') for a in low):
        raise Deny('delete', 'robocopy /MIR, /PURGE or /MOVE deletes files')
    if prog == 'find' and ctx.on('delete'):
        if '-delete' in low:
            raise Deny('delete', 'find -delete deletes files')
        for j, a in enumerate(low):
            if a in ('-exec', '-execdir', '-ok', '-okdir'):
                check_command(' '.join(args[j + 1:]), cwd, ctx, depth + 1)
    if prog == 'git':
        check_git(args, cwd, ctx)
    if PY_PROGRAM.match(prog):
        check_python(toks, seg, cwd, ctx)
    if prog in WRAPPERS:
        if ctx.on('delete') and prog in ('powershell', 'pwsh') and any(ENCODED_OPT.match(a) for a in low):
            raise Deny('delete', 'an encoded PowerShell command cannot be checked')
        j = 0
        while j < len(args):
            a = args[j].lower()
            if a in WRAPPER_VALUE_OPTS:
                j += 2
                continue
            if a.startswith('-') or (prog == 'cmd' and re.match(r'^/[a-z]$', a)) or \
                    re.match(r'^\d+(\.\d+)?[smhd]?$', a):
                j += 1
                continue
            break
        inner = ' '.join(args[j:])
        if inner:
            check_command(inner, cwd, ctx, depth + 1)
        for a in args:  # quoted inner commands and comma-separated argument lists
            for part in a.split(','):
                if part.strip() and part.strip() != inner:
                    check_command(part.strip(), cwd, ctx, depth + 1)


def check_command(text, cwd, ctx, depth=0):
    if depth > 5:
        return
    body, data, shell, _code = heredoc_split(text)
    if ctx.on('delete'):
        whole = text
        if any(PY_PROGRAM.match(base(t)) for s in split_segments(body)
               for t in strip_prefix(tokens(s))[:1]) and PY_DELETE.search(whole):
            raise Deny('delete', 'a Python delete call (rmtree, remove, unlink, rmdir)')
        if DOTNET_DELETE.search(body) or any(DOTNET_DELETE.search(s) for s in shell):
            raise Deny('delete', 'a .NET Delete call')
    for seg in split_segments(body):
        check_segment(seg, cwd, ctx, depth)
    for m in re.finditer(r'\$\(([^()]*)\)', body):  # substitutions inside double quotes
        check_command(m.group(1), cwd, ctx, depth + 1)
    for sh in shell:
        check_command(sh, cwd, ctx, depth + 1)


# ----------------------------------------------------------------------------- entry

def evaluate(payload, ctx=None):
    """None when the call may run, else a Deny with the matched rule."""
    ctx = ctx or Context()
    tool = payload.get('tool_name') or ''
    ti = payload.get('tool_input') or {}
    cwd = payload.get('cwd') or os.getcwd()
    try:
        if tool in ('Bash', 'PowerShell'):
            cmd = ti.get('command') or ''
            if ctx.on('protected_read'):
                check_command_paths(cmd, cwd, ctx)
            check_command(cmd, cwd, ctx)
        elif ctx.on('protected_read'):
            if tool == 'Read':
                check_tool_path(tool, ti.get('file_path'), cwd, ctx)
            elif tool in ('Edit', 'Write', 'NotebookEdit'):
                check_tool_path(tool, ti.get('file_path') or ti.get('notebook_path'), cwd, ctx,
                                write=True)
            elif tool == 'Grep':
                check_tool_path(tool, ti.get('path') or cwd, cwd, ctx, search_root=True)
                if ti.get('glob'):
                    g = ti['glob']
                    if key_hit(norm(g)) or any(k == 'blocked' for k, _ in role_hits(norm(g))):
                        raise Deny('protected_read', 'Grep glob reaches a protected folder')
            elif tool == 'Glob':
                root = ti.get('path') or cwd
                pattern = ti.get('pattern') or ''
                check_tool_path(tool, root, cwd, ctx)
                joined = pattern if re.match(r'^([a-zA-Z]:|/|~)', pattern) else \
                    str(root).rstrip('\\/') + '/' + pattern
                check_tool_path(tool, joined, cwd, ctx)
                nroot = resolve(root, cwd, ctx.home)
                if '**' in pattern and covers_protected(nroot, ctx, gitignore_aware=True):
                    raise Deny('protected_read', 'Glob ** over a folder that holds protected folders')
    except Deny as d:
        return d
    return None


def summary(payload):
    ti = payload.get('tool_input') or {}
    for key in ('command', 'file_path', 'notebook_path'):
        if ti.get(key):
            return str(ti[key])
    return ' '.join(str(ti.get(k)) for k in ('path', 'pattern', 'glob') if ti.get(k))


def log(record, ctx):
    try:
        ctx.private.mkdir(parents=True, exist_ok=True)
        with open(ctx.private / 'command_guard_log.jsonl', 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception:
        pass


def main(stdin=None, stdout=None, ctx=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    payload = {}
    try:
        raw = stdin.buffer.read().decode('utf-8-sig', 'replace') if hasattr(stdin, 'buffer') \
            else stdin.read().lstrip('﻿')
        payload = json.loads(raw or '{}')
        ctx = ctx or Context()
        verdict = evaluate(payload, ctx)
    except Exception as exc:  # fail open on the guard's own error, logged
        try:
            ctx = ctx or Context()
            log({'time': now(), 'tool': payload.get('tool_name', ''), 'rule': 'internal_error',
                 'decision': 'allowed (fail open)', 'error': redact(repr(exc), ctx.home)[:300],
                 'command': redact(summary(payload), ctx.home)[:200]}, ctx)
        except Exception:
            pass
        return 0
    if verdict is None:
        return 0
    reason = 'command_guard (%s): %s' % (verdict.rule, verdict.detail)
    try:
        log({'time': now(), 'tool': payload.get('tool_name', ''), 'rule': verdict.rule,
             'decision': 'denied', 'reason': redact(verdict.detail, ctx.home)[:300],
             'command': redact(summary(payload), ctx.home)[:200]}, ctx)
    except Exception:
        pass
    out = {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                  'permissionDecisionReason': redact(reason, ctx.home)}}
    stdout.write(json.dumps(out) + '\n')
    stdout.flush()
    return 0


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


if __name__ == '__main__':
    sys.exit(main())
