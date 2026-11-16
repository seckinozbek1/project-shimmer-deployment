"""The one way the loop deletes a folder or file (D-696, standing order 96; after the 16 Nov 2026 data loss).

A recursive delete on Windows can follow an NTFS junction or a symlink and delete its target outside the folder
being removed. This helper never does. It works in two steps:

    py -3.12 -X utf8 tools/loop/safe_delete.py PATH [PATH ...]            # dry run: prints every real path
    py -3.12 -X utf8 tools/loop/safe_delete.py --execute PATH [PATH ...]  # deletes, only if the dry run is clean

Rules, checked before anything is removed:
- Every path is walked without ever entering a link. A path that is itself a link, or that contains any junction or
  symlink anywhere inside, is REFUSED as a whole: the links must first be removed one by one as links
  (`unlink_only`), and the caller runs the dry run again.
- Every file and folder that would be removed is resolved to its real path and must lie inside the given path.
- A path under a protected root (the main checkout's docs/loop/private, output and external, and the role folders)
  is refused unless it is strictly below that root and the caller passes --allow-under-protected.
- Hard links: a file with more than one link is reported; removing it only removes this name.
Nothing is deleted when any check fails. The exit code is 0 for a clean run, 2 for a refusal.
"""
import argparse
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shared_paths  # noqa: E402


def main_checkout():
    """The main checkout, also when this file runs from a worktree: shared_paths' one rule (SHIMMER_MAIN_CHECKOUT,
    else the common git directory's parent), this file's own checkout when git cannot be read. A refused
    SHIMMER_MAIN_CHECKOUT raises, so nothing is checked against a guessed root."""
    here = Path(__file__).resolve().parents[2]
    return shared_paths.main_checkout(here, fallback=here)


MAIN = main_checkout()
PROTECTED = [MAIN / 'docs' / 'loop' / 'private', MAIN / 'output', MAIN / 'external',
             MAIN.parent / 'shimmer-roles']


def is_link(path):
    p = str(path)
    return os.path.islink(p) or os.path.isjunction(p)


def scan(root):
    """Walk root without entering links. Returns (links, entries) where entries are (path, is_dir, nlink)."""
    root = Path(root)
    links, entries = [], []
    if is_link(root):
        return [root], []
    if not root.exists():
        return [], []
    if root.is_file():
        return [], [(root, False, os.stat(root, follow_symlinks=False).st_nlink)]
    stack = [root]
    while stack:
        d = stack.pop()
        entries.append((d, True, 1))
        with os.scandir(d) as it:
            for e in it:
                p = Path(e.path)
                if e.is_symlink() or os.path.isjunction(e.path):
                    links.append(p)
                elif e.is_dir(follow_symlinks=False):
                    stack.append(p)
                else:
                    entries.append((p, False, e.stat(follow_symlinks=False).st_nlink))
    return links, entries


def inside(child, parent):
    try:
        Path(os.path.realpath(child)).relative_to(Path(os.path.realpath(parent)))
        return True
    except ValueError:
        return False


def check(root, allow_under_protected=False):
    """Return (problems, entries) for one root. No problem means the delete may go ahead."""
    problems = []
    root = Path(os.path.abspath(root))
    for prot in PROTECTED:
        real_root, real_prot = os.path.realpath(root), os.path.realpath(prot)
        if real_root == real_prot or inside(prot, root):
            problems.append('protected root %s is the path or inside it' % prot)
        elif inside(root, prot) and not allow_under_protected:
            problems.append('path is under the protected root %s (pass --allow-under-protected)' % prot)
    if problems:
        return problems, []          # a protected path is refused before anything is walked
    links, entries = scan(root)
    for link in links:
        problems.append('link inside: %s -> %s (remove the link alone first)' % (link, os.readlink(link)))
    for path, _, _ in entries:
        if not inside(path, root):
            problems.append('real path outside the target: %s' % os.path.realpath(path))
    return problems, entries


def unlink_only(link):
    """Remove one junction or symlink itself, never its target."""
    p = str(link)
    if not is_link(p):
        raise ValueError('not a link: %s' % p)
    if os.path.isjunction(p) or os.path.isdir(p):
        os.rmdir(p)          # removes the reparse point only
    else:
        os.unlink(p)
    if os.path.lexists(p):
        raise OSError('link still present: %s' % p)


def delete(entries):
    for path, is_dir, _ in sorted(entries, key=lambda x: len(x[0].parts), reverse=True):
        if is_link(path):
            raise OSError('a link appeared during the delete: %s' % path)
        if is_dir:
            os.rmdir(path)
        else:
            os.chmod(path, stat.S_IWRITE)
            os.unlink(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--allow-under-protected', action='store_true')
    args = ap.parse_args(argv)
    plan, refused = [], False
    for raw in args.paths:
        problems, entries = check(raw, args.allow_under_protected)
        files = sum(1 for e in entries if not e[1])
        size = sum(os.stat(e[0], follow_symlinks=False).st_size for e in entries if not e[1])
        multi = sum(1 for e in entries if not e[1] and e[2] > 1)
        print('%s: %d files, %d folders, %d bytes, %d hard-linked files' % (raw, files, len(entries) - files, size, multi))
        for e in entries:
            print('  real', os.path.realpath(e[0]))
        for p in problems:
            print('  REFUSED', p)
        refused = refused or bool(problems)
        plan.append(entries)
    if refused:
        print('nothing deleted')
        return 2
    if not args.execute:
        print('dry run only; nothing deleted')
        return 0
    for entries in plan:
        delete(entries)
    print('deleted')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
