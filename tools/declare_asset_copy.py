"""Write the operator's provider-side asset-copy declaration into a sealed bundle.

The declaration names a filesystem the OPERATOR created; nothing here creates,
resizes, deletes or prices a provider resource, and the provider adapter has no
endpoint that could (see docs/DEPLOYMENT_RESOURCES.md). It records, in the bundle
that will launch, which filesystem to attach and where the instance mounts it, so
the controller's copy path has a declaration to read and the launch receipt names
the resource the run used.

    py -3.12 tools/declare_asset_copy.py --bundle <bundle> --filesystem-name <name> --mount </lambda/nfs/name>

The bundle's own manifest supplies the archive digest the copy is keyed by, so a
declaration cannot name one archive and a bundle another.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path[:0] = [str(ROOT / 'tools')]
from ordinary_final_run import read, write, require


def declare(bundle, filesystem_name, mount, *, operator_authorized=True):
    """Write asset_copy_declaration.json into `bundle` and return it."""
    bundle = Path(bundle)
    manifest = read(bundle / 'execution_manifest.json')
    digest = manifest['assets_archive']['sha256']
    require(isinstance(filesystem_name, str) and filesystem_name and len(filesystem_name) <= 128,
            'A filesystem name is required')
    require(isinstance(mount, str) and mount.startswith('/') and len(mount) > 1,
            'An absolute mount path is required')
    declaration = dict(operator_authorized=bool(operator_authorized), filesystem_name=filesystem_name,
                       mount=mount.rstrip('/'), assets_sha256=digest,
                       copy_path=mount.rstrip('/') + '/assets-' + digest + '.tar',
                       note=('The operator created this filesystem by hand; no tool in this repository can '
                             'create, resize, price or delete a provider filesystem. Its footprint, '
                             'verification and deletion rule are in docs/DEPLOYMENT_RESOURCES.md.'))
    write(bundle / 'asset_copy_declaration.json', declaration)
    return declaration


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--filesystem-name', required=True)
    parser.add_argument('--mount', required=True)
    arguments = parser.parse_args(argv)
    declaration = declare(arguments.bundle, arguments.filesystem_name, arguments.mount)
    print(json.dumps(declaration, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
