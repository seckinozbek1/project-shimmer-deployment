"""Proofs for tools/factor_record.py (D-S82), on fixture manifests only (no run, no model).

Each rule is proven by neutralise, fail, restore, pass in `check()`, which gate check 342 runs.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import factor_record as fr  # noqa: E402


def manifest(**changes):
    value = dict(
        source_commit='a' * 40, arm='B3',
        models=[dict(model_id='org/producer', revision='r1', files={'model.safetensors': dict(sha256='1' * 64)})],
        project_files={'config/final_models.json': '2' * 64, 'config/semantic_thresholds.json': '3' * 64,
                       'config/compact_extraction_prompt.json': '4' * 64, 'config/decoding_policy.json': '5' * 64,
                       'tools/score_corpus.py': '6' * 64, 'scripts/pipeline_part.py': '7' * 64},
        decoding_policy={'local_producer': dict(sha256='8' * 64)},
        environment={'SHIMMER_INST_FINDER': 'on'},
        workload=dict(files={'context/doc.md': '9' * 64}))
    value.update(changes)
    return value


def changed_file(path, sha, **changes):
    value = manifest(**changes)
    value['project_files'] = dict(value['project_files'], **{path: sha})
    return value


A10 = dict(instance_type='gpu_1x_a10')
H100 = dict(instance_type='gpu_1x_h100_pcie')


class FactorRecordChecks(unittest.TestCase):
    def test_each_declared_file_moves_only_its_own_factor(self):
        """A record names every declared factor; a prompt file changes prompt_or_context alone,
        a calibration file calibration alone, an undeclared file code alone, the launch's type
        machine_type alone, and a factor nothing records is None on both sides and the same."""
        base = fr.record(manifest(), A10)
        self.assertEqual(list(base['factors']), fr.declaration()['factors'])
        self.assertIsNone(base['factors']['seed']['value'])
        self.assertIsNone(base['factors']['training_recipe']['value'])
        cases = [(changed_file('config/compact_extraction_prompt.json', 'f' * 64), A10, ['prompt_or_context']),
                 (changed_file('config/semantic_thresholds.json', 'f' * 64), A10, ['calibration']),
                 (changed_file('scripts/pipeline_part.py', 'f' * 64), A10, ['code']),
                 (changed_file('tools/score_corpus.py', 'f' * 64), A10, ['scorer']),
                 (manifest(), H100, ['machine_type']),
                 (manifest(workload=dict(files={'context/other.md': '9' * 64})), A10, ['item_set']),
                 (manifest(seed=7), A10, ['seed'])]
        for other, launch, expected in cases:
            self.assertEqual(fr.compare(base, fr.record(other, launch))['differs'], expected, expected)
        same = fr.compare(base, fr.record(manifest(), A10))
        self.assertEqual(same['differs'], [])
        self.assertIn('seed', same['unrecorded_on_both'])

    def test_a_gain_goes_to_one_factor_only_when_it_alone_changed_or_is_isolated(self):
        """One factor differs: the whole change is its. Two differ with no isolating run: one
        joint row, not split. With a run isolating the calibration: its measured part and the
        joint remainder. A pair differing in two factors, or on another metric, is refused as
        isolation."""
        a10 = fr.record(manifest(), A10)
        prompt = changed_file('config/compact_extraction_prompt.json', 'f' * 64)
        both = dict(prompt, project_files=dict(prompt['project_files'], **{'config/semantic_thresholds.json': 'e' * 64}))
        calibration = changed_file('config/semantic_thresholds.json', 'e' * 64)
        alone = fr.attribute(0.10, fr.compare(a10, fr.record(prompt, A10)), metric='accuracy')
        self.assertEqual([(r['part'], r['change']) for r in alone['rows']], [('prompt_or_context', 0.10)])
        joint = fr.attribute(0.10, fr.compare(a10, fr.record(both, A10)), metric='accuracy')
        self.assertEqual([(r['part'], r['factors']) for r in joint['rows']],
                         [('joint', ['calibration', 'prompt_or_context'])])
        isolating = [dict(label='calibration-alone', metric='accuracy', change=0.02,
                          comparison=fr.compare(a10, fr.record(calibration, A10))),
                     dict(label='two-at-once', metric='accuracy', change=0.05, comparison=fr.compare(a10, fr.record(both, A10))),
                     dict(label='other-metric', metric='seconds', change=-30,
                          comparison=fr.compare(a10, fr.record(calibration, A10)))]
        split = fr.attribute(0.10, fr.compare(a10, fr.record(both, A10)), isolating, metric='accuracy')
        self.assertEqual([(r['part'], r['factors'], round(r['change'], 6)) for r in split['rows']],
                         [('calibration', ['calibration'], 0.02), ('joint', ['prompt_or_context'], 0.08)])
        self.assertEqual([r['label'] for r in split['refused']], ['two-at-once', 'other-metric'])
        table = fr.render_table('ContraDoc accuracy', split)
        self.assertIn('| calibration | calibration | +0.02 | isolating run calibration-alone |', table)
        self.assertIn('| joint | prompt_or_context | +0.08 |', table)
        self.assertNotIn(chr(0x2014), table)

    def test_a_comparison_across_machine_types_needs_the_reference_pair(self):
        """D-S95 item 5, D-389 ruling 2: results are compared on one machine type, always. A
        comparison across types is refused, the machine alone or with another factor, and a
        reference-set pair given beside it licenses nothing; the reference-set pair itself is the
        one cross-type comparison admitted, for its time factor."""
        item = fr.declaration()['reference_set']['items'][0]
        seal = dict(test_manifest_sha256=item['test_manifest_sha256'])
        on_set = manifest(workload=dict(files=item['workload_files']))
        off = manifest(workload=dict(files={'context/x.md': '0' * 64}))
        b1_a10, b3_h100 = fr.record(dict(off, arm='B1'), A10), fr.record(off, H100)
        pair = fr.compare(fr.record(on_set, A10, seal), fr.record(on_set, H100, seal))
        self.assertTrue(pair['reference_pair'])
        for comparison, given in ((fr.compare(fr.record(off, A10), fr.record(off, H100)), []),
                                  (fr.compare(b1_a10, b3_h100), []),
                                  (fr.compare(b1_a10, b3_h100), [dict(label='pair', metric='accuracy', change=0.0,
                                                                     comparison=pair)])):
            with self.assertRaisesRegex(ValueError, 'across machine types is refused'):
                fr.attribute(0.1, comparison, given, metric='accuracy')
        self.assertFalse(fr.compare(fr.record(off, A10), fr.record(off, H100))['reference_pair'])
        self.assertEqual(fr.attribute(0.0, pair, metric='seconds')['rows'][0]['part'], 'machine_type')

    def test_a_paired_figure_of_two_arms_needs_one_machine_type(self):
        """D-389 ruling 2, where the figure is made: the benchmark adapters' paired score refuses two
        labels files that record different machine types, or one that records it beside one that
        does not; two that record none are paired and say so; the type is read from the arm's
        controller run folders, which must agree among themselves."""
        import importlib
        sys.path.insert(0, str(HERE.parent))
        cli = importlib.import_module('benchmark.adapters.common.cli')
        self.assertEqual(cli.check_same_machine({'machine_type': 'gpu_1x_a10'}, {'machine_type': 'gpu_1x_a10'}), 'gpu_1x_a10')
        self.assertEqual(cli.check_same_machine({}, {}), cli.NOT_RECORDED)
        # D-436 item 5b: two controller arms with an unrecorded type are refused; B0 runs on no machine.
        with self.assertRaisesRegex(ValueError, 'label each controller arm with --run-folder'):
            cli.check_same_machine({'arm': 'B3'}, {'arm': 'B1'})
        self.assertEqual(cli.check_same_machine({'arm': 'B3', 'machine_type': 'gpu_1x_a10'}, {'arm': 'B0'}), 'gpu_1x_a10')
        for mine, other in (({'machine_type': 'gpu_1x_a10'}, {'machine_type': 'gpu_1x_h100_pcie'}),
                            ({'arm': 'B3', 'machine_type': 'gpu_1x_a10'}, {'arm': 'B1'})):
            with self.assertRaisesRegex(ValueError, 'different or unrecorded machine types'):
                cli.check_same_machine(mine, other)
        with tempfile.TemporaryDirectory() as tmp:
            folders = []
            for name, machine in (('a', 'gpu_1x_a10'), ('b', 'gpu_1x_a10'), ('c', 'gpu_1x_h100_pcie')):
                folder = Path(tmp) / name
                folder.mkdir()
                (folder / 'launch_preflight.json').write_text(json.dumps(dict(selected=dict(type=machine))), encoding='utf-8')
                folders.append(folder)
            self.assertEqual(cli.machine_type_of(folders[:2]), 'gpu_1x_a10')
            with self.assertRaisesRegex(ValueError, 'different or unrecorded machine types'):
                cli.machine_type_of(folders)

    def test_a_machine_effect_needs_the_reference_set_and_the_machine_alone(self):
        """A declared reference item on both machines gives the time factor (against the declared
        A10 seconds) and whether a score moved (a hardware effect); it is refused with no declared
        set, off the set, when the first run is not on the A10, or when anything but the machine
        differs."""
        item = fr.declaration()['reference_set']['items'][0]
        on_set = manifest(workload=dict(files=item['workload_files']))
        seal = dict(test_manifest_sha256=item['test_manifest_sha256'])
        a10 = fr.record(on_set, A10, seal)
        h100 = fr.record(on_set, H100, seal)
        same = fr.machine_effect(a10, h100, item['a10_seconds'] / 2, {'acc': 0.6}, {'acc': 0.6})
        self.assertEqual((same['item'], same['time_factor'], same['scores_moved']), (item['item'], 2.0, []))
        moved = fr.machine_effect(a10, h100, 40, {'acc': 0.6}, {'acc': 0.61}, seconds_a10=100)
        self.assertEqual((moved['time_factor'], moved['scores_moved']), (2.5, ['acc']))
        self.assertTrue(moved['verdict'].startswith('hardware effect'))
        other_code = fr.record(dict(on_set, project_files=dict(on_set['project_files'], **{'scripts/pipeline_part.py': 'f' * 64})), H100, seal)
        with self.assertRaisesRegex(ValueError, 'differ in the machine alone'):
            fr.machine_effect(a10, other_code, 40, {}, {})
        with self.assertRaisesRegex(ValueError, 'not on the reference machine'):
            fr.machine_effect(h100, fr.record(on_set, A10, seal), 40, {}, {})
        off = manifest(workload=dict(files={'context/x.md': '0' * 64}))
        with self.assertRaisesRegex(ValueError, 'not on the declared reference set'):
            fr.machine_effect(fr.record(off, A10), fr.record(off, H100), 40, {}, {})
        spec = fr.declaration()
        spec['reference_set']['items'] = []
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'factor_record.json'
            config.write_text(json.dumps(spec), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'No fixed reference set declared'):
                fr.machine_effect(a10, h100, 40, {}, {}, config=config)

    def test_the_declared_reference_set_is_three_a10_entries_with_their_own_digests(self):
        """The lead's ruling (D-S82 item 3): one ContraDoc document and one SciTab table from C1
        and the timing entry's document (news_train_96, 01015e47de8a) from L12, each run on the
        A10 with integrity passed. Each item's item_set is the digest this reader computes from
        the item's own workload digests, so a run of that workload on any machine is recognised as
        that item and no other; every A10 time is positive and every source is named."""
        reference = fr.declaration()['reference_set']
        self.assertEqual(reference['machine'], 'gpu_1x_a10')
        items = reference['items']
        self.assertEqual([i['item'] for i in items], ['contradoc_0436316e6bb3', 'scitab_09b24267b75a', 'contradoc_01015e47de8a'])
        for item in items:
            computed = fr.record(manifest(workload=dict(files=item['workload_files'])), A10,
                                 dict(test_manifest_sha256=item['test_manifest_sha256']))['factors']['item_set']['value']
            self.assertEqual(computed, item['item_set'], item['item'])
            self.assertGreater(item['a10_seconds'], 0)
            self.assertTrue(item['execution_integrity_passed'] and item['source_run'] and item['source_folder']
                            and item['seconds_file'] and item['source_commit'])
            self.assertEqual(len(item['workload_files']), 2)
            self.assertTrue(all(len(v) == 64 for v in item['workload_files'].values()))
        self.assertEqual(len({i['item_set'] for i in items}), 3)

    def test_the_run_folder_record_reads_a_batch_entry_with_its_sessions_launch(self):
        """The CLI reads the run's own files: a batch entry's machine is its session's launch."""
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / 'session'
            entry = session / 'batch' / '00_item'
            entry.mkdir(parents=True)
            (session / 'launch.json').write_text(json.dumps(H100), encoding='utf-8')
            (entry / 'execution_manifest.json').write_text(json.dumps(manifest()), encoding='utf-8')
            rec = fr.folder_record(entry)
            self.assertEqual(rec['factors']['machine_type']['value'], 'gpu_1x_h100_pcie')
            self.assertEqual(rec['source_commit'], 'a' * 40)


NEUTRALISED = [
    # Every file read as code: a prompt change is no longer the prompt's.
    ('assign_files', lambda project_files, declared: dict({n: {} for n in declared}, code=dict(project_files)),
     ['test_each_declared_file_moves_only_its_own_factor']),
    # Nothing ever differs.
    ('differs', lambda a, b: False, ['test_each_declared_file_moves_only_its_own_factor']),
    # A joint change handed whole to its first factor.
    ('attribute', lambda change, comparison, isolating=(), metric=None: dict(
        metric=metric, change=change, refused=[],
        rows=[dict(part=comparison['differs'][0], factors=comparison['differs'][:1], change=change, basis='first')]),
     ['test_a_gain_goes_to_one_factor_only_when_it_alone_changed_or_is_isolated']),
    # The item set read from nothing: every workload is the same item.
    ('_value', lambda parts, source: dict(value='same', source=source),
     ['test_the_declared_reference_set_is_three_a10_entries_with_their_own_digests']),
    # A comparison across machine types admitted (D-389 ruling 2).
    ('require_machine_pair', lambda comparison, isolating=(), config=None: None,
     ['test_a_comparison_across_machine_types_needs_the_reference_pair']),
    # Arms on different machine types paired by the adapters (D-389 ruling 2).
    ('require_same_type', lambda folders: 'gpu_1x_a10', ['test_a_paired_figure_of_two_arms_needs_one_machine_type']),
    # Every pair reads as differing in the machine alone.
    ('compare', lambda a, b: dict(differs=['machine_type'], same=[], unrecorded_on_both=[]),
     ['test_a_machine_effect_needs_the_reference_set_and_the_machine_alone']),
]


def passes(*names):
    loader = unittest.defaultTestLoader
    suite = (unittest.TestSuite(FactorRecordChecks(n) for n in names) if names
             else loader.loadTestsFromTestCase(FactorRecordChecks))
    result = unittest.TextTestRunner(stream=open(__import__('os').devnull, 'w'), verbosity=0).run(suite)
    return result.wasSuccessful() and result.testsRun > 0


def check():
    if not passes():
        return 'FAIL', 'tools/factor_record_checks.py does not pass'
    proofs = []
    for attribute, mutant, names in NEUTRALISED:
        with patch.object(fr, attribute, mutant):
            failed = not passes(*names)
        restored = passes(*names)
        if not (failed and restored):
            return 'FAIL', 'factor_record.%s neutralised: failed=%s, restored pass=%s' % (attribute, failed, restored)
        proofs.append(attribute)
    return 'PASS', ('every result carries a Python-written factor record; a gain goes to one factor only when it '
                    'alone changed or an isolating run measures it, else it is joint; a machine effect needs the '
                    'fixed reference set and the machine alone; neutralised, failed, restored, passed: '
                    + ', '.join(proofs))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == 'PASS' else 1)
