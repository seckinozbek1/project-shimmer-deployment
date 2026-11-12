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
  --inputs-from        where runtime.candidate.lock and provider_inventory.json are read;
  --arm                B3 (default), B1 (with --items and --b1-checkpoints) or L (exposed only,
                       with --launcher-question): the launcher menu once, a review then a draft,
                       answered only from the sealed prompt map (D-S13 item 6d).
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

from prepare_cloud_run import git, make_source, pins, validate_wheels, gate_check_file
from cloud_run_common import credential_locations
from ordinary_final_run import (ARGV, MULTI_ROUND_ARGV, TOPOLOGY, CASE_MANIFEST, EXPOSED_NO_MANIFEST, sha, read,
                                write, require, cache_ref_bytes, validate_live_case_manifest, case_corpus_documents)
from prepare_ordinary_final_assets import build_assets
import ordinary_final_run as runner
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
            and not gate_check_file(n)]


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


def producer_attention_setting(files, attention=None, decision=None, prefill_chunk=None, prefill_decision=None):
    """SHIMMER_PRODUCER_ATTENTION and SHIMMER_PRODUCER_PREFILL_CHUNK (and their decisions) as
    the BOUND final_models reads them (D-058, D-061, D-063): sdpa pinned to the memory-efficient
    backend and one-shot prefill, both under D-063, when the operator names none; eager or
    chunked prefill only with the recorded decision (D-NNN) that asks for it, a measurement
    run. The rules are not
    copied: `producer_attention` and `producer_prefill` are read from the bound
    scripts/final_models.py and evaluated, so the seal refuses exactly what the instance would
    refuse. Both settings are written explicitly so the instance never runs an ambient value;
    the runner replaces every SHIMMER_ variable with the sealed ones."""
    require('scripts/final_models.py' in files, 'Frozen model source absent from the bound commit: scripts/final_models.py')
    source = files['scripts/final_models.py'].decode('utf-8-sig')
    tree = ast.parse(source)
    names = {'producer_attention', 'attention_setting', 'producer_prefill', 'prefill_setting', 'require',
             'PRODUCER_ATTENTION_ENV', 'PRODUCER_ATTENTION_DECISION_ENV', 'PRODUCER_ATTENTION_DEFAULT',
             'ATTENTION_DECISION_DEFAULT', 'EAGER', 'SDPA', 'PRODUCER_ATTENTIONS', 'SDPA_BACKEND', 'DECISION_ID',
             'PRODUCER_PREFILL_ENV', 'PRODUCER_PREFILL_DECISION_ENV', 'PREFILL_CHUNK_DEFAULT', 'PREFILL_DEFAULT',
             'PREFILL_DECISION_DEFAULT', 'E_CHUNK_TOKENS', 'ONE_SHOT', 'CHUNKED'}
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in names) or
            (isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and t.id in names for t in n.targets))]
    defined = {n.name for n in keep if isinstance(n, ast.FunctionDef)}
    require('producer_attention' in defined, 'The bound final_models has no producer attention setting (it predates D-058)')
    require('producer_prefill' in defined, 'The bound final_models has no producer prefill setting (it predates D-061)')
    scope = dict(os=os, re=re)
    exec(compile(ast.Module(body=keep, type_ignores=[]), 'bound_final_models_attention', 'exec'), scope)
    environ = {}
    for key, value in (('PRODUCER_ATTENTION_ENV', attention), ('PRODUCER_ATTENTION_DECISION_ENV', decision),
                       ('PRODUCER_PREFILL_ENV', prefill_chunk), ('PRODUCER_PREFILL_DECISION_ENV', prefill_decision)):
        if value is not None:
            environ[scope[key]] = str(value)
    try:
        record = scope['producer_attention'](environ)
    except RuntimeError as exc:
        raise RuntimeError('Refuse to seal the producer attention: ' + str(exc)) from None
    try:
        prefill = scope['producer_prefill'](environ)
    except RuntimeError as exc:
        raise RuntimeError('Refuse to seal the producer prefill: ' + str(exc)) from None
    sealed = {scope['PRODUCER_ATTENTION_ENV']: record['attention_implementation']}
    if record['attention_decision'] is not None:
        sealed[scope['PRODUCER_ATTENTION_DECISION_ENV']] = record['attention_decision']
    sealed[scope['PRODUCER_PREFILL_ENV']] = (scope['ONE_SHOT'] if prefill['prefill'] == scope['ONE_SHOT']
                                             else str(prefill['prefill_chunk_tokens']))
    sealed[scope['PRODUCER_PREFILL_DECISION_ENV']] = prefill['prefill_decision']
    return sealed


def seal_environment(files, value, attention=None, attention_decision=None, prefill_chunk=None, prefill_decision=None):
    """The runtime environment sealed into the manifest; an unratified `off` refuses here, and
    so does a producer attention or prefill the bound final_models would refuse (D-058, D-061)."""
    record = inst_finder_setting(files, value)
    require(not record['refusal'], 'Refuse to seal SHIMMER_INST_FINDER=off: no ratified amendment in the bound '
            'constitution names INST_FINDER and SHIMMER_INST_FINDER')
    return dict(SHIMMER_MODEL_MODE='final',SHIMMER_BACKEND_PROFILE='local',
        SHIMMER_INST_FINDER=record['setting'],
        **producer_attention_setting(files, attention, attention_decision, prefill_chunk, prefill_decision),
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


def gate_check_numbers(source):
    """The check numbers of the bound gate's CHECKS list, read from its titles."""
    text = git(ROOT, 'show', source+':scripts/verify_session1.py').decode('utf-8')
    numbers = [int(n) for n in re.findall(r'^\s*\("(\d+) ', text[text.index('\nCHECKS'):], re.M)]
    require(numbers and len(set(numbers)) == len(numbers), 'The bound gate lists no unique check numbers')
    return numbers


def gate_fields(gate, source, locked):
    """The sealed gate block (D-S75): the form, the checks, the known-red list, the bound gate's
    check numbers, the digest of the tracked tree at the bound commit, and the gate's own pins
    (requirements.txt at that commit), each of which must be in the sealed runtime lock."""
    require(isinstance(gate, dict) and gate.get('form') in runner.GATE_FORMS, 'The gate form is full or side')
    numbers = gate_check_numbers(source)
    checks = gate.get('checks', 'all')
    for name, value in (('checks', checks), ('known_red', gate.get('known_red', []))):
        if value != 'all':
            require(set(value) <= set(numbers), 'Not a check of the bound gate in --%s: %s'
                    % (name.replace('_', '-'), ', '.join(str(n) for n in sorted(set(value) - set(numbers)))))
    requirements = OUT/'gate_requirements.txt'
    requirements.write_bytes(git(ROOT, 'show', source+':requirements.txt'))
    needed = pins(requirements)
    requirements.unlink()
    # A pin holds against the lock with its local label dropped (2.5.1+cu121 holds 2.5.1), one
    # rule with the runner's admission (ordinary_final_run.pin_held).
    missing = sorted('%s==%s' % (n, v) for n, v in needed.items() if not runner.pin_held(locked.get(n), v))
    require(not missing, "The gate's pins are not in the sealed runtime lock: " + ', '.join(missing))
    import subprocess
    archive = OUT/runner.GATE_SOURCE
    done = subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=tar', '-o', str(archive), source],
                          capture_output=True, **({'creationflags': 0x08000000} if os.name == 'nt' else {}))
    require(done.returncode == 0 and archive.is_file(), 'The bound commit could not be archived for the gate')
    block = dict(form=gate['form'], checks=sorted(checks) if checks != 'all' else 'all',
                 known_red=sorted(gate.get('known_red', [])), check_numbers=numbers, source_sha256=sha(archive),
                 requirements=needed)
    return block


IMAGE_SPEC = 'image_spec.json'
IMAGE_TOOL = 'image_layers.py'


def image_layer_fields(assets, install_lock_sha256, machine_image, layers):
    """D-S108 form B: the layer spec (support file IMAGE_SPEC) and the instance's tool (IMAGE_TOOL),
    and the manifest's `layers` block naming both. Every model and wheels layer lists exactly the
    sealed asset members under it, so the instance checks the same digests the archive seals. The env
    layer is sealed only from a build record whose key is this bundle's env key; without one it is
    UNSEALED: never used, though a launch may build it and bring its record back."""
    import image_layers
    env_manifest = read(layers['env_manifest']) if layers.get('env_manifest') else None
    python_version = read(ROOT/'tools/cloud_run/runtime.json')['python']
    layer_spec = image_layers.spec(assets['members'], install_lock_sha256, machine_image['id'], python_version,
                                   env_manifest, layers.get('measure', False))
    spec_bytes = (json.dumps(layer_spec, indent=2, sort_keys=True) + '\n').encode('utf8')
    tool = (ROOT/'tools/image_layers.py').read_bytes().replace(b'\r\n', b'\n')
    block = dict(spec=IMAGE_SPEC, spec_sha256=hashlib.sha256(spec_bytes).hexdigest(), tool=IMAGE_TOOL,
                 tool_sha256=hashlib.sha256(tool).hexdigest(), python=python_version, measure=layer_spec['measure'],
                 env_sealed=env_manifest is not None,
                 keys={l['name']: l['key'] for l in layer_spec['layers']})
    return block, {IMAGE_SPEC: spec_bytes, IMAGE_TOOL: tool}


SINGLE_GPU_ONLY = ('Only single-GPU types are rentable until the runner\'s hardware projection changes '
                   '(D-382 item 3); --gpus is 1')


# D-S95 item 5, D-401 item 1 (c): the arms whose figures are compared with each other.
COMPARED_ARMS = ('B3', 'B1')
COMPARISON_REQUIRED = ('A B3 or B1 bundle names the comparison its figures belong to (--comparison <name>), or '
                       'states that they are compared with no other arm (--uncompared)')


def comparison_declared(arm, budget, reference_run):
    """D-401 item 1 (c): a B3 or B1 bundle names its comparison or states --uncompared, one of the
    two; a reference-set run, and every other arm, needs neither."""
    if arm in COMPARED_ARMS and reference_run is None:
        require(bool(budget.get('comparison')) != bool(budget.get('uncompared')), COMPARISON_REQUIRED)
    return True


def comparison_type(name, candidates, registry=None):
    """D-S95 item 5, D-401 item 1 (c, d): the one candidate a bundle of comparison `name` seals: the
    type the comparison's first launch recorded (read only; the record is written at launch, after
    the guard's decision and under the ledger lock, `loop_budget_guard.claim_comparison`), or with
    none recorded the first candidate. A recorded type that is not offered now refuses."""
    import re as _re
    require(isinstance(name, str) and _re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', name) is not None,
            'A comparison name is lower case letters, digits and hyphens')
    known = guard.comparison_recorded(name, registry)
    machine = known or candidates[0]['type']
    chosen = [c for c in candidates if c['type'] == machine][:1]
    require(chosen, 'Comparison %s runs on %s, which is not among the offered candidates now' % (name, machine))
    return chosen


def budget_fields(provider, budget, now_epoch, workload_files=None, arm='B3'):
    """The IV.3 budget, set from the live price in the provider inventory: the ordered
    instance candidates, and the soft cap (the forecast) and hard cap (the per-run cap).
    D-S95, D-S96 item 2, D-382 item 1: a fastest or listed order leaves the A10 only for a type
    whose reference-set pair is measured (`gpu_speed_order.json` `measured`, keyed by machine
    type, its provenance checked here by `factor_record.check_measured`), unless this bundle is a
    reference-set run (its workload is a declared reference item); until a pair is measured every
    launch stays on the A10. A listed type with no measured entry is refused. The speed order file
    is read now and sealed into the candidates; it is not pinned. D-382 item 2, D-401 item 1: a B3
    or B1 bundle names its comparison (`--comparison`, sealing one candidate type, the comparison's)
    or states `--uncompared`; a reference-set run needs neither."""
    require(isinstance(budget, dict), 'IV.3 budget inputs required: --ledger, --forecast-minutes, --storage-forecast-usd')
    gpus = budget.get('gpus', 1)
    require(gpus == 1, SINGLE_GPU_ONLY)
    import factor_record
    reference = guard.a10_reference_rate(budget['ledgers'])
    spec = read(guard.GPU_SPEED_ORDER)
    factor_record.check_measured(spec)
    # D-S78 item 2: a declared order of faster types, sealed from the inventory as given.
    declared = budget.get('instance_types')
    # D-S79: fastest first by default, from the declared GPU speed order; the A10-first rule only
    # when asked for (`--type-rule a10_first`).
    rule = 'listed' if declared else budget.get('type_rule') or 'fastest'
    require(rule in ('listed', 'fastest', 'a10_first'), 'The type rule is fastest or a10_first')
    reference_run = factor_record.reference_workload(workload_files) if workload_files else None
    if rule == 'listed' and reference_run is None:
        unmeasured = [t for t in declared if t != guard.PREFERRED_TYPE and t not in (spec.get('measured') or {})]
        require(not unmeasured, 'No reference-set pair is measured for: %s; run the D-S82 reference set on it beside '
                'the A10 first' % ', '.join(unmeasured))
    candidates = (guard.declared_candidates(provider['instance_types'], declared, gpus) if rule == 'listed'
                  else guard.fastest_candidates(provider['instance_types'], guard.speed_order(spec), gpus)
                  if rule == 'fastest' else guard.instance_candidates(provider['instance_types'], reference))
    if rule != 'a10_first':
        candidates = guard.measured_tiers(candidates, spec, reference_run=reference_run is not None)
    comparison = None
    comparison_declared(arm, budget, reference_run)
    if budget.get('comparison'):
        candidates = comparison_type(budget['comparison'], candidates)
        comparison = dict(name=budget['comparison'], type=candidates[0]['type'])
    tier = dict(reference_item=reference_run['item'] if reference_run else None,
                measured=sorted(spec.get('measured') or {}))
    rate = candidates[0]['max_hourly_rate']
    decision = guard.check(ledgers=budget['ledgers'], forecast_minutes=budget['forecast_minutes'], hourly_rate=rate,
                           storage_forecast_usd=budget['storage_forecast_usd'], now_epoch=now_epoch,
                           provider_names=guard.loop_inventory(provider['instances']),
                           reserve_minutes=WORKLOAD_STOP_RESERVE_SECONDS / 60, reaped=budget.get('reaped'))
    return dict(instance_candidates=candidates, type_rule='a10_first' if rule == 'a10_first' else 'declared',
        type_order=rule, tier=tier, gpus=gpus, comparison=comparison, uncompared=bool(budget.get('uncompared')),
        region=guard.PREFERRED_REGION,
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


def replay_declaration(data):
    """The sealed replay declaration (D-061 item 4) of a replay_prompts.json's bytes, written by
    benchmark/baselines/replay_prompts.py extract: its digest and prompt count, after the
    tool's own reader has checked every prompt against its SHA-256."""
    sys.path.insert(0, str(ROOT/'benchmark/baselines'))
    import replay_prompts
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/'replay_prompts.json'
        path.write_bytes(data)
        prompts = replay_prompts.load_prompts(path)
    return dict(prompts_sha256=hashlib.sha256(data).hexdigest(), prompt_count=len(prompts))


def b1_fields(items, targets, checkpoints, replay=None):
    """The sealed B1 declaration (S5 R2): the checkpoints, the items of the bundle's ONE
    document (its target's file stem, the id bare_model.py reads it under), and the items.json
    digest. `items` is the bytes of the adapter's items.json, `targets` the workload's
    _review_targets.json bytes, `checkpoints` the passes [{name, checkpoint?, args}] (a pass
    without `checkpoint` loads the one its name names; a pass {name, replay: true, args} runs
    replay_prompts.py on the sealed prompts, D-061 item 4), `replay` the replay declaration
    (replay_declaration) or None. Nothing of an item but its id."""
    targets = json.loads(targets.decode('utf-8')).get('targets') or []
    require(len(targets) == 1, 'A B1 bundle names exactly one document under review')
    document = Path(targets[0]).stem
    rows = json.loads(items.decode('utf-8'))
    rows = rows.get('items') if isinstance(rows, dict) else rows
    require(isinstance(rows, list), 'items.json holds no item table')
    ids = sorted(str(r['item_id']) for r in rows if isinstance(r, dict) and str(r.get('document_id')) == document
                 and r.get('item_id'))
    require(ids, 'items.json holds no item for the document under review')
    value = dict(checkpoints=checkpoints, item_ids=ids, items_sha256=hashlib.sha256(items).hexdigest())
    if replay is not None:
        value['replay'] = replay
    # The runner's own validation, so the seal refuses exactly what the instance would.
    runner_b1 = dict(b1=value)
    from ordinary_final_run import b1_checkpoints, b1_item_ids
    b1_checkpoints(runner_b1)
    b1_item_ids(runner_b1)
    return value


# Arm L (D-S13 item 6d): the prompts the launcher menu, the intake wizard and the pipeline print
# on a review then a draft, each with its answers in the order it is asked. Every text is checked
# word for word against the bound sources (runner.launcher_prompt_error) before the seal is
# written. The two escalation prompts and the preflight's continue question may never be asked;
# an escalation is deferred, since no operator is present.
LAUNCHER_PREFLIGHT = 'Preflight reported issues above. Continue to the menu anyway? [y/N]: '
LAUNCHER_DEFERRAL = 'No operator is present in a sealed launcher session; deferred.'


def launcher_prompts(question, targets_answer, prior_answer):
    """The sealed prompt map: (id, text, answers, optional, repeat_last) in the order the session
    first meets each. `prior_answer` is None when no document is grounding (the wizard then
    never asks for an earlier version)."""
    rows = [
        ('backend', 'Choose [L/C, Enter for Local]: ', ['L'], False, False),
        ('preflight_continue', LAUNCHER_PREFLIGHT, ['y'], True, False),
        ('menu', 'Choose an option [1-5, Q]: ', ['1', '1', 'Q'], False, False),
        ('task', 'What would you like to do? [R] Review existing documents  [D] Draft a memo from a question  [R/D]: ',
         ['R', 'D'], False, False),
        ('folder', 'Enter the folder containing your documents: ', [runner.LAUNCHER_WORKLOAD_TOKEN], False, False),
        ('cutoff', 'Change the cutoff? Enter a new date (YYYY-MM-DD) or press Enter to keep: ', [''], False, False),
        ('privacy', 'Choose [1/2; Enter cancels]: ', ['1', '1'], False, False),
        ('parallel', 'How many documents to review in parallel? (default 4, higher is faster but uses more API quota) '
         '[Enter for default]: ', [''], False, False),
        ('max_docs', 'How many documents to review at most? [Enter for all]: ', [''], False, False),
        ('proceed', 'Proceed? [y/N]: ', ['y', 'y'], False, False),
        ('targets', "Enter the numbers to review (comma-separated), 'all', or Enter to let the date cutoff decide: ",
         [targets_answer], False, False),
        ('draft_question', 'Enter your question or brief for the memo: ', [question], False, False),
        ('layer_override', '--sensitivity-layer-inactive-override: declare THIS run NON-SENSITIVE and proceed with the '
         'full sensitivity layer inactive? (yes/no): ', ['y', 'y'], False, False),
        ('redaction_override', '--no-redaction-override: declare THIS run NON-SENSITIVE and run with NO redaction? '
         '(yes/no): ', ['y', 'y'], False, False),
        ('proceed_calls', 'Proceed with live API calls? (yes/no): ', ['y', 'y'], False, False),
        ('escalation_decision', 'Decision (APPROVE / DENY / DEFER): ', ['DEFER'], True, True),
        ('escalation_rationale', 'Rationale: ', [LAUNCHER_DEFERRAL], True, True),
    ]
    if prior_answer is not None:
        rows.insert(11, ('prior', 'Is one of these an EARLIER VERSION of a document under review? Enter its number, '
                         'or Enter for none: ', [prior_answer], False, False))
    return [dict(id=i, prompt=p, answers=a, optional=o, repeat_last=r) for i, p, a, o, r in rows]


def launcher_sensitivity_error(conventions):
    """Why arm L's sealed answers may not declare this workload non-sensitive, or None. The map
    answers yes to both NON-SENSITIVE overrides and chooses Normal mode (no redaction) with no
    operator present, so the workload's conventions ({file name: bytes}, as the wizard places
    them in input/conventions/) are compiled by the pipeline's own parser and redaction compiler:
    an operator redaction or confidentiality rule in force, one that failed to compile, or a
    redaction-intent decision the ensemble could not make refuses the seal."""
    import convention_parser
    from sensitivity_layer.rules import redaction_rules
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder)/'input'/'conventions'
        target.mkdir(parents=True)
        for name, data in conventions.items():
            (target/name).write_bytes(data)
        report = redaction_rules(convention_parser.parse_conventions(Path(folder)).as_dict())
    if report['operator_in_force']:
        return 'The launcher workload carries an operator redaction or confidentiality rule (%s); arm L declares ' \
               'every run non-sensitive and redacts nothing' % ', '.join(r['id'] for r in report['operator_rules'])
    if report['warnings']:
        return 'The launcher workload carries a redaction-intent convention that does not compile (%s)' % ', '.join(
            w['id'] for w in report['warnings'])
    undecided = [v.get('id') for v in report.get('semantic_votes', []) if not v.get('available')]
    if undecided:
        return 'The ensemble could not decide whether the launcher workload\'s conventions are redaction rules (%s)' \
               % ', '.join(map(str, undecided))
    return None


def tracked_blob_ids(listing):
    """The blob ids in a `git ls-tree -r -z` listing (bytes)."""
    ids = set()
    for entry in listing.decode('utf-8', 'replace').split('\0'):
        meta = entry.partition('\t')[0].split()
        if len(meta) == 3 and meta[1] == 'blob':
            ids.add(meta[2])
    return ids


def repository_material(source):
    """The blob ids of every file tracked at the bound commit `source`."""
    return tracked_blob_ids(git(ROOT, 'ls-tree', '-r', '-z', '--full-tree', source))


def blob_id(data, length=40):
    """Git's object id of `data` as a blob (SHA-1, or SHA-256 in a repository whose ids have 64 digits)."""
    digest = hashlib.sha256 if length == 64 else hashlib.sha1
    return digest(b'blob %d\0' % len(data) + data).hexdigest()


def launcher_material_error(members, material):
    """Why this workload may not be sealed for arm L, or None. Arm L seals a run that redacts
    nothing, so D-159 allows it only on development material already in the repository: every
    workload file (the targets file, which names files and holds no material, aside) must be,
    byte for byte as staged, a file tracked at the bound commit (`material`, its blob ids).
    Public material not in the repository is committed first (benchmark/corpora/), then sealed
    (issue #135, D-184)."""
    length = len(next(iter(material), '0' * 40))
    outside = sorted(n for n, d in members.items() if n != '_review_targets.json' and blob_id(d, length) not in material)
    if outside:
        return ('Arm L seals only development material already in the repository (D-159); not a file tracked at '
                'the bound commit: ' + ', '.join(outside))
    return None


def launcher_fields(members, question, files):
    """The arm L workload and its sealed launcher block. The menu's wizard reads ONE flat folder,
    so the workload's context/ and conventions/ files go into launcher_input/ under their own
    names; each must be classified by the wizard's own classify() as it was staged (a context
    file a DOCUMENT, a conventions file the review rules). The review targets become the
    numbers the wizard lists them under (sorted names, as its scan lists them on Linux) and the
    declared earlier version its number among the grounding documents. The question must not
    read as a meta-level change (the pipeline would then ask a question the map does not hold).
    Returns ({project path: bytes}, launcher block)."""
    require(isinstance(question, str) and question.strip() == question and question and '\n' not in question
            and len(question) <= runner.LAUNCHER_QUESTION_LIMIT,
            'Arm L needs --launcher-question: one line of at most %d characters' % runner.LAUNCHER_QUESTION_LIMIT)
    import constitution_guard
    require(not constitution_guard.scan_for_meta_signature(question, project_root=ROOT),
            'The draft question reads like a meta-level change; the pipeline would ask a question the map does not hold')
    import intake_wizard
    targets_file = json.loads(members['_review_targets.json'].decode('utf-8'))
    flat, kinds = {}, {}
    with tempfile.TemporaryDirectory() as folder:
        for name, data in members.items():
            if name == '_review_targets.json':
                continue
            top, _, base = name.partition('/')
            require(top in ('context', 'conventions') and base and '/' not in base,
                    'The launcher wizard reads one flat folder: no file below context/ or conventions/')
            require(base not in flat, 'Two workload files share one name; the wizard reads one flat folder')
            (Path(folder)/base).write_bytes(data)
            kind = intake_wizard.classify(Path(folder)/base)[0]
            require(kind == ('DOCUMENT' if top == 'context' else 'CONVENTIONS'),
                    'The wizard would not place ' + name + ' where the workload staged it')
            flat[base], kinds[base] = data, kind
    documents = sorted(n for n, k in kinds.items() if k == 'DOCUMENT')
    require(any(k == 'CONVENTIONS' for k in kinds.values()), 'The launcher workload carries no conventions')
    sensitivity = launcher_sensitivity_error({n: flat[n] for n, k in kinds.items() if k == 'CONVENTIONS'})
    require(sensitivity is None, sensitivity or '')
    targets = list(targets_file.get('targets') or [])
    require(targets and all(t in documents for t in targets), 'The review targets are not documents of the launcher workload')
    grounding = [d for d in documents if d not in targets]
    prior = list(targets_file.get('prior') or [])
    require(all(p in grounding for p in prior) and len(prior) <= 1, 'The earlier version is not one grounding document')
    prior_answer = (str(grounding.index(prior[0]) + 1) if prior else '') if grounding else None
    block = dict(script=runner.LAUNCHER_SCRIPT, workload=runner.LAUNCHER_WORKLOAD, question=question,
                 prompts=launcher_prompts(question, ','.join(str(documents.index(t) + 1) for t in targets), prior_answer),
                 child_environment=dict(runner.LAUNCHER_CHILD_ENVIRONMENT))
    error = runner.launcher_prompt_error(block['prompts'], {n: files[n].decode('utf-8-sig') for n in runner.LAUNCHER_PROMPT_SOURCES})
    require(error is None, error or '')
    return {runner.LAUNCHER_WORKLOAD + '/' + n: d for n, d in flat.items()}, block


def asset_copy_for_bundle(out, sealed, reason=None):
    """D-S107 item 1, D-028: every loop bundle carries the asset copy declaration by default, from
    its own digest (tools/declare_asset_copy.py, the loop's filesystem). A sealed run never reads one,
    so it records the reason `sealed run`; a bundle launched outside us-east-1 records `another
    region`. The controller refuses a us-east-1 launch with neither (require_asset_copy_or_reason)."""
    from ordinary_final_cloud import ASSET_COPY_ABSENCE, ASSET_COPY_ABSENCE_REASONS
    import declare_asset_copy
    if sealed or reason is not None:
        why = 'sealed run' if sealed else reason
        require(why in ASSET_COPY_ABSENCE_REASONS, 'An asset copy absence reason is one of: ' + ', '.join(ASSET_COPY_ABSENCE_REASONS))
        write(Path(out) / ASSET_COPY_ABSENCE, dict(reason=why))
        return dict(declared=False, reason=why)
    declare_asset_copy.declare(out, declare_asset_copy.LOOP_FILESYSTEM_NAME, declare_asset_copy.LOOP_MOUNT)
    return dict(declared=True, reason=None)


def prepare(output, source_commit='HEAD', reuse_assets=None, *, budget=None, workload=None, exposure='exposed',
            test_manifest=None, protected_test=False, inputs_from=None, now_epoch=None, arm='B3', b1_items=None,
            b1_checkpoints=None, replay_prompts=None, launcher_question=None, gate=None, asset_copy_reason=None, layers=None):
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
    require(arm in ('B3', 'B1', 'L', 'G'), 'Arm is B3, B1, L or G')
    require((gate is not None) == (arm == 'G'), 'Arm G needs its gate form; no other arm takes one')
    require(arm != 'G' or (not sealed and workload is None), 'Arm G runs exposed only, on the bound commit, with no workload')
    require(arm != 'L' or not sealed, 'Arm L runs exposed only: a sealed run carries no launcher arm')
    require((launcher_question is not None) == (arm == 'L'), 'Arm L needs --launcher-question; no other arm takes one')
    require((b1_items is not None and b1_checkpoints is not None) == (arm == 'B1'),
            'A B1 bundle needs its items.json and its checkpoints; a B3 bundle takes neither')
    # D-061 item 4: replayed B3 prompts are development material, sealed only into an exposed B1 bundle.
    require(replay_prompts is None or (arm == 'B1' and not sealed),
            'Replay prompts are sealed only into an exposed B1 bundle')
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
    # Arm L also carries the menu and the two files its runtime check reads, and names the
    # sources its prompts are read from so their absence fails here in one line.
    launcher_extra = [n for n in runner.LAUNCHER_SOURCES + runner.LAUNCHER_PROMPT_SOURCES if n not in protocols]
    files = runtime_source(source, extra=protocols + (sorted(set(launcher_extra)) if arm == 'L' else []))
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
    # D-058, D-063: the producer's attention (sdpa, memory-efficient backend pinned) and prefill
    # (one shot), both under D-063, unless the operator seals eager or a chunk size with the
    # recorded decision that asks for it (a measurement run), read from the environment at sealing.
    environment = seal_environment(files, os.environ.get('SHIMMER_INST_FINDER'),
                                   os.environ.get('SHIMMER_PRODUCER_ATTENTION'),
                                   os.environ.get('SHIMMER_PRODUCER_ATTENTION_DECISION'),
                                   os.environ.get('SHIMMER_PRODUCER_PREFILL_CHUNK'),
                                   os.environ.get('SHIMMER_PRODUCER_PREFILL_DECISION'))
    # Only the explicitly selected input files may enter this bundle; named extras stay.
    files = {n:d for n,d in files.items() if not n.startswith('benchmark/') or any(named(n, p) for p in ARCHIVE_EXTRAS)}
    if arm == 'G':
        workload_name, members = 'gate', {'_review_targets.json': b'{}'}
    elif workload is None:
        workload_name, members = default_workload()
    else:
        workload_name, members = ('sealed_test' if sealed else Path(workload).stem), workload_members(workload)
    require('_review_targets.json' in members, 'The workload names its review targets (_review_targets.json)')
    case = members.pop(CASE_MANIFEST, None)
    workload_hashes = {}
    launcher = None
    if arm == 'L':
        # The menu places the workload itself: nothing under input/, the files in one flat folder.
        require(case is None, 'An arm L bundle is never multi-round')
        material = launcher_material_error(members, repository_material(source))
        require(material is None, material or '')
        placed, launcher = launcher_fields(members, launcher_question, files)
        files.update(placed)
        workload_hashes = {n: hashlib.sha256(d).hexdigest() for n, d in members.items() if n != '_review_targets.json'}
    for name, data in (members.items() if arm not in ('L', 'G') else ()):
        if name == '_review_targets.json':
            files['input/context/_review_targets.json'] = data
            continue
        files['input/'+name] = data
        workload_hashes[name] = hashlib.sha256(data).hexdigest()
    multi_round = case is not None
    b1 = None
    if arm == 'B1':
        require(not multi_round, 'A B1 bundle is never multi-round')
        items = Path(b1_items).read_bytes()
        replay_bytes = Path(replay_prompts).read_bytes() if replay_prompts is not None else None
        b1 = b1_fields(items, members['_review_targets.json'], b1_checkpoints,
                       replay_declaration(replay_bytes) if replay_bytes is not None else None)
        # Carried as a support file, never inside the test archive (S5 item 0.2): ids, no gold.
        (OUT/'items.json').write_bytes(items)
        if replay_bytes is not None:
            require(not credential_locations(replay_bytes, 'replay_prompts.json'),
                    'Possible credential in replay_prompts.json; stop without printing content')
            (OUT/'replay_prompts.json').write_bytes(replay_bytes)
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
    # A judging candidate (D-261, D-262): declared beside the list, which stays as it is; its digests
    # are pinned by this seal's manifest alone, since no frozen specification names it. Only the
    # candidate's lane holds this file.
    declared = ROOT/'tools/cloud_run/judge_candidates.json'
    candidates = read(declared) if declared.is_file() else {}
    listed = dict(read(ROOT/'tools/cloud_run/models.json'), **{m: c['revision'] for m, c in candidates.items()})
    for model, revision in listed.items():
        snapshot = cache/('models--'+model.replace('/','--'))/'snapshots'/revision
        allowed = (list(spec['producer']['base_hashes']) if model==spec['producer']['model_id'] else
                   list(spec['auditor']['base_hashes']) if model==spec['auditor']['model_id'] else
                   candidates[model]['files'] if model in candidates else
                   ['config.json','config_sentence_transformers.json','modules.json','sentence_bert_config.json',
                    'special_tokens_map.json','tokenizer.json','tokenizer_config.json','sentencepiece.bpe.model',
                    '1_Pooling/config.json','model.safetensors'])
        entries = {n:dict(sha256=sha(snapshot/n),bytes=(snapshot/n).stat().st_size) for n in allowed}
        if model != 'BAAI/bge-m3' and model not in candidates:
            role='producer' if model==spec['producer']['model_id'] else 'auditor'
            require({n:e['sha256'] for n,e in entries.items()} == spec[role]['base_hashes'], 'Base hashes changed')
        item = dict(model_id=model,revision=revision,files=entries)
        ref = cache_ref_bytes(item)
        item['cache_ref'] = dict(bytes=len(ref),sha256=hashlib.sha256(ref).hexdigest())
        models.append(item)
    locked = pins(OUT/'runtime.candidate.lock')
    gate_block = gate_fields(gate, source, locked) if arm == 'G' else None
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
    if gate_block:
        support_names.append(runner.GATE_SOURCE)
    if b1:
        support_names.append('items.json')
        if 'replay' in b1:
            support_names.append('replay_prompts.json')
    support = {n:sha(OUT/n) for n in support_names}
    provider = read(OUT/'provider_inventory.json')
    # Only loop instances, any number of them (D-S95); budget_fields' guard counts the ledgers too.
    guard.refuse_foreign_inventory(provider['instances'])
    import time
    budget_values = budget_fields(provider, budget, time.time() if now_epoch is None else now_epoch, workload_hashes, arm)
    if reuse_assets:
        assets = bind_existing_assets(reuse_assets,models,wheels,WHEELS,OUT/'assets.tar')
    else:
        assets = build_assets(OUT/'assets.tar',models,wheels,cache,WHEELS)
    workload_record = dict(name=workload_name,review_targets=None if sealed or arm == 'G' else 1,
                           files=({} if sealed else workload_hashes),file_count=len(workload_hashes),
                           answer_key_transferred=False)
    restrictions = ['no second instance','no automatic full-run retry','no tuning',
                    'no protected data' if not protected_test else 'protected test only as sealed by role B',
                    'multi-round only as the sealed case manifest declares' if multi_round else 'no multi-round',
                    'no benchmark workload substitution']
    if gate_block:
        restrictions.append('the sealed gate once on the bound commit\'s tracked tree; no pipeline workload')
    if launcher:
        restrictions.append('the launcher menu once, answered only from the sealed prompt map; base models as shipped, '
                            'no install, every child Python network-denied')
    manifest = dict(schema_version=1,source_commit=source,source_archive_sha256=sha(OUT/'project.tar.gz'),
        classification='PREPARED_NOT_AUTHORIZED',max_runs=1,model_mode='final',multi_round=multi_round,
        protected_test=protected_test,arm=arm,workload=workload_record,
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
            'tools/run_remote_experiment.py',
            # D-401: the cloud reference spend reader the guard counts the API spend with.
            'tools/loop/cloud_reference_spend.py',
            # F1 (D-421): the standing-orders checkers the guard runs before a launch.
            'tools/loop/standing_orders_check.py')},
        support_files=support,models=models,assets_archive=assets,
        preparation_source_hashes={n:sha(ROOT/n) for n in
            ('tools/prepare_ordinary_final_run.py','tools/prepare_ordinary_final_assets.py')},
        packages=locked,wheels=wheels,runtime_file_hashes=runtime_files,
        argv=(runner.gate_argv(gate_block) if gate_block else runner.LAUNCHER_ARGV if launcher
              else MULTI_ROUND_ARGV if multi_round else ARGV),topology=TOPOLOGY,provider='Lambda',
        instance=next(x for x in provider['instance_types']
                      if x['metadata']['type']==budget_values['instance_candidates'][0]['type']),
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
    if b1:
        manifest['b1'] = b1
    if launcher:
        manifest['launcher'] = launcher
    if gate_block:
        manifest['gate'] = gate_block
        # The runner's own reading, so the seal refuses exactly what the instance would.
        runner.arm_declaration(manifest)
    if sealed:
        manifest['test_archive_sha256'] = seal_fields['test_archive_sha256']
    if layers is not None:
        # D-S108, D-S109: the ready-to-run image's layer spec, from the assets just sealed.
        require(not sealed, 'A sealed run reads no provider-side copy, so it carries no image layers')
        manifest['layers'], extra = image_layer_fields(assets, support['install.lock'], manifest['image'], layers)
        for name, data in extra.items():
            (OUT/name).write_bytes(data)
            support[name] = sha(OUT/name)
        manifest['preparation_source_hashes']['tools/image_layers.py'] = sha(ROOT/'tools/image_layers.py')
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
    # D-S107 item 1: the asset copy declared by default, or the reason it is not.
    asset_copy_for_bundle(OUT, sealed, asset_copy_reason)
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
    parser.add_argument('--arm',choices=('B3','B1','L','G'),default='B3',
                        help='the arm this bundle runs (B1: bare_model.py; L: the launcher menu, exposed only; '
                             'G: the gate on the bound commit, exposed only)')
    parser.add_argument('--gate-form',choices=('full','side'),default=None,help='arm G: the gate, or the side gates')
    parser.add_argument('--gate-checks',default='all',help='arm G, full form: all, or check numbers n,n')
    parser.add_argument('--known-red',default='',help='arm G: check numbers expected to fail, n,n')
    parser.add_argument('--comparison',default=None,
                        help='D-S95 item 5: the comparison this bundle belongs to; every bundle of one name runs on one '
                             'machine type, the first launch\'s (recorded at launch beside the private ledger)')
    parser.add_argument('--no-asset-copy',choices=('another region',),default=None,
                        help='D-S107 item 1: the one recorded reason an exposed loop bundle carries no asset copy '
                             'declaration (a sealed run records "sealed run" by itself)')
    parser.add_argument('--uncompared',action='store_true',
                        help='D-401: a B3 or B1 bundle whose figures are compared with no other arm (a console review)')
    parser.add_argument('--gpus',type=int,default=1,
                        help='the GPUs the run needs, exactly (D-S95); only 1 is admitted until the runner\'s '
                             'hardware projection changes (D-382 item 3)')
    parser.add_argument('--type-rule',choices=('fastest','a10_first'),default='fastest',
                        help='D-S79: the fastest offered type first (default), or the A10-first rule')
    parser.add_argument('--instance-types',default=None,
                        help='D-S78: instance types in the order to try, n,n (faster types; no A10-first order or price limit)')
    parser.add_argument('--launcher-question',default=None,help='arm L: the draft question the menu is answered with')
    parser.add_argument('--items',type=Path,default=None,help="B1: the adapter's items.json (ids, no gold)")
    parser.add_argument('--b1-checkpoints',type=Path,default=None,
                        help='B1: JSON list of passes {"name", "checkpoint", "args"} ("checkpoint" tuned or base, '
                             'the name when omitted), run in order, each into evidence/b1/<name>; '
                             '{"name", "replay": true, "args"} runs replay_prompts.py (D-061 item 4)')
    parser.add_argument('--image-layers',action='store_true',
                        help='D-S108: seal the layer spec of the ready-to-run image, so the instance can start from '
                             'the layers on the filesystem when each reads MATCH (needs the asset-copy declaration)')
    parser.add_argument('--image-env-manifest',type=Path,default=None,
                        help='D-S108: the build record of the env layer from an earlier launch, sealing that layer')
    parser.add_argument('--image-measure',action='store_true',
                        help='D-S108 M1: after the image phases, measure cold read rates and form A on the instance')
    parser.add_argument('--replay-prompts',type=Path,default=None,
                        help='B1, exposed only: replay_prompts.json (replay_prompts.py extract) for replay passes')
    args = parser.parse_args()
    prepare(args.output_dir, args.source_commit, args.reuse_assets,
            budget=dict(ledgers=args.ledger, forecast_minutes=args.forecast_minutes,
                        storage_forecast_usd=args.storage_forecast_usd,
                        instance_types=args.instance_types.split(',') if args.instance_types else None,
                        type_rule=args.type_rule, gpus=args.gpus, comparison=args.comparison,
                        uncompared=args.uncompared),
            workload=args.workload, exposure=args.exposure, test_manifest=args.test_manifest,
            protected_test=args.protected_test, inputs_from=args.inputs_from, arm=args.arm, b1_items=args.items,
            b1_checkpoints=read(args.b1_checkpoints) if args.b1_checkpoints else None,
            replay_prompts=args.replay_prompts, launcher_question=args.launcher_question,
            asset_copy_reason=args.no_asset_copy,
            gate=dict(form=args.gate_form,
                      checks='all' if args.gate_checks == 'all' else [int(n) for n in args.gate_checks.split(',') if n],
                      known_red=[int(n) for n in args.known_red.split(',') if n]) if args.arm == 'G' else None,
            layers=dict(env_manifest=args.image_env_manifest, measure=args.image_measure)
            if args.image_layers or args.image_env_manifest or args.image_measure else None)
