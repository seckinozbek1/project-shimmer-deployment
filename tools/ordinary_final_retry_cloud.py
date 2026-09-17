"""One operator-authorized retry bound exclusively to the fixed eb71e6b seal."""
import ordinary_final_cloud as controller
from ordinary_final_run import read, write, sha, require


def execute():
    controller.BASE=controller.ROOT/'docs/fix/ordinary_final_cloud_run_v2'
    controller.MANIFEST='f06584d937b732fe65b5966081768ad922751c6e7cc0324d45b74c49ad3552b5'
    controller.SEAL='96f2f496d37b009423f231e660ab5ec7ef41b93a46b07aefd5c3030e95302701'
    controller.PREPARATION='eb71e6b9e1e43ee03855f686a277a08f8c503689'
    controller.INSTANCE_NAME='shimmer-ordinary-final-eb71e6b'
    b=controller.BASE
    require(sha(b/'execution_manifest.json')==controller.MANIFEST and sha(b/'seal.json')==controller.SEAL,'Authorized identity changed')
    m=read(b/'execution_manifest.json')
    require(m['source_archive_sha256']=='4867e1db33e656117844028d647744a6316f2a6b8154949cde9087a1f08c138a','Project identity changed')
    assets=m['assets_archive']
    require(assets['filename']=='assets.tar' and assets['sha256']=='8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6','Asset identity changed')
    require(not (b/'LAUNCH_INTENT.json').exists(),'Retry authorization already consumed')
    verified=read(b/'asset_verification.json')
    require(verified['passed'] and verified['manifest_sha256']==controller.MANIFEST and verified['archive_sha256']==assets['sha256'],'Asset verification absent')
    require(all(r['ref_bytes']==40 for r in verified['default_revision_resolutions']),'Refs not verified')
    write(b/'assets_transfer_archive.json',dict(path=(b/assets['filename']).relative_to(controller.ROOT).as_posix(),
        bytes=assets['bytes'],sha256=assets['sha256'],manifest_sha256=controller.MANIFEST))
    write(b/'retry_controller_identity.json',dict(wrapper_sha256=sha(__file__),controller_sha256=sha(controller.__file__),
        preparation_commit=controller.PREPARATION,manifest_sha256=controller.MANIFEST,maximum_instances=1,maximum_runs=1))
    controller.execute()


if __name__=='__main__':execute()
