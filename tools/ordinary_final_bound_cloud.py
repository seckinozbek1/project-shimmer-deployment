"""One operator-authorized run bound to the sealed bundle named by its authorization_binding.json.

The binding file, written when the bundle is sealed and checked here before
anything else, names the sealed source commit, the manifest, seal, project archive
and asset archive digests and the preparation commit. The controller is bound to
exactly those values and refuses on any difference, on a consumed authorization or
without a passed local reverification. HEAD may have moved by evidence-only
commits; what launches is the sealed archive whose digest is bound here.
"""
import argparse
from pathlib import Path

import ordinary_final_cloud as controller
from ordinary_final_run import read, write, sha, require


def execute(bundle):
    b = Path(bundle).resolve()
    binding = read(b / 'authorization_binding.json')
    controller.BASE = b
    controller.MANIFEST = binding['manifest_sha256']
    controller.SEAL = binding['seal_sha256']
    controller.PREPARATION = binding['preparation_commit']
    controller.INSTANCE_NAME = 'shimmer-ordinary-final-' + binding['preparation_commit'][:7]
    require(sha(b / 'execution_manifest.json') == binding['manifest_sha256'] and sha(b / 'seal.json') == binding['seal_sha256'],
            'Authorized identity changed')
    m = read(b / 'execution_manifest.json')
    require(m['source_commit'] == binding['source_commit'], 'Sealed source commit differs from the binding')
    require(m['source_archive_sha256'] == binding['project_sha256'], 'Project identity changed')
    require(sha(b / 'project.tar.gz') == binding['project_sha256'], 'Project archive bytes changed')
    assets = m['assets_archive']
    require(assets['filename'] == 'assets.tar' and assets['sha256'] == binding['assets_sha256'], 'Asset identity changed')
    require(m['soft_budget_usd'] == 5 and m['hard_ceiling_usd'] == 7 and m['max_hourly_rate'] == 1.29, 'Budget differs from the authorization')
    require(m['model_mode'] == 'final' and m['multi_round'] is False and m['max_runs'] == 1, 'Scope differs from the authorization')
    require(not (b / 'LAUNCH_INTENT.json').exists(), 'Authorization already consumed')
    verified = read(b / 'asset_verification.json')
    require(verified['passed'] and verified['manifest_sha256'] == binding['manifest_sha256']
            and verified['archive_sha256'] == binding['assets_sha256'], 'Asset verification absent for this identity')
    require(all(r['ref_bytes'] == 40 for r in verified['default_revision_resolutions']), 'Refs not verified at 40 bytes')
    local = read(b / 'AUTHORIZED_LOCAL_REVERIFICATION.json')
    require(local['passed'] and local['manifest_sha256'] == binding['manifest_sha256'], 'Local reverification missing')
    live = read(b / 'authorized_live_preflight.json')
    require(live['passed'] and live['manifest_sha256'] == binding['manifest_sha256'], 'Live preflight missing')
    write(b / 'assets_transfer_archive.json', dict(path=(b / assets['filename']).relative_to(controller.ROOT).as_posix(),
          bytes=assets['bytes'], sha256=assets['sha256'], manifest_sha256=binding['manifest_sha256']))
    write(b / 'bound_controller_identity.json', dict(wrapper_sha256=sha(__file__), controller_sha256=sha(controller.__file__),
          binding=binding, maximum_instances=1, maximum_runs=1))
    controller.execute()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    execute(parser.parse_args().bundle)
