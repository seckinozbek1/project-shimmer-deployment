"""Off-machine backup of the loop's private records and run outputs (D-697, standing order 96; Seckin 15:48).

The main checkout's docs/loop/private and output/ (without output/cloud_wheels, which is rebuilt from the
pinned requirements) are snapshotted into a separate git repository outside the main checkout,
<USER_HOME>/local/shimmer-history-backup/records, and pushed as one branch, `records/private`, to the private
remote `backup-private` (the same private GitHub repository tools/loop/backup_private.py uses).

    py -3.12 -X utf8 tools/loop/backup_records.py --dry-run   # everything except the push
    py -3.12 -X utf8 tools/loop/backup_records.py             # snapshot and push

How, so that nothing is copied, moved or deleted on disk:
- Each file is written into that repository's object store (`git hash-object -w --stdin-paths`) and a tree is
  built in a temporary index (`git update-index --index-info`, `git write-tree`); a commit on top of the previous
  snapshot (`git commit-tree`) names the time. The repository has no working tree.
- Links are never followed: a junction or symlink is skipped and listed.
- Every file is scanned for key bodies (a prefix followed by a key) and credential assignments whose value is not a placeholder; a file whose exact content is already a committed blob is not new; any other hit is held back, never pushed, and listed for review, and
  only its path is printed, never the match.
- Files over 50 MB are listed, not stored (GitHub's limit).
- A snapshot holding any path of a drive-only root (backup_coverage.drive_only_carried: a `roles/` path, or a
  file inside the roles root config/backup_extra_roots.json names) is refused before anything is stored: the
  role exchange folders and negotiation sets go to Drive only, never to git.
- The push is refused unless `gh api` reads the remote as private; it is a plain push, never forced.
- One line per run is appended to docs/loop/private/backup_log.jsonl: time, commit, counts, bytes, skipped.
"""
import argparse
import datetime as dt
import json
import re
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import backup_private as bp  # noqa: E402
import safe_delete  # noqa: E402

MAIN = safe_delete.MAIN
REPO = MAIN.parent / 'shimmer-history-backup' / 'records'
BRANCH = 'records/private'
SOURCES = [('private', MAIN / 'docs' / 'loop' / 'private', ()),
           ('output', MAIN / 'output', ('cloud_wheels',))]
MAX_BYTES = 50 * 1024 * 1024
SKIP_DIRS = ('__pycache__',)
# A key is a prefix followed by a key body; a mention of the prefix alone (in code, docs or logs of the guard
# itself) is not a key. An assignment counts unless its value reads as a placeholder.
STRICT = [('Anthropic key', re.compile('sk-' + 'ant-' + r'[A-Za-z0-9_-]{20,}')),
          ('OpenAI project key', re.compile('sk-' + 'proj-' + r'[A-Za-z0-9_-]{20,}')),
          ('OpenAI-style key', re.compile('sk-' + r'[A-Za-z0-9]{32,}')),
          ('AKIA key', re.compile(r'AKIA[A-Z0-9]{16}')),
          ('AIza key', re.compile(r'AIza[A-Za-z0-9_-]{35}'))]
ASSIGN = re.compile(r"(?:api_key|secret|token|password)\s*=\s*[\"']([A-Za-z0-9_-]{16,})", re.IGNORECASE)
NAME_FILE = MAIN / '.claude' / 'loop_private_patterns.txt'   # H5: names matched without spelling them
NAMES = [re.compile(r'(?i)(?<!lla)\x6d\x61\x61\x74(?!tention)')] + (
    [re.compile(x.strip()) for x in NAME_FILE.read_text(encoding='utf-8').splitlines() if x.strip()]
    if NAME_FILE.exists() else [])
PLACEHOLDER = re.compile(r'(test|fake|dummy|example|your|xxx|placeholder|sample|notreal|redacted)', re.IGNORECASE)
LOG = MAIN / 'docs' / 'loop' / 'private' / 'backup_log.jsonl'


def git(*args, inp=None, env=None):
    # stdin as raw bytes: in text mode Windows turns each newline into CR LF, and update-index then reads no line.
    done = subprocess.run(['git', '--git-dir', str(REPO), *args],
                          input=None if inp is None else inp.encode('utf-8'), capture_output=True,
                          env=env, timeout=1800, creationflags=bp.no_window())
    if done.returncode != 0:
        raise bp.BackupError('git %s failed: %s' % (args[0], done.stderr.decode('utf-8', 'replace').strip()[:200]))
    return done.stdout.decode('utf-8', 'replace')


def collect():
    """(files as (repo path, disk path, size), skipped links, skipped large files)."""
    files, links, large = [], [], []
    for prefix, root, excluded in SOURCES:
        stack = [root]
        while stack:
            d = stack.pop()
            with os.scandir(d) as it:
                for e in it:
                    if e.is_symlink() or os.path.isjunction(e.path):
                        links.append(e.path)
                        continue
                    rel = Path(e.path).relative_to(root).as_posix()
                    if d == root and e.name in excluded:
                        continue
                    if e.is_dir(follow_symlinks=False):
                        if e.name not in SKIP_DIRS:
                            stack.append(Path(e.path))
                        continue
                    size = e.stat(follow_symlinks=False).st_size
                    if size > MAX_BYTES:
                        large.append((prefix + '/' + rel, size))
                        continue
                    files.append((prefix + '/' + rel, e.path, size))
    return files, links, large


def committed(path):
    """True when the file's exact content is a blob in the main repository's history (scanned when committed)."""
    for args in (['hash-object', '--no-filters', path], ['hash-object', path]):
        done = subprocess.run(['git', '-C', str(MAIN), *args], capture_output=True, text=True,
                              creationflags=bp.no_window())
        sha = done.stdout.strip()
        if sha and subprocess.run(['git', '-C', str(MAIN), 'cat-file', '-e', sha], capture_output=True,
                                  creationflags=bp.no_window()).returncode == 0:
            return True
    return False


def secret_hits(files):
    hits = []
    for rel, path, _ in files:
        try:
            text = Path(path).read_bytes().decode('utf-8', errors='ignore')
        except OSError:
            continue
        if any(rx.search(text) for rx in NAMES):
            hits.append((rel, 'name pattern (H5)'))
            continue
        if not any(rx.search(text) for _, rx in STRICT) and not ASSIGN.search(text):
            continue
        if committed(path):
            continue
        for label, rx in STRICT:
            if rx.search(text):
                hits.append((rel, label))
                break
        else:
            if any(not PLACEHOLDER.search(v) for v in ASSIGN.findall(text)):
                hits.append((rel, 'credential assignment'))
    return hits


def drive_only_location():
    """The roles root the drive-only declaration names (config/backup_extra_roots.json), or None."""
    try:
        import backup_coverage as cov
        data = cov.load_extra_config()
        return cov.roles_location(MAIN, location=(data or {}).get('roots_location'))[0] if data else None
    except Exception:      # an unreadable declaration: the roles/ path rule alone still refuses
        return None


def snapshot(files):
    import backup_coverage as cov
    carried = cov.drive_only_carried(files, drive_only_location())
    if carried:      # the role exchange folders and negotiation sets go to Drive only, never to git
        raise bp.BackupError('%d files under a drive-only root; nothing stored or pushed' % len(carried))
    if not REPO.exists():
        REPO.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'init', '--bare', '-q', str(REPO)], check=True, creationflags=bp.no_window())
    shas = git('hash-object', '-w', '--stdin-paths', '--no-filters', inp='\n'.join(p for _, p, _ in files) + '\n').split()
    if len(shas) != len(files):
        raise bp.BackupError('hash-object returned %d of %d' % (len(shas), len(files)))
    with tempfile.TemporaryDirectory() as t:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(t) / 'index'))
        git('update-index', '--add', '--index-info',
            inp=''.join('100644 %s\t%s\n' % (s, rel) for (rel, _, _), s in zip(files, shas)), env=env)
        tree = git('write-tree', env=env).strip()
    stored = len(git('ls-tree', '-r', '--name-only', tree).splitlines())
    if stored != len(files):
        raise bp.BackupError('the snapshot tree holds %d of %d files; nothing pushed' % (stored, len(files)))
    try:
        parent = git('rev-parse', '--verify', '-q', 'refs/heads/' + BRANCH).strip()
    except bp.BackupError:
        parent = ''
    if parent and git('rev-parse', parent + '^{tree}').strip() == tree:
        return parent, False
    when = dt.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %z')
    msg = 'records snapshot %s: %d files\n' % (when, len(files))
    args = ['commit-tree', tree, '-m', msg] + (['-p', parent] if parent else [])
    env = dict(os.environ, GIT_AUTHOR_NAME='shimmer-loop', GIT_AUTHOR_EMAIL='loop@localhost',
               GIT_COMMITTER_NAME='shimmer-loop', GIT_COMMITTER_EMAIL='loop@localhost')
    commit = git(*args, env=env).strip()
    git('update-ref', 'refs/heads/' + BRANCH, commit)
    return commit, True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args(argv)
    files, links, large = collect()
    total = sum(s for _, _, s in files)
    print('files %d, bytes %d, links skipped %d, over 50 MB skipped %d' % (len(files), total, len(links), len(large)))
    for rel, size in large:
        print('  not stored (over 50 MB):', rel, size)
    hits = secret_hits(files)
    held = {rel for rel, _ in hits}
    for rel, label in hits:
        print('  HELD BACK, never pushed, for review: %s (%s)' % (rel, label))
    files = [f for f in files if f[0] not in held]
    total = sum(s for _, _, s in files)
    url, refusal = bp.target(MAIN, bp.REMOTE)
    seen = ''
    if not refusal:
        refusal, seen = bp.visibility_refusal(bp.gh_visibility, url)
    print('remote visibility:', seen or 'not read')
    if refusal:
        print('REFUSED:', refusal)
        return 2
    if args.dry_run:
        print('dry run; nothing stored or pushed')
        return 0
    commit, new = snapshot(files)
    if not bp.url_stable(MAIN, bp.REMOTE, url):
        print('REFUSED: the backup-private URL changed during the run')
        return 2
    push = subprocess.run(['git', '--git-dir', str(REPO), 'push', url, '%s:refs/heads/%s' % (commit, BRANCH)],
                          capture_output=True, text=True, timeout=1800, creationflags=bp.no_window())
    pushed = push.returncode == 0
    line = {'time': dt.datetime.now().astimezone().isoformat(timespec='seconds'), 'tool': 'backup_records',
            'branch': BRANCH, 'commit': commit, 'new_snapshot': new, 'files': len(files), 'bytes': total,
            'skipped_links': len(links), 'skipped_large': len(large), 'held_back_for_review': sorted(held),
            'pushed': pushed}
    with LOG.open('a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(line) + '\n')
    print(json.dumps(line))
    if not pushed:
        print('push failed:', push.stderr.strip()[:300])
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
