"""Sealed ordinary run admission and evidence assessment. No provisioning API.

Import and --verify are model-free. --execute requires a new manifest-bound
operator authorization and consumes one exclusive claim before any model load.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import threading
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def require(value, message):
    if not value:
        raise RuntimeError(message)


def cache_ref_bytes(model):
    """Hub refs are exact revision bytes, not newline-terminated text files."""
    revision = model['revision']
    require(isinstance(revision, str) and re.fullmatch(r'[0-9a-f]{40}', revision),
            'Invalid pinned cache revision')
    return revision.encode('ascii')


def admit_cache_ref(directory, model):
    expected = cache_ref_bytes(model)
    require(model['cache_ref'] == dict(bytes=len(expected), sha256=hashlib.sha256(expected).hexdigest()),
            'Cache ref manifest mismatch')
    require((Path(directory)/'refs/main').read_bytes() == expected,
            'Cache ref must equal exact pinned revision bytes (no whitespace)')


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n', encoding='utf8')


HEX64 = r'[0-9a-f]{64}'
CASE_MANIFEST = 'case_manifest.json'
EXPOSED_NO_MANIFEST = 'exposed, no manifest'
# The live case manifest (S2b item 2): the multi-round manifest schema version 1 of
# scripts/multi_round.py, with exactly these top-level fields, `fixture` false, and every
# source span measured on the bundled LF-normalised document bytes. A fixture (synthetic,
# pre-authored outputs, documents carried inside the file) is refused in a live run.
LIVE_CASE_FIELDS = frozenset({'schema_version', 'case_id', 'fixture', 'allow_recommendations',
                              'decision_support_mode', 'rounds', 'actors', 'issues', 'sources'})


def _multi_round_module():
    try:
        import multi_round
    except ImportError:
        sys.path.append(str(Path(__file__).resolve().parents[1]/'scripts'))
        import multi_round
    return multi_round


def validate_live_case_manifest(value, documents=None):
    """The live case manifest, or a one-line refusal naming the rule, never the content.

    `documents` maps a document id (a context file name without its extension) to its
    LF-normalised text; with it, every round's documents must exist and every source quote
    must equal the text between char_start and char_end exactly, as bind_sources requires
    at run time, so a sealed case cannot fail forty minutes into a rented instance."""
    require(isinstance(value, dict), 'Case manifest must be an object')
    require(set(value) <= LIVE_CASE_FIELDS, 'Case manifest carries a field outside the live schema')
    require(value.get('fixture') is False, 'Fixture case manifest refused in a live run')
    mr = _multi_round_module()
    try:
        checked = mr.validate_manifest(value)
    except mr.InvalidState as exc:
        raise RuntimeError('Invalid case manifest: ' + str(exc)) from None
    if documents is not None:
        for round_ in checked['rounds']:
            for doc in round_['document_ids']:
                require(doc in documents, 'Case document missing from the bundle: a round names an absent document')
        for source in checked['sources']:
            text = documents[source['document_id']]
            require(text[source['char_start']:source['char_end']] == source['quote'],
                    'Case source span does not match the bundled document text')
    return checked


def case_corpus_documents(members, pipeline_source):
    """{document id: text} for context files ({path under input/context/: bytes}), loaded by
    the BOUND pipeline's own _load_corpus: top-level files only, `_` files skipped, empty text
    skipped, ids `stem__ext` on a stem collision, binary formats through its extractor. Read
    from the bound source rather than restated, so sealing and launch validate exactly the
    documents bind_sources will see on the instance."""
    import ast
    import contextlib
    import io
    import tempfile
    source = pipeline_source.decode('utf-8-sig') if isinstance(pipeline_source, bytes) else pipeline_source
    function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == '_load_corpus')
    try:
        import text_extract
    except ImportError:
        sys.path.append(str(Path(__file__).resolve().parents[1]/'scripts'))
        import text_extract
    scope = dict(Path=Path, text_extract=text_extract)
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'bound_pipeline_load_corpus', 'exec'), scope)
    with tempfile.TemporaryDirectory() as folder:
        for name, data in members.items():
            parts = name.split('/')
            require(name and not name.startswith('/') and '..' not in parts and '' not in parts, 'Unsafe case document name')
            target = Path(folder, *parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        # The extractor warns on unsupported files by name; nothing of a test is printed here.
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            documents = scope['_load_corpus'](Path(folder))
    return {d['id']: d['text'] for d in documents}


def argv_for(manifest):
    """The one sealed flag list for the workload the manifest declares. An arm L bundle seals
    none: the launcher menu builds its own flags from the answers it is given."""
    if manifest.get('arm') == 'L':
        return LAUNCHER_ARGV
    return MULTI_ROUND_ARGV if manifest.get('multi_round') is True else ARGV


# The arm a bundle runs (S5 R2, R19): B3 is the full pipeline, B1 the bare-model baseline
# (benchmark/baselines/bare_model.py) on the same document. The sealer writes `arm` into every
# manifest; a manifest sealed before it carries none and is a B3 bundle. A B1 bundle carries
# `b1`: its sealed passes (each a name, optionally the checkpoint it loads, and the bare_model
# arguments that pin it) and the item ids of its one document, read from the sealed items.json.
# A pass's name is a free label (lower case, digits, underscore; unique in the bundle) and its
# output folder; a pass sealed without `checkpoint` loads the checkpoint its name names, as
# every pass did before D-056 condition 6 (so `base` and `tuned` keep their meaning).
# Arm L (D-S13 item 6d) is the launcher menu as shipped: shimmer.sh once, a review then a draft,
# answered only from the sealed prompt map (launcher_declaration, execute_launcher).
ARMS = ('B3', 'B1', 'L')
B1_ITEMS = 'items.json'
B1_NAME = re.compile(r'[a-z0-9][a-z0-9_]{0,31}')
# The checkpoints bare_model.py loads (its --checkpoint choices; a controller check holds them equal).
B1_CHECKPOINT_NAMES = ('tuned', 'base')
# Arguments the runner sets itself for every checkpoint; a sealed checkpoint never carries them.
B1_RUNNER_ARGS = ('--bundle', '--items', '--out', '--checkpoint', '--development')
# Every other option bare_model.py's parser takes (benchmark/baselines/bare_model.py
# build_parser), and whether it takes a value: a sealed checkpoint carries only these, so the
# seal admits exactly what bare_model accepts. A controller check holds this table and
# B1_RUNNER_ARGS equal to the parser's own options (S5 join).
B1_SEALED_ARGS = {'--agent': True, '--profile': True, '--max-new-tokens': True, '--expect-model-id': True,
                  '--expect-digest': True, '--expect-decoding': True, '--sensitive': False,
                  '--prefill-chunk': True, '--prefill-decision': True,
                  '--attention': True, '--attention-decision': True}


def b1_option_values(args, table=None):
    """{option: value} of a well-formed sealed argument list (b1_argument_error is None)."""
    table = B1_SEALED_ARGS if table is None else table
    values, k = {}, 0
    while k < len(args):
        option, joined, value = args[k].partition('=')
        if table.get(option) and not joined:
            value, k = args[k + 1], k + 1
        values[option] = value if table.get(option) else True
        k += 1
    return values


# D-063 (D-061's declared fallback): B1's run proper is sdpa, pinned to the memory-efficient
# backend, prefilled in one shot, both under D-063 (bare_model.attention_record,
# final_models.attention_setting and prefill_setting); eager or chunked prefill is a
# measurement pass and needs its recorded decision. Stated here so the seal refuses what the
# instance would without importing the model code; a controller check holds this rule equal
# to bare_model's on a table of cases.
B1_ATTENTION_DEFAULT = ('sdpa', 'D-063')
B1_PREFILL_DEFAULT = ('one_shot', 'D-063')
B1_DECISION = re.compile(r'D-\d{3}')


def b1_attention_error(args):
    """None, or a one-line reason when a pass's attention or prefill would be refused by
    bare_model (attention_record): eager only with --attention-decision, and an
    --attention-decision with sdpa only when it is the default's own (D-063); chunked prefill
    only with --prefill-decision, and a --prefill-decision with one_shot only when it is the
    default's own (D-063), so the seal refuses what the instance would."""
    values = b1_option_values(args)
    attention = values.get('--attention', B1_ATTENTION_DEFAULT[0])
    if attention not in ('sdpa', 'eager'):
        return 'A B1 pass names an attention bare_model does not take (eager or sdpa)'
    attention_decision = values.get('--attention-decision')
    if attention_decision is not None and not B1_DECISION.fullmatch(str(attention_decision)):
        return 'A B1 pass names an attention decision that is no recorded decision (D-NNN)'
    if attention == B1_ATTENTION_DEFAULT[0] and attention_decision not in (None, B1_ATTENTION_DEFAULT[1]):
        return 'A B1 pass names an attention decision only with eager'
    if attention != B1_ATTENTION_DEFAULT[0] and attention_decision is None:
        return 'A B1 pass runs eager only with --attention-decision'
    chunk, decision = values.get('--prefill-chunk'), values.get('--prefill-decision')
    if chunk is not None and chunk != 'one_shot' and not (chunk.isdigit() and int(chunk) > 0):
        return 'A B1 pass names a prefill chunk bare_model does not take (a positive number of tokens or one_shot)'
    if decision is not None and not B1_DECISION.fullmatch(str(decision)):
        return 'A B1 pass names a prefill decision that is no recorded decision (D-NNN)'
    default = chunk is None or chunk == B1_PREFILL_DEFAULT[0]
    if default and decision not in (None, B1_PREFILL_DEFAULT[1]):
        return 'A B1 pass names a prefill decision only with a chunk size'
    if not default and decision is None:
        return 'A B1 pass prefills in chunks only with --prefill-decision'
    return None


def b1_pass_checkpoint(entry):
    """The checkpoint a sealed pass loads: its `checkpoint`, or its name for a pass sealed
    without one (the meaning every pass had before D-056 condition 6). Refused unless it is one
    bare_model.py loads. A replay pass loads the tuned producer."""
    if entry.get('replay') is True:
        return 'tuned'
    checkpoint = entry.get('checkpoint', entry.get('name'))
    require(checkpoint in B1_CHECKPOINT_NAMES, 'A B1 pass names no checkpoint bare_model loads (tuned or base)')
    return checkpoint


# D-061 item 4: a replay pass runs benchmark/baselines/replay_prompts.py on the sealed
# replay_prompts.json (B3's own rendered producer prompts from an earlier run) instead of
# bare_model.py. The runner sets its prompts file and output folder; the seal carries only these
# options. Its paths and their rule are stated here as replay_prompts.py states them (a controller
# check holds the two equal): a measurement path needs --decision, and --decision needs one.
REPLAY_TOOL = 'benchmark/baselines/replay_prompts.py'
REPLAY_PROMPTS = 'replay_prompts.json'
REPLAY_MEASUREMENT = 'replay_measurement.json'
REPLAY_RUNNER_ARGS = ('--prompts', '--out')
REPLAY_SEALED_ARGS = {'--paths': True, '--decision': True, '--max-new-tokens': True}
REPLAY_PATHS = {'e': True, 'one_shot': True, 'sdpa': False, 'e_repeat': True, 'sdpa_constrained': False}
REPLAY_DEFAULT_PATHS = ('e', 'one_shot', 'sdpa', 'e_repeat')


def replay_paths(args):
    """The paths a well-formed replay pass runs, in order."""
    values = b1_option_values(args, REPLAY_SEALED_ARGS)
    return [p for p in values.get('--paths', ','.join(REPLAY_DEFAULT_PATHS)).split(',') if p]


def replay_error(args):
    """None, or a one-line reason when replay_prompts.py would refuse a replay pass's options."""
    error = b1_argument_error(args, REPLAY_SEALED_ARGS)
    if error:
        return error
    values = b1_option_values(args, REPLAY_SEALED_ARGS)
    paths = replay_paths(args)
    if not paths or len(set(paths)) != len(paths) or any(p not in REPLAY_PATHS for p in paths):
        return 'A replay pass names its paths once each, from ' + ', '.join(REPLAY_PATHS)
    measurement = any(REPLAY_PATHS[p] for p in paths)
    if measurement != ('--decision' in values):
        return 'A replay pass names --decision exactly when it runs a measurement path (e, one_shot or e_repeat)'
    if measurement and not B1_DECISION.fullmatch(str(values['--decision'])):
        return 'A replay pass names a decision that is no recorded decision (D-NNN)'
    return None


def b1_argument_error(args, table=None):
    """None when `args` is a run of B1_SEALED_ARGS options (or `table`'s), each value-taking
    one followed by its value (or written `--option=value`) and each flag alone; otherwise a
    one-line reason."""
    table = B1_SEALED_ARGS if table is None else table
    k = 0
    while k < len(args):
        option, joined, _ = args[k].partition('=')
        if option not in table:
            return 'A B1 checkpoint carries an argument bare_model does not take'
        if table[option] and not joined:
            if k + 1 >= len(args) or args[k + 1].startswith('--'):
                return 'A B1 checkpoint option has no value'
            k += 1
        elif not table[option] and joined:
            return 'A B1 checkpoint flag carries a value'
        k += 1
    return None


def arm_of(manifest):
    arm = manifest.get('arm', 'B3')
    require(arm in ARMS, 'Unknown arm in the manifest')
    return arm


def b1_checkpoints(manifest):
    """The sealed B1 passes, validated: [{name, checkpoint?, args}], at least one, names
    unique, each loading a checkpoint bare_model loads (b1_pass_checkpoint) with arguments
    bare_model takes and an attention it accepts."""
    b1 = manifest.get('b1')
    require(isinstance(b1, dict) and isinstance(b1.get('checkpoints'), list) and b1['checkpoints'],
            'B1 declared without its sealed checkpoints')
    names = []
    replay = b1.get('replay')
    for entry in b1['checkpoints']:
        require(isinstance(entry, dict) and set(entry) in ({'name', 'args'}, {'name', 'checkpoint', 'args'},
                                                            {'name', 'replay', 'args'})
                and isinstance(entry['name'], str)
                and B1_NAME.fullmatch(entry['name']) and isinstance(entry['args'], list)
                and all(isinstance(a, str) for a in entry['args']), 'B1 checkpoint needs a name and its arguments')
        if 'replay' in entry:
            # D-061 item 4: a replay pass, only in a bundle that sealed its prompts.
            require(entry['replay'] is True and isinstance(replay, dict), 'A replay pass needs the sealed replay prompts')
            require(not any(a.split('=', 1)[0] in REPLAY_RUNNER_ARGS for a in entry['args']),
                    'A replay pass carries an argument the runner sets')
            error = replay_error(entry['args'])
        else:
            b1_pass_checkpoint(entry)
            require(not any(a.split('=', 1)[0] in B1_RUNNER_ARGS for a in entry['args']),
                    'A B1 checkpoint carries an argument the runner sets')
            error = b1_argument_error(entry['args']) or b1_attention_error(entry['args'])
        require(error is None, error or '')
        names.append(entry['name'])
    require(len(set(names)) == len(names), 'B1 checkpoint names repeat')
    if replay is not None:
        require(isinstance(replay, dict) and set(replay) == {'prompts_sha256', 'prompt_count'}
                and isinstance(replay['prompts_sha256'], str) and re.fullmatch(HEX64, replay['prompts_sha256'])
                and type(replay['prompt_count']) is int and replay['prompt_count'] > 0,
                'B1 replay declared without its prompts digest and count')
        require(any(e.get('replay') is True for e in b1['checkpoints']), 'Replay prompts sealed without a replay pass')
    return b1['checkpoints']


def is_replay(entry):
    return entry.get('replay') is True


def b1_item_ids(manifest):
    ids = (manifest.get('b1') or {}).get('item_ids')
    require(isinstance(ids, list) and ids and all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids),
            'B1 declared without its item ids')
    return ids


def arm_declaration(manifest):
    """The arm, or a one-line refusal: a B1 bundle carries its checkpoints, its item ids and
    the sealed items.json and is never multi-round; a B3 bundle carries none of them."""
    arm = arm_of(manifest)
    support = manifest.get('support_files', {})
    if arm == 'L':
        launcher_declaration(manifest)
        require(manifest.get('multi_round') is False and manifest.get('protected_test') is False,
                'An arm L bundle is never multi-round and never a protected test')
        require('b1' not in manifest and B1_ITEMS not in support and REPLAY_PROMPTS not in support,
                'B1 fields sealed in an arm L bundle')
        return arm
    require('launcher' not in manifest, 'A launcher block sealed in a %s bundle' % arm)
    if arm == 'B1':
        b1_checkpoints(manifest)
        b1_item_ids(manifest)
        require(manifest.get('multi_round') is False, 'A B1 bundle is never multi-round')
        require(isinstance(support.get(B1_ITEMS), str) and support[B1_ITEMS] == manifest['b1'].get('items_sha256'),
                'B1 declared without its sealed items.json')
        replay = manifest['b1'].get('replay')
        if replay is None:
            require(REPLAY_PROMPTS not in support, 'Replay prompts sealed without a replay declaration')
        else:
            require(support.get(REPLAY_PROMPTS) == replay['prompts_sha256'], 'Replay declared without its sealed prompts')
    else:
        require('b1' not in manifest and B1_ITEMS not in support and REPLAY_PROMPTS not in support,
                'B1 fields sealed in a B3 bundle')
    return arm


def launcher_exposed(arm, exposure):
    """False only for an arm L bundle in a sealed run: the menu runs development material."""
    return not (arm == 'L' and exposure == 'sealed')


def admit_arm(manifest, permit):
    """The arm the launch plan ran this bundle as (written into its authorization by the
    controller) must equal the arm it was sealed with; an authorization naming no arm is a B3
    authorization, so a B1 bundle is never run on one."""
    require(permit.get('arm', 'B3') == arm_of(manifest), 'Arm authorization mismatch')


def admit_workload(manifest, seal, base=None):
    """Replaces the old blanket refusal ('Excluded workload') of multi-round and protected
    tests: each is admitted exactly when it is DECLARED in the manifest, SEALED (bound by a
    hash the seal covers) and VALID, and an undeclared one is refused as before. A bundle can
    never claim more than it was sealed with."""
    require(type(manifest.get('multi_round')) is bool and type(manifest.get('protected_test')) is bool,
            'Workload declaration must be explicit')
    exposure = seal.get('exposure', 'exposed')
    require(exposure in ('exposed', 'sealed'), 'Unknown exposure in the seal')
    if exposure == 'sealed':
        # Sealed runs only: declared sealed, the test archive hash the bundle was built from
        # equals the seal's, and the code commit equals the seal's (the frozen tag's commit,
        # resolved by the controller before launch).
        require(isinstance(seal.get('test_manifest_sha256'), str) and re.fullmatch(HEX64, seal['test_manifest_sha256'])
                and isinstance(manifest.get('test_archive_sha256'), str)
                and seal.get('test_archive_sha256') == manifest['test_archive_sha256']
                and seal.get('code_commit') == manifest['source_commit'], 'Sealed declaration not bound to its test')
    else:
        # Exposed runs behave as before: no protected test.
        require(manifest['protected_test'] is False, 'Protected test requires a sealed run')
        require(seal.get('test_manifest_sha256', EXPOSED_NO_MANIFEST) == EXPOSED_NO_MANIFEST,
                'An exposed run carries no test manifest')
    support = manifest.get('support_files', {})
    if manifest['multi_round']:
        digest = manifest.get('case_manifest_sha256')
        require(isinstance(digest, str) and re.fullmatch(HEX64, digest) and support.get(CASE_MANIFEST) == digest,
                'Multi-round declared without its sealed case manifest')
        if base is not None:
            require(sha(Path(base)/CASE_MANIFEST) == digest, 'Case manifest changed')
            case = read(Path(base)/CASE_MANIFEST)
            require(isinstance(case, dict) and case.get('fixture') is False, 'Fixture case manifest refused in a live run')
            require(set(case) <= LIVE_CASE_FIELDS, 'Case manifest carries a field outside the live schema')
    else:
        require('case_manifest_sha256' not in manifest and CASE_MANIFEST not in support,
                'Case manifest sealed without a multi-round declaration')
    require(manifest['argv'] == argv_for(manifest), 'Run flags changed')
    arm = arm_declaration(manifest)
    # D-061 item 4: replayed B3 prompts are development material, never part of a sealed run.
    require(not (arm == 'B1' and manifest['b1'].get('replay') is not None and exposure == 'sealed'),
            'Replay prompts are development material: a sealed run carries none')
    # D-S13 item 6d: the launcher menu runs base models on a development workload; never sealed.
    require(launcher_exposed(arm, exposure), 'Arm L runs exposed only: a sealed run carries no launcher arm')
    return dict(multi_round=manifest['multi_round'], protected_test=manifest['protected_test'], exposure=exposure, arm=arm)


def verify(base):
    base = Path(base).resolve()
    manifest = read(base/'execution_manifest.json')
    seal = read(base/'seal.json')
    require(seal['execution_manifest_sha256'] == sha(base/'execution_manifest.json'), 'Manifest seal mismatch')
    require(manifest['max_runs'] == 1 and manifest['model_mode'] == 'final', 'Ordinary final run only')
    admit_workload(manifest, seal, base)
    require(manifest['topology'] == TOPOLOGY, 'Residency topology changed')
    for key,value in {'SHIMMER_MODEL_MODE':'final','SHIMMER_BACKEND_PROFILE':'local',
                      'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','CUBLAS_WORKSPACE_CONFIG':':4096:8'}.items():
        require(manifest['environment'].get(key)==value,'Runtime environment changed: '+key)
    project = base/'project'
    expected = manifest['project_files']
    # A fresh allowlisted project is essential: ambient input/durable data must
    # never join the selected corpus, even if the expected files still match.
    actual = {p.relative_to(project).as_posix() for p in project.rglob('*') if p.is_file()}
    require(actual == set(expected), 'Unexpected or missing project files')
    for name, digest in expected.items():
        p = project/name
        require(not p.is_symlink() and sha(p) == digest, 'Project hash mismatch: '+name)
    for name, digest in manifest['support_files'].items():
        require(sha(base/name) == digest, 'Support hash mismatch: '+name)
    return manifest


ARGV = ['--backend-profile', 'local', '--activation-profile', 'dense',
        '--review-mode', 'paired', '--task', 'review', '--mode', 'standalone',
        '--non-interactive', '--skip-confirmation', '--sensitivity-layer-inactive-override',
        '--no-redaction-override', '--execution-topology', 'report_optimized',
        '--topology-config', 'topology.json', '--agent-briefs', 'enabled',
        '--input-language', 'auto', '--output-language', 'en']
TOPOLOGY = {'schema_version': 1, 'lanes': [
    {'name': 'primary', 'device': 'cuda:0', 'resident_limit': 1}]}
# A declared multi-round Review: the ordinary flags under `reference_serial` (D-011 choice 3:
# the topology code is not widened), no topology configuration, and the sealed case manifest.
MULTI_ROUND_ARGV = ['--backend-profile', 'local', '--activation-profile', 'dense',
                    '--review-mode', 'paired', '--task', 'review', '--mode', 'standalone',
                    '--non-interactive', '--skip-confirmation', '--sensitivity-layer-inactive-override',
                    '--no-redaction-override', '--execution-topology', 'reference_serial',
                    '--agent-briefs', 'enabled', '--input-language', 'auto', '--output-language', 'en',
                    '--multi-round', '--multi-round-manifest', CASE_MANIFEST]


def selected_candidate(manifest, permit):
    """The sealed instance candidate the authorization names; nothing outside the list."""
    matches = [c for c in manifest['instance_candidates'] if c['type'] == permit.get('instance_type')]
    require(len(matches) == 1 and permit.get('instance_candidate') == matches[0], 'Instance authorization mismatch')
    return matches[0]


def authorization(base, manifest, permit, now=None):
    now = time.time() if now is None else now
    require(permit.get('operator_authorized') is True and
            permit.get('action') == 'one-ordinary-final-cloud-run', 'New explicit authorization required')
    require(permit.get('execution_manifest_sha256') == sha(Path(base)/'execution_manifest.json'), 'Authorization manifest mismatch')
    require(permit.get('seal_sha256') == sha(Path(base)/'seal.json'), 'Authorization seal mismatch')
    require(permit.get('source_commit') == manifest['source_commit'], 'Authorization source mismatch')
    require(permit.get('soft_budget_usd') == manifest['soft_budget_usd'] and
            permit.get('hard_ceiling_usd') == manifest['hard_ceiling_usd'], 'Budget authorization mismatch')
    require(permit.get('multi_round') == manifest['multi_round'], 'Workload authorization mismatch')
    admit_arm(manifest, permit)
    candidate = selected_candidate(manifest, permit)
    require(permit.get('provider') == 'Lambda' and isinstance(permit.get('region'), str)
            and re.fullmatch(r'[a-z]+-[a-z]+-[0-9]+', permit['region']), 'Instance authorization mismatch')
    require(isinstance(permit.get('instance_id'),str) and
            re.fullmatch(r'[a-f0-9]{32}|[a-f0-9-]{36}',permit['instance_id']), 'Instance ID required')
    require(0 < permit['hourly_rate'] <= candidate['max_hourly_rate'], 'Price exceeds ceiling')
    start = permit['active_start_epoch']
    require(isinstance(start, (int, float)) and 0 < start <= now, 'Invalid billing start')
    require(now < start + manifest['hard_ceiling_usd']/permit['hourly_rate']*3600 - manifest['workload_stop_reserve_seconds'],
            'Insufficient execution/collection reserve')


def b1_observation(folder, item_ids):
    """What one B1 checkpoint left in its own output folder: its reply records
    (audit/model_replies, one file per call, reply_records.write) and its labels (one per item,
    each naming the call id of its reply). Counts and ids only, never a reply's text."""
    folder = Path(folder)
    records = {}
    replies = folder/'audit'/'model_replies'
    if replies.is_dir():
        for path in sorted(replies.glob('*.json')):
            try:
                call = read(path).get('call_id')
            except (OSError, ValueError, AttributeError):
                call = None
            records[path.name] = call
    calls = [c for c in records.values() if c]
    missing = []
    for item in item_ids:
        try:
            call = read(folder/'labels'/(item+'.json')).get('call_id')
        except (OSError, ValueError, AttributeError):
            call = None
        if not call or calls.count(call) != 1:
            missing.append(item)
    return dict(items=len(item_ids), reply_records=len(records), items_without_one_record=missing,
                summary_written=(folder/'b1_summary.json').is_file())


def replay_observation(folder, prompt_count, paths):
    """What one replay pass left in its own folder (D-061 item 4): one reply record per prompt
    per path, and its replay_measurement.json. Counts only, in b1_observation's shape, so the
    entry's assessment holds a replay pass to the same one-record-per-call rule."""
    folder = Path(folder)
    replies = folder/'audit'/'model_replies'
    records = len(list(replies.glob('*.json'))) if replies.is_dir() else 0
    expected = prompt_count*len(paths)
    return dict(items=expected, reply_records=records, items_without_one_record=[] if records == expected else ['replay'],
                summary_written=(folder/REPLAY_MEASUREMENT).is_file(), replay=True)


def pass_observation(base_evidence, manifest, entry):
    """The observation of one sealed pass, a bare_model pass or a replay pass."""
    folder = Path(base_evidence)/'b1'/entry['name']
    if is_replay(entry):
        return replay_observation(folder, manifest['b1']['replay']['prompt_count'], replay_paths(entry['args']))
    return b1_observation(folder, b1_item_ids(manifest))


def assess_b1(checkpoints):
    """A B1 entry's health: every sealed checkpoint returned 0 and left exactly one reply record
    per item in its own folder, and no other record. No pipeline marker is asked for."""
    reasons = []
    if not checkpoints:
        reasons.append('b1_no_checkpoint_ran')
    for name, seen in sorted((checkpoints or {}).items()):
        if seen.get('exit_code') != 0:
            reasons.append('b1_checkpoint_failed:'+name)
        if seen.get('items_without_one_record') or not seen.get('items'):
            reasons.append('b1_reply_record_missing:'+name)
        if seen.get('reply_records') != seen.get('items'):
            reasons.append('b1_reply_record_count:'+name)
    return {'execution_integrity_passed': not reasons, 'reasons': reasons, 'arm': 'B1',
            'checkpoints': checkpoints or {}, 'failed_backend_attempts': None,
            'collection_and_teardown_pending': True, 'quality_claim': None}


def semantic_incomplete(completion):
    """True when the pipeline reached its end with exit code 0 and its completion record marks
    the semantic work incomplete (scripts/run_completion.py: semantic_complete false, state
    stopped)."""
    return bool(completion and completion.get('reached_end') is True and completion.get('exit_code') == 0
                and completion.get('semantic_complete') is False)


def model_call_required(multi_round):
    """Whether the run's telemetry must hold a Producer 168 model call. Every run that is not
    a declared multi-round run must. A declared multi-round run (`multi_round` not None) asks no
    model by design (open item 35: its case records and round review are computed in Python), so
    its own evidence is the pipeline_start and pipeline_end pair and the case record checks.
    Measured, not preferred: L7 (2026-10-30) failed all nine multi-round entries that reached
    `reviewed` and `activated` on this requirement alone (D-100)."""
    return multi_round is None


def assess(completion, raw, multi_round=None, arm='B3', b1=None, launcher=None):
    """Run health. A declared multi-round run (D-011 choice 11) also needs its saved case
    record (multi_round.read_saved) to show outcome `reviewed`, activation `activated` and, when
    reviewed, a Python round review recorded (`round_review.availability`);
    quality is reported separately and is never a pass. Its telemetry needs exactly one
    pipeline_start and one pipeline_end and does not require a model call (model_call_required, D-101). A B1 entry is assessed on its own
    records (assess_b1, `b1` maps each checkpoint to its observation and exit code), an arm L
    entry on its session and its two run folders (assess_launcher)."""
    if arm == 'B1':
        return assess_b1(b1)
    if arm == 'L':
        return assess_launcher(launcher)
    reasons = []
    if multi_round is not None:
        if not (isinstance(multi_round, dict) and multi_round.get('outcome') == 'reviewed'):
            reasons.append('multi_round_not_reviewed')
        if not (isinstance(multi_round, dict) and (multi_round.get('activation') or {}).get('activated') is True):
            reasons.append('multi_round_not_activated')
        if (isinstance(multi_round, dict) and multi_round.get('outcome') == 'reviewed' and
                (multi_round.get('round_review') or {}).get('availability') != 'recorded'):
            # S2 checker A10: a reviewed run whose Python round review failed is not healthy.
            reasons.append('multi_round_round_review_not_recorded')
    if semantic_incomplete(completion):
        # D-061 (b): the pipeline reached its end with exit 0 and its completion record says the
        # semantic work was incomplete (PAIRING-A: a partition or a delivery failed its contract;
        # run_completion records it as state stopped). That is its own reason, not a pipeline
        # that did not complete.
        reasons.append('semantic_incomplete')
    elif not (completion and completion.get('state') == 'completed' and
              completion.get('reached_end') is True and completion.get('exit_code') == 0):
        reasons.append('pipeline_not_completed')
    if not (sum(r['event']=='pipeline_start' for r in raw)==1 and
            sum(r['event']=='pipeline_end' for r in raw)==1 and
            (not model_call_required(multi_round) or
             any(r['event']=='model_call' and r.get('adapter_checkpoint')==168 for r in raw))):
        reasons.append('required_telemetry_missing')
    if any(r['event'] == 'auditor_pair' and r.get('classifier_status') == 'failed' for r in raw):
        reasons.append('auditor_pair_failure')
    # PROCESSOR already has a bounded partition-recovery contract. Its terminal
    # merged completeness is enforced by RunCompletion; a recovered attempt must
    # remain visible without undoing that existing policy.
    if any(r['event'] == 'model_call' and r.get('contract_valid') is False and r.get('agent')!='PROCESSOR' for r in raw):
        reasons.append('required_contract_failure')
    if any(r['event'] == 'backend_invocation' and r.get('backend_success') is False and r.get('agent')!='PROCESSOR' for r in raw):
        reasons.append('backend_failure')
    # Refusal, unavailable ownership and structural disagreement are observations,
    # never fabricated findings or new semantic rejection criteria.
    return {'execution_integrity_passed': not reasons, 'reasons': reasons,
            'failed_backend_attempts':sum(r['event']=='backend_invocation' and r.get('backend_success') is False for r in raw),
            'collection_and_teardown_pending': True, 'quality_claim': None}


def failure_identity(exc, project):
    """Exception type, class module, raising frame and innermost project frame.

    File basenames, line numbers and function names only, never message text:
    the type-only receipt of run 88323b86 could not say where its RuntimeError
    was raised, and the cause had to be re-derived from source."""
    import traceback
    frames = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ is not None else []
    def label(frame):
        return Path(frame.filename).name+':'+str(frame.lineno)+':'+frame.name
    def inside(frame):
        # Same rule as scripts/model_telemetry.project_frame: a pseudo-filename
        # resolves against the working directory, which IS the project during a
        # run, and an in-tree virtual environment holds library code; either
        # would report a foreign frame as the project origin.
        name = str(frame.filename)
        if name.startswith('<') or not name.endswith('.py'):
            return False
        try:
            path = Path(name).resolve()
            relative = path.relative_to(Path(project).resolve())
        except (OSError, ValueError):
            return False
        return path.is_file() and relative.parts[0] not in {'.venv', 'venv', 'site-packages', '.tmp'}
    origin = next((f for f in reversed(frames) if inside(f)), None)
    return {'error_type': type(exc).__name__, 'error_module': type(exc).__module__,
            'error_frame': label(frames[-1]) if frames else None,
            'error_origin': label(origin) if origin else None}


def installed_runtime(manifest, distribution=None):
    if distribution is None:
        import importlib.metadata
        distribution=importlib.metadata.distribution
    for package,version in manifest['packages'].items():
        require(distribution(package).version==version,'Package mismatch: '+package)
    for package,files in manifest['runtime_file_hashes'].items():
        dist=distribution(package)
        for name,digest in files.items():
            require(sha(dist.locate_file(name))==digest,'Installed runtime hash mismatch: '+package)


def gpu_matches(token, name):
    """Whole-token match, so 'A10' never admits an 'A100'."""
    return bool(token) and re.search(r'(?<![A-Za-z0-9])'+re.escape(token)+r'(?![0-9])', str(name)) is not None


def hardware_admission(base, torch, psutil, candidate):
    """The selected type's requirements, read from its sealed candidate entry: its GPU, the
    run's VRAM, the host the provider advertised for that type, and the run's own floors."""
    require(torch.cuda.device_count()==1,'Exactly one GPU required')
    props=torch.cuda.get_device_properties(0)
    free,total=torch.cuda.mem_get_info(0)
    memory=psutil.virtual_memory()
    value=dict(gpu_name=props.name,gpu_total_bytes=total,gpu_free_bytes=free,
               cpu_count=psutil.cpu_count(),ram_total_bytes=memory.total,ram_available_bytes=memory.available,
               disk_free_bytes=shutil.disk_usage(base).free,instance_type=candidate['type'])
    require(gpu_matches(candidate['gpu_token'],props.name) and total>=candidate['run_gpu_total_bytes']
            and free>=candidate['run_gpu_free_bytes'],'GPU memory admission')
    require(value['cpu_count']>=candidate['min_cpu'] and memory.total>=candidate['min_ram_bytes']
            and memory.available>=candidate['run_ram_available_bytes'],'Host resource admission')
    require(value['disk_free_bytes']>=candidate['run_disk_free_bytes'],'Storage admission')
    return value


def disk_reading(path):
    """One reading of the filesystem holding `path`, in bytes, as `df -B1` reports it (used is
    the total less the free blocks; available is what an unprivileged writer may still use).
    Never raises: a failed reading says why. Self-contained, because the controller's evidence
    packer carries this function's own source to the instance."""
    import os
    import time
    try:
        stat = os.statvfs(str(path))
        total = stat.f_blocks*stat.f_frsize
        return dict(path=str(path), epoch=time.time(), total_bytes=total,
                    used_bytes=total-stat.f_bfree*stat.f_frsize, available_bytes=stat.f_bavail*stat.f_frsize)
    except Exception as exc:
        return dict(path=str(path), epoch=time.time(), unavailable=(type(exc).__name__+': '+str(exc))[:200])


DISK_SAMPLE_SECONDS = 15
DISK_USAGE = 'disk_usage.json'
DISK_PEAK_KIND = ('sampled: the largest of the readings taken before the workload, every %d s during it '
                  'and after it; not a continuous maximum' % DISK_SAMPLE_SECONDS)


class DiskSampler:
    """Disk in use on the run root's filesystem (environment, wheels, model cache, assets and
    run folder together): before the workload, sampled during it, after it. The file is
    rewritten after every reading, so a budget stop keeps what was read. Never fails a run."""

    def __init__(self, root, path, interval=DISK_SAMPLE_SECONDS, reading=None):
        self.root, self.path, self.interval = str(root), Path(path), interval
        self.reading = reading or (lambda where: disk_reading(where))
        self.stop_event = threading.Event()
        self.thread = None
        self.value = dict(path=self.root, sample_seconds=interval, peak_kind=DISK_PEAK_KIND, before_workload=None,
                          peak=None, after_workload=None, readings=0, unavailable_readings=0, last_unavailable=None)

    def take(self, slot=None):
        reading = self.reading(self.root)
        if 'used_bytes' in reading:
            self.value['readings'] += 1
            if self.value['peak'] is None or reading['used_bytes'] > self.value['peak']['used_bytes']:
                self.value['peak'] = reading
        else:
            self.value['unavailable_readings'] += 1
            self.value['last_unavailable'] = reading.get('unavailable')
        if slot:
            self.value[slot] = reading
        try:
            write(self.path, self.value)
        except Exception:
            pass

    def loop(self):
        while not self.stop_event.wait(self.interval):
            try:
                self.take()
            except Exception:
                pass

    def start(self):
        try:
            self.take('before_workload')
            self.thread = threading.Thread(target=self.loop, name='ordinary-disk-sampler', daemon=True)
            self.thread.start()
        except Exception:
            pass
        return self

    def stop(self):
        try:
            self.stop_event.set()
            if self.thread is not None:
                self.thread.join(timeout=5)
            self.take('after_workload')
        except Exception:
            pass


BARE_MODEL = 'benchmark/baselines/bare_model.py'


def load_bare_model(project):
    """benchmark/baselines/bare_model.py of the sealed project, imported in THIS process, so the
    budget stop's os._exit(124) and the controller's cleanup (which stops processes named
    ordinary_final_run.py) stop it as they stop the pipeline. The pipeline is never imported."""
    path = (Path(project)/BARE_MODEL).resolve()
    loaded = sys.modules.get('bare_model')
    if loaded is not None and Path(getattr(loaded, '__file__', '')).resolve() == path:
        return loaded
    import importlib.util
    spec = importlib.util.spec_from_file_location('bare_model', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['bare_model'] = module
    spec.loader.exec_module(module)
    return module


def load_replay(project):
    """benchmark/baselines/replay_prompts.py of the sealed project, imported in THIS process, as
    load_bare_model imports bare_model (D-061 item 4)."""
    path = (Path(project)/REPLAY_TOOL).resolve()
    loaded = sys.modules.get('replay_prompts')
    if loaded is not None and Path(getattr(loaded, '__file__', '')).resolve() == path:
        return loaded
    import importlib.util
    spec = importlib.util.spec_from_file_location('replay_prompts', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['replay_prompts'] = module
    spec.loader.exec_module(module)
    return module


def b1_argv(base, project, out, checkpoint):
    """bare_model.main's arguments for one sealed pass: the bundle is the sealed workload as the
    pipeline would read it (project/input: context/ with its targets file, and conventions/),
    the item table is the sealed items.json, the output is the pass's own folder, then the
    checkpoint the pass loads (b1_pass_checkpoint) and the arguments sealed with it. A replay
    pass runs replay_prompts.py on the sealed replay_prompts.json into its own folder."""
    if is_replay(checkpoint):
        return ['run', '--prompts', str(Path(base)/REPLAY_PROMPTS), '--out', str(out), *checkpoint['args']]
    return ['--bundle', str(Path(project)/'input'), '--items', str(Path(base)/B1_ITEMS), '--out', str(out),
            '--checkpoint', b1_pass_checkpoint(checkpoint), *checkpoint['args']]


def expected_records(manifest):
    """One reply record per item per bare_model pass, and per prompt per path per replay pass."""
    total = 0
    for entry in b1_checkpoints(manifest):
        total += (manifest['b1']['replay']['prompt_count']*len(replay_paths(entry['args'])) if is_replay(entry)
                  else len(b1_item_ids(manifest)))
    return total


def run_b1(base, manifest, project, evidence):
    """Run B1 once per sealed pass, in order, each into evidence/b1/<name>; returns
    {name: exit code}. A pass that raises is recorded and the next one still runs."""
    module = load_bare_model(project)
    checkpoints = b1_checkpoints(manifest)
    root = Path(evidence)/'b1'
    root.mkdir(exist_ok=False)
    # The progress reader's total (PROGRESS-A): one reply record per item per checkpoint, and
    # per prompt per path of a replay pass.
    (root/'expected_records').write_text('%d\n' % expected_records(manifest), encoding='utf8')
    codes = {}
    for checkpoint in checkpoints:
        out = root/checkpoint['name']
        require(not out.exists(), 'B1 checkpoint folder already exists')
        try:
            runner = load_replay(project) if is_replay(checkpoint) else module
            code = runner.main(b1_argv(base, project, out, checkpoint))
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
        except Exception as exc:
            out.mkdir(parents=True, exist_ok=True)
            write(out/'terminal_error.json', failure_identity(exc, project))
            code = 1
        codes[checkpoint['name']] = code if isinstance(code, int) else 1
    return codes


def execute_b1(base, manifest, project, evidence, rec):
    """The B1 arm after every guard execute() applies: no pipeline import, one bare_model run
    per sealed checkpoint, then the arm-aware assessment written to evidence/result.json."""
    codes = {}
    try:
        codes = run_b1(base, manifest, project, evidence)
    except BaseException as exc:
        write(evidence/'terminal_error.json', failure_identity(exc, project))
    finally:
        rec.close()
        seen = {c['name']: dict(pass_observation(evidence, manifest, c), exit_code=codes.get(c['name']))
                for c in b1_checkpoints(manifest)}
        result = assess(None, [], arm='B1', b1=seen)
        result['pipeline_exit_code'] = None
        write(evidence/'result.json', result)
    return 0 if result['execution_integrity_passed'] else 2


# Arm L (D-S13 item 6d): a real review and a real draft started from the launcher menu, on the
# loop's own instance, never on the laptop. shimmer.sh runs once with pipes; every prompt the
# menu, the intake wizard or the pipeline prints is answered ONLY from the sealed prompt map, by
# its exact text: the menu's [1] then R (the wizard: the sealed folder, the cutoff kept, Normal
# mode, the defaults, y, the sealed review targets), the pipeline's three questions, then [1]
# then D (the sealed question, Normal mode, y), the same three questions, then Q. A prompt the
# map does not hold, an answer list used up, or the deadline ends the session and is recorded;
# nothing is ever guessed. The children run the base checkpoints as shipped
# (SHIMMER_MODEL_MODE=base, config/local_models.json; the sealed asset archive carries them)
# with every child Python's network denied by a sitecustomize that applies the observer's own
# deny_network and records into its own log. Integrity only: base models as shipped make no
# claim comparable with B3 or B1.
LAUNCHER_ARGV = []
LAUNCHER_SCRIPT = 'shimmer.sh'
LAUNCHER_WORKLOAD = 'launcher_input'
LAUNCHER_WORKLOAD_TOKEN = '{launcher_workload}'
LAUNCHER_TASKS = ('review', 'draft')
# What every child of the menu runs under, exactly: the shipped base models, no install (the
# instance's pinned runtime is the environment), the hub and pip offline, unbuffered output.
LAUNCHER_CHILD_ENVIRONMENT = {'SHIMMER_MODEL_MODE': 'base', 'SHIMMER_SKIP_INSTALL': '1', 'HF_HUB_OFFLINE': '1',
                              'TRANSFORMERS_OFFLINE': '1', 'PIP_NO_INDEX': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
                              'PYTHONUNBUFFERED': '1'}
# Files the menu reads that the runtime archive does not otherwise carry (the sealer adds them).
LAUNCHER_SOURCES = ('shimmer.sh', 'tools/runtime_contract.py', 'tools/cloud_run/runtime.json')
# Where a sealed prompt must be written, word for word: a printf text of shimmer.sh or one
# string constant of the wizard or the pipeline.
LAUNCHER_PROMPT_SOURCES = ('shimmer.sh', 'scripts/intake_wizard.py', 'scripts/pipeline.py')
# Answers that fix what the session is: the menu's [1] twice then Q, a review then a draft.
LAUNCHER_FIXED_ANSWERS = {'menu': ['1', '1', 'Q'], 'task': ['R', 'D']}
LAUNCHER_PROMPT_KEYS = {'id', 'prompt', 'answers', 'optional', 'repeat_last'}
LAUNCHER_PROMPT_ID = re.compile(r'[a-z][a-z_]{0,31}')
LAUNCHER_QUESTION_LIMIT = 300
# A prompt is answered once the output has been quiet this long after it (it then waits on input).
LAUNCHER_QUIET_SECONDS = 0.5
# Output quiet this long on a line ending in ':' or '?' that no sealed prompt matches: an
# unknown prompt, and the session stops (a model load or a generation prints whole lines).
LAUNCHER_UNKNOWN_PROMPT_SECONDS = 60
# No output at all for this long stops the session (a hung child, or a prompt followed by a line
# another thread printed, which the map cannot see); a model call prints well within it.
LAUNCHER_IDLE_SECONDS = 1800
# The session is stopped this long before the runner's own budget stop, so it is recorded.
LAUNCHER_STOP_MARGIN_SECONDS = 60
LAUNCHER_NETWORK_DIR_ENV = 'SHIMMER_LAUNCHER_NETWORK_DIR'
LAUNCHER_OBSERVER_ENV = 'SHIMMER_LAUNCHER_OBSERVER'
# Every child Python of the menu loads this from PYTHONPATH (a -I interpreter loads nothing, and
# the runtime contract's own -I probes run nothing but a version query). It never fails a child:
# a denial that could not be installed in full is recorded as partial.
LAUNCHER_SITECUSTOMIZE = '''import os as _os


def _shimmer_deny_network():
    where = _os.environ.get(%(network)r)
    observer = _os.environ.get(%(observer)r)
    if not where or not observer:
        return
    import sys
    sys.path.insert(0, observer)
    try:
        import cloud_run_observer
    finally:
        sys.path.remove(observer)
    rec = cloud_run_observer.Recorder(_os.path.join(where, 'network_%%d.jsonl' %% _os.getpid()))
    rec.event('process_start', pid=_os.getpid(), parent=_os.getppid(),
              program=_os.path.basename(sys.argv[0]) if getattr(sys, 'argv', None) else '')
    import socket
    before = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo)
    try:
        cloud_run_observer.deny_network(rec)
        rec.event('network_denial', status='installed')
    except Exception as exc:
        # deny_network replaces the socket layer first, then the HTTP clients; an interpreter
        # without those clients (the image's own python3 the menu starts with) keeps the socket
        # layer denied, which every client goes through.
        after = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo)
        sockets = all(a is not b for a, b in zip(after, before))
        rec.event('network_denial', status='sockets' if sockets else 'partial', error_type=type(exc).__name__)


try:
    _shimmer_deny_network()
except Exception:
    pass
''' % dict(network=LAUNCHER_NETWORK_DIR_ENV, observer=LAUNCHER_OBSERVER_ENV)
# Called by the budget stop before it ends the runner, so the menu's children end with it.
STOP_HOOKS = []


def sitecustomize_source():
    """The sitecustomize every child Python of the menu loads (LAUNCHER_SITECUSTOMIZE)."""
    return LAUNCHER_SITECUSTOMIZE


def launcher_declaration(manifest):
    """The sealed launcher block, validated, or a one-line refusal: the menu script and the
    workload folder by name, the draft question, the children's environment exactly
    LAUNCHER_CHILD_ENVIRONMENT, and a prompt map whose answers make the session a review then a
    draft then Q. Each prompt {id, prompt, answers, optional, repeat_last}: ids and texts unique,
    no answer spanning a line, and only an optional prompt (one that may never be printed, such
    as an escalation) repeating its last answer."""
    value = manifest.get('launcher')
    require(isinstance(value, dict) and set(value) == {'script', 'workload', 'question', 'prompts', 'child_environment'},
            'Arm L declared without its sealed launcher block')
    require(value['script'] == LAUNCHER_SCRIPT and value['workload'] == LAUNCHER_WORKLOAD,
            'The launcher block names another script or workload folder')
    require(value['child_environment'] == LAUNCHER_CHILD_ENVIRONMENT,
            'The launcher children run the base models offline with no install, exactly as sealed')
    question = value['question']
    require(isinstance(question, str) and question.strip() == question and question
            and len(question) <= LAUNCHER_QUESTION_LIMIT and '\n' not in question and '\r' not in question,
            'The draft question is one line of at most %d characters' % LAUNCHER_QUESTION_LIMIT)
    prompts = value['prompts']
    require(isinstance(prompts, list) and prompts, 'The launcher block carries no prompt map')
    ids, texts = [], []
    for entry in prompts:
        require(isinstance(entry, dict) and set(entry) == LAUNCHER_PROMPT_KEYS and isinstance(entry['id'], str)
                and LAUNCHER_PROMPT_ID.fullmatch(entry['id']) and isinstance(entry['prompt'], str)
                and entry['prompt'].strip() and '\n' not in entry['prompt'] and isinstance(entry['answers'], list)
                and entry['answers'] and all(isinstance(a, str) and '\n' not in a and '\r' not in a for a in entry['answers'])
                and type(entry['optional']) is bool and type(entry['repeat_last']) is bool,
                'A sealed prompt needs an id, its text, its answers and whether it is optional')
        require(not entry['repeat_last'] or entry['optional'], 'Only an optional prompt repeats its last answer')
        ids.append(entry['id'])
        texts.append(entry['prompt'])
    require(len(set(ids)) == len(ids) and len(set(texts)) == len(texts), 'A sealed prompt repeats')
    by_id = {e['id']: e for e in prompts}
    for key, answers in LAUNCHER_FIXED_ANSWERS.items():
        require(key in by_id and by_id[key]['answers'] == answers and not by_id[key]['optional'],
                'The prompt map does not run a review, then a draft, then quit')
    require('draft_question' in by_id and by_id['draft_question']['answers'] == [question],
            'The prompt map does not answer the draft question with the sealed question')
    require('folder' in by_id and by_id['folder']['answers'] == [LAUNCHER_WORKLOAD_TOKEN],
            'The prompt map does not answer the folder question with the sealed workload')
    files = manifest.get('project_files') or {}
    require(LAUNCHER_SCRIPT in files and any(n.startswith(LAUNCHER_WORKLOAD + '/') for n in files),
            'The project carries no launcher or no launcher workload')
    return value


def launcher_prompt_texts(sources):
    """Every text a prompt can be in the bound sources ({name: text}): each printf text of a
    shell script, each string constant of a Python file (adjacent literals joined, as Python
    joins them)."""
    import ast
    texts = set()
    for name, text in sources.items():
        if name.endswith('.sh'):
            texts.update(re.findall(r'printf "((?:[^"\\]|\\.)*)"', text))
        else:
            texts.update(n.value for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Constant) and isinstance(n.value, str))
    return texts


def launcher_prompt_error(prompts, sources):
    """None, or a one-line reason naming the first sealed prompt the bound launcher, wizard and
    pipeline do not print word for word, so a map can never wait on a prompt that is not there."""
    texts = launcher_prompt_texts(sources)
    for entry in prompts:
        if entry['prompt'] not in texts:
            return 'A sealed prompt is not printed by the bound launcher, wizard or pipeline: ' + entry['id']
    return None


class PromptMap:
    """The sealed answers, given in sealed order per prompt, and how many of each were used."""

    def __init__(self, prompts, substitutions=None):
        self.prompts = list(prompts)
        self.used = {p['id']: 0 for p in self.prompts}
        self.substitutions = dict(substitutions or {})

    def match(self, pending):
        """The sealed prompt the pending output (everything since the last answer) ends with, at
        the start of a line, the longest when several do; None otherwise."""
        tail = pending.rstrip(' \t')
        best = None
        for entry in self.prompts:
            text = entry['prompt'].rstrip(' \t')
            if text and tail.endswith(text):
                start = len(tail) - len(text)
                if (start == 0 or tail[start - 1] in '\r\n') and (best is None or len(text) > len(best['prompt'].rstrip(' \t'))):
                    best = entry
        return best

    def answer(self, entry):
        """The next sealed answer to `entry`, its substitutions applied, or None when its answers
        are used up (an optional prompt that repeats gives its last answer again)."""
        count = self.used[entry['id']]
        if count < len(entry['answers']):
            value = entry['answers'][count]
        elif entry['repeat_last']:
            value = entry['answers'][-1]
        else:
            return None
        self.used[entry['id']] += 1
        for token, replacement in self.substitutions.items():
            value = value.replace(token, replacement)
        return value

    def required_total(self):
        return sum(len(p['answers']) for p in self.prompts if not p['optional'])

    def required_given(self):
        return sum(min(self.used[p['id']], len(p['answers'])) for p in self.prompts if not p['optional'])

    def unused(self):
        """The ids of the required prompts whose sealed answers were not all given."""
        return [p['id'] for p in self.prompts if not p['optional'] and self.used[p['id']] != len(p['answers'])]


def last_segment(text):
    return re.split(r'[\r\n]', text)[-1].rstrip(' \t')


def session_idle(silent, idle_after):
    """True once the menu has printed nothing for `idle_after` seconds."""
    return silent >= idle_after


def stop_session(proc):
    """End the menu and everything it started: its own process group on Linux (it was started
    in a new session), the process tree on Windows (the checks)."""
    if proc.poll() is not None and os.name != 'nt':
        try:
            os.killpg(proc.pid, 15)
        except OSError:
            pass
        return
    try:
        if os.name == 'nt':
            import subprocess
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        else:
            os.killpg(proc.pid, 15)
            try:
                proc.wait(timeout=10)
            except Exception:
                os.killpg(proc.pid, 9)
    except OSError:
        pass


def drive_session(argv, cwd, env, prompts, deadline, on_answer=None, quiet=LAUNCHER_QUIET_SECONDS,
                  unknown_after=LAUNCHER_UNKNOWN_PROMPT_SECONDS, active=None, idle_after=LAUNCHER_IDLE_SECONDS):
    """Run `argv` once with pipes and answer each prompt only from `prompts` (a PromptMap).
    Returns the session record: exit code, why it stopped (None when it ended by itself), the
    unknown prompt's last line, every answer given (id, occurrence, seconds, and what
    `on_answer()` adds) and the whole output as bytes."""
    import subprocess
    extra = dict(creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) if os.name == 'nt' else dict(start_new_session=True)
    began = time.time()
    proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, **extra)
    if active is not None:
        active['proc'] = proc
    chunks, lock, last = [], threading.Lock(), [time.time()]

    def reader():
        while True:
            data = os.read(proc.stdout.fileno(), 65536)
            if not data:
                return
            with lock:
                chunks.append(data)
                last[0] = time.time()
    thread = threading.Thread(target=reader, name='launcher-session-reader', daemon=True)
    thread.start()
    steps, mark, stop, unknown, total = [], 0, None, None, prompts.required_total()
    while True:
        if proc.poll() is not None and not thread.is_alive():
            break
        now = time.time()
        if now >= deadline:
            stop = 'deadline'
            break
        with lock:
            data = b''.join(chunks)
            silent = now - last[0]
        pending = data[mark:].decode('utf-8', errors='replace')
        if pending and silent >= quiet and proc.poll() is None:
            entry = prompts.match(pending)
            if entry is not None:
                answer = prompts.answer(entry)
                if answer is None:
                    stop, unknown = 'answers_used_up', entry['id']
                    break
                try:
                    proc.stdin.write((answer + '\n').encode('utf-8'))
                    proc.stdin.flush()
                except OSError:
                    stop = 'input_closed'
                    break
                mark = len(data)
                step = dict(id=entry['id'], occurrence=prompts.used[entry['id']], answer=answer,
                            seconds=round(time.time() - began, 3))
                if on_answer is not None:
                    step.update(on_answer())
                steps.append(step)
                # PROGRESS-A: the controller tails this, a measured count of the sealed answers.
                print('[launcher] answered %s: %d of %d sealed answers to the required prompts given at %.0f s'
                      % (entry['id'], prompts.required_given(), total, time.time() - began), file=sys.stderr, flush=True)
                continue
            segment = last_segment(pending)
            if silent >= unknown_after and segment.endswith((':', '?')):
                stop, unknown = 'unknown_prompt', segment[-200:]
                break
        if session_idle(silent, idle_after) and proc.poll() is None:
            # Nothing printed for this long: a prompt the map cannot see (another line printed
            # after it) or a hung child; the session stops instead of spending the budget.
            stop, unknown = 'output_idle', last_segment(pending)[-200:] or None
            break
        time.sleep(0.2)
    if stop is not None:
        stop_session(proc)
    try:
        proc.stdin.close()
    except OSError:
        pass
    try:
        code = proc.wait(timeout=60)
    except Exception:
        stop_session(proc)
        code = proc.poll()
    thread.join(timeout=10)
    with lock:
        output = b''.join(chunks)
    return dict(exit_code=code, stop_reason=stop, unknown_prompt=unknown, steps=steps, used=dict(prompts.used),
                unused=prompts.unused(), required_answers=total, seconds=round(time.time() - began, 3), output=output)


def launcher_environment(environ, declaration, site, network, observer, tmp):
    """The children's environment: the runner's (already cleaned of every inherited SHIMMER_,
    HF_, TRANSFORMERS_ and credential variable) with the sealed child environment over it, the
    backend profile left to the menu's own question, the network-denying sitecustomize first on
    PYTHONPATH, and temporary files under the evidence."""
    env = {k: v for k, v in environ.items() if k not in ('SHIMMER_BACKEND_PROFILE', 'PYTHONPATH', 'VIRTUAL_ENV')}
    env.update(declaration['child_environment'])
    env.update({'PYTHONPATH': str(site), LAUNCHER_NETWORK_DIR_ENV: str(network), LAUNCHER_OBSERVER_ENV: str(observer),
                'TMPDIR': str(tmp)})
    return env


def launcher_venv(project, runner=None):
    """project/.venv as shimmer.sh expects it, made from the pinned runtime the runner runs in:
    a fresh environment with no pip whose .pth adds the runner's own site-packages, so the menu's
    runtime check passes and SHIMMER_SKIP_INSTALL needs no install."""
    import subprocess
    venv = Path(project)/'.venv'
    require(not venv.exists(), 'The menu environment already exists')
    run = runner or subprocess.run
    result = run([sys.executable, '-m', 'venv', '--without-pip', str(venv)], capture_output=True, timeout=300,
                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    require(result.returncode == 0, 'The menu environment could not be created')
    found = list(venv.glob('lib/python*/site-packages')) + list(venv.glob('Lib/site-packages'))
    require(len(found) == 1, 'The menu environment has no site-packages folder')
    (found[0]/'_shimmer_runtime.pth').write_text('\n'.join(runtime_site_paths()) + '\n', encoding='utf8')
    return venv


def runtime_site_paths():
    """The site-packages folders the runner's own interpreter imports from, in its order (the
    pinned runtime's; a runtime that also sees its system site sees it here too)."""
    import sysconfig
    found = [sysconfig.get_paths()['purelib'], sysconfig.get_paths()['platlib']]
    found += [p for p in sys.path if p and Path(p).name in ('site-packages', 'dist-packages')]
    return list(dict.fromkeys(str(Path(p)) for p in found if Path(p).is_dir()))


def launcher_shell():
    """The shell shimmer.sh is run with on the instance."""
    return 'bash'


def run_names(project):
    runs = Path(project)/'output'/'runs'
    return sorted(p.name for p in runs.iterdir() if p.is_dir()) if runs.is_dir() else []


def launcher_run_record(folder, task):
    """What one menu run left (counts and states, never text): its completion record, its
    telemetry's pipeline_start and pipeline_end, and the deliverable its task must write."""
    folder = Path(folder)
    try:
        completion = read(folder/'audit'/'run_completion.json')
    except (OSError, ValueError):
        completion = None
    events = []
    telemetry = folder/'logs'/'model_telemetry.jsonl'
    if telemetry.is_file():
        for line in telemetry.read_text(encoding='utf8').splitlines():
            try:
                events.append(json.loads(line).get('event'))
            except (ValueError, AttributeError):
                events.append(None)
    completion = completion if isinstance(completion, dict) else None
    return dict(name=folder.name, task=task,
                completion={k: completion.get(k) for k in ('state', 'reached_end', 'exit_code', 'semantic_complete', 'task')}
                if completion else None,
                telemetry=telemetry.is_file(), pipeline_starts=events.count('pipeline_start'),
                pipeline_ends=events.count('pipeline_end'),
                run_summary=(folder/'deliverables'/'_run_summary.md').is_file(),
                memos=len(list(folder.glob('deliverables/*/memo.md'))))


def launcher_network(folder):
    """The children's own network logs: how many processes recorded one, how many installed the
    denial in full, and every blocked attempt (loopback is allowed and counted apart)."""
    logs = sorted(Path(folder).glob('network_*.jsonl')) if Path(folder).is_dir() else []
    events, pipelines, pipelines_installed = [], 0, 0
    for path in logs:
        own = []
        for line in path.read_text(encoding='utf8', errors='replace').splitlines():
            try:
                own.append(json.loads(line))
            except ValueError:
                own.append({'event': 'unreadable'})
        events += own
        if any(e.get('event') == 'process_start' and e.get('program') == 'pipeline.py' for e in own):
            pipelines += 1
            pipelines_installed += any(e.get('event') == 'network_denial' and e.get('status') == 'installed' for e in own)
    denial = [e for e in events if e.get('event') == 'network_denial']
    return dict(logs=len(logs), processes=sum(e.get('event') == 'process_start' for e in events),
                pipelines=pipelines, pipelines_installed=pipelines_installed,
                denial_installed=sum(e.get('status') == 'installed' for e in denial),
                denial_sockets_only=sum(e.get('status') == 'sockets' for e in denial),
                denial_partial=sum(e.get('status') == 'partial' for e in denial),
                blocked=sum(e.get('event') == 'network_blocked' for e in events),
                blocked_kinds=sorted({str(e.get('network_kind')) for e in events if e.get('event') == 'network_blocked'}),
                loopback=sum(e.get('event') == 'local_ipc' for e in events))


def launcher_observation(evidence, project, session):
    """Move each menu run into evidence/launcher/<task>/ (the review's are the runs that existed
    when the draft was chosen, the draft's the rest) and read what the session left: the
    session record, each run's record, input/context after the draft, the children's network."""
    launcher = Path(evidence)/'launcher'
    session = session or {}
    at_draft = next((s.get('runs') for s in session.get('steps') or [] if s.get('id') == 'task' and s.get('answer') == 'D'), None)
    present = run_names(project)
    review = sorted(at_draft if at_draft is not None else present)
    groups = dict(review=[n for n in review if n in present], draft=[n for n in present if n not in review])
    runs = {}
    for task, names in groups.items():
        target = launcher/task
        target.mkdir(parents=True, exist_ok=True)
        runs[task] = []
        for name in names:
            shutil.move(str(Path(project)/'output'/'runs'/name), str(target/name))
            runs[task].append(launcher_run_record(target/name, task))
    context = Path(project)/'input'/'context'
    try:
        manifest = read(context/'_review_targets.json') if (context/'_review_targets.json').is_file() else None
    except (OSError, ValueError):
        manifest = {'source': 'unreadable'}
    return dict(session={k: session.get(k) for k in ('exit_code', 'stop_reason', 'unknown_prompt', 'used', 'unused',
                                                       'required_answers', 'seconds')},
                answers=len(session.get('steps') or []), runs=runs,
                context=dict(system_draft_manifest=isinstance(manifest, dict) and manifest.get('source') == 'system_draft',
                             draft_memo_files=len(list(context.glob('draft_memo_*'))) if context.is_dir() else 0),
                network=launcher_network(launcher/'network'))


def assess_launcher(observation):
    """An arm L entry's health, integrity only: the menu ended by itself with exit 0 after Q,
    every sealed answer given and no prompt outside the map; exactly one review run and one draft
    run, each reaching its end with exit 0 and one pipeline_start and one pipeline_end in its
    telemetry; the review's run summary and the draft's memo written; the draft's system manifest
    and memo cleared from input/context at its end; every child Python logging its network with
    at least its socket layer denied (the image's own python3, which has no HTTP clients, can
    deny no more), every pipeline process (one per run at least) with the denial installed in
    full, and no blocked attempt. A run whose semantic work is incomplete is
    reported as such and does not fail the arm: base models as shipped carry no quality claim."""
    reasons = []
    o = observation or {}
    session = o.get('session') or {}
    if session.get('stop_reason'):
        reasons.append('launcher_stopped:' + str(session['stop_reason']))
    if session.get('exit_code') != 0:
        reasons.append('launcher_exit_nonzero')
    for name in session.get('unused') or []:
        reasons.append('launcher_answer_not_given:' + name)
    runs = o.get('runs') or {}
    semantic = {}
    for task in LAUNCHER_TASKS:
        found = runs.get(task) or []
        if len(found) != 1:
            reasons.append('launcher_%s_runs:%d' % (task, len(found)))
            continue
        run = found[0]
        completion = run.get('completion') or {}
        if not (completion.get('reached_end') is True and completion.get('exit_code') == 0
                and completion.get('state') in ('completed', 'stopped')):
            reasons.append(task + '_not_completed')
        semantic[task] = completion.get('semantic_complete')
        if not (run.get('telemetry') and run.get('pipeline_starts') == 1 and run.get('pipeline_ends') == 1):
            reasons.append(task + '_telemetry')
        if task == 'review' and not run.get('run_summary'):
            reasons.append('review_run_summary_missing')
        if task == 'draft' and run.get('memos') != 1:
            reasons.append('draft_memo_missing')
    context = o.get('context') or {}
    if context.get('system_draft_manifest') or context.get('draft_memo_files'):
        reasons.append('draft_context_not_cleared')
    network = o.get('network') or {}
    if not network.get('logs') or ((network.get('denial_installed') or 0) + (network.get('denial_sockets_only') or 0)
                                   != network.get('processes')) \
            or network.get('pipelines_installed') != network.get('pipelines') \
            or (network.get('pipelines') or 0) < sum(len(runs.get(t) or []) for t in LAUNCHER_TASKS):
        reasons.append('launcher_network_denial_incomplete')
    if network.get('blocked'):
        reasons.append('launcher_network_attempts:%d' % network['blocked'])
    return {'execution_integrity_passed': not reasons, 'reasons': reasons, 'arm': 'L', 'launcher': o,
            'semantic_complete': semantic, 'failed_backend_attempts': None,
            'collection_and_teardown_pending': True, 'quality_claim': None}


def execute_launcher(base, manifest, project, evidence, rec, deadline):
    """The arm L entry after every guard execute() applies: the menu once, answered only from
    the sealed map, its children base and network-denied, then the arm-aware assessment."""
    import signal
    declaration = launcher_declaration(manifest)
    launcher = Path(evidence)/'launcher'
    folders = {name: launcher/name for name in ('network', 'site', 'tmp')}
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=False)
    (folders['site']/'sitecustomize.py').write_text(sitecustomize_source(), encoding='utf8')
    session, active = None, {}

    def stop_children():
        if active.get('proc') is not None:
            stop_session(active['proc'])
    STOP_HOOKS.append(stop_children)

    def terminated(signum, frame):
        stop_children()
        raise SystemExit(143)
    previous = signal.signal(signal.SIGTERM, terminated)
    try:
        error = launcher_prompt_error(declaration['prompts'],
                                      {n: (Path(project)/n).read_text(encoding='utf8') for n in LAUNCHER_PROMPT_SOURCES})
        require(error is None, error or '')
        launcher_venv(project)
        env = launcher_environment(os.environ, declaration, folders['site'], folders['network'], Path(base), folders['tmp'])
        prompts = PromptMap(declaration['prompts'], {LAUNCHER_WORKLOAD_TOKEN: str(Path(project)/LAUNCHER_WORKLOAD)})
        session = drive_session([launcher_shell(), str(Path(project)/LAUNCHER_SCRIPT)], project, env, prompts,
                                deadline - LAUNCHER_STOP_MARGIN_SECONDS, on_answer=lambda: dict(runs=run_names(project)),
                                active=active)
    except BaseException as exc:
        write(Path(evidence)/'terminal_error.json', failure_identity(exc, project))
    finally:
        signal.signal(signal.SIGTERM, previous)
        stop_children()
        rec.close()
        if session is not None:
            (launcher/'session_output.log').write_bytes(session['output'])
            write(launcher/'transcript.json', {k: v for k, v in session.items() if k != 'output'})
        observation = launcher_observation(evidence, project, session)
        result = assess(None, [], arm='L', launcher=observation)
        result['pipeline_exit_code'] = None
        write(Path(evidence)/'result.json', result)
    return 0 if result['execution_integrity_passed'] else 2


def execute(base):
    base = Path(base).resolve()
    manifest = verify(base)
    require(sys.platform == 'linux', 'Remote Linux execution only')
    permit = read(base/'operator_authorization.json')
    authorization(base, manifest, permit)
    require((base/'WATCHDOG_ARMED.json').is_file(), 'Independent operator watchdog required')
    watch = read(base/'WATCHDOG_ARMED.json')
    own = sha(base/'execution_manifest.json')
    # A batch session's watchdog names every bundle of the batch it guards.
    require((watch.get('execution_manifest_sha256') == own or own in (watch.get('batch_manifest_sha256s') or [])) and
            watch.get('instance_id') == permit.get('instance_id') and
            0 <= time.time()-watch.get('heartbeat_epoch', 0) < 30, 'Watchdog not current')
    with (base/'RUN_CLAIMED').open('x', encoding='utf8') as stream:
        stream.write(str(time.time()))
    deadline = (permit['active_start_epoch'] + manifest['hard_ceiling_usd']/permit['hourly_rate']*3600
                - manifest['workload_stop_reserve_seconds'])
    def budget_stop():
        time.sleep(max(0, deadline-time.time()))
        write(base/'BUDGET_WORKLOAD_STOP.json', {'epoch':time.time(), 'completed':False})
        # An arm L session's children end with the runner (STOP_HOOKS is empty otherwise).
        for hook in list(STOP_HOOKS):
            try:
                hook()
            except Exception:
                pass
        # A blocked CUDA call must not outlive the collection reserve. Raw
        # telemetry is append-and-close; this is never reported as completion.
        os._exit(124)
    threading.Thread(target=budget_stop, name='ordinary-budget-stop', daemon=True).start()
    project = base/'project'
    for key in list(os.environ):
        if key.startswith(('SHIMMER_', 'HF_', 'TRANSFORMERS_')) or key.endswith(('API_KEY','TOKEN','SECRET','PASSWORD')):
            os.environ.pop(key, None)
    os.environ.update(manifest['environment'])
    os.environ.update(HF_HOME=str(base/'hf_cache'), HF_HUB_CACHE=str(base/'hf_cache/hub'),
                      PYTHONDONTWRITEBYTECODE='1')
    # Fresh cache refs are bound to the exact snapshots; no ambient cache used.
    cache = base/'hf_cache/hub'
    for model in manifest['models']:
        directory = cache/('models--'+model['model_id'].replace('/','--'))
        admit_cache_ref(directory, model)
        snapshot = directory/'snapshots'/model['revision']
        require({p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*') if p.is_file()} == set(model['files']), 'Unsealed cache files')
        for name, entry in model['files'].items():
            require(sha(snapshot/name) == entry['sha256'], 'Model cache hash mismatch')
    sys.path[:0] = [str(project/'scripts'), str(project/'tools')]
    os.chdir(project)
    # Verify all pinned packages before importing pipeline/model libraries.
    installed_runtime(manifest)
    import final_models
    final_models.admit_ordinary()
    import psutil
    write(base/'hardware_admission.json',hardware_admission(base,sys.modules['torch'],psutil,
                                                           selected_candidate(manifest, permit)))
    from cloud_run_observer import Recorder, deny_network
    evidence = base/'evidence'
    evidence.mkdir(exist_ok=False)
    rec = Recorder(evidence/'network.jsonl')
    deny_network(rec)
    # Open item 37: disk in use before, during and after the workload, in the evidence.
    disk = DiskSampler(base, evidence/DISK_USAGE).start()
    if arm_of(manifest) == 'B1':
        # Every guard above holds for B1 as for B3 (authorization with its arm, RUN_CLAIMED,
        # the budget stop thread, the sealed cache, the pinned runtime, the network denial).
        try:
            return execute_b1(base, manifest, project, evidence, rec)
        finally:
            disk.stop()
    if arm_of(manifest) == 'L':
        # Every guard above holds for arm L too; the menu then runs once, in its own session.
        try:
            return execute_launcher(base, manifest, project, evidence, rec, deadline)
        finally:
            disk.stop()
    # Every inherited runtime flag was removed; only the manifest flags survive.
    argv = list(argv_for(manifest))
    if '--topology-config' in argv:
        argv[argv.index('--topology-config')+1] = str(base/'topology.json')
    if '--multi-round-manifest' in argv:
        argv[argv.index('--multi-round-manifest')+1] = str(base/CASE_MANIFEST)
    argv += ['--output-dir', str(evidence/'run')]
    code = 1
    try:
        import pipeline
        code = pipeline.main(argv)
    except BaseException as exc:
        write(evidence/'terminal_error.json', failure_identity(exc, project))
    finally:
        disk.stop()
        rec.close()
        import model_telemetry, run_completion
        # The runtime may rename its output folder at completion.
        directories = [p.parent.parent for p in evidence.rglob('audit/run_completion.json')]
        if len(directories) == 1:
            directory = directories[0]
            raw = [json.loads(line) for line in (directory/'logs/model_telemetry.jsonl').read_text(encoding='utf8').splitlines() if line]
            completion = run_completion.read(directory)
            saved = None
            if manifest['multi_round']:
                import multi_round
                saved = multi_round.read_saved(directory, (completion or {}).get('run_id') or directory.name)
            result = assess(completion, raw, saved)
            model_telemetry.recompute(directory)
        else:
            result = assess(None, [], {} if manifest['multi_round'] else None)
        result['pipeline_exit_code'] = code
        write(evidence/'result.json', result)
    return 0 if code == 0 and result['execution_integrity_passed'] else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        raise SystemExit(execute(args.bundle))
    verify(args.bundle)
    print('Sealed project verified; no execution authorized or performed')
