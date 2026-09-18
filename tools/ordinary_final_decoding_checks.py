"""No-generation decoding gate: every local generate site, every pinned local family.

torch and transformers are imported for the real logits-processor construction
only. No weights load (the gate runner denies model loading and the network).
For each family the pinned generation_config.json is read from the local Hub
cache and reported; the kwargs the live call site hands generate() are captured
with a recording stand-in model; transformers' own _get_logits_processor builds
the chain a first sampling step would run from the checkpoint's config plus those
kwargs; the chain is applied to random logits with torch.cumsum instrumented and,
when CUDA is present, under torch.use_deterministic_algorithms(True), the mode
final_models.verify_runtime sets. The checkpoint's raw config runs through the
same instrument as a positive control, so the instrument is proven live wherever
the raw config samples with top-p.
"""
import contextlib
import copy
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts')]
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import torch
import transformers
from transformers import GenerationConfig
from transformers.generation.logits_process import LogitsProcessorList, RepetitionPenaltyLogitsProcessor
from transformers.generation.utils import GenerationMixin
import agent_wrapper
import decoding_policy
import final_models

HUB = Path(os.environ.get('HF_HUB_CACHE') or (Path.home() / '.cache/huggingface/hub'))
REPORTED = ('do_sample', 'temperature', 'top_k', 'top_p', 'repetition_penalty')
REPORT = {}
BUDGET = 16
PROBE_LENGTH = 8
PROBE_VOCAB = 4096


def registry_model(agent):
    value = json.loads((ROOT / 'config/agent_registry.json').read_text(encoding='utf8'))
    agents = value.get('agents', value)
    entry = agents[agent] if isinstance(agents, dict) else next(a for a in agents if a.get('name') == agent)
    return entry['model']


def families():
    """The three pinned local families and the site each one is generated through."""
    spec = json.loads((ROOT / 'config/final_models.json').read_text(encoding='utf8'))
    rows = []
    for role, backend in (('producer', 'local_producer'), ('auditor', 'local_auditor')):
        rows.append(dict(family=role, backend=backend, site='agent_wrapper.call_local', model_id=spec[role]['model_id'],
                         revision=spec[role]['revision'],
                         pinned_sha256=spec[role]['base_hashes']['generation_config.json']))
    redactor = registry_model('REDACTOR')
    ref = HUB / ('models--' + redactor.replace('/', '--')) / 'refs/main'
    rows.append(dict(family='redactor', backend='qwen_local', site='agent_wrapper.call_qwen', model_id=redactor,
                     revision=ref.read_text(encoding='ascii').strip() if ref.is_file() else None,
                     pinned_sha256=None))
    return rows


def snapshot(row):
    return HUB / ('models--' + row['model_id'].replace('/', '--')) / 'snapshots' / str(row['revision'])


def expected_kwargs(backend):
    """What the declaration and the protocol files say, read directly (never through decoding_policy)."""
    declared = json.loads((ROOT / 'config/decoding_policy.json').read_text(encoding='utf8'))
    entry = declared['backends'][backend]
    if entry['status'] == 'restored':
        recorded = json.loads((ROOT / entry['protocol']).read_bytes().replace(b'\r\n', b'\n').decode('utf8'))[entry['field']]
        return {k: v for k, v in recorded.items() if k not in declared['evaluation_only_keys']}
    return dict(entry['policy'])


class Inputs(dict):
    def to(self, device):
        return self


class Tokenizer:
    chat_template = 'configured'

    def apply_chat_template(self, messages, **kw):
        return 'TEMPLATED'

    def __call__(self, prompt, **kw):
        return Inputs(input_ids=SimpleNamespace(shape=(1, 3)))

    def decode(self, ids, **kw):
        return '{}'


class Output:
    def __init__(self, ids):
        self.ids, self.shape = list(ids), (1, len(ids))

    def __getitem__(self, key):
        return self.ids


def site_kwargs(row, mode='base'):
    """The kwargs the live call site hands generate(), captured with a recording stand-in model."""
    calls = []

    def generate(**kw):
        calls.append(dict(kw))
        return Output([1, 2, 3, 4])
    model = SimpleNamespace(device='cpu', generation_config=SimpleNamespace(eos_token_id=[4]), generate=generate,
                            _shimmer_identity=dict(model_mode='final', adapter_checkpoint=168))
    w = object.__new__(agent_wrapper.AgentWrapper)
    w.backend, w.name, w.run_context, w.cost_tracker = row['backend'], 'PROBE', None, None
    w.model, w._optimized_semantics = row['model_id'], True
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, SHIMMER_MODEL_MODE=mode))
        if mode == 'final':
            stack.enter_context(patch.object(final_models, 'resident', return_value=(Tokenizer(), model)))
            stack.enter_context(patch.object(agent_wrapper, '_load_qwen',
                                             side_effect=AssertionError('base loader forbidden in final mode')))
        else:
            stack.enter_context(patch.object(agent_wrapper, '_load_qwen', return_value=(Tokenizer(), model)))
        if row['site'].endswith('call_qwen'):
            result = w.call_qwen('probe', max_new_tokens=BUDGET)
        else:
            result = w.call_local('probe', max_new_tokens=BUDGET)
    assert result.ok and len(calls) == 1, 'stand-in site call failed: ' + str(result.error)
    kw = calls[0]
    kw.pop('input_ids')
    return kw


def build_chain(snapshot_dir, kwargs, device):
    """(raw generation config, effective config, processor chain) exactly as generate() would build them."""
    raw = GenerationConfig.from_pretrained(str(snapshot_dir), local_files_only=True)
    cfg = copy.deepcopy(raw)
    unused = cfg.update(**kwargs)  # generate(): kwargs override the model's generation config
    assert not unused, unused
    config = transformers.AutoConfig.from_pretrained(str(snapshot_dir), local_files_only=True)

    class StandIn(GenerationMixin):
        pass
    stand = StandIn()
    stand.config, stand.generation_config = config, cfg
    stand.device, stand.main_input_name = torch.device(device), 'input_ids'
    GenerationMixin._prepare_special_tokens(stand, cfg, True, device=device)
    processors = GenerationMixin._get_logits_processor(
        stand, generation_config=cfg, input_ids_seq_length=PROBE_LENGTH, encoder_input_ids=None,
        prefix_allowed_tokens_fn=None, logits_processor=LogitsProcessorList(), device=device, model_kwargs={})
    return raw, cfg, processors


@contextlib.contextmanager
def cumsum_recorder():
    """Record every cumsum call by dtype and device; floating-point CUDA cumsum is the op strict determinism rejects."""
    calls = []
    method, function = torch.Tensor.cumsum, torch.cumsum

    def record(tensor):
        calls.append(dict(dtype=str(tensor.dtype), device=tensor.device.type,
                          floating=bool(tensor.is_floating_point() or tensor.is_complex())))

    def patched_method(self, *args, **kwargs):
        record(self)
        return method(self, *args, **kwargs)

    def patched_function(tensor, *args, **kwargs):
        record(tensor)
        return function(tensor, *args, **kwargs)
    torch.Tensor.cumsum, torch.cumsum = patched_method, patched_function
    try:
        yield calls
    finally:
        torch.Tensor.cumsum, torch.cumsum = method, function


def apply(processors, device, seed=0):
    generator = torch.Generator().manual_seed(seed)
    scores = torch.randn(1, PROBE_VOCAB, generator=generator).to(device)
    input_ids = torch.randint(0, PROBE_VOCAB, (1, PROBE_LENGTH), generator=generator).to(device)
    return processors(input_ids, scores)


@contextlib.contextmanager
def strict_determinism():
    """The mode final_models.verify_runtime sets, restored afterwards."""
    previous = torch.are_deterministic_algorithms_enabled()
    warn = torch.is_deterministic_algorithms_warn_only_enabled()
    torch.use_deterministic_algorithms(True)
    try:
        yield
    finally:
        torch.use_deterministic_algorithms(previous, warn_only=warn)


class DecodingFamilyChecks(unittest.TestCase):
    def family_check(self, name):
        row = next(r for r in families() if r['family'] == name)
        folder = snapshot(row)
        self.assertTrue(folder.is_dir(), 'cached snapshot missing: %s' % folder)
        raw_bytes = (folder / 'generation_config.json').read_bytes()
        sha = hashlib.sha256(raw_bytes).hexdigest()
        if row['pinned_sha256']:
            self.assertEqual(sha, row['pinned_sha256'])
        raw_values = json.loads(raw_bytes.decode('utf8'))
        report = dict(row, generation_config_sha256=sha, generation_config={k: raw_values.get(k) for k in REPORTED},
                      raw_eos_token_id=raw_values.get('eos_token_id'), raw_pad_token_id=raw_values.get('pad_token_id'))
        REPORT[name] = report
        expected = expected_kwargs(row['backend'])
        kw = site_kwargs(row)
        if name == 'producer':
            self.assertEqual(site_kwargs(row, 'final'), kw)  # the final loader branch hands over the same kwargs
        self.assertEqual(kw.pop('max_new_tokens'), BUDGET)  # the pipeline's budget, not the evaluation cap
        self.assertEqual(kw, expected)
        report.update(site_kwargs=kw, policy_status=decoding_policy.policy(row['backend'])['status'])
        raw, cfg, processors = build_chain(folder, dict(kw, max_new_tokens=BUDGET), 'cpu')
        self.assertIs(cfg.do_sample, False)
        self.assertEqual(cfg.num_beams, 1)
        self.assertEqual(cfg.eos_token_id, expected.get('eos_token_id', raw.eos_token_id))
        self.assertEqual(cfg.pad_token_id, expected.get('pad_token_id', raw.pad_token_id))
        for key in ('repetition_penalty', 'temperature', 'top_k', 'top_p'):
            self.assertEqual(getattr(cfg, key), getattr(raw, key), key)  # untouched, exactly as during evaluation
        if raw.repetition_penalty not in (None, 1.0):
            self.assertTrue(any(isinstance(p, RepetitionPenaltyLogitsProcessor) for p in processors))
        report.update(effective=dict(do_sample=cfg.do_sample, num_beams=cfg.num_beams, use_cache=cfg.use_cache,
                                     eos_token_id=cfg.eos_token_id, pad_token_id=cfg.pad_token_id,
                                     repetition_penalty=cfg.repetition_penalty),
                      policy_chain=[type(p).__name__ for p in processors])
        with cumsum_recorder() as calls:
            apply(processors, 'cpu')
        floating = [c for c in calls if c['floating']]
        self.assertEqual(floating, [], 'floating-point cumsum in the policy chain')
        report['policy_chain_float_cumsum'] = len(floating)
        # Positive control: the checkpoint's raw config through the same instrument.
        _, raw_cfg, raw_processors = build_chain(folder, dict(max_new_tokens=BUDGET), 'cpu')
        with cumsum_recorder() as calls:
            apply(raw_processors, 'cpu')
        raw_floating = [c for c in calls if c['floating']]
        samples = bool(raw_cfg.do_sample) and raw_cfg.top_p is not None and raw_cfg.top_p < 1.0
        report.update(raw_chain=[type(p).__name__ for p in raw_processors], raw_chain_float_cumsum=len(raw_floating),
                      raw_config_samples_with_top_p=samples)
        if samples:
            self.assertTrue(raw_floating, 'instrument did not observe the raw chain')
        if torch.cuda.is_available():
            _, _, cuda_processors = build_chain(folder, dict(kw, max_new_tokens=BUDGET), 'cuda:0')
            with strict_determinism():
                apply(cuda_processors, 'cuda:0')
                if samples:
                    _, _, raw_cuda = build_chain(folder, dict(max_new_tokens=BUDGET), 'cuda:0')
                    with self.assertRaisesRegex(RuntimeError, 'cumsum_cuda_kernel'):
                        apply(raw_cuda, 'cuda:0')
            report['cuda_strict_determinism'] = 'policy chain passed' + (
                '; raw chain raised cumsum_cuda_kernel' if samples else '; raw chain does not sample')
        else:
            report['cuda_strict_determinism'] = 'unavailable on this host; the CPU instrument stands'

    def test_producer_family(self):
        self.family_check('producer')

    def test_auditor_family(self):
        self.family_check('auditor')

    def test_redactor_family(self):
        self.family_check('redactor')


if __name__ == '__main__':
    unittest.main(verbosity=2)
