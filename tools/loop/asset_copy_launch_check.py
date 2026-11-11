#!/usr/bin/env python3
"""Fail on every loop launch since a date that uploaded the asset archive while the provider-side copy
could have been used (loop D-S107 item 1; the evidence for item 2).

It reads the run records through `tools/loop/upload_losses.py` (lane/savings' reader, unchanged): every
launch in the budget ledger since `--since`, its bundle found by its instance name, and the bundle's own
asset copy receipt, upload timing and archive. A launch counts against the rule when all of these hold:
  - it ran in us-east-1, where the filesystem lives;
  - it was not a sealed run (its bundle's `seal.json`; a sealed run never reads the copy);
  - it uploaded the archive (`assets_transfer_timing.json`) and did not use the copy;
  - and either it declared no copy, or the archive was already on the filesystem at its launch (an
    earlier launch seeded or matched it), so it could have read it.
A declared launch that uploaded a digest no earlier launch had placed is the one seed D-S107 item 5
allows, and is not counted. Exit 1 when any launch counts; each is printed with its upload minutes
and cost.

    py -3.12 -X utf8 tools/loop/asset_copy_launch_check.py --ledger docs/loop/private/budget_ledger.jsonl \
        --bundles external/s05 [--since 2026-11-05]

Read-only: it reads the ledger and the run records and writes nothing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import upload_losses  # noqa: E402

SINCE = '2026-11-05'
REGION = 'us-east-1'


def sealed_bundle(found, row):
    """True when the launch's bundle was sealed (a sealed run never reads the copy)."""
    folder = found.get(str(row.get('instance') or '').rsplit('-', 1)[-1])
    seal = upload_losses._read(Path(folder) / 'seal.json') if folder else None
    return bool(seal and seal.get('exposure') == 'sealed')


def could_have_used(row, sealed):
    """D-S107 item 1: the launch row uploaded while the copy could have been used."""
    if row.get('region') != REGION or sealed or row.get('upload_seconds') is None or row.get('used'):
        return False
    return not row.get('declared') or bool(row.get('copy_on_filesystem_at_launch'))


def check(ledger, bundles_root, since=SINCE):
    result = upload_losses.table(ledger, bundles_root, since)
    found = upload_losses.bundles(bundles_root)
    findings = [row for row in result['rows'] if could_have_used(row, sealed_bundle(found, row))]
    return dict(since=since, launches_read=len(result['rows']), findings=findings,
                upload_minutes=round(sum(r['upload_seconds'] for r in findings) / 60, 1),
                upload_cost_usd=round(sum(r.get('upload_usd') or 0 for r in findings), 2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ledger', required=True)
    parser.add_argument('--bundles', required=True)
    parser.add_argument('--since', default=SINCE)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    result = check(args.ledger, args.bundles, args.since)
    if args.json:
        print(json.dumps(result, indent=1))
    for r in result['findings']:
        print('UPLOADED %s %s %s declared=%s state=%s on_filesystem=%s %.1f min %.2f USD' % (
            str(r.get('requested_utc'))[:16], r.get('purpose'), r.get('bundle'), r.get('declared'), r.get('state'),
            r.get('copy_on_filesystem_at_launch'), r['upload_seconds'] / 60, r.get('upload_usd') or 0))
    print('%d of %d loop launches since %s uploaded the archive while the copy could have been used: '
          '%.1f minutes, %.2f USD' % (len(result['findings']), result['launches_read'], result['since'],
                                      result['upload_minutes'], result['upload_cost_usd']))
    return 1 if result['findings'] else 0


if __name__ == '__main__':
    sys.exit(main())
