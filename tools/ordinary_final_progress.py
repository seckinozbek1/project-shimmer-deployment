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
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools')]
from ordinary_final_run import read
from cloud_run_common import no_window

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
                   'asset_copy_probe', 'asset_copy_use',
                   # D-S108: binding the checked layers read-only, a few mount calls with one answer.
                   'image_bind',
                   # After a failed bind, the unmount and one reading of the mount table; after an
                   # image phase's deadline, one kill of its process group. One answer each.
                   'image_release', 'stop_image_phase',
                   # A batch session's per-bundle steps (S2c item 11): moving the finished
                   # bundle aside, sending the next bundle's sealed files, checking and
                   # unpacking them, and collecting each bundle's evidence. Each is one
                   # command with one answer; the long step is batch_workload, read below.
                   'batch_park', 'batch_transfer', 'batch_integrity', 'batch_extract',
                   'batch_pack_evidence', 'batch_evidence_hash', 'batch_evidence_download')
SSH_OPTIONS = ['-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
               '-o', 'ConnectTimeout=15']


def observe(bundle, host, command, timeout=40):
    """One read-only observation on the instance. Returns its stdout, or None if unreadable."""
    argv = ['ssh', '-i', str(bundle / 'ssh_identity'), *SSH_OPTIONS,
            '-o', 'UserKnownHostsFile=' + str(bundle / 'known_hosts'), host, command]
    try:
        result = subprocess.run(argv, capture_output=True, timeout=timeout, creationflags=no_window())
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


B1_ROOT = 'evidence/b1'


def training_command(root):
    """The one read-only shell observation of a training pass, run from `root`. A mix's questions are
    its own folder's reply records and its own passes' (`<folder>/audit/model_replies` and
    `<folder>/passes/<name>/audit/model_replies`), at those depths only: permissive_mix's folder is
    the parent of dev_mix's, so a recursive count there read dev_mix's records as its own."""
    return ("cd %s && f=$(ls -t %s/*/training/progress.json %s/*/*/training/progress.json 2>/dev/null | head -1); "
            "if [ -n \"$f\" ]; then echo TRAINING; tr -d '\\n' < \"$f\"; echo; "
            "u=$(tr -d '\\n' < \"$f\" | grep -o '\"records_under\": *\"[^\"]*\"' | cut -d'\"' -f4); u=${u:-%s}; "
            "( (find \"$u/audit/model_replies\" -mindepth 1 -maxdepth 1 -name '*.json' 2>/dev/null; "
            "find \"$u/passes\" -mindepth 4 -maxdepth 4 -path '*/audit/model_replies/*.json' 2>/dev/null) | wc -l); "
            "date +%%s; else echo NONE; fi" % (root, B1_ROOT, B1_ROOT, B1_ROOT))


def training_reading(context, phase):
    """A judge training pass (benchmark/baselines/judge_train.py, T of D-S42): no reply record exists
    while it trains, so its reading is its own progress file, which states the update reached, the
    updates planned, the seconds spent and the measured seconds an update. Once the questions run,
    it is the reply records of every pass against the total the file states, timed from the start
    the file states, counted under the folder the file names (a session's recipes each have one).
    None when no such file exists: the reply-record reading then applies."""
    raw = context['look'](training_command(REMOTE_ROOT))
    if raw is None:
        return None
    lines = (raw.splitlines() + ['', '', '', ''])[:4]
    if lines[0].strip() != 'TRAINING':
        return None
    try:
        state = json.loads(lines[1])
    except ValueError:
        return unreadable(phase, 'the training progress file is being written')
    mix = (' (%s)' % state['mix']) if state.get('mix') else ''
    if state.get('phase') == 'questions':
        if digits(lines[2]) > state['questions_total']:
            return unreadable(phase + mix, '%d reply records counted against %d stated: they are not this pass\'s alone'
                              % (digits(lines[2]), state['questions_total']))
        return count_reading(phase + mix, digits(lines[2]), state['questions_total'], digits(lines[3]) - state['started_epoch'],
                             'reply records', 'every pass of the questions written')
    done, total, each = state['update'], state['of'], state['seconds_per_update']
    return ('%s progress: %d of %d training updates (%.1f%%) measured, %.1f min elapsed, %.1f s/update, ~%.1f min remaining at that rate'
            % (phase + mix, done, total, 100 * done / total, state['elapsed_seconds'] / 60, each, (total - done) * each / 60))


def b1_workload(context, phase):
    """A B1 entry (S5 R19): bare_model.py writes one reply record per item per sealed pass under
    evidence/b1/<pass name>/audit/model_replies (every pass's folder is counted, whatever
    checkpoint it loads), and the runner writes the total it expects (items times passes)
    beside them first. None when the workload is not a B1 run (the pipeline's reading applies)
    or the instance did not answer (the pipeline's own observation then says so)."""
    reading = training_reading(context, phase)
    if reading is not None:
        return reading
    raw = context['look'](
        "cd %s && if [ -d %s ]; then echo B1; (find %s -path '*/audit/model_replies/*.json' 2>/dev/null | wc -l); "
        "(cat %s/expected_records 2>/dev/null || echo 0); else echo PIPELINE; fi" % (REMOTE_ROOT, B1_ROOT, B1_ROOT, B1_ROOT))
    if raw is None:
        return None
    lines = (raw.splitlines() + ['', '', ''])[:3]
    if lines[0].strip() != 'B1':
        return None
    done, total = digits(lines[1]), digits(lines[2])
    return count_reading(phase, done, total or None, context['elapsed'], 'reply records',
                         'one reply record per item per pass, all written')


LAUNCHER_ROOT = 'evidence/launcher'
LAUNCHER_LINE = re.compile(r'(\d+) of (\d+) sealed answers to the required prompts given')


def launcher_workload(context, phase):
    """An arm L entry (D-S13 item 6d): the runner prints one line per answer it gives the menu,
    naming how many of the sealed answers to the required prompts are given of how many; the
    last such line is the reading. None when the workload is not arm L or the instance did not
    answer (the pipeline's own observation then says so)."""
    raw = context['look'](
        "cd %s && if [ -d %s ]; then echo L; (grep -o '[0-9]* of [0-9]* sealed answers to the required prompts given' "
        "workload.stderr.log 2>/dev/null | tail -1 || true); else echo OTHER; fi" % (REMOTE_ROOT, LAUNCHER_ROOT))
    if raw is None:
        return None
    lines = (raw.splitlines() + ['', ''])[:2]
    if lines[0].strip() != 'L':
        return None
    found = LAUNCHER_LINE.search(lines[1])
    elapsed = max(context['elapsed'], 0)
    if not found:
        return ('%s progress: no sealed answer given yet, %.1f min elapsed; the menu asks nothing before its '
                'runtime check and preflight end, so there is nothing to measure yet' % (phase, elapsed / 60))
    # The answers come in bursts between the menu's two runs, so a rate over them would predict
    # nothing: the count and the elapsed time are the reading, and no remaining time is claimed.
    return ('%s progress: %s of %s sealed answers to the required prompts given (measured from the runner\'s '
            'own answer lines), %.1f min elapsed; no rate or remaining time: the answers come in bursts between '
            'the two runs, whose length the menu decides' % (phase, found.group(1), found.group(2), elapsed / 60))


def ordinary_workload(context):
    """The run itself: count the telemetry records it writes as it goes (a B1 entry: its
    reply records, b1_workload; an arm L entry: the sealed answers given, launcher_workload)."""
    b1 = b1_workload(context, 'ordinary_workload')
    if b1 is not None:
        return b1
    launcher = launcher_workload(context, 'ordinary_workload')
    if launcher is not None:
        return launcher
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


def batch_workload(context):
    """A batch bundle's run: the same records in the same place (the finished bundle was moved
    aside before this one started), so the same reading under this phase's name."""
    return ordinary_workload(context).replace('ordinary_workload', 'batch_workload', 1)


def image_layers_reading(phase):
    """D-S108: the image tool's own progress file in the run root (tools/image_layers.py writes it
    every two seconds): the bytes hashed, copied or read, or the distributions installed, of the
    stage in hand, against its total, with that stage's own start for the rate."""
    def reader(context):
        raw = context['look']('cat %s/image_progress.json 2>/dev/null || echo none' % REMOTE_ROOT)
        if raw is None:
            return unreadable(phase, 'the instance did not answer')
        try:
            record = json.loads(raw)
        except ValueError:
            return unreadable(phase, 'the image tool has written no progress yet')
        done, total = record.get('done') or 0, record.get('total') or 0
        stage_elapsed = max(0.0, float(record.get('epoch', 0)) - float(record.get('stage_started', 0)))
        if record.get('unit') == 'bytes':
            line = size_reading(phase, done, total, stage_elapsed, 'the ' + str(record.get('stage')))
        else:
            line = count_reading(phase, done, total, stage_elapsed, str(record.get('unit')),
                                 'no remaining time can be read')
        return '%s (stage: %s; the phase %.1f min elapsed)' % (line, record.get('stage'), context['elapsed'] / 60)
    return reader


READERS = dict(assets_transfer=assets_transfer, asset_copy_seed=asset_copy_seed,
               install_pinned_wheels=install_pinned_wheels, ordinary_workload=ordinary_workload,
               batch_workload=batch_workload,
               **{p: image_layers_reading(p) for p in ('image_check', 'image_recheck', 'image_build', 'image_measure')})


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
