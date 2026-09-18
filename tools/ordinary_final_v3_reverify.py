"""Local, model-free reverification of sealed bundle v3 before its one authorized launch.

Proves, without loading a model or touching the provider:
  1. manifest, seal, project archive and asset archive digests equal the authorized values;
  2. the project archive is an exact tree: every member's digest is in the manifest's
     project_files and every project_files entry is present, nothing extra;
  3. the runtime in the archive IS sealed commit e4b52e6: every archived file that the
     commit's tree carries is byte-identical (LF-normalised) to `git show e4b52e6:<name>`,
     and HEAD differs from e4b52e6 only under docs/fix (evidence);
  4. the decoding policy resolved from the ARCHIVED declaration and protocols equals the
     manifest's recorded policy, protocol digests included (the admission check the remote
     runner performs, executed here first);
  5. the three generated Hub refs inside the asset archive are exactly 40 ASCII bytes of the
     admitted revisions;
  6. the operator-side controller sources still hash to the manifest's local_control_hashes
     and the support files to support_files.
Writes AUTHORIZED_LOCAL_REVERIFICATION.json, which the controller requires.
"""
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/fix/ordinary_final_cloud_run_v3'
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tools')]
from ordinary_final_run import read, sha, require, write, cache_ref_bytes
import decoding_policy

AUTHORIZED = dict(
    source_commit='e4b52e6d352575c00eeeb2aabfd245ac4ee53505',
    manifest='a2a8be14f3d9822fcf5dd2b5beb50bfd6e6586f78d5c1dc0aa219534a3d88bd7',
    seal='7638c3503f82607747cc744af27f8dc245f950a181d31afc42ef558409aeb8fc',
    project='b70cbded794a9ad97dbc50f84db996fec4f50706df43ae69c7d5389f2b28879d',
    assets='8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6')


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True).stdout


def main():
    receipt = dict(passed=False, model_workload=False, provider_contacted=False)
    manifest_sha = sha(BASE / 'execution_manifest.json')
    seal_sha = sha(BASE / 'seal.json')
    require(manifest_sha == AUTHORIZED['manifest'], 'Manifest digest differs from the authorization')
    require(seal_sha == AUTHORIZED['seal'], 'Seal digest differs from the authorization')
    m = read(BASE / 'execution_manifest.json')
    seal = read(BASE / 'seal.json')
    require(seal['execution_manifest_sha256'] == manifest_sha and seal['source_commit'] == AUTHORIZED['source_commit'], 'Seal does not bind this manifest')
    require(m['source_commit'] == AUTHORIZED['source_commit'], 'Manifest source commit differs from the authorization')
    require(m['source_archive_sha256'] == AUTHORIZED['project'] and sha(BASE / 'project.tar.gz') == AUTHORIZED['project'], 'Project archive differs')
    require(m['assets_archive']['sha256'] == AUTHORIZED['assets'], 'Asset archive identity differs')
    receipt.update(manifest_sha256=manifest_sha, seal_sha256=seal_sha, project_sha256=AUTHORIZED['project'],
                   assets_sha256=AUTHORIZED['assets'], source_commit=AUTHORIZED['source_commit'])

    # 2 and 3: exact tree, and the tree is the sealed commit's runtime.
    with tarfile.open(BASE / 'project.tar.gz') as archive:
        members = {x.name: archive.extractfile(x).read() for x in archive.getmembers() if x.isfile()}
    expected = m['project_files']
    require(set(members) == set(expected), 'Archive inventory differs from the manifest')
    for name, data in members.items():
        require(hashlib.sha256(data).hexdigest() == expected[name], 'Archive member digest mismatch: ' + name)
    tree = set(git('ls-tree', '-r', '--name-only', AUTHORIZED['source_commit']).decode().splitlines())
    compared = 0
    for name, data in members.items():
        if name in tree:
            committed = git('show', AUTHORIZED['source_commit'] + ':' + name).replace(b'\r\n', b'\n')
            require(committed == data, 'Archived runtime differs from sealed commit: ' + name)
            compared += 1
    generated = sorted(n for n in members if n not in tree)
    for name in generated:
        require(name.startswith('input/') or name.startswith('docs/fix/'), 'Unexpected non-committed archive member: ' + name)
    moved = git('diff', '--name-only', AUTHORIZED['source_commit'], 'HEAD').decode().splitlines()
    require(all(n.startswith('docs/fix/') for n in moved), 'HEAD changed runtime files after the sealed commit: ' + str([n for n in moved if not n.startswith('docs/fix/')]))
    head = git('rev-parse', 'HEAD').decode().strip()
    receipt.update(project_tree_verified=True, archive_members=len(members), members_compared_to_sealed_commit=compared,
                   generated_members=generated, head_commit=head, head_moved_by_evidence_only=moved,
                   sealed_runtime_is_what_launches=True)

    # 4: the decoding policy resolved from the archived files equals the manifest record.
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for name in [decoding_policy.DECLARATION] + [n for n in members if n.startswith('tuning/')]:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(members[name])
        resolved = {b: dict(status=p['status'], source=p['source'], sha256=p['sha256'], kwargs=p['kwargs'])
                    for b, p in decoding_policy.summary(root).items()}
    require(resolved == m['decoding_policy'], 'Decoding policy resolved from the archive differs from the manifest record')
    for backend, entry in resolved.items():
        require(entry['kwargs']['do_sample'] is False and entry['kwargs']['num_beams'] == 1, 'Policy not greedy: ' + backend)
    receipt.update(decoding_policy_admitted=resolved)

    # 5: the generated refs inside the asset archive are exactly the admitted 40 bytes.
    refs = {}
    with tarfile.open(BASE / m['assets_archive']['filename']) as archive:
        for member in archive:
            if member.name.endswith('/refs/main'):
                data = archive.extractfile(member).read()
                refs[member.name] = data
    require(len(refs) == len(m['models']), 'Ref count differs from the model count')
    for model in m['models']:
        name = 'hf_cache/hub/models--' + model['model_id'].replace('/', '--') + '/refs/main'
        require(refs[name] == cache_ref_bytes(model) and len(refs[name]) == 40, 'Ref is not the exact 40-byte revision: ' + model['model_id'])
    receipt.update(refs_exact_40_bytes={k: len(v) for k, v in refs.items()})

    # 6: operator-side control and support sources unchanged since sealing.
    for name, digest in m['local_control_hashes'].items():
        require(sha(ROOT / name) == digest, 'Controller source changed: ' + name)
    for name, digest in m['support_files'].items():
        require(sha(BASE / name) == digest, 'Support file changed: ' + name)
    for name, digest in m['preparation_source_hashes'].items():
        require(sha(ROOT / name) == digest, 'Preparation source changed: ' + name)
    receipt.update(source_tests_and_validation_hashes_match=True, passed=True)
    write(BASE / 'AUTHORIZED_LOCAL_REVERIFICATION.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'decoding_policy_admitted'}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
