"""Prepare only: hash-bound final ordinary workload, without model imports/cloud writes.

Defaults are the development path as it always was: the clinical workload, the bundle under
docs/fix/, an exposed run. Everything a loop launch or a sealed test needs is a parameter:
  --workload           a test archive (tar) or folder: context/, conventions/, an optional
                       _review_targets.json and an optional case_manifest.json (multi-round);
  --exposure sealed    with --test-manifest (role B's seal manifest): the bundle must sit
                       outside the repository and progress prints counts only (B.8);
  --ledger, --forecast-minutes, --storage-forecast-usd
                       the IV.3 inputs: the instance candidates and the soft and hard caps
                       are set from the live price in the inventory and the per-run cap
                       formula, never typed in;
  --inputs-from        where runtime.candidate.lock and provider_inventory.json are read.
"""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import zipfile

from prepare_cloud_run import git, make_source, pins, validate_wheels
from cloud_run_common import credential_locations
from ordinary_final_run import (ARGV, MULTI_ROUND_ARGV, TOPOLOGY, CASE_MANIFEST, EXPOSED_NO_MANIFEST, sha, read,
                                write, require, cache_ref_bytes, validate_live_case_manifest, case_corpus_documents)
from prepare_ordinary_final_assets import build_assets
import loop_budget_guard as guard

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/fix/ordinary_final_cloud_run'
WHEELS = ROOT/'output/cloud_wheels/ordinary_final_cp312'
WORKLOAD_STOP_RESERVE_SECONDS = 900
TERMINATION_RESERVE_SECONDS = 180

# Named extras of the cloud source archive: paths outside the runtime prefixes that later
# stages add (S4f's baseline tools, S4c's adapters, which the baselines import). A directory
# ends in '/'. A listed path the bound commit does not hold fails the build in one line.
ARCHIVE_EXTRAS = ('benchmark/adapters/', 'benchmark/baselines/')
# Test material never travels inside the source archive: a test reaches the instance by
# the external bundle path only.
NEVER_IN_SOURCE_ARCHIVE = ('input/', 'benchmark/corpora/', 'benchmark/keys/', 'seals/', '_xfer/', 'external/',
                           'output/', 'docs/')
RUNTIME_PREFIXES = ('scripts/', 'config/', 'corpus_ingest/')
RUNTIME_FILES = ('requirements.txt', 'genesis.md', 'tools/run_local_demo.py', 'tools/score_corpus.py')


def named(name, path):
    return name == path or (path.endswith('/') and name.startswith(path))


def archive_names(names, extra=(), extras=None):
    """The bound commit's names that enter the source archive, named extras included."""
    extras = ARCHIVE_EXTRAS if extras is None else tuple(extras)
    for path in extras:
        require(not path.startswith(NEVER_IN_SOURCE_ARCHIVE),
                'Test material travels by the external bundle path, never in the source archive: ' + path)
        require(any(named(n, path) for n in names), 'Named archive extra absent from the bound commit: ' + path)
    return [n for n in names if (n.startswith(RUNTIME_PREFIXES) or n in RUNTIME_FILES or n in extra
            or any(named(n, p) for p in extras))
            and not (n.endswith('_checks.py') or n.startswith('scripts/verify_') or '/fixtures/' in n)]


def runtime_source(source, extra=()):
    """The ordinary runtime files at the bound commit, byte-identical to the working tree.

    `extra` names files outside the runtime prefixes that the runtime reads at
    execution time (the frozen evaluation protocols the decoding policy is read
    from); they are bound and hash-checked exactly like the source."""
    names=archive_names(git(ROOT,'ls-tree','-r','--name-only',source).decode().splitlines(), extra)
    require(all(n in names for n in extra), 'Runtime-read file absent from the bound commit')
    with tarfile.open(fileobj=io.BytesIO(git(ROOT,'archive','--format=tar',source,'--',*names))) as archive:
        files={member.name:archive.extractfile(member).read().replace(b'\r\n',b'\n')
               for member in archive.getmembers() if member.isfile()}
    for name,data in files.items():
        require((ROOT/name).read_bytes().replace(b'\r\n',b'\n')==data,'Execution source differs from bound commit: '+name)
    return files


def expected_members(models, wheels, wheelhouse):
    """The asset inventory build_assets would write for these models and wheels."""
    members = {}
    for model in models:
        prefix = 'hf_cache/hub/models--'+model['model_id'].replace('/','--')
        members[prefix+'/refs/main'] = model['cache_ref']
        for name, entry in model['files'].items():
            members[prefix+'/snapshots/'+model['revision']+'/'+name] = entry
    for entry in wheels.values():
        members['wheels/'+entry['filename']] = dict(sha256=entry['sha256'],bytes=(Path(wheelhouse)/entry['filename']).stat().st_size)
    return members


def bind_existing_assets(bundle, models, wheels, wheelhouse, target):
    """Bind a previously sealed asset archive instead of writing a second 13 GB copy.

    Admitted only when its recorded inventory equals, member for member and hash
    for hash, what build_assets would produce now, and its archive bytes still
    hash to the recorded value. The archive is hard-linked into the new bundle so
    every tool that reads assets_archive.filename beside the manifest still does;
    across drives, where a hard link cannot exist, it is copied and hashed again."""
    bundle = Path(bundle).resolve()
    previous = read(bundle/'execution_manifest.json')['assets_archive']
    archive = bundle/previous['filename']
    require(previous['members'] == expected_members(models, wheels, wheelhouse),
            'Reused asset archive inventory differs from the current models or wheels')
    require(archive.stat().st_size == previous['bytes'] and sha(archive) == previous['sha256'],
            'Reused asset archive hash mismatch')
    require(not Path(target).exists(), 'Refuse to replace an existing asset archive')
    # Resolve the provenance label BEFORE creating the link: a bundle outside the
    # repository would otherwise raise after the link exists, and the leftover
    # would make every later attempt refuse on an archive nothing wrote.
    try:
        origin = bundle.relative_to(ROOT).as_posix()
    except ValueError:
        origin = bundle.as_posix()
    try:
        os.link(archive, target)
        linked = True
    except OSError:
        shutil.copyfile(archive, target)
        linked = False
    require(Path(target).stat().st_size == previous['bytes'], 'Linked asset archive size mismatch')
    if not linked:
        require(sha(target) == previous['sha256'], 'Copied asset archive hash mismatch')
    return dict(previous, filename=Path(target).name, reused_from=origin)


def inst_finder_setting(files, value):
    """SHIMMER_INST_FINDER as the BOUND pipeline would read it (R11, open item 12).

    The ratification test is not copied: `_inst_finder_switch` is read from the bound
    pipeline source and evaluated against the bound constitution, so the seal refuses
    exactly what the run would refuse. Importing the pipeline module would load its whole
    runtime; reading the one function keeps sealing model-free."""
    tree = ast.parse(files['scripts/pipeline.py'].decode('utf-8-sig'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_inst_finder_switch')
    environ = {} if value is None else {'SHIMMER_INST_FINDER': value}
    scope = dict(os=SimpleNamespace(environ=environ), json=json, re=re, Path=Path)
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'bound_pipeline_inst_finder', 'exec'), scope)
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder)/'config').mkdir()
        (Path(folder)/'config/constitution.json').write_bytes(files['config/constitution.json'])
        return scope['_inst_finder_switch'](folder)


def seal_environment(files, value):
    """The runtime environment sealed into the manifest; an unratified `off` refuses here."""
    record = inst_finder_setting(files, value)
    require(not record['refusal'], 'Refuse to seal SHIMMER_INST_FINDER=off: no ratified amendment in the bound '
            'constitution names INST_FINDER and SHIMMER_INST_FINDER')
    return dict(SHIMMER_MODEL_MODE='final',SHIMMER_BACKEND_PROFILE='local',
        SHIMMER_INST_FINDER=record['setting'],
        CUBLAS_WORKSPACE_CONFIG=':4096:8',PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True',
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',
        HF_HUB_DISABLE_IMPLICIT_TOKEN='1',PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',
        TOKENIZERS_PARALLELISM='false')


def text_member(name):
    """True for a member whose line endings may be normalised: the plain-text and HTML
    extensions the pipeline's own extractor reads as text (scripts/text_extract.py). A PDF,
    a DOCX or anything else is binary and keeps its bytes: a CR LF pair inside a zip or a
    PDF stream is data, and converting it corrupts the file, which the extractor then
    returns as empty text and _load_corpus silently skips."""
    try:
        import text_extract
    except ImportError:
        sys.path.append(str(ROOT/'scripts'))
        import text_extract
    return Path(name).suffix.lower() in (*text_extract.PLAINTEXT_EXTENSIONS, *text_extract.HTML_EXTENSIONS)


def workload_members(path):
    """A test's members as {relative name: bytes}, from an archive or a folder: text members
    LF-normalised, binary members and the case manifest exactly as given."""
    path = Path(path)
    members = {}
    if path.is_dir():
        for item in sorted(path.rglob('*')):
            if item.is_file():
                members[item.relative_to(path).as_posix()] = item.read_bytes()
    else:
        with tarfile.open(path) as archive:
            for member in archive.getmembers():
                require(not (member.issym() or member.islnk()) and '..' not in member.name.split('/'),
                        'Unsafe test archive member')
                if member.isfile():
                    members[member.name.removeprefix('./')] = archive.extractfile(member).read()
    allowed = ('context/', 'conventions/')
    for name in members:
        require(name.startswith(allowed) or name in ('_review_targets.json', CASE_MANIFEST),
                'Test archive member outside context/, conventions/, the targets file and the case manifest')
    return {n: (d.replace(b'\r\n', b'\n') if n != CASE_MANIFEST and text_member(n) else d) for n, d in members.items()}


def default_workload():
    corpus = ROOT/'benchmark/corpora/clinical_reference'
    members = {name: (corpus/name).read_bytes().replace(b'\r\n', b'\n')
               for name in ('context/result_sheet.md', 'context/analyte_reference_ranges.md', 'conventions/lab_conventions.md')}
    members['_review_targets.json'] = (json.dumps(dict(source='operator', targets=['result_sheet.md'],
        grounding=['analyte_reference_ranges.md'], prior=[]), sort_keys=True)+'\n').encode()
    return 'clinical_reference', members


def budget_fields(provider, budget, now_epoch):
    """The IV.3 budget, set from the live price in the provider inventory: the ordered
    instance candidates, and the soft cap (the forecast) and hard cap (the per-run cap)."""
    require(isinstance(budget, dict), 'IV.3 budget inputs required: --ledger, --forecast-minutes, --storage-forecast-usd')
    reference = guard.a10_reference_rate(budget['ledgers'])
    candidates = guard.instance_candidates(provider['instance_types'], reference)
    rate = candidates[0]['max_hourly_rate']
    decision = guard.check(ledgers=budget['ledgers'], forecast_minutes=budget['forecast_minutes'], hourly_rate=rate,
                           storage_forecast_usd=budget['storage_forecast_usd'], now_epoch=now_epoch,
                           provider_names=[i.get('name') for i in provider['instances']],
                           reserve_minutes=WORKLOAD_STOP_RESERVE_SECONDS / 60, reaped=budget.get('reaped'))
    return dict(instance_candidates=candidates, region=guard.PREFERRED_REGION,
        max_hourly_rate=max(c['max_hourly_rate'] for c in candidates), a10_reference_rate=reference,
        forecast_minutes=budget['forecast_minutes'], forecast_usd=decision['forecast_usd'],
        soft_budget_usd=decision['forecast_usd'], hard_ceiling_usd=decision['cap_usd'], per_run_cap_usd=decision['cap_usd'],
        workload_stop_reserve_seconds=WORKLOAD_STOP_RESERVE_SECONDS, termination_reserve_seconds=TERMINATION_RESERVE_SECONDS)


def test_seal(exposure, test_manifest, test_archive, source):
    """The seal's test fields (11.10, B.3): role B's manifest hash, or 'exposed, no manifest'."""
    require(exposure in ('exposed', 'sealed'), 'Exposure is exposed or sealed')
    if exposure == 'exposed':
        require(test_manifest is None, 'An exposed run carries no test manifest')
        return dict(exposure='exposed', test_manifest_sha256=EXPOSED_NO_MANIFEST)
    require(test_manifest is not None and test_archive is not None and Path(test_archive).is_file(),
            'A sealed run needs the test archive and role B\'s seal manifest')
    value = read(test_manifest)
    require(value.get('archive_sha256') == sha(test_archive), 'Test archive differs from the seal manifest')
    require(value.get('code_commit') == source, 'Code commit differs from the seal manifest')
    return dict(exposure='sealed', test_manifest_sha256=sha(test_manifest), test_archive_sha256=sha(test_archive),
                code_commit=source, scorer_sha256=value.get('scorer_sha256'))


def prepare(output, source_commit='HEAD', reuse_assets=None, *, budget=None, workload=None, exposure='exposed',
            test_manifest=None, protected_test=False, inputs_from=None, now_epoch=None):
    global OUT
    original = OUT
    OUT = Path(output).resolve()
    sealed = exposure == 'sealed'
    if sealed:
        # The test never enters the builder's repository (11.2): a sealed bundle is built
        # outside it, and only counts are printed (B.8).
        require(not OUT.is_relative_to(ROOT.resolve()), 'A sealed bundle must be prepared outside the repository')
        require(workload is not None and Path(workload).is_file(), 'A sealed bundle is built from the test archive')
    require(not protected_test or sealed, 'Only a sealed bundle may set protected_test')
    require(not (OUT/'execution_manifest.json').exists(), 'Refuse to reseal an existing execution identity')
    OUT.mkdir(parents=True,exist_ok=True)
    source_inputs = Path(inputs_from).resolve() if inputs_from else original
    for name in ('runtime.candidate.lock','provider_inventory.json'):
        (OUT/name).write_bytes((source_inputs/name).read_bytes())
    source = git(ROOT, 'rev-parse', source_commit).decode().strip()
    seal_fields = test_seal(exposure, test_manifest, workload if sealed else None, source)
    sys.path.insert(0, str(ROOT/'scripts'))
    import decoding_policy
    # The decoding policy is read at run time from the frozen evaluation protocols,
    # so they travel with the runtime and are hash-bound like every other file.
    protocols = sorted(e['protocol'] for e in decoding_policy.declaration(ROOT)[0]['backends'].values()
                       if e.get('status') == 'restored')
    files = runtime_source(source, extra=protocols)
    # The declaration and the module that reads it are runtime source: the remote
    # exact-tree check would accept an archive without them and the run would then
    # refuse at admission. Bundling from git means an uncommitted file is silently
    # absent, so require them present by name rather than trusting the prefixes.
    for name in (decoding_policy.DECLARATION, 'scripts/decoding_policy.py'):
        require(name in files, 'Decoding policy source absent from the bound commit: '+name)
    # The validated PROCESSOR prompt declaration (EXTRACTION-A) is read at the first
    # bounded partition, long after admission; an archive without it would fail the
    # run forty minutes in. Require it by name for the same reason as the policy.
    require('config/compact_extraction_prompt.json' in files,
            'Compact extraction prompt declaration absent from the bound commit')
    decoding = {b: dict(status=p['status'],source=p['source'],sha256=p['sha256'],kwargs=p['kwargs'])
                for b, p in decoding_policy.summary(ROOT).items()}
    environment = seal_environment(files, os.environ.get('SHIMMER_INST_FINDER'))
    # Only the explicitly selected input files may enter this bundle; named extras stay.
    files = {n:d for n,d in files.items() if not n.startswith('benchmark/') or any(named(n, p) for p in ARCHIVE_EXTRAS)}
    if workload is None:
        workload_name, members = default_workload()
    else:
        workload_name, members = ('sealed_test' if sealed else Path(workload).stem), workload_members(workload)
    require('_review_targets.json' in members, 'The workload names its review targets (_review_targets.json)')
    case = members.pop(CASE_MANIFEST, None)
    workload_hashes = {}
    for name, data in members.items():
        if name == '_review_targets.json':
            files['input/context/_review_targets.json'] = data
            continue
        files['input/'+name] = data
        workload_hashes[name] = hashlib.sha256(data).hexdigest()
    multi_round = case is not None
    if multi_round:
        # The documents bind_sources will see on the instance, by the bound pipeline's own rules.
        documents = case_corpus_documents({n[len('context/'):]: d for n, d in members.items() if n.startswith('context/')},
                                          files['scripts/pipeline.py'])
        validate_live_case_manifest(json.loads(case.decode('utf-8')), documents)
        (OUT/CASE_MANIFEST).write_bytes(case)
    # Numerical/prompt helpers only; no training controller or datasets.
    for name in ('auditor_linear_core.py', 'auditor_classifier_lora_stable.py'):
        files['tools/'+name] = (ROOT/'tools'/name).read_bytes().replace(b'\r\n',b'\n')
    import final_models
    spec = read(ROOT/'config/final_models.json')
    for role in ('producer','auditor'):
        _, paths = final_models.verify(role)
        for key, path in paths.items():
            files[spec[role]['files'][key]['path']] = path.read_bytes()
    for name, data in files.items():
        if not name.endswith(('.safetensors','.npy')):
            hits = credential_locations(data, name)
            require(not hits, 'Possible credential in '+('a test file' if sealed and name.startswith('input/') else name)
                    +'; stop without printing content')
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
    support_names = ['topology.json','ordinary_final_run.py','ordinary_final_summary.py','cloud_run_observer.py','install.lock']
    if multi_round:
        support_names.append(CASE_MANIFEST)
    support = {n:sha(OUT/n) for n in support_names}
    provider = read(OUT/'provider_inventory.json')
    require(provider['instances']==[], 'Provider inventory not empty')
    import time
    budget_values = budget_fields(provider, budget, time.time() if now_epoch is None else now_epoch)
    if reuse_assets:
        assets = bind_existing_assets(reuse_assets,models,wheels,WHEELS,OUT/'assets.tar')
    else:
        assets = build_assets(OUT/'assets.tar',models,wheels,cache,WHEELS)
    workload_record = dict(name=workload_name,review_targets=None if sealed else 1,
                           files=({} if sealed else workload_hashes),file_count=len(workload_hashes),
                           answer_key_transferred=False)
    restrictions = ['no second instance','no automatic full-run retry','no tuning',
                    'no protected data' if not protected_test else 'protected test only as sealed by role B',
                    'multi-round only as the sealed case manifest declares' if multi_round else 'no multi-round',
                    'no benchmark workload substitution']
    manifest = dict(schema_version=1,source_commit=source,source_archive_sha256=sha(OUT/'project.tar.gz'),
        classification='PREPARED_NOT_AUTHORIZED',max_runs=1,model_mode='final',multi_round=multi_round,
        protected_test=protected_test,workload=workload_record,
        decoding_policy=decoding,
        project_files={n:hashlib.sha256(d).hexdigest() for n,d in sorted(files.items())},
        # The CONTROLLER itself is bound here, with the wrapper that launches it and
        # the provider adapter it launches through. Before this the seal pinned the
        # runtime the controller carries but not the controller, so a bundle sealed
        # with one controller could be launched by another and only the launch
        # receipt would say so, after the instance existed. execute() verifies every
        # name in this map before its first provider call, so a changed controller
        # now refuses before anything is created.
        local_control_hashes={n:sha(ROOT/n) for n in ('tools/ordinary_final_watchdog.py',
            'tools/cloud_run_watchdog.py','tools/cloud_run_common.py','tools/ordinary_final_run.py',
            'tools/ordinary_final_cloud.py','tools/ordinary_final_bound_cloud.py',
            'tools/lambda_experiment_provider.py',
            # What the controller imports to decide and record a launch (S2): the budget
            # guard, the reaper's ledger reading it reuses, the keep-awake helper and the
            # termination and state functions it takes from the general controller.
            'tools/loop_budget_guard.py','tools/loop/instance_reaper.py','tools/loop/keep_awake.py',
            'tools/run_remote_experiment.py')},
        support_files=support,models=models,assets_archive=assets,
        preparation_source_hashes={n:sha(ROOT/n) for n in
            ('tools/prepare_ordinary_final_run.py','tools/prepare_ordinary_final_assets.py')},
        packages=locked,wheels=wheels,runtime_file_hashes=runtime_files,
        argv=MULTI_ROUND_ARGV if multi_round else ARGV,topology=TOPOLOGY,provider='Lambda',
        instance=next(x for x in provider['instance_types'] if x['metadata']['type']==guard.PREFERRED_TYPE),
        provider_observed_at=provider['observed_at'],image=provider['images'][0],
        **budget_values,
        # SHIMMER_INST_FINDER is written explicitly so the instance runs the setting the
        # operator prepared with (default on), never an ambient value. `off` is sealed
        # only under a ratified amendment in the bound constitution (seal_environment).
        environment=environment,
        restrictions=restrictions,
        known_auditor_limitations=spec['auditor']['limitations'])
    if multi_round:
        manifest['case_manifest_sha256'] = support[CASE_MANIFEST]
    if sealed:
        manifest['test_archive_sha256'] = seal_fields['test_archive_sha256']
    write(OUT/'execution_manifest.json', manifest)
    write(OUT/'seal.json',dict(execution_manifest_sha256=sha(OUT/'execution_manifest.json'),
        source_commit=source,operator_authorized=False,classification='PREPARED_NOT_AUTHORIZED',**seal_fields))
    write(OUT/'transfer_plan.json',dict(
        project_archive=dict(path='project.tar.gz',sha256=sha(OUT/'project.tar.gz'),bytes=(OUT/'project.tar.gz').stat().st_size),
        model_bytes=sum(e['bytes'] for m in models for e in m['files'].values()),
        wheel_bytes=sum((WHEELS/e['filename']).stat().st_size for e in wheels.values()),
        model_cache_local=str(cache),wheelhouse_local=str(WHEELS),
        local_paths_not_transferred=True,credentials_transferred=False,
        assets_archive={k:v for k,v in assets.items() if k!='members'},
        model_delivery='Use sealed assets.tar; refs/main are exactly 40 ASCII revision bytes, no newline',
        excluded=['all benchmark answer keys','all other corpora','TRAIN/DEV/HOLDOUT datasets',
                  'multi-round data other than the sealed case manifest and its documents' if multi_round
                  else 'multi-round data','operator input','durable state','credentials','Git history']))
    if sealed:
        print('Prepared sealed bundle: %d project files, %d support files; no authorization, model load or provisioning'
              % (len(files), len(support)))
    else:
        print('Prepared sealed ordinary final run; no authorization, model load or provisioning')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--source-commit',default='HEAD',
                        help='the commit the runtime source is bound to; the working tree must match it')
    parser.add_argument('--reuse-assets',type=Path,default=None,
                        help='a sealed bundle whose verified asset archive is bound again instead of rebuilt')
    parser.add_argument('--inputs-from',type=Path,default=None,
                        help='folder holding runtime.candidate.lock and provider_inventory.json (default: docs/fix bundle)')
    parser.add_argument('--workload',type=Path,default=None,help='test archive or folder (default: the clinical workload)')
    parser.add_argument('--exposure',choices=('exposed','sealed'),default='exposed')
    parser.add_argument('--test-manifest',type=Path,default=None,help="role B's seal manifest (sealed runs)")
    parser.add_argument('--protected-test',action='store_true',help='sealed bundles prepared by role B only')
    parser.add_argument('--ledger',type=Path,action='append',required=True,help='loop ledger(s) the IV.3 cap reads')
    parser.add_argument('--forecast-minutes',type=float,required=True,help='measured basis in minutes (docs/loop/BUDGET.md)')
    parser.add_argument('--storage-forecast-usd',type=float,required=True)
    args = parser.parse_args()
    prepare(args.output_dir, args.source_commit, args.reuse_assets,
            budget=dict(ledgers=args.ledger, forecast_minutes=args.forecast_minutes,
                        storage_forecast_usd=args.storage_forecast_usd),
            workload=args.workload, exposure=args.exposure, test_manifest=args.test_manifest,
            protected_test=args.protected_test, inputs_from=args.inputs_from)
