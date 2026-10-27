"""R2 (loop stage S2): a declared multi-round Review, end to end, mocked.

One chain, each link the project's own code, no model, provider, network or pipeline run:

1. the sealer's own prepare() seals a workload that carries a live case manifest; the
   heavy collaborators (git, the frozen adapters, the model cache, the wheels and the
   13 GB asset archive) are replaced by small stand-ins, everything that decides the
   workload (the case manifest validation, the flags, the support files, the budget, the
   seal) runs as written;
2. the instance-side seal check (ordinary_final_run.verify, on the project extracted as
   the instance extracts it) admits the bundle;
3. the real controller (ordinary_final_cloud.execute) launches it against the fake
   provider, transport and clock of tools/ordinary_final_controller_checks.py, writes a
   multi-round authorization, and the instance-side authorization check accepts it;
4. scripts/pipeline.py main()'s own statements up to the first run side effect (argument
   parsing, the final-mode admission and the multi-round request validation) run on the
   flags the runner builds, under the sealed environment (SHIMMER_MODEL_MODE=final). The
   statements are read from the source with ast and executed, so the pipeline module is
   never imported (it would load the whole runtime): no phase, no model. Draft, the flag
   alone and the manifest alone stay refused by the final-mode block itself;
5. the runner's assessment passes a multi-round run only when the saved case record,
   read back through multi_round.read_saved, shows outcome `reviewed` and activation
   `activated` (D-011 choice 11).

Every key assertion is proven by neutralise, fail, restore, pass (scripts/effect_proof.py).
"""
import argparse
import ast
import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT / 'scripts'), str(ROOT / 'tools')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import ordinary_final_controller_checks as cc  # the controller gate's fakes
import ordinary_final_cloud as controller
import ordinary_final_run as runner
import prepare_ordinary_final_run as sealer
import agent_activation
import decoding_policy
import final_models
import localization
import multi_round as mr
from effect_proof import prove_effect
from ordinary_final_run import read, sha, write
from reference_builder import ReferenceIndex
from run_context import for_run_dir

PIPELINE = ROOT / 'scripts' / 'pipeline.py'
# main()'s first statement with a run side effect; everything before it is parsing,
# the final-mode admission and the multi-round request validation.
FIRST_SIDE_EFFECT = 'args.backend_profile = apply_backend_profile(args.backend_profile)'
FINAL_MODE_TEST = "final_models.mode() == 'final'"
FINAL_MODE_REFUSAL = 'Frozen final models are limited to Review'
# The runtime files the stand-in source carries: the pipeline the seal reads the
# INST_FINDER switch from, the constitution it is evaluated against, and the files the
# sealer requires by name.
RUNTIME_SAMPLE = ('scripts/pipeline.py', 'scripts/multi_round.py', 'scripts/decoding_policy.py',
                  'config/constitution.json', 'config/compact_extraction_prompt.json')
DOCS = {'round_one': '# Round one\n\nThe first statement of the case.\n',
        'round_two': '# Round two\n\nThe second statement of the case.\n'}
CONVENTIONS = '# Conventions\n\n## Named sources [severity: low]\nEvery statement names its source.\n'


def live_case(**changes):
    """A live case manifest (schema 1, the live field set, fixture false) whose one source
    span is measured on the bundled round-one text."""
    quote = 'first statement'
    start = DOCS['round_one'].index(quote)
    value = dict(schema_version=1, case_id='launch-case', fixture=False, decision_support_mode='trajectory_only',
                 allow_recommendations=False,
                 rounds=[dict(round_id='r1', sequence=1, document_ids=['round_one']),
                         dict(round_id='r2', sequence=2, document_ids=['round_two'])],
                 actors=[dict(actor_id='actor_a')], issues=[dict(issue_id='issue_a')],
                 sources=[dict(source_id='s1', round_id='r1', actor_id='actor_a', issue_id='issue_a',
                               document_id='round_one', unit_id='u01', char_start=start, char_end=start + len(quote),
                               quote=quote, state='accepted')])
    value.update(changes)
    return value


def write_workload(folder, case):
    """A test folder as the sealer reads one: context/, conventions/, the targets file
    and the case manifest."""
    for name, text in DOCS.items():
        (folder / 'context').mkdir(parents=True, exist_ok=True)
        (folder / 'context' / (name + '.md')).write_text(text, encoding='utf-8', newline='\n')
    (folder / 'conventions').mkdir(parents=True, exist_ok=True)
    (folder / 'conventions' / 'review_conventions.md').write_text(CONVENTIONS, encoding='utf-8', newline='\n')
    write(folder / '_review_targets.json', dict(source='operator', targets=[n + '.md' for n in DOCS], grounding=[], prior=[]))
    write(folder / runner.CASE_MANIFEST, case)


@contextlib.contextmanager
def sealing_stand_ins():
    """Only the heavy collaborators of prepare() are replaced; its own logic runs."""
    real_read = sealer.read

    def read_without_the_model_cache(path):
        # tools/cloud_run/models.json names the multi-gigabyte model snapshots; none is bound here.
        return {} if Path(path).as_posix().endswith('tools/cloud_run/models.json') else real_read(path)

    def source_sample(source, extra=()):
        names = RUNTIME_SAMPLE + (decoding_policy.DECLARATION,) + tuple(extra)
        return {n: (ROOT / n).read_bytes().replace(b'\r\n', b'\n') for n in names}

    def small_assets(target, models, wheels, cache, wheelhouse):
        Path(target).write_bytes(b'asset archive stand-in')
        return dict(filename=Path(target).name, sha256=sha(target), bytes=Path(target).stat().st_size, members={})

    environment = {k: v for k, v in os.environ.items() if k != 'SHIMMER_INST_FINDER'}
    with patch.object(sealer, 'OUT', sealer.OUT), \
            patch.object(sealer, 'git', lambda root, *args: ('f' * 40 + '\n').encode()), \
            patch.object(sealer, 'runtime_source', source_sample), \
            patch.object(sealer, 'read', read_without_the_model_cache), \
            patch.object(sealer, 'pins', lambda path: {}), \
            patch.object(sealer, 'validate_wheels', lambda directory, locked: {}), \
            patch.object(sealer, 'build_assets', small_assets), \
            patch.object(final_models, 'verify', lambda role, root=None: (None, {})), \
            patch.dict(os.environ, environment, clear=True), \
            contextlib.redirect_stdout(io.StringIO()):
        yield


def prepare_bundle(root, case):
    """Seal a multi-round workload with the sealer's own prepare(); returns (bundle, ledger)."""
    root = Path(root)
    write_workload(root / 'workload', case)
    inputs = root / 'inputs'
    inputs.mkdir()
    (inputs / 'runtime.candidate.lock').write_text('', encoding='utf-8')
    write(inputs / 'provider_inventory.json', dict(instances=[], instance_types=[cc.A10_TYPE], images=[dict(cc.IMAGE)],
                                                   observed_at='fixture'))
    ledger = root / 'ledger' / 'budget_ledger.jsonl'
    cc.open_ledger(ledger)
    bundle = root / 'bundle'
    with sealing_stand_ins():
        # reaped=[ledger]: the guard reads only this fixture ledger, never the loop's real ones.
        sealer.prepare(bundle, budget=dict(ledgers=[ledger], forecast_minutes=cc.FORECAST_MINUTES,
                                           storage_forecast_usd=cc.STORAGE_USD, reaped=[ledger]),
                       workload=root / 'workload', inputs_from=inputs, now_epoch=cc.FakeClock().now)
    return bundle, ledger


def instance_verify(bundle):
    """The instance-side seal check on the project extracted as the instance extracts it."""
    project = bundle / 'project'
    if not project.exists():
        project.mkdir()
        with tarfile.open(bundle / 'project.tar.gz') as archive:
            for member in archive.getmembers():
                target = project / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
    return runner.verify(bundle)


def runner_argv(bundle, manifest):
    """The flags the runner hands to pipeline.main: runner.execute's own statements, from
    `argv = list(argv_for(manifest))` to the --output-dir append, read from its source."""
    tree = ast.parse(Path(runner.__file__).read_text(encoding='utf-8'))
    execute = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
    first = next(i for i, s in enumerate(execute.body) if ast.unparse(s) == 'argv = list(argv_for(manifest))')
    last = next(i for i, s in enumerate(execute.body) if i > first and isinstance(s, ast.AugAssign)
                and ast.unparse(s.target) == 'argv')
    scope = dict(argv_for=runner.argv_for, manifest=manifest, base=bundle, CASE_MANIFEST=runner.CASE_MANIFEST,
                 evidence=bundle / 'evidence')
    exec(compile(ast.Module(body=execute.body[first:last + 1], type_ignores=[]), 'runner_argv', 'exec'), scope)
    return scope['argv']


class Refused(Exception):
    pass


def pipeline_admission(argv, environment, final_test=None):
    """Execute main()'s own statements before its first side effect: the real parser, the
    final-mode block and the multi-round validation. Returns ('admitted', details) or
    ('refused', the parser's message). `final_test` replaces the final-mode refusal test
    (a neutralisation)."""
    tree = ast.parse(PIPELINE.read_text(encoding='utf-8'))
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    main = functions['main']
    stop = next(i for i, s in enumerate(main.body) if ast.unparse(s) == FIRST_SIDE_EFFECT)
    prefix = copy.deepcopy(main.body[:stop])
    if final_test is not None:
        block = next(s for s in prefix if isinstance(s, ast.If) and ast.unparse(s.test) == FINAL_MODE_TEST)
        refusal = next(s for s in block.body if isinstance(s, ast.If) and 'parser.error' in ast.unparse(s.body[0]))
        refusal.test = ast.parse(final_test, mode='eval').body
    scope = dict(argparse=argparse, agent_activation=agent_activation, json=json, Path=Path, localization=localization)
    exec(compile(ast.Module(body=[functions['_build_arg_parser']], type_ignores=[]), 'pipeline_parser', 'exec'), scope)
    build = scope['_build_arg_parser']

    def error(message):
        raise Refused(message)

    def parser_that_reports():
        parser = build()
        parser.error = error
        return parser
    scope.update(_build_arg_parser=parser_that_reports, argv=list(argv))
    calls = []
    body = ast.Module(body=[*prefix, *ast.parse('outcome = (args, multi_manifest)').body], type_ignores=[])
    try:
        with patch.dict(os.environ, environment), \
                patch.object(final_models, 'verify', lambda role, root=None: calls.append('verify ' + role)), \
                patch.object(final_models, 'admit_ordinary', lambda: calls.append('admit_ordinary')):
            exec(compile(ast.fix_missing_locations(body), 'pipeline_main_admission', 'exec'), scope)
    except Refused as exc:
        return 'refused', str(exc)
    args, case = scope['outcome']
    # Names only: a temporary folder differs on every observation.
    return 'admitted', dict(task=args.task, topology=args.execution_topology,
                            topology_config=Path(args.topology_config).name if args.topology_config else None,
                            multi_round=args.multi_round, case_id=(case or {}).get('case_id'), final_checks=calls)


def without(argv, flag, takes_value):
    i = argv.index(flag)
    return argv[:i] + argv[i + 1 + int(takes_value):]


def admission_cases(bundle, manifest):
    """The declared multi-round Review, an ordinary Review, and the three that stay refused."""
    declared = runner_argv(bundle, manifest)
    ordinary = list(runner.ARGV) + ['--output-dir', str(bundle / 'evidence' / 'run')]
    ordinary[ordinary.index('--topology-config') + 1] = str(bundle / 'topology.json')
    draft = list(declared)
    draft[draft.index('--task') + 1] = 'draft'
    return {'declared_multi_round_review': declared, 'ordinary_review': ordinary, 'draft_multi_round': draft,
            'flag_alone': without(declared, '--multi-round-manifest', True),
            'manifest_alone': without(declared, '--multi-round', False)}


# ---- observations (each returns the consumer's outcome, never a verdict) ----------------

def observe_seal(case=None):
    """Seal, then the instance-side seal check; the refusal message if either refuses."""
    with tempfile.TemporaryDirectory() as folder:
        try:
            bundle, _ = prepare_bundle(folder, case or live_case())
        except RuntimeError as exc:
            return dict(sealed=False, refusal=str(exc))
        m = read(bundle / 'execution_manifest.json')
        outcome = dict(sealed=True, multi_round=m['multi_round'],
                       topology=m['argv'][m['argv'].index('--execution-topology') + 1],
                       topology_config='--topology-config' in m['argv'],
                       case_sealed=m.get('case_manifest_sha256') == m['support_files'].get(runner.CASE_MANIFEST)
                       == sha(bundle / runner.CASE_MANIFEST),
                       restriction='multi-round only as the sealed case manifest declares' in m['restrictions'],
                       exposure=read(bundle / 'seal.json')['exposure'])
        try:
            instance_verify(bundle)
            outcome['instance_verify'] = 'admitted'
        except RuntimeError as exc:
            outcome['instance_verify'] = str(exc)
        return outcome


SEALED = dict(sealed=True, multi_round=True, topology='reference_serial', topology_config=False, case_sealed=True,
              restriction=True, exposure='exposed', instance_verify='admitted')


def controller_repository(root):
    """The repository the controller is bound to: the bound controller files, byte for byte."""
    repo = Path(root) / 'repo'
    for name in read(Path(root) / 'bundle' / 'execution_manifest.json')['local_control_hashes']:
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, repo / name)
    return repo


def observe_launch():
    """The real controller launches the sealed multi-round bundle against the fakes; the
    instance-side authorization check then reads the authorization it wrote."""
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        bundle, ledger = prepare_bundle(root, live_case())
        repo = controller_repository(root)
        digest = sha(bundle / 'execution_manifest.json')
        assets = bundle / 'assets.tar'
        # What the bound local reverification writes before any launch.
        write(bundle / 'AUTHORIZED_LOCAL_REVERIFICATION.json', dict(passed=True, manifest_sha256=digest))
        write(bundle / 'assets_transfer_archive.json', dict(path=assets.as_posix(), sha256=sha(assets),
                                                            manifest_sha256=digest, bytes=assets.stat().st_size))
        credential = root / 'operator_provider_access.txt'
        credential.write_text('placeholder, not a key\n', encoding='utf8')
        cc.FakeProvider.state, cc.FakeProvider.types, cc.FakeProvider.ledger = None, None, ledger
        transport = cc.FakeTransport(bundle, None, {'evidence_hash': (hashlib.sha256(cc.EVIDENCE).hexdigest()
                                                                      + '  collected_evidence.tar.gz\n').encode()})
        try:
            transport, _, ran = cc.run_controller(repo, bundle, cc.fixture_plan(ledger), transport, cc.FakeProvider,
                                                  cc.FakeClock(bundle), credential)
        except RuntimeError as exc:
            return dict(launched=False, refusal=str(exc), launches=(cc.FakeProvider.state or {}).get('launches', 0))
        finally:
            cc.FakeProvider.ledger = None
        failure = ran / 'controller_failure.json'
        permit = read(ran / 'operator_authorization.json')
        try:
            runner.authorization(bundle, read(bundle / 'execution_manifest.json'), permit,
                                 now=permit['active_start_epoch'] + 1)
            authorized = 'admitted'
        except RuntimeError as exc:
            authorized = str(exc)
        return dict(launched=True, failure=read(failure) if failure.exists() else None,
                    workload_started='ordinary_workload' in transport.started,
                    record_multi_round=read(ran / 'run_record.json')['multi_round'],
                    permit_multi_round=permit['multi_round'], instance_authorization=authorized,
                    loop_name=cc.FakeProvider.state['launch_body']['name'].startswith('shimmer-loop-'),
                    ledger_events=[r['event'] for r in cc.ledger_rows(ledger) if r['event'] != 'budget_open'])


LAUNCHED = dict(launched=True, failure=None, workload_started=True, record_multi_round=True, permit_multi_round=True,
                instance_authorization='admitted', loop_name=True,
                ledger_events=['launch_intent', 'launch', 'termination'])


# A neutralisation of main()'s final-mode refusal test, read by observe_admission.
_FINAL_TEST_OVERRIDE = []


@contextlib.contextmanager
def final_test_replaced(expression):
    _FINAL_TEST_OVERRIDE.append(expression)
    try:
        yield
    finally:
        _FINAL_TEST_OVERRIDE.pop()


def observe_admission():
    final_test = _FINAL_TEST_OVERRIDE[-1] if _FINAL_TEST_OVERRIDE else None
    with tempfile.TemporaryDirectory() as folder:
        bundle, _ = prepare_bundle(folder, live_case())
        manifest = instance_verify(bundle)
        return {name: list(pipeline_admission(argv, manifest['environment'], final_test))
                for name, argv in admission_cases(bundle, manifest).items()}


ADMISSION_CHECKS = ['verify producer', 'verify auditor', 'admit_ordinary']


def admission_verdict(outcome):
    declared, ordinary = outcome['declared_multi_round_review'], outcome['ordinary_review']
    good = (declared[0] == 'admitted' and declared[1] == dict(task='review', topology='reference_serial',
                                                               topology_config=None, multi_round=True,
                                                               case_id='launch-case', final_checks=ADMISSION_CHECKS)
            and ordinary[0] == 'admitted' and ordinary[1]['topology'] == 'report_optimized'
            and ordinary[1]['topology_config'] == 'topology.json'
            and ordinary[1]['multi_round'] is False and ordinary[1]['final_checks'] == ADMISSION_CHECKS
            # refused by the final-mode block itself, before any case material is read
            and all(outcome[n][0] == 'refused' and outcome[n][1].startswith(FINAL_MODE_REFUSAL)
                    for n in ('draft_multi_round', 'flag_alone', 'manifest_alone')))
    return ('PASS' if good else 'FAIL'), 'final-mode admission of the declared multi-round Review'


ASSESSMENT_CASES = {
    'reviewed_and_activated': ('reviewed', True),
    'refused_but_activated': ('refused', True),
    'phase_not_completed': (None, True),
    'reviewed_not_activated': ('reviewed', False),
    'no_case_record': ('absent', False),
}


def saved_case_record(folder, outcome, activated):
    """A run folder holding the case record multi_round itself writes, read back the way
    runner.execute reads it (multi_round.read_saved)."""
    ctx = for_run_dir(ROOT, Path(folder))
    if outcome == 'absent':
        (Path(folder) / 'audit').mkdir(parents=True)
        write(Path(folder) / 'audit' / 'multi_round_request.json', dict(requested=True))
        return mr.read_saved(ctx.run_dir, ctx.run_id)
    record = mr.begin(ctx, live_case())
    if activated:
        # Bound exactly as multi_round_phase.execute binds them before it activates.
        refs = ReferenceIndex.open(ctx.project_root, index_path=ctx.reference_index_path())
        record['evidence'] = mr.bind_sources(record['manifest'], [dict(id=k, name=k + '.md', text=v)
                                                                  for k, v in DOCS.items()], refs)
        record['activation'] = mr.activation(True, eligible=True, reached=True)
    else:
        record['activation'] = mr.activation(True, eligible=False, reason='sensitive_multi_round_unavailable')
    if outcome is not None:
        record['outcome'] = outcome
    mr.write_record(ctx, record)
    return mr.read_saved(ctx.run_dir, ctx.run_id)


def observe_assessment():
    completion = dict(state='completed', reached_end=True, exit_code=0)
    raw = [dict(event='pipeline_start'), dict(event='model_call', adapter_checkpoint=168), dict(event='pipeline_end')]
    result = {}
    for name, (outcome, activated) in ASSESSMENT_CASES.items():
        with tempfile.TemporaryDirectory() as folder:
            saved = saved_case_record(Path(folder) / 'run', outcome, activated)
            verdict = runner.assess(completion, raw, saved)
            result[name] = [verdict['execution_integrity_passed'], verdict['reasons']]
    ordinary = runner.assess(completion, raw, None)
    result['ordinary_run'] = [ordinary['execution_integrity_passed'], ordinary['reasons']]
    return result


ASSESSED = {'reviewed_and_activated': [True, []],
            'refused_but_activated': [False, ['multi_round_not_reviewed']],
            'phase_not_completed': [False, ['multi_round_not_reviewed']],
            'reviewed_not_activated': [False, ['multi_round_not_activated']],
            'no_case_record': [False, ['multi_round_not_reviewed', 'multi_round_not_activated']],
            'ordinary_run': [True, []]}


# ---- neutralisations ---------------------------------------------------------------------

def blanket_refusal():
    """The S1 controller rule this replaced: every multi-round or protected workload refused."""
    real = runner.admit_workload

    def refuse(manifest, seal, base=None):
        runner.require(not manifest.get('multi_round') and not manifest.get('protected_test'), 'Excluded workload')
        return real(manifest, seal, base)
    return patch.object(runner, 'admit_workload', refuse)


def assessment_without_the_case_record():
    """The S1 assessment, which never read the saved case record."""
    real = runner.assess
    return patch.object(runner, 'assess', lambda completion, raw, multi_round=None: real(completion, raw, None))


class MultiRoundLaunchChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise, check=None):
        verdict = check or (lambda: ('PASS' if observe() == expected else 'FAIL', name))
        result = prove_effect(name=name, validate=lambda: mr.validate_manifest(live_case()) is not None,
                              observe=observe, check=verdict, neutralise=neutralise)
        MultiRoundLaunchChecks.evidence.append(result)

    def test_the_sealer_seals_a_declared_multi_round_review_and_the_instance_admits_it(self):
        """Neutralised: the sealer writes the ordinary flags for a multi-round workload, and
        the instance-side seal check refuses it ('Run flags changed')."""
        self.prove('seal_declares_multi_round', observe_seal, SEALED,
                   lambda: patch.object(sealer, 'MULTI_ROUND_ARGV', runner.ARGV))

    def test_a_fixture_case_manifest_is_refused_at_sealing(self):
        """Neutralised: the live case validation is skipped and a fixture case is sealed."""
        refused = dict(sealed=False, refusal='Fixture case manifest refused in a live run')
        self.prove('fixture_case_refused_at_seal', lambda: observe_seal(live_case(fixture=True)), refused,
                   lambda: patch.object(sealer, 'validate_live_case_manifest', lambda value, documents=None: value))

    def test_the_controller_launches_it_and_the_instance_accepts_its_authorization(self):
        """Neutralised: the S1 blanket refusal of multi-round is reinstated; the controller
        refuses before any instance exists."""
        self.prove('controller_launches_declared_multi_round', observe_launch, LAUNCHED, blanket_refusal)

    def test_final_mode_admits_the_declared_multi_round_review_only(self):
        """Neutralised: main()'s final-mode test is put back to the S1 condition, which
        refused every multi-round Review."""
        old = "args.multi_round or args.multi_round_manifest or args.task != 'review'"
        self.prove('final_mode_admission_old_condition', observe_admission, None,
                   lambda: final_test_replaced(old), check=lambda: admission_verdict(observe_admission()))

    def test_draft_flag_alone_and_manifest_alone_are_refused_by_the_final_mode_block(self):
        """Neutralised: the final-mode test checks the task only; the flag alone and the
        manifest alone are then refused later, by the multi-round validation, not by the
        final-mode block, which this check requires."""
        self.prove('final_mode_refusals_are_its_own', observe_admission, None,
                   lambda: final_test_replaced("args.task != 'review'"),
                   check=lambda: admission_verdict(observe_admission()))

    def test_the_assessment_passes_only_on_reviewed_and_activated(self):
        """Neutralised: the assessment ignores the saved case record, as before D-011 choice 11."""
        self.prove('assessment_needs_reviewed_and_activated', observe_assessment, ASSESSED,
                   assessment_without_the_case_record)


def check():
    MultiRoundLaunchChecks.evidence = []
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MultiRoundLaunchChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(' ')[0] + ': ' + str(err).strip().splitlines()[-1][:160]
                    for case, err in list(result.failures) + list(result.errors)]
        return 'FAIL', '; '.join(problems[:4])
    return 'PASS', ('%d R2 proofs, each neutralise, fail, restore, pass: the sealer seals a declared multi-round '
                    'Review (reference_serial, no topology file, case manifest sealed) and the instance admits it; '
                    'a fixture case is refused at sealing; the real controller launches it under the loop guard and '
                    'the instance accepts its authorization; pipeline main() in final mode admits it and refuses '
                    'Draft, the flag alone and the manifest alone in its own block; the assessment passes only on '
                    'outcome reviewed and activation activated' % result.testsRun)


def main():
    status, detail = check()
    for proof in MultiRoundLaunchChecks.evidence:
        print(proof['name'], proof['status'])
        print('  before:  ', json.dumps(proof['before'], sort_keys=True)[:400])
        print('  mutated: ', json.dumps(proof['mutated'], sort_keys=True)[:400])
        print('  restored:', json.dumps(proof['restored'], sort_keys=True)[:400])
    print(status, detail)
    return 0 if status == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
