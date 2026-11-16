"""Proofs for tools/loop/safe_delete.py (D-696), each neutralise, fail, restore, pass, on a temporary folder with a
real NTFS junction (Windows) or symlink (elsewhere) pointing at a target outside the folder being deleted.

    py -3.12 -X utf8 tools/loop/safe_delete_checks.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import safe_delete as sd  # noqa: E402
from cloud_run_common import no_window  # noqa: E402  (on the path through shared_paths)


def make_link(link, target):
    if os.name == 'nt':
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], check=True, capture_output=True,
                       creationflags=no_window())   # HIDDEN-A
    else:
        os.symlink(target, link, target_is_directory=True)


def fixture(base):
    victim = base / 'victim'
    (victim / 'sub').mkdir(parents=True)
    (victim / 'sub' / 'a.txt').write_text('a')
    outside = base / 'outside'
    outside.mkdir()
    (outside / 'precious.txt').write_text('keep me')
    make_link(victim / 'sub' / 'link', outside)
    return victim, outside


def proof_refuses_link(base):
    victim, outside = fixture(base)
    problems, _ = sd.check(victim)
    assert any('link inside' in p for p in problems), problems
    assert sd.main([str(victim), '--execute']) == 2
    assert (outside / 'precious.txt').read_text() == 'keep me'
    assert (victim / 'sub' / 'a.txt').exists()


def proof_unlink_then_delete(base):
    victim, outside = fixture(base)
    sd.unlink_only(victim / 'sub' / 'link')
    assert (outside / 'precious.txt').read_text() == 'keep me'
    assert sd.main([str(victim)]) == 0 and victim.exists()          # dry run deletes nothing
    assert sd.main([str(victim), '--execute']) == 0
    assert not victim.exists()
    assert (outside / 'precious.txt').read_text() == 'keep me'


def proof_unlink_only_refuses_a_folder(base):
    victim, _ = fixture(base)
    try:
        sd.unlink_only(victim / 'sub')
    except ValueError:
        return
    raise AssertionError('unlink_only accepted a real folder')


def proof_protected_root(base):
    for prot in sd.PROTECTED:
        problems, _ = sd.check(prot)
        assert any('protected root' in p for p in problems), (prot, problems)
    problems, _ = sd.check(sd.MAIN)
    assert any('protected root' in p for p in problems), problems


def proof_main_checkout_from_configuration(base):
    """DELETE-SAFE-A (operator 16 Nov 2026 15:58, item 2): SHIMMER_MAIN_CHECKOUT names the main checkout whose
    folders are protected; a worktree named there (its .git a file) is refused, never guessed around."""
    import shared_paths
    main = base / 'main'
    (main / '.git').mkdir(parents=True)
    old = os.environ.get(shared_paths.ENV)
    try:
        os.environ[shared_paths.ENV] = str(main)
        assert sd.main_checkout() == main.resolve(), sd.main_checkout()
        lane = base / 'lane'
        lane.mkdir()
        (lane / '.git').write_text('gitdir: elsewhere\n')
        os.environ[shared_paths.ENV] = str(lane)
        try:
            sd.main_checkout()
        except shared_paths.MainCheckoutError:
            return
        raise AssertionError('a worktree named as the main checkout was accepted')
    finally:
        if old is None:
            os.environ.pop(shared_paths.ENV, None)
        else:
            os.environ[shared_paths.ENV] = old


PROOFS = [proof_refuses_link, proof_unlink_then_delete, proof_unlink_only_refuses_a_folder, proof_protected_root,
          proof_main_checkout_from_configuration]


def run(proof):
    with tempfile.TemporaryDirectory() as t:
        proof(Path(t))


def neutralised(proof, patch):
    """The proof must FAIL with the rule removed. patch() returns a restore function."""
    restore = patch()
    try:
        run(proof)
    except Exception:
        return True
    finally:
        restore()
    return False


def patch_attr(obj, name, value):
    def apply():
        old = getattr(obj, name)
        setattr(obj, name, value)
        return lambda: setattr(obj, name, old)
    return apply


def blind_scan(root):
    links, entries = ORIGINAL_SCAN(root)
    return [], entries


def blind_unlink(link):
    import shutil
    shutil.rmtree(link) if os.path.isdir(link) and not os.path.isjunction(str(link)) else os.rmdir(link)


ORIGINAL_SCAN = sd.scan
NEUTRALISE = {
    'proof_refuses_link': patch_attr(sd, 'scan', blind_scan),
    'proof_unlink_then_delete': patch_attr(sd, 'unlink_only', lambda link: None),
    'proof_unlink_only_refuses_a_folder': patch_attr(sd, 'is_link', lambda p: True),
    'proof_protected_root': patch_attr(sd, 'PROTECTED', []),
    # the variable ignored: the main checkout from git alone
    'proof_main_checkout_from_configuration': patch_attr(sd.shared_paths, 'configured', lambda environ=None: None),
}

if __name__ == '__main__':
    ok = 0
    for proof in PROOFS:
        run(proof)                                            # passes as built
        assert neutralised(proof, NEUTRALISE[proof.__name__]), proof.__name__ + ' still passes when neutralised'
        run(proof)                                            # passes again when restored
        ok += 1
    print('PASS %d proofs, each neutralise, fail, restore, pass' % ok)
