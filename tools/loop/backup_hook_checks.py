"""Fixture proofs for the pre-push hook exception of D-616 (tools/loop/pre_push_backup_exception.sh).

The template is composed into a throwaway hook (its @...@ words filled in, the S13 refusal after it), run by `sh` as
git runs a pre-push hook (the remote name and URL as arguments, the pushed refs on stdin), with `gh` faked through
PATH, a copy of the four pinned scan files in a temporary tree and a temporary bare repository as the fake remote.
Each proof has a neutralisation (an edit of the template text, of the tool copy, or of a tool function) that makes
it fail; check() runs each, restores and requires a pass.
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import os
import py_compile
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import backup_private as bp  # noqa: E402
from backup_private_checks import FAKE_KEY, Fixture, commit, failure_lines, sh  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloud_run_common import no_window  # noqa: E402  (D-079, HIDDEN-A)

TEMPLATE = HERE / 'pre_push_backup_exception.sh'
REAL_URL = 'https://github.com/seckinozbek1/project-shimmer-backup-private'
ZERO = '0' * 40
S13 = 'S13 REFUSAL'
FILES = {
    'tools/loop/backup_private.py': HERE / 'backup_private.py',
    'tools/loop/backup_allowlist.json': HERE / 'backup_allowlist.json',
    'scripts/guard_secrets.py': HERE.parents[1] / 'scripts' / 'guard_secrets.py',
    'tools/cloud_run_common.py': HERE.parent / 'cloud_run_common.py',
}
PIN_WORDS = {'tools/loop/backup_private.py': '@SHA_TOOL@', 'tools/loop/backup_allowlist.json': '@SHA_ALLOW@',
             'scripts/guard_secrets.py': '@SHA_GUARD@', 'tools/cloud_run_common.py': '@SHA_COMMON@'}

# The hook's literal `py -3.12` is the Windows launcher; a Linux gate has no such command (or a different one), so the
# tests always put a `py` shim for this interpreter first on PATH. (The neutralisation turns that off.)
SHIM_ALWAYS = True
SHIM_USED = True
SHIM_MODE = 0o755

# What the neutralisations change while their tests run.
ACTIVE = {'hook': None, 'tool': None}
LAST = {}
CRASH = ('        code, reason = hook_scan(', '        code, reason = 1 // 0 and hook_scan(')


def tool_tree(tmp, tool_change=None, tamper=None, missing=False, plant=None):
    """A copy of the four pinned files; the pins are taken from the copy as built (the tool change included),
    then `tamper` (relative path -> appended text) changes a file after the pins were taken."""
    root = Path(tmp) / 'tree'
    pins = {}
    for rel, source in FILES.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        if tool_change and rel == 'tools/loop/backup_private.py':
            text = data.decode('utf-8')
            old, new = tool_change
            assert text.count(old) == 1, old
            data = text.replace(old, new).encode('utf-8')
        target.write_bytes(data)
        pins[rel] = hashlib.sha256(data).hexdigest()
    for rel, data in (plant or {}).items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    for rel, extra in (tamper or {}).items():
        with open(root / rel, 'ab') as handle:
            handle.write(extra.encode('utf-8'))
    return (Path(tmp) / 'nowhere' if missing else root), pins


def composed(url, tmp, tree):
    text = TEMPLATE.read_text(encoding='utf-8')
    if ACTIVE['hook']:
        text = ACTIVE['hook'](text)
    root, pins = tree
    out = []
    for line in text.splitlines():
        if url is not None and line.startswith('backup_url='):
            line = 'backup_url="%s"' % url
        out.append(line)
    text = '\n'.join(out)
    text = text.replace('@TOOL_DIR@', root.as_posix())
    for rel, word in PIN_WORDS.items():
        text = text.replace(word, pins[rel])
    return text + '\necho "%s" >&2\nexit 1\n' % S13


def fake_gh(folder, mode):
    body = {'true': "printf 'true\\nprivate\\n'", 'false': "printf 'false\\npublic\\n'", 'none': 'exit 0',
            'fail': 'echo boom >&2; exit 1', 'spaces': "printf ' true\\nprivate\\n'", 'single': "printf 'true\\n'"}[mode]
    path = Path(folder) / 'gh'
    path.write_text('#!/bin/sh\n%s\n' % body, encoding='utf-8', newline='\n')
    path.chmod(0o755)


def hook_env(tmp, gh, extra=None, py_exe=None):
    # Off Windows there is no `py` launcher: a shim named py runs this interpreter (the hook's own call stays `py -3.12`).
    py_exe = py_exe or (sys.executable if (SHIM_ALWAYS or not shutil.which('py')) else None)
    gh_dir = Path(tmp) / 'ghbin'
    gh_dir.mkdir(exist_ok=True)
    fake_gh(gh_dir, gh)
    if SHIM_USED and py_exe:
        shim = gh_dir / 'py'
        shim.write_text(chr(10).join(['#!/bin/sh', 'shift', 'exec "%s" "$@"' % Path(py_exe).as_posix(), '']), encoding='utf-8', newline=chr(10))
        shim.chmod(SHIM_MODE)
    return dict(os.environ, PATH=str(gh_dir) + os.pathsep + os.environ['PATH'], **(extra or {}))


def run_hook(fx, tmp, name, url, lines, gh='true', real_url=False, tool_change=None, env_extra=None, py_exe=None, **tree_options):
    tree = tool_tree(tmp, tool_change or ACTIVE['tool'], **tree_options)
    hook = Path(tmp) / 'hook.sh'
    hook.write_text(composed(None if real_url else str(fx.backup), tmp, tree), encoding='utf-8', newline='\n')
    return subprocess.run(['sh', str(hook), name, url], cwd=str(fx.main), input=lines, env=hook_env(tmp, gh, env_extra, py_exe),
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300, creationflags=no_window())


def brief(done, all_stderr=False):
    """One short line saying why a hook run ended as it did: what the scan printed, then what the interpreter or
    the shell wrote to stderr (the hook's own refusal lines left out), so a gate line names the cause."""
    out = [x.strip() for x in done.stdout.splitlines() if x.strip()]
    err = [x.strip() for x in done.stderr.splitlines() if x.strip() and (all_stderr or not x.startswith('pre-push:'))]
    return ('rc=%s | %s | %s' % (done.returncode, ' / '.join(out)[-90:], ' / '.join(err)[-110:]))[:230]


def lines_for(fx, branch):
    sha = sh(fx.main, 'rev-parse', 'refs/heads/' + branch)
    return 'refs/heads/%s %s refs/heads/%s %s\n' % (branch, sha, branch, ZERO)


def drop(old, new):
    def change(text):
        assert old in text, old
        return text.replace(old, new)
    return change


def both(*changes):
    def change(text):
        for one in changes:
            text = one(text)
        return text
    return change


NAME_AND_URL = 'if [ "$1" = "$backup_name" ] && { [ "$2" = "$backup_url" ] || [ "$2" = "$backup_url.git" ]; }; then'
SCAN_CALL = 'if printf '+chr(39)+'%s\\n'+chr(39)+' "$backup_lines" | PYTHONPYCACHEPREFIX="$backup_tmp/pyc" py -3.12 -I -S -B -X utf8 "$backup_tree/tools/loop/backup_private.py" --hook-scan "$2"; then'
SCAN_IN_PLACE = ('if printf ' + chr(39) + '%s\\n' + chr(39) + ' "$backup_lines" | py -3.12 -X utf8 '
                 '"$backup_tool_dir/tools/loop/backup_private.py" --hook-scan "$2"; then')
COPY_FUNCTION = 'backup_copy() { mkdir -p "$backup_tree/$(dirname "$1")" && cp "$backup_tool_dir/$1" "$backup_tree/$1"; }'
TRAP = "  trap 'rm -r \"$backup_tmp\"' EXIT\n"
PIN_FUNCTION ='backup_pin_ok() { [ -f "$1" ] && [ "$(sha256sum "$1" | cut -d\' \' -f1)" = "$2" ]; }'
VISIBILITY = 'if [ "$backup_vis" != "$(printf \'true\\nprivate\')" ]; then'
SCAN_IGNORED = drop(SCAN_CALL, 'if true; then')
PINS_IGNORED = drop(PIN_FUNCTION, 'backup_pin_ok() { return 0; }')
WITH_SITE = drop(' -I -S -B ', ' -I -B ')
COPY_IGNORED = drop(COPY_FUNCTION, 'backup_copy() { return 0; }')
IN_PLACE = drop(SCAN_CALL, SCAN_IN_PLACE)
NO_TRAP = drop(TRAP, '')


class HookChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(self.tmp.name)
        self.fx.branch('lane/clean', 'ok.txt', 'fine' + chr(10))
        self.url = str(self.fx.backup)

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, name, url, branch='lane/clean', lines=None, **kw):
        return run_hook(self.fx, self.tmp.name, name, url, lines or lines_for(self.fx, branch), **kw)

    def refused(self, done, word=None):
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        if word:
            self.assertIn(word, done.stderr)

    def test_the_name_origin_and_the_origin_url_fall_through_to_the_refusal(self):
        for name, url in (('origin', str(self.fx.origin)), ('origin', self.url)):
            self.refused(self.hook(name, url), S13)
        self.refused(self.hook('backup-private', str(self.fx.origin)))

    def test_the_right_name_with_another_url_is_refused(self):
        self.refused(self.hook('backup-private', 'https://github.com/seckinozbek1/project-shimmer-deployment'), S13)
        self.refused(self.hook('backup-private', self.url + '-other'))

    def test_the_right_name_with_a_variant_of_the_real_url_is_refused(self):
        variants = [REAL_URL + '/', 'http://github.com/seckinozbek1/project-shimmer-backup-private',
                    'git@github.com:seckinozbek1/project-shimmer-backup-private.git',
                    'ssh://git@github.com/seckinozbek1/project-shimmer-backup-private', REAL_URL.upper(),
                    'https://user:pw@github.com/seckinozbek1/project-shimmer-backup-private',
                    REAL_URL + '-evil', 'x' + REAL_URL, REAL_URL + ' ']
        for url in variants:
            self.refused(self.hook('backup-private', url, real_url=True), S13)

    def test_a_visibility_that_is_not_true_is_refused(self):
        for mode in ('false', 'none', 'fail'):
            self.refused(self.hook('backup-private', self.url, gh=mode), 'visibility')

    def test_a_visibility_answer_with_spaces_or_missing_its_second_line_is_refused(self):
        for mode in ('spaces', 'single'):
            self.refused(self.hook('backup-private', self.url, gh=mode), 'visibility')

    def test_a_planted_key_and_a_seals_path_are_refused(self):
        self.fx.branch('lane/leaky', 'cfg.txt', 'v = %s' % FAKE_KEY + chr(10))
        done = self.hook('backup-private', self.url, branch='lane/leaky')
        self.refused(done)
        self.assertNotIn(FAKE_KEY, done.stdout + done.stderr)
        self.fx.branch('lane/seals', 'seals/x.json', '{}' + chr(10))
        self.refused(self.hook('backup-private', self.url, branch='lane/seals'))

    def test_an_annotated_tag_message_carrying_a_key_is_refused(self):
        sh(self.fx.main, 'tag', '-a', 'vkey', '-m', 'note %s' % FAKE_KEY, 'lane/clean')
        sha = sh(self.fx.main, 'rev-parse', 'refs/tags/vkey')
        done = self.hook('backup-private', self.url, lines='refs/tags/vkey %s refs/tags/vkey %s\n' % (sha, ZERO))
        self.refused(done)
        self.assertNotIn(FAKE_KEY, done.stdout + done.stderr)

    def test_a_tag_object_pushed_to_a_branch_is_refused(self):
        sh(self.fx.main, 'tag', '-a', 'vplain', '-m', 'plain note', 'lane/clean')
        sha = sh(self.fx.main, 'rev-parse', 'refs/tags/vplain')
        self.refused(self.hook('backup-private', self.url, lines='refs/heads/x %s refs/heads/x %s\n' % (sha, ZERO)))

    def test_a_delete_only_push_is_refused(self):
        sha = sh(self.fx.main, 'rev-parse', 'refs/heads/lane/clean')
        self.refused(self.hook('backup-private', self.url, lines='refs/heads/gone %s refs/heads/gone %s\n' % (ZERO, sha)))

    def test_a_repository_with_a_replace_ref_is_refused(self):
        a = sh(self.fx.main, 'rev-parse', 'refs/heads/lane/clean')
        b = sh(self.fx.main, 'rev-parse', 'refs/heads/main')
        sh(self.fx.main, 'replace', '-f', a, b)
        self.refused(self.hook('backup-private', self.url))

    def test_a_missing_scan_tool_is_refused(self):
        self.refused(self.hook('backup-private', self.url, missing=True), 'pinned')

    def test_a_crashing_scan_is_refused(self):
        self.refused(self.hook('backup-private', self.url, tool_change=CRASH), 'scan')

    def test_a_changed_scan_file_is_refused(self):
        for rel in FILES:
            self.refused(self.hook('backup-private', self.url, tamper={rel: ' # changed'}), 'pinned')

    def planted(self, plant, **extra):
        marker = Path(self.tmp.name) / 'marker.txt'
        code = ('open(%r, "w").write("ran")' % str(marker) + chr(10) + 'raise SystemExit(0)' + chr(10)).encode('utf-8')
        self.count = getattr(self, 'count', 0) + 1
        branch = 'lane/leaky%d' % self.count
        self.fx.branch(branch, 'cfg.txt', 'v = %s' % FAKE_KEY + chr(10))
        done = self.hook('backup-private', self.url, branch=branch, plant=plant(code), **extra)
        self.assertFalse(marker.exists(), 'planted code ran')
        self.refused(done, 'scan')
        return done

    def test_a_planted_module_beside_the_pinned_files_does_not_run(self):
        self.planted(lambda code: {'tools/loop/json.py': code})
        self.planted(lambda code: {'scripts/json.py': code, 'tools/json.py': code})

    def test_a_planted_pyc_and_a_planted_pythonpath_do_not_run(self):
        def pycs(code):
            work = Path(self.tmp.name) / 'plant'
            work.mkdir(exist_ok=True)
            source = work / 'evil.py'
            source.write_bytes(code)
            out = {}
            sourceless = work / 'json.pyc'
            py_compile.compile(str(source), cfile=str(sourceless), doraise=True)
            out['tools/loop/json.pyc'] = sourceless.read_bytes()
            cache = work / 'guard.pyc'
            py_compile.compile(str(source), cfile=str(cache), doraise=True,
                               invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
            tag = Path(importlib.util.cache_from_source('scripts/guard_secrets.py')).as_posix()
            out[tag] = cache.read_bytes()
            return out
        self.planted(pycs)
        evil_dir = Path(self.tmp.name) / 'evilpath'
        evil_dir.mkdir()

        def on_path(code):
            evil_dir.joinpath('json.py').write_bytes(code)
            return {}
        self.planted(on_path, env_extra={'PYTHONPATH': str(evil_dir)})

    def test_the_temporary_folder_is_removed_on_every_exit(self):
        scratch = Path(self.tmp.name) / 'scratch'
        scratch.mkdir()
        extra = {'TMPDIR': scratch.as_posix()}
        done = self.hook('backup-private', self.url, env_extra=extra)
        self.assertEqual(done.returncode, 0, brief(done))
        self.assertEqual(list(scratch.iterdir()), [])
        self.fx.branch('lane/leaky', 'cfg.txt', 'v = %s' % FAKE_KEY + chr(10))
        done = self.hook('backup-private', self.url, branch='lane/leaky', env_extra=extra)
        self.refused(done)
        self.assertEqual(list(scratch.iterdir()), [])
        done = self.hook('backup-private', self.url, env_extra=extra, tamper={'scripts/guard_secrets.py': ' # x'})
        self.refused(done, 'pinned')
        self.assertEqual(list(scratch.iterdir()), [])

    def test_a_planted_site_pth_and_sitecustomize_do_not_run(self):
        venv = Path(self.tmp.name) / 'venv'
        subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(venv)], check=True, capture_output=True, creationflags=no_window())
        exe = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        site = subprocess.run([str(exe), '-c', 'import sysconfig;print(sysconfig.get_paths()["purelib"])'],
                              capture_output=True, text=True, check=True, creationflags=no_window()).stdout.strip()
        marker = Path(self.tmp.name) / 'site_marker.txt'
        body = 'open(%r, "w").write("ran")' % str(marker)
        (Path(site) / 'evil.pth').write_text('import os; ' + body + chr(10), encoding='utf-8')
        (Path(site) / 'sitecustomize.py').write_text(body + chr(10), encoding='utf-8')
        self.fx.branch('lane/leaky', 'cfg.txt', 'v = %s' % FAKE_KEY + chr(10))
        done = self.hook('backup-private', self.url, branch='lane/leaky', py_exe=exe)
        self.assertFalse(marker.exists(), 'site code ran')
        self.refused(done, 'scan')

    def test_the_isolated_interpreter_starts_and_runs_the_scan_from_the_copy(self):
        # What the hook relies on, run the way the hook runs it (through sh, the `py` found on PATH, -I -S -B): the
        # standard library modules the scan needs import, and the tool starts from a copy (an empty push is refused
        # for its own reason).
        env = hook_env(self.tmp.name, 'true')
        modules = ('json, subprocess, tarfile, lzma, bz2, zipfile, ipaddress, hashlib, argparse, threading, contextlib, '
                   'gzip, io, re, pathlib, datetime, math, os, sys')
        probe = subprocess.run(['sh', '-c', 'command -v py >/dev/null || { echo "no py on PATH" >&2; exit 127; }; py -3.12 -I -S -B -X utf8 -c "import ' + modules + '"'],
                               env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120, creationflags=no_window())
        self.assertEqual(probe.returncode, 0, 'rc=%s %s' % (probe.returncode, ' '.join((probe.stdout + probe.stderr).split())[-190:]))
        tree = tool_tree(self.tmp.name)[0]
        started = subprocess.run(['sh', '-c', 'py -3.12 -I -S -B -X utf8 "$0" --hook-scan', str(tree / 'tools/loop/backup_private.py')],
                                 input='', cwd=str(self.fx.main), env=env, capture_output=True, text=True, encoding='utf-8',
                                 errors='replace', timeout=120, creationflags=no_window())
        self.assertEqual(started.returncode, 1, 'rc=%s %s' % (started.returncode, ' '.join((started.stdout + started.stderr).split())[-190:]))
        self.assertIn('could not be read', started.stdout)

    def test_the_py_shim_and_the_fake_gh_are_executable_for_sh(self):
        if os.name == 'nt':
            self.skipTest('the executable bit is POSIX only; Windows ignores it')
        old = os.umask(0o022)
        try:
            env = hook_env(self.tmp.name, 'true')
        finally:
            os.umask(old)
        for name in ('py', 'gh'):
            self.assertTrue(os.access(Path(self.tmp.name) / 'ghbin' / name, os.X_OK), name)
        self.assertEqual(subprocess.run(['sh', '-c', 'command -v py'], env=env, capture_output=True, creationflags=no_window()).returncode, 0)

    def test_a_decoy_py_command_on_the_path_does_not_decide_which_python_runs_the_scan(self):
        decoy = Path(self.tmp.name) / 'decoy'
        decoy.mkdir()
        (decoy / 'py').write_text('#!/bin/sh' + chr(10) + 'exit 127' + chr(10), encoding='utf-8', newline=chr(10))
        (decoy / 'py').chmod(0o755)
        with patch.dict(os.environ, {'PATH': str(decoy) + os.pathsep + os.environ['PATH']}):
            done = self.hook('backup-private', self.url)
        self.assertEqual(done.returncode, 0, brief(done))

    def test_a_clean_push_to_the_right_name_and_url_passes(self):
        done = self.hook('backup-private', self.url)
        self.assertEqual(done.returncode, 0, brief(done))
        self.assertNotIn(S13, done.stderr)

    def test_the_template_names_the_exact_target_and_pins_the_scan(self):
        text = TEMPLATE.read_text(encoding='utf-8')
        self.assertIn('backup_url="%s"' % REAL_URL, text)
        self.assertIn('backup_name="backup-private"', text)
        self.assertIn('--hostname github.com', text)
        self.assertNotIn('--show-toplevel', text)
        self.assertNotIn('worktrees', text)
        self.assertNotIn('SHIMMER_PUSH_OK', text.replace('SHIMMER_PUSH_OK shortcut', ''))
        self.assertNotIn('origin', text.replace('origin is never matched', ''))

    def installed_hook(self, gh='true'):
        LAST['url'] = str(self.fx.backup)
        hooks = Path(self.tmp.name) / 'hooks'
        hooks.mkdir(exist_ok=True)
        tree = tool_tree(self.tmp.name, ACTIVE['tool'])
        (hooks / 'pre-push').write_text('#!/bin/sh' + chr(10) + composed(str(self.fx.backup), self.tmp.name, tree),
                                        encoding='utf-8', newline=chr(10))
        (hooks / 'pre-push').chmod(0o755)
        sh(self.fx.main, 'config', 'core.hooksPath', str(hooks))
        return hook_env(self.tmp.name, gh)

    def test_a_real_git_push_goes_through_the_hook(self):
        env = self.installed_hook()
        done = subprocess.run(['git', 'push', 'backup-private', 'refs/heads/lane/clean:refs/heads/lane/clean'],
                              cwd=str(self.fx.main), env=env, capture_output=True, text=True, encoding='utf-8', creationflags=no_window())
        self.assertEqual(done.returncode, 0, brief(done, True))
        self.assertIn('refs/heads/lane/clean', sh(self.fx.main, 'ls-remote', str(self.fx.backup)))
        self.fx.branch('lane/leaky', 'cfg.txt', 'v = %s' % FAKE_KEY + chr(10))
        done = subprocess.run(['git', 'push', 'backup-private', 'refs/heads/lane/leaky:refs/heads/lane/leaky'],
                              cwd=str(self.fx.main), env=env, capture_output=True, text=True, encoding='utf-8', creationflags=no_window())
        self.assertNotEqual(done.returncode, 0)
        self.assertNotIn('lane/leaky', sh(self.fx.main, 'ls-remote', str(self.fx.backup)))

    def test_the_backup_run_itself_pushes_through_the_hook(self):
        env = self.installed_hook()
        with patch.dict(os.environ, {'PATH': env['PATH']}):
            record = bp.backup(self.fx.main, read=lambda url: ('true', 'private'), now=lambda: '2026-11-13T12:00:00Z')
        self.assertEqual(record['refused'], [], '; '.join('%s %s' % (r['ref'], '/'.join(r['reasons'])) for r in record['refused'])[:230])
        self.assertIn('refs/heads/lane/clean', record['pushed'])
        self.assertIn('refs/heads/lane/clean', sh(self.fx.main, 'ls-remote', str(self.fx.backup)))

    def test_the_backup_run_is_refused_by_the_hook_when_gh_reads_public(self):
        env = self.installed_hook(gh='false')
        with patch.dict(os.environ, {'PATH': env['PATH']}):
            record = bp.backup(self.fx.main, read=lambda url: ('true', 'private'), now=lambda: '2026-11-13T12:00:00Z')
        self.assertEqual(record['pushed'], [])
        self.assertEqual(sh(self.fx.main, 'ls-remote', str(self.fx.backup)), '')


def tool_edit(old, new):
    return ('tool', (old, new))


NEUTRALISED = [
    ('origin matched like the backup (condition always true)', 'hook', drop(NAME_AND_URL, 'if true; then'),
     ['test_the_name_origin_and_the_origin_url_fall_through_to_the_refusal']),
    ('the name not required (URL alone)', 'hook',
     drop(NAME_AND_URL, 'if [ "$2" = "$backup_url" ] || [ "$2" = "$backup_url.git" ]; then'),
     ['test_the_name_origin_and_the_origin_url_fall_through_to_the_refusal']),
    ('the URL not required (name alone)', 'hook', drop(NAME_AND_URL, 'if [ "$1" = "$backup_name" ]; then'),
     ['test_the_right_name_with_another_url_is_refused']),
    ('the URL matched by a glob', 'hook',
     drop(NAME_AND_URL, 'if [ "$1" = "$backup_name" ] && case "$2" in *seckinozbek1/project-shimmer-backup-private*) true ;; *) false ;; esac; then'),
     ['test_the_right_name_with_a_variant_of_the_real_url_is_refused']),
    ('the visibility check skipped', 'hook', drop(VISIBILITY, 'if false; then'),
     ['test_a_visibility_that_is_not_true_is_refused']),
    ('the visibility read by substring', 'hook', drop(VISIBILITY, 'if ! printf \'%s\' "$backup_vis" | grep -q true; then'),
     ['test_a_visibility_answer_with_spaces_or_missing_its_second_line_is_refused']),
    ('the scan skipped', 'hook', SCAN_IGNORED,
     ['test_a_planted_key_and_a_seals_path_are_refused', 'test_a_crashing_scan_is_refused']),
    ('the scan, the copy and the pins skipped', 'hook', both(SCAN_IGNORED, PINS_IGNORED, COPY_IGNORED),
     ['test_a_missing_scan_tool_is_refused']),
    ('the pins skipped', 'hook', PINS_IGNORED, ['test_a_changed_scan_file_is_refused']),
    ('the scan run in place, not from the isolated copy', 'hook', IN_PLACE,
     ['test_a_planted_module_beside_the_pinned_files_does_not_run', 'test_a_planted_pyc_and_a_planted_pythonpath_do_not_run']),
    ('python run with its site module (no -S)', 'hook', WITH_SITE, ['test_a_planted_site_pth_and_sitecustomize_do_not_run']),
    ('the temporary folder left behind', 'hook', NO_TRAP, ['test_the_temporary_folder_is_removed_on_every_exit']),
    ('a crashing scan tool, its outcome ignored', 'hook', SCAN_IGNORED, ['test_a_crashing_scan_is_refused']),
    ('a clean push refused', 'hook', drop('    exit 0\n  fi\n  echo "pre-push: refused, the backup-private scan', '    exit 1\n  fi\n  echo "pre-push: refused, the backup-private scan'),
     ['test_a_clean_push_to_the_right_name_and_url_passes']),
    ('annotated tag messages not scanned', *tool_edit('            where = tag_refusals(root, remote_ref, git, local_sha)', '            where = []'),
     ['test_an_annotated_tag_message_carrying_a_key_is_refused']),
    ('a tag object accepted for a branch', *tool_edit("                if kind.returncode != 0 or kind.stdout.strip() != 'commit':", '                if False:'),
     ['test_a_tag_object_pushed_to_a_branch_is_refused']),
    ('a delete let through', *tool_edit("                return 1, '%s: the hook never deletes a backup ref' % remote_ref", '                continue'),
     ['test_a_delete_only_push_is_refused']),
    ('replace refs not refused', *tool_edit("        why = replace_refusal(root, git)\n        if why:\n            return 1, why\n        tips = []", '        tips = []'),
     ['test_a_repository_with_a_replace_ref_is_refused']),
]
# The backup run's own push goes through the remote name: pushing to the bare URL meets the S13 refusal.
ATTRIBUTE = [
    ('push_args', lambda remote, sha, ref: ['push', '--no-follow-tags', LAST['url'], '%s:%s' % (sha, ref)],
     ['test_the_backup_run_itself_pushes_through_the_hook']),
]


# A neutralisation of the tests' own helper: with the shim only when no `py` is found, a decoy `py` runs the scan.
DECOY = ['test_a_decoy_py_command_on_the_path_does_not_decide_which_python_runs_the_scan']
OWN = [('SHIM_ALWAYS', False, DECOY),
       ('SHIM_USED', False, DECOY),
       ('SHIM_MODE', 0o644, ['test_the_py_shim_and_the_fake_gh_are_executable_for_sh',
                            'test_the_isolated_interpreter_starts_and_runs_the_scan_from_the_copy',
                            'test_a_clean_push_to_the_right_name_and_url_passes'])]
POSIX_ONLY = {'SHIM_MODE'}


def passes(*names, kind=None, change=None):
    ACTIVE['hook'] = change if kind == 'hook' else None
    ACTIVE['tool'] = change if kind == 'tool' else None
    try:
        suite = (unittest.TestSuite(HookChecks(n) for n in names) if names
                 else unittest.defaultTestLoader.loadTestsFromTestCase(HookChecks))
        with open(os.devnull, 'w') as sink:
            result = unittest.TextTestRunner(stream=sink, verbosity=0).run(suite)
        FAILED[:] = failure_lines(result)
        return result.wasSuccessful() and result.testsRun > 0
    finally:
        ACTIVE['hook'] = ACTIVE['tool'] = None


FAILED = []
LINES = []
SKIPPED = []


def check():
    if not passes():
        return 'FAIL', 'tools/loop/backup_hook_checks.py does not pass: ' + ' | '.join(FAILED)[:1500]
    proofs = []
    for label, kind, change, names in NEUTRALISED:
        failed = not passes(*names, kind=kind, change=change)
        restored = passes(*names)
        LINES.append('hook neutralised %-52s: failed=%s, restored and passed=%s' % (label, failed, restored))
        if not (failed and restored):
            return 'FAIL', 'hook neutralisation "%s": failed=%s, restored=%s' % (label, failed, restored)
        proofs.append(label)
    for attribute, mutant, names in ATTRIBUTE:
        with patch.object(bp, attribute, mutant):
            failed = not passes(*names)
        restored = passes(*names)
        LINES.append('hook neutralised %-52s: failed=%s, restored and passed=%s' % ('tool ' + attribute, failed, restored))
        if not (failed and restored):
            return 'FAIL', 'tool neutralisation %s: failed=%s, restored=%s' % (attribute, failed, restored)
        proofs.append('tool ' + attribute)
    for attribute, mutant, names in OWN:
        if attribute in POSIX_ONLY and os.name == 'nt':
            LINES.append('hook neutralised helper %s: not run here (Linux only)' % attribute)
            SKIPPED.append('helper ' + attribute)
            continue
        survivors = []
        with patch.object(sys.modules[__name__], attribute, mutant):
            for name in names:
                if passes(name):
                    survivors.append(name)
        restored = passes(*names)
        LINES.append('hook neutralised %-52s: each of %d test(s) failed=%s, restored and passed=%s'
                     % ('helper ' + attribute, len(names), not survivors, restored))
        if survivors or not restored:
            return 'FAIL', 'helper neutralisation %s: still passing %s, restored=%s' % (attribute, ','.join(survivors), restored)
        proofs.append('helper ' + attribute)
    return 'PASS', ('the pre-push exception passes only backup-private at its exact URL, visibility true and private, '
                    'the pinned scan code and a clean scan; neutralised, failed, restored, passed: ' + '; '.join(proofs)
                    + ('; NOT RUN on this OS (Linux only): ' + ', '.join(SKIPPED) if SKIPPED else ''))


if __name__ == '__main__':
    status, detail = check()
    print('\n'.join(LINES))
    print(status, detail)
    sys.exit(0 if status == 'PASS' else 1)
