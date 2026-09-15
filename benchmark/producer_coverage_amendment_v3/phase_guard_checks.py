"""Synthetic-only guard checks; never consult authored or historical artifacts."""
import hashlib
import json
from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from access_guard import Guard, POLICY_ID, RELEASE_ID, PRE_GOLD, POST_GOLD_ONLY


def run_checks(workspace=None):
    workspace = Path(workspace or Path(__file__).resolve().parents[2]).resolve()
    fixtures = workspace / 'output/producer_coverage_amendment_v3/test_fixtures'
    fixtures.mkdir(parents=True, exist_ok=True)
    # Fixtures are retained for inspection, not deleted recursively.
    root = Path(tempfile.mkdtemp(prefix='guard-', dir=fixtures))
    base = root / 'benchmark/producer_coverage_amendment_v3'
    blind = base / 'blind_evidence'
    blind.mkdir(parents=True)
    evidence = blind / 'synthetic.txt'
    evidence.write_text('synthetic evidence', encoding='utf-8')
    target = root / 'output/producer_coverage_amendment_v3/test_fixtures/planted_targets.json'
    target.parent.mkdir(parents=True)
    target.write_text('{"synthetic_target": true}', encoding='utf-8')
    active = {'policy_id': POLICY_ID, 'release_id': RELEASE_ID}
    (base / 'ACTIVE_RELEASE.json').write_text(json.dumps(active), encoding='utf-8')
    freeze = {'policy_id': POLICY_ID, 'release_id': RELEASE_ID, 'active_release': active,
              'files': {evidence.relative_to(root).as_posix(): hashlib.sha256(evidence.read_bytes()).hexdigest()}}
    manifest = blind / 'PRE_GOLD_FREEZE.json'
    manifest.write_text(json.dumps(freeze), encoding='utf-8')
    committed = manifest.read_bytes()
    commit = 'a' * 40
    expected_ref = commit + ':' + manifest.relative_to(root).as_posix()
    def git_reader(ref):
        if ref != expected_ref:
            raise ValueError('Synthetic commit absent')
        return committed
    guard = Guard(root, base, git_reader)
    checks = []
    def reject(name, action):
        try:
            action()
        except (ValueError, FileNotFoundError, PermissionError):
            checks.append(name)
        else:
            raise AssertionError('Expected rejection: ' + name)
        assert guard.log['successful_target_reads'] == []
    assert guard.classify(target) == POST_GOLD_ONLY
    def assert_denied():
        try:
            guard._audit('open', (str(target), 'r', 0))
        except PermissionError:
            return
        raise AssertionError('Guard effect invariant did not reject synthetic target')
    assert_denied()
    original_classifier = guard.classify
    guard.classify = lambda path: PRE_GOLD
    try:
        try:
            assert_denied()
        except AssertionError:
            neutralization_detected = True
        else:
            neutralization_detected = False
    finally:
        guard.classify = original_classifier
    assert neutralization_detected
    assert_denied()
    checks.append('guard classification neutralize fail restore pass effect')
    reject('pre-gold target open', lambda: guard._audit('open', (str(target), 'r', 0)))
    reject('missing commit', lambda: guard.enable_post_phase(None))
    reject('nonhex commit', lambda: guard.enable_post_phase('z' * 40))
    reject('missing marker', lambda: guard.verify_post_phase(commit))
    wrong = dict(active, release_id='wrong-release')
    guard.active.write_text(json.dumps(wrong), encoding='utf-8')
    reject('wrong release', lambda: guard.enable_post_phase(commit))
    guard.active.write_text(json.dumps(active), encoding='utf-8')
    evidence.write_text('drift', encoding='utf-8')
    reject('hash drift', lambda: guard.enable_post_phase(commit))
    evidence.write_text('synthetic evidence', encoding='utf-8')
    guard.enable_post_phase(commit)
    guard._audit('open', (str(target), 'r', 0))
    assert json.loads(target.read_text(encoding='utf-8')) == {'synthetic_target': True}
    assert len(guard.log['authorized_target_open_attempts']) == 1
    assert guard.log['successful_target_reads'] == []
    checks.append('validated committed freeze permits synthetic target')
    # A real installed audit hook demonstrates denial before the OS can open.
    real = Guard(root, base, git_reader).install(PRE_GOLD)
    try:
        target.read_text(encoding='utf-8')
    except PermissionError:
        checks.append('installed hook blocks before actual open')
    else:
        raise AssertionError('Installed hook permitted target')
    real.enable_post_phase(commit)
    assert 'synthetic_target' in target.read_text(encoding='utf-8')
    assert len(real.log['successful_target_reads']) == 1
    assert real.log['first_actual_target_read_at']
    checks.append('installed hook permits validated synthetic target')
    marker_text = real.marker.read_text(encoding='utf-8')
    real.marker.write_text('{}', encoding='utf-8')
    try:
        target.read_text(encoding='utf-8')
    except ValueError:
        checks.append('tampered marker rejected before target open')
    else:
        raise AssertionError('Tampered marker permitted target')
    assert len(real.log['successful_target_reads']) == 1
    real.marker.write_text(marker_text, encoding='utf-8')
    real.enable_post_phase(commit)
    evidence.write_text('post-authorization drift', encoding='utf-8')
    try:
        target.read_text(encoding='utf-8')
    except ValueError:
        checks.append('post-authorization drift rejected before target open')
    else:
        raise AssertionError('Drift permitted target')
    assert len(real.log['successful_target_reads']) == 1
    return {'passed': len(checks), 'checks': checks, 'fixture_root': str(root)}


if __name__ == '__main__':
    print(json.dumps(run_checks(), indent=2))
