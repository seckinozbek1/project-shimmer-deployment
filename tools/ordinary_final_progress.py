"""Measured progress for the long phase of an ordinary final run, read from the work itself.

PROGRESS-A (CLAUDE.md): any phase that takes more than a couple of minutes reports four
values in every sitrep: how much of the work is done against the total, how long it has
been running, the current rate, and the remaining time at that rate. The controller
captures its transfers and the detached remote phases with no incremental output of their
own, so
this tool takes a READ-ONLY OBSERVATION of the work itself (a stat of the partial file on
the instance, a count of the records the run has written) through the run's own temporary
key, and states the answer as MEASURED. Where a phase writes nothing countable, the
reading says so and says WHY; an estimate is never printed in place of a reading.

    py -3.12 tools/ordinary_final_progress.py --bundle docs/fix/ordinary_final_cloud_run_v12

Every reading is one line. Nothing here launches, terminates, writes to the instance or
touches the provider API: the only remote call is one `ssh` of a read-only command, and
`--observations` replaces even that with a saved JSON file, which is how the gate proves
each reader against a finished run's own evidence.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools')]
from ordinary_final_run import read

# The phases worth a reading, with what each one's total is and where its work can be seen.
REMOTE_ROOT = '/home/ubuntu/shimmer-ordinary-final'
TELEMETRY = 'evidence/run/logs/model_telemetry.jsonl'
# Phases that report only on completion. Naming them is itself a reading: the tool says
# there is nothing incremental to read rather than inventing a percentage.
COMPLETION_ONLY = ('archive_integrity', 'extract_payload', 'create_environment', 'dependency_closure',
                   'evidence_download', 'pack_evidence', 'evidence_hash', 'final_gpu_state',
                   'gpu_metadata', 'python_gate', 'fresh_directory', 'support_transfer',
                   'watchdog_receipt_transfer', 'stop_workload', 'terminate_instance',
                   # The copy phases: the probe is one hash of a file already in place and the
                   # use is a local copy on the instance, both over in seconds with one answer.
                   'asset_copy_probe', 'asset_copy_use')
SSH_OPTIONS = ['-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
               '-o', 'ConnectTimeout=15']


def observe(bundle, host, command, timeout=40):
    """One read-only observation on the instance. Returns its stdout, or None if unreadable."""
    argv = ['ssh', '-i', str(bundle / 'ssh_identity'), *SSH_OPTIONS,
            '-o', 'UserKnownHostsFile=' + str(bundle / 'known_hosts'), host, command]
    try:
        result = subprocess.run(argv, capture_output=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode('utf8', 'replace').strip()


def unreadable(phase, why):
    return '%s progress: not measurable (%s)' % (phase, why)


def size_reading(phase, done, total, elapsed, what):
    """Four values for a phase whose work is a file growing towards a known size."""
    if total <= 0:
        return unreadable(phase, 'no total is declared for ' + what)
    if elapsed <= 0 or done <= 0:
        return ('%s progress: %.2f of %.2f GB measured, %.1f min elapsed, rate not yet readable'
                % (phase, done / 1e9, total / 1e9, max(elapsed, 0) / 60))
    rate = done / elapsed
    remaining = (total - done) / rate / 60 if done < total else 0.0
    return ('%s progress: %.2f of %.2f GB (%.1f%%) measured, %.1f min elapsed, %.1f MB/s, ~%.1f min remaining'
            % (phase, done / 1e9, total / 1e9, 100 * done / total, elapsed / 60, rate / 1e6, remaining))


def count_reading(phase, done, total, elapsed, noun, baseline):
    """Four values for a phase whose work is a count of records written as it goes."""
    if done <= 0:
        return ('%s progress: no %s recorded yet, %.1f min elapsed; the phase writes nothing before its '
                'first one, so there is nothing to measure yet' % (phase, noun, max(elapsed, 0) / 60))
    rate = done / elapsed if elapsed > 0 else 0
    if total and done < total and rate > 0:
        tail = ', ~%.1f min remaining at that rate' % ((total - done) / rate / 60)
    else:
        tail = ', %s' % baseline
    return ('%s progress: %d of %s %s measured, %.1f min elapsed, %.1f %s/min%s'
            % (phase, done, total if total else 'an unknown number of', noun, elapsed / 60,
               rate * 60, noun.rstrip('s'), tail))


def assets_transfer(context):
    """The sealed archive being uploaded: stat the partial file on the instance."""
    raw = context['look']('stat -c %%s %s/assets.tar 2>/dev/null || echo 0' % REMOTE_ROOT)
    if raw is None:
        return unreadable('assets_transfer', 'the instance did not answer the stat')
    return size_reading('assets_transfer', digits(raw), context['assets_bytes'], context['elapsed'], 'the archive')


def asset_copy_seed(context):
    """The copy being written to the filesystem: stat the partial, then the final name."""
    path = context['copy_path']
    if not path:
        return unreadable('asset_copy_seed', 'the bundle declares no asset copy')
    raw = context['look']('stat -c %%s %s.partial 2>/dev/null || stat -c %%s %s 2>/dev/null || echo 0' % (path, path))
    if raw is None:
        return unreadable('asset_copy_seed', 'the instance did not answer the stat')
    return size_reading('asset_copy_seed', digits(raw), context['assets_bytes'], context['elapsed'], 'the copy')


def install_pinned_wheels(context):
    """Wheels being installed: count what is in site-packages against the pinned requirements."""
    raw = context['look']('ls %s/venv/lib/python3.12/site-packages 2>/dev/null | wc -l' % REMOTE_ROOT)
    if raw is None:
        return unreadable('install_pinned_wheels', 'the instance did not answer')
    done = digits(raw)
    total = context['pinned']
    elapsed = context['elapsed']
    if done <= 0:
        return ('install_pinned_wheels progress: no installed package measured yet, %.1f min elapsed'
                % (elapsed / 60))
    # Entries and requirements are not one to one (a wheel can install several top-level
    # entries), so the total is named as what it is and no percentage is claimed.
    rate = done / elapsed if elapsed > 0 else 0
    return ('install_pinned_wheels progress: %d site-packages entries measured against %d pinned requirements '
            '(not one to one), %.1f min elapsed, %.1f entries/min' % (done, total, elapsed / 60, rate * 60))


def ordinary_workload(context):
    """The run itself: count the telemetry records it writes as it goes."""
    raw = context['look'](
        "cd %s && (grep -c '\"event\": \"model_call\"' %s 2>/dev/null || echo 0); "
        "(grep -c '\"event\": \"auditor_pair\"' %s 2>/dev/null || echo 0); "
        "(grep -o 'completed=[0-9]*/[0-9]*' workload.stdout.log 2>/dev/null | tail -1 || true)"
        % (REMOTE_ROOT, TELEMETRY, TELEMETRY))
    if raw is None:
        return unreadable('ordinary_workload', 'the instance did not answer')
    lines = (raw.splitlines() + ['', '', ''])[:3]
    calls, pairs, counter = digits(lines[0]), digits(lines[1]), lines[2].strip()
    elapsed = context['elapsed']
    if counter.startswith('completed='):
        done, total = counter.split('=')[1].split('/')
        reading = count_reading('ordinary_workload', int(done), int(total), elapsed, 'agents',
                                'every agent accounted for')
        return reading + '; %d model calls and %d auditor pairs measured' % (calls, pairs)
    if calls:
        return (count_reading('ordinary_workload', calls, None, elapsed, 'model calls',
                              'no total is declared, the run decides its own call count')
                + '; %d auditor pairs measured' % pairs)
    return ('ordinary_workload progress: no telemetry record written yet, %.1f min elapsed; the phase writes '
            'nothing before its first model call, so there is nothing to measure yet' % (max(elapsed, 0) / 60))


READERS = dict(assets_transfer=assets_transfer, asset_copy_seed=asset_copy_seed,
               install_pinned_wheels=install_pinned_wheels, ordinary_workload=ordinary_workload)


def digits(text):
    """The leading integer of an observation, or 0. Never raises on a surprising answer."""
    head = (text or '').strip().splitlines()
    token = head[0].strip() if head else ''
    return int(token) if token.isdigit() else 0


def reading_for(bundle, phase=None, elapsed=None, observations=None, now=None):
    """The one measured line for the phase now running under `bundle`.

    `observations` replaces the ssh call with a saved {command_substring: output} map, so a
    finished run's own evidence can drive every reader with no instance in existence.
    """
    bundle = Path(bundle)
    if phase is None or elapsed is None:
        try:
            current = read(bundle / 'CURRENT_PHASE.json')
        except (OSError, ValueError):
            return 'phase progress: not measurable (the bundle has no CURRENT_PHASE.json yet)'
        phase = phase if phase is not None else current.get('phase', '')
        if elapsed is None:
            elapsed = (now if now is not None else time.time()) - float(current.get('epoch', 0))

    if observations is None:
        host = host_for(bundle)
        if host is None:
            look = lambda command: None
        else:
            look = lambda command: observe(bundle, host, command)
    else:
        def look(command):
            for key, value in observations.items():
                if key in command:
                    return value
            return None

    context = dict(look=look, elapsed=elapsed, assets_bytes=assets_bytes(bundle),
                   copy_path=copy_path(bundle), pinned=pinned_requirements(bundle))
    reader = READERS.get(phase)
    if reader is not None:
        return reader(context)
    if phase in COMPLETION_ONLY:
        return ('%s progress: no incremental record exists for this phase, it reports only on completion; '
                '%.1f min elapsed' % (phase, max(elapsed, 0) / 60))
    return '%s progress: not a long phase, nothing to measure (%.1f min elapsed)' % (phase, max(elapsed, 0) / 60)


def host_for(bundle):
    activation = None
    try:
        activation = read(Path(bundle) / 'activation.json')
    except (OSError, ValueError):
        return None
    address = (activation.get('metadata') or {}).get('public_ip')
    return 'ubuntu@' + address if address else None


def assets_bytes(bundle):
    for name in ('assets_transfer_archive.json', 'execution_manifest.json'):
        try:
            record = read(Path(bundle) / name)
        except (OSError, ValueError):
            continue
        if 'bytes' in record:
            return int(record['bytes'])
        archive = record.get('assets_archive') or {}
        if 'bytes' in archive:
            return int(archive['bytes'])
    return 0


def copy_path(bundle):
    try:
        return read(Path(bundle) / 'asset_copy_declaration.json').get('copy_path')
    except (OSError, ValueError):
        return None


def pinned_requirements(bundle):
    lock = Path(bundle) / 'install.lock'
    if not lock.exists():
        return 0
    return sum(1 for line in lock.read_text(encoding='utf8').splitlines() if '==' in line)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--phase', default=None, help='Read this phase instead of the bundle\'s current one.')
    parser.add_argument('--elapsed', type=float, default=None, help='Seconds in phase, for a replayed reading.')
    parser.add_argument('--observations', type=Path, default=None,
                        help='A saved {command substring: output} map, replacing every remote call.')
    arguments = parser.parse_args(argv)
    saved = json.loads(arguments.observations.read_text(encoding='utf8')) if arguments.observations else None
    print(reading_for(arguments.bundle, arguments.phase, arguments.elapsed, saved))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
