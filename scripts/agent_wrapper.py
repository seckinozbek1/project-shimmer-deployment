"""Base agent wrapper.

API key loading via .env_path, Claude/GPT/Qwen dispatch, contract enforcement,
bus posting with mandatory constitution_check, cost tracker hook.

The agent registry (config/agent_registry.json) is the SOLE source of each
agent's model: `spec["backend"]` selects the family (cross-family audit, LAW-III)
and `spec["model"]` selects the exact model id. The key layer (.env_path ->
config.py) provides API keys ONLY; it never sets or overrides a model.
"""

from __future__ import annotations

import gc
import importlib
import importlib.util
import json
import os
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import call_evidence
import agent_activation
import agent_briefs
import run_options
import generation_observation
from bus_reader import (_estimate_tokens, assemble_context,
                        begin_truncation_capture, end_truncation_capture)
from constitution import CheckResult, Constitution
from cost_tracker import CostTracker
from message_bus import MessageBus
from shimmer_logging import get_logger, log_event

# productization STEP 7: structured JSON-lines logging for the wrapper's own
# diagnostics (stderr, same stream as before). Module-level so every call site
# shares one logger, exactly as pipeline.py does.
_LOG = get_logger("shimmer.agent")


# Throttle concurrent GPT calls — at most 2 in flight at once. The 30K
# TPM cap on gpt-4o is best avoided by serializing more aggressively than
# the asyncio task graph would otherwise.
_GPT_SEMAPHORE = threading.Semaphore(2)

# Shared resident local-model cache (qwen_local). A 4-bit 7B is several GB
# resident; loading a fresh copy per qwen_local call meant multiple agents on the
# SAME model_id tried to hold several copies and a later load failed (the
# redactor_unavailable that broke the old tier ladder). Key by model_id so the
# first qwen_local call loads once and every later wrapper with that model_id
# REUSES the resident instance. This changes only HOW the model loads, never WHAT
# it does (LAW-IV: still fully local).
_QWEN_MODELS: dict = {}                 # model_id -> (tokenizer, model)
_QWEN_LOAD_LOCK = threading.Lock()      # guards first-load so a concurrent first call cannot double-load

# Job B: an outer backstop on a local call's output budget, never the budget
# itself. Every local call site in pipeline.py now sets its own max_tokens,
# sized to what that call type is shown to need; this exists only so a caller
# that forgets to size one, or asks for something unreasonable, cannot run the
# wall clock away unboundedly. Both local models' own context windows (Qwen
# 32768, Phi 131072 positions) are far larger, so this is not a model limit.
LOCAL_MAX_OUTPUT_TOKENS = 8192


def _evict_generation_models(keep_model_id=None):
    """Remove every generation model from _QWEN_MODELS except keep_model_id.
    Caller MUST hold _QWEN_LOAD_LOCK. After deletion, collects reference cycles and
    calls torch.cuda.empty_cache() so the freed VRAM is returned to the allocator.
    On an 8 GB card two 7B-class models cannot co-reside; this keeps at most
    one resident so the next load succeeds.

    local RUNDAY: the gc.collect() is load-bearing, not hygiene. An nn.Module graph
    carries reference cycles (a device_map load also attaches module._hf_hook
    back-references), so plain refcounting does NOT reclaim the evicted model's
    HOST-side buffers when the dict entry is popped; empty_cache() only returns VRAM
    that is already free. Without the collect, the outgoing model's CPU allocations
    can still be committed while the incoming checkpoint is staged, which is exactly
    the moment this machine runs out of system RAM."""
    to_evict = [mid for mid in _QWEN_MODELS if mid != keep_model_id]
    if not to_evict:
        return
    torch = importlib.import_module("torch")
    for mid in to_evict:
        _tok, _mdl = _QWEN_MODELS.pop(mid)
        del _tok, _mdl
        print(f"[local] evicted {mid} from GPU cache", file=sys.stderr, flush=True)
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        vram_after = torch.cuda.memory_allocated(0)
        print(f"[local] VRAM after eviction: {vram_after / 1024**2:.0f} MB",
              file=sys.stderr, flush=True)


def _checkpoint_is_prequantised(transformers, model_id) -> bool:
    """True when the checkpoint on disk ALREADY carries its own quantization_config,
    i.e. its weights are stored quantised (e.g. an unsloth *-bnb-4bit repo).

    Why this matters (local RUNDAY, the load-memory fix): quantising on the fly reads
    the full fp16 checkpoint into HOST RAM shard by shard and quantises each shard
    there, so peak system RAM tracks the fp16 size (~15.2 GB for a 7B), not the 4-bit
    size it ends up as. A pre-quantised checkpoint is read at its stored 4-bit size
    (~5.5 GB) with no fp16 staging step at all.

    It also decides whether BitsAndBytesConfig may be passed. It may NOT: when the
    checkpoint carries its own config, transformers' merge_quantization_configs copies
    loading attributes only for GPTQ/AWQ/AutoRound/FbgemmFp8/CompressedTensors, NOT for
    BitsAndBytes, so a passed BitsAndBytesConfig is silently discarded and only emits a
    warning. Reads config.json only; no weights are touched.

    local_files_only=True: server.py's own pre-run check already resolves this
    exact model_id with local_files_only=True and reports it as cached before a
    run is even allowed to start. A load here that omits the flag reaches out to
    the hub anyway (a revision check, not a real cache miss) and breaks that
    promise the moment the network is unreliable or absent, exactly the case a
    closed-network deployment (a rented container, an air-gapped machine) exists
    to be immune to. Same flag, same guarantee, every call on this path."""
    try:
        cfg = transformers.AutoConfig.from_pretrained(model_id, local_files_only=True)
    except Exception:
        return False
    return getattr(cfg, "quantization_config", None) is not None


def _local_checkpoint_path(model_id):
    """Resolve a local model once, without a Hub metadata request.

    Transformers 4.52.3 probes custom generation code by repo id even when
    from_pretrained carries local_files_only=True. A snapshot path keeps that
    nested lookup local as well. The configured id remains the cache/log key.
    """
    if Path(model_id).is_dir():
        snapshot = Path(model_id).resolve()
    else:
        from huggingface_hub import snapshot_download
        snapshot = Path(snapshot_download(model_id, local_files_only=True))
    # A Hub cache becoming a local path must not implicitly authorize code
    # overriding generate(). The configured checkpoints use standard generation.
    if (snapshot / "custom_generate" / "generate.py").is_file():
        raise RuntimeError("custom generation code is not authorized by the local loader")
    return str(snapshot)


def _load_qwen(model_id):
    """Return the shared resident (tokenizer, model) for `model_id`, loading it at
    most once. Double-checked locking: the fast path returns the cached instance
    without the lock; the slow path loads under the lock and re-checks, so two
    concurrent first-callers cannot each load a copy. Deterministic and local,
    same from_pretrained arguments as before, only shared.

    local_files_only=True on every from_pretrained call below (tokenizer and
    model alike): this is the ACTUAL loader a run uses, and server.py's
    check_local_model_availability already resolves these same model_ids with
    the same flag before a run is allowed to start, reporting them as cached.
    Before this fix, this function was the one place that promise was broken:
    it never set the flag, so every real load reached the hub anyway (found
    live, twice, when a routine network hiccup here turned into a fatal
    ConnectionResetError killing the run's very first agent call, on a machine
    where the weights were already, genuinely, fully cached). A container on a
    rented machine, or any closed network, would die on that same first call
    while the pre-flight check insisted everything was fine. Gate check 193
    proves the fix: this path loads successfully with the network blocked.

    Before loading a NEW model_id, any OTHER resident model is evicted so that
    at most one generation model occupies the GPU at a time (L2 memory strategy).
    VRAM is measured and logged after every load."""
    import execution_topology
    resident = execution_topology.resident_model(model_id)
    if resident is not None:
        return resident
    cached = _QWEN_MODELS.get(model_id)
    if cached is not None:
        return cached
    transformers = importlib.import_module("transformers")
    torch = importlib.import_module("torch")
    with _QWEN_LOAD_LOCK:
        cached = _QWEN_MODELS.get(model_id)        # re-check under the lock
        if cached is None:
            checkpoint_path = _local_checkpoint_path(model_id)
            _evict_generation_models(keep_model_id=model_id)
            tok = transformers.AutoTokenizer.from_pretrained(checkpoint_path, local_files_only=True)
            # BP-6 (GPU placement): PIN the 4-bit model fully onto GPU 0. The old
            # device_map="auto" let accelerate offload layers to CPU under VRAM
            # pressure, which ran generation at CPU speed (~1 tok/s). 4-bit NF4 with
            # fp16 compute fits a small (8 GB) GPU at ~4.5 GB resident, where a full
            # fp16 7B (~14 GB) would not, so we keep 4-bit and just force the device.
            # No CUDA -> plain CPU load (functional, slow, never a silent failure).
            prequantised = False
            if torch.cuda.is_available():
                prequantised = _checkpoint_is_prequantised(transformers, checkpoint_path)
                if prequantised:
                    # Weights are ALREADY 4-bit on disk: no fp16 host staging, and no
                    # BitsAndBytesConfig may be passed (it would be silently discarded,
                    # see _checkpoint_is_prequantised). device_map pins it to GPU 0 as
                    # before; compute dtype comes from the checkpoint's own config.
                    mdl = transformers.AutoModelForCausalLM.from_pretrained(
                        checkpoint_path, device_map={"": 0}, local_files_only=True)
                else:
                    # Quantise on the fly (the original path, unchanged except for
                    # double quant): reads the full fp16 checkpoint through host RAM.
                    # bnb_4bit_use_double_quant nests the quant constants, ~0.4 bits
                    # per parameter, roughly 300 MB of VRAM on a 7B. VRAM only: it does
                    # NOT reduce the host-RAM staging spike.
                    bnb = transformers.BitsAndBytesConfig(
                        load_in_4bit=True, bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.float16,
                        bnb_4bit_use_double_quant=True)
                    mdl = transformers.AutoModelForCausalLM.from_pretrained(
                        checkpoint_path, quantization_config=bnb, device_map={"": 0},
                        local_files_only=True)
            else:
                # No CUDA: unchanged fallback, except torch_dtype. Without it the model
                # materialises at the fp32 default (a 7B is ~30 GB), which cannot
                # complete on a 16 GB machine and dies after committing all of it.
                mdl = transformers.AutoModelForCausalLM.from_pretrained(
                    checkpoint_path, torch_dtype=torch.float16, local_files_only=True)
            # Log the ACTUAL device every run, so a CPU fallback is never silent.
            try:
                dev = next(mdl.parameters()).device
            except Exception:
                dev = "unknown"
            if not torch.cuda.is_available():
                mode = "CPU (no CUDA)"
            elif prequantised:
                mode = "4-bit prequantised checkpoint"
            else:
                mode = "4-bit nf4 / fp16 compute / double quant"
            vram_msg = ""
            if torch.cuda.is_available():
                vram_mb = torch.cuda.memory_allocated(0) / 1024**2
                vram_msg = f", VRAM={vram_mb:.0f} MB"
            print(f"[local] {model_id} loaded on device {dev} ({mode}{vram_msg})",
                  file=sys.stderr, flush=True)
            cached = (tok, mdl)
            _QWEN_MODELS[model_id] = cached
    return cached

# Substrings (case-insensitive) that mark a retryable rate-limit / overload error
# from OpenAI OR Anthropic (529 overloaded). Shared by call_gpt and call_claude.
_RATE_LIMIT_MARKERS = ("rate limit", "ratelimit", "429", "tokens per min", "tpm",
                       "overloaded", "529")


def _is_rate_limit_error(err: str) -> bool:
    if not err:
        return False
    e = err.lower()
    return any(m in e for m in _RATE_LIMIT_MARKERS)


# productization STEP 3: no provider call carried a wall-clock timeout, so a
# hung network call could block a run indefinitely. SHIMMER_PROVIDER_TIMEOUT_S
# (default 600s, generous; the operator tunes it from the observed baseline
# later) is read once and passed straight to the Anthropic/OpenAI client calls,
# both of which accept a per-request `timeout` kwarg on the installed SDK
# versions (anthropic>=0.87, openai>=2.38, verified this session). Qwen has no
# wall-clock parameter for local generation; it is bounded by max_new_tokens
# instead (see call_qwen).
def _provider_timeout_s() -> float:
    raw = os.environ.get("SHIMMER_PROVIDER_TIMEOUT_S", "600")
    try:
        v = float(raw)
    except ValueError:
        return 600.0
    return v if v > 0 else 600.0


# productization STEP 3: provider exception strings land verbatim in
# CallResult.error, which is written unredacted to the message bus (agent_
# wrapper.py::run_task's BACKEND_ERROR body) and to the cost log (cost_tracker.
# py::CostEvent.error). A key value can appear in an SDK exception message
# (e.g. an auth-error echoing a malformed key). Scrub at the single point every
# provider error string is FORMED, so every downstream sink (bus + cost log)
# inherits the redaction for free. Reuses guard_secrets' own patterns rather
# than duplicating them (import, not copy-paste, so the two never drift).
def _scrub_error(text: str) -> str:
    if not text:
        return text
    import guard_secrets as _gs
    scrubbed = _gs.ANTHROPIC_RE.sub("[REDACTED_KEY]", text)
    scrubbed = _gs.GENERIC_SK_RE.sub("[REDACTED_KEY]", scrubbed)
    scrubbed = _gs.AWS_RE.sub("[REDACTED_KEY]", scrubbed)
    return scrubbed


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


# External key-file resolution. The operator's config.py lives OUTSIDE the repo
# and is located at runtime in this fixed order — no absolute path or username is
# ever baked into a tracked file:
#   1. $SHIMMER_CONFIG_PATH  -- explicit override; may point at a config.py file
#      or at a directory containing one. Wins if set and the target exists.
#   2. ../api_keys/config.py -- sibling folder one level above the repo root.
#   3. .env_path             -- legacy repo-root pointer holding a relative path
#      to the config (kept as a fallback for pre-existing setups).
CONFIG_ENV_VAR = "SHIMMER_CONFIG_PATH"
CONFIG_DIRNAME = "api_keys"
CONFIG_FILENAME = "config.py"


def _as_config_file(p) -> Path:
    """Normalize a candidate to the config.py file: a candidate may point at the
    file directly or at a directory that contains it."""
    p = Path(p).expanduser()
    return p / CONFIG_FILENAME if p.is_dir() else p


def candidate_config_paths() -> "list[tuple[str, Path]]":
    """Ordered (source-label, path) config candidates. Pure resolution — does not
    check existence, so callers (e.g. the preflight tool) can report each source.
    No absolute path or username is hardcoded; everything is relative to the repo
    root or supplied by the operator's environment."""
    root = project_root()
    cands: "list[tuple[str, Path]]" = []
    env = os.environ.get(CONFIG_ENV_VAR)
    if env:
        cands.append((CONFIG_ENV_VAR, _as_config_file(env)))
    cands.append(("sibling ../" + CONFIG_DIRNAME + "/" + CONFIG_FILENAME,
                  root.parent / CONFIG_DIRNAME / CONFIG_FILENAME))
    env_path_file = root / ".env_path"
    if env_path_file.exists():
        rel = env_path_file.read_text(encoding="utf-8").strip()
        if rel:
            cands.append((".env_path pointer", (root / rel).resolve()))
    return cands


def resolve_config_path() -> "Path | None":
    """Return the first existing config candidate, or None if the operator has set
    none up. Resilient by design: a keyless environment is a supported state (the
    pipeline gates handle absent keys — model-gate skip, redaction waiver)."""
    for _src, p in candidate_config_paths():
        try:
            if p.exists():
                return p
        except OSError:
            continue
    return None


def load_api_keys() -> dict[str, str]:
    target = resolve_config_path()
    if target is None:
        return {}
    spec = importlib.util.spec_from_file_location("_shimmer_keys", target)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_shimmer_keys"] = mod
    spec.loader.exec_module(mod)
    out = {}
    # KEYS ONLY. The external key file (located via .env_path -> an
    # operator-managed config.py outside the repo) may define anything, but this
    # reader copies out ONLY the allowlisted API-key names below. Every other
    # variable in that file is ignored -- in particular any `model` / `MODEL`
    # (or otherwise model-related) assignment is deliberately NOT read and can
    # never influence which model an agent runs. Model selection is owned
    # exclusively by config/agent_registry.json (spec.model). Do NOT add a model
    # name to this allowlist.
    _KEY_NAMES = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "BRAVE_API_KEY")
    for k in _KEY_NAMES:
        if hasattr(mod, k):
            out[k] = getattr(mod, k)
    return out


def _now(): return datetime.now(timezone.utc).isoformat()


def _match_balanced(text, start):
    """Return the index of the close delimiter matching the JSON opener at
    text[start], or None if unbalanced. Braces/brackets inside JSON string
    literals are ignored (string state + backslash escapes are tracked)."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': in_str = False
            continue
        if c == '"': in_str = True
        elif c in "{[": depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                return i
    return None


def _iter_balanced_json(text):
    """Yield each top-level balanced {...} / [...] span in document order. Nested
    structures inside a span are part of that span, not yielded separately. Used to
    recover JSON from output that wraps it in prose or emits several fragments."""
    i, n = 0, len(text)
    while i < n:
        if text[i] in "{[":
            end = _match_balanced(text, i)
            if end is not None:
                yield text[i:end + 1]
                i = end + 1
                continue
        i += 1


# ---------------------------------------------------------------------------
# Canonical inter-agent envelope (INFRA-037).
#
# Every agent output payload is ONE wrapper, carried as body.payload inside the
# existing message-bus transport envelope (the transport envelope is unchanged):
#
#     {"agent": str, "doc_id": str, "items": [ <flat item>, ... ]}
#
# items is ALWAYS a list (singleton -> one element; empty result -> []). No bare
# list, no bare dict, ever. Each item is STRICTLY FLAT (interp #1): every value is
# a scalar OR an array of scalars -- no nested objects, no arrays of objects.
# Structure is expressed as MORE ITEMS, not nesting.
#
# Per-item core fields:
#   model-owned (the model must supply): ref, kind, confidence, and verdict
#     (verdict is OPTIONAL: present when the agent judges, absent when it only
#     extracts).
#   runtime-owned (stamped/derived here, interp #2 -- the model is never required
#     to produce these correctly): item_id, revision, ts.
#   ref is the singular PRIMARY anchor consumers filter on; ref_ids is the flat
#     array carrying all citations (interp #3).
CORE_ITEM_REQUIRED = ("ref", "kind", "confidence")  # model-owned; verdict optional


def _is_scalar(v) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def _is_flat_item(item) -> bool:
    """Interp #1: an item is one level -- every value is a scalar or an array of
    scalars. A nested object, or an array containing an object, is NOT flat."""
    if not isinstance(item, dict):
        return False
    for v in item.values():
        if _is_scalar(v):
            continue
        if isinstance(v, list) and all(_is_scalar(e) for e in v):
            continue
        return False
    return True


def is_envelope(payload) -> bool:
    """True iff payload is the canonical wrapper shape (agent:str, doc_id:str,
    items:list). Does not validate per-item content."""
    return (isinstance(payload, dict)
            and isinstance(payload.get("agent"), str)
            and isinstance(payload.get("doc_id"), str)
            and isinstance(payload.get("items"), list))


def make_envelope(agent, doc_id, items) -> dict:
    """Build/normalize the canonical wrapper, stamping the RUNTIME-owned per-item
    fields (interp #2): ts (UTC now) and revision (default 1) when absent, and a
    derived item_id when the model omitted one. Model-owned fields are untouched.
    Re-emitting the same logical item with a higher `revision` is how a producer
    supersedes a prior value (see current_items)."""
    norm = []
    for idx, it in enumerate(items or []):
        if not isinstance(it, dict):
            norm.append(it)  # left as-is; validation will flag it
            continue
        item = dict(it)
        if not item.get("ts"):
            item["ts"] = _now()
        if not isinstance(item.get("revision"), int) or isinstance(item.get("revision"), bool):
            item["revision"] = 1
        if not item.get("item_id"):
            item["item_id"] = f"{agent}:{item.get('kind')}:{item.get('ref')}:{idx}"
        norm.append(item)
    return {"agent": agent, "doc_id": doc_id, "items": norm}


def current_items(items):
    """VERSION GUARDRAIL (INFRA-037): reduce items to the current revision per
    item_id -- highest `revision`, tie-break latest `ts`. Items without an item_id
    are kept as-is (they cannot collide). This is the single helper every consumer
    uses so a superseded value is never read."""
    best = {}
    passthrough = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        key = it.get("item_id")
        if key is None:
            passthrough.append(it)
            continue
        cur = best.get(key)
        cand_rank = (it.get("revision", 1), it.get("ts", ""))
        if cur is None or cand_rank > (cur.get("revision", 1), cur.get("ts", "")):
            best[key] = it
    return list(best.values()) + passthrough


def decode_items(payload, *, current=True):
    """THE canonical decoder. Given an agent's body.payload (the wrapper), return
    its items -- by default reduced to the current revision per item_id. A payload
    that is not the canonical wrapper returns [] (callers treat an absent/invalid
    wrapper as 'no items', then flag absence per the READ-WHEN-PRESENT rule). This
    is the ONE reader; no agent path bypasses it."""
    if not is_envelope(payload):
        return []
    items = [it for it in payload["items"] if isinstance(it, dict)]
    return current_items(items) if current else items


# Prompt section classification (local D2). EVERY header ContextPackage.as_prompt_sections
# can emit is listed here, plus the agent identity block, so the dump has NO unnamed
# remainder and scaffold + material sum to 100. scaffold = text telling the agent who it
# is and how to behave; material = text it is meant to analyse or compare against.
PROMPT_SECTION_CLASS = {
    "agent_identity": "scaffold",
    "CONSTITUTION": "scaffold",
    "CONVENTION_REGISTRY": "scaffold",
    "RUN_OBJECTIVES": "scaffold",
    "TASK_FORCE_CHARTER": "scaffold",
    "PRECEDENTS": "material",
    "REFERENCE_INDEX": "material",
    "OLDER_BUS_SUMMARY": "material",
    "RECENT_BUS": "material",
    "WORK_PAYLOAD": "material",
}


@dataclass
class CallResult:
    backend: str
    model: str
    raw_text: str
    parsed: Any = None
    usage: dict = field(default_factory=dict)
    ok: bool = True
    error: str = ""


@dataclass
class AgentWrapper:
    name: str
    constitution: Constitution
    bus: MessageBus
    registry: dict
    contracts: dict
    keys: dict = field(default_factory=dict)
    cost_tracker: CostTracker | None = None
    # Per-run context (run_context.RunContext). Threaded from the orchestrator so
    # every agent writes its run-scoped artifacts (contract-violation dumps) into
    # the CURRENT run's folder, never a shared global output/ path (Part XXVII §A).
    run_context: Any = None
    # LAW-IV outbound masking (INFRA-041 P2, chokepoint 1). An INJECTED callable
    # (built by sensitivity_layer.make_outbound_prompt_masker; pipeline owns the import,
    # so the boundary "only orchestration imports sensitivity_layer" holds and this module
    # imports nothing from the privacy home). Called just before dispatch to mask the
    # outbound prompt for NETWORK backends under sensitive mode; None => no masking (the
    # default, so non-sensitive runs and unmodified callers are byte-for-byte unchanged).
    outbound_masker: Any = None
    # productization STEP 4: the run's sensitive/redaction_enabled flag (the same
    # signal pipeline.main threads into outbound_masker construction as
    # sensitive=redaction_enabled). Used ONLY to decide whether a contract-
    # violation dump is hashed rather than written as text (see
    # _persist_contract_violation_raw_text); it does NOT gate masking itself,
    # which stays owned entirely by outbound_masker. Defaults to False so every
    # caller that does not pass it explicitly is unchanged (raw text kept).
    sensitive: bool = False

    def __post_init__(self):
        if self.name not in self.registry:
            raise ValueError(f"agent {self.name!r} not in registry")
        self.spec = self.registry[self.name]
        self.backend = self.spec["backend"]
        # Registry is the sole source of the agent's model id (no key-layer
        # override, no hardcoded default).
        self.model = self.spec.get("model")
        self.contract = self.contracts.get(self.name, {})
        # structure H2a: what the last parse did (which JSON candidate was taken,
        # how many were scanned, how many valid-but-empty wrappers were passed
        # over). Written by parse_contract_output, read by run_task.
        self.last_parse_trace = {}
        if not self.keys:
            self.keys = load_api_keys()

    def _record_cost(self, r, *, duration_ms=0):
        self._generation_usage = dict(r.usage or {}, backend_success=r.ok, backend_call_seconds=duration_ms / 1000)
        if self.cost_tracker is None: return
        u = r.usage or {}
        self.cost_tracker.record(
            agent=self.name, backend=r.backend, model=r.model,
            input_tokens=u.get("input_tokens"),
            output_tokens=u.get("output_tokens"),
            # Prompt-cache usage (INFRA-036). Anthropic: cache_read/creation;
            # OpenAI: cached_input_tokens. Absent -> 0 (handled in record()).
            cache_read_input_tokens=u.get("cache_read_input_tokens"),
            cache_creation_input_tokens=u.get("cache_creation_input_tokens"),
            cached_input_tokens=u.get("cached_input_tokens"),
            # Job B's own measurement, carried to the row instead of stopping at
            # the wrapper: a response that hit its ceiling is a DIFFERENT fact
            # from one that came back short, and the 2026-09-12 runs could not
            # tell them apart on disk. None when the backend reported no usage.
            truncated=u.get("truncated"),
            ok=r.ok, error=r.error,
            # productization STEP 4: cost dimensions. phase/doc_id are transient
            # instance attributes run_task sets immediately before calling
            # dispatch() (and clears in a finally block), read here rather than
            # threaded as parameters through every call_claude/call_gpt/
            # call_qwen return point. duration_ms is measured by the caller
            # (each call_* method, around its own full body including retries)
            # and passed explicitly, since it must reflect THIS call's timing
            # rather than instance state that could not be set before this
            # method runs. Absent caller (e.g. a gate check outside run_task)
            # -> "" / 0, exactly the prior behavior.
            phase=getattr(self, "_cost_phase", ""), doc_id=getattr(self, "_cost_doc_id", ""),
            duration_ms=duration_ms,
            # call evidence: the id run_task minted for this call, so the cost row
            # joins logs/call_evidence.jsonl. "" outside run_task, as phase/doc_id are.
            call_id=getattr(self, "_cost_call_id", ""),
        )

    def check_constitution(self, situation): return self.constitution.check(situation)

    def call_claude(self, stable_prefix, dynamic_suffix="", *, max_tokens=4096):
        # productization STEP 4: wall-clock timing for this call, passed to every
        # _record_cost() below (including the early-return paths) so duration_ms
        # is populated regardless of where the call ends.
        _t0 = time.perf_counter()
        def _record_cost(r):
            self._record_cost(r, duration_ms=int((time.perf_counter() - _t0) * 1000))

        key = self.keys.get("ANTHROPIC_API_KEY")
        if not key:
            r = CallResult("claude_api", "?", "", ok=False, error="ANTHROPIC_API_KEY not loaded")
            _record_cost(r); return r
        try:
            anthropic = importlib.import_module("anthropic")
        except ImportError as e:
            r = CallResult("claude_api", "?", "", ok=False, error=f"anthropic not installed: {e}")
            _record_cost(r); return r
        model = self.model
        if not model:
            # No silent substitution: a missing/invalid model is surfaced, not
            # quietly replaced. The registry is the sole source of truth.
            r = CallResult("claude_api", "?", "", ok=False,
                           error=f"no model configured for agent {self.name!r} in agent_registry.json")
            _record_cost(r); return r
        # Prompt caching (INFRA-036), EXPLICIT for Anthropic: mark the END of the
        # stable prefix with cache_control so it is written once and read at 0.1x
        # on subsequent calls. The prefix must be an EXACT match across calls;
        # build_prompt guarantees no dynamic content precedes the breakpoint.
        # Default TTL is ephemeral (5 minutes), which fits this workload: a run
        # fires many agent calls back-to-back within minutes, so the 5-min window
        # (1.25x write) covers reuse without paying the 2x one-hour write premium.
        if stable_prefix:
            content = [{"type": "text", "text": stable_prefix,
                        "cache_control": {"type": "ephemeral"}}]
            if dynamic_suffix:
                content.append({"type": "text", "text": dynamic_suffix})
        else:
            content = [{"type": "text", "text": dynamic_suffix}]
        # BP-5: retry rate-limit / overload (429/529) with backoff. Parallel document
        # processing raises the number of concurrent Claude calls on one API key;
        # call_claude previously had no retry (unlike call_gpt), so a transient 429
        # killed the agent. Belt-and-suspenders with the doc-concurrency semaphore.
        timeout_s = _provider_timeout_s()

        def _attempt():
            try:
                client = anthropic.Anthropic(api_key=key, timeout=timeout_s)
                resp = client.messages.create(model=model, max_tokens=max_tokens,
                                              messages=[{"role": "user", "content": content}])
            except anthropic.APITimeoutError:
                return None, f"timeout after {timeout_s:g}s"
            except Exception as e:
                return None, _scrub_error(f"{type(e).__name__}: {e}")
            return resp, ""
        resp, err = _attempt()
        for delay in (20, 40):
            if resp is not None or not _is_rate_limit_error(err):
                break
            log_event(_LOG, f"rate_limit_retry backend=claude_api wait_s={delay}",
                      level="warning", agent=self.name,
                      run_id=getattr(self.run_context, "run_id", "") or "")
            time.sleep(delay)
            resp, err = _attempt()
        if resp is None:
            r = CallResult("claude_api", model, "", ok=False, error=err)
            _record_cost(r); return r
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        # Cache fields (absent on older models / SDKs -> 0, never crash).
        r = CallResult("claude_api", model, text, usage={
            "requested_max_output_tokens": max_tokens,
            "finish_reason": getattr(resp, "stop_reason", None),
            "truncated": None if getattr(resp, "stop_reason", None) is None else resp.stop_reason == "max_tokens",
            "input_tokens": getattr(resp.usage, "input_tokens", None),
            "output_tokens": getattr(resp.usage, "output_tokens", None),
            "cache_creation_input_tokens": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
            "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
        })
        _record_cost(r); return r

    def call_gpt(self, stable_prefix, dynamic_suffix="", *, max_tokens=4096):
        with _GPT_SEMAPHORE:
            return self._call_gpt_locked(stable_prefix, dynamic_suffix, max_tokens=max_tokens)

    def _call_gpt_locked(self, stable_prefix, dynamic_suffix="", *, max_tokens=4096):
        # productization STEP 4: same per-call wall-clock timing pattern as call_claude.
        _t0 = time.perf_counter()
        def _record_cost(r):
            self._record_cost(r, duration_ms=int((time.perf_counter() - _t0) * 1000))

        # Prompt caching (INFRA-036), AUTOMATIC for OpenAI: no cache_control. We
        # only STRUCTURE the prompt stable-prefix-first (identical discipline as
        # Claude) so OpenAI's automatic prefix cache actually catches, then verify
        # it via the logged cached_tokens field below.
        prompt = stable_prefix + ("\n\n" + dynamic_suffix if (stable_prefix and dynamic_suffix)
                                  else dynamic_suffix)
        key = self.keys.get("OPENAI_API_KEY")
        if not key:
            r = CallResult("openai_api", "?", "", ok=False, error="OPENAI_API_KEY not loaded")
            _record_cost(r); return r
        try:
            openai = importlib.import_module("openai")
        except ImportError as e:
            r = CallResult("openai_api", "?", "", ok=False, error=f"openai not installed: {e}")
            _record_cost(r); return r
        model = self.model
        if not model:
            r = CallResult("openai_api", "?", "", ok=False,
                           error=f"no model configured for agent {self.name!r} in agent_registry.json")
            _record_cost(r); return r

        timeout_s = _provider_timeout_s()

        def _attempt():
            try:
                client = openai.OpenAI(api_key=key, timeout=timeout_s)
                resp = client.chat.completions.create(
                    model=model, max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
            except openai.APITimeoutError:
                return None, f"timeout after {timeout_s:g}s"
            except Exception as e:
                return None, _scrub_error(f"{type(e).__name__}: {e}")
            return resp, ""

        resp, err = _attempt()
        if resp is None and _is_rate_limit_error(err):
            log_event(_LOG, "rate_limit_retry backend=openai_api wait_s=60",
                      level="warning", agent=self.name,
                      run_id=getattr(self.run_context, "run_id", "") or "")
            time.sleep(60)
            resp, err = _attempt()
        if resp is None:
            r = CallResult("openai_api", model, "", ok=False, error=err)
            _record_cost(r); return r
        text = resp.choices[0].message.content or ""
        # OpenAI reports the auto-cached prefix in usage.prompt_tokens_details
        # .cached_tokens (object OR dict, depending on SDK). Absent -> 0, never
        # crash. Logging it makes a silent provider-side cache loss visible (the
        # cached count drops to zero in the cost log) instead of hidden.
        cached = 0
        details = getattr(resp.usage, "prompt_tokens_details", None)
        if isinstance(details, dict):
            cached = details.get("cached_tokens") or 0
        elif details is not None:
            cached = getattr(details, "cached_tokens", 0) or 0
        r = CallResult("openai_api", model, text, usage={
            "requested_max_output_tokens": max_tokens,
            "finish_reason": getattr(resp.choices[0], "finish_reason", None),
            "truncated": None if getattr(resp.choices[0], "finish_reason", None) is None else resp.choices[0].finish_reason == "length",
            "input_tokens": getattr(resp.usage, "prompt_tokens", None),
            "output_tokens": getattr(resp.usage, "completion_tokens", None),
            "cached_input_tokens": cached,
        })
        _record_cost(r); return r

    # productization STEP 3: transformers' generate() has no wall-clock timeout
    # parameter, so local Qwen generation cannot be bounded by seconds the way
    # the two network calls above are. It is bounded by TOKEN COUNT instead:
    # max_new_tokens (default 1024, unchanged by this step) caps how much the
    # model can produce, which caps wall time indirectly since decoding speed
    # on a given device is roughly constant. This is a documented limitation,
    # not a defect: a wall-clock kill would require a separate watchdog thread
    # around generate(), out of scope for this step (SHIMMER_PROVIDER_TIMEOUT_S
    # governs only the two network calls, call_claude and call_gpt).
    def call_qwen(self, prompt, *, max_new_tokens=1024):
        # productization STEP 4: same per-call wall-clock timing pattern as
        # call_claude/call_gpt. Qwen has no wall-clock timeout parameter (STEP 3
        # note); this is purely a duration MEASUREMENT, not a bound.
        _t0 = time.perf_counter()
        def _record_cost(r):
            self._record_cost(r, duration_ms=int((time.perf_counter() - _t0) * 1000))

        try:
            torch = importlib.import_module("torch")
            transformers = importlib.import_module("transformers")
        except ImportError as e:
            r = CallResult("qwen_local", "qwen2.5-7b", "", ok=False, error=f"torch/transformers missing: {e}")
            _record_cost(r); return r
        model_id = self.model
        if not model_id:
            r = CallResult("qwen_local", "?", "", ok=False,
                           error=f"no model configured for agent {self.name!r} in agent_registry.json")
            _record_cost(r); return r
        try:
            # Shared resident instance (loaded once per model_id) — the single
            # REDACTOR (qwen_local) reuses ONE 7B; any other qwen_local agent on
            # the same model_id reuses it too (see _load_qwen).
            tok, mdl = _load_qwen(model_id)
        except Exception as e:
            r = CallResult("qwen_local", model_id, "", ok=False, error=f"qwen load failed: {e}")
            _record_cost(r); return r
        template_applied = bool(getattr(self, "_optimized_semantics", False))
        if template_applied:
            if not getattr(tok, "chat_template", None):
                raise ValueError("Configured local tokenizer has no chat template")
            prompt = tok.apply_chat_template([{"role": "user", "content": prompt}],
                                            tokenize=False, add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt", **({"add_special_tokens": False} if template_applied else {})).to(mdl.device)
        generation_started = time.perf_counter()
        with torch.no_grad():
            out = mdl.generate(**inputs, max_new_tokens=max_new_tokens)
        generation_seconds = time.perf_counter() - generation_started
        generated_count = int(out.shape[-1]) - int(inputs["input_ids"].shape[1])
        last_token = int(out[0][-1]) if generated_count else None
        eos_ids = getattr(getattr(mdl, "generation_config", None), "eos_token_id", None)
        stop_reason, truncated = generation_observation.local_stop(last_token, eos_ids, generated_count, max_new_tokens)
        text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        out_tokens = out.shape[-1] - int(inputs["input_ids"].shape[1])
        # EOS may occur on the final allowed token. Record cap contact and the
        # actual terminal token separately; a short response without known EOS
        # remains unknown rather than being certified complete.
        r = CallResult("qwen_local", model_id, text, usage={
            "input_tokens": int(inputs["input_ids"].shape[1]),
            "output_tokens": out_tokens,
            "truncated": truncated, "finish_reason": stop_reason,
            "requested_max_output_tokens": max_new_tokens,
            "generation_seconds": generation_seconds, "time_to_first_token_seconds": None,
            "chat_template_applied": template_applied,
            "rendered_prompt_sha256": generation_observation.prompt_identity(prompt),
            "cap_hit": out_tokens >= max_new_tokens,
            "terminal_token_id": last_token, "configured_eos_token_ids": eos_ids,
        })
        _record_cost(r); return r

    def call_local(self, prompt, *, max_new_tokens=1024):
        """Generic local inference for local_producer/local_auditor backends.
        Same loading and generation pattern as call_qwen, same shared model
        cache (_load_qwen / _QWEN_MODELS), reports the agent's own backend."""
        _t0 = time.perf_counter()
        def _record_cost(r):
            self._record_cost(r, duration_ms=int((time.perf_counter() - _t0) * 1000))

        try:
            torch = importlib.import_module("torch")
            importlib.import_module("transformers")
        except ImportError as e:
            r = CallResult(self.backend, "?", "", ok=False, error=f"torch/transformers missing: {e}")
            _record_cost(r); return r
        model_id = self.model
        if not model_id:
            r = CallResult(self.backend, "?", "", ok=False,
                           error=f"no model configured for agent {self.name!r} in agent_registry.json")
            _record_cost(r); return r
        try:
            tok, mdl = _load_qwen(model_id)
        except Exception as e:
            r = CallResult(self.backend, model_id, "", ok=False, error=f"local model load failed: {e}")
            _record_cost(r); return r
        template_applied = bool(getattr(self, "_optimized_semantics", False))
        if template_applied:
            if not getattr(tok, "chat_template", None):
                raise ValueError("Configured local tokenizer has no chat template")
            prompt = tok.apply_chat_template([{"role": "user", "content": prompt}],
                                            tokenize=False, add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt", **({"add_special_tokens": False} if template_applied else {})).to(mdl.device)
        generation_started = time.perf_counter()
        with torch.no_grad():
            out = mdl.generate(**inputs, max_new_tokens=max_new_tokens)
        generation_seconds = time.perf_counter() - generation_started
        generated_count = int(out.shape[-1]) - int(inputs["input_ids"].shape[1])
        last_token = int(out[0][-1]) if generated_count else None
        eos_ids = getattr(getattr(mdl, "generation_config", None), "eos_token_id", None)
        stop_reason, truncated = generation_observation.local_stop(last_token, eos_ids, generated_count, max_new_tokens)
        text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        in_tokens = int(inputs["input_ids"].shape[1])
        out_tokens = out.shape[-1] - in_tokens
        # Return the generation buffers before the next call asks for them.
        # A call's KV cache and logits are large and are dead the moment the
        # text is decoded, but the caching allocator holds them as RESERVED,
        # and on Windows expandable_segments is a no-op so that reservation
        # fragments. Measured on an 8 GB card: a run died with 6.11 GiB
        # allocated and 1.42 GiB reserved-but-unallocated, needing 148 MiB it
        # could not get. Freeing here costs a few milliseconds per call and
        # shrinks no input, which matters because the benchmark may not be
        # shrunk to make a run fit.
        del inputs, out
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass  # freeing memory must never take the run down
        # Use the terminal token and the configured EOS set, not length alone.
        r = CallResult(self.backend, model_id, text, usage={
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "truncated": truncated, "finish_reason": stop_reason,
            "requested_max_output_tokens": max_new_tokens,
            "generation_seconds": generation_seconds, "time_to_first_token_seconds": None,
            "chat_template_applied": template_applied,
            "rendered_prompt_sha256": generation_observation.prompt_identity(prompt),
            "cap_hit": out_tokens >= max_new_tokens,
            "terminal_token_id": last_token, "configured_eos_token_ids": eos_ids,
        })
        _record_cost(r); return r

    def dispatch(self, stable_prefix, dynamic_suffix="", **kwargs):
        """Route a cache-structured (stable_prefix, dynamic_suffix) prompt to the
        backend. Claude marks the stable prefix as an explicit cache breakpoint;
        GPT concatenates stable-first for OpenAI's automatic prefix cache; Qwen
        (local, no caching) receives the plain concatenation."""
        if self.backend == "claude_api": return self.call_claude(stable_prefix, dynamic_suffix, **kwargs)
        if self.backend == "openai_api": return self.call_gpt(stable_prefix, dynamic_suffix, **kwargs)
        if self.backend == "qwen_local":
            full = stable_prefix + ("\n\n" + dynamic_suffix if dynamic_suffix else "")
            return self.call_qwen(full, **kwargs)
        if self.backend in ("local_producer", "local_auditor"):
            full = stable_prefix + ("\n\n" + dynamic_suffix if dynamic_suffix else "")
            return self.call_local(full, **kwargs)
        return CallResult(self.backend, "?", "", ok=False, error=f"unknown backend {self.backend!r}")

    def _contract_missing(self, obj):
        """Validate obj against the CANONICAL ENVELOPE (INFRA-037). Returns the
        list of problems; an empty list means the wrapper is valid (an empty
        `items` list IS valid -- a 'nothing to report' result). A bare list or
        bare dict is rejected: it is not the wrapper.

        Checks: the wrapper shape ({agent:str, doc_id:str, items:list}); per item,
        flatness (interp #1), the model-owned core fields (ref/kind/confidence;
        verdict optional, runtime stamps item_id/revision/ts), and this agent's
        contract `required` (agent-specific per-item fields)."""
        if not is_envelope(obj):
            return ["not a canonical envelope {agent:str, doc_id:str, items:list}"]
        missing = []
        required = self.contract.get("required", [])  # agent-specific per-item fields
        for i, item in enumerate(obj["items"]):
            if not isinstance(item, dict):
                missing.append(f"items[{i}].(not an object)")
                continue
            if not _is_flat_item(item):
                missing.append(f"items[{i}].(not flat: nested object or array-of-objects)")
            for rkey in CORE_ITEM_REQUIRED:
                if rkey not in item or item.get(rkey) in (None, ""):
                    missing.append(f"items[{i}].{rkey}")
            for rkey in required:
                if rkey not in item or item.get(rkey) in (None, ""):
                    missing.append(f"items[{i}].{rkey}")
        return missing

    def _finalize_envelope(self, obj):
        """Validate obj as the wrapper and (when it is one) stamp the runtime-owned
        item fields. Returns (wrapper-or-obj, missing)."""
        adapter = getattr(self, "_source_adapter", None)
        if adapter is not None:
            try:
                obj = adapter(obj)
            except ValueError as exc:
                return obj, [str(exc)]
        missing = self._contract_missing(obj)
        if is_envelope(obj):
            return make_envelope(obj["agent"], obj["doc_id"], obj["items"]), missing
        return obj, missing

    def parse_contract_output(self, raw):
        """Parse the model response into the CANONICAL ENVELOPE (INFRA-037).

        (1) STRICT fast path: whole-response json.loads. A clean wrapper is
            accepted (and stamped); a clean bare list/dict is REJECTED (it is not
            the wrapper) and reported as a contract violation.
        (2) TOLERANT recovery (only if strict json fails): scan balanced JSON
            candidates and recover a valid wrapper -- recovery recovers INTO the
            wrapper, it never fabricates one from a bare list. If a candidate
            parses but is not a valid wrapper, it is returned as a best-effort
            with its problems (so the violation is reported, not masked). If
            nothing parses, return (None, [parse failure]).

        structure H2a. Recovery used to stop at the FIRST valid wrapper, which
        meant a valid-but-EMPTY envelope emitted ahead of real content ended the
        scan and the content behind it was discarded. That is not hypothetical:
        D4's own INST_FINDER measurement (agent_wrapper.py, _role_anchor_text)
        found two of five apparent successes were exactly this, an empty envelope
        emitted before real content, counted as a clean hold. Recovery now prefers
        the first POPULATED valid wrapper and falls back to a valid empty one only
        when no populated wrapper exists anywhere in the response.

        What counts as VALID is unchanged: _finalize_envelope decides, and an
        empty items list is still a legitimate hold when it is all the model sent.
        The only change is WHICH valid candidate wins when there is more than one.

        The scan records what it did in self.last_parse_trace, which run_task
        returns and posts to the bus, so a post-mortem can see that a hold was
        chosen over content rather than having to infer it."""
        if getattr(self, "_compact_contract", None):
            # Task-scoped compact output must be one complete JSON response.
            # Never recover a valid prefix from a truncated or trailing envelope.
            try:
                obj = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return None, ["Complete compact JSON response required"]
            self.last_parse_trace = {"path": "strict_compact", "candidates_scanned": 1,
                                     "chosen_index": 0, "empty_valid_skipped": 0}
            return self._finalize_envelope(obj)
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"): text = text[4:].strip()
        # (1) strict fast path
        try:
            obj = json.loads(text)
            env, missing = self._finalize_envelope(obj)
            self.last_parse_trace = {"path": "strict", "candidates_scanned": 1,
                                     "chosen_index": 0, "empty_valid_skipped": 0}
            return env, missing
        except json.JSONDecodeError:
            pass
        # (2) tolerant recovery
        first_parsed = None          # best-effort: parsed but not a valid wrapper
        first_valid_empty = None     # a valid wrapper carrying no items
        last_error = None
        scanned = 0
        empty_valid_skipped = 0
        for index, cand in enumerate(_iter_balanced_json(text)):
            scanned += 1
            try:
                obj = json.loads(cand)
            except json.JSONDecodeError as e:
                last_error = e
                continue
            env, missing = self._finalize_envelope(obj)
            if not missing:
                if env.get("items"):
                    self.last_parse_trace = {
                        "path": "recovery", "candidates_scanned": scanned,
                        "chosen_index": index, "empty_valid_skipped": empty_valid_skipped,
                    }
                    return env, []   # a populated valid wrapper always wins
                empty_valid_skipped += 1
                if first_valid_empty is None:
                    first_valid_empty = (env, index)
                continue
            if first_parsed is None:
                first_parsed = (env, missing, index)
        if first_valid_empty is not None:
            env, index = first_valid_empty
            self.last_parse_trace = {
                "path": "recovery", "candidates_scanned": scanned,
                "chosen_index": index,
                # This one was chosen, so it is not itself "skipped".
                "empty_valid_skipped": max(0, empty_valid_skipped - 1),
            }
            return env, []
        if first_parsed is not None:
            env, missing, index = first_parsed
            self.last_parse_trace = {
                "path": "recovery", "candidates_scanned": scanned,
                "chosen_index": index, "empty_valid_skipped": empty_valid_skipped,
            }
            return env, missing
        self.last_parse_trace = {"path": "recovery", "candidates_scanned": scanned,
                                 "chosen_index": None,
                                 "empty_valid_skipped": empty_valid_skipped}
        if scanned and last_error is not None:
            return None, [f"json parse failure: {last_error}"]
        return None, ["no JSON object found in output"]

    def post_to_bus(self, *, recipient, channel, msg_type, body, constitution_check, sender_role="agent"):
        return self.bus.post({
            "timestamp": _now(), "sender": self.name, "sender_role": sender_role,
            "recipient": recipient, "channel": channel, "type": msg_type, "body": body,
            "constitution_check": constitution_check,
        })

    def _persist_contract_violation_raw_text(self, raw_text: str, missing: list) -> Path | None:
        """Write the full raw_text of a contract-violating response to disk so
        the operator can recover what the model actually produced. The bus
        message stores only an excerpt; this file holds the complete output.

        Path: <run_dir>/audit/contract_violations/{agent}_{timestamp}.txt — the
        CURRENT run's folder (run-awareness threaded in from the orchestrator).
        If no run context was supplied (e.g. an isolated unit construction), it
        falls back to output/audit/contract_violations/ so nothing is lost.

        productization STEP 4: under a redaction-enabled run (self.sensitive is
        True, the same signal pipeline.main threads as sensitive=redaction_
        enabled), the raw response is document-derived text and must not sit as
        plaintext in this shared-shaped directory: only a SHA-256 hash of the
        bytes and their length are persisted, never the text itself. Under a
        non-sensitive run the full text is kept exactly as before.

        Returns the path on success, or None if persistence failed (never
        raises — recovery is best-effort and must not interrupt the pipeline).
        """
        if not raw_text:
            return None
        try:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            import execution_topology
            ts = execution_topology.artifact_stamp(ts)
            if self.run_context is not None:
                out_dir = self.run_context.contract_violations_dir()
            else:
                out_dir = project_root() / "output" / "audit" / "contract_violations"
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{self.name}_{ts}.txt"
            raw_bytes = raw_text.encode("utf-8")
            if self.sensitive:
                import hashlib
                body = (
                    f"sha256: {hashlib.sha256(raw_bytes).hexdigest()}\n"
                    f"length_bytes: {len(raw_bytes)}\n"
                )
            else:
                body = raw_text
            header = (
                f"# Contract violation raw output\n"
                f"# agent: {self.name}\n"
                f"# timestamp: {datetime.now(timezone.utc).isoformat()}\n"
                f"# missing_fields: {missing}\n"
                f"# raw_text_bytes: {len(raw_bytes)}\n"
                f"# sensitive: {bool(self.sensitive)}\n"
                f"# ---\n"
            )
            path.write_text(header + body, encoding="utf-8")
            return path
        except Exception:
            return None

    def build_constitution_check(self, *, laws_consulted, result, resolution=""):
        return {"laws_consulted": laws_consulted, "result": result, "resolution": resolution}

    def _output_contract_text(self) -> str:
        """The CANONICAL ENVELOPE output instruction (INFRA-037), shared by
        prompt_template and _stable_agent_block so the two never drift. Instructs
        the wrapper with a 'nothing to report' example and a one-item example."""
        if getattr(self, "_compact_contract", None):
            return self._compact_contract
        cf = self.contract.get("fields", {}); required = self.contract.get("required", [])
        # structure H2b: the declared field forms are PREPENDED, so every existing
        # line of the output contract below is byte-identical to what it was and an
        # agent that declares no forms gets exactly its previous prompt.
        body = (
            "## Output contract — return ONE JSON object (the canonical envelope), no markdown fences:\n"
            f'{{"agent": "{self.name}", "doc_id": "<document id>", "items": [ ... ]}}\n'
            "`items` is ALWAYS a list. Each item is FLAT: one level, values are scalars or arrays of "
            "scalars only — NO nested objects and NO arrays of objects (express structure as MORE items, "
            "e.g. one item per finding/element/redaction).\n"
            "Per item, supply the core fields: ref (the REF-*/segment id this item is about), kind, "
            "confidence (CONFIDENT|UNCERTAIN), verdict (only when you judge), ref_ids (flat array of all "
            "REF-* you cite; a search-discovered web reference is cited as a WEB-REF-* id, INFRA-042). "
            "Plus this agent's fields: "
            f"{cf}; required per item: {required}. "
            "(item_id, revision, ts are stamped by the runtime — you may omit them.)\n"
            f'Nothing to report -> {{"agent": "{self.name}", "doc_id": "<id>", "items": []}}\n'
            f"One item -> {self._worked_item_example()}\n"
        )
        return self._field_forms_text() + self._finding_record_text() + body

    def _finding_record_text(self) -> str:
        """structure H3: ask, in the prompt, for the typed inter-agent record.

        Declaring the record in config/agent_contracts.json was not enough on its
        own. Measured on the api backend over three passes, four agents that the
        contract told about `finding_record` emitted 15 items and ZERO typed
        records: the shape reached the model only as one key inside the stringified
        `fields` dict, which is not an instruction. H2b's A/B had already shown
        what works, a sentence per field plus one filled example, so the same
        treatment is applied here.

        Rendered only for an agent whose contract lists `finding_record` among its
        fields; every other agent's prompt is byte-identical to before."""
        if "finding_record" not in (self.contract.get("fields") or {}):
            return ""
        try:
            import finding_record as _fr
            sch = _fr.schema()
        except Exception:
            return ""
        says = sch.get("says") or {}
        lines = []
        for field in sch.get("fields", []):
            sentence = says.get(field)
            if sentence:
                lines.append(f"- {field}: {sentence}")
        if not lines:
            return ""
        example = json.dumps({
            "ref": "REF-0001", "kind": "finding", "confidence": "CONFIDENT",
            "rule_id": "CONV-001", "unit_id": "<the unit this is about>",
            "relation": sch["relations"][0], "record_verdict": sch["verdicts"][-1],
            "verdict": "<your own contract's verdict value, unchanged>",
            "value_a": 12.5, "unit_a": "<unit>", "value_b": 13.0, "unit_b": "<unit>",
            "source_refs": ["REF-0001"],
            "explanation": "<one or two sentences for the person reading the review>",
            "ref_ids": ["REF-0001"],
        }, ensure_ascii=False)
        return (
            "## The typed finding record\n"
            "When a finding is a comparison of two figures, state it in FIELDS, not in "
            "a sentence. Another agent reads your fields; only a person reads your "
            "explanation. Set these on the item itself, flat, alongside the core fields:\n"
            + "\n".join(lines) + "\n"
            f"relation is one of {list(sch['relations'])}; record_verdict is one of "
            f"{list(sch['verdicts'])}. Keep your own `verdict` field as your "
            f"contract defines it: record_verdict is an additional field, not a "
            f"replacement.\n"
            f"Worked example: {example}\n"
            "A finding that is not a comparison of figures does not need these fields.\n\n"
        )

    def _field_forms_text(self) -> str:
        """structure H2b: state the contract's declared field forms IN THE PROMPT.

        Two properties failed in practice and were only ever caught after the run:
        location has to be a REF-* id (or the document-level sentinel), and comment
        has to spell out a CONV-* and a REF-* in its own text. The model was never
        told either one in so many words; it was left to infer them from a field
        description. They are now declared in config/agent_contracts.json under
        `field_forms` and rendered here verbatim, so the prompt, the validator and
        the contract cannot drift apart. An agent with no declared forms gets an
        empty string and its prompt is byte-identical to before."""
        forms = self.contract.get("field_forms") or {}
        lines = []
        for field, spec in forms.items():
            says = spec.get("says") if isinstance(spec, dict) else ""
            if says:
                lines.append(f"- {field}: {says}")
        if not lines:
            return ""
        return ("## Field forms, checked after you answer\n"
                "These are not style preferences. An item that breaks one of them is "
                "recorded as ungrounded.\n" + "\n".join(lines) + "\n\n")

    def _worked_item_example(self) -> str:
        """A per-agent worked one-item example. REDACTOR gets a REDACTION-shaped
        example (kind='redaction') so the generic 'finding' example never seeds it
        (that bleed caused valid redactions to be tagged kind='finding' and dropped)."""
        if self.name == "REDACTOR":
            return ('{"agent": "REDACTOR", "doc_id": "<id>", "items": ['
                    '{"ref": "REF-0006", "kind": "redaction", "confidence": "CONFIDENT", '
                    '"span": "<exact text to redact, verbatim>", "category": "<the matched rule\'s category>", '
                    '"replacement": "[REDACTED]", "method": "REDACT", '
                    '"rule_id": "<id of the rule that matched, e.g. CONV-006 or RED-DFLT-001>", '
                    '"ref_ids": ["REF-0006"]}]}')
        if self.name.startswith("EDITOR"):
            return ('{"agent": "' + self.name + '", "doc_id": "<id>", "items": ['
                    '{"ref": "REF-0003", "kind": "editorial_observation", "confidence": "CONFIDENT", '
                    '"verdict": "concern", '
                    '"rationale": "<prose: e.g. amendment 2 restates convention CONV-004 without adding analysis; '
                    'consider merging it with amendment 1 or cutting it for necessity>", '
                    '"ref_ids": ["REF-0003"]}]}')
        if self.contract.get("field_forms"):
            # structure H2b: an agent whose contract declares field forms gets a
            # FILLED example rather than a three-field stub, so the shape it is
            # being asked for is unmistakable. Built from this agent's own
            # required list, so it cannot drift from the contract.
            filled = {
                "location": "REF-0001",
                "convention_ref": "CONV-007",
                "original_text": "<the exact words being amended, copied verbatim>",
                "proposed_text": "<the replacement, or null to flag only>",
                "action": "flag",
                "comment": ("<why this is an issue> Grounded in CONV-007 at REF-0001."),
                "finding_type": "factual",
                "severity": "required",
                "ref_ids": ["REF-0001"],
            }
            item = {"ref": "REF-0001", "kind": self.contract.get("item_kind", "finding").split()[0],
                    "confidence": "CONFIDENT"}
            for key in self.contract.get("required", []):
                if key in filled:
                    item[key] = filled[key]
            item.setdefault("ref_ids", filled["ref_ids"])
            return json.dumps({"agent": self.name, "doc_id": "<id>", "items": [item]},
                              ensure_ascii=False)
        return ('{"agent": "' + self.name + '", "doc_id": "<id>", "items": ['
                '{"ref": "REF-0001", "kind": "finding", "confidence": "CONFIDENT", "ref_ids": ["REF-0001"]}]}')

    def _role_anchor_text(self) -> str:
        """local D4: role anchoring / identity reinforcement (never "prompt injection",
        W7), appended last, immediately before generation, on the local profile only.
        GENERATED from existing definitions, never hand-written per agent: identity is
        self.name; the single job is self.spec["does"][0] (config/agent_registry.json,
        this agent's first and primary capability); the envelope shape is this agent's
        own item_kind and required fields (config/agent_contracts.json) -- the SAME two
        values _output_contract_text() already renders, so there is one source of truth
        and no hardcoded duplicate can drift from it. required is used rather than the
        worked-example renderer because the worked example is a static, mostly-generic
        template for non-REDACTOR/EDITOR agents (see _worked_item_example): it would not
        visibly change if a plain agent's contract fields changed, and this anchor must.
        No domain content (S5): role, job, and shape only. Short by design: an anchor,
        not a second system prompt.

        D4 SECOND PASS (smallest additional change, sanctioned by the depth.md D4 spec):
        a real INST_FINDER measurement (5 trials before, 5 after, local Qwen2.5-7B-Instruct)
        found anchoring alone did not clearly help: naive pipeline scoring read 2/5 held
        before vs 4/5 after, but two of the four "after" successes had resolved to a
        trivially-valid EMPTY envelope (items: []) emitted before real content, which
        parse_contract_output's tolerant recovery accepts as a complete, non-violating
        result and never looks further -- confirmed directly against the actual recovery
        code. Corrected for that, GENUINE content-bearing holds were 2/5 both before and
        after: no real improvement, and a new failure mode (premature empty-item hedging)
        appeared. The one-item worked example below is built from THIS agent's own
        item_kind/required (already read above), not the static, mostly-generic
        _worked_item_example renderer, so it is non-empty, concrete, and still
        contract-derived rather than hand-written."""
        if getattr(self, "_compact_contract", None):
            return "\nComplete the task-specific compact JSON contract above.\n"
        does = self.spec.get("does") or []
        job = does[0] if does else "carry out this run's assigned task"
        item_kind = self.contract.get("item_kind", "finding")
        required = self.contract.get("required", [])
        example_fields = "".join(f', "{f}": "<{f}>"' for f in required)
        worked_example = (
            f'{{"agent": "{self.name}", "doc_id": "<id>", "items": [{{"ref": "REF-0001", '
            f'"kind": "{item_kind}", "confidence": "CONFIDENT"{example_fields}, '
            f'"ref_ids": ["REF-0001"]}}]}}'
        )
        return (
            f"\n\n## Final reminder\nYou are {self.name}. Your single job right now: {job}. "
            f'Return ONLY the canonical envelope: {{"agent": "{self.name}", "doc_id": "<id>", '
            f'"items": [...]}}. Each item\'s kind is \'{item_kind}\'; it MUST include: '
            f"{required} (plus the core fields ref, kind, confidence, ref_ids). "
            f"An empty items list means you found nothing after checking every document; "
            f"do not use it as a shortcut. Worked example with one real item: {worked_example}\n"
        )

    def prompt_template(self, context_text, work):
        does = getattr(self, "_compact_role", None) or "\n".join(f"- {d}" for d in self.spec.get("does", []))
        does_not = "\n".join(f"- {d}" for d in self.spec.get("does_not", []))
        directives = self.contract.get("directives") or []
        work_str = work if isinstance(work, str) else json.dumps(work, ensure_ascii=False, indent=2)
        directives_block = ""
        if directives:
            directives_block = "## Directives (from contract)\n" + "\n".join(
                f"- {d}" for d in directives
            ) + "\n\n"
        return (f"You are {self.name}, a Project Shimmer agent.\n\n"
                f"## You DO\n{does}\n\n"
                f"## You DO NOT (LAW-II)\n{does_not}\n\n"
                f"{directives_block}"
                f"{self._execution_instructions()}\n\n"
                f"## Context\n{context_text}\n\n"
                f"{self._output_contract_text()}\n"
                f"## Work payload\n{work_str}\n")

    def _stable_agent_block(self) -> str:
        """The per-agent STABLE prompt block: identity + DO/DO-NOT + directives +
        output contract. Identical across this agent's calls within a run; carries
        no per-call/dynamic content. Same text as the corresponding parts of
        prompt_template (only relocated to the front for caching)."""
        does = getattr(self, "_compact_role", None) or "\n".join(f"- {d}" for d in self.spec.get("does", []))
        does_not = "\n".join(f"- {d}" for d in self.spec.get("does_not", []))
        directives = self.contract.get("directives") or []
        directives_block = ""
        if directives:
            directives_block = "## Directives (from contract)\n" + "\n".join(
                f"- {d}" for d in directives
            ) + "\n\n"
        return (f"You are {self.name}, a Project Shimmer agent.\n\n"
                f"## You DO\n{does}\n\n"
                f"## You DO NOT (LAW-II)\n{does_not}\n\n"
                f"{directives_block}"
                f"{self._output_contract_text()}")

    def _execution_instructions(self):
        options = run_options.for_context(self.run_context)
        brief = agent_briefs.render(self.name, self.spec, self.contract) if options.agent_briefs == "enabled" else ""
        return (brief + "\n\n" if brief else "") + run_options.instruction(options)

    def build_prompt(self, pkg, work):
        """Cache-structured prompt as (stable_prefix, dynamic_suffix), INFRA-036.

        stable_prefix = agent stable block, execution brief, language and constitution, the
        largest identical-across-calls block, with NO dynamic content. It is the
        explicit cache breakpoint on the Claude path and the auto-cached prefix on
        the GPT path. dynamic_suffix = per-call context (objectives, precedents,
        retrieved passages, recent bus) + the work payload.

        Same information as prompt_template(pkg.as_text(), work), only reordered
        stable-first (constitution/conventions and the output contract move ahead
        of the per-call sections)."""
        work_str = work if isinstance(work, str) else json.dumps(work, ensure_ascii=False, indent=2)
        stable = self._stable_agent_block()
        stable += "\n\n" + self._execution_instructions()
        st = pkg.stable_text()
        if st:
            stable = stable + "\n## Context\n" + st
        # local D3b: pkg.dynamic_sections() already carries a WORK_PAYLOAD entry
        # (ContextPackage.as_prompt_sections() appends one unconditionally). Joining it
        # wholesale via pkg.dynamic_text() and then appending work_str below duplicated
        # the entire work payload in every prompt, on every backend, since commit
        # 862dbaa. Exclude it here so the "## Work payload" block below is the one place
        # it appears; every other dynamic section is untouched (same join format as
        # ContextPackage.dynamic_text()).
        dyn_sections = [(h, b) for h, b in pkg.dynamic_sections() if h != "WORK_PAYLOAD"]
        dyn = "\n\n".join(f"=== {h} ===\n{b}" for h, b in dyn_sections)
        dynamic = (dyn + "\n\n" if dyn else "") + f"## Work payload\n{work_str}\n"
        return stable, dynamic

    def _dump_prompt_breakdown(self, pkg, stable_prefix, dynamic_suffix, truncation):
        """Write a prompt anatomy file to <run_dir>/logs/prompt_dump_<AGENT>.json when
        SHIMMER_DUMP_PROMPTS=1 (local D2). Records per-section sizes BEFORE and AFTER
        truncation, so the dump answers what the budget CUT and not merely what survived.
        Counts only: no prompt text and no document text is ever written (W8)."""
        run_dir = os.environ.get("SHIMMER_OUTPUT_DIR")
        if not run_dir:
            return None
        log_dir = Path(run_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        bodies = {"agent_identity": self._stable_agent_block()}
        for header, body in pkg.as_prompt_sections():
            bodies[header] = body

        sections = {}
        unclassified = []
        scaffold_tokens = material_tokens = 0
        for name, body in bodies.items():
            klass = PROMPT_SECTION_CLASS.get(name)
            if klass is None:
                unclassified.append(name)
            tok = _estimate_tokens(body) if body else 0
            entry = {"chars": len(body), "tokens": tok, "class": klass or "UNCLASSIFIED"}
            t = truncation.get(name)
            if t:
                entry.update({"before_chars": t["before_chars"], "after_chars": t["after_chars"],
                              "cut_chars": t["cut_chars"], "budget_tokens": t["budget_tokens"],
                              "truncated": t["truncated"]})
            else:
                # No budget applies to this section, so nothing was cut assembling it.
                entry.update({"before_chars": len(body), "after_chars": len(body),
                              "cut_chars": 0, "budget_tokens": None, "truncated": False})
            sections[name] = entry
            if klass == "scaffold":
                scaffold_tokens += tok
            elif klass == "material":
                material_tokens += tok

        classified = scaffold_tokens + material_tokens
        scaffold_pct = round(scaffold_tokens / classified * 100, 1) if classified else 0.0
        assembled_chars = len(stable_prefix) + len(dynamic_suffix)
        dump = {
            "agent": self.name,
            "backend": self.backend,
            "sections": sections,
            "unclassified_sections": unclassified,
            "scaffold_tokens_est": scaffold_tokens,
            "material_tokens_est": material_tokens,
            "classified_tokens_est": classified,
            "scaffold_pct": scaffold_pct,
            # Complement by construction, so the two always sum to exactly 100.
            "material_pct": round(100.0 - scaffold_pct, 1),
            "total_cut_chars": sum(s["cut_chars"] for s in sections.values()),
            "stable_prefix_chars": len(stable_prefix),
            "dynamic_suffix_chars": len(dynamic_suffix),
            "assembled_total_chars": assembled_chars,
            "assembled_total_tokens_est": _estimate_tokens(stable_prefix + dynamic_suffix),
            # Section headers and payload framing added by build_prompt, not owned by
            # any single section. Disclosed rather than folded into a category.
            "framing_overhead_chars": assembled_chars - sum(s["chars"] for s in sections.values()),
            # WORK_PAYLOAD reaches assemble_context ALREADY clipped by the pipeline's
            # character-based _truncate, which this layer cannot observe. See the D2
            # report for the six pipeline.py clip sites.
            "work_payload_pipeline_clip_visible": False,
        }
        out_path = log_dir / f"prompt_dump_{self.name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(dump, f, indent=2, ensure_ascii=False)
        return out_path

    @generation_observation.observe
    @agent_activation.observe_task
    def run_task(self, *, work_payload, run_objectives="", channel="main",
                 recipient="ORCHESTRATOR", recent_bus_limit=30, max_tokens=4096,
                 relevant_precedent_ids=None, convention_registry=None,
                 reference_index_excerpt=None, phase="", doc_id="",
                 items_are_advisory=False, activation=None):
        """`items_are_advisory` marks a call whose reply is NOT the record.

        In paired mode the model is asked one narrow question about one unit
        and one rule, and PYTHON mints the typed Finding from its own
        arithmetic; the model's sentence is used as the explanation and nothing
        else. The reply's own items are therefore an opinion, not a record, and
        posting them as typed findings put 23 unattributed findings on the bus
        of the 2026-09-11 clean run, carrying no rule_id and no unit_id, which
        cannot be checked, cited or scored. Two of them were plainly false
        (a Class-B entry that carries a signature called missing one; a reading
        of 112 inside a 90 to 130 range called a violation).

        With this set the envelope is still posted, with its item_count,
        parse_trace and truncated intact, so nothing about the call is hidden:
        only the ITEMS are withheld from the bus, because a caller that mints
        its own records is the author of the record."""
        situation = {"agent": self.name, "action": "execute_task",
                     "tags": ["task_execution", self.spec.get("category", "")]}
        check = self.check_constitution(situation)
        # local D2: capture what each budget CUT while the package is assembled.
        # Off unless SHIMMER_DUMP_PROMPTS=1, so default behavior is unchanged.
        dump_prompts = os.environ.get("SHIMMER_DUMP_PROMPTS") == "1"
        if dump_prompts:
            begin_truncation_capture()
        try:
            pkg = assemble_context(
                backend=self.backend, constitution=self.constitution, bus=self.bus,
                work_payload=work_payload, run_objectives=run_objectives,
                relevant_precedent_ids=relevant_precedent_ids, channel=channel,
                recent_bus_limit=recent_bus_limit,
                convention_registry=convention_registry,
                reference_index_excerpt=reference_index_excerpt,
            )
        finally:
            truncation = end_truncation_capture() if dump_prompts else {}
        # Cache-structured prompt (INFRA-036): stable prefix first, dynamic suffix
        # last, so Claude (explicit cache_control) and GPT (automatic prefix cache)
        # both reuse the stable prefix across calls.
        stable_prefix, dynamic_suffix = self.build_prompt(pkg, work_payload)
        if dump_prompts:
            self._dump_prompt_breakdown(pkg, stable_prefix, dynamic_suffix, truncation)
        # LAW-IV outbound masking (INFRA-041 P2, chokepoint 1): mask the assembled prompt
        # UPSTREAM of dispatch, for NETWORK backends under sensitive mode (qwen_local is
        # exempt: local hardware is the sanctioned sensitive handler). The injected masker
        # owns the network/exempt/may_handle_sensitive decision; when none is injected (the
        # default, and every non-sensitive run) this is a no-op and the prompt is unchanged.
        if self.outbound_masker is not None:
            stable_prefix, dynamic_suffix = self.outbound_masker(
                stable_prefix, dynamic_suffix, backend=self.backend, agent=self.name)
        # local D4: role anchoring, LOCAL PROFILE ONLY. Appended here, after masking, so
        # it is the LAST text added to dynamic_suffix before dispatch: small local models
        # weight the end of the prompt most, so the anchor belongs at the true end, not
        # merely near it. Off by default (cloud path byte-for-byte unchanged, W5).
        if os.environ.get("SHIMMER_BACKEND_PROFILE") == "local":
            dynamic_suffix = dynamic_suffix + self._role_anchor_text()
        # Per-agent token ceiling override from contract (e.g., ARCHIVIST=4096
        # to fit the corpus-level structural inventory). The contract's
        # max_output_tokens wins over the caller-supplied max_tokens because
        # agents with structural output requirements (inventories, large
        # lists) know better than callers what they need.
        contract_max = self.contract.get("max_output_tokens")
        if isinstance(contract_max, int) and contract_max > 0:
            max_tokens = max(max_tokens, contract_max)
        # FOUR: measured local extraction needs more output space than the
        # general production default. A local-only declaration keeps cloud
        # budgets unchanged until there is evidence from that backend.
        if self.backend in ("qwen_local", "local_producer", "local_auditor"):
            local_contract_max = self.contract.get("local_max_output_tokens")
            if isinstance(local_contract_max, int) and local_contract_max > 0:
                max_tokens = max(max_tokens, local_contract_max)
        bounded_budget = getattr(self, "_bounded_output_budget", None)
        if bounded_budget is not None:
            max_tokens = bounded_budget
        # Call evidence (scripts/call_evidence.py): the prompt below is about to be
        # sent and then dropped, so this is the one point that knows everything the
        # call was shown. Record the STRUCTURAL identifiers of it (unit, neighbours,
        # heading, references, rules, model, backend, run, a fresh call id), never
        # the text, under <run>/logs/call_evidence.jsonl. The same call id goes on
        # this call's cost row and on the bus post it produces, so the three saved
        # artifacts join. A write failure is logged and never takes the call down.
        call_id = uuid.uuid4().hex
        self._generation_call_id = call_id
        self._requested_output_budget = min(max_tokens, LOCAL_MAX_OUTPUT_TOKENS) if self.backend in (
            "qwen_local", "local_producer", "local_auditor") else max_tokens
        try:
            run_options.record_prompt(self.run_context, call_id, self.name, stable_prefix, dynamic_suffix)
        except OSError as exc:
            log_event(_LOG, "prompt_structure_write_error error_type=" + type(exc).__name__, level="warning")
        try:
            evidence_written = call_evidence.record(self.run_context, call_evidence.extract(
                work_payload, call_id=call_id,
                run_id=getattr(self.run_context, "run_id", "") or "",
                phase=phase or "", doc_id=doc_id or "", agent=self.name,
                backend=self.backend, model=self.model or "",
                convention_registry=convention_registry,
                reference_index_excerpt=reference_index_excerpt,
                prompt_chars=len(stable_prefix) + len(dynamic_suffix),
                rendered=getattr(pkg, "rendered", None)))
        except Exception as e:  # never fail a call for its own bookkeeping
            evidence_written = None
            log_event(_LOG, f"call_evidence_write_error error_type={type(e).__name__}",
                      level="warning", agent=self.name,
                      run_id=getattr(self.run_context, "run_id", "") or "")
        # productization STEP 4: cost dimensions. _cost_phase/_cost_doc_id are
        # transient instance state, read by _record_cost (called from inside
        # dispatch -> call_claude/call_gpt/call_qwen, each of which also times
        # its own SDK call into _cost_duration_ms) and cleared in the finally
        # block so they never leak into an unrelated later call on the same
        # wrapper instance. _cost_call_id joins the cost row to the evidence record.
        self._cost_phase = phase or ""
        self._cost_doc_id = doc_id or ""
        self._cost_call_id = call_id
        try:
            if self.backend in ("qwen_local", "local_producer", "local_auditor"):
                # Job B: the blanket 1024 ceiling this used to apply to every
                # local call regardless of type is gone. It was never a
                # measured content requirement (see call_qwen's own comment:
                # it exists to bound wall time, decoding speed being roughly
                # constant), and on real evidence it was cutting several call
                # types before they finished (9 of 16 calls on one run hit it
                # exactly, several producing zero usable items). The caller
                # now sets a budget sized to what that call type is shown to
                # need (pipeline.py's call sites); LOCAL_MAX_OUTPUT_TOKENS is
                # the backstop. It permits PROCESSOR's measured allowance and
                # the editorial board's configured 8192-token request.
                result = agent_activation.call_dispatch(self, call_id, stable_prefix, dynamic_suffix,
                                       max_new_tokens=min(max_tokens, LOCAL_MAX_OUTPUT_TOKENS))
            else:
                result = agent_activation.call_dispatch(self, call_id, stable_prefix, dynamic_suffix,
                                                        max_tokens=max_tokens)
        finally:
            self._cost_phase = ""
            self._cost_doc_id = ""
            self._cost_call_id = ""
        if not result.ok:
            self.post_to_bus(recipient=recipient, channel=channel, msg_type="YIELD",
                             body={"event": "BACKEND_ERROR", "backend": result.backend, "model": result.model,
                                   "error": result.error, "call_id": call_id},
                             constitution_check=self.build_constitution_check(
                                 laws_consulted=["LAW-V"], result="RESOLVED",
                                 resolution="agent yielded on backend error"))
            return {"ok": False, "agent": self.name, "backend": result.backend, "model": result.model,
                    "parsed": None, "raw_text": "", "contract_missing": [], "error": result.error,
                    "call_id": call_id, "call_evidence_path": str(evidence_written) if evidence_written else None}
        # Backends preserve true/false/unknown completeness. Transport success
        # does not establish contract validity or semantic acceptance.
        truncated = result.usage.get("truncated")
        parsed, missing = self.parse_contract_output(result.raw_text)
        self._observed_contract_valid = parsed is not None and not missing
        if getattr(self, "_optimized_semantics", False) and truncated is not False:
            missing = list(missing) + ["response completeness not established"]
        if parsed is None or missing:
            # Persist the full raw_text to disk so post-mortem analysis can
            # recover what the model actually produced. The bus message keeps
            # only a 400-char excerpt for readability; the full text lives at
            # <run_dir>/audit/contract_violations/{agent}_{timestamp}.txt.
            raw_text_path = self._persist_contract_violation_raw_text(
                result.raw_text, missing
            )
            self.post_to_bus(
                recipient=recipient, channel=channel, msg_type="CHALLENGE",
                body={
                    "event": "CONTRACT_VIOLATION",
                    "backend": result.backend, "model": result.model,
                    "missing_fields": missing,
                    "raw_excerpt": result.raw_text[:400],
                    "raw_text_path": str(raw_text_path) if raw_text_path else None,
                    "raw_text_bytes": len(result.raw_text.encode("utf-8")) if result.raw_text else 0,
                    "truncated": truncated,
                    "call_id": call_id,
                },
                constitution_check=self.build_constitution_check(
                    laws_consulted=["LAW-II"], result="RESOLVED",
                    resolution="agent output did not match contract"
                ),
            )
            return {"ok": False, "agent": self.name, "backend": result.backend, "model": result.model,
                    "parsed": parsed, "raw_text": result.raw_text, "contract_missing": missing,
                    "raw_text_path": str(raw_text_path) if raw_text_path else None,
                    "error": "contract_violation", "truncated": truncated,
                    "parse_trace": dict(self.last_parse_trace),
                    "call_id": call_id, "call_evidence_path": str(evidence_written) if evidence_written else None}
        # First task (post-D4): a contract-valid empty envelope (items: []) is a
        # legitimate "nothing to report" hold (INFRA-037; verify_session1.py:1005-1008
        # asserts this must stay accepted) and must keep recording ok=True/error=None
        # here, unchanged. But until now it was recorded IDENTICALLY to a populated
        # hold: same shape, no field distinguishing the two. D4's own measurement
        # (agent_wrapper.py:946-958, "Corrected reading") found this let two hollow
        # empty-envelope passes count as INST_FINDER holding its contract while real
        # content sitting right behind them in the same raw text was discarded and
        # never counted. item_count is purely additive (no existing key changed), so
        # every consumer keying off ok/error/contract_missing (e.g. pipeline.py:1162)
        # is unaffected, and this runs identically on every backend (dispatch has
        # already returned by this point, so the cloud path is byte-identical).
        item_count = len(parsed.get("items", []))
        # structure H2a: the recovery trace travels with the output. Counts only,
        # never text (W8), so it is safe in the append-only bus.
        parse_trace = dict(self.last_parse_trace)
        # Job B: a response that PARSED cleanly can still be an incomplete
        # answer, when the cut landed exactly at the end of a complete item
        # and the model had more items still to write. The envelope carries
        # no field for "and there was more"; truncated=True on an ok result
        # says the item_count above may undercount what the agent actually
        # had to report, without inventing a number for what was lost. A
        # caller that treats a truncated hold as a complete "nothing to
        # report" would be parsing a cut answer as though it were whole,
        # which is exactly what this flag exists to prevent.
        # An advisory reply's ITEMS are withheld from the bus: the caller mints
        # the record from its own arithmetic and the model's items are an
        # opinion, not a finding. Everything else about the call is posted
        # unchanged, so the call is still fully on the record.
        posted_payload = parsed
        if items_are_advisory and isinstance(parsed, dict):
            posted_payload = dict(parsed)
            posted_payload["items"] = []
            posted_payload["items_withheld"] = item_count
            posted_payload["items_withheld_reason"] = (
                "advisory reply: the caller mints the typed record from its own "
                "arithmetic, so these items are an opinion and not a finding")
        self.post_to_bus(recipient=recipient, channel=channel, msg_type="INFORM",
                         body={"event": "AGENT_OUTPUT", "backend": result.backend, "model": result.model,
                               "item_count": item_count, "parse_trace": parse_trace,
                               "truncated": truncated,
                               "payload": posted_payload, "call_id": call_id},
                         constitution_check=self.build_constitution_check(
                             laws_consulted=["LAW-V"],
                             result=check.layer or ("RESOLVED" if check.resolved else "RESOLVED"),
                             resolution=(f"governed by {check.rule_id}" if check.resolved
                                         else "no governing rule yet; novel action recorded")))
        return {"ok": True, "agent": self.name, "backend": result.backend, "model": result.model,
                "parsed": parsed, "raw_text": result.raw_text, "contract_missing": [], "error": None,
                "item_count": item_count, "parse_trace": parse_trace, "truncated": truncated,
                "call_id": call_id, "call_evidence_path": str(evidence_written) if evidence_written else None}
