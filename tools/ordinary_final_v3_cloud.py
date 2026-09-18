"""One operator-authorized run bound exclusively to sealed bundle v3 (decoding policy restored).

The authorization names the manifest, seal, project archive and asset archive
digests below and the sealed source commit e4b52e6. HEAD has since moved by
evidence-only commits; what launches is the sealed archive, whose digest is bound
here and re-checked by the controller before transfer, so the runtime that
executes is e4b52e6's and nothing later. Nothing else about the controller,
workload, routing, models or budget changes.
"""
import ordinary_final_cloud as controller
from ordinary_final_run import read, write, sha, require

SOURCE_COMMIT = 'e4b52e6d352575c00eeeb2aabfd245ac4ee53505'
PREPARATION_COMMIT = '8d46fe9'  # the commit that sealed bundle v3; resolved to its full id below
MANIFEST = 'a2a8be14f3d9822fcf5dd2b5beb50bfd6e6586f78d5c1dc0aa219534a3d88bd7'
SEAL = '7638c3503f82607747cc744af27f8dc245f950a181d31afc42ef558409aeb8fc'
PROJECT_ARCHIVE = 'b70cbded794a9ad97dbc50f84db996fec4f50706df43ae69c7d5389f2b28879d'
ASSETS_ARCHIVE = '8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6'


def execute():
    from prepare_cloud_run import git
    preparation = git(controller.ROOT, 'rev-parse', PREPARATION_COMMIT).decode().strip()
    controller.BASE = controller.ROOT / 'docs/fix/ordinary_final_cloud_run_v3'
    controller.MANIFEST = MANIFEST
    controller.SEAL = SEAL
    controller.PREPARATION = preparation
    controller.INSTANCE_NAME = 'shimmer-ordinary-final-' + preparation[:7]
    b = controller.BASE
    require(sha(b / 'execution_manifest.json') == MANIFEST and sha(b / 'seal.json') == SEAL, 'Authorized identity changed')
    m = read(b / 'execution_manifest.json')
    require(m['source_commit'] == SOURCE_COMMIT, 'Sealed source commit differs from the authorization')
    require(m['source_archive_sha256'] == PROJECT_ARCHIVE, 'Project identity changed')
    require(sha(b / 'project.tar.gz') == PROJECT_ARCHIVE, 'Project archive bytes changed')
    assets = m['assets_archive']
    require(assets['filename'] == 'assets.tar' and assets['sha256'] == ASSETS_ARCHIVE, 'Asset identity changed')
    require(m['soft_budget_usd'] == 5 and m['hard_ceiling_usd'] == 7 and m['max_hourly_rate'] == 1.29, 'Budget differs from the authorization')
    require(m['model_mode'] == 'final' and m['multi_round'] is False and m['max_runs'] == 1, 'Scope differs from the authorization')
    require(not (b / 'LAUNCH_INTENT.json').exists(), 'Authorization already consumed')
    verified = read(b / 'asset_verification.json')
    require(verified['passed'] and verified['manifest_sha256'] == MANIFEST and verified['archive_sha256'] == ASSETS_ARCHIVE,
            'Asset verification absent for this identity')
    require(all(r['ref_bytes'] == 40 for r in verified['default_revision_resolutions']), 'Refs not verified at 40 bytes')
    require(read(b / 'AUTHORIZED_LOCAL_REVERIFICATION.json')['passed'], 'Local reverification missing')
    write(b / 'assets_transfer_archive.json', dict(path=(b / assets['filename']).relative_to(controller.ROOT).as_posix(),
          bytes=assets['bytes'], sha256=assets['sha256'], manifest_sha256=MANIFEST))
    write(b / 'v3_controller_identity.json', dict(wrapper_sha256=sha(__file__), controller_sha256=sha(controller.__file__),
          sealed_source_commit=SOURCE_COMMIT, preparation_commit=preparation, manifest_sha256=MANIFEST, seal_sha256=SEAL,
          maximum_instances=1, maximum_runs=1))
    controller.execute()


if __name__ == '__main__':
    execute()
