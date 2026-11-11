"""The asset copy on every launch (D-S107 items 1 and 5, D-403, D-421 F7) and the one shared salvage
folder (D-412 item 2): proofs on the controller checks' fakes, no provider and no network.

The tests live in AssetCopyChecks, mixed into ControllerChecks, and each rule is proven by neutralise,
fail, restore, pass through ASSET_COPY_NEUTRALIZATIONS.
"""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT / 'tools'), str(ROOT / 'tools' / 'loop')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import instance_reaper  # noqa: E402
import ordinary_final_cloud as controller  # noqa: E402
import ordinary_final_bound_preflight as bound_preflight  # noqa: E402
import prepare_ordinary_final_run as sealer  # noqa: E402
import declare_asset_copy  # noqa: E402
from ordinary_final_run import read, write  # noqa: E402

import loop_budget_guard as guard  # noqa: E402

REAL_STANDING_ORDERS_REFUSAL = guard.standing_orders_refusal
REAL_SPEND_STORE_PATH = guard.spend_store_path
LIVE_FILESYSTEM = dict(id='a' * 32, name='fixture-fs', region='us-east-1', bytes_used=12_903_487_114, is_in_use=False)


def history_lines():
    path = guard.spend_store_path().parent / controller.ASSET_COPY_HISTORY_NAME
    return [json.loads(l) for l in path.read_text(encoding='utf8').splitlines() if l.strip()] if path.is_file() else []


def orders_root(root, budget=500.0, hard_stop=499.0, spend=10.0, launch=False):
    """A main checkout's records, as standing orders 1 to 3 read them."""
    private = Path(root) / 'docs' / 'loop' / 'private'
    private.mkdir(parents=True, exist_ok=True)
    (private / 'budget_ledger.jsonl').write_text(json.dumps(dict(event='budget_change', time_utc='2026-11-09T14:00:00+00:00',
                                                                 budget_usd=budget, hard_stop_usd=hard_stop)) + chr(10),
                                                encoding='utf8')
    (private / 'reaper_status.json').write_text(json.dumps(dict(total_spend_usd=spend)), encoding='utf8')
    (private / 'cloud_reference_spend.jsonl').write_text('', encoding='utf8')
    (private / 'FOR_SECKIN.md').write_text('# For Seckin' + chr(10), encoding='utf8')
    (Path(root) / 'external').mkdir(exist_ok=True)
    if launch:
        folder = Path(root) / 'external' / 'run'
        folder.mkdir(parents=True)
        (folder / 'LAUNCH_INTENT.json').write_text(json.dumps(dict(epoch=1_794_000_000.0)), encoding='utf8')
    return Path(root)


def unassigned_names(source):
    """D-436 item 1: every name a module's code loads that nothing in the module assigns, defines or
    imports, and no builtin is: the shape of the NameError tiers-check found (a coarse check, all
    scopes together)."""
    import ast
    import builtins
    tree = ast.parse(source)

    def bound(node):
        names = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
                names.add(sub.id)
            elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(sub.name)
            elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                names.update((a.asname or a.name).split('.')[0] for a in sub.names)
            elif isinstance(sub, ast.arg):
                names.add(sub.arg)
            elif isinstance(sub, ast.ExceptHandler) and sub.name:
                names.add(sub.name)
            elif isinstance(sub, (ast.Global, ast.Nonlocal)):
                names.update(sub.names)
        return names

    known = bound(tree) | set(dir(builtins)) | {'__file__', '__name__', '__doc__'}
    return sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                   and n.id not in known})


def git_checkouts(root):
    """A fixture main checkout with one commit and a second worktree of it."""
    import subprocess
    main, other = Path(root) / 'main', Path(root) / 'worktree'
    main.mkdir()
    run = lambda *args, cwd=main: subprocess.run(['git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid',
                                                  *args], cwd=cwd, capture_output=True, text=True, check=True)
    run('init', '-q')
    (main / 'README.md').write_text('fixture', encoding='utf8')
    run('add', 'README.md')
    run('commit', '-q', '-m', 'fixture')
    run('worktree', 'add', '-q', str(other), '-b', 'fixture-lane')
    for folder in (main, other):
        (folder / 'docs' / 'loop' / 'private').mkdir(parents=True, exist_ok=True)
    return main.resolve(), other.resolve()


class AssetCopyChecks:
    def test_the_api_ceiling_is_its_own_with_reserves_in_order(self):
        """D-S121, D-441: the API's ceiling and warning are read from the store's latest ceiling line,
        never a constant (none refuses every paid run); a run is refused when closed spend, running
        caps, the reserves of runs ordered before it and its own worst case would pass the ceiling; a
        reserve holds until its run opens an intent or is recorded skipped; the warning flags at 50.
        The guard and the reaper add none of it to Lambda's 299."""
        import cloud_reference_spend as spend
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / 'cloud_reference_spend.jsonl'
            store.write_text(json.dumps(dict(run_id='old', event='close', spent_usd=7.07)) + chr(10), encoding='utf8')
            self.assertIn('no API ceiling line', spend.api_room(store, 'gate', 1.0)['reason'])
            lines = [dict(event='ceiling', time_utc='2026-11-09T19:00:00+00:00', ceiling_usd=60.0, warning_usd=50.0),
                     dict(event='reserve', kind='gate', order=1, worst_case_usd=20.0),
                     dict(event='reserve', kind='pubhealth', order=2, worst_case_usd=15.0),
                     dict(event='reserve', kind='causal', order=3, worst_case_usd=30.0)]
            with store.open('a', encoding='utf8') as handle:
                handle.write(''.join(json.dumps(l) + chr(10) for l in lines))
            self.assertTrue(spend.api_room(store, 'gate', 20.0)['ok'])
            self.assertEqual(spend.api_room(store, 'pubhealth', 15.0)['reserved_before_usd'], 20.0)
            causal = spend.api_room(store, 'causal', 30.0)
            self.assertFalse(causal['ok'])     # 7.07 + 20 + 15 + 30 > 60
            self.assertIn('would pass the API ceiling 60.00', causal['reason'])
            with store.open('a', encoding='utf8') as handle:
                handle.write(json.dumps(dict(event='skipped', kind='pubhealth')) + chr(10))
            self.assertEqual(spend.api_room(store, 'causal', 30.0)['reserved_before_usd'], 20.0)
            self.assertTrue(spend.api_room(store, 'causal', 30.0)['ok'])      # 7.07 + 20 + 30 <= 60 once skipped
            self.assertFalse(spend.api_room(store, 'causal', 35.0)['ok'])
            self.assertTrue(spend.api_room(store, 'causal', 25.0)['warn'])
            with store.open('a', encoding='utf8') as handle:
                handle.write(json.dumps(dict(event='ceiling', time_utc='2026-11-09T21:00:00+00:00', ceiling_usd=80.0,
                                             warning_usd=70.0)) + chr(10))
            self.assertTrue(spend.api_room(store, 'causal', 35.0)['ok'])     # the latest ceiling line decides
            self.assertEqual(spend.state(store)['spent_usd'], 7.07)          # ceiling and reserve lines are no spend
            bad = Path(tmp) / 'bad.jsonl'
            bad.write_text(json.dumps(dict(event='ceiling', time_utc='x', ceiling_usd=60.0, warning_usd=70.0)) + chr(10),
                           encoding='utf8')
            with self.assertRaises(spend.SpendStoreError):
                spend.api_room(bad, 'gate', 1.0)

    def test_a_budget_line_may_carry_the_lambda_warning(self):
        """D-S121: a budget_change line may carry warning_usd (270); the reaper reads it with its
        budget figures, the guard's decision carries it and says when the launch would reach it, and
        the reaper's status names it."""
        lines = [dict(event='budget_open', time_utc='2026-10-27T03:00:00+00:00', budget_usd=200.0, hard_stop_usd=199.0),
                 dict(event='budget_change', time_utc='2026-11-09T19:00:00+00:00', budget_usd=300.0, hard_stop_usd=299.0,
                      warning_usd=270.0)]
        self.assertEqual(instance_reaper.budget_figures(lines), (300.0, 299.0))
        self.assertEqual(instance_reaper.warning_figure(lines), 270.0)
        self.assertIsNone(instance_reaper.warning_figure(lines[:1]))
        self.assertIn('warning_usd', instance_reaper.BUDGET_LINE_FIELDS)
        ledger = Path(self.root) / 'warn' / 'ledger.jsonl'
        ledger.parent.mkdir()
        ledger.write_text(''.join(json.dumps(l) + chr(10) for l in lines)
                          + json.dumps(dict(event='launch', instance_id='a' * 32, instance_name='shimmer-loop-old',
                                            price_usd_per_hour=1.29, launch_requested_utc='2026-11-09T19:00:00+00:00'))
                          + chr(10) + json.dumps(dict(event='termination', instance_id='a' * 32,
                                                      instance_name='shimmer-loop-old', actual_cost=269.0)) + chr(10),
                          encoding='utf8')
        decision = guard.check(ledgers=[ledger], forecast_minutes=60, hourly_rate=1.29, storage_forecast_usd=3.9,
                               now_epoch=1_794_300_000.0, reserve_minutes=15, reaped=[])
        self.assertEqual((decision['warning_usd'], decision['warning_reached']), (270.0, True))

    def test_the_guard_loads_no_name_it_never_assigns(self):
        """D-436 item 1: an AST check over the guard, the reaper, the controller and the spend reader:
        no code loads a name that no scope assigns. The 4cdceafe shape (a function using a constant
        that was removed) is caught."""
        for path in ('tools/loop_budget_guard.py', 'tools/loop/instance_reaper.py', 'tools/ordinary_final_cloud.py',
                     'tools/loop/cloud_reference_spend.py', 'tools/ordinary_final_bound_preflight.py'):
            with self.subTest(path=path):
                self.assertEqual(unassigned_names((ROOT / path).read_text(encoding='utf8')), [])
        self.assertEqual(unassigned_names("def spend_store_path():" + chr(10) + "    return SPEND_STORE_NAME" + chr(10)),
                         ['SPEND_STORE_NAME'])

    def test_every_tool_finds_the_main_checkout_from_a_worktree(self):
        """D-436 items 1 and 2, D-412 item 2, the lead's two-checkout proof: from a fixture worktree, the
        real spend_store_path, the comparison registry, the asset copy history and the salvage folder all
        resolve to the fixture MAIN checkout's private folder; a reaper in the main checkout writes a
        salvage request that a controller launched from the worktree reads, and refuses its next phase."""
        import cloud_reference_spend
        with tempfile.TemporaryDirectory() as tmp:
            main, other = git_checkouts(tmp)
            private = main / 'docs' / 'loop' / 'private'
            (private / 'cloud_reference_spend.jsonl').write_text('', encoding='utf8')
            with patch.object(guard, 'spend_store_path', REAL_SPEND_STORE_PATH), patch.object(guard, 'ROOT', other):
                self.assertEqual(guard.spend_store_path(), private / 'cloud_reference_spend.jsonl')
                self.assertEqual(guard.comparison_registry(), private / 'comparisons.jsonl')
                self.assertEqual(guard.spend_store_path().parent / controller.ASSET_COPY_HISTORY_NAME,
                                 private / 'asset_copy_history.jsonl')
            instance_reaper._RESOLVED.clear()
            self.addCleanup(instance_reaper._RESOLVED.clear)
            with patch.object(instance_reaper, 'SALVAGE_DIR', None), patch.object(instance_reaper, 'ROOT', main):
                self.assertEqual(instance_reaper.salvage_dir(), private / 'salvage')
                instance_reaper._write_json(instance_reaper.request_path('shimmer-loop-fixture'),
                                            dict(episode='fixture', trigger='usage', requested_utc='2026-11-09T20:00:00+00:00'))
            with patch.object(instance_reaper, 'SALVAGE_DIR', None), patch.object(instance_reaper, 'ROOT', other):
                self.assertEqual(instance_reaper.salvage_dir(), private / 'salvage')
                transport, console, failure = self.execute()
            self.assertEqual(failure['message'], 'Salvage requested: no new phase is started')
            self.assertEqual(transport.started.count('ordinary_workload'), 0)
            self.assertTrue(cloud_reference_spend.STORE_NAME)

    def test_the_salvage_folder_resolves_once_and_a_git_failure_is_no_request(self):
        """D-436 item 4: the main checkout is found once per process for each checkout, and a salvage
        folder git cannot find reads as no request in the controller's poll, never a crash."""
        import cloud_reference_spend
        calls = []
        instance_reaper._RESOLVED.clear()
        self.addCleanup(instance_reaper._RESOLVED.clear)
        with tempfile.TemporaryDirectory() as tmp, patch.object(instance_reaper, 'SALVAGE_DIR', None), \
                patch.object(cloud_reference_spend, 'store_path',
                             lambda root: calls.append(root) or Path(tmp) / 'private' / 'cloud_reference_spend.jsonl'):
            first, second = instance_reaper.salvage_dir(), instance_reaper.salvage_dir()
            self.assertEqual((first, second, len(calls)), (Path(tmp) / 'private' / 'salvage',) * 2 + (1,))
        instance_reaper._RESOLVED.clear()

        def broken(root):
            raise cloud_reference_spend.SpendStoreError('The main checkout cannot be found from git')
        with patch.object(instance_reaper, 'SALVAGE_DIR', None), patch.object(cloud_reference_spend, 'store_path', broken):
            self.assertIsNone(instance_reaper.salvage_request('shimmer-loop-x'))

    def test_the_guard_finds_the_one_spend_store_and_main_checkout(self):
        """D-401, F1, read for real (no patch): the guard's spend store is the main checkout's
        docs/loop/private/cloud_reference_spend.jsonl by the store's own path rule, and the standing
        orders read that checkout."""
        import cloud_reference_spend
        with patch.object(guard, 'spend_store_path', REAL_SPEND_STORE_PATH):
            store = guard.spend_store_path()
            self.assertEqual(store, cloud_reference_spend.store_path(guard.ROOT))
            self.assertEqual(store.parts[-4:], ('docs', 'loop', 'private', 'cloud_reference_spend.jsonl'))
            self.assertEqual(guard.standing_orders_root(), store.parents[3])

    def test_a_launch_waits_for_standing_orders_one_to_three(self):
        """F1 (D-421, D-430): through the real guard path (check with the reaper's own ledgers), a
        launch is refused while standing order 1, 2 or 3 is broken or unable to check, read by
        `launch_refusals` as a state word: a checker returning 'broken', a non-empty string, refuses
        (a truthiness test would pass it); with the three kept the guard goes on to its other rules."""
        import standing_orders_check as orders
        kept = lambda ctx: ('kept', 'fixture')
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(guard, 'standing_orders_refusal', REAL_STANDING_ORDERS_REFUSAL), \
                patch.object(guard, 'standing_orders_root', lambda: Path(tmp)), \
                patch.dict(orders.CHECKERS, {2: ('API key', kept), 3: ('Budget', kept)}):
            decide = lambda: guard.check(ledgers=[self.ledger], forecast_minutes=60, hourly_rate=1.29,
                                         storage_forecast_usd=3.9, now_epoch=1_000_000.0, reserve_minutes=15)
            for state in ('broken', 'unable'):
                with self.subTest(state=state), patch.dict(orders.CHECKERS, {1: ('image', lambda ctx: (state, 'fixture'))}), \
                        self.assertRaisesRegex(guard.GuardRefusal, 'order 1 %s: fixture' % state):
                    decide()
            with patch.dict(orders.CHECKERS, {1: ('image', kept)}):
                try:
                    decide()
                except guard.GuardRefusal as other:   # any later rule may refuse; never the standing orders
                    self.assertNotIn('standing order', str(other))
    def plan(self, **changes):
        import ordinary_final_controller_checks as checks
        return checks.fixture_plan(self.ledger, **changes)

    def test_a_us_east_launch_needs_the_asset_copy_or_a_reason(self):
        """D-S107 item 1, D-421 (F7): a us-east-1 loop launch without the declaration is refused unless
        its bundle records a reason that holds (a sealed run's reason on an exposed bundle does not),
        before any key or instance; with the declaration and a MATCH it launches; an upload in the
        forecast needs a checked reason: the seed of a missing digest holds once, and is refused once
        the history shows that digest seeded."""
        with self.assertRaisesRegex(RuntimeError, 'carries the asset copy declaration'):
            self.execute(require_copy=True, plan=self.plan(forecast_includes_upload=False))
        write(self.base / controller.ASSET_COPY_ABSENCE, dict(reason='sealed run'))
        with self.assertRaisesRegex(RuntimeError, 'carries the asset copy declaration'):
            self.execute(require_copy=True, plan=self.plan(forecast_includes_upload=False))
        import ordinary_final_controller_checks as checks
        self.assertEqual((checks.FakeProvider.state or {}).get('launches', 0), 0)
        self.setUp()
        self.declare_copy()
        digest = self.assets_digest()
        with self.assertRaisesRegex(RuntimeError, 'needs a reason'):
            self.execute(require_copy=True, plan=self.plan())
        self.setUp()
        self.declare_copy()
        transport, console, failure = self.execute(require_copy=True, mount=dict(present=True, files={}),
                                                   plan=self.plan(upload_reason='seed of a missing digest'))
        self.assertIsNone(failure, failure)
        self.assertEqual(self.copy_receipt()['upload_reason'], 'seed of a missing digest')
        self.assertEqual([l['new_digest'] for l in history_lines()], [digest])
        kept = history_lines()
        self.setUp()
        path = guard.spend_store_path().parent / controller.ASSET_COPY_HISTORY_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(l) + chr(10) for l in kept), encoding='utf8')
        self.declare_copy()
        with self.assertRaisesRegex(RuntimeError, 'does not hold for this launch: seed of a missing digest'):
            self.execute(require_copy=True, plan=self.plan(upload_reason='seed of a missing digest'))
        self.setUp()
        self.declare_copy()
        transport, console, failure = self.execute(require_copy=True, mount=dict(present=True, files={digest: digest}),
                                                   plan=self.plan(forecast_includes_upload=False))
        self.assertIsNone(failure, failure)
        self.assertTrue(self.copy_receipt()['used'])

    def test_the_bound_preflight_refuses_an_undeclared_us_east_bundle(self):
        """D-421 (F7): the bound preflight refuses an undeclared us-east-1 bundle before the launch, and
        passes it once the declaration is there."""
        from ordinary_final_run import sha
        write(self.base / 'authorization_binding.json', dict(manifest_sha256=sha(self.base / 'execution_manifest.json')))
        manifest = read(self.base / 'execution_manifest.json')
        import ordinary_final_controller_checks as checks

        class Provider:
            def __init__(self, credential):
                pass

            def request(self, endpoint, body=None):
                return {'data': {'instances': [], 'instance-types': [checks.A10_TYPE], 'images': [manifest['image']]}[endpoint]}
        with patch.object(bound_preflight, 'LambdaExperiment', Provider), \
                patch.object(bound_preflight, 'credential_path', lambda: 'fixture-credential-path'), \
                patch('sys.stdout'):
            with self.assertRaisesRegex(RuntimeError, 'carries the asset copy declaration'):
                bound_preflight.main(self.base)
            self.declare_copy()
            bound_preflight.main(self.base)
        self.assertTrue(read(self.base / 'authorized_live_preflight.json')['passed'])

    def test_the_sealer_declares_the_asset_copy_on_every_bundle(self):
        """D-S107 item 1: the sealer writes the declaration, from the bundle's own digest, on the loop's
        filesystem; a sealed run records `sealed run` instead, a bundle for another region `another
        region`, and no other reason is accepted."""
        with tempfile.TemporaryDirectory() as tmp:
            for name, sealed, reason in (('exposed', False, None), ('sealed', True, None), ('west', False, 'another region')):
                out = Path(tmp) / name
                out.mkdir()
                write(out / 'execution_manifest.json', dict(assets_archive=dict(sha256='c' * 64, bytes=10)))
                result = sealer.asset_copy_for_bundle(out, sealed, reason)
                if name == 'exposed':
                    declaration = read(out / 'asset_copy_declaration.json')
                    self.assertEqual((declaration['filesystem_name'], declaration['mount'], declaration['assets_sha256']),
                                     (declare_asset_copy.LOOP_FILESYSTEM_NAME, declare_asset_copy.LOOP_MOUNT, 'c' * 64))
                    self.assertTrue(result['declared'])
                else:
                    self.assertFalse((out / 'asset_copy_declaration.json').exists())
                    self.assertEqual(read(out / controller.ASSET_COPY_ABSENCE)['reason'],
                                     'sealed run' if sealed else 'another region')
            out = Path(tmp) / 'bad'
            out.mkdir()
            write(out / 'execution_manifest.json', dict(assets_archive=dict(sha256='c' * 64, bytes=10)))
            with self.assertRaises(RuntimeError):
                sealer.asset_copy_for_bundle(out, False, 'faster this way')

    def test_a_missing_copy_is_seeded_with_its_history_and_room_read_as_the_live_inventory(self):
        """D-S107 item 5, D-403: a MISSING copy on a filesystem whose inventory has no capacity field (the
        live response, D-306) has room and is seeded after integrity; the receipt and
        asset_copy_history.jsonl record the old digest the filesystem held, the new one and the launch."""
        self.declare_copy()
        FakeProvider_filesystems = [LIVE_FILESYSTEM]
        import ordinary_final_controller_checks as checks
        checks.FakeProvider.filesystems = FakeProvider_filesystems
        old = 'b' * 64
        transport, console, failure = self.execute(mount=dict(present=True, files={old: old}))
        self.assertIsNone(failure, failure)
        receipt = self.copy_receipt()
        self.assertEqual((receipt['state'], receipt['seeded'], receipt['old_digests']), ('MISSING', True, [old]))
        self.assertEqual(receipt['room']['basis'], 'no capacity field: no quota (D-306)')
        lines = history_lines()
        self.assertEqual([(l['old_digests'], l['new_digest'], l['launch']) for l in lines],
                         [([old], self.assets_digest(), lines[0]['launch'])])
        self.assertTrue(lines[0]['launch'].startswith('shimmer-loop-'))
        started = transport.started
        self.assertLess(started.index('archive_integrity'), started.index('asset_copy_seed'))

    def test_a_probe_past_its_deadline_falls_back_to_the_upload(self):
        """D-421 (F7): a probe that runs past its deadline is recorded as PROBE_TIMEOUT and the archive
        is uploaded as before; the run is not failed."""
        self.declare_copy()
        transport, console, failure = self.execute(polls={'asset_copy_probe': ['RUNNING'] * 200},
                                                   mount=dict(present=True, files={}))
        self.assertIsNone(failure, failure)
        self.assertEqual(self.copy_receipt()['state'], 'PROBE_TIMEOUT')
        self.assertTrue(self.scp_assets_argv(transport))
        self.assertIn('ordinary_workload', transport.started)

    def test_the_salvage_folder_is_the_main_checkouts_for_every_tool(self):
        """D-412 item 2: with none set, the salvage folder is the main checkout's
        docs/loop/private/salvage, found through git's common directory by the spend store's path rule,
        whatever checkout the reaper, the controller or the hook runs from."""
        import cloud_reference_spend
        instance_reaper._RESOLVED.clear()   # resolved once per process: start from none
        self.addCleanup(instance_reaper._RESOLVED.clear)
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / 'main' / 'docs' / 'loop' / 'private' / 'cloud_reference_spend.jsonl'
            with patch.object(instance_reaper, 'SALVAGE_DIR', None), \
                    patch.object(cloud_reference_spend, 'store_path', lambda root: store):
                self.assertEqual(instance_reaper.salvage_dir(), store.parent / 'salvage')
                self.assertEqual(instance_reaper.request_path('shimmer-loop-x'),
                                 store.parent / 'salvage' / 'requests' / 'shimmer-loop-x.request.json')


ASSET_COPY_NEUTRALIZATIONS = [
    # D-S121, D-441: a run admitted whatever the API ceiling and the reserves say.
    ('test_the_api_ceiling_is_its_own_with_reserves_in_order', __import__('cloud_reference_spend'), 'reserved_before',
     lambda store, kind: 0.0),
    # D-S121: the Lambda warning on a budget line ignored.
    ('test_a_budget_line_may_carry_the_lambda_warning', instance_reaper, 'warning_figure', lambda rows: None),
    # D-436 item 1: an AST check that reports nothing.
    ('test_the_guard_loads_no_name_it_never_assigns', sys.modules[__name__], 'unassigned_names', lambda source: []),
    # D-436 item 2, D-412 item 2: each checkout its own private folder.
    ('test_every_tool_finds_the_main_checkout_from_a_worktree', instance_reaper, 'main_private',
     lambda: instance_reaper.ROOT / 'docs' / 'loop' / 'private'),
    # D-436 item 4: the main checkout found again on every call.
    ('test_the_salvage_folder_resolves_once_and_a_git_failure_is_no_request', instance_reaper, 'main_private',
     lambda: __import__('cloud_reference_spend').store_path(instance_reaper.ROOT).parent),

    # F1: a launch not held to standing orders 1 to 3.
    ('test_a_launch_waits_for_standing_orders_one_to_three', guard, 'standing_orders_failures', lambda root: []),
    # D-S107 item 1: an undeclared us-east-1 launch admitted with no reason.
    ('test_a_us_east_launch_needs_the_asset_copy_or_a_reason', controller, 'require_asset_copy_or_reason',
     lambda copy, region, base, sealed: None),
    ('test_the_bound_preflight_refuses_an_undeclared_us_east_bundle', controller, 'require_asset_copy_or_reason',
     lambda copy, region, base, sealed: None),
    # D-421: an upload in the forecast admitted with any or no reason.
    ('test_a_us_east_launch_needs_the_asset_copy_or_a_reason', controller, 'upload_reason_admitted',
     lambda plan, copy, region, sealed, digest: None),
    # D-S107 item 1: the sealer writes no declaration.
    ('test_the_sealer_declares_the_asset_copy_on_every_bundle', sealer, 'asset_copy_for_bundle',
     lambda out, sealed, reason=None: dict(declared=False)),
    # D-S107 item 5: a seed with no history line.
    ('test_a_missing_copy_is_seeded_with_its_history_and_room_read_as_the_live_inventory', controller,
     'record_asset_copy_history', lambda *args, **kwargs: {}),
    # D-403: no capacity field read as no room.
    ('test_a_missing_copy_is_seeded_with_its_history_and_room_read_as_the_live_inventory', controller, 'asset_copy_room',
     lambda provider, name, needed: dict(enough=False, reason='free space not readable')),
    # D-421: a probe timeout fails the run.
    ('test_a_probe_past_its_deadline_falls_back_to_the_upload', controller, 'probe_timed_out', lambda exc: False),
    # D-412 item 2: each checkout its own salvage folder.
    ('test_the_salvage_folder_is_the_main_checkouts_for_every_tool', instance_reaper, 'salvage_dir',
     lambda: instance_reaper.PRIVATE / 'salvage'),
]
