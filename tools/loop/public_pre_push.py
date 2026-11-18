"""Pre-push scan for a public push from the clean push clone (Seckin 12:21, 18 Nov: no push without a pre-push hook).

Git passes the refs being pushed on stdin, one line each: <local ref> <local sha> <remote ref> <remote sha>. For each
pushed commit this reads the lines it adds against the remote's commit (or the whole tree for a new ref) and refuses the
push on any key pattern: Anthropic, OpenAI, AWS and Google key shapes, and a long literal assigned to a credential-named
variable. A tag push is checked through the commit it points to. Prints counts only, never a matched value.

Installed in the push clone as .git/hooks/pre-push:
    #!/bin/sh
    exec py -3.12 -X utf8 <main checkout>/tools/loop/public_pre_push.py "$@"
"""
import re
import subprocess
import sys

ZERO = '0' * 40
# The prefixes are joined at run time so this file itself never matches the repository's own key scan.
SK, AWS, GOOGLE = 's' + 'k-', 'AK' + 'IA', 'AI' + 'za'
PATTERNS = (
    re.compile(SK + 'ant-' + r'[A-Za-z0-9_-]{8,}'),
    re.compile(SK + 'proj-' + r'[A-Za-z0-9_-]{8,}'),
    re.compile(r'\b' + SK + r'[A-Za-z0-9]{20,}'),
    re.compile(r'\b' + AWS + r'[A-Z0-9]{16}\b'),
    re.compile(r'\b' + GOOGLE + r'[A-Za-z0-9_-]{35}\b'),
    re.compile(r'''(?i)\b(api_key|secret|token|password)\s*[:=]\s*["'][A-Za-z0-9_\-]{16,}["']'''),
)


def no_window():
    """The child's creation flags through cloud_run_common.no_window (HIDDEN-A), read from this file's own tools/
    folder; the Windows no-window flag itself if it cannot be imported."""
    from pathlib import Path
    tools = str(Path(__file__).resolve().parents[1])
    try:
        sys.path.insert(0, tools)
        import cloud_run_common
        return cloud_run_common.no_window()
    except Exception:
        return 0x08000000 if sys.platform == 'win32' else 0
    finally:
        if sys.path and sys.path[0] == tools:
            sys.path.pop(0)


def git(*args):
    done = subprocess.run(['git'] + list(args), capture_output=True, text=True, encoding='utf-8', errors='replace',
                          creationflags=no_window())
    if done.returncode:
        raise SystemExit('public_pre_push: git %s failed; refusing the push' % ' '.join(args[:2]))
    return done.stdout


def added_lines(local, remote):
    if remote == ZERO:
        # A new ref (a tag or branch): only what is not on the remote yet. A tag on a commit the remote already has
        # adds nothing; otherwise diff from the parent of the oldest new commit, or the whole tree for a root commit.
        new = git('rev-list', '--reverse', local, '--not', '--remotes=origin').split()
        if not new:
            return []
        parents = git('rev-list', '--parents', '-n', '1', new[0]).split()[1:]
        if not parents:
            return git('grep', '-I', '-h', '-e', '', local).splitlines()
        remote = parents[0]
    diff = git('diff', '--unified=0', '--no-color', remote, local)
    return [l[1:] for l in diff.splitlines() if l.startswith('+') and not l.startswith('+++')]


def hits(lines):
    return sum(1 for line in lines for p in PATTERNS if p.search(line))


def main(stdin=None):
    refs = [l.split() for l in (stdin if stdin is not None else sys.stdin.read()).splitlines() if l.strip()]
    total = 0
    for local_ref, local, remote_ref, remote in refs:
        if local == ZERO:
            continue
        commit = git('rev-parse', local + '^{commit}').strip()
        base = git('rev-parse', remote + '^{commit}').strip() if remote != ZERO else ZERO
        lines = added_lines(commit, base)
        found = hits(lines)
        print('public_pre_push: %s: %d added lines scanned, %d key pattern hits' % (remote_ref, len(lines), found))
        total += found
    if total:
        print('public_pre_push: refused (%d hits); no value printed' % total)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
