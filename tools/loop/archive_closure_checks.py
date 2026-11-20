"""Gate check 660 (tools/loop/archive_closure.py, GNN_TRAIN_6f48d5ed): the preflight proves every file a bundle's
workload will run or import is inside its project archive and refuses otherwise.

Fixture: a throwaway git repository with a stub sealer rule, a dispatcher with two lazy per-pass loaders, a pass
module whose trainer imports a tools module inside a function, names a tools builder by path, and imports an
optional tools module inside a try; a launch folder (launch.py COMMIT, requests.json for a B1 replay request). At
the first commit the sealer carries neither tools file: the folder is REFUSED (exit 1) naming exactly the two, the
optional import is listed and not refused, the other pass's tools import is latent and not refused, and an
import inside a function nothing calls is not followed. At the
second commit the sealer's RUNTIME_FILES lists both: COMPLETE (exit 0). On the repository itself, the rule read
from the sealer's constants equals the sealer's own archive_names on HEAD, and, where HEAD holds the GNN training
pass, its closure is complete. Neutralised (resolve finds nothing, so no import is followed): failed; restored,
passed.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (HERE, REPO / 'tools'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import archive_closure as ac  # noqa: E402

NO_WINDOW = ac.NO_WINDOW


class ProofFailed(AssertionError):
    pass


def need(cond, what):
    if not cond:
        raise ProofFailed(what)


SEALER_STUB = '''
RUNTIME_PREFIXES = ('scripts/', 'config/')
RUNTIME_FILES = %r
ARCHIVE_EXTRAS = ('benchmark/baselines/',)


def build(files, ROOT):
    for name in ('helper_numeric.py',):
        files['tools/' + name] = b''
    support_names = ['topology.json', 'runner_support.py']
'''
FILES = {
    'tools/prepare_cloud_run.py': "RUNTIME_MODULES_NAMED_LIKE_CHECKS = ()\n",
    'tools/helper_numeric.py': "X = 1\n",
    'tools/runner_support.py': "Y = 1\n",
    'benchmark/baselines/replay_prompts.py': (
        "import json\nimport reply_store\n\n\ndef _p_pass():\n    import p_pass\n    return p_pass\n\n\n"
        "def _other_pass():\n    import other_pass\n    return other_pass\n"),
    'benchmark/baselines/p_pass.py': 'SCHEMA = "p-pass-v1"\n\n\ndef run():\n    import trainer\n    return trainer\n',
    'benchmark/baselines/other_pass.py': 'SCHEMA = "other-pass-v1"\nimport other_only\n',
    'scripts/reply_store.py': "import runner_support\n",
    'scripts/libmod.py': 'def used():\n    return 1\n\n\ndef unused():\n    import never_tool\n    return never_tool\n',
    'tools/never_tool.py': "V = 1\n",
    'scripts/trainer.py': (
        'import libmod\nBUILDER = "tools/graph_builder.py"\n\n\ndef train():\n    libmod.used()\n'
        '    import overlap_tool\n    try:\n'
        '        import optional_tool\n    except ImportError:\n        optional_tool = None\n    return BUILDER\n'),
    'tools/overlap_tool.py': "import json\n",
    'tools/graph_builder.py': "import json\n",
    'tools/optional_tool.py': "Z = 1\n",
    'tools/other_only.py': "W = 1\n",
    'scripts/cfg_reader.py': "R = 1\n",
    'config/app.json': json.dumps({"reader": "cfg_reader:read"}),
}


def _git(root, *args):
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=gate', '-c', 'user.email=gate@example.invalid',
                    '-c', 'core.autocrlf=false', *args], check=True, capture_output=True, creationflags=ac.no_window())
    return subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True,
                          creationflags=ac.no_window()).stdout.strip() if args[0] == 'commit' else None


def _commit(root, runtime_files, message):
    (root / 'tools/prepare_ordinary_final_run.py').write_text(SEALER_STUB % (runtime_files,), encoding='utf-8')
    _git(root, 'add', '-A')
    return _git(root, 'commit', '-q', '-m', message)


def _folder(base, commit):
    folder = base / 'LAUNCH'
    (folder / 'work').mkdir(parents=True, exist_ok=True)
    (folder / 'work' / 'pass.json').write_text(json.dumps({"schema": "p-pass-v1"}), encoding='utf-8')
    (folder / 'launch.py').write_text("COMMIT = %r\n" % commit, encoding='utf-8')
    (folder / 'requests.json').write_text(json.dumps({"requests": [{"name": "FIXTURE_B1", "argv": [
        "--arm", "B1", "--replay-prompts", str(folder / 'work' / 'pass.json')]}]}), encoding='utf-8')
    return folder


def _main(folder, repo):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = ac.main(['folder', str(folder), '--repo', str(repo)])
    return rc, out.getvalue()


def proof_fixture():
    base = Path(tempfile.mkdtemp(prefix='shimmer_archive_closure_'))
    try:
        repo = base / 'repo'
        for name, text in FILES.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text, encoding='utf-8')
        _git(repo, 'init', '-q')
        first = _commit(repo, ('genesis.md',), 'without the tools files')
        result = ac.check_folder(_folder(base, first), repo)[0]
        need(result['missing'] == {'tools/overlap_tool.py': ['scripts/trainer.py']},
             'the import absent from the archive was not refused: %s' % result['missing'])
        need(result['missing_named'] == {'tools/graph_builder.py': ['scripts/trainer.py']},
             'the builder named by path was not refused: %s' % result['missing_named'])
        need(list(result['optional_missing']) == ['tools/optional_tool.py'], 'the optional import was not listed apart')
        need(list(result['latent']) == ['tools/other_only.py'], 'the other pass was not kept latent')
        need('scripts/cfg_reader.py' in result['followed'], 'the config-declared module:function was not followed')
        need('scripts/libmod.py' in result['followed'] and 'tools/never_tool.py' not in str(result),
             'an import inside a function nothing reaches was followed')
        rc, text = _main(base / 'LAUNCH', repo)
        need(rc == 1 and text.startswith('REFUSED FIXTURE_B1'), 'the preflight did not refuse (exit %d)' % rc)
        second = _commit(repo, ('genesis.md', 'tools/overlap_tool.py', 'tools/graph_builder.py'), 'with them')
        rc, text = _main(_folder(base, second), repo)
        need(rc == 0 and text.startswith('COMPLETE FIXTURE_B1'), 'the fixed rule was not complete (exit %d): %s'
             % (rc, text.splitlines()[:3]))
        return 'fixture refused the two absent tools files (exit 1), optional and latent apart; complete once carried'
    finally:
        shutil.rmtree(base, ignore_errors=True)


def proof_repository():
    head = subprocess.run(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], capture_output=True, text=True,
                          creationflags=ac.no_window()).stdout.strip()
    tree = ac.Tree(REPO, head)
    import prepare_ordinary_final_run as sealer
    own = set(sealer.archive_names(sorted(tree.names)))
    rule = ac.sealer_archive(tree)
    need(own <= rule, 'the constants rule drops a file the sealer archives: %s' % sorted(own - rule)[:3])
    helpers = set(ac._tool_helpers(tree.read(ac.SEALER).decode('utf-8')))
    extra = {n for n in rule - own if n.endswith('.py') and n not in helpers}
    need(not extra, 'the constants rule adds code the sealer does not: %s' % sorted(extra)[:3])
    entry = 'benchmark/baselines/ontology_train_pass.py'
    if entry not in tree.names:
        return 'rule equals the sealer on HEAD; HEAD holds no GNN training pass'
    result = ac.closure(tree, ac.sealer_archive(tree), ['benchmark/baselines/replay_prompts.py', entry],
                        ac.sealer_support(tree), 'benchmark/baselines/replay_prompts.py', entry)
    need(not result['missing'] and not result['missing_named'],
         'the GNN training pass at HEAD reaches files outside the archive: %s'
         % sorted(set(result['missing']) | set(result['missing_named'])))
    return 'rule equals the sealer on HEAD; the GNN training pass closure is complete (%d files)' % len(result['followed'])


def proof():
    return proof_fixture() + '; ' + proof_repository()


@contextlib.contextmanager
def _neutralised():
    original = ac.resolve
    ac.resolve = lambda module, level, importer, names: []
    try:
        yield
    finally:
        ac.resolve = original


def run_group(number=660):
    """(status, detail): shipped PASS, neutralised FAIL, restored PASS."""
    try:
        shipped = proof()
    except ProofFailed as exc:
        return 'FAIL', 'shipped: %s' % exc
    with _neutralised():
        try:
            proof_fixture()
            return 'FAIL', 'neutralised, the proof still passed: it proves nothing'
        except ProofFailed:
            pass
    try:
        proof_fixture()
    except ProofFailed as exc:
        return 'FAIL', 'restored: %s' % exc
    return 'PASS', '%s; neutralised, failed; restored, passed' % shipped


if __name__ == '__main__':
    status, detail = run_group()
    print('660 %s %s' % (status, detail))
    sys.exit(0 if status == 'PASS' else 1)
