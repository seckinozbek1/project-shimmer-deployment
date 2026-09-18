"""Local, model-free reverification of a sealed bundle against its authorization binding.

Proves, without loading a model or touching the provider:
  1. manifest, seal, project archive and asset archive digests equal the binding;
  2. the project archive is an exact tree of the manifest's project_files;
  3. every archived file the sealed commit's tree carries is byte-identical (LF-normalised)
     to `git show <sealed commit>:<name>`, and HEAD differs from it only under docs/fix;
  4. the decoding policy resolved from the ARCHIVED declaration and protocols equals the
     manifest's record, protocol digests included;
  5. the generated Hub refs inside the asset archive are exactly 40 ASCII bytes of the
     admitted revisions;
  6. the operator-side control, support and preparation sources still hash to the manifest.
Writes AUTHORIZED_LOCAL_REVERIFICATION.json, which the bound controller requires.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tools')]
from ordinary_final_run import read, sha, require, write, cache_ref_bytes
import decoding_policy


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True).stdout


def main(bundle):
    base = Path(bundle).resolve()
    binding = read(base / 'authorization_binding.json')
    receipt = dict(passed=False, model_workload=False, provider_contacted=False, binding=binding)
    manifest_sha = sha(base / 'execution_manifest.json')
    seal_sha = sha(base / 'seal.json')
    require(manifest_sha == binding['manifest_sha256'], 'Manifest digest differs from the binding')
    require(seal_sha == binding['seal_sha256'], 'Seal digest differs from the binding')
    m = read(base / 'execution_manifest.json')
    seal = read(base / 'seal.json')
    require(seal['execution_manifest_sha256'] == manifest_sha and seal['source_commit'] == binding['source_commit'], 'Seal does not bind this manifest')
    require(m['source_commit'] == binding['source_commit'], 'Manifest source commit differs from the binding')
    require(m['source_archive_sha256'] == binding['project_sha256'] and sha(base / 'project.tar.gz') == binding['project_sha256'], 'Project archive differs')
    require(m['assets_archive']['sha256'] == binding['assets_sha256'], 'Asset archive identity differs')
    receipt.update(manifest_sha256=manifest_sha, seal_sha256=seal_sha, project_sha256=binding['project_sha256'],
                   assets_sha256=binding['assets_sha256'], source_commit=binding['source_commit'])
    with tarfile.open(base / 'project.tar.gz') as archive:
        members = {x.name: archive.extractfile(x).read() for x in archive.getmembers() if x.isfile()}
    expected = m['project_files']
    require(set(members) == set(expected), 'Archive inventory differs from the manifest')
    for name, data in members.items():
        require(hashlib.sha256(data).hexdigest() == expected[name], 'Archive member digest mismatch: ' + name)
    tree = set(git('ls-tree', '-r', '--name-only', binding['source_commit']).decode().splitlines())
    compared = 0
    for name, data in members.items():
        if name in tree:
            require(git('show', binding['source_commit'] + ':' + name).replace(b'\r\n', b'\n') == data,
                    'Archived runtime differs from sealed commit: ' + name)
            compared += 1
    generated = sorted(n for n in members if n not in tree)
    for name in generated:
        require(name.startswith('input/') or name.startswith('docs/fix/'), 'Unexpected non-committed archive member: ' + name)
    moved = git('diff', '--name-only', binding['source_commit'], 'HEAD').decode().splitlines()
    require(all(n.startswith('docs/fix/') for n in moved),
            'HEAD changed runtime files after the sealed commit: ' + str([n for n in moved if not n.startswith('docs/fix/')]))
    receipt.update(project_tree_verified=True, archive_members=len(members), members_compared_to_sealed_commit=compared,
                   generated_members=generated, head_commit=git('rev-parse', 'HEAD').decode().strip(),
                   head_moved_by_evidence_only=moved, sealed_runtime_is_what_launches=True)
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
    refs = {}
    with tarfile.open(base / m['assets_archive']['filename']) as archive:
        for member in archive:
            if member.name.endswith('/refs/main'):
                refs[member.name] = archive.extractfile(member).read()
    require(len(refs) == len(m['models']), 'Ref count differs from the model count')
    for model in m['models']:
        name = 'hf_cache/hub/models--' + model['model_id'].replace('/', '--') + '/refs/main'
        require(refs[name] == cache_ref_bytes(model) and len(refs[name]) == 40, 'Ref is not the exact 40-byte revision: ' + model['model_id'])
    receipt.update(refs_exact_40_bytes={k: len(v) for k, v in refs.items()})
    for name, digest in m['local_control_hashes'].items():
        require(sha(ROOT / name) == digest, 'Controller source changed: ' + name)
    for name, digest in m['support_files'].items():
        require(sha(base / name) == digest, 'Support file changed: ' + name)
    for name, digest in m['preparation_source_hashes'].items():
        require(sha(ROOT / name) == digest, 'Preparation source changed: ' + name)
    receipt.update(source_tests_and_validation_hashes_match=True, passed=True)
    write(base / 'AUTHORIZED_LOCAL_REVERIFICATION.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k not in ('decoding_policy_admitted', 'binding')}, indent=2, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    main(parser.parse_args().bundle)
