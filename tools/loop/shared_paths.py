"""The main checkout's shared folders, reached through configuration, never through a link (DELETE-SAFE-A).

After the 16 November 2026 data loss (operator 15:58, item 2) no working copy links into the main checkout. A
tool run from a worktree or a clone that needs the main checkout's docs/loop/private (the budget ledger the
reaper reads, the spend store, the private records), output/ (output/cloud_wheels, the pinned wheelhouse the
sealer reads) or external/ finds it here, by one rule:

1. SHIMMER_MAIN_CHECKOUT, when set and not empty, is the main checkout's root. It must be an absolute path to an
   existing folder that is not itself a link and holds a `.git` FOLDER (a main checkout; a worktree's `.git` is a
   file). Anything else is refused in one line, never guessed around, whatever `fallback` says.
2. Unset, the parent of git's common directory as seen from `start` (default: this checkout), the rule
   cloud_reference_spend.store_path and safe_delete.main_checkout already used. From a worktree that is the main
   checkout with nothing set; from a separate clone it is the clone, so a clone sets the variable.

A git failure raises MainCheckoutError, unless the caller names a `fallback` (a tool whose own checkout is the
right answer when git cannot be read, as before).

    py -3.12 -X utf8 tools/loop/shared_paths.py              # the root, how it was found, and each shared path
    py -3.12 -X utf8 tools/loop/shared_paths.py ledger       # one path: root, private, ledger, output, external, wheelhouse
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
from cloud_run_common import no_window  # noqa: E402  (HIDDEN-A: the git call opens no window)

ENV = 'SHIMMER_MAIN_CHECKOUT'
PRIVATE = ('docs', 'loop', 'private')
LEDGER_NAME = 'budget_ledger.jsonl'
WHEELHOUSE = 'ordinary_final_cp312'   # output/cloud_wheels/<name>: the ordinary final sealer's pinned wheelhouse
_UNSET = object()


class MainCheckoutError(Exception):
    """The main checkout cannot be named: a refused SHIMMER_MAIN_CHECKOUT, or git unreadable."""


def _is_link(path):
    text = str(path)
    return os.path.islink(text) or bool(getattr(os.path, 'isjunction', lambda p: False)(text))


def configured(environ=None):
    """The main checkout SHIMMER_MAIN_CHECKOUT names, checked; None when it is unset or empty."""
    value = str((os.environ if environ is None else environ).get(ENV) or '').strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        raise MainCheckoutError('%s must be an absolute path to the main checkout' % ENV)
    if _is_link(path):
        raise MainCheckoutError('%s names a link; name the main checkout itself' % ENV)
    if not path.is_dir():
        raise MainCheckoutError('%s names no folder' % ENV)
    if not (path / '.git').is_dir():
        raise MainCheckoutError('%s names no main checkout (its .git is not a folder)' % ENV)
    return path.resolve()


def from_git(start=None, runner=None):
    """The parent of git's common directory as seen from `start`."""
    runner = runner or subprocess.run
    try:
        done = runner(['git', '-C', str(start or HERE), 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                      capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL, creationflags=no_window())
    except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError) as exc:
        raise MainCheckoutError('The main checkout cannot be found from git (%s)' % type(exc).__name__)
    if done.returncode != 0 or not (done.stdout or '').strip():
        raise MainCheckoutError('The main checkout cannot be found from git')
    return Path(done.stdout.strip()).resolve().parent


def found(start=None, environ=None, runner=None, fallback=_UNSET):
    """(root, how): how is 'SHIMMER_MAIN_CHECKOUT', 'git' or 'fallback'."""
    path = configured(environ)
    if path is not None:
        return path, ENV
    try:
        return from_git(start, runner), 'git'
    except MainCheckoutError:
        if fallback is _UNSET:
            raise
        return Path(fallback), 'fallback'


def main_checkout(start=None, environ=None, runner=None, fallback=_UNSET):
    """The main checkout's root, by the one rule above."""
    return found(start, environ, runner, fallback)[0]


def private_dir(start=None, **kwargs):
    """docs/loop/private of the main checkout."""
    return main_checkout(start, **kwargs).joinpath(*PRIVATE)


def ledger(start=None, **kwargs):
    """The budget ledger the reaper reads: docs/loop/private/budget_ledger.jsonl of the main checkout."""
    return private_dir(start, **kwargs) / LEDGER_NAME


def output_dir(start=None, **kwargs):
    return main_checkout(start, **kwargs) / 'output'


def external_dir(start=None, **kwargs):
    return main_checkout(start, **kwargs) / 'external'


def wheelhouse(name=WHEELHOUSE, start=None, **kwargs):
    """output/cloud_wheels/<name> of the main checkout."""
    return output_dir(start, **kwargs) / 'cloud_wheels' / name


NAMES = {'root': main_checkout, 'private': private_dir, 'ledger': ledger, 'output': output_dir,
         'external': external_dir, 'wheelhouse': lambda: wheelhouse()}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv:
            if len(argv) != 1 or argv[0] not in NAMES:
                print('name one of: ' + ', '.join(NAMES))
                return 2
            print(NAMES[argv[0]]())
            return 0
        root, how = found()
        print('main checkout: %s (from %s)' % (root, how))
        for key in ('private', 'ledger', 'output', 'external', 'wheelhouse'):
            print('%s: %s' % (key, NAMES[key]()))
        return 0
    except MainCheckoutError as exc:
        print(str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
