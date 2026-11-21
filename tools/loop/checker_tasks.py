"""Checkers and watch jobs started by Windows Task Scheduler, independent of any Claude session
(supervisor batch 2026-11-18 12:30 item E; lead 14:14; standing orders 103 and 106).

    py -3.12 -X utf8 tools/loop/checker_tasks.py compliance      # task ShimmerComplianceCheck, every 2 hours
    py -3.12 -X utf8 tools/loop/checker_tasks.py followthrough   # task ShimmerFollowthroughCheck, daily
    py -3.12 -X utf8 tools/loop/checker_tasks.py checkercheck    # task ShimmerCheckerCheck, daily (checker of the checkers)
    py -3.12 -X utf8 tools/loop/checker_tasks.py disksweep       # task ShimmerDiskSweepDaily, daily, DRY RUN ONLY
    py -3.12 -X utf8 tools/loop/checker_tasks.py recovery        # task ShimmerLoopRecovery, every 10 minutes

Each run appends one line to docs/loop/private/mechanism_trace.jsonl and writes ALERT.md when it fails.

The three checkers are fresh, headless Claude sessions (`claude -p`, model sonnet, effort medium, order 104),
in restricted mode with no MCP servers, no saved session, and permission mode dontAsk, so every tool use not
listed is refused without a prompt: Read, Grep, Glob; Bash only for the read-only commands in BASH_ALLOWED;
Write only under docs/loop/private/compliance/. The working folder is the main checkout, so role folders
outside it cannot be read; benchmark/keys is refused. A checker that writes no report but returns text has
that text saved by this runner as the report, as compliance/BRIEF.md asks. The compliance checker also runs
tools/loop/seckin_language_check.py (D-780: no decision numbers, file names, paths, commit ids or em dashes in
the main text of FOR_SECKIN and ALERT since 19 November 13:09) and reads the same entries for the language part.

disksweep runs tools/loop/disk_sweep.py --dry-run only and traces what it would remove. It never passes
--apply: deletions need Seckin's explicit yes to a dry-run list (his 11:29 rule, standing order 96) and this
lane deletes nothing (order 107). The lead runs --apply by hand after that yes.

recovery writes ALERT.md and a FOR_SECKIN entry (at most every 2 hours) when LOOP_STATE.md is not DONE, no
STOP_ALLOWED file exists, and no lead heartbeat (LEAD.lock heartbeat_utc; the file times of
continue_hook_state.json, poll_heartbeat.json, LOOP_STATE.md and LOOP_HEARTBEAT.txt, the lead's own beat file since
20 Nov 14:4x, as for the reaper in 5739d04d) is newer than 30 minutes. It never starts
Claude: a session is started only by the operator. Lambda machines are saved and stopped by the reaper
(ShimmerLoopReaper, SALVAGE-A), not here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mechanism_common as mc  # noqa: E402

COMPLIANCE_DIR = mc.PRIVATE / 'compliance'
FOR_SECKIN = mc.PRIVATE / 'FOR_SECKIN.md'
CLAUDE_TIMEOUT_S = 45 * 60
SILENT_S = 30 * 60
# D-780 (Seckin 19 Nov 2026 13:09): the form of what the loop writes for him, checked by pattern; read-only.
SECKIN_LANGUAGE_COMMAND = 'py -3.12 -X utf8 tools/loop/seckin_language_check.py'
BASH_ALLOWED = [
    'Bash(gh issue list:*)', 'Bash(gh issue view:*)', 'Bash(git log:*)', 'Bash(git show:*)',
    'Bash(git status:*)', 'Bash(git rev-parse:*)', 'Bash(git diff:*)', 'Bash(git branch:*)', 'Bash(date:*)',
    'Bash(ls:*)', 'Bash(wc:*)', 'Bash(stat:*)', 'Bash(df:*)', 'Bash(tasklist:*)', 'Bash(cd:*)',
    'Bash(py -3.12 -X utf8 launch.py preflight)',
    'Bash(%s)' % SECKIN_LANGUAGE_COMMAND,
    'Bash(powershell.exe -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB")',
]
RULES = ('Tools: Read, Grep and Glob anywhere in this checkout; Bash only for these read-only commands: %s; '
         'Write only for your one report under docs/loop/private/compliance/. Anything else is refused '
         'without a prompt, so do not try it. Never read benchmark keys, sealed material or role folders. '
         'Plain English, no em dashes, no personal paths (write <USER_HOME>). The time now is %s (+0300).')
KINDS = {
    'compliance': ('compliance_checker', 'COMPLIANCE',
                   'Read docs/loop/private/compliance/BRIEF.md and carry it out exactly. Write your report to '
                   'docs/loop/private/compliance/COMPLIANCE_%(stamp)s.md. For free RAM use the one allowed '
                   'powershell.exe command; for part (f) use cd into the folder, then the allowed preflight command. '
                   'Also run the allowed seckin_language_check.py command (D-780, Seckin\'s language rule for '
                   'FOR_SECKIN and ALERT since 2026-11-19 13:09) and put its last line and every flagged heading '
                   'and time in your report as a row | D-780 form | OK or BROKEN | its output |; then read the '
                   'same entries yourself for what the script cannot decide (natural Turkish with full Turkish '
                   'characters, short plain sentences, decisions shaped durum, soru, öneri) and say BROKEN with '
                   'the heading where one is not.'),
    'followthrough': ('followthrough_checker', 'FOLLOWTHROUGH',
                      'You are a fresh, read-only decision follow-through checker for the Shimmer loop (standing '
                      'order 103). You are not the lead and did not do the work. Read '
                      'docs/loop/private/DECISION_FOLLOWTHROUGH.md. For every row: is the decision carried out? '
                      'Check the evidence the row names (a file, commit, log line or result) yourself; a "Read:" '
                      'line or a statement of intent is not evidence. Flag every row whose expected time has '
                      'passed, every row marked DONE whose evidence you cannot find, and every row with no '
                      'done-means or no expected time. Write one report, '
                      'docs/loop/private/compliance/FOLLOWTHROUGH_%(stamp)s.md: a header (time, sources read), '
                      'then a table | # | Row | OK / BEHIND / BROKEN | Evidence (path, line, command output) | What '
                      'would make it OK |, BROKEN and BEHIND first, then counts. Return the BROKEN and BEHIND '
                      'items only, under 300 words.'),
    'checkercheck': ('checker_of_checkers', 'CHECKER_CHECK',
                     'You are the checker of the checkers for the Shimmer loop (standing orders 103 and 106). '
                     'Read the newest docs/loop/private/compliance/COMPLIANCE_*.md and the newest '
                     'docs/loop/private/compliance/FOLLOWTHROUGH_*.md (if one exists). From each pick 5 items, '
                     'mixing OK and BROKEN or BEHIND ones, and check each again yourself against the evidence. '
                     'Say for each whether you agree, and why, with the evidence. Also say whether each report '
                     'covered everything its brief (compliance/BRIEF.md; order 103 for the follow-through) asks. '
                     'Write one report, docs/loop/private/compliance/CHECKER_CHECK_%(stamp)s.md, with a table | '
                     '# | Report | Item | Their verdict | Your verdict | Evidence |, then counts of agreements '
                     'and disagreements. Return the disagreements only, under 300 words.'),
}


def stamp(t):
    return t.strftime('%Y%m%d_%H%M')


def write_rules():
    """Write allowed only under compliance/. Claude Code matches the Write tool against Edit(...) rules, not
    Write(...) rules: the 14:25 and 14:31 runs were refused under Write(...) rules, and a scratch test at 14:35
    showed Edit(./x/**), Edit(x/**), Edit(//c/...) and Edit(C:/...) all let the Write through. Only the Write
    tool is given (no Edit tool), so this grants nothing else."""
    posix = COMPLIANCE_DIR.resolve().as_posix()             # C:/Users/.../compliance
    drive, rest = posix.split(':', 1)
    return ['Edit(./docs/loop/private/compliance/**)', 'Edit(//%s%s/**)' % (drive.lower(), rest)]


def run_claude(prompt, timeout=CLAUDE_TIMEOUT_S):
    exe = shutil.which('claude') or str(Path.home() / '.local' / 'bin' / 'claude.exe')
    cmd = [exe, '-p', prompt, '--restricted', '--strict-mcp-config', '--tools', 'Read,Grep,Glob,Bash,Write',
           '--allowedTools', *(['Read', 'Grep', 'Glob'] + write_rules() + BASH_ALLOWED),
           '--disallowedTools', 'Read(./benchmark/keys/**)', 'WebFetch', 'WebSearch',
           '--permission-mode', 'dontAsk', '--model', 'sonnet', '--effort', 'medium',
           '--no-session-persistence', '--output-format', 'json']
    env = dict(os.environ, CLAUDE_CODE_EFFORT_LEVEL='medium', CLAUDECODE='', PYTHONDONTWRITEBYTECODE='1')
    try:
        done = subprocess.run(cmd, cwd=str(mc.MAIN), capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=timeout, stdin=subprocess.DEVNULL, env=env,
                              creationflags=mc.no_window())
    except subprocess.TimeoutExpired:
        return 124, {}, 'timed out after %d s' % timeout
    except OSError as exc:
        return 127, {}, 'claude could not start (%s)' % type(exc).__name__
    try:
        data = json.loads(done.stdout)
    except ValueError:
        data = {}
    return done.returncode, data, (done.stderr or '').strip()[-300:]


def verdict_counts(text):
    counts = {}
    for word in ('BROKEN', 'BEHIND', 'OK'):
        counts[word] = len(re.findall(r'\|\s*\**%s\**\s*\|' % word, text))
    return counts


def checker(kind):
    name, prefix, task = KINDS[kind]
    if not mc.wait_for_ram(name):
        mc.trace(name, 'deferred_ram', ram_free_gib=mc.free_ram_gib())
        mc.alert(name + ':ram', '%s did not start: free RAM stayed under 2.1 GiB for 10 minutes.' % name)
        return 3
    start = mc.now()
    st = stamp(start)
    mc.trace(name, 'started', model='sonnet', effort='medium')
    prompt = (task % {'stamp': st}) + '\n\n' + RULES % ('; '.join(BASH_ALLOWED), start.strftime('%Y-%m-%d %H:%M'))
    code, data, err = run_claude(prompt)
    target = COMPLIANCE_DIR / ('%s_%s.md' % (prefix, st))
    # Only the file this run was told to write counts: another session's report written meanwhile is not ours.
    reports = [target] if target.exists() and target.stat().st_mtime >= start.timestamp() - 5 else []
    saved_from_reply = False
    text = data.get('result') or ''
    denials = data.get('permission_denials') or []
    if not reports and text.strip():
        if not target.exists():
            target.write_text('<!-- saved by tools/loop/checker_tasks.py from the checker reply; the checker '
                              'did not write the file itself -->\n' + text, encoding='utf-8', newline='\n')
            reports, saved_from_reply = [target], True
    details = {'exit': code, 'model': 'sonnet', 'effort': 'medium', 'is_error': data.get('is_error'),
               'num_turns': data.get('num_turns'), 'duration_min': round((data.get('duration_ms') or 0) / 60000, 1),
               'cost_usd_reported': data.get('total_cost_usd'), 'saved_from_reply': saved_from_reply,
               'permission_denials': len(denials),
               'denied_first': [str(d.get('tool_name')) + ' ' + json.dumps(d.get('tool_input'))[:120]
                                for d in denials[:5] if isinstance(d, dict)]}
    if reports:
        report = max(reports, key=lambda p: p.stat().st_mtime)
        details.update(report=str(report.relative_to(mc.MAIN)).replace('\\', '/'),
                       verdicts=verdict_counts(report.read_text(encoding='utf-8', errors='replace')))
        mc.trace(name, 'ok', **details)
        return 0
    details['stderr_last'] = err
    details['reply_first'] = text[:300]
    mc.trace(name, 'failed', **details)
    mc.alert(name + ':failed', '%s (Windows task, headless claude -p sonnet medium) wrote no report: exit %s%s. '
             'Evidence: docs/loop/private/mechanism_trace.jsonl.' % (name, code, (', ' + err[:150]) if err else ''))
    return 1


def disksweep():
    name = 'disk_sweep_dry_run'
    if not mc.wait_for_ram(name):
        mc.trace(name, 'deferred_ram', ram_free_gib=mc.free_ram_gib())
        return 3
    cmd = mc.python_cmd() + [str(HERE / 'disk_sweep.py'), '--dry-run']
    try:
        done = subprocess.run(cmd, cwd=str(mc.MAIN), capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=7200, stdin=subprocess.DEVNULL, creationflags=mc.no_window())
        code, out, err = done.returncode, done.stdout or '', done.stderr or ''
    except subprocess.TimeoutExpired:
        code, out, err = 124, '', 'timed out'
    lines = [ln for ln in out.splitlines() if ln.strip()]
    sizes = re.findall(r'([0-9.]+)\s*(GiB|MiB|GB|MB)', '\n'.join(lines[-5:]))
    details = {'exit': code, 'mode': 'dry-run only (no --apply: deletions need Seckin\'s yes to the list; '
               'order 96 and 107)', 'free_disk_gib': round(shutil.disk_usage('C:/').free / mc.GIB, 2),
               'summary_last_lines': [ln[:200] for ln in lines[-4:]], 'sizes_named': sizes[:6]}
    if code != 0:
        details['stderr_last'] = err.strip()[-200:]
        mc.trace(name, 'failed', **details)
        mc.alert(name + ':failed', 'Disk sweep dry run (task ShimmerDiskSweepDaily) failed, exit %d.' % code)
        return 1
    mc.trace(name, 'ok', **details)
    return 0


def lead_heartbeats():
    out = {}
    lock = mc.PRIVATE / 'LEAD.lock'
    try:
        m = re.search(r'^heartbeat_utc:\s*(\S+)', lock.read_text(encoding='utf-8'), re.M)
        if m:
            out['LEAD.lock heartbeat_utc'] = dt.datetime.fromisoformat(m.group(1).replace('Z', '+00:00'))
    except (OSError, ValueError):
        pass
    for rel in ('continue_hook_state.json', 'poll_heartbeat.json', 'LOOP_STATE.md', 'LOOP_HEARTBEAT.txt'):
        p = mc.PRIVATE / rel
        if p.exists():
            out[rel + ' written'] = dt.datetime.fromtimestamp(p.stat().st_mtime).astimezone()
    return out


def loop_status():
    try:
        for line in (mc.PRIVATE / 'LOOP_STATE.md').read_text(encoding='utf-8').splitlines():
            if line.startswith('- Status:'):
                return line[len('- Status:'):].strip()
    except OSError:
        return 'LOOP_STATE.md unreadable'
    return 'no status line'


def add_for_seckin(title, body):
    try:
        old = FOR_SECKIN.read_text(encoding='utf-8')
    except OSError:
        old = '# For Seckin\n'
    head, _, rest = old.partition('\n')
    entry = '## %s: %s\n\n%s\n\n---\n' % (mc.now().strftime('%Y-%m-%d %H:%M %z'), title, body)
    new = head + '\n\n' + entry + '\n' + rest.lstrip('\n')
    tmp = FOR_SECKIN.with_name(FOR_SECKIN.name + '.writing')
    tmp.write_text(new, encoding='utf-8', newline='\n')
    os.replace(tmp, FOR_SECKIN)


def recovery():
    name = 'loop_recovery'
    t = mc.now()
    beats = lead_heartbeats()
    newest_key = max(beats, key=lambda k: beats[k]) if beats else None
    newest = beats.get(newest_key)
    silent_s = None if newest is None else (t - newest).total_seconds()
    status = loop_status()
    done = status.upper().startswith('DONE')
    stop_allowed = (mc.PRIVATE / 'STOP_ALLOWED').exists()
    silent = silent_s is None or silent_s > SILENT_S
    details = {'loop_status': status[:80], 'stop_allowed': stop_allowed,
               'newest_heartbeat': newest.isoformat(timespec='seconds') if newest else None,
               'newest_heartbeat_source': newest_key,
               'silent_min': None if silent_s is None else round(silent_s / 60, 1),
               'heartbeats': {k: v.astimezone().isoformat(timespec='seconds') for k, v in beats.items()},
               'starts_claude': False}
    if silent and not done and not stop_allowed:
        first = mc.alert('loop_recovery:silent', 'Loop lead silent: no lead heartbeat for %s minutes (newest %s, %s); '
                         'LOOP_STATE is not DONE. Please restart the lead session. Task ShimmerLoopRecovery only '
                         'reports; it starts nothing. Lambda machines are watched by ShimmerLoopReaper.' % (
                             details['silent_min'], details['newest_heartbeat'], newest_key), every=2 * 3600)
        if first:
            add_for_seckin('SORU: Döngü oturumu %s dakikadır ses vermiyor; yeniden başlatır mısın?' % (
                int(details['silent_min']) if details['silent_min'] is not None else 'uzun süre'),
                'Son işaret: %s (%s). LOOP_STATE durumu DONE değil, STOP_ALLOWED yok. Bu satırı Windows görevi '
                'ShimmerLoopRecovery yazdı; Claude\'u kendisi başlatmaz, yalnızca haber verir. Kiralık makineleri '
                'ShimmerLoopReaper ayrıca izliyor. Kanıt: docs/loop/private/mechanism_trace.jsonl.' % (
                    details['newest_heartbeat'], newest_key))
        details['alert_written'] = first
        mc.trace(name, 'lead_silent', **details)
        return 0
    mc.trace(name, 'ok', **details)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('kind', choices=sorted(list(KINDS) + ['disksweep', 'recovery']))
    args = ap.parse_args(argv)
    if args.kind in KINDS:
        return checker(args.kind)
    return disksweep() if args.kind == 'disksweep' else recovery()


if __name__ == '__main__':
    raise SystemExit(main())
