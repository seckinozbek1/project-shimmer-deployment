"""Prospective Producer-only execution mechanics; no model loader or CLI executor.

Local tests use stand-ins, never Qwen/Phi generation. Future execution requires a
separately bound authorization and the frozen control gate in protocol.json.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import weakref
from config_state import ConfigSnapshot, owned_dict


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def authorize(permit, protocol, release_hash):
    require(permit.get('operator_authorized') is True, 'New explicit authorization required')
    expected = dict(experiment='second-tuning-eval-runtime-v2_1', action='producer-checkpoint120-evaluation-only',
                    role='producer', split='canonical', checkpoint=120,
                    runtime_release_sha256=release_hash,
                    protocol_sha256=digest(protocol), adapter_sha256=protocol['adapter']['files']['adapter_model.safetensors'])
    for key, value in expected.items():
        require(permit.get(key) == value, 'Authorization mismatch: ' + key)
    require(not permit.get('protected_access') and not permit.get('training'), 'Forbidden authorization scope')
    return expected


def validate_records(records, protocol, full=True):
    expected = protocol['dev_ids'] if full else protocol['control_ids']
    require([x['example_id'] for x in records] == expected, 'Wrong DEV population/order')
    bindings = protocol['prompt_bindings']
    for row in records:
        require(row['role'] == 'producer' and row['split'] == 'canonical', 'Producer canonical only')
        b = bindings[row['example_id']]
        require(hashlib.sha256(row['prompt'].encode()).hexdigest() == b['prompt_sha256'], 'Prompt changed')
        require(digest(row['input_ids']) == b['input_ids_sha256'], 'Prompt token IDs changed')
        require(row['attention_mask'] == [1] * len(row['input_ids']), 'Unpadded single-example attention mask required')


def validate_generation(settings, protocol):
    require(settings == protocol['generation_kwargs'], 'Generation settings changed')
    require(settings['use_cache'] is True and settings['do_sample'] is False and settings['num_beams'] == 1, 'Frozen greedy cached task required')
    require(settings['max_new_tokens'] == 288, 'Frozen cap changed')
    require(not settings.get('return_dict_in_generate', False) and not settings.get('output_scores', False), 'Extra generation outputs forbidden')


def parameter_state(model):
    return [(id(p), str(p.dtype), str(p.device), p.requires_grad, getattr(p, '_version', None),
             id(getattr(p, 'grad', None)), getattr(getattr(p, 'grad', None), '_version', None)) for p in model.parameters()]


_MISSING = object()
_PREFLIGHTS = weakref.WeakKeyDictionary()


def owned_configuration_fields(model):
    result = []
    for index, module in enumerate(model.modules()):
        state = owned_dict(module)
        for name in ('config', 'generation_config'):
            if name in state:
                result.append((module, name, state[name], index))
    return result


@contextmanager
def evaluation_state(model, torch_api):
    """Type-safe exact restoration; no tensor copy, cast or weight update."""
    modules = list(model.modules())
    training = [(m, m.training) for m in modules]
    names = ('config', 'generation_config', 'gradient_checkpointing',
             '_gradient_checkpointing_func', 'active_adapter', '_active_adapter', 'active_adapters')
    owned = [(m, name, owned_dict(m).get(name, _MISSING)) for m in modules for name in names]
    fields = owned_configuration_fields(model)
    snapshots = ConfigSnapshot([value for _, _, value, _ in fields])
    adapter_roots = [value for _, name, value in owned
                     if name in ('active_adapter', '_active_adapter', 'active_adapters') and value is not _MISSING]
    adapters_snapshot = ConfigSnapshot(adapter_roots)
    adapters = deepcopy(getattr(model, 'active_adapters', None))
    parameters = list(model.parameters())
    parameter_before = parameter_state(model)
    parameter_flags = [(p, p.requires_grad, getattr(p, 'grad', _MISSING)) for p in parameters]
    try:
        model.eval()
        snapshots.enable_cache()
        require(all(not m.training for m in modules), 'Eval transition failed')
        with torch_api.inference_mode():
            require(not torch_api.is_grad_enabled(), 'Autograd remains enabled')
            yield
    finally:
        # Independently attempt each restoration even if one object was damaged.
        errors = []
        def restore(action):
            try: action()
            except BaseException as exc: errors.append(exc)
        restore(snapshots.restore)
        restore(adapters_snapshot.restore)
        for module, name, prior in owned:
            def field_restore(module=module, name=name, prior=prior):
                if prior is _MISSING: owned_dict(module).pop(name, None)
                else: owned_dict(module)[name] = prior
            restore(field_restore)
        for module, prior in training:
            restore(lambda module=module, prior=prior: setattr(module, 'training', prior))
        for parameter, flag, grad in parameter_flags:
            def parameter_restore(parameter=parameter, flag=flag, grad=grad):
                if parameter.requires_grad != flag: parameter.requires_grad = flag
                if grad is not _MISSING and getattr(parameter, 'grad', None) is not grad: parameter.grad = grad
            restore(parameter_restore)
        require(not errors, 'State restoration encountered unsupported mutation: ' + (type(errors[0]).__name__ if errors else ''))
        require(all(m.training == prior for m, prior in training), 'Training flags not restored')
        require(all(owned_dict(m).get(name, _MISSING) is prior for m, name, prior in owned), 'Owned attribute identity not restored')
        snapshots.verify(); adapters_snapshot.verify()
        require(parameter_state(model) == parameter_before, 'Parameter state/version changed during evaluation')
        require(getattr(model, 'active_adapters', None) == adapters, 'Active adapter changed')


def real_runtime_context_preflight(model, torch_api):
    """Mandatory real-object entry/exit probe; no generation call is made here.

    Fresh loaded pinned model/adapter required by the future authorized loader.
    A failed attempt cannot be retried on the same model in this process.
    """
    require(model not in _PREFLIGHTS, 'No repeated REAL_RUNTIME_CONTEXT_PREFLIGHT')
    _PREFLIGHTS[model] = dict(passed=False)
    fields = owned_configuration_fields(model)
    snapshot = ConfigSnapshot([value for _, _, value, _ in fields])
    inventory = [dict(module_index=index, attribute=name, **info)
                 for (_, name, _, index), info in zip(fields, snapshot.inventory())]
    with evaluation_state(model, torch_api):
        require(all(not module.training for module in model.modules()), 'Preflight eval state failed')
        require(not torch_api.is_grad_enabled(), 'Preflight grad state failed')
    snapshot.verify()
    receipt = dict(name='REAL_RUNTIME_CONTEXT_PREFLIGHT', passed=True,
                   owned_config_fields=inventory, state_restored=True, generation_calls=0)
    _PREFLIGHTS[model] = receipt
    return deepcopy(receipt)


def require_context_preflight(model):
    require(_PREFLIGHTS.get(model, {}).get('passed') is True,
            'REAL_RUNTIME_CONTEXT_PREFLIGHT required before generation')


class DurableRows:
    """One flush/fsync per completed example, outside the generation timer."""
    def __init__(self, path):
        self.path = Path(path)
        self.stream = self.path.open('x', encoding='utf8', newline='\n')

    def append(self, value):
        self.stream.write(json.dumps(value, ensure_ascii=False) + '\n')
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def close(self):
        self.stream.close()


def evaluate_records(model, tokenizer, torch_api, records, protocol, sink, score,
                     *, reference_trace=None, clock=time.perf_counter):
    """Low-level mechanism for the future authorized harness; stand-ins in tests.

    Never loads a model, accesses a provider, selects a checkpoint or consumes a
    protected receipt. The harness must validate authorization and control receipt.
    Full and control populations are validated separately by that harness.
    """
    require_context_preflight(model)
    validate_generation(protocol['generation_kwargs'], protocol)
    require(sys.gettrace() is None and sys.getprofile() is None, 'Ambient tracing/profiling prohibited')
    results = []
    with evaluation_state(model, torch_api):
        for row in records:
            require(row['role'] == 'producer' and row['split'] == 'canonical', 'Forbidden role/split')
            # Frozen prepared token IDs, no prompt construction or tokenizer reload here.
            transfer_start = clock()
            inputs = {k: torch_api.tensor([row[k]], dtype=torch_api.long).to(model.device) for k in ('input_ids', 'attention_mask')}
            transfer_wall = clock() - transfer_start
            memory_before = {name: int(getattr(torch_api.cuda, name)()) for name in ('memory_allocated', 'memory_reserved', 'max_memory_allocated', 'max_memory_reserved')}
            start = clock()
            torch_api.cuda.synchronize()
            try:
                if reference_trace is not None:
                    sys.settrace(reference_trace)
                output = model.generate(**inputs, **deepcopy(protocol['generation_kwargs']))
                torch_api.cuda.synchronize()
            finally:
                if reference_trace is not None:
                    sys.settrace(None)
            generation_wall = clock() - start
            memory_after = {name: int(getattr(torch_api.cuda, name)()) for name in ('memory_allocated', 'memory_reserved', 'max_memory_allocated', 'max_memory_reserved')}
            ids = output[0, len(row['input_ids']):].tolist()
            terminal = bool(ids and ids[-1] in protocol['generation_kwargs']['eos_token_id'])
            raw = tokenizer.decode(ids, skip_special_tokens=True)
            evidence = dict(example_id=row['example_id'], role='producer', split='canonical',
                            runtime='historical-observer-reference' if reference_trace is not None else 'second-tuning-eval-runtime-v2_1',
                            checkpoint=120, adapter=protocol['adapter'], prompt_sha256=hashlib.sha256(row['prompt'].encode()).hexdigest(),
                            input_ids_sha256=digest(row['input_ids']), output_token_ids=ids,
                            raw_output=raw, raw_output_with_special_tokens=tokenizer.decode(ids, skip_special_tokens=False),
                            stop_reason='eos' if terminal else 'length', truncated=not terminal,
                            output_tokens=len(ids), generation_seconds=generation_wall,
                            tensor_preparation_seconds=transfer_wall,
                            cuda_memory_before=memory_before, cuda_memory_after=memory_after,
                            memory_observation='Per-example boundaries and CUDA high-water counters; independent process samples GPU/RSS/CPU each second',
                            ttft_seconds=None, decode_only_seconds=None)
            sink.append(evidence)  # Raw evidence is durable before semantic scoring.
            evidence['metrics'] = score(row['example_id'], raw, not terminal)
            results.append(evidence)
            del inputs, output
    return results


def control_gate(reference, optimized, protocol):
    require([x['example_id'] for x in reference] == protocol['control_ids'], 'Incomplete reference control')
    require([x['example_id'] for x in optimized] == protocol['control_ids'], 'Incomplete optimized control')
    same_tokens = all(a['output_token_ids'] == b['output_token_ids'] for a, b in zip(reference, optimized))
    same_metrics = all(a['metrics'] == b['metrics'] for a, b in zip(reference, optimized))
    same_prompts = all(a['prompt_sha256'] == b['prompt_sha256'] and a['input_ids_sha256'] == b['input_ids_sha256'] for a, b in zip(reference, optimized))
    for row in reference + optimized:
        binding = protocol['prompt_bindings'][row['example_id']]
        require(row['prompt_sha256'] == binding['prompt_sha256'] and row['input_ids_sha256'] == binding['input_ids_sha256'], 'Unbound control prompt')
        require(row['adapter'] == protocol['adapter'] and row['checkpoint'] == 120, 'Unbound control adapter')
    def rate(rows):
        seconds = sum(x['generation_seconds'] for x in rows)
        require(seconds > 0 and all(math.isfinite(x['generation_seconds']) and x['generation_seconds'] > 0 for x in rows), 'Invalid timing evidence')
        tokens = sum(len(x['output_token_ids']) for x in rows)
        require(tokens > 0, 'Empty control outputs')
        return tokens / seconds
    baseline, candidate = rate(reference), rate(optimized)
    passed = same_tokens and same_metrics and same_prompts and candidate >= protocol['speed_gate']['minimum_tokens_per_second'] and candidate >= protocol['speed_gate']['minimum_paired_speedup'] * baseline
    return dict(pass_gate=passed, token_identity=same_tokens, metric_identity=same_metrics,
                prompt_identity=same_prompts, reference_tokens_per_second=baseline,
                optimized_tokens_per_second=candidate, paired_speedup=candidate / baseline,
                no_go_action='Stop and preserve evidence; no full DEV, protocol changes, rescue or retraining')


def cache_effect_gate(observations):
    """Validate actual future first-two-forward observations; no mocked admission."""
    for mode in ('reference', 'optimized'):
        rows = observations.get(mode, [])
        require(len(rows) == 2, 'Missing first-two-forward cache evidence')
        first, second = rows
        require(all(x['use_cache'] is True and x['training'] is False and x['grad_enabled'] is False for x in rows), 'Wrong generation state')
        require(first['input_length'] > 1 and first['returned_cache_length'] == first['input_length'], 'Prefill cache not created')
        require(second['input_length'] == 1 and second['incoming_cache_length'] == first['returned_cache_length'], 'Incremental cached decode missing')
        require(second['returned_cache_length'] == first['returned_cache_length'] + 1, 'Cache did not advance')
    return True


@contextmanager
def cache_probe(model, torch_api):
    """Prospective separate preflight only; never enabled during speed trials.

    Hooks observe pinned Qwen2Model below PEFT and the causal LM. No cache is
    invented; an absent cache, wrong input length or training flag fails closed.
    """
    target = model.get_base_model().model
    observations = []
    pending = []
    def before(module, args, kwargs):
        if len(observations) >= 2:
            return
        ids = kwargs.get('input_ids')
        if ids is None and args:
            ids = args[0]
        prior = kwargs.get('past_key_values')
        pending.append(dict(input_length=int(ids.shape[-1]), use_cache=kwargs.get('use_cache'),
                            training=module.training, grad_enabled=torch_api.is_grad_enabled(),
                            incoming_cache_length=0 if prior is None else int(prior.get_seq_length())))
    def after(module, args, kwargs, output):
        if len(observations) >= 2:
            return
        row = pending.pop(0)
        cache = getattr(output, 'past_key_values', None)
        row['returned_cache_length'] = 0 if cache is None else int(cache.get_seq_length())
        observations.append(row)
    pre = target.register_forward_pre_hook(before, with_kwargs=True)
    try:
        post = target.register_forward_hook(after, with_kwargs=True)
        try:
            yield observations
        finally:
            post.remove()
    finally:
        pre.remove()


class EvaluationSession:
    """Future harness admission, testable without loading weights or a provider."""
    def __init__(self, permit, protocol, release_hash):
        authorize(permit, protocol, release_hash)
        self.protocol = deepcopy(protocol)
        self.protocol_hash = digest(protocol)
        self.context_model = None
        self.context_attempted = False
        self.cache_verified = False
        self.cache_attempted = False
        self.control_attempted = False
        self.control_receipt = None
        self.full_used = False

    def preflight_context(self, model, torch_api):
        require(not self.context_attempted, 'No repeated context preflight or rescue')
        self.context_attempted = True
        receipt = real_runtime_context_preflight(model, torch_api)
        self.context_model = model
        return receipt

    def admit_cache(self, observations):
        require(self.context_model is not None, 'Context preflight required before cache admission')
        require_context_preflight(self.context_model)
        require(not self.cache_attempted, 'No repeated cache preflight or rescue')
        self.cache_attempted = True
        self.cache_verified = cache_effect_gate(observations)

    def admit_control(self, reference, optimized):
        require(self.cache_verified, 'Cache preflight required before speed control')
        require(not self.control_attempted, 'No repeated control or threshold adaptation')
        self.control_attempted = True
        self.control_receipt = control_gate(reference, optimized, self.protocol)
        return deepcopy(self.control_receipt)

    def complete_dev(self, model, tokenizer, torch_api, records, sink, score):
        require(model is self.context_model, 'Preflight must bind the same resident model')
        require_context_preflight(model)
        require(self.cache_verified and self.control_receipt and self.control_receipt['pass_gate'], 'Control NO_GO or absent')
        require(not self.full_used, 'Full evaluation already attempted; no automatic resume')
        require(digest(self.protocol) == self.protocol_hash, 'Prospective protocol changed')
        validate_records(records, self.protocol, full=True)
        self.full_used = True
        results = evaluate_records(model, tokenizer, torch_api, records, self.protocol, sink, score)
        require(len(results) == 60, 'Incomplete new evaluation')
        return results
