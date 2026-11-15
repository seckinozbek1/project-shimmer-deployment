"""Private off-laptop backup of every local branch and tag (D-612, issue #267).

Pushes the main checkout's local branches and tags to a PRIVATE GitHub repository under its own
remote name, `backup-private`. The public origin is never used or changed.

    py -3.12 -X utf8 tools/loop/backup_private.py --setup <url>   # add the remote, once
    py -3.12 -X utf8 tools/loop/backup_private.py --dry-run       # everything except the push
    py -3.12 -X utf8 tools/loop/backup_private.py                 # the backup

Rules, each in code:
1. The remote is refused if it is named origin, if its URL equals origin's, or if its URL names
   project-shimmer-deployment (`remote_refusal`). `--setup` refuses the same, and an existing remote.
2. Before EVERY push the remote's URLs are read again (`target`: exactly one URL, fetch equal to push,
   `remote_refusal` on it), the target's visibility is read with `gh api repos/<owner>/<repo>
   --jq .private,.visibility`; the push is refused unless it reads `true` and `private`. An API
   failure, an unreadable URL or any other answer refuses (`visibility_refusal`), the URLs are read once more
   (`url_stable`: a change during the read refuses) and the push goes to that exact URL, not the name.
3. For each ref pushed, the range is what backup-private already has (its refs, as `git ls-remote`
   reads them), or refs/remotes/origin/main for a first push. The range's added lines go through
   the key patterns of CLAUDE.md (`PATTERNS`), its archives and refused
   paths through guard_secrets' archive and path refusals. A hit refuses that ref and is reported as
   file:line and pattern name, never by value (`secret_refusals`).
4. Large data stays out: a ref whose range adds a blob over `MAX_BLOB_BYTES` (50 MB), or any path
   under external/, output/ or seals/, or audit/model_replies/, is refused (`path_refusals`,
   `blob_refusals`).
5. One push per ref, `git push --no-follow-tags <url> <ref>:<ref>`, never --force, never --mirror, a tag at a
   time (`push_args`). Paths changed or moved in the range are read with --name-status (`changed_paths`).
6. Each run appends one JSON line to docs/loop/private/backup_log.jsonl of the main checkout: the
   time from the clock, the refs pushed, the refs refused with reasons and the visibility as read.
"""
from __future__ import annotations

import argparse
import os
import io
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'scripts'))
from cloud_run_common import no_window  # noqa: E402
import guard_secrets  # noqa: E402

REMOTE = 'backup-private'
PUBLIC_NAME = 'project-shimmer-deployment'
MAX_BLOB_BYTES = 50 * 1024 * 1024
ROOT_PREFIXES = ('external/', 'output/')
LOG = Path('docs') / 'loop' / 'private' / 'backup_log.jsonl'
GIT_TIMEOUT = 600
PATTERNS = (
    # Every alternative of the CLAUDE.md quick-scan grep, case-insensitive as `grep -iE` reads it.
    ('Anthropic key prefix', re.compile('sk-' + 'ant-', re.IGNORECASE)),
    ('OpenAI project key prefix', re.compile('sk-' + 'proj-', re.IGNORECASE)),
    ('OpenAI-style key of 20 characters', re.compile('sk-' + r'[a-zA-Z0-9]{20,}', re.IGNORECASE)),
    ('AKIA key', re.compile(r'AKIA[A-Z0-9]{16}', re.IGNORECASE)),
    ('AIza key', re.compile(r'AIza[A-Za-z0-9_-]{35}', re.IGNORECASE)),
    ('api_key assignment', re.compile(r"api_key\s*=\s*[\"'][A-Za-z0-9_-]{16,}", re.IGNORECASE)),
    ('secret assignment', re.compile(r"secret\s*=\s*[\"'][A-Za-z0-9_-]{16,}", re.IGNORECASE)),
)
ALLOWLIST = Path(__file__).with_name('backup_allowlist.json')


class BackupError(RuntimeError):
    pass


def scan_env():
    """The environment of every git call the tool makes: replace refs and objects are never read."""
    return dict(os.environ, GIT_NO_REPLACE_OBJECTS='1')


def run_git(root, *args, check=False):
    done = subprocess.run(['git', *args], cwd=str(root), stdin=subprocess.DEVNULL, capture_output=True, env=scan_env(),
                          text=True, encoding='utf-8', errors='replace', timeout=GIT_TIMEOUT,
                          creationflags=no_window())
    if check and done.returncode != 0:
        raise BackupError('git %s failed' % args[0])
    return done


def normal_url(url):
    """A URL in one comparable form: no scheme, credentials, .git suffix or trailing slash, lower case."""
    text = (url or '').strip().lower()
    text = re.sub(r'^[a-z+]+://', '', text)
    text = re.sub(r'^[^@/]*@', '', text)
    text = text.replace(':', '/', 1) if re.match(r'^[^/]+:[^/0-9]', text) else text
    return re.sub(r'(\.git)?/*$', '', text)


def remote_refusal(name, url, origin_urls):
    """Rule 1: why this remote may not be the backup target, or None."""
    if (name or '').strip().casefold() == 'origin':
        return 'the remote is named origin'
    if not url:
        return 'the remote has no URL'
    if PUBLIC_NAME in url.casefold():
        return 'the URL names %s' % PUBLIC_NAME
    if normal_url(url) in {normal_url(u) for u in origin_urls if u}:
        return "the URL equals origin's URL"
    return None


def origin_urls(root, git=run_git):
    urls = []
    for args in (('remote', 'get-url', '--all', 'origin'), ('remote', 'get-url', '--push', '--all', 'origin')):
        done = git(root, *args)
        if done.returncode == 0:
            urls += [line.strip() for line in done.stdout.splitlines() if line.strip()]
    return urls


def remote_urls(root, name, git=run_git):
    """(fetch URLs, push URLs) of a remote, every one of them."""
    found = []
    for args in (('remote', 'get-url', '--all', name), ('remote', 'get-url', '--push', '--all', name)):
        done = git(root, *args)
        if done.returncode != 0:
            return None
        found.append([line.strip() for line in done.stdout.splitlines() if line.strip()])
    return found


def rewrite_refusal(root, git=run_git):
    """Why the run is refused when any url.* config (insteadOf, pushInsteadOf, any scope) could rewrite the target."""
    done = git(root, 'config', '--get-regexp', r'^url\.')
    if done.returncode == 1 and not done.stdout.strip():
        return None
    if done.returncode == 0:
        return 'a url.* configuration exists and could rewrite the target'
    return 'url.* configuration could not be read'


def url_refusal(root, name, git=run_git):
    """(the one URL, refusal or None): exactly one fetch and one push URL, equal, and fit by `remote_refusal`."""
    why = rewrite_refusal(root, git)
    if why:
        return None, why
    urls = remote_urls(root, name, git)
    if urls is None:
        return None, 'the remote %s has no readable URL' % name
    fetch, push = urls
    if len(fetch) != 1 or len(push) != 1:
        return None, 'the remote has %d fetch and %d push URLs, not one each' % (len(fetch), len(push))
    if fetch[0] != push[0]:
        return None, 'the fetch URL and the push URL differ'
    return fetch[0], remote_refusal(name, fetch[0], origin_urls(root, git))


def target(root, name, git=run_git):
    return url_refusal(root, name, git)


def url_stable(root, name, url, git=run_git):
    """Whether the remote still has exactly the URL that was checked."""
    again, why = url_refusal(root, name, git)
    return why is None and again == url


def parse_repo(url):
    match = re.match(r'^(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([^/\s]+)/([^/\s]+?)(?:\.git)?/*$',
                     url or '', re.IGNORECASE)
    return (match.group(1), match.group(2)) if match else None


def gh_args(owner, repo):
    """The one gh call: github.com named, never the host a gh configuration prefers."""
    return ['gh', 'api', '--hostname', 'github.com', 'repos/%s/%s' % (owner, repo), '--jq', '.private,.visibility']


def gh_visibility(url, runner=subprocess.run):
    """(private, visibility) as `gh api` reads them for the URL's repository; raises on any failure."""
    repo = parse_repo(url)
    if repo is None:
        raise BackupError('the URL is not a GitHub repository URL')
    done = runner(gh_args(*repo), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
                  creationflags=no_window())
    if done.returncode != 0:
        raise BackupError('gh api failed (exit %d)' % done.returncode)
    lines = [line.strip() for line in done.stdout.splitlines() if line.strip()]
    if len(lines) != 2:
        raise BackupError('gh api answered in an unexpected form')
    return lines[0], lines[1]


def visibility_refusal(read, url):
    """Rule 2: (refusal or None, the visibility as read)."""
    try:
        private, visibility = read(url)
    except Exception as exc:  # noqa: BLE001 - any failure of the read refuses
        return 'visibility not read (%s)' % type(exc).__name__, 'not read'
    seen = '%s/%s' % (private, visibility)
    if str(private).lower() == 'true' and str(visibility).lower() == 'private':
        return None, seen
    return 'the target reads %s, not true/private' % seen, seen


def push_args(remote, sha, ref):
    """Rule 5: the one push form, through the remote name (the hook checks name and URL together; the tool has
    just confirmed that the name maps to the private URL), from the object id that was scanned (never the ref name,
    which can move). No force, no mirror, no plus, no tags that follow."""
    return ['push', '--no-follow-tags', remote, '%s:%s' % (sha, ref)]


def refs(root, git=run_git):
    """{refname: object id} of every local branch and tag."""
    done = git(root, 'for-each-ref', '--format=%(refname) %(objectname)', 'refs/heads', 'refs/tags')
    if done.returncode != 0:
        raise BackupError('git for-each-ref failed')
    return dict(line.split(' ', 1) for line in done.stdout.splitlines() if ' ' in line)


def remote_refs(root, url, git=run_git):
    done = git(root, 'ls-remote', url)
    if done.returncode != 0:
        raise BackupError('git ls-remote failed')
    found = {}
    for line in done.stdout.splitlines():
        sha, _, name = line.partition('\t')
        if name and not name.endswith('^{}'):
            found[name] = sha
    return found


def negatives(root, have, git=run_git):
    """The object ids the range starts after: what the backup holds (those this clone has), else origin/main."""
    known = [sha for sha in sorted(set(have.values()))
             if git(root, 'cat-file', '-e', sha + '^{commit}').returncode == 0 or
             git(root, 'cat-file', '-e', sha).returncode == 0]
    if known:
        return known
    verified = origin_main_base(root, git)
    return [verified] if verified else []


def origin_main_base(root, git=run_git):
    """The local refs/remotes/origin/main, but only when the public repository's own main still equals it
    (a read-only `git ls-remote origin refs/heads/main`); a mismatch or no answer gives None (no base)."""
    local = git(root, 'rev-parse', '--verify', '-q', 'refs/remotes/origin/main')
    if local.returncode != 0 or not local.stdout.strip():
        return None
    remote = git(root, 'ls-remote', 'origin', 'refs/heads/main')
    answer = remote.stdout.split()
    if remote.returncode != 0 or not answer or answer[0] != local.stdout.strip():
        return None
    return local.stdout.strip()


def replace_refusal(root, git=run_git):
    """Why the run is refused when the repository holds replace refs (they could hide what is scanned)."""
    done = git(root, 'for-each-ref', 'refs/replace')
    if done.returncode != 0:
        return 'replace refs could not be read'
    return 'the repository holds replace refs' if done.stdout.strip() else None


def run_input(root, args, text):
    return subprocess.run(['git', *args], cwd=str(root), input=text, capture_output=True, text=True, env=scan_env(),
                          encoding='utf-8', errors='replace', timeout=GIT_TIMEOUT, creationflags=no_window())


def parse_batch(done, count):
    """The lines of cat-file --batch-check, one per object asked for; a failure or a short answer raises."""
    lines = done.stdout.splitlines()
    if done.returncode != 0 or len(lines) != count:
        raise BackupError('git cat-file --batch-check failed or answered %d of %d' % (len(lines), count))
    return lines


def revs_input(tips, base):
    """The revisions for `git ... --stdin`: every tip, then every base negated."""
    return ''.join(tip + '\n' for tip in tips) + ''.join('^' + b + '\n' for b in base)


RAW = re.compile(r'^:(\d+) (\d+) ([0-9a-f]+) ([0-9a-f]+) ([A-Z])\d*\t(.*)$')


def raw_entries(root, tips, base):
    """[(commit, blob id, path or None, mode)] of every file each commit of the range adds or changes.
    A line that cannot be read, or a quoted path, becomes an entry with no path (fail closed)."""
    flags = ['-c', 'core.quotePath=false', 'log', '--raw', '--no-abbrev', '--no-renames', '-m',
             '--format=%x01%H', '--stdin']
    entries, commit = [], None
    for text in git_lines(root, flags, revs_input(tips, base)):
        if text.startswith('\x01'):
            commit = text[1:]
        elif text.strip():
            match = RAW.match(text)
            if not match or commit is None or match.group(6).startswith('"'):
                entries.append((commit, None, None, None))
            elif match.group(5) != 'D':
                entries.append((commit, match.group(4), match.group(6), match.group(2)))
    return entries


def changed_paths(entries):
    """[(commit, path)] of every path the range adds, modifies or moves to (a move is an add)."""
    return [(commit, path) for commit, _, path, _ in entries if path is not None]


def range_objects(root, tips, base, git=run_git, entries=None):
    """[(commit, blob id, size, path)] of the files the range adds. Every blob is sized, none skipped."""
    tips = [tips] if isinstance(tips, str) else tips
    entries = raw_entries(root, tips, base) if entries is None else entries
    wanted = [e for e in entries if e[2] is not None and e[3] != '160000']
    ids = sorted({e[1] for e in wanted})
    if not ids:
        return []
    checked = run_input(root, ['cat-file', '--batch-check=%(objecttype) %(objectname) %(objectsize)'],
                        '\n'.join(ids) + '\n')
    sizes = {}
    for line in parse_batch(checked, len(ids)):
        kind, sha, size = line.split(' ')
        sizes[sha] = int(size) if kind == 'blob' else None
    return [(commit, sha, sizes[sha], path) for commit, sha, path, _ in wanted if sizes.get(sha) is not None]


def path_refusal(path):
    normal = path.replace('\\', '/')
    if guard_secrets.is_refused_path(normal):
        return 'path %s must never leave the laptop (seals or saved replies)' % path
    if normal.casefold().startswith(ROOT_PREFIXES):
        return 'path %s is run data kept out of the backup' % path
    return None


def blob_refusal(size, path):
    if size > MAX_BLOB_BYTES:
        return 'blob %s adds %d MB over the %d MB limit' % (path, size // (1024 * 1024), MAX_BLOB_BYTES // (1024 * 1024))
    return None


def archive_refusal(root, sha, path, size):
    if not guard_secrets.is_archive_name(path):
        return None

    def raw():
        data = run_git_bytes(root, 'cat-file', 'blob', sha)
        return io.BytesIO(data)
    reason = guard_secrets.refusal_for(path, lambda: size, raw)
    return 'archive %s: %s' % (path, reason) if reason else None


def run_git_bytes(root, *args):
    done = subprocess.run(['git', *args], cwd=str(root), stdin=subprocess.DEVNULL, capture_output=True, env=scan_env(),
                          timeout=GIT_TIMEOUT, creationflags=no_window())
    if done.returncode != 0:
        raise BackupError('git %s failed' % args[0])
    return done.stdout


def path_refusals(root, blobs, paths=()):
    """Rules 3 (archives) and 4 (paths and size): [(commit, reason)]."""
    found = [(commit, reason) for commit, path in paths for reason in [path_refusal(path)] if reason]
    # Per-run, per-blob verdicts: keyed by content (blob id and path) inside this one call and dropped with it.
    # It is not a cache across runs (D-614 forbids those): nothing is written or read between runs.
    per_run_blob_verdicts = {}
    for commit, sha, size, path in blobs:
        reason = blob_refusal(size, path)
        if reason:
            found.append((commit, reason))
        if size <= MAX_BLOB_BYTES:
            if (sha, path) not in per_run_blob_verdicts:
                per_run_blob_verdicts[(sha, path)] = archive_refusal(root, sha, path, size)
            if per_run_blob_verdicts[(sha, path)]:
                found.append((commit, per_run_blob_verdicts[(sha, path)]))
    return found


PREFIX_RULES = {'Anthropic key prefix': 'sk-' + 'ant-', 'OpenAI project key prefix': 'sk-' + 'proj-'}
BARE_KEY_CHARS = 16


def bare_prefix(line, rule):
    """Whether every occurrence of the rule's prefix on the line is bare: followed by fewer than 16 key characters
    (letters, digits, underscore, hyphen), so it is prose about the prefix and not the start of a key."""
    prefix = PREFIX_RULES[rule]
    for match in re.finditer(re.escape(prefix), line, re.IGNORECASE):
        run = re.match(r'[A-Za-z0-9_-]*', line[match.end():]).group()
        if len(run) >= BARE_KEY_CHARS:
            return False
    return True


PROSE_SUFFIXES = ('.md', '.txt', '.log')


def is_prose_path(path):
    """Prose files: *.md, *.txt, *.log and anything under docs/. A bare key prefix in code is still a hit."""
    folded = (path or '').replace('\\', '/').casefold()
    return folded.endswith(PROSE_SUFFIXES) or folded.startswith('docs/')


def line_hits(line, prose=False):
    """The names of the key patterns of CLAUDE.md the line holds (never the matched text). In prose (a prose
    file, a commit or tag message) a prefix rule does not count a line that mentions the prefix only bare."""
    return [name for name, pattern in PATTERNS
            if pattern.search(line) and not (prose and name in PREFIX_RULES and bare_prefix(line, name))]


LOG_FLAGS = ['-c', 'core.quotePath=false', 'log', '-p', '--text', '--no-renames', '--no-color',
             '--no-ext-diff', '--no-textconv', '--format=%x01%H', '-m', '--stdin']
HUNK = re.compile(r'@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
UNKNOWN = '?'


def header_path(text):
    """The new path of a `+++ ` header, None for /dev/null; a quoted or odd path raises (fail closed)."""
    if text == '+++ /dev/null':
        return None
    if text.startswith('+++ b/') and not text.startswith('+++ b/"') and '\t' not in text:
        return text[6:]
    raise BackupError('a path in the diff cannot be read')


def scan_diff(lines):
    """[(commit, 'file:line pattern')] for each added line holding a key pattern in a unified diff given as text
    lines, each commit opened by a `\\x01<id>` line. Hunk lengths are counted, so a content line that looks like a
    header is read as content; a path that cannot be read marks its commit (fail closed)."""
    found, commit, path, number, old_left, new_left = [], UNKNOWN, None, 0, 0, 0
    for text in lines:
        if old_left > 0 or new_left > 0:
            if text.startswith('+'):
                for hit in line_hits(text[1:], is_prose_path(path)):
                    found.append((commit, '%s:%d %s' % (path, number, hit.split(':')[0])))
                number += 1
                new_left -= 1
            elif text.startswith('-'):
                old_left -= 1
            elif text.startswith(' ') or text == '':
                number += 1
                old_left -= 1
                new_left -= 1
            continue
        if text.startswith('\x01'):
            commit = text[1:]
        elif text.startswith('diff --git '):
            path = None
        elif text.startswith('+++ '):
            try:
                path = header_path(text)
            except BackupError:
                path = None
                found.append((commit, 'a path in the diff cannot be read'))
        elif text.startswith('@@'):
            match = HUNK.match(text)
            if not match:
                found.append((commit, 'a hunk header cannot be read'))
                continue
            old_left = int(match.group(1)) if match.group(1) is not None else 1
            number = int(match.group(2))
            new_left = int(match.group(3)) if match.group(3) is not None else 1
    return found


def git_lines(root, args, text=''):
    proc = subprocess.Popen(['git', *args], cwd=str(root), env=scan_env(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, creationflags=no_window())
    try:
        proc.stdin.write(text.encode('utf-8'))
        proc.stdin.close()
        for raw in proc.stdout:
            yield raw.decode('utf-8', errors='replace').rstrip('\n').rstrip('\r')
    finally:
        proc.stdout.close()
        if proc.wait() != 0:
            raise BackupError('git %s failed' % args[args.index('log') if 'log' in args else 0])


def secret_refusals(root, tips, base):
    """Rule 3: [(commit, 'file:line pattern name')] for each added line of the range holding a key pattern."""
    return scan_diff(git_lines(root, LOG_FLAGS, revs_input(tips, base)))


def message_refusals(root, tips, base):
    """Key patterns in the range's commit messages: [(commit, 'message line N pattern name')]."""
    found, sha, number = [], UNKNOWN, 0
    for text in git_lines(root, ['log', '--format=%x01%H%n%B', '-m', '--stdin'], revs_input(tips, base)):
        if text.startswith('\x01'):
            sha, number = text[1:], 0
            continue
        number += 1
        found += [(sha, 'message line %d %s' % (number, hit.split(':')[0])) for hit in line_hits(text, True)]
    return found


def commits_in(root, rev, base):
    """The set of commits a ref holds beyond the base."""
    return set(line for line in git_lines(root, ['rev-list', '--stdin'], revs_input([rev], base)) if line)


HIT = re.compile(r'^(.*):(\d+) (.*)$')


def load_allowlist(path=None):
    """[(path, blob id, rule, public)] from the committed allowlist; an entry without all of path, a 40-hex blob id,
    rule and a recorded reason is refused (the file is unusable: BackupError)."""
    path = Path(path or ALLOWLIST)
    if not path.is_file():
        return []
    entries = []
    for item in json.loads(path.read_text(encoding='utf-8')):
        if not (item.get('path') and item.get('rule') and str(item.get('reason', '')).strip()
                and re.fullmatch(r'[0-9a-f]{40}', str(item.get('blob', '')))):
            raise BackupError('an allowlist entry lacks its path, blob id, rule or reason')
        entries.append((item['path'], item['blob'], item['rule'], bool(item.get('public'))))
    return entries


def public_blobs(root, ids):
    """The ids of `ids` reachable from refs/remotes/origin/main (the public repository)."""
    wanted, found = set(ids), set()
    if not wanted:
        return found
    for line in git_lines(root, ['rev-list', '--objects', 'refs/remotes/origin/main']):
        head = line.split(' ', 1)[0]
        if head in wanted:
            found.add(head)
    return found


def usable_allowlist(root, entries):
    """{(path, blob, rule)} that may suppress a hit: an entry marked public only when its blob is in origin/main."""
    public = public_blobs(root, [blob for _, blob, _, flag in entries if flag])
    return {(path, blob, rule) for path, blob, rule, flag in entries if not flag or blob in public}


def commit_findings(root, tips, base, git=run_git, allowed=(), suppressed=None, hits=None):
    """{commit: [reasons]} for every commit of the union range (all tips at once, each commit read once).
    A content hit is dropped only when (its path, the blob that path holds in that commit, its rule) is in
    `allowed`; those dropped are listed in `suppressed`."""
    found = {}

    def add(commit, reason):
        found.setdefault(commit or UNKNOWN, []).append(reason)
    entries = raw_entries(root, tips, base)
    blob_of = {(commit, path): blob for commit, blob, path, _ in entries if path is not None}
    for commit, _, path, _ in entries:
        if path is None:
            add(commit, 'a path in the log cannot be read')
    for commit, reason in path_refusals(root, range_objects(root, tips, base, git, entries), changed_paths(entries)):
        add(commit, reason)
    for commit, where in secret_refusals(root, tips, base):
        match = HIT.match(where)
        if hits is not None and match:
            hits.append((commit, match.group(1), blob_of.get((commit, match.group(1))), match.group(3)))
        if match and (match.group(1), blob_of.get((commit, match.group(1))), match.group(3)) in allowed:
            if suppressed is not None:
                suppressed.append((commit, match.group(1), blob_of[(commit, match.group(1))], match.group(3)))
            continue
        add(commit, 'key pattern at %s' % where)
    for commit, where in message_refusals(root, tips, base):
        add(commit, 'key pattern in commit message, %s' % where)
    return found


def tag_refusals(root, ref, git=run_git, rev=None):
    """Key patterns in an annotated tag's own message (a lightweight tag has none)."""
    if not ref.startswith('refs/tags/'):
        return []
    kind = git(root, 'cat-file', '-t', rev or ref)
    if kind.returncode != 0:
        raise BackupError('git cat-file -t failed')
    if kind.stdout.strip() != 'tag':
        return []
    done = git(root, 'cat-file', 'tag', rev or ref)
    if done.returncode != 0:
        raise BackupError('git cat-file tag failed')
    return ['tag message line %d %s' % (n, hit.split(':')[0])
            for n, text in enumerate(done.stdout.splitlines(), 1) for hit in line_hits(text, True)]


def kind_refusal(root, ref, git=run_git, rev=None):
    """A ref must peel to a commit, and a tag must point at a commit itself, never at another tag."""
    rev = rev or ref
    peeled = git(root, 'cat-file', '-t', rev + '^{}')
    if peeled.returncode != 0 or peeled.stdout.strip() != 'commit':
        return 'the ref does not peel to a commit'
    if ref.startswith('refs/tags/'):
        kind = git(root, 'cat-file', '-t', rev)
        if kind.returncode != 0:
            return 'the tag type cannot be read'
        if kind.stdout.strip() == 'tag':
            body = git(root, 'cat-file', 'tag', rev)
            header = body.stdout.split('\n\n', 1)[0].split('\n') if body.returncode == 0 else []
            if 'type commit' not in header:
                return 'the tag does not point at a commit'
    return None


def ref_refusals(root, ref, base, git=run_git, rev=None, findings=None):
    """Refusals for one ref, every scan reading `rev` (the object id taken at the start), never the name.
    `findings` is the union scan; without it the ref is scanned alone."""
    rev = rev or ref
    why = kind_refusal(root, ref, git, rev)
    if why:
        return [why]
    if findings is None:
        findings = commit_findings(root, [rev], base, git)
    reasons = list(findings.get(UNKNOWN, []))
    own = set(findings) - {UNKNOWN}
    if own:
        held = commits_in(root, rev, base)
        for commit in sorted(own & held):
            reasons += ['%s (commit %s)' % (reason, commit[:8]) for reason in findings[commit]]
    reasons += ['key pattern in %s' % where for where in tag_refusals(root, ref, git, rev)]
    return reasons


def now_utc():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def append_log(root, record):
    path = Path(root) / LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(record, sort_keys=True) + '\n')


def backup(root, remote=REMOTE, dry_run=False, read=gh_visibility, now=now_utc, git=run_git, allow=True):
    """One backup run. Returns the log record (already appended)."""
    root = Path(root)
    record = {'time_utc': now(), 'remote': remote, 'dry_run': bool(dry_run), 'visibility': 'not read',
              'pushed': [], 'refused': [], 'unchanged': 0}
    try:
        url, why = target(root, remote, git)
        if why:
            record['refused'].append({'ref': '*', 'reasons': [why]})
            return record
        why = replace_refusal(root, git)
        if why:
            record['refused'].append({'ref': '*', 'reasons': [why]})
            return record
        have = remote_refs(root, url, git)
        base = negatives(root, have, git)
        todo = [(ref, sha) for ref, sha in sorted(refs(root, git).items(),
                                                  key=lambda item: (item[0] != 'refs/heads/main', item[0]))
                if have.get(ref) != sha]
        record['unchanged'] = len(refs(root, git)) - len(todo)
        tips = [sha for ref, sha in todo if kind_refusal(root, ref, git, sha) is None]
        findings, scan_error, suppressed = {}, None, []
        try:
            allowed = usable_allowlist(root, load_allowlist()) if allow else set()
            findings = commit_findings(root, tips, base, git, allowed, suppressed) if tips else {}
        except (BackupError, OSError, subprocess.SubprocessError) as exc:
            scan_error = 'scan failed: %s' % str(exc)[:120]
        record['allowlisted_hits'] = len(suppressed)
        for ref, sha in todo:
            try:
                reasons = [scan_error] if scan_error else ref_refusals(root, ref, base, git, sha, findings)
            except BackupError as exc:
                reasons = ['scan failed: %s' % str(exc)[:120]]
            if reasons:
                record['refused'].append({'ref': ref, 'reasons': reasons})
                continue
            again, why = target(root, remote, git)
            if not why and again != url:
                why = 'the remote URL changed during the run'
            if not why:
                why, seen = visibility_refusal(read, again)
                record['visibility'] = seen
            if not why and not url_stable(root, remote, url, git):
                why = 'the remote URL changed while its visibility was read'
            if why:
                record['refused'].append({'ref': ref, 'reasons': [why]})
                continue
            if dry_run:
                record['pushed'].append(ref)
                continue
            done = git(root, *push_args(remote, sha, ref))
            if done.returncode == 0:
                record['pushed'].append(ref)
            else:
                record['refused'].append({'ref': ref, 'reasons': ['push failed (exit %d)' % done.returncode]})
        if record['visibility'] == 'not read':
            record['visibility'] = visibility_refusal(read, url)[1]
    except (BackupError, OSError, subprocess.SubprocessError) as exc:
        record['refused'].append({'ref': '*', 'reasons': ['run stopped: %s' % str(exc)[:200]]})
    finally:
        append_log(root, record)
    return record


def setup(root, url, remote=REMOTE, git=run_git):
    """Add the remote; refused when one of that name exists, for the name origin and for origin's URL."""
    why = remote_refusal(remote, url, origin_urls(root, git))
    if why:
        raise BackupError('setup refused: %s' % why)
    listed = git(root, 'remote').stdout.split()
    if remote in listed:
        raise BackupError('setup refused: a remote named %s already exists' % remote)
    if git(root, 'remote', 'add', remote, url).returncode != 0:
        raise BackupError('git remote add failed')


ZERO = '0' * 40


def hook_scan(root, text, url=None, git=run_git):
    """The pre-push hook's scan (D-616): the lines git gives a pre-push hook (local ref, local sha, remote ref,
    remote sha) for a push to the backup. (0, '') when every pushed commit passes the same scans the backup run
    makes, with the D-614 allowlist; otherwise (1, one value-free line). A scan that cannot run is (1, reason).
    A delete (all-zero local sha) is never allowed, a tag object may not go to a branch, an annotated tag's
    message is scanned, and a repository with replace refs is refused."""
    try:
        rows = [line.split() for line in text.splitlines() if line.strip()]
        if not rows or any(len(row) != 4 for row in rows):
            return 1, 'the pushed refs could not be read'
        why = replace_refusal(root, git)
        if why:
            return 1, why
        tips = []
        for _, local_sha, remote_ref, _ in rows:
            if local_sha == ZERO:
                return 1, '%s: the hook never deletes a backup ref' % remote_ref
            if not remote_ref.startswith(('refs/heads/', 'refs/tags/')):
                return 1, 'a pushed ref is neither a branch nor a tag'
            why = kind_refusal(root, remote_ref, git, local_sha)
            if why:
                return 1, '%s: %s' % (remote_ref, why)
            if remote_ref.startswith('refs/heads/'):
                kind = git(root, 'cat-file', '-t', local_sha)
                if kind.returncode != 0 or kind.stdout.strip() != 'commit':
                    return 1, '%s: only a commit goes to a branch' % remote_ref
            where = tag_refusals(root, remote_ref, git, local_sha)
            if where:
                return 1, '%s: key pattern in %s' % (remote_ref, where[0])
            tips.append(local_sha)
        known = {sha for _, _, _, sha in rows if sha != ZERO}
        if url:
            try:
                known |= set(remote_refs(root, url, git).values())
            except BackupError:
                pass
        base = negatives(root, {sha: sha for sha in known}, git)
        findings = commit_findings(root, tips, base, git, usable_allowlist(root, load_allowlist()))
        if findings:
            first = sorted(findings)[0]
            return 1, '%d flagged commit(s), first %s: %s' % (len(findings), first[:8], findings[first][0][:160])
        return 0, ''
    except Exception as exc:  # noqa: BLE001 - a scan that cannot run refuses
        return 1, 'the scan could not run (%s)' % type(exc).__name__


def main(argv=None):
    parser = argparse.ArgumentParser(description='Back up all local branches and tags to a private repository.')
    parser.add_argument('--setup', metavar='URL', help='add the backup remote with this URL, once')
    parser.add_argument('--dry-run', action='store_true', help='do everything except the push')
    parser.add_argument('--remote', default=REMOTE, help='the remote name (default %s; never origin)' % REMOTE)
    parser.add_argument('--root', help='the main checkout (default: found through git)')
    parser.add_argument('--hook-scan', nargs='?', const='', metavar='URL',
                        help="pre-push hook mode: read git's pre-push lines on stdin and scan them (D-616)")
    args = parser.parse_args(argv)
    if args.hook_scan is not None:
        code, reason = hook_scan(Path.cwd(), sys.stdin.read(), args.hook_scan or None)
        if code:
            print('backup scan refused: %s' % reason)
        return code
    try:
        import session_end_salvage
        root = session_end_salvage.checked_root(args.root) if args.root else session_end_salvage.main_root()
        if args.setup:
            setup(root, args.setup, args.remote)
            print('remote %s added' % args.remote)
            return 0
        record = backup(root, args.remote, args.dry_run)
    except Exception as exc:  # noqa: BLE001
        print(str(exc))
        return 2
    print('backup %s: pushed %d, refused %d, unchanged %d, visibility %s' % (
        'dry run' if record['dry_run'] else 'run', len(record['pushed']), len(record['refused']),
        record['unchanged'], record['visibility']))
    for item in record['refused']:
        print('REFUSED %s: %s' % (item['ref'], '; '.join(item['reasons'])))
    return 1 if record['refused'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
