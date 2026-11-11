"""Stage a built benchmark bundle as the ordinary final sealer's workload folder.

The sealer (tools/prepare_ordinary_final_run.py --workload) reads a folder holding exactly:

  _review_targets.json     the targets file, at the TOP of the folder
  context/                 the documents
  conventions/             the operator's rules
  case_manifest.json       only for a declared multi-round case

An adapter build (benchmark/adapters) and a generator build (benchmark/generators) write
each bundle as context/ (with context/_review_targets.json inside it), conventions/ and
answer_key.json, and a generator's multi-round case also case_manifest.json; an adapter
writes its item table, items.json, beside the bundles. This tool copies a bundle into the
sealer's layout byte for byte (the sealer does its own line-ending normalisation) and copies
nothing else: never the answer key, never parts.json or any other build record. Any file
under context/ or conventions/ whose name reads like a key (answer, key or gold as a word of
its name, or the answer key's own name) refuses the whole staging before anything is written.

For a B1 bundle it also writes the item table the sealer's --items takes: the rows of the
build's items.json for this bundle's ONE document, with only the four fields bare_model.py
reads (item_id, document_id, rule_id, benchmark). It is written OUTSIDE the workload folder,
because the sealer refuses any other member there.

  py -3.12 tools/stage_workload.py --bundle <build>/<bundle> --out <folder> [--items-out <file>]
  py -3.12 tools/stage_workload.py --build <build> --out <folder>
      every bundle of a build: <folder>/<bundle>/workload/ and, when the build has an
      items.json, <folder>/<bundle>/items.json

It prints counts only, never document text. No model, provider or network is touched.
"""
import argparse
import json
from pathlib import Path
import re
import sys

TARGETS = '_review_targets.json'
CASE_MANIFEST = 'case_manifest.json'
ITEM_TABLE = 'items.json'
FOLDERS = ('context', 'conventions')
ITEM_FIELDS = ('item_id', 'document_id', 'rule_id', 'benchmark')
# A name that reads like a key: answer, key or gold as a word of the file name (words split on
# anything that is not a letter or digit), or the answer key's own name.
KEY_WORDS = frozenset({'answer', 'key', 'keys', 'gold'})


class StagingError(RuntimeError):
    pass


def refuse(condition, message):
    if not condition:
        raise StagingError(message)


def key_like(name):
    """True when a file name reads like an answer key."""
    words = {w for w in re.split(r'[^a-z0-9]+', Path(name).name.lower()) if w}
    return bool(words & KEY_WORDS) or 'answer_key' in name.lower()


def bundle_files(bundle):
    """{workload member name: source path} for one built bundle, refused on anything unsafe."""
    bundle = Path(bundle)
    refuse(bundle.is_dir(), 'Bundle folder not found: ' + bundle.name)
    refuse((bundle / 'context' / TARGETS).is_file(), 'Bundle has no context/' + TARGETS + ': ' + bundle.name)
    members = {TARGETS: bundle / 'context' / TARGETS}
    for folder in FOLDERS:
        root = bundle / folder
        refuse(root.is_dir(), 'Bundle has no %s/ folder: %s' % (folder, bundle.name))
        for path in sorted(root.rglob('*')):
            refuse(not path.is_symlink(), 'A bundle member is a link: ' + path.name)
            if not path.is_file() or (folder == 'context' and path.relative_to(root).as_posix() == TARGETS):
                continue
            refuse(not key_like(path.name), 'A file named like a key is in the bundle\'s %s/: %s' % (folder, path.name))
            members[folder + '/' + path.relative_to(root).as_posix()] = path
    if (bundle / CASE_MANIFEST).is_file():
        members[CASE_MANIFEST] = bundle / CASE_MANIFEST
    return members


def document_id(bundle):
    """The one document under review: the stem of the targets file's only target."""
    targets = json.loads((Path(bundle) / 'context' / TARGETS).read_text(encoding='utf-8')).get('targets') or []
    refuse(len(targets) == 1, 'A benchmark bundle names exactly one document under review')
    return Path(targets[0]).stem


def item_table(bundle, items):
    """The B1 item table for this bundle's document: only the fields bare_model.py reads."""
    data = json.loads(Path(items).read_text(encoding='utf-8'))
    rows = data.get('items') if isinstance(data, dict) else data
    refuse(isinstance(rows, list), 'items.json holds no item table')
    doc = document_id(bundle)
    chosen = sorted(({k: r[k] for k in ITEM_FIELDS} for r in rows
                     if isinstance(r, dict) and str(r.get('document_id')) == doc),
                    key=lambda r: str(r['item_id']))
    refuse(chosen and all(all(r.get(k) for k in ITEM_FIELDS) for r in chosen),
           'items.json holds no complete item for the document under review')
    value = {'items': chosen}
    if isinstance(data, dict) and data.get('benchmark'):
        value = {'benchmark': data['benchmark'], 'items': chosen}
    return value


def copy_member(source, target):
    """Byte for byte: line endings are the sealer's to normalise, never the staging's."""
    target.write_bytes(source.read_bytes())


def stage(bundle, out, items_out=None, items=None):
    """Stage one bundle into `out` (absent or empty). With `items_out`, also write its B1 item
    table from `items` (default: items.json beside the bundle). Returns counts."""
    bundle, out = Path(bundle), Path(out)
    members = bundle_files(bundle)
    refuse(not out.exists() or not any(out.iterdir()), 'The workload folder is not empty: ' + out.name)
    table = None
    if items_out is not None:
        items = Path(items) if items else bundle.parent / ITEM_TABLE
        refuse(items.is_file(), 'No items.json for this bundle: B1 needs the build\'s item table')
        table = item_table(bundle, items)
        refuse(not Path(items_out).resolve().is_relative_to(out.resolve()),
               'The item table goes outside the workload folder')
    for name, source in members.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        copy_member(source, target)
    if table is not None:
        Path(items_out).parent.mkdir(parents=True, exist_ok=True)
        Path(items_out).write_text(json.dumps(table, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    left = sorted(p.name for p in bundle.iterdir() if p.name not in (*FOLDERS, CASE_MANIFEST))
    return dict(bundle=bundle.name, members=len(members), multi_round=CASE_MANIFEST in members,
                items=len(table['items']) if table else None, not_copied=len(left))


def stage_build(build, out):
    """Stage every bundle of a build (each sub-folder holding context/_review_targets.json)."""
    build, out = Path(build), Path(out)
    bundles = sorted(p for p in build.iterdir() if (p / 'context' / TARGETS).is_file())
    refuse(bundles, 'No bundle in the build folder')
    refuse(not out.exists() or not any(out.iterdir()), 'The output folder is not empty')
    items = build / ITEM_TABLE if (build / ITEM_TABLE).is_file() else None
    # Every bundle is checked before the first is written, so a refusal leaves nothing behind.
    for bundle in bundles:
        bundle_files(bundle)
        if items:
            item_table(bundle, items)
    return [stage(b, out / b.name / 'workload', out / b.name / ITEM_TABLE if items else None, items) for b in bundles]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], allow_abbrev=False)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--bundle', type=Path, help='one built bundle folder')
    source.add_argument('--build', type=Path, help='a build folder: every bundle in it')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--items-out', type=Path, help='with --bundle: write the B1 item table here')
    parser.add_argument('--items', type=Path, help='with --bundle: the build\'s items.json (default: beside the bundle)')
    args = parser.parse_args(argv)
    try:
        if args.build:
            refuse(args.items_out is None and args.items is None, '--items-out and --items go with --bundle')
            result = stage_build(args.build, args.out)
        else:
            result = [stage(args.bundle, args.out, args.items_out, args.items)]
    except (StagingError, OSError, ValueError) as exc:
        print('staging refused: %s' % exc, file=sys.stderr)
        return 2
    print(json.dumps(dict(bundles=len(result), members=sum(r['members'] for r in result),
                          multi_round=sum(r['multi_round'] for r in result),
                          items=sum(r['items'] or 0 for r in result)), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
