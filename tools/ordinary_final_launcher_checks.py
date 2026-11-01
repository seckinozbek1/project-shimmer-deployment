"""Arm L checks (D-S13 item 6d): the launcher menu as a third sealed arm.

A real review and a real draft started from the launcher menu run on the loop's own instance,
never on the laptop. These checks prove every new rule of that arm here, on fixtures, with no
model, no pipeline and no network: the sealed launcher block and its exposed-only rule, the
prompt map read word for word from the bound launcher, wizard and pipeline sources, the
sealer's mapping of the workload as the wizard lists it, the session driver answering only
from the map (and stopping on an unknown prompt, on answers used up and at its deadline), the
REAL shimmer.sh and the REAL intake wizard driven through a review then a draft then Q with a
stand-in pipeline (each child Python network-denied by the sealed sitecustomize), the
REAL shimmer.sh, runtime check, preflight, wizard and pipeline started from an extracted copy of
the project archive the sealer builds for arm L, up to the pipeline's first question (L14), the
menu's environment made from the runner's runtime, the arm-aware assessment, the controller's
single-bundle rule and its stop of the menu's children, and the analyser's report row.

The tests live in LauncherArmChecks, mixed into the controller checks' ControllerChecks, so the
controller's own harness (fake provider, transport and clock) is theirs; each rule is proven by
neutralise, fail, restore, pass through LAUNCHER_NEUTRALIZATIONS (the controller gate and gate
check 311). A test needing a launcher file the tree does not hold (the container image ships no
shimmer.sh) or a bash (Windows without Git) is skipped with that reason.
"""
import base64
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT / 'tools'), str(ROOT / 'scripts')):
    if _path not in sys.path:
        sys.path.insert(0, _path)
import analyze_ordinary_final_run as analysis
import ordinary_final_cloud as controller
import ordinary_final_run as runner
import prepare_ordinary_final_run as sealer
from ordinary_final_run import read, write

NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
QUESTION = 'Summarise which results on the result sheet fall outside their reference ranges.'
# The real files the menu path runs here; everything else it calls is a stand-in.
REAL_WIZARD_FILES = ('scripts/intake_wizard.py', 'scripts/role_resolution.py', 'scripts/convention_parser.py',
                     'scripts/text_extract.py', 'scripts/run_choices.py')
CONTRACT_STUB = """import os, sys
if "--resolve" in sys.argv[1:]:
    print(os.environ.get("LAUNCHER_CHECK_PYTHON") or sys.executable)
sys.exit(0)
"""
# The readiness preflight reports an issue, so the menu asks its optional continue question.
PREFLIGHT_STUB = """import sys


def sensitive_readiness(project_root=None):
    return False, "stand-in: no sensitive mode here"


if __name__ == "__main__":
    print("STAND_IN_PREFLIGHT " + " ".join(sys.argv[1:]))
    sys.exit(1)
"""
# The pipeline stand-in prints the pipeline's own three questions (texts from the sealed map,
# which the prompt check holds to the real pipeline's source), asks one escalation on the
# review, and leaves the run folder a real run leaves, through the real role_resolution for the
# draft's system manifest. With LAUNCHER_FIXTURE_NETWORK set it tries one outside connection.
PIPELINE_STAND_IN = '''import json, os, socket, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import role_resolution
PROMPTS = %(prompts)r
args = sys.argv[1:]
task = args[args.index("--task") + 1] if "--task" in args else "review"
assert "--backend-profile" in args and args[args.index("--backend-profile") + 1] == "local", args
assert "--sensitivity-layer-inactive-override" in args and "--no-redaction-override" in args, args
assert "--non-interactive" not in args, args
if os.environ.get("SHIMMER_MODEL_MODE") != "base":
    sys.exit(11)
if os.environ.get("LAUNCHER_FIXTURE_NETWORK"):
    try:
        socket.create_connection(("192.0.2.1", 9), timeout=1)
    except Exception:
        pass
for key in ("layer_override", "redaction_override"):
    if input(PROMPTS[key]).strip().lower() not in ("y", "yes"):
        sys.exit(6)
context = ROOT / "input" / "context"
memo = None
if task == "draft":
    question = args[args.index("--question") + 1]
    memo = context / "draft_memo_fixture.md"
    memo.write_text("# Memo\\n\\n" + question + "\\n", encoding="utf-8")
    role_resolution.write_manifest(context, [memo.name], "system_draft", grounding=[])
if input(PROMPTS["proceed_calls"]).strip().lower() not in ("y", "yes"):
    sys.exit(0)
if task == "review":
    print("=== OPERATOR ESCALATION: stand-in ===", file=sys.stderr)
    input(PROMPTS["escalation_decision"])
    input(PROMPTS["escalation_rationale"])
run = ROOT / "output" / "runs" / ("%%s__%%s" %% (time.strftime("%%Y%%m%%dT%%H%%M%%S"), task))
(run / "audit").mkdir(parents=True)
(run / "logs").mkdir()
(run / "deliverables").mkdir()
(run / "logs" / "model_telemetry.jsonl").write_text(
    json.dumps({"event": "pipeline_start"}) + "\\n" + json.dumps({"event": "pipeline_end"}) + "\\n", encoding="utf-8")
(run / "deliverables" / "_run_summary.md").write_text("# Run summary\\n", encoding="utf-8")
if memo is not None:
    (run / "deliverables" / memo.stem).mkdir()
    (run / "deliverables" / memo.stem / "memo.md").write_bytes(memo.read_bytes())
    role_resolution.clear_system_draft(context)
(run / "audit" / "run_completion.json").write_text(json.dumps(dict(
    state="completed", reached_end=True, exit_code=0, semantic_complete=True, task=task)), encoding="utf-8")
print("STAND_IN_PIPELINE finished " + task)
'''


def git_bash():
    """A bash that runs a script itself. On Windows that is Git's bash beside git (the System32
    bash is the WSL launcher and is never used); elsewhere the bash on PATH."""
    if os.name != 'nt':
        return shutil.which('bash')
    git = shutil.which('git')
    if not git:
        return None
    for base in list(Path(git).resolve().parents)[:3]:
        for candidate in (base / 'usr' / 'bin' / 'bash.exe', base / 'bin' / 'bash.exe'):
            if candidate.is_file():
                return str(candidate)
    return None


def bound_sources():
    """The sources the prompts are read from, as the sealer reads them from the bound commit."""
    return {n: (ROOT / n).read_bytes().replace(b'\r\n', b'\n') for n in runner.LAUNCHER_PROMPT_SOURCES}


def ensemble_says_no(rule_text):
    """A model-free stand-in for the five-voter redaction-intent decision: available, and no. The
    sealer's own compiler still runs its declared-category and phrasing rules; the clinical
    workload's real ensemble verdict (5 of 5 voters no on every convention) was measured once,
    with the models, when the sealer's sensitivity rule was added."""
    return False, (dict(available=True, result=False, stand_in=True) if str(rule_text or '').strip() else None)


def ensemble_unavailable(rule_text):
    return False, dict(available=False, reason='stand-in: no embedding model')


def model_free_ensemble(stand_in=ensemble_says_no):
    """Sealing an arm L workload compiles its conventions (launcher_sensitivity_error); the checks
    load no model, so the ensemble's decision is the stand-in's."""
    import sensitivity_layer.rules as rules
    return patch.object(rules, '_ensemble_redaction_intent', stand_in)


def launcher_block(question=QUESTION, members=None):
    """The sealer's own placed workload and launcher block for the clinical development workload."""
    with model_free_ensemble():
        placed, block = sealer.launcher_fields(members or sealer.default_workload()[1], question, bound_sources())
    return placed, block


def l_manifest(block, placed, **changes):
    """An arm L manifest as far as the runner's rules read it."""
    value = dict(arm='L', launcher=block, multi_round=False, protected_test=False, argv=runner.LAUNCHER_ARGV,
                 support_files={}, project_files=dict({runner.LAUNCHER_SCRIPT: 'f' * 64},
                                                      **{n: 'e' * 64 for n in placed}))
    value.update(changes)
    return value


def menu_stand_in(path, script):
    """A small Python 'menu' for the driver checks: `script` is a list of ('ask', text) and
    ('print', text) steps; every answer read is echoed as ANSWER=<text>."""
    lines = ['import sys, time']
    for kind, text in script:
        if kind == 'ask':
            lines.append('print("ANSWER=" + input(%r))' % text)
        elif kind == 'print':
            lines.append('print(%r, flush=True)' % text)
        elif kind == 'raw':
            lines.append('sys.stdout.write(%r); sys.stdout.flush()' % text)
        elif kind == 'sleep':
            lines.append('time.sleep(%s)' % text)
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8')


def prompt(id_, text, answers, optional=False, repeat_last=False):
    return dict(id=id_, prompt=text, answers=list(answers), optional=optional, repeat_last=repeat_last)


def launcher_project(root, block, placed):
    """A project folder the real shimmer.sh runs in: the real menu and wizard files, stand-ins
    for the runtime contract, the preflight and the pipeline, the sealed launcher workload, and
    a stand-in venv activate script. Returns (project, fake python3)."""
    project = Path(root) / 'project'
    for name in (runner.LAUNCHER_SCRIPT,) + REAL_WIZARD_FILES:
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes().replace(b'\r\n', b'\n'))
    for name, text in (('tools/runtime_contract.py', CONTRACT_STUB), ('scripts/preflight.py', PREFLIGHT_STUB),
                       ('scripts/pipeline.py', PIPELINE_STAND_IN % dict(
                           prompts={p['id']: p['prompt'] for p in block['prompts']}))):
        (project / name).parent.mkdir(parents=True, exist_ok=True)
        (project / name).write_text(text, encoding='utf-8', newline='\n')
    for name, data in placed.items():
        (project / name).parent.mkdir(parents=True, exist_ok=True)
        (project / name).write_bytes(data)
    (project / 'config').mkdir(exist_ok=True)
    (project / '.venv' / ('Scripts' if os.name == 'nt' else 'bin')).mkdir(parents=True)
    (project / '.venv' / ('Scripts' if os.name == 'nt' else 'bin') / 'activate').write_text('# stand-in\n', encoding='utf-8')
    fake = Path(root) / 'fakebin' / 'python3'
    fake.parent.mkdir(parents=True)
    fake.write_text('#!/usr/bin/env bash\nexec "%s" "$@"\n' % Path(sys.executable).as_posix(), encoding='utf-8', newline='\n')
    os.chmod(fake, 0o755)
    return project, fake


def git_usr_bin(bash):
    """Git's usr/bin (dirname, cat, rm), which shimmer.sh calls by name; elsewhere bash's own folder."""
    folder = Path(bash).parent
    if os.name == 'nt' and folder.name.lower() == 'bin' and folder.parent.name.lower() != 'usr':
        folder = folder.parent / 'usr' / 'bin'
    return folder


def tracked_source(source, extra=()):
    """The sealer's runtime_source over this tree: its own selection (archive_names) of the tracked
    files, read from the working tree where the sealer reads the same names from the bound commit."""
    listed = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, timeout=120, check=True,
                            stdin=subprocess.DEVNULL, creationflags=NO_WINDOW).stdout.decode('utf-8')
    names = sealer.archive_names([n for n in listed.split('\0') if n], extra)
    return {n: (ROOT / n).read_bytes().replace(b'\r\n', b'\n') for n in names if (ROOT / n).is_file()}


def sealed_arm_l_project(root, ledger, harness):
    """Seal an arm L bundle with the sealer's own prepare() over this tree's tracked files and
    extract its project archive, as the instance does. Returns (project, manifest)."""
    import tarfile
    import multi_round_launch_checks as mr_checks
    inputs = Path(root) / 'inputs'
    inputs.mkdir(parents=True)
    (inputs / 'runtime.candidate.lock').write_text('', encoding='utf-8')
    write(inputs / 'provider_inventory.json', dict(instances=[], instance_types=[harness.A10_TYPE],
                                                   images=[dict(harness.IMAGE)], observed_at='fixture'))
    with mr_checks.sealing_stand_ins(), patch.object(sealer, 'runtime_source', tracked_source), model_free_ensemble():
        sealer.prepare(Path(root) / 'bundle', budget=dict(ledgers=[ledger], forecast_minutes=harness.FORECAST_MINUTES,
                                                          storage_forecast_usd=harness.STORAGE_USD, reaped=[ledger]),
                       inputs_from=inputs, now_epoch=harness.FakeClock().now, arm='L', launcher_question=QUESTION)
    manifest = read(Path(root) / 'bundle' / 'execution_manifest.json')
    project = Path(root) / 'project'
    with tarfile.open(Path(root) / 'bundle' / 'project.tar.gz') as archive:
        archive.extractall(project, filter='data')
    return project, manifest


# One review cut at the pipeline's first question, which is declined: the pipeline then returns 6
# before any model work and the menu quits. The draft's prompts are never met.
REVIEW_TO_THE_PIPELINE = {'menu': ['1', 'Q'], 'task': ['R'], 'layer_override': ['n']}
DRAFT_ONLY_PROMPTS = ('draft_question', 'redaction_override', 'proceed_calls', 'escalation_decision',
                      'escalation_rationale')


def review_to_the_pipeline(prompts):
    """The sealed map cut to that review: every other review prompt keeps its first sealed answer."""
    return [dict(p, answers=REVIEW_TO_THE_PIPELINE.get(p['id'], p['answers'][:1]))
            for p in prompts if p['id'] not in DRAFT_ONLY_PROMPTS]


def decoded_phase_script(transport, label):
    """The command a detached phase ran, decoded from its launch (as the controller sends it)."""
    launch = next(argv[-1] for argv, _ in transport.calls if argv[0] == 'ssh' and '/%s.pid' % label in argv[-1])
    return base64.b64decode(re.search(r"printf %s '?([A-Za-z0-9+/=]+)'?", launch).group(1)).decode()


def assessment_fixture(root, *, memo=True, summary=True, review_runs=1, cleared=True, blocked=0, semantic=True,
                       network_logs=True, pipeline_denial='installed', bootstrap_denial='sockets'):
    """A project and evidence folder as a finished session leaves them, for the assessment."""
    project, evidence = Path(root) / 'project', Path(root) / 'evidence'
    runs = project / 'output' / 'runs'
    names = {'review': ['20261101T100000__review%d' % k for k in range(review_runs)], 'draft': ['20261101T110000__draft']}
    for task, folders in names.items():
        for name in folders:
            run = runs / name
            (run / 'audit').mkdir(parents=True)
            (run / 'logs').mkdir()
            (run / 'deliverables').mkdir()
            write(run / 'audit' / 'run_completion.json', dict(state='completed' if semantic else 'stopped', reached_end=True,
                                                              exit_code=0, semantic_complete=semantic, task=task))
            (run / 'logs' / 'model_telemetry.jsonl').write_text(
                '{"event": "pipeline_start"}\n{"event": "pipeline_end"}\n', encoding='utf-8')
            if task == 'review' and summary:
                (run / 'deliverables' / '_run_summary.md').write_text('# summary\n', encoding='utf-8')
            if task == 'draft' and memo:
                (run / 'deliverables' / 'draft_memo_x').mkdir()
                (run / 'deliverables' / 'draft_memo_x' / 'memo.md').write_text('# memo\n', encoding='utf-8')
    context = project / 'input' / 'context'
    context.mkdir(parents=True)
    if not cleared:
        write(context / '_review_targets.json', dict(source='system_draft', targets=['draft_memo_x.md']))
        (context / 'draft_memo_x.md').write_text('# memo\n', encoding='utf-8')
    network = evidence / 'launcher' / 'network'
    network.mkdir(parents=True)
    if network_logs:
        # The image's python3 the menu starts with (no HTTP clients: its socket layer only), then
        # one pipeline process per run.
        logs = [('runtime_contract.py', bootstrap_denial)] + [('pipeline.py', pipeline_denial)] * (review_runs + 1)
        for pid, (program, status) in enumerate(logs, 1):
            rows = [dict(event='process_start', pid=pid, program=program), dict(event='network_denial', status=status)]
            if pid == len(logs):
                rows += [dict(event='network_blocked', network_kind='create_connection')] * blocked
            (network / ('network_%d.jsonl' % pid)).write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    steps = [dict(id='task', answer='R', runs=[]), dict(id='task', answer='D', runs=sorted(names['review']))]
    session = dict(exit_code=0, stop_reason=None, unknown_prompt=None, steps=steps, used={}, unused=[],
                   required_answers=2, seconds=1.0)
    return project, evidence, session


class LauncherArmChecks:
    """Arm L's rules, mixed into ControllerChecks (its setUp, self.root and harness)."""

    def harness(self):
        """The controller checks module this class was mixed into (it may be __main__)."""
        return sys.modules[type(self).__module__]

    def need_launcher_files(self):
        missing = [n for n in (runner.LAUNCHER_SCRIPT,) + runner.LAUNCHER_PROMPT_SOURCES if not (ROOT / n).is_file()]
        if missing:
            self.skipTest('launcher file absent from this tree: ' + ', '.join(missing))

    def test_an_arm_l_bundle_is_admitted_only_with_its_sealed_launcher_block(self):
        """The runner admits arm L only with its sealed block: the menu and workload by name, the
        children's environment exactly the sealed one (base models, offline, no install), a map
        that runs a review, then a draft, then Q, the draft answered with the sealed question; a
        launcher block in a B3 or B1 bundle and B1 fields in an arm L bundle are refused."""
        self.need_launcher_files()
        placed, block = launcher_block()
        seal = dict(exposure='exposed')
        self.assertEqual(runner.admit_workload(l_manifest(block, placed), seal)['arm'], 'L')
        refusals = [
            (dict(block, child_environment=dict(block['child_environment'], SHIMMER_MODEL_MODE='final')), 'exactly as sealed'),
            (dict(block, child_environment={k: v for k, v in block['child_environment'].items() if k != 'HF_HUB_OFFLINE'}),
             'exactly as sealed'),
            (dict(block, prompts=[dict(p, answers=['1', '1']) if p['id'] == 'menu' else p for p in block['prompts']]),
             'review, then a draft, then quit'),
            (dict(block, prompts=[dict(p, answers=['D', 'R']) if p['id'] == 'task' else p for p in block['prompts']]),
             'review, then a draft, then quit'),
            (dict(block, question='Another question.'), 'sealed question'),
            (dict(block, prompts=[dict(p, optional=False, repeat_last=True) if p['id'] == 'backend' else p
                                  for p in block['prompts']]), 'Only an optional prompt'),
            (dict(block, script='other.sh'), 'another script'),
        ]
        for changed, message in refusals:
            with self.assertRaisesRegex(RuntimeError, message):
                runner.admit_workload(l_manifest(changed, placed), seal)
        with self.assertRaisesRegex(RuntimeError, 'no launcher or no launcher workload'):
            runner.admit_workload(l_manifest(block, {}, project_files={}), seal)
        b3 = l_manifest(block, placed, arm='B3', argv=runner.ARGV)
        with self.assertRaisesRegex(RuntimeError, 'launcher block sealed in a B3 bundle'):
            runner.admit_workload(b3, seal)
        with self.assertRaisesRegex(RuntimeError, 'B1 fields sealed in an arm L bundle'):
            runner.admit_workload(l_manifest(block, placed, b1=dict(checkpoints=[])), seal)

    def test_an_arm_l_bundle_runs_exposed_only(self):
        """Arm L runs development material: the runner refuses it in a sealed run, and the sealer
        refuses to seal it as one."""
        self.need_launcher_files()
        placed, block = launcher_block()
        manifest = l_manifest(block, placed, source_commit='f' * 40, test_archive_sha256='a' * 64)
        sealed = dict(exposure='sealed', test_manifest_sha256='b' * 64, test_archive_sha256='a' * 64, code_commit='f' * 40)
        with self.assertRaisesRegex(RuntimeError, 'Arm L runs exposed only'):
            runner.admit_workload(manifest, sealed)
        archive = self.root / 'test.tar'
        archive.write_bytes(b'archive stand-in')
        with self.assertRaisesRegex(RuntimeError, 'Arm L runs exposed only'):
            sealer.prepare(self.root / 'sealed_l', exposure='sealed', workload=archive, arm='L', launcher_question=QUESTION)
        with self.assertRaisesRegex(RuntimeError, 'needs --launcher-question'):
            sealer.prepare(self.root / 'no_question', arm='L')

    def test_every_sealed_prompt_is_printed_word_for_word_by_the_bound_sources(self):
        """Each sealed prompt is a printf text of shimmer.sh or one string constant of the wizard
        or the pipeline (adjacent literals joined), so the map can never wait on a prompt that is
        not printed; a prompt changed by one character is refused, naming it."""
        self.need_launcher_files()
        _placed, block = launcher_block()
        sources = {n: d.decode('utf-8') for n, d in bound_sources().items()}
        self.assertIsNone(runner.launcher_prompt_error(block['prompts'], sources))
        texts = runner.launcher_prompt_texts(sources)
        self.assertIn('Choose an option [1-5, Q]: ', texts)
        self.assertIn(next(p['prompt'] for p in block['prompts'] if p['id'] == 'layer_override'), texts)
        changed = [dict(p, prompt='Proceed? [Y/n]: ') if p['id'] == 'proceed' else p for p in block['prompts']]
        self.assertEqual(runner.launcher_prompt_error(changed, sources),
                         'A sealed prompt is not printed by the bound launcher, wizard or pipeline: proceed')
        with self.assertRaisesRegex(RuntimeError, 'not printed by the bound launcher'), model_free_ensemble():
            sealer.launcher_fields(sealer.default_workload()[1], QUESTION, dict(
                bound_sources(), **{'scripts/pipeline.py': b'print("no prompts here")\n'}))

    def test_the_sealer_maps_the_workload_as_the_wizard_lists_it(self):
        """The sealer places the workload in one flat folder, each file where the wizard's own
        classify() places it, and answers the wizard's target question with the numbers it
        lists the targets under; the sealer's own prepare() writes an arm L manifest whose
        project carries the menu and the workload and nothing under input/, which the
        instance-side verify admits."""
        self.need_launcher_files()
        placed, block = launcher_block()
        self.assertEqual(sorted(placed), ['launcher_input/analyte_reference_ranges.md', 'launcher_input/lab_conventions.md',
                                          'launcher_input/result_sheet.md'])
        answers = {p['id']: p['answers'] for p in block['prompts']}
        self.assertEqual(answers['targets'], ['2'])
        self.assertEqual(answers['prior'], [''])
        self.assertEqual(answers['draft_question'], [QUESTION])
        self.assertEqual(answers['folder'], [runner.LAUNCHER_WORKLOAD_TOKEN])
        members = sealer.default_workload()[1]
        with self.assertRaisesRegex(RuntimeError, 'would not place'):
            sealer.launcher_fields(dict(members, **{'context/lab_conventions.md': members.pop('conventions/lab_conventions.md')}),
                                   QUESTION, bound_sources())
        members = sealer.default_workload()[1]
        with self.assertRaisesRegex(RuntimeError, 'one flat folder'):
            sealer.launcher_fields(dict(members, **{'context/sub/extra.md': b'# Extra\n'}), QUESTION, bound_sources())
        with self.assertRaisesRegex(RuntimeError, 'one line'):
            sealer.launcher_fields(sealer.default_workload()[1], 'Two\nlines', bound_sources())
        import multi_round_launch_checks as mr_checks
        harness = self.harness()
        inputs = self.root / 'inputs'
        inputs.mkdir()
        (inputs / 'runtime.candidate.lock').write_text('', encoding='utf-8')
        write(inputs / 'provider_inventory.json', dict(instances=[], instance_types=[harness.A10_TYPE],
                                                       images=[dict(harness.IMAGE)], observed_at='fixture'))
        with mr_checks.sealing_stand_ins(), model_free_ensemble():
            sealer.prepare(self.root / 'l', budget=dict(ledgers=[self.ledger], forecast_minutes=harness.FORECAST_MINUTES,
                                                        storage_forecast_usd=harness.STORAGE_USD, reaped=[self.ledger]),
                           inputs_from=inputs, now_epoch=harness.FakeClock().now, arm='L', launcher_question=QUESTION)
        manifest = read(self.root / 'l' / 'execution_manifest.json')
        self.assertEqual((manifest['arm'], manifest['argv'], manifest['launcher']), ('L', [], block))
        self.assertTrue(set(placed) | set(runner.LAUNCHER_SOURCES) <= set(manifest['project_files']))
        self.assertFalse([n for n in manifest['project_files'] if n.startswith('input/')])
        self.assertEqual(mr_checks.instance_verify(self.root / 'l')['arm'], 'L')

    def test_arm_l_is_sealed_only_for_a_workload_with_no_redaction_rule(self):
        """Arm L's map declares every run NON-SENSITIVE, twice, and chooses Normal mode (no
        redaction) with no operator present, so the sealer compiles the workload's conventions with
        the pipeline's own parser and redaction compiler first: the clinical sheet (no operator
        redaction rule) is sealed; the same workload with a confidentiality rule added, or with an
        ensemble that cannot decide, is refused (S7 close, adversarial item 13)."""
        self.need_launcher_files()
        members = sealer.default_workload()[1]
        conventions = {n.split('/', 1)[1]: d for n, d in members.items() if n.startswith('conventions/')}
        with model_free_ensemble():
            self.assertIsNone(sealer.launcher_sensitivity_error(conventions))
        private = dict(members, **{'conventions/lab_conventions.md': members['conventions/lab_conventions.md'] +
                                   b'\n## CONV-L06 , conv-confidentiality [required]\nRedact the patient name from every '
                                   b'deliverable.\n'})
        with self.assertRaisesRegex(RuntimeError, 'operator redaction or confidentiality rule'), model_free_ensemble():
            sealer.launcher_fields(private, QUESTION, bound_sources())
        with self.assertRaisesRegex(RuntimeError, 'ensemble could not decide'), model_free_ensemble(ensemble_unavailable):
            sealer.launcher_fields(members, QUESTION, bound_sources())

    def test_the_session_answers_only_from_the_map_and_stops_on_anything_else(self):
        """The driver answers each prompt from the map in sealed order, at a line start, once the
        output is quiet; it stops when a prompt's answers are used up, when an unknown prompt
        waits on input, and at its deadline, ending the process it started each time."""
        menu = self.root / 'menu.py'
        mapped = [prompt('pick', 'Pick [a/b]: ', ['a', 'b']), prompt('name', 'Name: ', ['ok'])]

        def drive(script, prompts, deadline=30, unknown_after=60, idle_after=60):
            menu_stand_in(menu, script)
            return runner.drive_session([sys.executable, '-u', str(menu)], self.root, dict(os.environ),
                                        runner.PromptMap(prompts), time.time() + deadline, unknown_after=unknown_after,
                                        idle_after=idle_after)
        done = drive([('print', 'Pick [a/b]: is printed whole here, never a prompt'), ('ask', 'Pick [a/b]: '),
                      ('ask', 'Pick [a/b]: '), ('ask', 'Name: ')], mapped)
        self.assertEqual((done['stop_reason'], done['exit_code'], done['unused']), (None, 0, []))
        self.assertEqual([(s['id'], s['answer']) for s in done['steps']], [('pick', 'a'), ('pick', 'b'), ('name', 'ok')])
        self.assertIn(b'ANSWER=a', done['output'])
        self.assertIn(b'ANSWER=b', done['output'])
        used_up = drive([('ask', 'Pick [a/b]: ')] * 3, mapped)
        self.assertEqual((used_up['stop_reason'], used_up['unknown_prompt']), ('answers_used_up', 'pick'))
        unknown = drive([('ask', 'Pick [a/b]: '), ('raw', 'Something else? '), ('sleep', 30)], mapped, deadline=20,
                        unknown_after=1)
        self.assertEqual((unknown['stop_reason'], unknown['unknown_prompt']), ('unknown_prompt', 'Something else?'))
        self.assertIsNotNone(unknown['exit_code'])
        late = drive([('sleep', 30)], mapped, deadline=2)
        self.assertEqual(late['stop_reason'], 'deadline')
        self.assertIsNotNone(late['exit_code'])
        # A prompt another line was printed after cannot be seen; the silence that follows stops it.
        hidden = drive([('raw', 'Pick [a/b]: '), ('print', 'a line printed after the prompt'), ('ask', '')], mapped,
                       deadline=20, idle_after=2)
        self.assertEqual(hidden['stop_reason'], 'output_idle')
        self.assertIsNotNone(hidden['exit_code'])

    def test_the_real_menu_runs_a_review_then_a_draft_from_the_map(self):
        """The REAL shimmer.sh and the REAL intake wizard, driven by the runner's own
        execute_launcher through a review, then a draft, then Q, every answer from the sealed map
        (the preflight's continue question and the review's escalation, both optional, are met
        and answered); the stand-in pipeline gets the menu's own flags and base mode; both runs
        are moved under evidence/launcher, the draft's memo kept and its system manifest cleared,
        every child Python logs its network with the denial installed, and the assessment
        passes. An outside connection each pipeline child tries is refused, recorded and fails
        the arm. The
        analyser's report row reads the collected session."""
        self.need_launcher_files()
        bash = git_bash()
        if not bash:
            self.skipTest('no bash that runs a script (Git Bash on Windows)')
        placed, block = launcher_block()
        manifest = l_manifest(block, placed)

        def session(name, **extra):
            work = self.root / name
            project, fake = launcher_project(work, block, placed)
            evidence = work / 'evidence'
            evidence.mkdir()
            import cloud_run_observer
            rec = cloud_run_observer.Recorder(evidence / 'network.jsonl')
            path = os.pathsep.join([str(fake.parent), str(Path(bash).parent), os.environ.get('PATH', '')])
            environ = {k: v for k, v in os.environ.items() if not k.startswith(('SHIMMER_', 'LAUNCHER_'))}
            environ.update(PATH=path, LAUNCHER_CHECK_PYTHON=fake.as_posix(), PYTHONIOENCODING='utf-8', **extra)
            # The runner's observer (cloud_run_observer.py) sits beside it in a bundle; here in tools/.
            with patch.dict(os.environ, environ, clear=True), \
                    patch.object(runner, 'launcher_venv', lambda project: None), \
                    patch.object(runner, 'launcher_shell', lambda: bash):
                code = runner.execute_launcher(ROOT / 'tools', manifest, project, evidence, rec, time.time() + 240)
            return code, read(evidence / 'result.json'), evidence
        code, result, evidence = session('clean')
        self.assertEqual((code, result['reasons']), (0, []), result)
        seen = result['launcher']
        self.assertEqual(seen['session']['stop_reason'], None)
        self.assertEqual(seen['session']['exit_code'], 0)
        self.assertEqual(seen['session']['used']['menu'], 3)
        self.assertEqual(seen['session']['used']['preflight_continue'], 1)
        self.assertEqual(seen['session']['used']['escalation_decision'], 1)
        self.assertEqual([len(seen['runs'][t]) for t in runner.LAUNCHER_TASKS], [1, 1])
        self.assertEqual(seen['runs']['draft'][0]['memos'], 1)
        self.assertEqual(seen['context'], dict(system_draft_manifest=False, draft_memo_files=0))
        self.assertGreater(seen['network']['logs'], 0)
        self.assertEqual((seen['network']['pipelines'], seen['network']['pipelines_installed']), (2, 2))
        self.assertEqual(seen['network']['denial_installed'] + seen['network']['denial_sockets_only'],
                         seen['network']['processes'])
        self.assertEqual(seen['network']['blocked'], 0)
        transcript = read(evidence / 'launcher' / 'transcript.json')
        self.assertEqual([s['answer'] for s in transcript['steps'] if s['id'] in ('menu', 'task')], ['1', 'R', '1', 'D', 'Q'])
        folder = next(s['answer'] for s in transcript['steps'] if s['id'] == 'folder')
        self.assertTrue(folder.endswith(runner.LAUNCHER_WORKLOAD))
        self.assertTrue((evidence / 'launcher' / 'session_output.log').is_file())
        status = dict(launcher=analysis.launcher_status(evidence.parent, result))
        row = analysis.launcher_text(status)
        self.assertIn('the menu ended by itself with exit code 0', row)
        self.assertIn('review: state completed, reached its end True, exit code 0', row)
        self.assertIn('0 blocked attempts', row)
        # Both pipeline children (the review's and the draft's) try once; each attempt is refused.
        code, result, _ = session('network', LAUNCHER_FIXTURE_NETWORK='1')
        self.assertEqual(code, 2)
        self.assertEqual(result['reasons'], ['launcher_network_attempts:2'])
        self.assertEqual(result['launcher']['network']['blocked_kinds'], ['create_connection'])

    def test_the_real_menu_starts_from_the_project_archive_the_sealer_builds(self):
        """L14: on the instance shimmer.sh stopped one second in, before its first prompt, because
        its runtime check imported a module the sealed project archive does not carry; the test
        above runs the menu from the repository tree and could not see it. Here the REAL
        shimmer.sh, its REAL runtime check, the REAL preflight, the REAL intake wizard and the REAL
        pipeline run from an EXTRACTED copy of the project archive the sealer's own prepare()
        builds for arm L, in the menu environment the runner makes (its venv, its sitecustomize,
        every child Python network-denied, Git's usr/bin on PATH): a review answered from the
        sealed map up to the pipeline's first question, declined, so the pipeline stops before
        any model work, and the menu quits. A module the menu path imports that the archive
        lacks fails it."""
        self.need_launcher_files()
        bash = git_bash()
        if not bash:
            self.skipTest('no bash that runs a script (Git Bash on Windows)')
        if not (ROOT / '.git').exists():
            self.skipTest('no git checkout to list the tracked files the sealer selects from')
        project, manifest = sealed_arm_l_project(self.root / 'sealed', self.ledger, self.harness())
        self.assertFalse((project / 'tools' / 'remote_short_burst_probe.py').exists())
        work = self.root / 'session'
        folders = {name: work / name for name in ('site', 'network', 'tmp')}
        for folder in folders.values():
            folder.mkdir(parents=True)
        (folders['site'] / 'sitecustomize.py').write_text(runner.sitecustomize_source(), encoding='utf-8')
        runner.launcher_venv(project)
        fake = work / 'fakebin' / 'python3'
        fake.parent.mkdir()
        fake.write_text('#!/usr/bin/env bash\nexec "%s" "$@"\n' % Path(sys.executable).as_posix(), encoding='utf-8',
                        newline='\n')
        os.chmod(fake, 0o755)
        environ = {k: v for k, v in os.environ.items()
                   if not k.startswith(('SHIMMER_', 'LAUNCHER_', 'HF_', 'TRANSFORMERS_', 'VIRTUAL_ENV'))}
        environ.update(PATH=os.pathsep.join([str(fake.parent), str(git_usr_bin(bash)), environ.get('PATH', '')]),
                       PYTHONIOENCODING='utf-8')
        env = runner.launcher_environment(environ, manifest['launcher'], folders['site'], folders['network'],
                                          ROOT / 'tools', folders['tmp'])
        prompts = runner.PromptMap(review_to_the_pipeline(manifest['launcher']['prompts']),
                                   {runner.LAUNCHER_WORKLOAD_TOKEN: str(project / runner.LAUNCHER_WORKLOAD)})
        session = runner.drive_session([bash, str(project / runner.LAUNCHER_SCRIPT)], project, env, prompts,
                                       time.time() + 900)
        output = session['output'].decode('utf-8', errors='replace')
        self.assertNotIn('Source import failed', output)
        self.assertEqual((session['stop_reason'], session['exit_code'], session['unused']), (None, 0, []),
                         output[-2000:])
        self.assertEqual((session['used']['menu'], session['used']['layer_override']), (2, 1))
        self.assertIn('override not confirmed; aborting', output)
        seen = runner.launcher_network(folders['network'])
        self.assertGreater(seen['processes'], 0)
        self.assertEqual(seen['blocked'], 0)

    def test_every_child_python_denies_its_network_and_says_how_far(self):
        """The sealed sitecustomize, loaded from PYTHONPATH by a child Python, records the
        process and installs the observer's deny_network: an outside connection is refused and
        recorded, loopback is allowed. An interpreter without the HTTP clients keeps its socket
        layer denied and says so ('sockets'); the runner's own environment for the children
        carries it first on PYTHONPATH."""
        site, network = self.root / 'site', self.root / 'network'
        site.mkdir()
        network.mkdir()
        (site / 'sitecustomize.py').write_text(runner.sitecustomize_source(), encoding='utf-8')
        env = runner.launcher_environment(dict(os.environ), dict(child_environment=runner.LAUNCHER_CHILD_ENVIRONMENT),
                                          site, network, ROOT / 'tools', self.root)
        self.assertEqual(env['PYTHONPATH'], str(site))
        self.assertEqual(env['SHIMMER_MODEL_MODE'], 'base')
        attempt = ('import socket\ntry:\n    socket.create_connection(("192.0.2.1", 9), timeout=1)\n'
                   'except RuntimeError as exc:\n    print("REFUSED", exc)\n')

        def child(code, extra_path=None):
            run_env = dict(env, PYTHONPATH=os.pathsep.join([str(site)] + ([str(extra_path)] if extra_path else [])))
            return subprocess.run([sys.executable, '-c', code], env=run_env, capture_output=True, text=True, timeout=120,
                                  stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
        done = child(attempt)
        self.assertIn('REFUSED Diagnostic forbids network', done.stdout, done.stderr[-300:])
        seen = runner.launcher_network(network)
        self.assertEqual((seen['processes'], seen['denial_installed'], seen['blocked']), (1, 1, 1))
        shadow = self.root / 'shadow'
        shadow.mkdir()
        (shadow / 'requests.py').write_text('raise ImportError("no HTTP client in this interpreter")\n', encoding='utf-8')
        child(attempt, shadow)
        seen = runner.launcher_network(network)
        self.assertEqual((seen['processes'], seen['denial_installed'], seen['denial_sockets_only'], seen['blocked']),
                         (2, 1, 1, 2))

    def test_the_menu_environment_is_made_from_the_pinned_runtime(self):
        """project/.venv is a fresh environment with no pip whose .pth adds the runner's own
        site-packages, so the menu's Python imports the pinned packages with no install; an
        existing .venv is refused."""
        project = self.root / 'venv_project'
        project.mkdir()
        venv = runner.launcher_venv(project)
        python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        probe = subprocess.run([str(python), '-c', 'import requests, sys; print(sys.prefix)'], capture_output=True,
                               text=True, timeout=120, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
        self.assertEqual(probe.returncode, 0, probe.stderr[-300:])
        self.assertEqual(Path(probe.stdout.strip()).resolve(), venv.resolve())
        self.assertFalse(list(venv.rglob('pip')))
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            runner.launcher_venv(project)

    def test_the_assessment_needs_both_runs_their_deliverables_and_no_network(self):
        """Integrity only: one review run and one draft run, each reaching its end with exit 0
        and one pipeline_start and end; the run summary and the memo; the draft's context cleared;
        the children's network logged with the denial installed and no blocked attempt. A run
        whose semantic work is incomplete is recorded and does not fail the arm."""
        cases = [(dict(), []), (dict(memo=False), ['draft_memo_missing']), (dict(summary=False), ['review_run_summary_missing']),
                 (dict(review_runs=2), ['launcher_review_runs:2']), (dict(cleared=False), ['draft_context_not_cleared']),
                 (dict(blocked=2), ['launcher_network_attempts:2']),
                 (dict(network_logs=False), ['launcher_network_denial_incomplete']),
                 (dict(bootstrap_denial='installed'), []),
                 (dict(bootstrap_denial='partial'), ['launcher_network_denial_incomplete']),
                 (dict(pipeline_denial='sockets'), ['launcher_network_denial_incomplete'])]
        for k, (changes, reasons) in enumerate(cases):
            project, evidence, session = assessment_fixture(self.root / ('case%d' % k), **changes)
            result = runner.assess(None, [], arm='L', launcher=runner.launcher_observation(evidence, project, session))
            self.assertEqual(result['reasons'], reasons, changes)
            self.assertEqual(result['arm'], 'L')
            self.assertFalse(list((project / 'output' / 'runs').iterdir()))
        project, evidence, session = assessment_fixture(self.root / 'semantic', semantic=False)
        result = runner.assess(None, [], arm='L', launcher=runner.launcher_observation(evidence, project, session))
        self.assertEqual((result['reasons'], result['semantic_complete']), ([], dict(review=False, draft=False)))
        stopped = dict(session, stop_reason='unknown_prompt', unknown_prompt='Something?', exit_code=-15, unused=['menu'])
        project, evidence, _ = assessment_fixture(self.root / 'stopped')
        result = runner.assess(None, [], arm='L', launcher=runner.launcher_observation(evidence, project, stopped))
        self.assertEqual(result['reasons'][:3], ['launcher_stopped:unknown_prompt', 'launcher_exit_nonzero',
                                                 'launcher_answer_not_given:menu'])

    def test_arm_l_runs_as_one_bundle_and_the_stop_ends_the_menus_children(self):
        """The controller refuses an arm L bundle in a batch before any provider call, runs it as
        a single bundle on an authorization naming arm L, and its stop_workload phase ends the
        runner and then every process running from the remote project (the menu's shell and its
        children)."""
        self.need_launcher_files()
        harness = self.harness()
        placed, block = launcher_block()
        files = dict({runner.LAUNCHER_SCRIPT: 'f' * 64}, **{n: 'e' * 64 for n in placed})
        with patch.object(controller, 'ROOT', self.root):
            harness.make_bundle(self.base, self.root / 'assets.tar', arm='L', launcher=block, project_files=files,
                                argv=runner.LAUNCHER_ARGV)
        entries = [dict(item='i1', arm='L', bundle=self.base)]
        with self.assertRaisesRegex(RuntimeError, 'Arm L runs as a single bundle'):
            self.execute(plan=harness.fixture_plan(self.ledger, batch=entries))
        self.assertIsNone(harness.FakeProvider.state)
        transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        self.assertEqual(read(self.base / 'operator_authorization.json')['arm'], 'L')
        stop = decoded_phase_script(transport, 'stop_workload')
        self.assertIn("pkill -TERM -f '%s/[o]rdinary_final_run.py'" % controller.REMOTE, stop)
        self.assertIn("pkill -TERM -f '%s/[p]roject/'" % controller.REMOTE, stop)


def launcher_status_without_the_transcript(target, result):
    return dict(transcript=False, answers=0, answer_ids=[], seconds=None, session={}, runs={}, network={}, context={},
                semantic={})


def stop_command_without_the_project(remote):
    return "pkill -TERM -f '" + remote + "/[o]rdinary_final_run.py' || true"


def record_with_every_deliverable(folder, task):
    return dict(_ORIGINAL_RUN_RECORD(folder, task), run_summary=True, memos=1)


def network_seen_as_clean(folder):
    return dict(_ORIGINAL_NETWORK(folder), blocked=0, blocked_kinds=[])


def network_with_every_pipeline_installed(folder):
    value = _ORIGINAL_NETWORK(folder)
    return dict(value, pipelines_installed=value['pipelines'])


def environment_without_the_denial(environ, declaration, site, network, observer, tmp):
    env = _ORIGINAL_ENVIRONMENT(environ, declaration, site, network, observer, tmp)
    env.pop('PYTHONPATH', None)
    return env


def archive_without_the_preflights_import(names, extra=(), extras=None):
    """The sealer's archive less one module the menu's runtime check imports (through the
    preflight), the shape of L14's gap."""
    return [n for n in _ORIGINAL_ARCHIVE_NAMES(names, extra, extras) if n != 'scripts/run_choices.py']


_ORIGINAL_RUN_RECORD = runner.launcher_run_record
_ORIGINAL_ARCHIVE_NAMES = sealer.archive_names
_ORIGINAL_NETWORK = runner.launcher_network
_ORIGINAL_ENVIRONMENT = runner.launcher_environment
_ORIGINAL_PROMPTS = sealer.launcher_prompts
_ORIGINAL_SITECUSTOMIZE = runner.sitecustomize_source

# (test, owner, attribute, mutant): each rule's neutralisation; the test must fail under it.
LAUNCHER_NEUTRALIZATIONS = [
    # The sealed block not validated: any block, any child environment, admitted.
    ('test_an_arm_l_bundle_is_admitted_only_with_its_sealed_launcher_block', runner, 'launcher_declaration',
     lambda manifest: manifest.get('launcher')),
    # Arm L admitted in a sealed run.
    ('test_an_arm_l_bundle_runs_exposed_only', runner, 'launcher_exposed', lambda arm, exposure: True),
    # The prompts not held to the bound sources.
    ('test_every_sealed_prompt_is_printed_word_for_word_by_the_bound_sources', runner, 'launcher_prompt_error',
     lambda prompts, sources: None),
    # The wizard's target question answered 'all' (every document reviewed, the grounding lost).
    ('test_the_sealer_maps_the_workload_as_the_wizard_lists_it', sealer, 'launcher_prompts',
     lambda question, targets_answer, prior_answer: _ORIGINAL_PROMPTS(question, 'all', None)),
    # Every occurrence of a prompt answered with its first answer.
    ('test_the_session_answers_only_from_the_map_and_stops_on_anything_else', runner.PromptMap, 'answer',
     lambda self, entry: entry['answers'][0]),
    # The waiting line never read, so an unknown prompt is never seen and the session hangs.
    ('test_the_session_answers_only_from_the_map_and_stops_on_anything_else', runner, 'last_segment', lambda text: ''),
    # A silent session never stopped, so a prompt the map cannot see holds it to the deadline.
    ('test_the_session_answers_only_from_the_map_and_stops_on_anything_else', runner, 'session_idle',
     lambda silent, idle_after: False),
    # The children started without the network-denying sitecustomize.
    ('test_the_real_menu_runs_a_review_then_a_draft_from_the_map', runner, 'launcher_environment',
     environment_without_the_denial),
    # Any workload sealed into arm L, its redaction rules unread.
    ('test_arm_l_is_sealed_only_for_a_workload_with_no_redaction_rule', sealer, 'launcher_sensitivity_error',
     lambda conventions: None),
    # The project archive missing a module the menu's startup imports (L14).
    ('test_the_real_menu_starts_from_the_project_archive_the_sealer_builds', sealer, 'archive_names',
     archive_without_the_preflights_import),
    # The analyser's row written without reading the collected session.
    ('test_the_real_menu_runs_a_review_then_a_draft_from_the_map', analysis, 'launcher_status',
     launcher_status_without_the_transcript),
    # The children's sitecustomize that records the process but denies nothing.
    ('test_every_child_python_denies_its_network_and_says_how_far', runner, 'sitecustomize_source',
     lambda: _ORIGINAL_SITECUSTOMIZE().replace('cloud_run_observer.deny_network(rec)', 'pass', 1)),
    # The menu's environment made without the runner's runtime.
    ('test_the_menu_environment_is_made_from_the_pinned_runtime', runner, 'runtime_site_paths', lambda: []),
    # Every run taken to have written its deliverables.
    ('test_the_assessment_needs_both_runs_their_deliverables_and_no_network', runner, 'launcher_run_record',
     record_with_every_deliverable),
    # The children's blocked attempts not counted.
    ('test_the_assessment_needs_both_runs_their_deliverables_and_no_network', runner, 'launcher_network',
     network_seen_as_clean),
    # A pipeline process whose HTTP clients were never denied taken as denied in full.
    ('test_the_assessment_needs_both_runs_their_deliverables_and_no_network', runner, 'launcher_network',
     network_with_every_pipeline_installed),
    # An arm L bundle admitted into a batch.
    ('test_arm_l_runs_as_one_bundle_and_the_stop_ends_the_menus_children', controller, 'single_bundle_arm',
     lambda m, plan: True),
    # The stop ends the runner only, leaving the menu's children running.
    ('test_arm_l_runs_as_one_bundle_and_the_stop_ends_the_menus_children', controller, 'stop_command',
     stop_command_without_the_project),
]
NAMES = sorted({name for name, _owner, _attribute, _mutant in LAUNCHER_NEUTRALIZATIONS})


def check():
    """Gate check 311: every arm L test passes, and each neutralisation makes its test fail,
    then the restored code passes again. SKIP when the tree holds no shimmer.sh (the container
    image) or no bash runs a script."""
    import io
    import ordinary_final_controller_checks as checks

    def outcome(name):
        result = unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(checks.ControllerChecks(name))
        return ('skip' if result.skipped else 'pass' if result.wasSuccessful() else 'fail'), result
    if not (ROOT / runner.LAUNCHER_SCRIPT).is_file():
        return 'SKIP', 'no shimmer.sh in this tree (the container image ships no launcher)'
    failed = []
    skipped = []
    for name in NAMES:
        state, result = outcome(name)
        if state == 'skip':
            skipped.append(name)
        elif state == 'fail':
            failed.append('%s: %s' % (name, (result.failures + result.errors)[0][1].strip().splitlines()[-1][:200]))
    if failed:
        return 'FAIL', 'arm L check failed: ' + '; '.join(failed)
    proofs = []
    for name, owner, attribute, mutant in LAUNCHER_NEUTRALIZATIONS:
        if name in skipped:
            continue
        calls = []

        def replacement(*args, _mutant=mutant, **kwargs):
            calls.append(1)
            return _mutant(*args, **kwargs)
        with patch.object(owner, attribute, replacement):
            neutralised, _ = outcome(name)
        restored, _ = outcome(name)
        if not (neutralised == 'fail' and calls and restored == 'pass'):
            return 'FAIL', 'neutralising %s.%s did not fail %s and restore (%s, %d calls, %s)' % (
                getattr(owner, '__name__', owner), attribute, name, neutralised, len(calls), restored)
        proofs.append(attribute)
    detail = ('%d arm L tests, %d neutralisations each failing its test and restored: the sealed launcher block, exposed '
              'only, prompts word for word in the bound sources, the wizard\'s numbering, the session answering only '
              'from the map and stopping otherwise, the real menu and wizard through a review then a draft with every '
              'child network-denied, the real menu, preflight, wizard and pipeline started from an extracted sealed '
              'arm L project archive, arm L sealed only for a workload with no operator redaction rule, the menu environment from the runtime, the assessment, a single bundle and the '
              'stop of the menu\'s children' % (len(NAMES) - len(skipped), len(proofs)))
    if skipped:
        return 'SKIP', detail + '; skipped here: ' + ', '.join(skipped)
    return 'PASS', detail
