"""D-S107 item 2 (D-405): what uploading the asset archive cost, read from the run records only.

For every loop launch in the budget ledger from a date on, the bundle it launched (found by its instance name,
which ends in the first eight hex digits of the bundle's execution_manifest.json digest), and from that bundle's
own records: the asset copy receipt (declared, state, seeded, used), the archive's digest and size, the upload
phase's measured seconds and return code (assets_transfer_timing.json), the probe's status, and the ledger's
billed minutes, price and cost. A copy "was on the filesystem" for a launch only when an earlier launch's
receipt records that digest seeded or matched. Nothing here starts a process, writes a file or reads a key.

    py -3.12 -X utf8 tools/loop/upload_losses.py --ledger docs/loop/private/budget_ledger.jsonl \
        --bundles external/s05 [--since 2026-11-05] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SKIP_DIRS = ("D-S56",)   # the fresh set's folder is never read


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def bundles(root):
    """{first eight hex digits of a manifest digest: bundle folder} under `root`, the fresh set's folder left out."""
    out = {}
    for manifest in Path(root).rglob("execution_manifest.json"):
        if any(part in SKIP_DIRS for part in manifest.parts) or "downloaded" in manifest.parts or "batch" in manifest.parts:
            continue
        key, folder = _sha(manifest)[:8], manifest.parent
        launched = (folder / "LAUNCH_INTENT.json").is_file()
        # the launched bundle wins over a copy of its manifest elsewhere (an extracted evidence folder)
        if key not in out or (launched and not (out[key] / "LAUNCH_INTENT.json").is_file()):
            out[key] = folder
    return out


def launches(ledger, since):
    rows = [json.loads(line) for line in Path(ledger).read_text(encoding="utf-8").splitlines() if line.strip()]
    ends = {r.get("instance_name"): r for r in rows if r.get("event") == "termination"}
    return [dict(r, end=ends.get(r.get("instance_name"))) for r in rows
            if r.get("event") == "launch" and str(r.get("time_utc", "")) >= since]


def read_launch(launch, found):
    name = launch.get("instance_name") or ""
    bundle = found.get(name.rsplit("-", 1)[-1])
    end = launch.get("end") or {}
    row = {"purpose": launch.get("purpose"), "instance": name, "requested_utc": launch.get("launch_requested_utc"),
           "region": launch.get("region"), "price_usd_per_hour": launch.get("price_usd_per_hour"),
           "billed_minutes": end.get("actual_minutes"), "cost_usd": end.get("actual_cost"),
           "bundle": None if bundle is None else bundle.name}
    if bundle is None:
        return dict(row, note="no bundle found for this instance name")
    manifest = _read(bundle / "execution_manifest.json") or {}
    receipt = _read(bundle / "asset_copy_receipt.json") or {}
    upload = _read(bundle / "assets_transfer_timing.json")
    probe = _read(bundle / "asset_copy_probe_status.json")
    assets = manifest.get("assets_archive") or {}
    row.update(archive=str(assets.get("sha256", ""))[:8], archive_gb=round((assets.get("bytes") or assets.get("size_bytes") or 0) / 1e9, 2),
               declared=receipt.get("declared"), state=receipt.get("state"), seeded=receipt.get("seeded"), used=receipt.get("used"),
               upload_seconds=None if upload is None else round(upload.get("seconds", 0), 1),
               upload_returncode=None if upload is None else upload.get("returncode"),
               probe=None if probe is None else {k: probe.get(k) for k in ("state", "error", "returncode") if k in probe})
    if upload is not None and row["price_usd_per_hour"]:
        row["upload_usd"] = round(upload.get("seconds", 0) / 3600 * float(row["price_usd_per_hour"]), 4)
    return row


def table(ledger, root, since):
    found, on_filesystem, rows = bundles(root), {}, []
    for launch in sorted(launches(ledger, since), key=lambda r: r.get("launch_requested_utc") or ""):
        row = read_launch(launch, found)
        digest = row.get("archive")
        row["copy_on_filesystem_at_launch"] = on_filesystem.get(digest)
        rows.append(row)
        if digest and (row.get("seeded") or row.get("state") == "MATCH"):
            on_filesystem.setdefault(digest, row["purpose"] + " " + str(row.get("requested_utc"))[:16])
    uploaded = [r for r in rows if r.get("upload_seconds") is not None]
    totals = {"launches": len(rows), "uploaded": len(uploaded),
              "upload_minutes": round(sum(r["upload_seconds"] for r in uploaded) / 60, 1),
              "upload_usd": round(sum(r.get("upload_usd", 0) for r in uploaded), 2),
              "uploaded_with_copy_on_filesystem": sum(1 for r in uploaded if r["copy_on_filesystem_at_launch"])}
    return {"since": since, "rows": rows, "totals": totals}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--bundles", required=True)
    parser.add_argument("--since", default="2026-11-05")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = table(args.ledger, args.bundles, args.since)
    if args.json:
        print(json.dumps(result, indent=1))
        return 0
    for r in result["rows"]:
        print("%-26s %-9s up=%-8s rc=%-4s copy=%-6s/%-8s seeded=%-5s on_fs=%s  billed=%s min %s USD  upload %s USD" % (
            r["purpose"], r.get("archive"), r.get("upload_seconds"), r.get("upload_returncode"), r.get("declared"),
            r.get("state"), r.get("seeded"), r.get("copy_on_filesystem_at_launch"), r.get("billed_minutes"),
            r.get("cost_usd"), r.get("upload_usd")))
    print(json.dumps(result["totals"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
