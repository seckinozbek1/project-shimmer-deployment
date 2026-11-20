"""D-827: the deletion counterpart of tools/loop/fs_listing.py. One guarded loop launch that deletes named
project archives from the persistent file system `shimmer-filesystem`, ONE EXACT FILE AT A TIME.

It reuses fs_listing's pieces unchanged: the plan check and own cap (`check_plan`, `own_cap_refusal`, at most
the per-step pre-approval read from config/loop_spend_limits.json at call time), the cheapest x86_64
single-GPU type in us-east-1, the budget guard's decision under the ledger lock with the inventory read again,
the ledger lines (`launch_intent` with its deadline before the launch request, `launch`, `termination` with
billed minutes and cost, through `loop_budget_guard.ledger_line`), the provider adapter, the temporary ssh key
registered and removed, termination confirmed in a finally block, and a pinned command set
(`TEMPLATES_SHA256`). Purpose `fs-trim`, instance `shimmer-loop-fs-trim-<UTC time>`, default cap 1 USD,
deadline 30 minutes.

Input: `--list FILE`, a JSON array of {"path": "projects/project-<hex>.tar.gz", "bytes": N}, 1 to 200 entries.
The lead hands it only the files both D-827 checkers marked SAFE. Before any provider call every entry is
validated: under `projects/` and nowhere else, one plain `project-<hex>.tar.gz` name of [A-Za-z0-9_.-]+, no
`..`, no further `/`, no wildcard, no never-touch name (`assets-*`, `image/*`, anything at the mount root),
bytes a positive integer, no repeat. Anything else refuses the whole run.

The fixed script goes on ssh's standard input to the one remote command `bash -s`, as one brace group, never on
the command line (the 20 Nov 10:06 run's script was cut near 8 KB by the Windows ssh client and never reached
its loop). On the instance it prints `df -B1` of the mount, writes the validated list to a temporary file with
one `printf` (validated names only, each quoted), prints the list's line count and stops with LIST_SHORT before
the loop unless it is the entry count, then for each entry: a link is SKIP_LINK (`test -L`),
an absent file SKIP_MISSING, a non-regular file SKIP_NOT_FILE, a `stat -c %s` size other than the listed
bytes SKIP_SIZE; only then `rm -f --` of that exact path, DELETED once it is gone (FAILED if it is not).
No glob, no -r, no find -delete. Then `df -B1` again. A TRY line goes out before each file is touched and
the loop stops itself before the local timeout; a command cut by the timeout or a lost connection keeps its
partial output, so every entry ends as an outcome, `in_flight` (may be deleted) or `not_tried` (untouched). The output and a summary (deleted count and bytes,
skips by reason, df before and after) go under the main checkout's docs/loop/private/fs_trim/<instance>/.

    py -3.12 -X utf8 tools/loop/fs_trim.py --list safe.json            # dry run: list, script, forecast
    py -3.12 -X utf8 tools/loop/fs_trim.py --list safe.json --execute  # the one launch

Proofs: tools/loop/fs_trim_checks.py (fixtures, a fake provider and a fake ssh; check 661).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fs_listing as fsl  # noqa: E402  (puts tools/ on the path too)
from fs_listing import (guard, credential_locations, utc, record, terminate_confirmed,  # noqa: E402
                        generate_key, real_provider, cheapest_type, check_plan, own_cap_refusal, awake, save)

PURPOSE = 'fs-trim'
FILESYSTEM_NAME = fsl.FILESYSTEM_NAME
MOUNT = fsl.MOUNT
REGION = fsl.REGION
IMAGE_FAMILY = fsl.IMAGE_FAMILY
PROJECTS = 'projects/'
DEFAULT_CAP_USD = 1.0
# 20 Nov 09:32 run (shimmer-loop-fs-trim-20261120t093221): the remote command's ssh call hit its local timeout
# and its output was thrown away, so the outcome was unknown. Now a timed-out or failed command's partial
# output is kept and summarised, every entry ends as an outcome, in_flight or not_tried, and the remote loop
# stops itself STOP_MARGIN_SECONDS before the local timeout so df after still prints.
DEFAULT_FORECAST_MINUTES = 15.0
DEFAULT_DEADLINE_MINUTES = 30.0
STOP_RESERVE_MINUTES = fsl.STOP_RESERVE_MINUTES
TRIM_SECONDS = 900
STOP_MARGIN_SECONDS = 90                      # the remote loop stops this long before the local timeout
MIN_REMOTE_SECONDS, MAX_REMOTE_SECONDS = 30, 3600
RM_SECONDS = 300                              # one file's rm
STAT_SECONDS = 60
ACTIVATION_SECONDS = fsl.ACTIVATION_SECONDS
SSH_ATTEMPTS = fsl.SSH_ATTEMPTS
MAX_ENTRIES = 200
NAME_CHARS = re.compile(r'[A-Za-z0-9_.-]+')
ARCHIVE_NAME = re.compile(r'project-[0-9a-f]{8,64}\.tar\.gz')
NEVER_TOUCH_PREFIXES = ('assets-', 'image/', 'image')
OUTCOMES = ('DELETED', 'SKIP_SIZE', 'SKIP_MISSING', 'SKIP_LINK', 'SKIP_NOT_FILE', 'FAILED')

# The whole remote command set. Only {mount} (the constant above, quoted), {entries} (validated paths, each
# quoted, each followed by its integer bytes) and {seconds} (the remote time budget, a validated integer) are
# filled in. Deletes only listed regular files of exact size. A TRY line (path, bytes, epoch) goes out before
# each file is touched, so a cut run names the one file in flight; the loop stops itself at its time budget.
HEADER = ("set -u; test -d {mount}/projects || {{ echo 'projects absent'; exit 3; }}; "
          "if test -L {mount}/projects; then echo 'projects is a link'; exit 4; fi")
DF_BEFORE = "echo '== df before'; timeout 120 df -B1 --output=size,used,avail,target {mount}"
LIST = ("end=$(( $(date -u +%s) + {seconds} )); list=$(mktemp) || exit 5; "
        "printf '%s %s\\n' {entries} > \"$list\"; n=$(wc -l < \"$list\"); echo '== list'; echo \"$n\"; "
        "if [ \"$n\" -ne {count} ]; then echo 'LIST_SHORT'; exit 6; fi")
LOOP = ("echo '== trim'; while read -r p b; do "
        "if [ \"$(date -u +%s)\" -ge \"$end\" ]; then echo 'STOPPED_AT_TIME'; break; fi; "
        "f={mount}/\"$p\"; printf 'TRY\\t%s\\t%s\\t%s\\n' \"$p\" \"$b\" \"$(date -u +%s)\"; "
        "if test -L \"$f\"; then printf 'SKIP_LINK\\t%s\\t%s\\n' \"$p\" \"$b\"; "
        "elif ! test -e \"$f\"; then printf 'SKIP_MISSING\\t%s\\t%s\\n' \"$p\" \"$b\"; "
        "elif ! test -f \"$f\"; then printf 'SKIP_NOT_FILE\\t%s\\t%s\\n' \"$p\" \"$b\"; "
        "else s=$(timeout " + str(STAT_SECONDS) + " stat -c %s -- \"$f\" 2>/dev/null || echo unknown); "
        "if [ \"$s\" != \"$b\" ]; then printf 'SKIP_SIZE\\t%s\\t%s\\t%s\\n' \"$p\" \"$b\" \"$s\"; "
        "else timeout " + str(RM_SECONDS) + " rm -f -- \"$f\"; r=$?; "
        "if ! test -e \"$f\" && ! test -L \"$f\"; then printf 'DELETED\\t%s\\t%s\\n' \"$p\" \"$b\"; "
        "else printf 'FAILED\\t%s\\t%s\\t%s\\n' \"$p\" \"$b\" \"$r\"; fi; fi; fi; "
        "done < \"$list\"; rm -f -- \"$list\"; echo '== trim end'; date -u +%s")
DF_AFTER = "echo '== df after'; timeout 120 df -B1 --output=size,used,avail,target {mount}"
TEMPLATES = (HEADER, DF_BEFORE, LIST, LOOP, DF_AFTER)
# 20 Nov 10:06 run (shimmer-loop-fs-trim-20261120t100616): the 10 200-character script went on the ssh command
# line and arrived cut at about 8 190 characters (the Windows ssh client's command limit), inside the printf of
# the 90 entries: the remote shell printed df and 79 entry lines to stdout, never wrote the list, never reached
# the loop and exited 0. So the script now goes on ssh's standard input to the one fixed remote command
# REMOTE_COMMAND, as one brace group (WRAP) that a cut input cannot run (a syntax error), and the remote side
# counts the list lines and stops with LIST_SHORT before the loop when they are not the entry count.
REMOTE_COMMAND = 'bash -s'
WRAP = ('{ ', '; }\n')
MAX_COMMAND_CHARS = 1024                      # the ssh argv command; the Windows client cuts near 8 KB
TEMPLATES_SHA256 = '8241c03d856b6da4dd69d29e607e247a58f41b41765989b6cec4a37436409e34'


class TrimRefusal(fsl.ListingRefusal):
    """A one-line refusal before or around the launch (a ListingRefusal, so fs_listing's pieces agree)."""


def refuse(condition, message):
    if not condition:
        raise TrimRefusal(message)


def templates_digest(templates=None, mount=None):
    value = [list(TEMPLATES if templates is None else templates), MOUNT if mount is None else mount, PROJECTS,
             REMOTE_COMMAND, list(WRAP)]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode('utf-8')).hexdigest()


def pinned():
    """The command set is the one reviewed: its digest equals the pin written in this file."""
    return templates_digest() == TEMPLATES_SHA256


def validate_entry(entry):
    """One entry {path, bytes}: projects/<one plain project archive name>, bytes a positive integer."""
    refuse(isinstance(entry, dict) and set(entry) == {'path', 'bytes'}, 'Each entry is exactly {"path", "bytes"}')
    path, size = entry['path'], entry['bytes']
    refuse(isinstance(path, str) and 0 < len(path) <= 160, 'A path is a short string')
    refuse(type(size) is int and size > 0, 'bytes must be a positive integer: %r' % (path,))
    refuse('..' not in path,'A path may not contain ..: %r' % path)
    refuse(not any(c in path for c in '*?[]{}~\\'), 'A path may not contain a wildcard: %r' % path)
    refuse(not path.lower().startswith(NEVER_TOUCH_PREFIXES), 'A never-touch path (assets-*, image/*): %r' % path)
    refuse(path.startswith(PROJECTS), 'A path outside projects/ (the mount root included): %r' % path)
    name = path[len(PROJECTS):]
    refuse('/' not in name, 'A path may not go below projects/: %r' % path)
    refuse(NAME_CHARS.fullmatch(name) is not None, 'A name holds only letters, digits and _ . -: %r' % path)
    refuse(not name.lower().startswith('assets-'), 'A never-touch name (assets-*): %r' % path)
    refuse(ARCHIVE_NAME.fullmatch(name) is not None, 'Not a plain project-<hex>.tar.gz name: %r' % path)
    return dict(path=path, bytes=size)


def validate_list(entries):
    """The whole list: a JSON array of 1 to MAX_ENTRIES valid entries, no path twice. Any bad entry refuses
    the whole run, before any provider call."""
    refuse(isinstance(entries, list), 'The list is a JSON array')
    refuse(0 < len(entries) <= MAX_ENTRIES, 'The list holds 1 to %d entries' % MAX_ENTRIES)
    out = [validate_entry(e) for e in entries]
    refuse(len({e['path'] for e in out}) == len(out), 'A path repeats')
    return out


def read_list(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        refuse(False, 'The list file cannot be read as JSON: %s' % Path(path).name)
    return validate_list(value)


def remote_seconds(timeout_seconds):
    """The remote loop's own time budget: the local timeout less the stop margin, a bounded integer."""
    seconds = int(timeout_seconds) - STOP_MARGIN_SECONDS
    refuse(MIN_REMOTE_SECONDS <= seconds <= MAX_REMOTE_SECONDS,
           'The remote time budget %d s is outside %d..%d s' % (seconds, MIN_REMOTE_SECONDS, MAX_REMOTE_SECONDS))
    return seconds


def trim_script(entries, seconds):
    """The one remote command: the pinned templates, the validated entries quoted into the list template and
    the remote time budget (an integer in range) into its one slot."""
    refuse(pinned(), 'The trim command set differs from its pinned digest; it is never run altered')
    entries = validate_list(entries)
    refuse(type(seconds) is int and MIN_REMOTE_SECONDS <= seconds <= MAX_REMOTE_SECONDS,
           'The remote time budget is an integer of %d..%d s' % (MIN_REMOTE_SECONDS, MAX_REMOTE_SECONDS))
    mount = shlex.quote(MOUNT)
    filled = ' '.join('%s %d' % (shlex.quote(e['path']), e['bytes']) for e in entries)
    return WRAP[0] + '; '.join([HEADER.format(mount=mount), DF_BEFORE.format(mount=mount),
                                LIST.format(entries=filled, seconds=seconds, count=len(entries)),
                                LOOP.format(mount=mount), DF_AFTER.format(mount=mount)]) + WRAP[1]


def remote_call(base, script):
    """The trim's ssh argv and its standard input: the one fixed remote command, the script on stdin, so its
    length never meets a command-line limit (the 20 Nov 10:06 cut)."""
    return base + [REMOTE_COMMAND], script.encode('utf-8')


def ssh_input(argv, timeout, data=None):
    """fs_listing's ssh runner with the script on standard input."""
    return subprocess.run(argv, input=data, capture_output=True, timeout=timeout, creationflags=fsl.no_window())


def parse_df(lines):
    for line in lines:
        parts = line.split()
        if len(parts) >= 4 and all(p.isdigit() for p in parts[:3]):
            return dict(size=int(parts[0]), used=int(parts[1]), avail=int(parts[2]), target=parts[3])
    return None


def summarise(text, entries, cut=False):
    """The summary of the remote output, complete or cut, against the list. Every entry ends in exactly one
    of: an outcome line; `in_flight` (its TRY line went out with no outcome after it: it may or may not be
    deleted, the next run's SKIP_MISSING or a listing settles it); or `not_tried` (no TRY line: untouched, as
    the loop handles one file at a time in list order). So a partial run is never unknown."""
    sections, current = {}, None
    for line in text.splitlines():
        if line.startswith('== '):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    listed = {e['path']: e['bytes'] for e in entries}
    outcomes, tries, unexpected, stopped = {}, {}, [], False
    for line in sections.get('trim', []):
        parts = line.split('\t')
        if (len(parts) == 4 and parts[0] == 'TRY' and parts[1] in listed and parts[1] not in tries
                and parts[2] == str(listed[parts[1]]) and parts[3].isdigit()):
            tries[parts[1]] = int(parts[3])
        elif (len(parts) in (3, 4) and parts[0] in OUTCOMES and parts[1] in listed and parts[1] not in outcomes
                and parts[1] in tries and parts[2] == str(listed[parts[1]])):
            extra = {} if len(parts) == 3 else {'rm_exit' if parts[0] == 'FAILED' else 'found': parts[3]}
            outcomes[parts[1]] = dict(outcome=parts[0], path=parts[1], bytes=listed[parts[1]], **extra)
        elif line.strip() == 'STOPPED_AT_TIME' and not stopped:
            stopped = True
        elif line.strip():
            unexpected.append(line[:200])
    rows = [outcomes[p] for p in listed if p in outcomes]
    deleted = [r for r in rows if r['outcome'] == 'DELETED']
    skips = {}
    for r in rows:
        if r['outcome'] != 'DELETED':
            skips[r['outcome']] = skips.get(r['outcome'], 0) + 1
    in_flight = [p for p in listed if p in tries and p not in outcomes]
    not_tried = [p for p in listed if p not in tries and p not in outcomes]
    counted = [l.strip() for l in sections.get('list', []) if l.strip().isdigit()]
    list_lines = int(counted[0]) if counted else None
    reached_trim = 'trim' in sections
    end = [l for l in sections.get('trim end', []) if l.strip().isdigit()]
    times = sorted(tries.values()) + ([int(end[0])] if end else [])
    steps = [b - a for a, b in zip(times, times[1:])]
    before, after = parse_df(sections.get('df before', [])), parse_df(sections.get('df after', []))
    complete = (not cut and not stopped and not in_flight and not not_tried and not unexpected and bool(end)
                and list_lines == len(entries) and reached_trim)
    return dict(entries=len(entries), complete=complete, cut_by_local_timeout=bool(cut), stopped_at_time=stopped,
                list_lines=list_lines, reached_trim=reached_trim,
                deleted_count=len(deleted), deleted_bytes=sum(r['bytes'] for r in deleted), skips_by_reason=skips,
                in_flight=in_flight, not_tried=not_tried, unreported=in_flight + not_tried,
                unexpected_lines=unexpected, tried=len(tries),
                remote_trim_seconds=(times[-1] - times[0]) if len(times) > 1 else None,
                slowest_file_seconds=max(steps) if steps else None,
                df_before=before, df_after=after,
                freed_bytes_by_df=(before['used'] - after['used']) if before and after else None, rows=rows)


def out_root():
    """docs/loop/private/fs_trim of the MAIN checkout (instance_reaper.main_private)."""
    return Path(guard.instance_reaper.main_private()) / 'fs_trim'


def offline_forecast(forecast_minutes, cap_usd):
    """The dry run's forecast from the newest saved provider inventory (no provider call), or None."""
    try:
        import step_cost
        import shared_paths
        try:
            main_root = shared_paths.main_checkout()
        except shared_paths.MainCheckoutError:
            main_root = None
        path = step_cost.newest_inventory(step_cost.inventory_candidates(main_root))
        inventory = step_cost.read_json(path, 'provider inventory')
        kind, rate = cheapest_type(inventory['instance_types'])
        forecast = guard.forecast_usd(forecast_minutes, rate)
        return dict(type=kind, rate=rate, forecast_usd=round(forecast, 4), cap_usd=cap_usd,
                    within_cap=forecast <= cap_usd, inventory=Path(path).name,
                    observed_at=inventory.get('observed_at'))
    except Exception as exc:
        return dict(unavailable=type(exc).__name__ + ': ' + str(exc)[:160])


def execute(entries, *, cap_usd=DEFAULT_CAP_USD, forecast_minutes=DEFAULT_FORECAST_MINUTES,
            deadline_minutes=DEFAULT_DEADLINE_MINUTES, storage_forecast_usd=0.0, provider=None, ssh=None,
            keygen=None, clock=time, ledger=None, reaped=None, spend_store=None, out_dir=None, key_dir=None,
            keep_awake=awake, now_name=None):
    """The one trim launch. Returns the run record. Refusals before the intent line raise; after it, every
    failure is recorded and the instance is still terminated and the ledger closed."""
    check_plan(cap_usd, forecast_minutes, deadline_minutes, storage_forecast_usd)
    entries = validate_list(entries)
    trim_script(entries, MIN_REMOTE_SECONDS)   # the pin and every entry, before any provider call
    ledger = Path(guard.reaper_ledgers()[0] if ledger is None else ledger)
    guard.require_reaped(ledger, reaped)
    name = guard.instance_name('fs-trim-' + (now_name or datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S')))
    provider = real_provider() if provider is None else provider
    ssh = ssh_input if ssh is None else ssh
    keygen = generate_key if keygen is None else keygen
    guard.refuse_foreign_inventory(provider.request('instances')['data'])
    kind, rate = cheapest_type(provider.request('instance-types')['data'])
    forecast = guard.forecast_usd(forecast_minutes, rate)
    own_cap_refusal(forecast, cap_usd)
    filesystems = [f for f in provider.request('file-systems')['data']
                   if f.get('name') == FILESYSTEM_NAME and f.get('region') == REGION]
    refuse(len(filesystems) == 1, 'The provider does not list %s in %s' % (FILESYSTEM_NAME, REGION))
    images = [i for i in provider.request('images')['data']
              if i.get('region') == REGION and i.get('family') == IMAGE_FAMILY and i.get('architecture') == 'x86_64']
    refuse(images, 'No %s image in %s' % (IMAGE_FAMILY, REGION))
    image = sorted(images, key=lambda i: str(i.get('version')))[-1]
    folder = Path(out_root() if out_dir is None else out_dir) / name
    keys = Path(tempfile.mkdtemp(prefix='fs-trim-') if key_dir is None else key_dir)
    identity = keys / 'ssh_identity'
    refuse(not identity.exists() and not Path(str(identity) + '.pub').exists(), 'Temporary key path occupied')
    run = dict(instance_name=name, purpose=PURPOSE, type=kind, region=REGION, price_usd_per_hour=rate,
               forecast_usd=round(forecast, 4), trim_cap_usd=cap_usd, entries=len(entries),
               listed_bytes=sum(e['bytes'] for e in entries), phases=[])
    lock = guard.acquire_lock(ledger)
    registration = iid = None
    intent = launch_line = held = False
    start = deadline = None
    common = {}
    try:
        inventory = provider.request('instances')['data']
        decision = guard.check(ledgers=[ledger], forecast_minutes=forecast_minutes, hourly_rate=rate,
                               storage_forecast_usd=storage_forecast_usd, now_epoch=clock.time(),
                               reserve_minutes=STOP_RESERVE_MINUTES, provider_names=guard.loop_inventory(inventory),
                               instance_type=kind, reaped=reaped, spend_store=spend_store)
        cap = min(cap_usd, decision['cap_usd'])
        own_cap_refusal(forecast, cap)
        run.update(cap_usd=round(cap, 4), budget=decision)
        folder.mkdir(parents=True, exist_ok=False)
        Path(folder, 'entries.json').write_text(json.dumps(entries, indent=1) + '\n', encoding='utf-8')
        public = keygen(identity, name)
        registration = provider.request('ssh-keys', dict(name=name, public_key=public))['data'][0]
        start = clock.time()
        deadline = start + min(deadline_minutes * 60, cap / rate * 3600)
        common = dict(instance_name=name, type=kind, region=REGION, price_usd_per_hour=rate, purpose=PURPOSE,
                      forecast_usd=round(forecast, 4), cap_usd=round(cap, 4))
        # IV.3: the name and the deadline are in the ledger before the launch request.
        record(ledger, 'launch_intent', time_utc=utc(start), launch_requested_utc=utc(start),
               deadline_utc=utc(deadline), **common)
        intent = True
    finally:
        guard.release_lock(lock)
        if not intent and registration is not None:
            try:
                provider.request('ssh-keys/' + registration['id'], method='DELETE')
            except Exception:
                pass
            registration = None
    status = 'failed'
    try:
        held = bool(keep_awake('hold'))
        launched = provider.request('instance-operations/launch', dict(
            region_name=REGION, instance_type_name=kind, ssh_key_names=[registration['name']], quantity=1,
            name=name, image={'id': image['id']}, file_system_names=[FILESYSTEM_NAME]))['data']
        iid = launched['instance_ids'][0]
        record(ledger, 'launch', time_utc=utc(clock.time()), launch_requested_utc=utc(start), instance_id=iid,
               deadline_utc=utc(deadline), **common)
        launch_line = True
        while True:
            state = provider.instance(iid)
            if state.get('status') == 'active' and state.get('public_ip'):
                run['phases'].append(dict(phase='active', seconds_since_request=round(clock.time() - start, 1)))
                break
            refuse(clock.time() - start < ACTIVATION_SECONDS, 'Activation timeout')
            clock.sleep(5)
        refuse(float(state.get('hourly_rate', rate)) == rate, 'The activated price differs from the selected price')
        options = ['-i', str(identity), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                   '-o', 'StrictHostKeyChecking=accept-new', '-o', 'UserKnownHostsFile=' + str(keys / 'known_hosts'),
                   '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2']
        base = ['ssh', *options, 'ubuntu@' + state['public_ip']]
        for attempt in range(SSH_ATTEMPTS):
            try:
                ready = ssh(base + ['true'], 20).returncode == 0
            except subprocess.TimeoutExpired:
                ready = False
            run['phases'].append(dict(phase='ssh_ready', attempt=attempt, ready=ready,
                                      seconds_since_request=round(clock.time() - start, 1)))
            if ready:
                break
            clock.sleep(5)
        else:
            refuse(False, 'ssh not ready')
        remaining = int(deadline - STOP_RESERVE_MINUTES * 60 - clock.time())
        refuse(remaining > 0, 'The deadline leaves no time for the trim')
        timeout = min(TRIM_SECONDS, remaining)
        seconds = remote_seconds(timeout)
        script = trim_script(entries, seconds)
        argv, data = remote_call(base, script)
        refuse(len(argv[-1]) <= MAX_COMMAND_CHARS, 'The ssh command argument is %d characters, over %d; the '
               'script goes on standard input, never on the command line' % (len(argv[-1]), MAX_COMMAND_CHARS))
        began = clock.time()
        cut = False
        try:
            done = ssh(argv, timeout, data)
            out, err, returncode = done.stdout or b'', done.stderr or b'', done.returncode
        except subprocess.TimeoutExpired as exc:
            # subprocess.run kills ssh and attaches what it had read: keep it, so a cut run is never unknown
            cut, returncode = True, None
            out, err = exc.stdout or b'', exc.stderr or b''
        run['phases'].append(dict(phase='trim', returncode=returncode, timed_out=cut, timeout_seconds=timeout,
                                  remote_seconds=seconds, seconds=round(clock.time() - began, 1),
                                  remote_command=argv[-1], script_bytes=len(data or b''),
                                  stdout_bytes=len(out), stderr_bytes=len(err)))
        refuse(not credential_locations(out + err, 'trim'), 'Possible credential in the trim output; output withheld')
        Path(folder, 'trim.txt').write_bytes(out)
        Path(folder, 'trim_stderr.txt').write_bytes(err)
        summary = summarise(out.decode('utf-8', errors='replace'), entries, cut=cut)
        save(folder, 'summary.json', summary)
        run['summary'] = {k: v for k, v in summary.items() if k != 'rows'}
        refuse(not cut, 'The trim ran past its time (%d s); the outcome lines read before the cut are in '
                        'summary.json' % timeout)
        refuse(summary['list_lines'] is None or summary['list_lines'] == len(entries),
               'The remote list holds %s lines for %d entries (LIST_SHORT): the script did not arrive whole; the '
               'loop never started, nothing was deleted' % (summary['list_lines'], len(entries)))
        refuse(returncode == 0, 'The trim exited %d' % returncode)
        refuse(summary['reached_trim'], 'The remote script exited 0 before its trim step (no "== trim" line, '
               '%d entries not tried): it did not arrive whole; the loop never started, nothing was deleted'
               % len(summary['not_tried']))
        refuse(not summary['stopped_at_time'], 'The remote loop stopped at its time budget; %d entries not tried'
               % len(summary['not_tried']))
        refuse(summary['complete'], 'The trim output does not give exactly one outcome per entry')
        refuse(summary['df_before'] is not None and summary['df_after'] is not None, 'df before or after missing')
        status = 'trimmed'
    except Exception as exc:
        run['failure'] = dict(error_type=type(exc).__name__,
                              message=str(exc) if isinstance(exc, (fsl.ListingRefusal, guard.GuardRefusal)) else 'see phases')
    finally:
        recovered = True
        if iid is None:
            try:
                matches = [x for x in provider.request('instances')['data'] if x.get('name') == name]
                refuse(len(matches) <= 1, 'Ambiguous launch recovery')
                if matches:
                    iid = matches[0]['instance_id']
            except Exception as exc:
                recovered = False      # unknown: the ledger stays open, the reaper ends it at its deadline
                run['recovery_failure'] = type(exc).__name__
        end = terminate_confirmed(provider, iid, clock) if iid else clock.time()
        run['termination_confirmed'] = end is not None
        if recovered and end is not None:
            try:
                if iid and not launch_line:
                    record(ledger, 'launch', time_utc=utc(end), launch_requested_utc=utc(start), instance_id=iid,
                           deadline_utc=utc(deadline), **common)
                minutes = max(0, math.ceil((end - start) / 60)) if iid else 0
                record(ledger, 'termination', time_utc=utc(end), launch_requested_utc=utc(start), instance_id=iid,
                       actual_minutes=minutes, actual_cost=round(rate * minutes / 60, 4), **common)
                run.update(actual_minutes=minutes, actual_cost=round(rate * minutes / 60, 4))
            except Exception as exc:
                run['ledger_close_failure'] = type(exc).__name__
        if held:
            keep_awake('release')
        try:
            provider.request('ssh-keys/' + registration['id'], method='DELETE')
            run['ssh_key_removed'] = all(k.get('id') != registration['id'] for k in provider.request('ssh-keys')['data'])
        except Exception as exc:
            run['ssh_key_removed'] = False
            run['ssh_key_failure'] = type(exc).__name__
        for path in (identity, Path(str(identity) + '.pub'), keys / 'known_hosts'):
            Path(path).unlink(missing_ok=True)   # files only; the empty temporary folder is left
        try:
            left = [x for x in provider.request('instances')['data']
                    if (iid and x.get('instance_id') == iid) or x.get('name') == name]
            run['own_instance_absent'] = not [x for x in left if x.get('status') != 'terminated']
        except Exception as exc:
            run['own_instance_absent'] = None
            run['inventory_failure'] = type(exc).__name__
        run.update(status=status, instance_id=iid, requested_utc=utc(start), deadline_utc=utc(deadline))
        save(folder, 'run.json', run)
    return dict(run, folder=str(folder))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], allow_abbrev=False)
    parser.add_argument('--list', required=True, help='JSON array of {"path": "projects/...", "bytes": N}')
    parser.add_argument('--cap-usd', type=float, default=DEFAULT_CAP_USD)
    parser.add_argument('--forecast-minutes', type=float, default=DEFAULT_FORECAST_MINUTES)
    parser.add_argument('--deadline-minutes', type=float, default=DEFAULT_DEADLINE_MINUTES)
    parser.add_argument('--storage-forecast-usd', type=float, default=0.0)
    parser.add_argument('--execute', action='store_true', help='launch; without it nothing is called')
    args = parser.parse_args(argv)
    try:
        check_plan(args.cap_usd, args.forecast_minutes, args.deadline_minutes, args.storage_forecast_usd)
        entries = read_list(args.list)
        # the most the remote command can get: the deadline less the stop reserve (boot time comes off it live)
        longest = int(min(TRIM_SECONDS, (args.deadline_minutes - STOP_RESERVE_MINUTES) * 60))
        script = trim_script(entries, remote_seconds(longest))
        if not args.execute:
            print('dry run, no provider call; %d validated entries, %d bytes:' % (
                len(entries), sum(e['bytes'] for e in entries)))
            for e in entries:
                print('  %s\t%d' % (e['path'], e['bytes']))
            print('the remote command would be %r with this script on its standard input (time budget shown'
                  % REMOTE_COMMAND + ' for a zero boot; at the launch it is the '
                  'deadline less the reserve, less the boot, less %d s):' % STOP_MARGIN_SECONDS)
            print(script)
            f = offline_forecast(args.forecast_minutes, args.cap_usd)
            if 'unavailable' in f:
                print('cost forecast: unavailable offline (%s); the launch prices it live' % f['unavailable'])
            else:
                print('cost forecast: %s at %.2f USD/h x %.0f min x %.1f = %.4f USD, cap %.2f USD (%s); '
                      'from saved inventory %s observed %s; the launch prices it again live' % (
                          f['type'], f['rate'], args.forecast_minutes, guard.FORECAST_FACTOR, f['forecast_usd'],
                          f['cap_usd'], 'within' if f['within_cap'] else 'OVER', f['inventory'], f['observed_at']))
            return 0
        result = execute(entries, cap_usd=args.cap_usd, forecast_minutes=args.forecast_minutes,
                         deadline_minutes=args.deadline_minutes, storage_forecast_usd=args.storage_forecast_usd)
    except (fsl.ListingRefusal, guard.GuardRefusal) as exc:
        print('refused: ' + str(exc))
        return 2
    s = result.get('summary') or {}
    print('%s on %s at %.2f USD/h: %s; deleted %s (%s bytes), skips %s; termination confirmed: %s; billed %s min, '
          '%s USD; folder %s' % (
              result['instance_name'], result['type'], result['price_usd_per_hour'], result['status'],
              s.get('deleted_count'), s.get('deleted_bytes'), s.get('skips_by_reason'), result['termination_confirmed'],
              result.get('actual_minutes'), result.get('actual_cost'), result['folder']))
    if s and not s.get('complete'):
        print('partial: %s tried; in flight (may or may not be deleted) %s; not tried (untouched) %s; '
              'cut by the local timeout %s; stopped at the remote time budget %s' % (
                  s.get('tried'), s.get('in_flight'), len(s.get('not_tried') or []), s.get('cut_by_local_timeout'),
                  s.get('stopped_at_time')))
    if result.get('failure'):
        print('failure: %s %s' % (result['failure']['error_type'], result['failure']['message']))
    if not result['termination_confirmed']:
        print('TERMINATION NOT CONFIRMED: the ledger stays open and the reaper ends the instance at its deadline')
        return 2
    return 0 if result['status'] == 'trimmed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
