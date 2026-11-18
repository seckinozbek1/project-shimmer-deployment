"""Checks for tools/loop/command_guard.py: fixture hook JSON only, no command is ever run.

Every blocked case must be denied by its rule, every allowed case must pass, and with each
rule switched off (neutralised) its own cases must stop being denied, which proves the
checks see the rule and not something else. main() is driven end to end with a temporary
log folder: a deny prints the PreToolUse JSON, the log line carries <USER_HOME>, and an
internal error fails open with a logged line.

    python tools/loop/command_guard_checks.py      exit 0 when every check holds
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import command_guard as cg  # noqa: E402

HOME = 'C:/Users/fixture_user'
MAIN = HOME + '/local/shimmer-deployment'
ROLES = HOME + '/local/shimmer-roles'
EXISTING = {cg.norm(p) for p in (
    MAIN, MAIN + '/benchmark', MAIN + '/benchmark/keys', MAIN + '/tools',
    MAIN + '/docs/loop/private/role_starts/start_s1.cmd', HOME, HOME + '/local', ROLES,
)}
APPROVAL = ('C:/Users/fixture_user/local/old_wt | Seckin yes: SUPERVISOR_INBOX '
            '2026-11-18 12:24 item 3\n'
            'C:/Users/fixture_user/local/undated | Seckin yes\n')


def ctx(disabled=(), hook=True, private=None):
    c = cg.Context(home=HOME, main=MAIN, approvals=APPROVAL,
                   prepush=lambda d: (hook, 'hooks/pre-push'),
                   exists=lambda p: cg.norm(p) in EXISTING, disabled=disabled)
    if private:
        c.private = Path(private)
    return c


def sh(cmd, tool='Bash'):
    return {'tool_name': tool, 'tool_input': {'command': cmd}, 'cwd': MAIN}


def ps(cmd):
    return sh(cmd, 'PowerShell')


def tool(name, **ti):
    return {'tool_name': name, 'tool_input': ti, 'cwd': MAIN}


SD = 'py -3.12 -X utf8 tools/loop/safe_delete.py '
BLOCKED = [
    # (label, payload, rule)
    ('rm -rf', sh('rm -rf output/old'), 'delete'),
    ('rmdir', sh('rmdir build'), 'delete'),
    ('del', ps('del /q notes.txt'), 'delete'),
    ('erase', ps('erase notes.txt'), 'delete'),
    ('Remove-Item', ps('Remove-Item -Recurse -Force external\\x'), 'delete'),
    ('ri alias', ps('ri x.txt'), 'delete'),
    ('rd alias', ps('rd x'), 'delete'),
    ('pipe into Remove-Item', ps('Get-ChildItem tmp | Remove-Item'), 'delete'),
    ('script block delete', ps('foreach ($f in $a) { Remove-Item $f }'), 'delete'),
    ('Clear-Content', ps('Clear-Content log.txt'), 'delete'),
    ('git clean', sh('git clean -fdx'), 'delete'),
    ('git -C clean', sh('git -C ../wt clean -n'), 'delete'),
    ('git worktree remove', sh('git worktree remove --force ../wt'), 'delete'),
    ('git reset --hard', sh('git reset --hard HEAD~1'), 'delete'),
    ('git push --force', sh('git push --force origin main'), 'delete'),
    ('git push -f', sh('git push -f origin main'), 'delete'),
    ('git push --force-with-lease', sh('git push --force-with-lease origin main'), 'delete'),
    ('git push +refspec', sh('git push origin +main'), 'delete'),
    ('git push --delete', sh('git push origin --delete lane/x'), 'delete'),
    ('git branch -D', sh('git branch -D lane/x'), 'delete'),
    ('robocopy /MIR', ps('robocopy a b /MIR'), 'delete'),
    ('robocopy /PURGE', ps('robocopy a b /PURGE'), 'delete'),
    ('cmd /c rd', ps('cmd /c "rd /s /q x"'), 'delete'),
    ('powershell -Command', sh('powershell -NoProfile -Command "Remove-Item x"'), 'delete'),
    ('bash -c rm', ps('bash -lc "rm -f x"'), 'delete'),
    ('substitution in quotes', sh('echo "$(rm -rf x)"'), 'delete'),
    ('find -delete', sh('find . -name "*.tmp" -delete'), 'delete'),
    ('python rmtree heredoc', sh("python - <<'EOF'\nimport shutil\nshutil.rmtree('x')\nEOF"),
     'delete'),
    ('dotnet Delete', ps("[System.IO.File]::Delete('x')"), 'delete'),
    ('encoded powershell', ps('powershell -EncodedCommand SQBFAFgA'), 'delete'),
    ('safe_delete --execute unapproved', sh(SD + 'C:/Users/fixture_user/local/other --execute'),
     'safe_delete_approval'),
    ('safe_delete --execute undated yes', sh(SD + 'C:/Users/fixture_user/local/undated --execute'),
     'safe_delete_approval'),
    ('Read answer key', tool('Read', file_path=MAIN + '/benchmark/keys/a.json'), 'protected_read'),
    ('cat answer key', sh('cat benchmark/keys/a.json'), 'protected_read'),
    ('Get-Content answer key', ps('Get-Content benchmark\\keys\\a.json'), 'protected_read'),
    ('answer key wildcard', sh('ls benchmark/k*'), 'protected_read'),
    ('grep -r over checkout', sh('grep -rn secret .'), 'protected_read'),
    ('grep -r, working folder implied', sh('grep -r secret'), 'protected_read'),
    ('Grep tool on benchmark', tool('Grep', pattern='x', path=MAIN + '/benchmark'), 'protected_read'),
    ('Read role B', tool('Read', file_path=ROLES + '/B/notes.md'), 'protected_read'),
    ('Read role V', tool('Read', file_path=ROLES + '/V/x.md'), 'protected_read'),
    ('Read role N', tool('Read', file_path=ROLES + '/N/x.md'), 'protected_read'),
    ('Read _seckin', tool('Read', file_path=ROLES + '/_seckin/x.md'), 'protected_read'),
    ('Read _xfer/B_to_V', tool('Read', file_path=ROLES + '/_xfer/B_to_V/x.md'), 'protected_read'),
    ('Read _xfer/N_to_seals', tool('Read', file_path=ROLES + '/_xfer/N_to_seals/x'), 'protected_read'),
    ('Read _xfer/lead_to_B', tool('Read', file_path=ROLES + '/_xfer/lead_to_B/x.md'), 'protected_read'),
    ('Write role B', tool('Write', file_path=ROLES + '/B/x.md', content='x'), 'protected_read'),
    ('Edit _xfer/C_to_B', tool('Edit', file_path=ROLES + '/_xfer/C_to_B/x.md'), 'protected_read'),
    ('Get-Content role C', ps('Get-Content C:\\Users\\fixture_user\\local\\shimmer-roles\\C\\a.md'),
     'protected_read'),
    ('cat role S via ~', sh('cat ~/local/shimmer-roles/S/a.md'), 'protected_read'),
    ('cat role R via /c', sh('cat /c/Users/fixture_user/local/shimmer-roles/R/a.md'), 'protected_read'),
    ('Get-Content lead_to read', ps('Get-Content $HOME\\local\\shimmer-roles\\_xfer\\lead_to_S\\a'),
     'protected_read'),
    ('role wildcard', sh('ls ~/local/shimmer-roles/*'), 'protected_read'),
    ('cd into roles', ps('cd C:\\Users\\fixture_user\\local\\shimmer-roles'), 'protected_read'),
    ('recursive over roles', ps('Get-ChildItem -Recurse C:\\Users\\fixture_user\\local\\shimmer-roles'),
     'protected_read'),
    ('listing piped to reader', ps('Get-ChildItem -Recurse C:\\Users\\fixture_user\\local | '
                                   'Select-String token'), 'protected_read'),
    ('Grep tool on roles root', tool('Grep', pattern='x', path=ROLES), 'protected_read'),
    ('Grep tool on home', tool('Grep', pattern='x', path=HOME), 'protected_read'),
    ('Glob ** from home', tool('Glob', pattern='**/*.md', path=HOME), 'protected_read'),
    ('Glob into role V', tool('Glob', pattern='V/*.md', path=ROLES), 'protected_read'),
    # real reads in a reading position (lead, 18 Nov 14:34)
    ('python script argument', sh('py -3.12 tools/x.py benchmark/keys/a.json'), 'protected_read'),
    ('python -c code', ps('py -c "print(open(\'benchmark/keys/a.json\').read())"'), 'protected_read'),
    ('python heredoc program', sh("python - <<'EOF'\nprint(open('benchmark/keys/a.json').read())\nEOF"),
     'protected_read'),
    ('cmd type', ps('cmd /c type benchmark\\keys\\a.json'), 'protected_read'),
    ('redirect source', sh('sort < benchmark/keys/a.json'), 'protected_read'),
    ('Copy-Item source key', ps('Copy-Item benchmark\\keys\\a.json C:\\Temp\\'), 'protected_read'),
    ('Copy-Item source lead_to', ps('Copy-Item C:\\Users\\fixture_user\\local\\shimmer-roles\\_xfer\\'
                                    'lead_to_S\\a.md C:\\Temp\\'), 'protected_read'),
    ('Get-Content -Path:', ps('Get-Content -Path:benchmark/keys/a.json'), 'protected_read'),
    ('Select-String -Path key', ps('Select-String -Pattern x -Path benchmark\\keys\\*.json'),
     'protected_read'),
    ('grep file argument', sh('grep -n token benchmark/keys/a.json'), 'protected_read'),
    ('dir keys', ps('dir benchmark\\keys'), 'protected_read'),
    ('Get-ChildItem role V', ps('Get-ChildItem C:\\Users\\fixture_user\\local\\shimmer-roles\\V'),
     'protected_read'),
    ('powershell -Command read', sh('powershell -NoProfile -Command "Get-Content benchmark/keys/a.json"'),
     'protected_read'),
    ('subexpression in expandable here-string',
     ps('@"\nkeys: $(Get-Content benchmark/keys/a.json)\n"@ | Set-Content out.md'), 'protected_read'),
    ('role root in a variable', ps('$r = "C:\\Users\\fixture_user\\local\\shimmer-roles"'),
     'protected_read'),
    ('git push, hook missing', sh('git push origin main'), 'push_hook'),
    ('git push --no-verify', sh('git push --no-verify origin main'), 'push_hook'),
]
ALLOWED = [
    ('git status', sh('git status')),
    ('PowerShell git status', ps('git status --short')),
    ('Read DECISIONS.md', tool('Read', file_path=MAIN + '/docs/loop/DECISIONS.md')),
    ('safe_delete dry run', sh(SD + 'C:/Users/fixture_user/local/other')),
    ('safe_delete --execute approved', sh(SD + 'C:/Users/fixture_user/local/old_wt --execute')),
    ('commit message with rm in quotes', sh('git commit -m "docs: say rm -rf; del are refused"')),
    ('commit heredoc with rm line', sh("git commit -F - <<'EOF'\nrm -rf is refused now\nEOF")),
    ('git push with hook', sh('git push origin main')),
    ('git branch -d merged', sh('git branch -d lane/merged')),
    ('git rm --cached', sh('git rm --cached notes.txt')),
    ('Grep tool on checkout', tool('Grep', pattern='benchmark/keys', path=MAIN + '/scripts')),
    ('Grep tool on checkout root', tool('Grep', pattern='x', path=MAIN)),
    ('Glob ** in checkout', tool('Glob', pattern='**/*.py', path=MAIN)),
    ('Read _xfer/S_to_lead', tool('Read', file_path=ROLES + '/_xfer/S_to_lead/r.md')),
    ('Read _xfer/B_to_lead_dev', tool('Read', file_path=ROLES + '/_xfer/B_to_lead_dev/r.md')),
    ('Read _xfer/N_to_lead', tool('Read', file_path=ROLES + '/_xfer/N_to_lead/r.md')),
    ('Read _xfer/B_to_seals', tool('Read', file_path=ROLES + '/_xfer/B_to_seals/r.md')),
    ('Read _handoff', tool('Read', file_path=ROLES + '/_handoff/h.md')),
    ('Write _xfer/lead_to_B', tool('Write', file_path=ROLES + '/_xfer/lead_to_B/x.md', content='x')),
    ('Copy-Item into lead_to_S', ps('Copy-Item report.md C:\\Users\\fixture_user\\local\\'
                                    'shimmer-roles\\_xfer\\lead_to_S\\')),
    ('run approved start file', ps('cmd /c docs\\loop\\private\\role_starts\\start_s1.cmd')),
    ('rg in checkout', sh('rg -n token scripts')),
    ('Get-ChildItem in tools', ps('Get-ChildItem -Recurse tools -Filter *.py')),
    ('pytest-like run', sh('py -3.12 -X utf8 tools/loop/command_guard_checks.py')),
    # protected paths inside literals written to a file are not reads (lead, 18 Nov 14:34)
    ('here-string report', ps("@'\nThe answer keys stay in benchmark/keys/ and role B works in\n"
                              "C:\\Users\\fixture_user\\local\\shimmer-roles\\B\\ only.\n'@ | "
                              "Set-Content -Path docs/loop/private/report.md -Encoding utf8")),
    ('Set-Content -Value literal', ps('Set-Content -Path r.md -Value "keys stay in benchmark/keys/"')),
    ('Add-Content quoted literal', ps('Add-Content r.md "role V folder: shimmer-roles/V/ is closed"')),
    ('echo into a file', sh('echo "see ~/local/shimmer-roles/_xfer/lead_to_B/ and benchmark/keys" > n.md')),
    ('bash heredoc to a file', sh("cat > n.md <<'EOF'\nbenchmark/keys/ and shimmer-roles/C/ are closed\nEOF")),
    ('commit message naming keys', sh('git commit -m "benchmark/keys stays ignored"')),
    ('Select-String for the key path text', ps('Select-String -Pattern "benchmark/keys" -Path scripts\\*.py')),
    ('grep for the key path text', sh('grep -n "benchmark/keys" scripts/verify_session1.py')),
    ('cd into an allowed folder', ps('cd C:\\Users\\fixture_user\\local\\shimmer-roles\\_xfer\\S_to_lead')),
]
# the reads the 14:34 change must keep blocking, used for the code-level neutralisation
READ_LABELS = ('python script argument', 'cmd type', 'redirect source', 'Copy-Item source key',
               'Get-Content -Path:', 'grep file argument', 'dir keys', 'Get-ChildItem role V',
               'cat answer key', 'Get-Content answer key')


def main():
    fails = []
    for label, payload, rule in BLOCKED:
        d = cg.evaluate(payload, ctx(hook=(rule != 'push_hook')))
        if d is None or d.rule != rule:
            fails.append('NOT BLOCKED as %s: %s -> %s' % (rule, label, d and d.rule))
    for label, payload in ALLOWED:
        d = cg.evaluate(payload, ctx())
        if d is not None:
            fails.append('WRONGLY BLOCKED: %s -> %s: %s' % (label, d.rule, d.detail))
    neutral = {}
    for r in cg.RULES:
        cases = [(l, p) for l, p, rr in BLOCKED if rr == r]
        still = [l for l, p in cases
                 if (lambda d: d is not None and d.rule == r)(
                     cg.evaluate(p, ctx(disabled={r}, hook=(r != 'push_hook'))))]
        passed = len(cases) - len(still)
        neutral[r] = (passed, len(cases))
        if still or not cases:
            fails.append('NEUTRALISED %s still blocks: %s' % (r, still or '(no cases)'))
    # code-level neutralisation: read_tokens returning nothing must let the real reads
    # through (fail), and restoring it must block them again (pass)
    saved = cg.read_tokens
    cases = [(l, p) for l, p, _ in BLOCKED if l in READ_LABELS]
    try:
        cg.read_tokens = lambda prog, toks: []
        leaked = [l for l, p in cases if cg.evaluate(p, ctx()) is None]
    finally:
        cg.read_tokens = saved
    restored = [l for l, p in cases if cg.evaluate(p, ctx()) is None]
    neutral['read_tokens (code)'] = (len(leaked), len(cases))
    if len(leaked) != len(cases) or len(cases) != len(READ_LABELS):
        fails.append('neutralised read_tokens still blocks: %s'
                     % sorted(set(l for l, _ in cases) - set(leaked)))
    if restored:
        fails.append('restored read_tokens lets through: %s' % restored)
    with tempfile.TemporaryDirectory() as tmp:
        out = io.StringIO()
        cg.main(io.StringIO(json.dumps(sh('rm -rf ' + HOME + '/local/x'))), out, ctx(private=tmp))
        res = json.loads(out.getvalue() or '{}').get('hookSpecificOutput', {})
        if res.get('permissionDecision') != 'deny' or res.get('hookEventName') != 'PreToolUse':
            fails.append('main() did not print a PreToolUse deny')
        logf = Path(tmp) / 'command_guard_log.jsonl'
        lines = logf.read_text(encoding='utf-8').splitlines() if logf.exists() else []
        if not lines or '<USER_HOME>' not in lines[-1] or 'fixture_user' in lines[-1]:
            fails.append('block log line missing or home not replaced: %r' % lines[-1:])
        rec = json.loads(lines[-1]) if lines else {}
        if not all(k in rec for k in ('time', 'tool', 'rule', 'command')):
            fails.append('block log line lacks a field: %r' % rec)
        out = io.StringIO()
        broken = ctx(private=tmp)

        def boom(d):
            raise RuntimeError('fixture failure')
        broken.prepush = boom
        code = cg.main(io.StringIO(json.dumps(sh('git push origin main'))), out, broken)
        lines = logf.read_text(encoding='utf-8').splitlines()
        if code != 0 or out.getvalue().strip() or 'internal_error' not in lines[-1]:
            fails.append('internal error did not fail open with a logged line')
        out = io.StringIO()
        cg.main(io.StringIO(json.dumps(sh('git status'))), out, ctx(private=tmp))
        if out.getvalue().strip():
            fails.append('allowed call printed output')
    print('blocked cases: %d, allowed cases: %d' % (len(BLOCKED), len(ALLOWED)))
    for r, (p, n) in neutral.items():
        print('neutralised %-21s %d of %d of its cases no longer blocked' % (r, p, n))
    for f in fails:
        print('FAIL ' + f)
    print('command_guard_checks: %s' % ('PASS' if not fails else 'FAIL (%d)' % len(fails)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
