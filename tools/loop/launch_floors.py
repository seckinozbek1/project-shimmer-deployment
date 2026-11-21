"""The laptop RAM floor of a launch folder step, per step kind, read from config/launch_ram_floors.json at each call.

Seckin, 18 Nov 18:54 (the lead 18:58): a Lambda launch is never refused for laptop RAM. A step whose heavy work runs on
Lambda (the seal request, the seal launch, a part launch, the watch) needs only the small floor its measured laptop
peak calls for; a step that runs on the laptop (the admission's unpack and reverify, local reads) keeps the D-726 floor.

Each launch folder's launch.py (per folder and untracked) loads this file by its path in the main checkout and calls

    ram_problem(step, free_ram_gib, lambda_steps)

where `lambda_steps` names the folder's Lambda launches (its PURPOSES: the seal and every part). Kinds:

    request  -> 'request'              seal   -> 'seal'           admit -> 'admit'
    watch    -> 'watch'                a step in lambda_steps -> 'part'
    anything else (preflight with no step, inventory, labels, draws ...) -> 'local'

When the config cannot be read, or names no number for the kind, the floor is `fallback_gib`, else FALLBACK_GIB (the
D-726 1.2 GiB): an unreadable declaration never lowers a floor. A reading that is not a number (no psutil) is a problem.

The laptop DISK rule (Seckin, 19 November 2026 12:03 +0300) lives here too, read from config/laptop_disk_floor.json at
each call: heavy work on the laptop (downloads, builds, installs, clones, an admission's unpack and reverify) needs

    free disk >= the job's own expected footprint + margin_gib (10 since D-849, 20 Nov 2026; 12 until then)

    disk_problem(footprint_gib, free_gib=None, where=None)

returns None or a one-line reason naming free, footprint, margin and their sum. A footprint that is not known (None,
not a number, negative) is said so and held to the old fixed floor FALLBACK_DISK_GIB (30 GiB, D-099), never to the
margin alone. An unreadable or malformed file never lowers a floor: the margin and the Lambda launch floor both fall
back to FALLBACK_DISK_GIB and the reason says 'fallback'. `lambda_launch_floor_gib()` is the 10 GiB floor of the route (12 GiB until 20 November 2026, D-849)
request (D-726), unchanged by the 19 November decision.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / 'config' / 'launch_ram_floors.json'
DISK_CONFIG = Path(__file__).resolve().parents[2] / 'config' / 'laptop_disk_floor.json'
FALLBACK_GIB = 1.2
FALLBACK_DISK_GIB = 30.0   # the old fixed laptop floor (D-099): what an unreadable rule or an unknown footprint holds
GIB = 2 ** 30
FIXED = {'request': 'request', 'seal': 'seal', 'admit': 'admit', 'watch': 'watch'}
KINDS = ('request', 'seal', 'part', 'watch', 'admit', 'local')


def load(path=None):
    """The declaration, read now (never cached). Raises on a missing or malformed file."""
    cfg = json.loads(Path(path or CONFIG).read_text(encoding='utf-8'))
    if not isinstance(cfg, dict) or not isinstance(cfg.get('kinds'), dict):
        raise ValueError('launch_ram_floors.json has no kinds table')
    return cfg


def kind_of(step, lambda_steps=()):
    step = str(step or 'preflight')
    if step in FIXED:
        return FIXED[step]
    if step in tuple(lambda_steps or ()):
        return 'part'
    return 'local'


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def floor_gib(step, lambda_steps=(), path=None):
    """(floor in GiB, kind, source) for the step; source is 'config' or 'fallback'."""
    kind = kind_of(step, lambda_steps)
    try:
        cfg = load(path)
    except (OSError, ValueError):
        return FALLBACK_GIB, kind, 'fallback'
    entry = cfg['kinds'].get(kind)
    value = entry.get('floor_gib') if isinstance(entry, dict) else entry
    if _number(value):
        return float(value), kind, 'config'
    fallback = cfg.get('fallback_gib')
    return (float(fallback) if _number(fallback) else FALLBACK_GIB), kind, 'fallback'


def ram_problem(step, free_gib, lambda_steps=(), path=None):
    """None when free RAM holds the step's floor, else the preflight's problem line."""
    floor, kind, source = floor_gib(step, lambda_steps, path)
    try:
        free = float(free_gib)
    except (TypeError, ValueError):
        free = float('nan')
    if free >= floor:
        return None
    return 'free RAM %.2f GiB is under %.1f (step %s, kind %s, %s floor)' % (free, floor, step, kind, source)


def load_disk(path=None):
    """The laptop disk rule, read now (never cached). Raises on a missing or malformed file."""
    cfg = json.loads(Path(path or DISK_CONFIG).read_text(encoding='utf-8'))
    if not isinstance(cfg, dict):
        raise ValueError('laptop_disk_floor.json is not an object')
    return cfg


def _disk_value(key, path=None):
    try:
        value = load_disk(path).get(key)
    except (OSError, ValueError):
        return FALLBACK_DISK_GIB, 'fallback'
    if _number(value):
        return float(value), 'config'
    return FALLBACK_DISK_GIB, 'fallback'


def margin_gib(path=None):
    """(margin in GiB, source): the margin every heavy laptop job needs above its own footprint."""
    return _disk_value('margin_gib', path)


def lambda_launch_floor_gib(path=None):
    """(floor in GiB, source): the free disk a Lambda launch's laptop step (the route request) needs."""
    return _disk_value('lambda_launch_floor_gib', path)


def footprint_known(footprint_gib):
    return (isinstance(footprint_gib, (int, float)) and not isinstance(footprint_gib, bool)
            and math.isfinite(footprint_gib) and footprint_gib >= 0)


def required_gib(footprint_gib, path=None):
    """(required free GiB, margin, source, known): footprint + margin; an unknown footprint holds the fallback."""
    margin, source = margin_gib(path)
    if footprint_known(footprint_gib):
        return float(footprint_gib) + margin, margin, source, True
    return max(FALLBACK_DISK_GIB, margin), margin, source, False


def free_disk_gib(where=None):
    """Free disk in GiB on the drive of `where` (its nearest existing parent), default this checkout's drive."""
    p = Path(where) if where is not None else Path(__file__).resolve().parents[2]
    p = p.resolve()
    while not p.exists() and p != p.parent:
        p = p.parent
    return shutil.disk_usage(str(p)).free / GIB


def disk_problem(footprint_gib, free_gib=None, where=None, path=None):
    """None when free disk holds the job's footprint plus the margin, else the one-line reason."""
    need, margin, source, known = required_gib(footprint_gib, path)
    try:
        free = float(free_disk_gib(where) if free_gib is None else free_gib)
    except (TypeError, ValueError, OSError):
        free = float('nan')
    if free >= need:
        return None
    if known:
        return ('free disk %.2f GiB is under %.2f GiB (job footprint %.2f GiB + margin %.1f GiB, %s rule)'
                % (free, need, float(footprint_gib), margin, source))
    return ('free disk %.2f GiB is under %.2f GiB (job footprint not known: the %.0f GiB fallback floor holds; '
            'margin %.1f GiB, %s rule)' % (free, need, FALLBACK_DISK_GIB, margin, source))
