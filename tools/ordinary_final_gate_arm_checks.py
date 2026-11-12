"""Arm G checks (D-S75, D-329) and the declared type order (D-S78 item 2).

The gate runs on a rented machine as a sealed arm: `scripts/verify_session1.py`, or the declared
side gates, on the bound commit's tracked tree, with the laptop's own command. These checks prove
its rules here, on fixtures, with no model, no provider and no network: the sealed gate block and
what it refuses, the sealed command, the assessment (every check outside the known-red list must
pass), the runner on a stand-in gate in a real child process with its own clean environment, the
gate's two flags (`--results`, `--checks`) on stand-in checks, the sealer's reading of the bound
gate's check numbers, the analyser's Gate row, and the declared instance-type order with its
GPU-count admission.

The tests live in GateArmChecks, mixed into the controller checks' ControllerChecks, and each
rule is proven by neutralise, fail, restore, pass through GATE_NEUTRALIZATIONS.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT / 'tools'), str(ROOT / 'scripts')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import analyze_ordinary_final_run as analysis  # noqa: E402
import loop_budget_guard as guard  # noqa: E402
import ordinary_final_run as runner  # noqa: E402
from ordinary_final_run import read, sha, write  # noqa: E402
import prepare_ordinary_final_run as sealer  # noqa: E402
import verify_session1 as gate_module  # noqa: E402
import factor_record as factor_record_module  # noqa: E402

DIGEST = 'a' * 64
_REAL_ASSESS = runner.assess_gate
_REAL_DECLARED = guard.declared_candidates

FAKE_GATE = '''import json, os, sys
args = sys.argv[1:]
path = args[args.index('--results') + 1]
chosen = None
if '--checks' in args:
    chosen = {int(n) for n in args[args.index('--checks') + 1].split(',')}
statuses = {1: 'PASS', 2: 'FAIL', 3: 'SKIP'}
clean = not any(k.startswith('SHIMMER_') for k in os.environ) and os.environ.get('HF_HUB_OFFLINE') == '1'
with open(path, 'w') as out:
    for n, s in statuses.items():
        if chosen is None or n in chosen:
            out.write(json.dumps({'number': n, 'title': 'clean' if clean else 'dirty', 'status': s, 'seconds': 0.1}) + '\\n')
sys.exit(1)
'''


GIT_GATE = '''import json, subprocess, sys
args = sys.argv[1:]
path = args[args.index('--results') + 1]
run = lambda *a: subprocess.run(['git', *a], capture_output=True, text=True)
seen = dict(head=run('rev-parse', 'HEAD').stdout.strip(), status=run('status', '--porcelain', '--untracked-files=all').stdout,
            crlf=subprocess.run(['git', 'cat-file', 'blob', 'HEAD:docs/crlf.txt'], capture_output=True).stdout
            == open('docs/crlf.txt', 'rb').read())
with open(path, 'w') as out:
    out.write(json.dumps({'number': 1, 'title': json.dumps(seen), 'status': 'PASS', 'seconds': 0.1}) + '\\n')
'''


def gate_manifest(**fields):
    block = dict(form='full', checks='all', known_red=[], check_numbers=[1, 2, 3], source_sha256=DIGEST, source_tree='c' * 40,
                 requirements={'fastapi': '0.1'})
    block.update(fields)
    return dict(arm='G', gate=block, support_files={runner.GATE_SOURCE: DIGEST}, packages={'fastapi': '0.1'},
                multi_round=False, protected_test=False)


def raw_tree_id(members, root):
    """The git tree id of `members` taken as raw bytes (hash-object --no-filters into a scratch
    repository's index), or None for a member git cannot name (a path leaving the tree)."""
    import subprocess
    repo = Path(tempfile.mkdtemp(dir=root))
    run = lambda *a, data=None: subprocess.run(['git', '-C', str(repo), *a], input=data, capture_output=True, check=True).stdout
    try:
        run('init', '-q')
        for name, data in members.items():
            blob = run('hash-object', '-w', '--no-filters', '--stdin', data=data).decode().strip()
            run('update-index', '--add', '--cacheinfo', '100644,%s,%s' % (blob, name))
        return run('write-tree').decode().strip()
    except subprocess.CalledProcessError:
        return None


def unguarded_git(tree, env, deadline, *args):
    """gate_git with no refusal of its own: git's failures raised as they come."""
    import subprocess
    return subprocess.run(['git', '-C', str(tree), *args], env=env, capture_output=True, text=True, check=True).stdout


def archive_through_git(root, source, archive):
    """The sealer's archive as it was: `git archive`, which applies the repository's eol and
    autocrlf settings to every member."""
    import subprocess
    run = lambda *a: subprocess.run(['git', '-C', str(root), *a], capture_output=True, check=True).stdout
    run('archive', '--format=tar', '-o', str(archive), source)
    return run('rev-parse', source + '^{tree}').decode().strip()


def refused(call):
    try:
        call()
    except Exception as exc:
        return str(exc)
    return None


def inventory_entry(name, rate, gpu, count=1, regions=('us-east-1',)):
    return dict(metadata=dict(type=name, hourly_rate=rate, gpu_type=gpu, gpu_count=count, cpu=30, ram_gib=200,
                              storage_gib=1400), architecture='x86_64', regions=list(regions))


class GateArmChecks:
    def test_the_fastest_route_takes_higher_tiers_by_measurement_with_the_gpus_the_run_needs(self):
        """D-S95: one and two tiers above the A10 are candidates (A100, H100, B200) in the declared
        generations order, with no price factor, and a type is taken only with exactly the GPUs the
        run needs, never more, in the fastest and the declared orders alike (D-382 item 4). An
        arm64 GH200 stays out: the sealed wheels are x86_64."""
        offered = [inventory_entry('gpu_1x_a10', 1.29, 'A10 (24 GB PCIe)'),
                   inventory_entry('gpu_1x_a100', 1.99, 'A100 (40 GB PCIe)'),
                   inventory_entry('gpu_1x_h100_pcie', 3.29, 'H100 (80 GB PCIe)'),
                   inventory_entry('gpu_1x_b200', 6.99, 'B200 (180 GB SXM6)'),
                   inventory_entry('gpu_8x_h100_sxm5', 31.92, 'H100 (80 GB SXM5)', count=8),
                   dict(inventory_entry('gpu_1x_gh200', 1.49, 'GH200 (96 GB)'), architecture='arm64')]
        order = guard.speed_order(dict(order=['B200', 'H100', 'GH200', 'A100', 'A10']))
        declared = guard.fastest_candidates(offered, order)
        self.assertEqual([c['type'] for c in declared], ['gpu_1x_b200', 'gpu_1x_h100_pcie', 'gpu_1x_a100', 'gpu_1x_a10'])
        self.assertGreater(declared[0]['max_hourly_rate'], guard.TYPE_RULE_FACTOR * 1.29)  # no price factor
        self.assertIsNotNone(refused(lambda: guard.speed_order(dict(order=['A10', 'A10']))))
        self.assertEqual([c['type'] for c in guard.fastest_candidates(offered, order, gpus=8)], ['gpu_8x_h100_sxm5'])
        self.assertIsNotNone(refused(lambda: guard.fastest_candidates(offered, order, gpus=2)))
        self.assertIsNotNone(refused(lambda: guard.fastest_candidates(offered, order, gpus=0)))
        self.assertIn('another GPU count', refused(lambda: guard.declared_candidates(offered, ['gpu_8x_h100_sxm5'])) or '')
        self.assertEqual([c['type'] for c in guard.declared_candidates(offered, ['gpu_8x_h100_sxm5'], gpus=8)],
                         ['gpu_8x_h100_sxm5'])
        # The sealer admits one GPU only, in one sentence, until the runner's projection changes.
        self.assertEqual(refused(lambda: sealer.budget_fields({}, dict(ledgers=[], gpus=2), 0)), sealer.SINGLE_GPU_ONLY)

    def test_a_compared_run_leaves_the_a10_only_for_a_type_with_its_reference_pair(self):
        """D-S95, D-S96 item 2, D-382 item 1: a run leaves the A10 only for a machine type whose
        reference-set pair is measured (keyed by machine type); the kept types rank by their measured
        factor with the A10 at 1.0, so one measured slower than the A10 ranks below it; the
        reference-set run itself may take any offered type; with nothing left it refuses."""
        offered = [inventory_entry('gpu_1x_a10', 1.29, 'A10 (24 GB PCIe)'),
                   inventory_entry('gpu_1x_a100', 1.99, 'A100 (40 GB PCIe)'),
                   inventory_entry('gpu_1x_h100_pcie', 3.29, 'H100 (80 GB PCIe)')]
        order = ['B200', 'H100', 'GH200', 'A100', 'A10']
        fastest = guard.fastest_candidates(offered, order)
        measured = lambda **factors: {k: dict(time_factor=v) for k, v in factors.items()}
        types = lambda spec, **kw: [c['type'] for c in guard.measured_tiers(fastest, spec, **kw)]
        self.assertEqual(types(dict(order=order, measured={})), ['gpu_1x_a10'])
        self.assertEqual(types(dict(order=order, measured=measured(gpu_1x_h100_pcie=2.5))), ['gpu_1x_h100_pcie', 'gpu_1x_a10'])
        # A token key is not a machine type: nothing is measured for gpu_1x_h100_pcie.
        self.assertEqual(types(dict(order=order, measured={'H100': dict(time_factor=2.5)})), ['gpu_1x_a10'])
        self.assertEqual(types(dict(order=order, measured=measured(gpu_1x_h100_pcie=1.5, gpu_1x_a100=2.0))),
                         ['gpu_1x_a100', 'gpu_1x_h100_pcie', 'gpu_1x_a10'])
        self.assertEqual(types(dict(order=order, measured=measured(gpu_1x_h100_pcie=0.8))), ['gpu_1x_a10', 'gpu_1x_h100_pcie'])
        self.assertEqual(types(dict(order=order, measured={}), reference_run=True),
                         ['gpu_1x_h100_pcie', 'gpu_1x_a100', 'gpu_1x_a10'])
        self.assertIn('reference-set pair', refused(lambda: guard.measured_tiers(fastest[:1], dict(order=order, measured={})))
                      or '')
        # The sealer recognises a reference-set run by its workload alone.
        import factor_record
        item = factor_record.declaration()['reference_set']['items'][0]
        self.assertEqual(factor_record.reference_workload(item['workload_files'])['item'], item['item'])
        self.assertIsNone(factor_record.reference_workload(dict(item['workload_files'], extra='0' * 64)))

    def reference_pair_folders(self, root, commit='c' * 40, other='gpu_1x_h100_pcie'):
        """Run folders of the three reference items on the A10 and on `other`, at one commit."""
        import factor_record
        reference = factor_record.declaration()['reference_set']
        pairs = []
        for item in reference['items']:
            records = {}
            for machine in ('gpu_1x_a10', other):
                folder = Path(root) / (item['item'] + '_' + machine)
                folder.mkdir(parents=True)
                (folder / 'execution_manifest.json').write_text(json.dumps(dict(
                    source_commit=commit, arm='B3', project_files={'scripts/x.py': '1' * 64},
                    workload=dict(files=item['workload_files']))), encoding='utf-8')
                (folder / 'seal.json').write_text(json.dumps(dict(test_manifest_sha256=item['test_manifest_sha256'])),
                                                  encoding='utf-8')
                (folder / 'launch.json').write_text(json.dumps(dict(instance_type=machine)), encoding='utf-8')
                records[machine] = folder
            pairs.append(dict(item=item['item'], a10_folder=records['gpu_1x_a10'], other_folder=records[other]))
        return pairs

    def test_a_measured_entry_carries_its_reference_set_result_and_moved_no_score(self):
        """D-382 item 1, D-401 item 3: a `measured` entry is the reference pair of all three reference
        items, each with both runs' folders and record digests and one commit, read again at sealing;
        its factor is the median of the three items' factors; any moved score keeps the type out (and
        exact equality may never hold across GPU generations, which then keeps it out too). An entry
        with a changed record, a wrong factor, a missing item, two commits or another key is refused.
        The shipped file carries none yet."""
        import factor_record
        with tempfile.TemporaryDirectory() as tmp:
            pairs = self.reference_pair_folders(tmp)
            factors = (2.0, 3.0, 2.5)
            for pair, factor in zip(pairs, factors):
                a10, other = factor_record.folder_record(pair['a10_folder']), factor_record.folder_record(pair['other_folder'])
                pair['effect'] = factor_record.machine_effect(a10, other, 100.0 / factor, {'acc': 0.6}, {'acc': 0.6},
                                                              seconds_a10=100.0)
            entry = factor_record.measured_entry(pairs)
            self.assertEqual((entry['time_factor'], entry['commit'], len(entry['items'])), (2.5, 'c' * 40, 3))
            self.assertTrue(factor_record.check_measured(dict(measured={'gpu_1x_h100_pcie': entry})))
            moved = [dict(pair) for pair in pairs]
            moved[1]['effect'] = dict(moved[1]['effect'], scores_moved=['acc'])
            with self.assertRaisesRegex(ValueError, 'keeps the type out'):
                factor_record.measured_entry(moved)
            with self.assertRaisesRegex(ValueError, 'every declared reference item once'):
                factor_record.measured_entry(pairs[:2])
            bad = [{'gpu_1x_a100': entry}, {'gpu_1x_h100_pcie': dict(entry, time_factor=3.0)},
                   {'gpu_1x_h100_pcie': dict(entry, items=entry['items'][:2])},
                   {'gpu_1x_h100_pcie': dict(entry, commit='d' * 40)},
                   {'gpu_1x_h100_pcie': dict(entry, scores_moved=True)}]
            for measured in bad:
                with self.subTest(measured=sorted(measured)), self.assertRaisesRegex(ValueError, 'not a checked reference-set'):
                    factor_record.check_measured(dict(measured=measured))
            # A run folder changed after the entry was made refuses it at sealing.
            folder = Path(entry['items'][0]['other_folder'])
            (folder / 'launch.json').write_text(json.dumps(dict(instance_type='gpu_1x_b200')), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'not a checked reference-set'):
                factor_record.check_measured(dict(measured={'gpu_1x_h100_pcie': entry}))
        with tempfile.TemporaryDirectory() as tmp:
            two = self.reference_pair_folders(tmp)
            (Path(two[2]['a10_folder']) / 'execution_manifest.json').write_text(json.dumps(dict(
                json.loads((Path(two[2]['a10_folder']) / 'execution_manifest.json').read_text()), source_commit='d' * 40)))
            for pair in two:
                pair['effect'] = dict(machine='gpu_1x_h100_pcie', time_factor=2.0, scores_moved=[])
            with self.assertRaisesRegex(ValueError, 'one machine type beside the A10 at one commit'):
                factor_record.measured_entry(two)
        self.assertEqual(json.loads(guard.GPU_SPEED_ORDER.read_text(encoding='utf-8')).get('measured'), {})

    def test_one_comparison_seals_one_machine_type_and_its_arms_ran_on_it(self):
        """D-S95 item 5, D-401 item 1: a B3 or B1 bundle names its comparison or says --uncompared;
        the comparison's type is recorded at launch, after the guard's decision and under the lock,
        beside the private ledger (a later launch on another type refused); the sealer reads the
        record and seals that one type; and a figure whose arms ran on different (or unrecorded)
        machine types is refused, by the records check and by the analyser's batch pairing."""
        import factor_record
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / 'comparisons.jsonl'
            self.assertTrue(guard.claim_comparison('gate-contradoc', 'gpu_1x_a10', 0, registry)['first'])
            self.assertFalse(guard.claim_comparison('gate-contradoc', 'gpu_1x_a10', 0, registry)['first'])
            self.assertIn('runs on gpu_1x_a10', refused(lambda: guard.claim_comparison('gate-contradoc', 'gpu_1x_h100_pcie',
                                                                                       0, registry)) or '')
            self.assertIsNotNone(refused(lambda: guard.claim_comparison('Bad Name', 'gpu_1x_a10', 0, registry)))
            offered = [dict(type='gpu_1x_h100_pcie'), dict(type='gpu_1x_a10')]
            self.assertEqual(sealer.comparison_type('gate-contradoc', offered, registry), [dict(type='gpu_1x_a10')])
            self.assertEqual(sealer.comparison_type('gate-scitab', offered, registry), [dict(type='gpu_1x_h100_pcie')])
            self.assertIsNotNone(refused(lambda: sealer.comparison_type('gate-contradoc', offered[:1], registry)))
            for arm, budget, ok in (('B3', {}, False), ('B3', dict(comparison='x', uncompared=True), False),
                                    ('B1', dict(comparison='x'), True), ('B3', dict(uncompared=True), True),
                                    ('G', {}, True), ('L', {}, True)):
                with self.subTest(arm=arm, budget=budget):
                    if ok:
                        self.assertTrue(sealer.comparison_declared(arm, budget, None))
                    else:
                        self.assertEqual(refused(lambda: sealer.comparison_declared(arm, budget, None)),
                                         sealer.COMPARISON_REQUIRED)
            self.assertTrue(sealer.comparison_declared('B3', {}, dict(item='reference')))
            arms = []
            for name, machine in (('b3', 'gpu_1x_a10'), ('b1', 'gpu_1x_a10'), ('other', 'gpu_1x_h100_pcie')):
                folder = Path(tmp) / name
                folder.mkdir()
                (folder / 'launch_preflight.json').write_text(json.dumps(dict(selected=dict(type=machine))), encoding='utf8')
                (folder / 'seal_entry.json').write_text(json.dumps(dict(item='i1', arm=name)), encoding='utf8')
                arms.append(folder)
            self.assertEqual(factor_record.require_same_type(arms[:2]), 'gpu_1x_a10')
            with self.assertRaisesRegex(ValueError, 'different or unrecorded machine types'):
                factor_record.require_same_type(arms)
            with self.assertRaisesRegex(ValueError, 'different or unrecorded machine types'):
                factor_record.require_same_type([arms[0], Path(tmp) / 'missing'])
            self.assertEqual(analysis.pair_machine_types(arms[:2]), {'i1': 'gpu_1x_a10'})
            with self.assertRaisesRegex(ValueError, 'different or unrecorded machine types'):
                analysis.pair_machine_types(arms)

    def test_the_controller_claims_the_comparisons_type_under_the_lock(self):
        """D-401 item 1 (d), on the real controller: a bundle sealed under a comparison records its
        type at launch beside the private ledger, after the guard's decision; a second launch of the
        same comparison on another recorded type is refused before any instance."""
        self.remanifest(comparison=dict(name='gate-contradoc', type='gpu_1x_a10'))
        transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        registry = guard.comparison_registry()
        self.assertEqual(guard.comparison_recorded('gate-contradoc'), 'gpu_1x_a10')
        self.assertTrue(read(self.base / 'comparison_claim.json')['first'])
        self.setUp()
        guard.claim_comparison('gate-contradoc', 'gpu_1x_h100_pcie', 0, guard.comparison_registry())
        self.remanifest(comparison=dict(name='gate-contradoc', type='gpu_1x_a10'))
        with self.assertRaisesRegex(guard.GuardRefusal, 'runs on gpu_1x_h100_pcie'):
            self.execute()
        self.assertIsNotNone(registry)

    def test_the_guard_counts_the_cloud_reference_spend_and_waits_for_role_cs(self):
        """D-S121 (D-453), D-401 item 11: the guard counts Lambda alone toward its hard stop: the cloud
        reference's spend and running intents, read from the store, add nothing to the decision; an
        absent store refuses, never read as no spend, and a handed-back role C file not yet appended
        refuses (lead_may_spend) until it is appended."""
        import cloud_reference_spend as cloud_spend
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / 'private' / 'cloud_reference_spend.jsonl'
            store.parent.mkdir()
            ledger = Path(tmp) / 'ledger.jsonl'
            ledger.write_text(json.dumps(dict(event='budget_open', time_utc='2026-10-27T03:00:00+00:00', budget_usd=50.0,
                                              loop_start_utc='2026-10-27T03:00:00+00:00', storage_usd_per_day=0.0))
                              + chr(10), encoding='utf-8')
            decide = lambda **kw: guard.check(ledgers=[ledger], forecast_minutes=60, hourly_rate=1.29, storage_forecast_usd=3.9,
                                             now_epoch=1_000_000.0, reserve_minutes=15, reaped=[], **kw)
            self.assertIn('does not exist', refused(lambda: decide(spend_store=store)) or '')
            store.write_text(json.dumps(dict(run_id='r1', event='close', spent_usd=40.0)) + chr(10)
                             + json.dumps(dict(run_id='c1', event='intent', cap_usd=2.0, kind=cloud_spend.ROLE_C_KIND)) + chr(10),
                             encoding='utf-8')
            with_api, without = decide(spend_store=store), decide()
            self.assertEqual((with_api['spend_usd'], with_api['running_caps_usd'], with_api['cap_usd']),
                             (without['spend_usd'], without['running_caps_usd'], without['cap_usd']))
            drop = cloud_spend.handback_dir(store)
            drop.mkdir()
            handed = drop / 'role_c_spend.jsonl'
            handed.write_text(json.dumps(dict(run_id='c1', event='close', spent_usd=1.0)) + chr(10), encoding='utf-8')
            self.assertIn('handed back and not appended', refused(lambda: decide(spend_store=store)) or '')
            cloud_spend.append_handed_back(store, handed)
            self.assertEqual(decide(spend_store=store)['cap_usd'], without['cap_usd'])
    def test_the_bound_preflight_applies_the_sealed_declared_type_rule(self):
        """The bound preflight reads the manifest's type rule as the controller does: a declared,
        fastest-first manifest (no A10 first in its candidates) passes against a fake inventory and
        selects its first offered type; the same bundle with the A10-first rule is refused."""
        import ordinary_final_bound_preflight as bound_preflight
        inventory = [inventory_entry('gpu_1x_a10', 1.29, 'A10 (24 GB PCIe)'),
                     inventory_entry('gpu_1x_h100_pcie', 3.29, 'H100 (80 GB PCIe)')]
        candidates = guard.fastest_candidates(inventory, ['H100', 'GH200', 'A100', 'A10'])
        self.assertEqual(candidates[0]['type'], 'gpu_1x_h100_pcie')
        manifest = read(self.base / 'execution_manifest.json')
        manifest.update(instance_candidates=candidates, type_rule='declared', type_order='fastest', a10_reference_rate=1.29)
        write(self.base / 'execution_manifest.json', manifest)
        write(self.base / 'authorization_binding.json', dict(manifest_sha256=sha(self.base / 'execution_manifest.json')))
        self.declare_copy()   # D-421: the bound preflight refuses an undeclared us-east-1 bundle
        calls = []

        class Provider:
            def __init__(self, credential):
                pass

            def request(self, endpoint, body=None):
                calls.append(endpoint)
                return {'data': {'instances': [], 'instance-types': inventory, 'images': [manifest['image']]}[endpoint]}
        with patch.object(bound_preflight, 'LambdaExperiment', Provider),                 patch.object(bound_preflight, 'credential_path', lambda: 'fixture-credential-path'),                 contextlib.redirect_stdout(io.StringIO()):
            bound_preflight.main(self.base)
        receipt = read(self.base / 'authorized_live_preflight.json')
        self.assertTrue(receipt['passed'])
        self.assertFalse(receipt['launched'])
        self.assertEqual((receipt['instance']['metadata']['type'], receipt['region'], receipt['rate_authorized_ceiling']),
                         ('gpu_1x_h100_pcie', 'us-east-1', 3.29))
        self.assertEqual(calls, ['instances', 'instance-types', 'images'])

    def test_an_arm_g_bundle_is_admitted_only_with_its_sealed_gate_block(self):
        self.assertEqual(runner.arm_declaration(gate_manifest()), 'G')
        self.assertEqual(runner.arm_declaration(gate_manifest(form='side')), 'G')
        self.assertEqual(runner.arm_declaration(gate_manifest(checks=[1, 3], known_red=[2])), 'G')
        bad = [gate_manifest(checks=[4]), gate_manifest(checks=[]), gate_manifest(known_red=[9]),
               gate_manifest(form='other'), gate_manifest(form='side', checks=[1]),
               gate_manifest(source_sha256='b' * 64), gate_manifest(requirements={'fastapi': '0.2'}),
               gate_manifest(check_numbers=[]), dict(gate_manifest(), b1={}), dict(gate_manifest(), multi_round=True)]
        extra = gate_manifest()
        extra['gate'] = dict(extra['gate'], more=1)
        bad.append(extra)
        for manifest in bad:
            self.assertIsNotNone(refused(lambda: runner.arm_declaration(manifest)), manifest)
        # A gate block or its archive in any other arm's bundle is refused.
        b3 = dict(gate_manifest(), arm='B3')
        b3.pop('packages')
        self.assertIn('gate block sealed', refused(lambda: runner.arm_declaration(b3)) or '')

    def test_a_gate_pin_holds_against_the_lock_with_its_local_label_dropped(self):
        # One rule (ordinary_final_run.pin_held) at sealing and at admission: the lock's local
        # label is dropped when the pin names none, and nothing else is loosened.
        held = [('2.5.1+cu121', '2.5.1'), ('2.5.1', '2.5.1'), ('2.5.1+cu121', '2.5.1+cu121')]
        not_held = [('2.5.2+cu121', '2.5.1'), ('2.5.10', '2.5.1'), ('2.5.1+cu124', '2.5.1+cu121'),
                    ('2.5.1', '2.5.1+cu121'), ('4.51.3', '4.52.3'), (None, '2.5.1'), ('2.5.1', None)]
        self.assertEqual([runner.pin_held(a, b) for a, b in held], [True] * len(held))
        self.assertEqual([runner.pin_held(a, b) for a, b in not_held], [False] * len(not_held))
        # The runner admits a sealed gate block whose pin the lock holds only through its label.
        cuda = gate_manifest(requirements={'torch': '2.5.1'})
        cuda['packages'] = {'torch': '2.5.1+cu121'}
        self.assertEqual(runner.arm_declaration(cuda), 'G')
        other = gate_manifest(requirements={'torch': '2.5.1'})
        other['packages'] = {'torch': '2.5.2+cu121'}
        self.assertIsNotNone(refused(lambda: runner.arm_declaration(other)))
        # The sealer: the shipped pair (torch 2.5.1 against 2.5.1+cu121) seals; a real version
        # difference is refused by name, and the labelled package is not named.
        locked = {'torch': '2.5.1+cu121', 'transformers': '4.51.3'}

        def seal(requirements):
            with tempfile.TemporaryDirectory() as tmp:
                def archive(root, source, path):
                    Path(path).write_bytes(b'tree')
                    return 'd' * 40
                with patch.object(sealer, 'OUT', Path(tmp)), \
                        patch.object(sealer, 'gate_check_numbers', lambda source: [1, 2, 3]), \
                        patch.object(sealer, 'git', lambda *args: requirements.encode()), \
                        patch.object(sealer, 'bound_tree_archive', archive):
                    return sealer.gate_fields(dict(form='full', checks='all', known_red=[]), 'c' * 40, locked)
        block = seal('torch==2.5.1\ntransformers==4.51.3\n')
        self.assertEqual(block['requirements'], {'torch': '2.5.1', 'transformers': '4.51.3'})
        message = refused(lambda: seal('torch==2.5.1\ntransformers==4.52.3\n')) or ''
        self.assertIn('transformers==4.52.3', message)
        self.assertNotIn('torch', message)

    def test_check_zero_is_a_check_of_the_bound_gate(self):
        # The real gate's first check is number 0; a block listing it, choosing it or declaring it
        # known red is admitted. A negative number, a bool or a repeated number is still refused.
        self.assertEqual(runner.arm_declaration(gate_manifest(check_numbers=[0, 1, 2, 3])), 'G')
        self.assertEqual(runner.arm_declaration(gate_manifest(check_numbers=[0, 1, 2, 3], checks=[0, 2],
                                                              known_red=[0])), 'G')
        for bad in (gate_manifest(check_numbers=[-1, 1, 2, 3]), gate_manifest(check_numbers=[True, 2, 3]),
                    gate_manifest(check_numbers=[0, 0, 1]), gate_manifest(check_numbers=[0, 1, 2, 3], checks=[-1])):
            self.assertIsNotNone(refused(lambda: runner.arm_declaration(bad)), bad)

    def test_the_gate_command_is_the_laptops_with_the_sealed_flags(self):
        gate = gate_manifest()['gate']
        self.assertEqual(runner.gate_argv(gate), ['-u', '-X', 'utf8', 'scripts/verify_session1.py', '--results', '{results}'])
        self.assertEqual(runner.gate_argv(dict(gate, checks=[1, 3]))[-2:], ['--checks', '1,3'])
        side = runner.gate_argv(dict(gate, form='side'))
        self.assertEqual([a[3] for a in side], [argv[0] for _, argv in runner.SIDE_GATES])
        self.assertEqual(side[-1][-2:], ['--output-dir', '{evidence}/side/controller_out'])
        self.assertEqual(runner.argv_for(gate_manifest()), runner.gate_argv(gate))

    def test_the_gate_passes_only_when_every_check_outside_known_red_passes(self):
        gate = gate_manifest(known_red=[2])['gate']
        rows = lambda *statuses: [dict(number=n, status=s) for n, s in zip((1, 2, 3), statuses)]
        passed = runner.assess_gate(gate, rows('PASS', 'FAIL', 'SKIP'), True, 60)
        self.assertTrue(passed['execution_integrity_passed'], passed)
        self.assertEqual((passed['known_red_failed'], passed['now_green']), ([2], []))
        green = runner.assess_gate(gate, rows('PASS', 'PASS', 'WARN'), True, 60)
        self.assertEqual((green['execution_integrity_passed'], green['now_green']), (True, [2]))
        failed = runner.assess_gate(gate, rows('FAIL', 'FAIL', 'PASS'), True, 60)
        self.assertEqual((failed['execution_integrity_passed'], failed['failing']), (False, [1]))
        self.assertIn('gate_checks_not_run', runner.assess_gate(gate, rows('PASS', 'FAIL'), True, 60)['reasons'])
        self.assertIn('gate_not_ended', runner.assess_gate(gate, rows('PASS', 'FAIL', 'PASS'), False, 60)['reasons'])
        self.assertIn('gate_rows_unexpected',
                      runner.assess_gate(gate, rows('PASS', 'FAIL', 'PASS') + [dict(number=7, status='PASS')], True, 60)['reasons'])
        side = dict(gate, form='side')
        good = [dict(gate=name, exit=0) for name, _ in runner.SIDE_GATES]
        self.assertTrue(runner.assess_gate(side, good, True, 60)['execution_integrity_passed'])
        self.assertFalse(runner.assess_gate(side, good[:-1] + [dict(gate=good[-1]['gate'], exit=1)], True, 60)
                         ['execution_integrity_passed'])

    def gate_bundle(self, members):
        base = Path(tempfile.mkdtemp(dir=self.root))
        with tarfile.open(base / runner.GATE_SOURCE, 'w') as archive:
            for name, data in members.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        if not hasattr(self, 'trees'):
            self.trees = {}
        self.trees[base] = raw_tree_id(members, self.root)
        return base

    def test_the_runner_runs_the_sealed_gate_on_the_sealed_tree_in_a_clean_environment(self):
        base = self.gate_bundle({'scripts/verify_session1.py': FAKE_GATE.encode()})
        evidence = base / 'evidence'
        evidence.mkdir()
        with patch.dict(os.environ, {'SHIMMER_MODEL_MODE': 'final'}):
            code = runner.execute_gate(base, gate_manifest(known_red=[2], source_tree=self.trees[base]), evidence, time.time() + 120)
        result = read_json(evidence / 'result.json')
        rows = runner.gate_rows(evidence / 'gate' / 'results.jsonl')
        self.assertEqual((code, result['execution_integrity_passed'], result['counts']['FAIL']), (0, True, 1))
        self.assertEqual({r['title'] for r in rows}, {'clean'})
        self.assertTrue((evidence / 'gate' / 'verify.log').is_file())
        # Checks chosen at sealing are the only ones run.
        base = self.gate_bundle({'scripts/verify_session1.py': FAKE_GATE.encode()})
        (base / 'evidence').mkdir()
        runner.execute_gate(base, gate_manifest(checks=[1, 3], source_tree=self.trees[base]), base / 'evidence', time.time() + 120)
        self.assertEqual([r['number'] for r in runner.gate_rows(base / 'evidence' / 'gate' / 'results.jsonl')], [1, 3])
        # The side form runs each declared side gate once.
        stub = b'import sys; sys.exit(0)\n'
        base = self.gate_bundle({argv[0]: stub for _, argv in runner.SIDE_GATES})
        (base / 'evidence').mkdir()
        self.assertEqual(runner.execute_gate(base, gate_manifest(form='side', source_tree=self.trees[base]), base / 'evidence', time.time() + 120), 0)
        # A member leaving the tree is refused before anything runs.
        base = self.gate_bundle({'../outside.py': stub})
        self.assertIn('Gate source member refused', refused(lambda: runner.extract_gate_source(base / runner.GATE_SOURCE,
                                                                                                 base / 'gate_tree')) or '')

    def test_the_gate_tree_is_a_git_checkout_of_exactly_the_extracted_files(self):
        """The extracted tree is a git checkout with one commit of exactly its files, every byte kept
        whatever its own .gitattributes asks (a CRLF file under eol=lf, an expanded $Id$ under ident,
        a UTF-16 file under working-tree-encoding, a file its .gitignore ignores), its tree id the
        sealed one, its status clean, git's version and the commit in the gate evidence; the gate runs
        inside it. A commit whose tree is not the sealed tree is refused. -filter cannot be made
        load-bearing here: no filter driver can be configured with no global or system config."""
        import shutil
        if shutil.which('git') is None:
            self.skipTest('git is not installed here')
        members = {'scripts/verify_session1.py': GIT_GATE.encode(),
                   'docs/crlf.txt': b'one' + bytes([13, 10]) + b'two' + bytes([13, 10]),
                   'docs/ident.txt': b'$Id: ' + b'0123456789abcdef' * 2 + b'01234567 $' + bytes([10]),
                   'docs/utf16.txt': 'hi'.encode('utf-16'),
                   '.gitattributes': bytes([10]).join([b'* text=auto eol=lf', b'docs/ident.txt ident',
                                                       b'docs/utf16.txt working-tree-encoding=UTF-16', b'']),
                   '.gitignore': b'docs/' + bytes([10])}
        base = self.gate_bundle(members)
        evidence = base / 'evidence'
        evidence.mkdir()
        manifest = gate_manifest(checks=[1], check_numbers=[1], source_tree=self.trees[base])
        self.assertEqual(runner.execute_gate(base, manifest, evidence, time.time() + 120), 0)
        record = read_json(evidence / 'gate' / 'git_checkout.json')
        seen = json.loads(runner.gate_rows(evidence / 'gate' / 'results.jsonl')[0]['title'])
        self.assertEqual((record['files'], record['status_clean'], record['tree']), (6, True, self.trees[base]))
        self.assertTrue(record['git_version'].startswith('git version'))
        self.assertEqual((seen['head'], seen['status'], seen['crlf']), (record['commit'], '', True))
        for name, data in members.items():
            self.assertEqual((base / 'gate_tree' / name).read_bytes(), data, name)
        # A tree other than the sealed one is refused before the gate runs.
        base = self.gate_bundle(members)
        (base / 'evidence').mkdir()
        wrong = gate_manifest(checks=[1], check_numbers=[1], source_tree='0' * 40)
        message = refused(lambda: runner.execute_gate(base, wrong, base / 'evidence', time.time() + 120)) or ''
        self.assertIn("is not the bound commit's tree", message)
        self.assertFalse((base / 'evidence' / 'gate' / 'results.jsonl').exists())
        # The refusal's reason is in the gate evidence the controller collects.
        refusal = read_json(base / 'evidence' / 'gate' / 'refusal.json')
        self.assertEqual((refusal['refused'], refusal['message']), (True, message))
        # So is an extraction refusal (a member leaving the tree).
        base = self.gate_bundle({'../outside.py': b'x'})
        (base / 'evidence').mkdir()
        message = refused(lambda: runner.execute_gate(base, wrong, base / 'evidence', time.time() + 120)) or ''
        self.assertIn('Gate source member refused', message)
        self.assertEqual(read_json(base / 'evidence' / 'gate' / 'refusal.json')['message'], message)

    def test_the_sealer_archives_the_bound_tree_byte_for_byte(self):
        """The sealer's gate archive is the bound commit's blobs byte for byte, whatever the
        repository's autocrlf or the tree's eol attribute would write on a checkout, and the tree id
        it seals is the commit's own."""
        import shutil
        import subprocess
        if shutil.which('git') is None:
            self.skipTest('git is not installed here')
        repo = Path(tempfile.mkdtemp(dir=self.root))
        run = lambda *a: subprocess.run(['git', '-C', str(repo), *a], capture_output=True, check=True).stdout
        run('init', '-q')
        for key, value in (('user.name', 'fixture'), ('user.email', 'fixture@localhost'), ('core.autocrlf', 'true')):
            run('config', key, value)
        (repo / '.gitattributes').write_bytes(b'*.txt text eol=crlf' + bytes([10]))
        (repo / 'a.txt').write_bytes(b'one' + bytes([10]) + b'two' + bytes([10]))
        run('add', '-A')
        run('commit', '-q', '-m', 'fixture')
        archive = repo.parent / (repo.name + '.tar')
        tree = sealer.bound_tree_archive(repo, 'HEAD', archive)
        self.assertEqual(tree, run('rev-parse', 'HEAD^{tree}').decode().strip())
        with tarfile.open(archive) as stream:
            members = {m.name: stream.extractfile(m).read() for m in stream.getmembers() if m.isfile()}
        self.assertEqual(members, {'.gitattributes': run('cat-file', 'blob', 'HEAD:.gitattributes'),
                                   'a.txt': run('cat-file', 'blob', 'HEAD:a.txt')})
        self.assertNotIn(bytes([13]), members['a.txt'])

    def test_the_sealer_refuses_a_symlink_or_a_submodule_in_the_bound_tree(self):
        """A bound tree holding a symlink (120000) or a submodule (160000) is refused at sealing by
        name, before any archive is written; a tree of regular files is archived."""
        import shutil
        import subprocess
        if shutil.which('git') is None:
            self.skipTest('git is not installed here')
        for mode, label in (('120000', 'link'), ('160000', 'module')):
            repo = Path(tempfile.mkdtemp(dir=self.root))
            run = lambda *a, data=None: subprocess.run(['git', '-C', str(repo), *a], input=data, capture_output=True,
                                                       check=True).stdout
            run('init', '-q')
            for key, value in (('user.name', 'fixture'), ('user.email', 'fixture@localhost')):
                run('config', key, value)
            plain = run('hash-object', '-w', '--stdin', data=b'plain').decode().strip()
            run('update-index', '--add', '--cacheinfo', '100644,%s,plain.txt' % plain)
            target = plain if mode == '120000' else 'e' * 40
            run('update-index', '--add', '--cacheinfo', '%s,%s,%s' % (mode, target, label))
            tree = run('write-tree').decode().strip()
            commit = run('commit-tree', tree, '-m', 'fixture').decode().strip()
            archive = repo.parent / (repo.name + '.tar')
            message = refused(lambda: sealer.bound_tree_archive(repo, commit, archive)) or ''
            self.assertIn('The bound tree holds an entry the gate cannot carry: ' + label, message)
            self.assertFalse(archive.exists())
        self.assertTrue(sealer.gate_carries('100644', 'blob') and sealer.gate_carries('100755', 'blob'))

    def test_a_git_failure_in_the_gate_tree_is_a_one_line_refusal(self):
        """git missing (an OSError), a call past its time, a non-zero exit and a passed deadline each
        end the checkout in one refusal naming the call and the cause: the exception's type, or
        git's own error."""
        import subprocess
        tree = Path(tempfile.mkdtemp(dir=self.root))
        cases = [(lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError('git')), 'FileNotFoundError'),
                 (lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired(['git'], 1)), 'TimeoutExpired'),
                 (lambda *a, **k: subprocess.CompletedProcess(a[0], 128, '', 'fatal: not here' + chr(10) + 'more'),
                  'fatal: not here more')]
        for fake, cause in cases:
            with patch('subprocess.run', fake):
                message = refused(lambda: runner.gate_git(tree, {}, None, 'init')) or ''
            self.assertEqual(message, 'The gate tree could not be made a git checkout (git init: ' + cause + ')')
        message = refused(lambda: runner.gate_git(tree, {}, time.time() - 1, 'init')) or ''
        self.assertEqual(message, 'The gate tree could not be made a git checkout (git init: deadline passed)')
        with patch('subprocess.run', cases[0][0]):
            message = refused(lambda: runner.git_checkout(tree, {}, 'c' * 40)) or ''
        self.assertIn('could not be made a git checkout (git --version: FileNotFoundError)', message)

    def test_the_sealer_reads_the_hub_cache_huggingface_reads(self):
        """The sealer reads the models from HF_HUB_CACHE, else HF_HOME's hub, else the home default,
        so the gate's children (HF_HUB_CACHE the sealed cache) seal from the sealed models."""
        home = Path.home() / '.cache/huggingface/hub'
        self.assertEqual(sealer.model_cache({}), home)
        self.assertEqual(sealer.model_cache({'HF_HOME': '/h'}), Path('/h') / 'hub')
        self.assertEqual(sealer.model_cache({'HF_HOME': '/h', 'HF_HUB_CACHE': '/c'}), Path('/c'))
        self.assertEqual(sealer.model_cache({'HF_HOME': '/h', 'HUGGINGFACE_HUB_CACHE': '/o'}), Path('/o'))
        self.assertEqual(sealer.model_cache({'XDG_CACHE_HOME': '/x'}), Path('/x') / 'huggingface' / 'hub')
        self.assertEqual(sealer.model_cache({'XDG_CACHE_HOME': '/x', 'HF_HOME': '/h'}), Path('/h') / 'hub')
        with patch.dict(os.environ, runner.gate_environment(self.root)):
            self.assertEqual(sealer.model_cache(), self.root / 'hf_cache' / 'hub')

    def test_the_gate_writes_a_row_per_check_and_runs_only_the_chosen_checks(self):
        checks = [('1 one', lambda: ('PASS', 'a')), ('2 two', lambda: ('FAIL', 'b')), ('3 three', lambda: ('SKIP', 'c'))]
        path = Path(tempfile.mkdtemp(dir=self.root)) / 'results.jsonl'
        with patch.object(gate_module, 'CHECKS', checks), contextlib.redirect_stdout(io.StringIO()):
            code = gate_module.main(['--results', str(path), '--checks', '1,3'])
            unknown = gate_module.main(['--checks', '1,9'])
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual([(r['number'], r['status']) for r in rows], [(1, 'PASS'), (3, 'SKIP')])
        self.assertTrue(all(isinstance(r['seconds'], float) for r in rows))
        self.assertEqual((code, unknown), (0, 2))

    def test_the_sealer_reads_the_bound_gates_check_numbers(self):
        head = sealer.git(ROOT, 'rev-parse', 'HEAD').decode().strip()
        committed = sealer.git(ROOT, 'show', head + ':scripts/verify_session1.py').decode('utf-8')
        numbers = sealer.gate_check_numbers(head)
        self.assertEqual(len(numbers), committed[committed.index('\nCHECKS'):].count('\n    ("'))
        self.assertTrue(set(numbers) >= {21, 118, 324, 325})

    def test_the_report_names_the_gate_its_counts_and_its_minutes(self):
        manifest = gate_manifest(known_red=[2])
        result = runner.assess_gate(manifest['gate'], [dict(number=1, status='PASS'), dict(number=2, status='FAIL'),
                                                        dict(number=3, status='SKIP')], True, 600)
        text = analysis.gate_text(manifest, result)
        for part in ('PASS 1', 'FAIL 1', 'SKIP 1', 'known red [2], of them failing [2]', '10.0 minutes of gate'):
            self.assertIn(part, text)
        self.assertIn('no gate result collected', analysis.gate_text(manifest, None))

    def test_a_declared_type_order_admits_faster_types_and_drops_the_a10_limits(self):
        inventory = [inventory_entry('gpu_1x_a10', 1.29, 'A10 (24 GB PCIe)'),
                     inventory_entry('gpu_1x_h100_pcie', 3.29, 'H100 (80 GB PCIe)'),
                     inventory_entry('gpu_8x_a100', 14.32, 'A100 (40 GB SXM4)', count=8, regions=('us-west-1',))]
        # The A10-first rule keeps its order and its price limit.
        self.assertEqual([c['type'] for c in guard.instance_candidates(inventory, 1.29)], ['gpu_1x_a10'])
        # Each declared type with exactly its run's GPUs (D-382 item 4): the eight-GPU type only for
        # an eight-GPU run, refused beside a one-GPU one.
        self.assertIsNotNone(refused(lambda: guard.declared_candidates(inventory, ['gpu_1x_h100_pcie', 'gpu_8x_a100'])))
        declared = (guard.declared_candidates(inventory, ['gpu_1x_h100_pcie'])
                    + guard.declared_candidates(inventory, ['gpu_8x_a100'], gpus=8))
        self.assertEqual([(c['type'], c['gpu_count'], c['max_hourly_rate']) for c in declared],
                         [('gpu_1x_h100_pcie', 1, 3.29), ('gpu_8x_a100', 8, 14.32)])
        for types in (['gpu_1x_h200'], ['gpu_1x_a10', 'gpu_1x_a10'], []):
            self.assertIsNotNone(refused(lambda: guard.declared_candidates(inventory, types)), types)
        clock = SimpleNamespace(time=time.time, sleep=lambda s: self.fail('a declared order never polls'))
        listing = lambda rows: (lambda: rows)
        chosen = guard.select_instance(listing(inventory), declared, 1.29, clock, type_rule='declared')
        self.assertEqual((chosen[0]['type'], chosen[1], chosen[2], chosen[3]), ('gpu_1x_h100_pcie', 'us-east-1', 3.29, 1))
        gone = [inventory[0], dict(inventory[1], regions=[]), inventory[2]]
        self.assertEqual(guard.select_instance(listing(gone), declared, 1.29, clock, type_rule='declared')[:2],
                         (declared[1], 'us-west-1'))
        dearer = [inventory[0], inventory_entry('gpu_1x_h100_pcie', 4.0, 'H100 (80 GB PCIe)')]
        self.assertIn('No declared instance type offered',
                      refused(lambda: guard.select_instance(listing(dearer), declared[:1], 1.29, clock, type_rule='declared')) or '')
        # D-S79: by default the fastest offered type first, from the declared order; the A10 last.
        # D-S95: with exactly the GPUs the run needs, so the eight-GPU A100 is not offered to a
        # one-GPU run.
        offered = inventory + [inventory_entry('gpu_1x_a100', 1.99, 'A100 (40 GB PCIe)')]
        fastest = guard.fastest_candidates(offered, ['H100', 'GH200', 'A100', 'A10'])
        self.assertEqual([c['type'] for c in fastest], ['gpu_1x_h100_pcie', 'gpu_1x_a100', 'gpu_1x_a10'])
        self.assertEqual([c['type'] for c in guard.fastest_candidates([inventory[0]], ['H100', 'A10'])], ['gpu_1x_a10'])
        self.assertIsNotNone(refused(lambda: guard.fastest_candidates([inventory[0]], ['H100'])))
        shipped = json.loads(guard.GPU_SPEED_ORDER.read_text(encoding='utf-8'))
        self.assertEqual(guard.speed_order(shipped), ['B200', 'H100', 'GH200', 'A100', 'A10'])
        # The runner admits the GPU count its selected type declares, and no other.
        candidate = declared[1]
        torch = lambda count: SimpleNamespace(cuda=SimpleNamespace(
            device_count=lambda: count, get_device_properties=lambda i: SimpleNamespace(name='NVIDIA A100-SXM4-40GB'),
            mem_get_info=lambda i: (40 * 10**9, 40 * 10**9)))
        psutil = SimpleNamespace(virtual_memory=lambda: SimpleNamespace(total=200 * 2**30, available=190 * 2**30),
                                 cpu_count=lambda: 30)
        with patch.object(runner.shutil, 'disk_usage', lambda path: SimpleNamespace(free=10**13)):
            self.assertEqual(runner.hardware_admission(self.root, torch(8), psutil, candidate)['instance_type'], 'gpu_8x_a100')
            self.assertIn('GPU count', refused(lambda: runner.hardware_admission(self.root, torch(1), psutil, candidate)) or '')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


GATE_NEUTRALIZATIONS = [
    # The extracted tree left as a plain folder: no git checkout, no commit recorded.
    ('test_the_gate_tree_is_a_git_checkout_of_exactly_the_extracted_files', runner, 'git_checkout',
     lambda tree, env, source_tree, deadline=None: dict(git_version='', commit='', tree='', files=0, status_clean=False)),
    # The tree's own .gitattributes obeyed on the commit: line ends converted.
    ('test_the_gate_tree_is_a_git_checkout_of_exactly_the_extracted_files', runner, 'GATE_GIT_ATTRIBUTES', ''),
    # Its ident attribute obeyed: the expanded $Id$ collapsed in the blob.
    ('test_the_gate_tree_is_a_git_checkout_of_exactly_the_extracted_files', runner, 'GATE_GIT_ATTRIBUTES',
     '* -text -filter -working-tree-encoding\n'),
    # Its working-tree-encoding obeyed: the UTF-16 file stored as UTF-8.
    ('test_the_gate_tree_is_a_git_checkout_of_exactly_the_extracted_files', runner, 'GATE_GIT_ATTRIBUTES',
     '* -text -filter -ident\n'),
    # The refusal dropped: any commit admitted as the bound commit's tree.
    ('test_the_gate_tree_is_a_git_checkout_of_exactly_the_extracted_files', runner, 'checkout_holds',
     lambda committed, files, status, head_tree, source_tree: True),
    # A symlink or a submodule admitted into the gate archive.
    ('test_the_sealer_refuses_a_symlink_or_a_submodule_in_the_bound_tree', sealer, 'gate_carries',
     lambda mode, kind: True),
    # git's failures raised as they come, not refused in one line.
    ('test_a_git_failure_in_the_gate_tree_is_a_one_line_refusal', runner, 'gate_git', unguarded_git),
    # The sealer archiving through git archive again: the repository's eol written into the tree.
    ('test_the_sealer_archives_the_bound_tree_byte_for_byte', sealer, 'bound_tree_archive', archive_through_git),
    # The sealer reading the home folder's cache again, whatever the environment names.
    ('test_the_sealer_reads_the_hub_cache_huggingface_reads', sealer, 'model_cache',
     lambda environ=None: Path.home() / '.cache/huggingface/hub'),
    # The bound preflight drops the sealed type rule and applies the A10-first rule.
    ('test_the_bound_preflight_applies_the_sealed_declared_type_rule', __import__('ordinary_final_bound_preflight'),
     'sealed_type_rule', lambda manifest: 'a10_first'),
    # The sealed gate block not validated: any block admitted.
    ('test_an_arm_g_bundle_is_admitted_only_with_its_sealed_gate_block', runner, 'gate_declaration',
     lambda manifest: manifest.get('gate')),
    # A gate pin compared exactly again: the lock's local label (+cu121) no longer dropped.
    ('test_a_gate_pin_holds_against_the_lock_with_its_local_label_dropped', runner, 'pin_held',
     lambda locked, wanted: locked == wanted),
    # Check numbers read as positive only again: the gate's check 0 refused.
    ('test_check_zero_is_a_check_of_the_bound_gate', runner, '_numbers',
     lambda value: isinstance(value, list) and all(type(n) is int and n > 0 for n in value) and len(set(value)) == len(value)),
    # A gate command that drops the sealed results file.
    ('test_the_gate_command_is_the_laptops_with_the_sealed_flags', runner, 'gate_argv',
     lambda gate: ['-u', '-X', 'utf8', 'scripts/verify_session1.py']),
    # An assessment that reads every check as passed.
    ('test_the_gate_passes_only_when_every_check_outside_known_red_passes', runner, 'assess_gate',
     lambda gate, rows, ended, seconds: _REAL_ASSESS(gate, [dict(r, status='PASS', exit=0) for r in rows], True, seconds)),
    # The runner's own environment handed to the gate.
    ('test_the_runner_runs_the_sealed_gate_on_the_sealed_tree_in_a_clean_environment', runner, 'gate_environment',
     lambda base: dict(os.environ)),
    # A gate that cannot tell one check from another.
    ('test_the_gate_writes_a_row_per_check_and_runs_only_the_chosen_checks', gate_module, '_check_number',
     lambda title: 1),
    # The declared order read as the A10-first rule.
    ('test_a_declared_type_order_admits_faster_types_and_drops_the_a10_limits', guard, 'declared_candidates',
     lambda inventory, types: guard.instance_candidates(inventory, 1.29)),
    # The fastest-first default read as the A10-first rule.
    ('test_a_declared_type_order_admits_faster_types_and_drops_the_a10_limits', guard, 'fastest_candidates',
     lambda inventory, order, gpus=1: guard.instance_candidates(inventory, 1.29)),
    # D-382 item 1: a measured type ranked by the declared order, not by its measured factor.
    ('test_a_compared_run_leaves_the_a10_only_for_a_type_with_its_reference_pair', guard, 'measured_tiers',
     lambda candidates, spec, reference_run=False: [c for c in candidates if reference_run or c['type'] == guard.PREFERRED_TYPE
                                                    or c['type'] in (spec.get('measured') or {})]),
    # D-382 item 1: a measured entry admitted with no checked provenance.
    ('test_a_measured_entry_carries_its_reference_set_result_and_moved_no_score', factor_record_module,
     'check_measured', lambda spec, config=None: True),
    # D-401 item 1 (d): a comparison admits any type its launches run on.
    ('test_one_comparison_seals_one_machine_type_and_its_arms_ran_on_it', guard, 'claim_comparison',
     lambda name, machine, now_epoch, registry=None: dict(name=name, type=machine, first=True)),
    ('test_the_controller_claims_the_comparisons_type_under_the_lock', guard, 'claim_comparison',
     lambda name, machine, now_epoch, registry=None: dict(name=name, type=machine, first=True)),
    # D-401 item 1 (c): a compared arm sealed with no comparison named.
    ('test_one_comparison_seals_one_machine_type_and_its_arms_ran_on_it', sealer, 'comparison_declared',
     lambda arm, budget, reference_run: True),
    # D-401: the cloud reference's spend left out of the guard's count.
    ('test_the_guard_counts_the_cloud_reference_spend_and_waits_for_role_cs', guard, 'cloud_spend_refusal',
     lambda store: True),
    # D-382 item 2: a figure whose arms ran on different machine types admitted.
    ('test_one_comparison_seals_one_machine_type_and_its_arms_ran_on_it', factor_record_module, 'require_same_type',
     lambda folders: 'gpu_1x_a10'),
    # D-S96 item 2: an unmeasured faster type admitted for a compared run.
    ('test_a_compared_run_leaves_the_a10_only_for_a_type_with_its_reference_pair', guard, 'measured_tiers',
     lambda candidates, spec, reference_run=False: list(candidates)),
    # D-S95: more GPUs than the run needs admitted.
    ('test_the_fastest_route_takes_higher_tiers_by_measurement_with_the_gpus_the_run_needs', guard, 'gpus_needed_match',
     lambda entry, gpus: True),
]
