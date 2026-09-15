"""Fail-closed, stdlib-only access boundary for the V3 blind phase.

Install before invoking review code. Audit hooks are process-wide and irreversible;
use a fresh process per phase. This boundary is not a sandbox for hostile Python.
"""
from __future__ import annotations

import hashlib
import builtins
import io
import importlib.machinery
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import sysconfig
import threading
from datetime import datetime, timezone

POLICY_ID = 'producer-semantic-policy-v3'
RELEASE_ID = 'producer-coverage-amendment-v3'
PRE_GOLD = 'PRE_GOLD'
POST_GOLD_ONLY = 'POST_GOLD_ONLY'
DENIED = 'DENIED'


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Guard:
    def __init__(self, workspace=None, base=None, git_reader=None):
        self.workspace = Path(workspace or Path(__file__).resolve().parents[2]).resolve()
        self.base = Path(base or self.workspace / 'benchmark/producer_coverage_amendment_v3').resolve()
        if not self.base.is_relative_to(self.workspace):
            raise ValueError('V3 base must be inside workspace')
        self.output = self.workspace / 'output/producer_coverage_amendment_v3'
        self.manifest = self.base / 'blind_evidence/PRE_GOLD_FREEZE.json'
        self.active = self.base / 'ACTIVE_RELEASE.json'
        self.marker = self.base / 'blind_evidence/POST_GOLD_PHASE.json'
        self.git_reader = git_reader
        self.installed = False
        self.authorized = False
        self.commit = None
        self._local = threading.local()
        self._git_running = False
        self.runtime = {Path(sysconfig.get_path(k)).resolve() for k in ('stdlib', 'platstdlib')}
        self.log = {'policy_id': POLICY_ID, 'release_id': RELEASE_ID,
                    'pid': os.getpid(), 'successful_target_reads': [],
                    'authorized_target_open_attempts': [],
                    'blocked_target_reads': [], 'first_actual_target_read_at': None}
        self.log_path = self.output / 'access_logs' / ('access-%s-%s.json' % (os.getpid(), __import__('time').time_ns()))

    def classify(self, path):
        if isinstance(path, int):
            return DENIED
        try:
            p = Path(os.fsdecode(path)).resolve()
        except (TypeError, ValueError, OSError):
            return DENIED
        if p.is_relative_to(self.workspace):
            rel = p.relative_to(self.workspace)
            parts = tuple(x.lower() for x in rel.parts)
            if any('post_freeze' in x or 'post_gold' in x for x in parts) and p != self.marker:
                return POST_GOLD_ONLY
            if p.is_relative_to(self.output / 'test_fixtures'):
                return POST_GOLD_ONLY if any('target' in x.lower() for x in p.parts) else PRE_GOLD
            if p in (self.active, self.manifest, self.marker):
                return PRE_GOLD
            if p.parent == self.base and p.name in {
                'policy.md', 'schema.json', 'population.json', 'reviewer_instructions.md',
                'PRE_GOLD_ACCESS_AUDIT.json', '.gitattributes', 'pre_validation.json',
                'PRE_REVIEW_METHOD_FREEZE.json', 'test_phase_manifest.json',
            }:
                return PRE_GOLD
            if any(p.is_relative_to(self.base / x) for x in ('method', 'inputs', 'blind_evidence')):
                return PRE_GOLD
            if p.is_relative_to(self.output):
                return PRE_GOLD
            metadata = self.workspace / 'benchmark/task_semantics_v2'
            if p in (metadata / 'family_manifest.json', metadata / 'review_admin_mapping.json'):
                return PRE_GOLD
            if p.parent == metadata / 'review_packets' and p.suffix == '.json':
                return PRE_GOLD
            if p in (self.workspace / 'config/agent_contracts.json', self.workspace / 'config/agent_registry.json'):
                return PRE_GOLD
            if p.suffix.lower() == '.py':
                return PRE_GOLD
            return POST_GOLD_ONLY
        if any(p.is_relative_to(root) for root in self.runtime):
            if 'site-packages' not in p.parts and 'dist-packages' not in p.parts:
                return PRE_GOLD
        return DENIED

    def _flush(self):
        self._local.logging = True
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.write_text(json.dumps(self.log, indent=2) + '\n', encoding='utf-8')
        finally:
            self._local.logging = False

    def _audit(self, event, args):
        if getattr(self._local, 'logging', False):
            return
        if event.startswith('socket.') or event in ('os.system', 'os.posix_spawn', 'os.fork', 'os.exec'):
            raise PermissionError('Network and process execution disabled by V3 guard')
        if event == 'subprocess.Popen' and not self._git_running:
            raise PermissionError('Process execution disabled by V3 guard')
        if event == 'import':
            name = args[0].split('.')[0]
            if name not in sys.stdlib_module_names and name not in sys.builtin_module_names:
                spec = importlib.machinery.PathFinder.find_spec(name, sys.path)
                origin = Path(spec.origin).resolve() if spec and spec.origin and spec.origin not in ('built-in', 'frozen') else None
                if origin is None or not origin.is_relative_to(self.workspace) or origin.suffix != '.py' or self.classify(origin) != PRE_GOLD:
                    raise PermissionError('Non-stdlib import disabled: ' + name)
        if event != 'open':
            return
        path, mode, flags = args
        if isinstance(path, int) and self._git_running:
            return  # Only the verifier's subprocess pipe descriptors.
        reading = not isinstance(mode, str) or 'r' in mode or '+' in mode
        if mode is None:
            reading = (flags & os.O_ACCMODE) != os.O_WRONLY
        if not reading:
            return
        classification = self.classify(path)
        if classification == PRE_GOLD:
            return
        if classification == DENIED:
            raise PermissionError('Private or unknown path blocked by V3 guard')
        record = {'path': str(Path(os.fsdecode(path)).resolve()), 'at': _now()}
        if not self.authorized:
            self.log['blocked_target_reads'].append(record)
            self._flush()
            raise PermissionError('POST_GOLD_ONLY artifact blocked before open')
        # Recheck all evidence before every protected open, catching post-authorization drift.
        try:
            self.verify_post_phase(self.commit)
        except Exception:
            self.authorized = False
            self.log['blocked_target_reads'].append(record)
            self._flush()
            raise
        self.log['authorized_target_open_attempts'].append(record)
        self._flush()

    def _wrap_open(self, original, descriptor=False):
        def guarded(file, *args, **kwargs):
            if descriptor:
                flags = args[0] if args else kwargs.get('flags', 0)
                reading = (flags & os.O_ACCMODE) != os.O_WRONLY
            else:
                mode = args[0] if args else kwargs.get('mode', 'r')
                reading = 'r' in mode or '+' in mode
            target = reading and self.classify(file) == POST_GOLD_ONLY
            result = original(file, *args, **kwargs)
            if target:
                record = {'path': str(Path(os.fsdecode(file)).resolve()), 'at': _now()}
                self.log['successful_target_reads'].append(record)
                self.log['first_actual_target_read_at'] = self.log['first_actual_target_read_at'] or record['at']
                self._flush()
            return result
        return guarded

    def _run_git(self, *args):
        self._git_running = True
        try:
            # Mandatory staged credential scan before the verifier's git read.
            sys.path.insert(0, str(self.workspace / 'tools'))
            from cloud_run_common import credential_locations
            names = subprocess.run(['git', '-C', str(self.workspace), 'diff', '--cached', '--name-only', '--diff-filter=ACMRT', '-z'], capture_output=True, check=True).stdout
            for name in names.decode('utf-8').split('\0'):
                if not name:
                    continue
                staged = subprocess.run(['git', '-C', str(self.workspace), 'show', ':' + name], capture_output=True, check=True).stdout
                if credential_locations(staged, name):
                    raise ValueError('Possible staged credential: ' + name + '; stop without printing values')
            result = subprocess.run(['git', '-C', str(self.workspace), *args],
                                    capture_output=True, check=True)
            return result.stdout
        finally:
            self._git_running = False

    def _read_git(self, ref):
        if self.git_reader is not None:
            return self.git_reader(ref)
        if self._run_git('cat-file', '-t', ref.split(':', 1)[0]).strip() != b'commit':
            raise ValueError('Freeze reference is not a commit object')
        return self._run_git('show', ref)

    def _validate(self, commit):
        if not isinstance(commit, str) or not re.fullmatch('[0-9a-fA-F]{40}', commit):
            raise ValueError('Full 40-hex committed freeze required')
        active = json.loads(self.active.read_text(encoding='utf-8'))
        if active.get('policy_id') != POLICY_ID or active.get('release_id') != RELEASE_ID:
            raise ValueError('Wrong active V3 release')
        raw = self.manifest.read_bytes()
        freeze = json.loads(raw)
        if freeze.get('policy_id') != POLICY_ID or freeze.get('release_id') != RELEASE_ID:
            raise ValueError('Wrong freeze identity')
        if freeze.get('active_release') != active:
            raise ValueError('Freeze must bind exact active release')
        committed = self._read_git(commit + ':' + self.manifest.relative_to(self.workspace).as_posix())
        if isinstance(committed, str):
            committed = committed.encode('utf-8')
        if committed != raw:
            raise ValueError('Committed manifest differs from exact active freeze')
        files = freeze.get('files')
        if not isinstance(files, dict) or not files:
            raise ValueError('Freeze must contain nonempty file hashes')
        for relative, digest in files.items():
            path = (self.workspace / relative).resolve()
            if Path(relative).is_absolute() or not path.is_relative_to(self.workspace):
                raise ValueError('Invalid freeze path')
            if self.classify(path) != PRE_GOLD or path in (self.manifest, self.marker):
                raise ValueError('Freeze hash entries must be PRE_GOLD evidence')
            if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or _sha(path) != digest:
                raise ValueError('Freeze hash drift: ' + relative)
        return {'policy_id': POLICY_ID, 'release_id': RELEASE_ID, 'active_release': active,
                'commit': commit, 'manifest_sha256': hashlib.sha256(raw).hexdigest()}

    def enable_post_phase(self, commit):
        self.authorized = False
        binding = self._validate(commit)
        self.marker.write_text(json.dumps(binding, indent=2) + '\n', encoding='utf-8')
        self.commit = commit
        self.verify_post_phase(commit)
        self.authorized = True
        return binding

    def verify_post_phase(self, commit=None):
        marker = json.loads(self.marker.read_text(encoding='utf-8'))
        binding = self._validate(commit or marker.get('commit'))
        if marker != binding:
            raise ValueError('Post-phase marker binding mismatch')
        return binding

    def install(self, phase='auto'):
        if self.installed:
            raise RuntimeError('Guard already installed')
        if phase not in ('auto', PRE_GOLD, 'POST_GOLD'):
            raise ValueError('Unknown phase')
        self._flush()
        sys.addaudithook(self._audit)
        builtins.open = self._wrap_open(builtins.open)
        io.open = self._wrap_open(io.open)
        os.open = self._wrap_open(os.open, descriptor=True)
        self.installed = True
        if phase == 'POST_GOLD' or (phase == 'auto' and self.marker.exists()):
            binding = self.verify_post_phase()
            self.commit = binding['commit']
            self.authorized = True
        return self

    def audited_entry(self, entry, phase='auto', commit=None):
        self.install(PRE_GOLD if commit else phase)
        if commit:
            self.enable_post_phase(commit)
        if callable(entry):
            return entry()
        return runpy.run_path(str(entry), run_name='__main__')


_DEFAULT = None


def _default():
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Guard()
    return _DEFAULT


def classify(path):
    return _default().classify(path)


def install(phase='auto'):
    return _default().install(phase)


def enable_post_phase(commit):
    return _default().enable_post_phase(commit)


def verify_post_phase(commit=None):
    return _default().verify_post_phase(commit)


def audited_entry(entry, phase='auto', commit=None):
    return _default().audited_entry(entry, phase, commit)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Invoke a Python entry through the V3 access boundary')
    parser.add_argument('--phase', choices=('auto', PRE_GOLD, 'POST_GOLD'), default=PRE_GOLD)
    parser.add_argument('--commit')
    parser.add_argument('entry')
    parser.add_argument('entry_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    sys.argv = [args.entry, *args.entry_args]
    sys.path.insert(0, str(Path(args.entry).resolve().parent))
    audited_entry(args.entry, args.phase, args.commit)
