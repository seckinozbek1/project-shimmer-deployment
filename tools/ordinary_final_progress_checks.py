"""Proofs for the measured-progress reader, driven by a finished run's own evidence.

PROGRESS-A demands a reading per long phase, measured from the work itself, and an
explicit refusal where nothing can be read. These checks hold both halves. Every
observation is replayed from `--observations`, the saved map of remote command to remote
answer, so no check reaches a network, a provider or an instance: the numbers each reader
is asked to reproduce are the ones run v12 actually produced (upload 13.15 GB in 37.4 min,
seed 13.15 GB in 31.9 s, wheels during a 79 s install, workload 7 auditor pairs in 6.3 min).

The reader once broke on a quoting fault while a run was live, printing an empty rate into
a sitrep. `test_every_reader_is_syntactically_whole` and the per-phase readings below are
what catch that class of fault before it reaches a status block.

    py -3.12 tools/ordinary_final_progress_checks.py
"""
import ast
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools')]
import ordinary_final_progress as progress

# What run v12 measured, phase by phase. A reading must reproduce these or the tool is wrong.
ASSETS_BYTES = 13149972480
COPY_PATH = '/home/ubuntu/shimmer-filesystem/assets-8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6.tar'


def bundle_with(directory, **files):
    base = Path(directory)
    for name, payload in files.items():
        (base / name.replace('__', '.')).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf8')
    return base


class ProgressReadings(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.bundle = bundle_with(
            self.directory.name,
            assets_transfer_archive__json=dict(bytes=ASSETS_BYTES, sha256='8f0cbd81', path='assets.tar'),
            asset_copy_declaration__json=dict(filesystem_name='shimmer-filesystem', copy_path=COPY_PATH,
                                              mount='/home/ubuntu/shimmer-filesystem', operator_authorized=True),
            activation__json=dict(metadata=dict(public_ip='198.51.100.10')),
        )
        (self.bundle / 'install.lock').write_text('\n'.join('pkg%d==1.0' % n for n in range(92)), encoding='utf8')

    def read(self, phase, elapsed, observations):
        return progress.reading_for(self.bundle, phase=phase, elapsed=elapsed, observations=observations)

    # --- a reading per long phase, measured from the work itself -------------------------

    def test_upload_reading_reproduces_the_partial_file_on_the_instance(self):
        # Half way through v12's upload: 6.29 GB after 17.8 minutes.
        line = self.read('assets_transfer', 17.8 * 60, {'stat -c %s /home/ubuntu/shimmer-ordinary-final/assets.tar': '6291456000'})
        self.assertIn('6.29 of 13.15 GB', line)
        self.assertIn('(47.8%)', line)
        self.assertIn('17.8 min elapsed', line)
        self.assertIn('MB/s', line)
        self.assertIn('min remaining', line)
        self.assertIn('measured', line)

    def test_upload_reading_at_completion_reports_the_whole_archive_and_no_remaining_time(self):
        line = self.read('assets_transfer', 2245.0, {'assets.tar': str(ASSETS_BYTES)})
        self.assertIn('13.15 of 13.15 GB (100.0%)', line)
        self.assertIn('~0.0 min remaining', line)
        # v12 uploaded at 5.86 MB/s over 37.4 minutes.
        self.assertIn('5.9 MB/s', line)

    def test_seed_reading_watches_the_partial_copy_on_the_declared_mount(self):
        # v12 wrote the whole copy in 31.9 s; the partial name is what exists mid-write.
        line = self.read('asset_copy_seed', 31.9, {COPY_PATH + '.partial': str(ASSETS_BYTES)})
        self.assertIn('13.15 of 13.15 GB', line)
        self.assertIn('412.2 MB/s', line)

    def test_seed_reading_refuses_when_the_bundle_declares_no_copy(self):
        undeclared = bundle_with(tempfile.mkdtemp(),
                                 assets_transfer_archive__json=dict(bytes=ASSETS_BYTES))
        line = progress.reading_for(undeclared, phase='asset_copy_seed', elapsed=10, observations={})
        self.assertIn('not measurable', line)
        self.assertIn('declares no asset copy', line)

    def test_wheel_reading_counts_installed_entries_and_names_what_the_total_is(self):
        line = self.read('install_pinned_wheels', 24.0, {'site-packages': '72'})
        self.assertIn('72 site-packages entries', line)
        self.assertIn('92 pinned requirements', line)
        # Entries are not requirements; the reading must say so rather than claim a percentage.
        self.assertIn('not one to one', line)
        self.assertNotIn('%)', line)

    def test_workload_reading_uses_the_runs_own_agent_counter_when_it_has_written_one(self):
        line = self.read('ordinary_workload', 4.0 * 60,
                         {'model_call': '40\n7\ncompleted=10/12'})
        self.assertIn('10 of 12 agents', line)
        self.assertIn('40 model calls', line)
        self.assertIn('7 auditor pairs', line)
        self.assertIn('4.0 min elapsed', line)
        self.assertIn('min remaining', line)

    def test_workload_reading_falls_back_to_calls_before_the_counter_exists(self):
        line = self.read('ordinary_workload', 2.0 * 60, {'model_call': '29\n0\n'})
        self.assertIn('29 of an unknown number of model calls', line)
        self.assertIn('the run decides its own call count', line)
        self.assertIn('0 auditor pairs', line)

    # --- the explicit refusals ----------------------------------------------------------

    def test_workload_says_nothing_is_measurable_before_the_first_record(self):
        line = self.read('ordinary_workload', 12.0, {'model_call': '0\n0\n'})
        self.assertIn('nothing to measure yet', line)
        self.assertIn('writes nothing before its first model call', line)
        self.assertNotIn('%', line)

    def test_an_unanswered_observation_is_reported_as_unreadable_not_as_zero(self):
        for phase in ('assets_transfer', 'asset_copy_seed', 'install_pinned_wheels', 'ordinary_workload'):
            line = self.read(phase, 60.0, {})          # every command misses: the instance said nothing
            self.assertIn('not measurable', line, phase)
            self.assertNotIn('0.00 of', line, phase)

    def test_a_completion_only_phase_says_so_instead_of_inventing_a_percentage(self):
        for phase in ('archive_integrity', 'extract_payload', 'evidence_download'):
            line = self.read(phase, 30.0, {})
            self.assertIn('reports only on completion', line, phase)
            self.assertNotIn('%', line, phase)

    def test_a_missing_current_phase_file_is_a_refusal_not_a_crash(self):
        empty = Path(tempfile.mkdtemp())
        self.assertIn('not measurable', progress.reading_for(empty))

    # --- the fault that actually happened -----------------------------------------------

    def test_every_reader_is_syntactically_whole(self):
        """The scratchpad version once emitted an empty rate from a broken format string."""
        source = (ROOT / 'tools/ordinary_final_progress.py').read_text(encoding='utf8')
        compile(source, 'ordinary_final_progress.py', 'exec')
        for phase, elapsed, observation in (
                ('assets_transfer', 600.0, {'assets.tar': '1000000000'}),
                ('asset_copy_seed', 30.0, {COPY_PATH: '1000000000'}),
                ('install_pinned_wheels', 30.0, {'site-packages': '40'}),
                ('ordinary_workload', 120.0, {'model_call': '5\n1\ncompleted=3/12'})):
            line = self.read(phase, elapsed, observation)
            self.assertTrue(line.startswith(phase), line)
            # No empty substitution, and every number present has a unit beside it.
            self.assertNotIn('  ', line, line)
            self.assertNotIn(', ,', line, line)
            self.assertNotRegex(line, r'\d(?:\s*$|,)\s*~', line)
            self.assertNotIn('%s', line)
            self.assertNotIn('%d', line)
            self.assertNotIn('%.1f', line)

    def test_every_long_phase_of_the_controller_has_a_reader_or_is_named_completion_only(self):
        """A new long phase must not silently fall through to 'nothing to measure'."""
        controller = (ROOT / 'tools/ordinary_final_cloud.py').read_text(encoding='utf8')
        named = set(re.findall(r"(?:remote|transport|phase)\('([a-z_0-9]+)'", controller))
        unclassified = named - set(progress.READERS) - set(progress.COMPLETION_ONLY)
        unclassified = {p for p in unclassified if not p.startswith(('ssh_ready', 'launch_', 'temporary_',
                                                                     'activation', 'terminated_'))}
        self.assertEqual(set(), unclassified,
                         'these controller phases have neither a reader nor a completion-only entry')

    def test_the_reader_never_touches_the_provider_or_writes_to_the_instance(self):
        """Read the CODE, not the prose: a docstring may name what the tool refuses to do."""
        tree = ast.parse((ROOT / 'tools/ordinary_final_progress.py').read_text(encoding='utf8'))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) else [])
                for name in filter(None, names):
                    self.assertNotIn('lambda', name.lower(), 'the reader must not reach the provider')
                    self.assertNotIn('requests', name.lower(), 'the reader must not reach the network')
        # Every string the tool can send to the instance is a read-only shell command.
        # Docstrings are prose about the tool, not commands, so they are excluded first.
        prose = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                text = ast.get_docstring(node, clean=False)
                if text is not None:
                    prose.add(text)
        sent = [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value not in prose and
                any(verb in n.value for verb in ('stat ', 'grep ', 'ls ', 'cd '))]
        self.assertTrue(sent, 'no remote command found to inspect')
        for command in sent:
            for writing in (' rm ', ' mv ', ' cp ', ' > ', ' >> ', 'tee ', 'truncate', 'chmod', 'kill',
                            'pkill', 'shutdown', 'terminate'):
                self.assertNotIn(writing, command, 'a remote command must not write or kill: ' + command)


# Neutralizations: each replaces one reader's honesty with a plausible shortcut, and the
# named proof must FAIL while it is in force. A check that cannot fail proves nothing.


def size_reading_that_invents_a_rate(phase, done, total, elapsed, what):
    """The fault that reached a live sitrep: a reading whose rate went missing."""
    return '%s progress: %.2f of %.2f GB (%.1f%%) measured, %.1f min elapsed, , ~0.0 min remaining' % (
        phase, done / 1e9, total / 1e9, 100 * done / max(total, 1), max(elapsed, 0) / 60)


def unreadable_that_reports_zero_instead_of_refusing(phase, why):
    """The tempting shortcut: call an unanswered observation zero work done."""
    return '%s progress: 0.00 of 13.15 GB (0.0%%) measured, 0.0 min elapsed, 0.0 MB/s' % phase


NEUTRALIZATIONS = (
    ('test_upload_reading_reproduces_the_partial_file_on_the_instance',
     progress, 'size_reading', size_reading_that_invents_a_rate),
    ('test_an_unanswered_observation_is_reported_as_unreadable_not_as_zero',
     progress, 'unreadable', unreadable_that_reports_zero_instead_of_refusing),
)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProgressReadings)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
