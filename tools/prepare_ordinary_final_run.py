"""Prepare only: hash-bound final ordinary workload, without model imports/cloud writes."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import zipfile

from prepare_cloud_run import git, make_source, pins, validate_wheels
from cloud_run_common import credential_locations
from ordinary_final_run import ARGV, TOPOLOGY, sha, read, write, require, cache_ref_bytes
from prepare_ordinary_final_assets import build_assets

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/fix/ordinary_final_cloud_run'
WHEELS = ROOT/'output/cloud_wheels/ordinary_final_cp312'


def runtime_source(source):
    names=git(ROOT,'ls-tree','-r','--name-only',source).decode().splitlines()
    names=[n for n in names if (n.startswith(('scripts/','config/','corpus_ingest/')) or
        n in ('requirements.txt','genesis.md','tools/run_local_demo.py','tools/score_corpus.py')) and
        not (n.endswith('_checks.py') or n.startswith('scripts/verify_') or '/fixtures/' in n)]
    with tarfile.open(fileobj=io.BytesIO(git(ROOT,'archive','--format=tar',source,'--',*names))) as archive:
        files={member.name:archive.extractfile(member).read().replace(b'\r\n',b'\n')
               for member in archive.getmembers() if member.isfile()}
    for name,data in files.items():
        require((ROOT/name).read_bytes().replace(b'\r\n',b'\n')==data,'Execution source differs from bound commit: '+name)
    return files


def prepare(output):
    global OUT
    original = OUT
    OUT = Path(output).resolve()
    require(not (OUT/'execution_manifest.json').exists(), 'Refuse to reseal an existing execution identity')
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ('runtime.candidate.lock','provider_inventory.json'):
        (OUT/name).write_bytes((original/name).read_bytes())
    source = git(ROOT, 'rev-parse', '2f0d0f7').decode().strip()
    files = runtime_source(source)
    # Only the explicitly selected ordinary input files may enter this bundle.
    files = {n:d for n,d in files.items() if not n.startswith('benchmark/')}
    corpus = ROOT/'benchmark/corpora/clinical_reference'
    workload = {}
    for name in ('context/result_sheet.md', 'context/analyte_reference_ranges.md', 'conventions/lab_conventions.md'):
        data = (corpus/name).read_bytes().replace(b'\r\n', b'\n')
        files['input/'+name] = data
        workload[name] = hashlib.sha256(data).hexdigest()
    files['input/context/_review_targets.json'] = (json.dumps(dict(source='operator',
        targets=['result_sheet.md'], grounding=['analyte_reference_ranges.md'], prior=[]), sort_keys=True)+'\n').encode()
    # Numerical/prompt helpers only; no training controller or datasets.
    for name in ('auditor_linear_core.py', 'auditor_classifier_lora_stable.py'):
        files['tools/'+name] = (ROOT/'tools'/name).read_bytes().replace(b'\r\n',b'\n')
    sys.path.insert(0, str(ROOT/'scripts'))
    import final_models
    spec = read(ROOT/'config/final_models.json')
    for role in ('producer','auditor'):
        _, paths = final_models.verify(role)
        for key, path in paths.items():
            files[spec[role]['files'][key]['path']] = path.read_bytes()
    for name, data in files.items():
        if not name.endswith(('.safetensors','.npy')):
            hits = credential_locations(data, name)
            require(not hits, 'Possible credential in '+name+'; stop without printing content')
    OUT.mkdir(exist_ok=True)
    make_source(files, OUT/'project.tar.gz')
    cache = Path.home()/'.cache/huggingface/hub'
    models = []
    for model, revision in read(ROOT/'tools/cloud_run/models.json').items():
        snapshot = cache/('models--'+model.replace('/','--'))/'snapshots'/revision
        allowed = (list(spec['producer']['base_hashes']) if model==spec['producer']['model_id'] else
                   list(spec['auditor']['base_hashes']) if model==spec['auditor']['model_id'] else
                   ['config.json','config_sentence_transformers.json','modules.json','sentence_bert_config.json',
                    'special_tokens_map.json','tokenizer.json','tokenizer_config.json','sentencepiece.bpe.model',
                    '1_Pooling/config.json','model.safetensors'])
        entries = {n:dict(sha256=sha(snapshot/n),bytes=(snapshot/n).stat().st_size) for n in allowed}
        if model != 'BAAI/bge-m3':
            role='producer' if model==spec['producer']['model_id'] else 'auditor'
            require({n:e['sha256'] for n,e in entries.items()} == spec[role]['base_hashes'], 'Base hashes changed')
        item = dict(model_id=model,revision=revision,files=entries)
        ref = cache_ref_bytes(item)
        item['cache_ref'] = dict(bytes=len(ref),sha256=hashlib.sha256(ref).hexdigest())
        models.append(item)
    locked = pins(OUT/'runtime.candidate.lock')
    wheels = validate_wheels(WHEELS, locked)
    runtime_files = {}
    for package, entry in wheels.items():
        with zipfile.ZipFile(WHEELS/entry['filename']) as archive:
            # Hash actual importable code/native libraries and package data. pip's
            # generated RECORD/entry-point scripts are deliberately not asserted.
            runtime_files[package] = {n:hashlib.sha256(archive.read(n)).hexdigest()
                for n in archive.namelist() if not n.endswith('/') and '.dist-info/' not in n
                and '.data/' not in n}
    write(OUT/'topology.json', TOPOLOGY)
    for name in ('ordinary_final_run.py','ordinary_final_summary.py','cloud_run_observer.py'):
        (OUT/name).write_bytes((ROOT/'tools'/name).read_bytes().replace(b'\r\n',b'\n'))
    install = ''.join(f'{n}=={locked[n]} --hash=sha256:{wheels[n]["sha256"]}\n' for n in sorted(locked))
    (OUT/'install.lock').write_text(install,encoding='utf8')
    support = {n:sha(OUT/n) for n in ('topology.json','ordinary_final_run.py','ordinary_final_summary.py','cloud_run_observer.py','install.lock')}
    provider = read(OUT/'provider_inventory.json')
    require(provider['instances']==[], 'Provider inventory not empty')
    selected = next(x for x in provider['instance_types'] if x['metadata']['type']=='gpu_1x_a10')
    require('us-east-1' in selected['regions'] and selected['metadata']['hourly_rate']<=1.29, 'A10 unavailable/rate changed')
    assets = build_assets(OUT/'assets.tar',models,wheels,cache,WHEELS)
    manifest = dict(schema_version=1,source_commit=source,source_archive_sha256=sha(OUT/'project.tar.gz'),
        classification='PREPARED_NOT_AUTHORIZED',max_runs=1,model_mode='final',multi_round=False,protected_test=False,
        workload=dict(name='clinical_reference',review_targets=1,grounding_documents=1,conventions=1,
                      files=workload,answer_key_transferred=False),
        project_files={n:hashlib.sha256(d).hexdigest() for n,d in sorted(files.items())},
        local_control_hashes={n:sha(ROOT/n) for n in ('tools/ordinary_final_watchdog.py',
            'tools/cloud_run_watchdog.py','tools/cloud_run_common.py','tools/ordinary_final_run.py')},
        support_files=support,models=models,assets_archive=assets,
        preparation_source_hashes={n:sha(ROOT/n) for n in
            ('tools/prepare_ordinary_final_run.py','tools/prepare_ordinary_final_assets.py')},
        packages=locked,wheels=wheels,runtime_file_hashes=runtime_files,
        argv=ARGV,topology=TOPOLOGY,provider='Lambda',region='us-east-1',instance=selected,
        provider_observed_at=provider['observed_at'],image=provider['images'][0],max_hourly_rate=1.29,
        soft_budget_usd=5,hard_ceiling_usd=7,workload_stop_reserve_seconds=900,termination_reserve_seconds=180,
        environment=dict(SHIMMER_MODEL_MODE='final',SHIMMER_BACKEND_PROFILE='local',
            CUBLAS_WORKSPACE_CONFIG=':4096:8',PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True',
            HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',
            HF_HUB_DISABLE_IMPLICIT_TOKEN='1',PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',
            TOKENIZERS_PARALLELISM='false'),
        restrictions=['no second instance','no automatic full-run retry','no tuning','no protected data',
                      'no multi-round','no benchmark workload substitution'],
        known_auditor_limitations=spec['auditor']['limitations'])
    write(OUT/'execution_manifest.json', manifest)
    write(OUT/'seal.json',dict(execution_manifest_sha256=sha(OUT/'execution_manifest.json'),
        source_commit=source,operator_authorized=False,classification='PREPARED_NOT_AUTHORIZED'))
    write(OUT/'transfer_plan.json',dict(
        project_archive=dict(path='project.tar.gz',sha256=sha(OUT/'project.tar.gz'),bytes=(OUT/'project.tar.gz').stat().st_size),
        model_bytes=sum(e['bytes'] for m in models for e in m['files'].values()),
        wheel_bytes=sum((WHEELS/e['filename']).stat().st_size for e in wheels.values()),
        model_cache_local=str(cache),wheelhouse_local=str(WHEELS),
        local_paths_not_transferred=True,credentials_transferred=False,
        assets_archive={k:v for k,v in assets.items() if k!='members'},
        model_delivery='Use sealed assets.tar; refs/main are exactly 40 ASCII revision bytes, no newline',
        excluded=['all benchmark answer keys','all other corpora','TRAIN/DEV/HOLDOUT datasets',
                  'multi-round data','operator input','durable state','credentials','Git history']))
    print('Prepared sealed ordinary final run; no authorization, model load or provisioning')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    prepare(parser.parse_args().output_dir)
