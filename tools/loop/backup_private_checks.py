"""Fixture proofs for tools/loop/backup_private.py (D-612, gate check 386).

Real git on temporary repositories (a bare origin, a bare backup), the GitHub visibility read faked.
Every proof has a neutralisation that makes it fail; the check runs each, restores and requires a pass.
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import backup_private as bp  # noqa: E402
import register_backup_task as task  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloud_run_common import no_window  # noqa: E402  (D-079, HIDDEN-A)

ENV = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t',
           GIT_COMMITTER_EMAIL='t@t', GIT_CONFIG_NOSYSTEM='1')
PRIVATE = lambda url: ('true', 'private')  # noqa: E731
PUBLIC = lambda url: ('false', 'public')  # noqa: E731
FAKE_KEY = 'sk-' + 'ant-' + 'a1B2' * 8


def sh(cwd, *args):
    done = subprocess.run(['git', *args], cwd=str(cwd), env=ENV, capture_output=True, text=True, encoding='utf-8', creationflags=no_window())
    assert done.returncode == 0, (args, done.stderr)
    return done.stdout.strip()


def commit(root, name, data, message='c', binary=False):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if binary else data.encode())
    sh(root, 'add', name)
    sh(root, 'commit', '-q', '-m', message)


class Fixture:
    def __init__(self, tmp):
        self.tmp = Path(tmp)
        self.origin = self.tmp / 'origin.git'
        self.backup = self.tmp / 'backup.git'
        self.main = self.tmp / 'main'
        sh(self.tmp, 'init', '-q', '--bare', str(self.origin))
        sh(self.tmp, 'init', '-q', '--bare', str(self.backup))
        sh(self.tmp, 'init', '-q', '-b', 'main', str(self.main))
        commit(self.main, 'a.txt', 'hello\n')
        sh(self.main, 'remote', 'add', 'origin', str(self.origin))
        sh(self.main, 'push', '-q', 'origin', 'main')
        sh(self.main, 'fetch', '-q', 'origin')
        sh(self.main, 'branch', '-q', 'lane/good')
        sh(self.main, 'checkout', '-q', 'lane/good')
        commit(self.main, 'docs/b.txt', 'fine\n')
        sh(self.main, 'tag', 'v1')
        sh(self.main, 'checkout', '-q', 'main')
        bp.setup(self.main, str(self.backup), git=lambda r, *a: bp.run_git(r, *a))

    def branch(self, name, filename, data, binary=False):
        sh(self.main, 'checkout', '-q', '-b', name, 'main')
        commit(self.main, filename, data, binary=binary)
        sh(self.main, 'checkout', '-q', 'main')

    def held(self):
        return sh(self.main, 'ls-remote', str(self.backup))

    def log(self):
        path = self.main / bp.LOG
        return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []

    def run(self, **kw):
        kw.setdefault('read', PRIVATE)
        kw.setdefault('now', lambda: '2026-11-13T12:00:00Z')
        return bp.backup(self.main, **kw)


class BackupChecks(unittest.TestCase):
    def test_a_clean_run_pushes_branches_and_tags_and_logs_one_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            record = fx.run()
            self.assertEqual(record['refused'], [])
            self.assertIn('refs/heads/lane/good', record['pushed'])
            self.assertIn('refs/tags/v1', record['pushed'])
            self.assertIn('refs/tags/v1', fx.held())
            self.assertEqual(fx.run()['pushed'], [])

    def test_a_run_appends_one_log_line_with_time_and_visibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.run()
            lines = fx.log()
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]['time_utc'], '2026-11-13T12:00:00Z')
            self.assertEqual(lines[0]['visibility'], 'true/private')
            self.assertTrue(lines[0]['pushed'])

    def test_a_public_target_is_refused_and_nothing_is_pushed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            record = fx.run(read=PUBLIC)
            self.assertEqual(record['pushed'], [])
            self.assertTrue(record['refused'])
            self.assertEqual(fx.held(), '')

    def test_an_api_error_is_refused_and_nothing_is_pushed(self):
        def broken(url):
            raise RuntimeError('boom')
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            record = fx.run(read=broken)
            self.assertEqual(record['pushed'], [])
            self.assertEqual(fx.held(), '')
            self.assertEqual(record['visibility'], 'not read')

    def test_the_name_origin_and_the_origin_url_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            self.assertEqual(fx.run(remote='origin')['pushed'], [])
            sh(fx.main, 'remote', 'add', 'copycat', str(fx.origin))
            self.assertEqual(fx.run(remote='copycat')['pushed'], [])
            self.assertEqual(fx.held(), '')
            self.assertEqual(sh(fx.main, 'ls-remote', str(fx.origin)).count('refs/tags'), 0)
            with self.assertRaises(bp.BackupError):
                bp.setup(fx.main, str(fx.origin), remote='another')
            with self.assertRaises(bp.BackupError):
                bp.setup(fx.main, 'x', remote='origin')
            with self.assertRaises(bp.BackupError):
                bp.setup(fx.main, 'https://github.com/someone/project-shimmer-deployment.git', remote='third')
            with self.assertRaises(bp.BackupError):
                bp.setup(fx.main, str(fx.backup))

    def test_a_planted_key_refuses_that_ref_by_file_and_line_never_by_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.branch('lane/leaky', 'cfg/x.txt', 'line one\nvalue = %s\n' % FAKE_KEY)
            record = fx.run()
            refused = {r['ref']: r['reasons'] for r in record['refused']}
            self.assertIn('refs/heads/lane/leaky', refused)
            self.assertTrue(any('cfg/x.txt:2' in r for r in refused['refs/heads/lane/leaky']))
            self.assertNotIn(FAKE_KEY, json.dumps(record))
            self.assertNotIn(FAKE_KEY, (fx.main / bp.LOG).read_text())
            self.assertNotIn('refs/heads/lane/leaky', fx.held())
            self.assertIn('refs/heads/lane/good', fx.held())

    def test_a_large_blob_and_run_data_paths_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.branch('lane/big', 'data/blob.bin', os.urandom(5000), binary=True)
            fx.branch('lane/out', 'output/runs/r.txt', 'x\n')
            fx.branch('lane/replies', 'x/audit/model_replies/r.json', '{}\n')
            with patch.object(bp, 'MAX_BLOB_BYTES', 1000):
                record = fx.run()
            refused = {r['ref'] for r in record['refused']}
            self.assertEqual(refused, {'refs/heads/lane/big', 'refs/heads/lane/out', 'refs/heads/lane/replies'})
            self.assertNotIn('lane/big', fx.held())

    def test_an_archive_with_a_refused_member_is_refused(self):
        import tarfile
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode='w:gz') as tar:
                info = tarfile.TarInfo('run/audit/model_replies/r.json')
                info.size = 2
                tar.addfile(info, io.BytesIO(b'{}'))
            fx.branch('lane/arch', 'docs/pack.tar.gz', buf.getvalue(), binary=True)
            record = fx.run()
            self.assertIn('refs/heads/lane/arch', {r['ref'] for r in record['refused']})

    def test_no_push_carries_force_or_mirror_and_each_ref_goes_alone(self):
        seen = []

        def recorder(root, *args, **kw):
            if args and args[0] == 'push':
                seen.append(list(args))
            return bp.run_git(root, *args, **kw)
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            url = sh(fx.main, 'remote', 'get-url', bp.REMOTE)
            shas = bp.refs(fx.main)
            fx.run(git=recorder)
        self.assertEqual(len(seen), 3)
        for argv in seen:
            self.assertEqual(len(argv), 4)
            self.assertEqual(argv[:2], ['push', '--no-follow-tags'])
            self.assertEqual(argv[2], bp.REMOTE)
            self.assertNotIn('--force', argv)
            self.assertNotIn('--mirror', argv)
            self.assertFalse(argv[3].startswith('+'))
            sha, ref = argv[3].split(':')
            self.assertEqual(sha, shas[ref])

    def test_a_dry_run_pushes_nothing_and_still_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            record = fx.run(dry_run=True)
            self.assertTrue(record['pushed'])
            self.assertEqual(fx.held(), '')
            self.assertTrue(fx.log()[0]['dry_run'])

    def test_the_task_is_daily_in_the_operators_session_and_dry_run_registers_nothing(self):
        xml = task.task_xml('PC\\user', Path('pythonw.exe'), Path('s.py'), Path('r'))
        for part in ('<ScheduleByDay>', '<DaysInterval>1</DaysInterval>', 'InteractiveToken', 'LeastPrivilege'):
            self.assertIn(part, xml)
        calls = []
        with patch.object(task.subprocess, 'run', lambda *a, **k: calls.append(a)), \
                patch.object(task.hook, 'windowless_python', lambda: Path('pythonw.exe')), \
                patch.object(task.session_end_salvage, 'main_root', lambda: Path('r')), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(task.main(['--dry-run']), 0)
        self.assertEqual(calls, [])
        self.assertIn('<CalendarTrigger>', out.getvalue())

    def test_several_urls_or_a_fetch_push_mismatch_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            other = Path(tmp) / 'other.git'
            sh(fx.tmp, 'init', '-q', '--bare', str(other))
            sh(fx.main, 'remote', 'set-url', '--add', '--push', bp.REMOTE, str(other))
            self.assertEqual(fx.run()['pushed'], [])
            sh(fx.main, 'config', '--unset-all', 'remote.%s.pushurl' % bp.REMOTE)
            sh(fx.main, 'remote', 'set-url', '--add', bp.REMOTE, str(other))
            self.assertEqual(fx.run()['pushed'], [])
            self.assertEqual(fx.held(), '')
            self.assertEqual(sh(fx.main, 'ls-remote', str(other)), '')

    def test_a_url_changed_while_the_visibility_is_read_refuses_the_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            other = Path(tmp) / 'other.git'
            sh(fx.tmp, 'init', '-q', '--bare', str(other))

            def swapping(url):
                sh(fx.main, 'remote', 'set-url', bp.REMOTE, str(other))
                return ('true', 'private')
            record = fx.run(read=swapping)
            self.assertEqual(record['pushed'], [])
            self.assertEqual(fx.held(), '')
            self.assertEqual(sh(fx.main, 'ls-remote', str(other)), '')

    def test_keys_in_binary_files_commit_messages_and_tag_messages_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.branch('lane/bin', 'data/x.dat', b'\x00\x01\x02\nkey = %s\n' % FAKE_KEY.encode(), binary=True)
            sh(fx.main, 'checkout', '-q', '-b', 'lane/msg', 'main')
            commit(fx.main, 'ok.txt', 'fine\n', message='note %s' % FAKE_KEY)
            sh(fx.main, 'checkout', '-q', 'main')
            sh(fx.main, 'tag', '-a', 'vkey', '-m', 'tag note %s' % FAKE_KEY)
            record = fx.run()
            refused = {r['ref']: ' '.join(r['reasons']) for r in record['refused']}
            self.assertIn('data/x.dat:2', refused['refs/heads/lane/bin'])
            self.assertIn('message line', refused['refs/heads/lane/msg'])
            self.assertIn('tag message line', refused['refs/tags/vkey'])
            self.assertNotIn(FAKE_KEY, json.dumps(record))
            self.assertNotIn('lane/msg', fx.held())

    def test_a_key_in_a_non_ascii_path_is_reported_by_that_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.branch('lane/uni', 'dir/\u00fcr\u00fcn.txt', 'key = %s\n' % FAKE_KEY)
            refused = {r['ref']: ' '.join(r['reasons']) for r in fx.run()['refused']}
            self.assertIn('dir/\u00fcr\u00fcn.txt:1', refused['refs/heads/lane/uni'])

    def test_a_diff_is_read_by_hunk_lengths_and_an_unreadable_path_fails_closed(self):
        hunk = ['diff --git a/f b/f', '--- /dev/null', '+++ b/f', '@@ -0,0 +1,2 @@', '++++ b/other', '+x = %s' % FAKE_KEY]
        self.assertEqual(bp.scan_diff(hunk)[0][1].split(' ')[0], 'f:2')
        found = bp.scan_diff(['diff --git a/f b/f', '--- /dev/null', '+++ "b/x\ty"', '@@ -0,0 +1 @@', '+x'])
        self.assertTrue(any('cannot be read' in text for _, text in found))

    def test_a_failed_object_listing_raises_and_refuses_the_ref(self):
        class Failed:
            returncode, stdout = 1, ''
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.branch('lane/new', 'n.txt', 'new\n')
            with patch.object(bp, 'run_input', lambda *a, **k: Failed()):
                with self.assertRaises(bp.BackupError):
                    bp.range_objects(fx.main, 'refs/heads/lane/new', [])
                record = fx.run()
            self.assertIn('refs/heads/lane/new', {r['ref'] for r in record['refused']})
            self.assertNotIn('lane/new', fx.held())

    def test_a_file_moved_into_run_data_is_refused_though_its_blob_is_known(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            sh(fx.main, 'checkout', '-q', '-b', 'lane/moved', 'main')
            (fx.main / 'seals').mkdir()
            sh(fx.main, 'mv', 'a.txt', 'seals/a.txt')
            sh(fx.main, 'commit', '-q', '-m', 'move')
            sh(fx.main, 'checkout', '-q', 'main')
            record = fx.run()
            self.assertIn('refs/heads/lane/moved', {r['ref'] for r in record['refused']})
            self.assertNotIn('lane/moved', fx.held())

    def test_only_github_hosts_anchored_at_the_start_are_read(self):
        for url in ('https://gitlab.com/github.com/o/r', 'https://evil.example/x/github.com/o/r',
                    'http://github.com/o/r', 'git@evil.example:github.com/o/r'):
            self.assertIsNone(bp.parse_repo(url), url)
        for url in ('https://github.com/o/r.git', 'git@github.com:o/r.git', 'ssh://git@github.com/o/r'):
            self.assertEqual(bp.parse_repo(url), ('o', 'r'), url)

    def test_a_tag_on_a_tree_and_a_tag_of_a_tag_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            sh(fx.main, 'tag', 'lwtree', 'main^{tree}')
            sh(fx.main, 'tag', '-a', 'inner', '-m', 'x', 'main')
            sh(fx.main, 'tag', '-a', 'outer', '-m', 'y', 'inner')
            record = fx.run()
            refused = {r['ref'] for r in record['refused']}
            self.assertEqual(refused, {'refs/tags/lwtree', 'refs/tags/outer'})
            held = fx.held()
            self.assertNotIn('lwtree', held)
            self.assertNotIn('refs/tags/outer', held)
            self.assertIn('refs/tags/inner', held)

    def test_a_url_rewrite_configuration_refuses_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            other = Path(tmp) / 'elsewhere.git'
            sh(fx.tmp, 'init', '-q', '--bare', str(other))
            sh(fx.main, 'config', 'url.%s.insteadOf' % other.as_posix(), str(fx.backup))
            record = fx.run()
            self.assertEqual(record['pushed'], [])
            self.assertEqual(sh(other, 'for-each-ref'), '')
            self.assertEqual(sh(fx.backup, 'for-each-ref'), '')


    def test_the_object_id_that_was_scanned_is_what_is_pushed_when_a_ref_moves(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            old = sh(fx.main, 'rev-parse', 'refs/heads/lane/good')
            moved = []

            def moving(url):
                if not moved:
                    moved.append(1)
                    sh(fx.main, 'checkout', '-q', 'lane/good')
                    commit(fx.main, 'late.txt', 'key = %s\n' % FAKE_KEY)
                    sh(fx.main, 'checkout', '-q', 'main')
                return ('true', 'private')
            fx.run(read=moving)
            new = sh(fx.main, 'rev-parse', 'refs/heads/lane/good')
            self.assertNotEqual(old, new)
            held = dict(line.split('\t')[::-1] for line in fx.held().splitlines())
            self.assertIn(held.get('refs/heads/lane/good', old), (old,))
            self.assertNotIn(new, fx.held())

    def test_the_visibility_call_names_github_com(self):
        calls = []

        class Done:
            returncode, stdout = 0, 'true\nprivate\n'

        def runner(argv, **kw):
            calls.append(argv)
            return Done()
        self.assertEqual(bp.gh_visibility('https://github.com/o/r.git', runner), ('true', 'private'))
        argv = calls[0]
        self.assertEqual(argv[argv.index('--hostname') + 1], 'github.com')
        self.assertEqual(argv[:2], ['gh', 'api'])

    def test_a_commit_shared_by_a_refused_ref_refuses_every_ref_holding_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.branch('lane/a_leaky', 'cfg.txt', 'v = %s' % FAKE_KEY + chr(10))
            sh(fx.main, 'checkout', '-q', '-b', 'lane/b_child', 'lane/a_leaky')
            commit(fx.main, 'more.txt', 'fine' + chr(10))
            sh(fx.main, 'checkout', '-q', 'main')
            fx.branch('lane/c_clean', 'c.txt', 'fine' + chr(10))
            record = fx.run()
            self.assertEqual({r['ref'] for r in record['refused']}, {'refs/heads/lane/a_leaky', 'refs/heads/lane/b_child'})
            self.assertIn('refs/heads/lane/c_clean', record['pushed'])
            self.assertNotIn('b_child', fx.held())

    def test_a_key_in_a_commit_unique_to_the_second_ref_is_still_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.branch('lane/a_first', 'a.txt.new', 'fine' + chr(10))
            sh(fx.main, 'checkout', '-q', '-b', 'lane/b_second', 'lane/a_first')
            commit(fx.main, 'cfg.txt', 'v = %s' % FAKE_KEY + chr(10))
            sh(fx.main, 'checkout', '-q', 'main')
            record = fx.run()
            self.assertEqual({r['ref'] for r in record['refused']}, {'refs/heads/lane/b_second'})
            self.assertIn('refs/heads/lane/a_first', record['pushed'])
            self.assertNotIn('b_second', fx.held())

    def test_every_pattern_of_the_quick_scan_is_read(self):
        lines = {
            'Anthropic key prefix': 'sk-' + 'ant-' + 'A' * 16,
            'OpenAI project key prefix': 'sk-' + 'proj-' + 'A' * 16,
            'OpenAI-style key of 20 characters': 'sk-' + 'A' * 20,
            'AKIA key': 'AK' + 'IA' + 'B' * 16,
            'AIza key': 'AI' + 'za' + 'c' * 35,
            'api_key assignment': 'api_key = "' + 'Ab1_' * 5 + '"',
            'secret assignment': "SECRET = '" + 'Ab1_' * 5 + "'",
        }
        for rule, line in lines.items():
            self.assertIn(rule, bp.line_hits(line), rule)
        self.assertEqual(bp.line_hits('api_key = "short"'), [])

    def allow_fixture(self, tmp, public=False, reason='test fixture'):
        fx = Fixture(tmp)
        line = 'api_key = "' + 'Ab1_' * 5 + '"' + chr(10)
        fx.branch('lane/k', 'cfg/x.txt', line)
        blob = sh(fx.main, 'rev-parse', 'lane/k:cfg/x.txt')
        entry = {'path': 'cfg/x.txt', 'blob': blob, 'rule': 'api_key assignment', 'reason': reason, 'public': public}
        allow = Path(tmp) / 'allow.json'
        allow.write_text(json.dumps([entry]))
        return fx, allow, entry

    def test_a_real_shaped_api_key_in_a_new_blob_is_refused_and_an_allowlisted_blob_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, allow, _ = self.allow_fixture(tmp)
            with patch.object(bp, 'ALLOWLIST', Path(tmp) / 'none.json'):
                self.assertIn('refs/heads/lane/k', {r['ref'] for r in fx.run()['refused']})
            with patch.object(bp, 'ALLOWLIST', allow):
                record = fx.run()
                self.assertIn('refs/heads/lane/k', record['pushed'])
                self.assertEqual(record['allowlisted_hits'], 1)
                fx.branch('lane/k2', 'cfg/x.txt', 'api_key = "' + 'Zz9_' * 5 + '"' + chr(10))
                self.assertIn('refs/heads/lane/k2', {r['ref'] for r in fx.run()['refused']})

    def test_an_entry_marked_public_applies_only_when_its_blob_is_in_origin_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, allow, _ = self.allow_fixture(tmp, public=True)
            with patch.object(bp, 'ALLOWLIST', allow):
                self.assertIn('refs/heads/lane/k', {r['ref'] for r in fx.run()['refused']})
            sh(fx.main, 'checkout', '-q', '-b', 'public_twin', 'main')
            commit(fx.main, 'cfg/x.txt', 'api_key = "' + 'Ab1_' * 5 + '"' + chr(10))
            sh(fx.main, 'update-ref', 'refs/remotes/origin/main', 'public_twin')
            sh(fx.main, 'checkout', '-q', 'main')
            sh(fx.main, 'branch', '-q', '-D', 'public_twin')
            with patch.object(bp, 'ALLOWLIST', allow):
                self.assertIn('refs/heads/lane/k', fx.run()['pushed'])

    def test_a_bare_prefix_is_prose_and_a_prefix_followed_by_a_key_run_is_refused(self):
        for prefix in ('sk-' + 'ant-', 'sk-' + 'proj-'):
            self.assertEqual(bp.line_hits('scan for `' + prefix + '`, then stop', True), [])
            self.assertTrue(bp.line_hits('scan for `' + prefix + '`, then stop'))
            self.assertEqual(bp.line_hits(prefix + 'A' * 15, True), [])
            self.assertTrue(bp.line_hits(prefix + 'A' * 16))
            self.assertTrue(bp.line_hits('see `' + prefix + '` and later ' + prefix + 'B' * 20, True))
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.branch('lane/prose', 'notes.md', 'scan for `' + 'sk-' + 'ant-' + '` prefixes' + chr(10))
            fx.branch('lane/run', 'notes.md', 'v ' + 'sk-' + 'ant-' + 'C' * 20 + chr(10))
            record = fx.run()
            self.assertIn('refs/heads/lane/prose', record['pushed'])
            self.assertIn('refs/heads/lane/run', {r['ref'] for r in record['refused']})

    def test_a_bare_prefix_in_a_code_file_is_refused_and_only_prose_paths_are_read_as_prose(self):
        for path in ('a.md', 'b.TXT', 'c.log', 'docs/x/y.py'):
            self.assertTrue(bp.is_prose_path(path), path)
        for path in ('x.py', 'tools/a.json', 'scripts/docs.py', 'mydocs/a.py'):
            self.assertFalse(bp.is_prose_path(path), path)
        code_line = "X = '" + 'sk-' + "ant-' + '" + 'A' * 20 + "'" + chr(10)
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.branch('lane/code', 'src/x.py', code_line)
            record = fx.run()
            self.assertIn('refs/heads/lane/code', {r['ref'] for r in record['refused']})

    def test_lowercase_key_prefixes_are_read(self):
        self.assertIn('AKIA key', bp.line_hits('akia' + 'b' * 16))
        self.assertIn('AIza key', bp.line_hits('aiza' + 'c' * 35))

    def check_entries(self, root, entries):
        for path, blob, rule, _ in entries:
            data = subprocess.run(['git', 'cat-file', 'blob', blob], cwd=str(root), capture_output=True, creationflags=no_window())
            self.assertEqual(data.returncode, 0, path)
            listed = subprocess.run(['git', 'log', '--all', '--format=', '--raw', '--no-abbrev', '--', path],
                                    cwd=str(root), capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=no_window())
            self.assertIn(blob, listed.stdout, path)
            lines = data.stdout.decode('utf-8', errors='replace').splitlines()
            self.assertTrue(any(rule in bp.line_hits(line, bp.is_prose_path(path)) for line in lines), path)

    def test_each_allowlist_entry_names_a_blob_that_sits_at_its_path_and_gives_its_rule(self):
        root = HERE.parents[1]
        entries = bp.load_allowlist()
        count = subprocess.run(['git', 'rev-list', '--count', '--all'], cwd=str(root), capture_output=True, text=True, creationflags=no_window())
        if count.returncode != 0 or int(count.stdout.strip() or 0) < 50:
            self.skipTest('this checkout has too little history to hold the allowlisted blobs, so their paths cannot be read')
        self.check_entries(root, entries)

    def test_an_allowlist_file_is_read_back_whole_and_its_blob_is_proved_in_a_temporary_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.branch('lane/k', 'cfg/x.txt', 'api_key = "' + 'Ab1_' * 5 + '"' + chr(10))
            blob = sh(fx.main, 'rev-parse', 'lane/k:cfg/x.txt')
            allow = Path(tmp) / 'allow.json'
            allow.write_text(json.dumps([{'path': 'cfg/x.txt', 'blob': blob, 'rule': 'api_key assignment',
                                          'reason': 'test fixture', 'public': False}]))
            entries = bp.load_allowlist(allow)
            self.assertEqual(entries, [('cfg/x.txt', blob, 'api_key assignment', False)])
            self.check_entries(fx.main, entries)

    def test_the_committed_allowlist_is_usable_and_has_a_reason_for_each_entry(self):
        entries = bp.load_allowlist()
        self.assertTrue(entries)
        for path, blob, rule, public in entries:
            self.assertIn(rule, [name for name, _ in bp.PATTERNS])
            self.assertEqual(len(blob), 40)

    def test_the_public_main_is_a_base_only_when_it_still_equals_the_local_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            local = sh(fx.main, 'rev-parse', 'refs/remotes/origin/main')
            self.assertEqual(bp.origin_main_base(fx.main), local)
            self.assertEqual(bp.negatives(fx.main, {}), [local])
            sh(fx.main, 'update-ref', 'refs/remotes/origin/main', sh(fx.main, 'rev-parse', 'lane/good'))
            self.assertIsNone(bp.origin_main_base(fx.main))
            self.assertEqual(bp.negatives(fx.main, {}), [])
            sh(fx.main, 'update-ref', 'refs/remotes/origin/main', local)
            sh(fx.main, 'remote', 'set-url', 'origin', str(Path(tmp) / 'nowhere.git'))
            self.assertIsNone(bp.origin_main_base(fx.main))

    def test_every_git_call_ignores_replace_objects_and_replace_refs_refuse_the_run(self):
        self.assertEqual(bp.scan_env()['GIT_NO_REPLACE_OBJECTS'], '1')
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            sh(fx.main, 'replace', '-f', sh(fx.main, 'rev-parse', 'lane/good'), sh(fx.main, 'rev-parse', 'main'))
            record = fx.run()
            self.assertEqual(record['pushed'], [])
            self.assertEqual(fx.held(), '')

    def test_an_allowlist_entry_without_a_reason_is_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, allow, _ = self.allow_fixture(tmp, reason=' ')
            with self.assertRaises(bp.BackupError):
                bp.load_allowlist(allow)
            with patch.object(bp, 'ALLOWLIST', allow):
                record = fx.run()
            self.assertEqual(record['pushed'], [])

_REAL_REF_REFUSALS = bp.ref_refusals
_REAL_LOAD = bp.load_allowlist
_SEEN = []


def _skip_by_ref_name(root, ref, *args, **kwargs):
    """A skip keyed by ref name: once a ref has been scanned, every later ref is taken as scanned."""
    if ref == 'refs/heads/main':
        _SEEN.clear()
    if _SEEN:
        return []
    _SEEN.append(ref)
    return _REAL_REF_REFUSALS(root, ref, *args, **kwargs)


class _AnyBlob(set):
    def __contains__(self, key):
        return (key[0], key[2]) in {(p, r) for p, _, r in self}


NEUTRALISED = [
    ('origin_main_base', lambda root, git=bp.run_git: (bp.run_git(root, 'rev-parse', '--verify', '-q', 'refs/remotes/origin/main').stdout.strip() or None),
     ['test_the_public_main_is_a_base_only_when_it_still_equals_the_local_copy']),
    ('scan_env', lambda: dict(os.environ), ['test_every_git_call_ignores_replace_objects_and_replace_refs_refuse_the_run']),
    ('replace_refusal', lambda root, git=bp.run_git: None, ['test_every_git_call_ignores_replace_objects_and_replace_refs_refuse_the_run']),
    ('is_prose_path', lambda path: True, ['test_a_bare_prefix_in_a_code_file_is_refused_and_only_prose_paths_are_read_as_prose']),
    ('PATTERNS', tuple((n, re.compile(p.pattern)) for n, p in bp.PATTERNS), ['test_lowercase_key_prefixes_are_read']),
    ('load_allowlist', lambda path=None: _REAL_LOAD(path) + [('tools/nowhere.py', '0' * 40, 'Anthropic key prefix', False)],
     ['test_each_allowlist_entry_names_a_blob_that_sits_at_its_path_and_gives_its_rule',
      'test_an_allowlist_file_is_read_back_whole_and_its_blob_is_proved_in_a_temporary_repository']),
    ('bare_prefix', lambda line, rule: False, ['test_a_bare_prefix_is_prose_and_a_prefix_followed_by_a_key_run_is_refused']),
    ('bare_prefix', lambda line, rule: True, ['test_a_bare_prefix_is_prose_and_a_prefix_followed_by_a_key_run_is_refused']),
    ('ref_refusals', _skip_by_ref_name, ['test_a_key_in_a_commit_unique_to_the_second_ref_is_still_refused']),
    ('PATTERNS', bp.PATTERNS[:-1], ['test_every_pattern_of_the_quick_scan_is_read']),
    ('usable_allowlist', lambda root, entries: _AnyBlob({(p, b, r) for p, b, r, _ in entries}),
     ['test_a_real_shaped_api_key_in_a_new_blob_is_refused_and_an_allowlisted_blob_is_not']),
    ('usable_allowlist', lambda root, entries: {(p, b, r) for p, b, r, _ in entries},
     ['test_an_entry_marked_public_applies_only_when_its_blob_is_in_origin_main']),
    ('load_allowlist', lambda path=None: [(i['path'], i['blob'], i['rule'], bool(i.get('public')))
                                          for i in json.loads(Path(path or bp.ALLOWLIST).read_text())],
     ['test_an_allowlist_entry_without_a_reason_is_unusable']),
    ('visibility_refusal', lambda read, url: (None, 'true/private'),
     ['test_a_public_target_is_refused_and_nothing_is_pushed',
      'test_an_api_error_is_refused_and_nothing_is_pushed']),
    ('remote_refusal', lambda name, url, origins: None,
     ['test_the_name_origin_and_the_origin_url_are_refused']),
    ('secret_refusals', lambda root, ref, base: [],
     ['test_a_planted_key_refuses_that_ref_by_file_and_line_never_by_value']),
    ('blob_refusal', lambda size, path: None, ['test_a_large_blob_and_run_data_paths_are_refused']),
    ('path_refusal', lambda path: None, ['test_a_large_blob_and_run_data_paths_are_refused']),
    ('archive_refusal', lambda root, sha, path, size: None,
     ['test_an_archive_with_a_refused_member_is_refused']),
    ('push_args', lambda url, sha, ref: ['push', '--force', '--no-follow-tags', url, '%s:%s' % (sha, ref)],
     ['test_no_push_carries_force_or_mirror_and_each_ref_goes_alone']),
    ('push_args', lambda url, sha, ref: ['push', url, '%s:%s' % (sha, ref)],
     ['test_no_push_carries_force_or_mirror_and_each_ref_goes_alone']),
    ('push_args', lambda url, sha, ref: ['push', '--no-follow-tags', url, '%s:%s' % (ref, ref)],
     ['test_the_object_id_that_was_scanned_is_what_is_pushed_when_a_ref_moves',
      'test_no_push_carries_force_or_mirror_and_each_ref_goes_alone']),
    ('commits_in', lambda root, rev, base: set(),
     ['test_a_commit_shared_by_a_refused_ref_refuses_every_ref_holding_it']),
    ('gh_args', lambda owner, repo: ['gh', 'api', 'repos/%s/%s' % (owner, repo), '--jq', '.private,.visibility'],
     ['test_the_visibility_call_names_github_com']),
    ('url_refusal', lambda root, name, git=bp.run_git: (bp.remote_urls(root, name, git)[0][0], None),
     ['test_several_urls_or_a_fetch_push_mismatch_are_refused']),
    ('url_stable', lambda root, name, url, git=bp.run_git: True,
     ['test_a_url_changed_while_the_visibility_is_read_refuses_the_push']),
    ('LOG_FLAGS', ['-c', 'core.quotePath=false', 'log', '-p', '--no-renames', '--no-color', '--no-ext-diff',
                   '--no-textconv', '--format=%x01%H', '-m', '--stdin'],
     ['test_keys_in_binary_files_commit_messages_and_tag_messages_refuse']),
    ('LOG_FLAGS', ['-c', 'core.quotePath=true', 'log', '-p', '--text', '--no-renames', '--no-color', '--no-ext-diff',
                   '--no-textconv', '--format=%x01%H', '-m', '--stdin'],
     ['test_a_key_in_a_non_ascii_path_is_reported_by_that_path']),
    ('parse_repo', lambda url: (('o', 'r') if 'github.com' in (url or '') else None),
     ['test_only_github_hosts_anchored_at_the_start_are_read']),
    ('kind_refusal', lambda *a, **k: None,
     ['test_a_tag_on_a_tree_and_a_tag_of_a_tag_are_refused']),
    ('rewrite_refusal', lambda root, git=bp.run_git: None,
     ['test_a_url_rewrite_configuration_refuses_the_run']),
    ('message_refusals', lambda root, ref, base: [],
     ['test_keys_in_binary_files_commit_messages_and_tag_messages_refuse']),
    ('tag_refusals', lambda *a, **k: [],
     ['test_keys_in_binary_files_commit_messages_and_tag_messages_refuse']),
    ('header_path', lambda text: None if text == '+++ /dev/null' else text[6:].strip('"'),
     ['test_a_diff_is_read_by_hunk_lengths_and_an_unreadable_path_fails_closed']),
    ('parse_batch', lambda done, count: [],
     ['test_a_failed_object_listing_raises_and_refuses_the_ref']),
    ('changed_paths', lambda entries: [],
     ['test_a_file_moved_into_run_data_is_refused_though_its_blob_is_known']),
    ('append_log', lambda root, record: None,
     ['test_a_run_appends_one_log_line_with_time_and_visibility']),
]


def passes(*names):
    suite = (unittest.TestSuite(BackupChecks(n) for n in names) if names
             else unittest.defaultTestLoader.loadTestsFromTestCase(BackupChecks))
    with open(os.devnull, 'w') as sink:
        result = unittest.TextTestRunner(stream=sink, verbosity=0).run(suite)
    FAILED[:] = failure_lines(result)
    return result.wasSuccessful() and result.testsRun > 0


FAILED = []


def failure_lines(result):
    """One short line for each test that failed or errored: its name and the last line of its traceback."""
    lines = []
    for test, trace in list(result.failures) + list(result.errors):
        last = [line for line in trace.strip().splitlines() if line.strip()][-1] if trace.strip() else ''
        lines.append('%s: %s' % (test.id().rsplit('.', 1)[-1], last[:200]))
    return lines


LINES = []


def check():
    if not passes():
        return 'FAIL', 'tools/loop/backup_private_checks.py does not pass: ' + ' | '.join(FAILED)[:1500]
    proofs = []
    for attribute, mutant, names in NEUTRALISED:
        with patch.object(bp, attribute, mutant):
            failed = not passes(*names)
        restored = passes(*names)
        LINES.append('neutralised %-18s tests=%d: failed=%s, restored and passed=%s' % (attribute, len(names), failed, restored))
        if not (failed and restored):
            return 'FAIL', 'backup_private.%s neutralised: failed=%s, restored=%s' % (attribute, failed, restored)
        proofs.append(attribute)
    import backup_hook_checks
    hook_status, hook_detail = backup_hook_checks.check()
    LINES.extend(backup_hook_checks.LINES)
    if hook_status != 'PASS':
        return hook_status, hook_detail
    note = ('; not run on this OS (Linux only): ' + ', '.join(backup_hook_checks.SKIPPED)) if backup_hook_checks.SKIPPED else ''
    proofs.append('the pre-push exception of D-616 (%d neutralisations%s)' % (len(backup_hook_checks.NEUTRALISED), note))
    return 'PASS', ('the private backup refuses a public or unreadable target, origin by name and URL, a planted key, '
                    'a large blob, run data and archives with refused members, never forces and logs each run; '
                    'neutralised, failed, restored, passed: ' + ', '.join(proofs))


if __name__ == '__main__':
    status, detail = check()
    print('\n'.join(LINES))
    print(status, detail)
    sys.exit(0 if status == 'PASS' else 1)
