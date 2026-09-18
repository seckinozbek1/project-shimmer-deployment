"""Payload-free generation and acceptance evidence, including unknowns."""
from functools import wraps
import hashlib
import json
import threading
import time
import model_telemetry

_LOCK = threading.RLock()


def local_stop(last_token, eos_ids, output_tokens, requested):
    ids = eos_ids if isinstance(eos_ids, (list, tuple, set)) else [eos_ids]
    if last_token in [x for x in ids if x is not None]:
        return "eos", False
    if output_tokens >= requested:
        return "length", True
    return "unknown", None


def append(context, row):
    if context is None:
        return
    path = context.logs_dir() / "generation_observation.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True) + "\n")


def mark_incomplete(context):
    if context is not None:
        context.semantic_incomplete = True


def observe(function):
    @wraps(function)
    def run(self, *args, **kwargs):
        started = time.perf_counter()
        started_at = model_telemetry.now()
        self._telemetry_phase = kwargs.get('phase')
        self._generation_usage = {}
        self._backend_timing = {}
        self._observed_contract_valid = None
        self._generation_call_id = None
        self._requested_output_budget = None
        result = None
        error_type = None
        location = {}
        try:
            result = function(self, *args, **kwargs)
            import auditor_pairs
            auditor_pairs.stamp_ownership(self, result)
            auditor_pairs.compare(self, result)
            result["generation"] = dict(self._generation_usage)
            if getattr(self,"_optimized_semantics",False) and not hasattr(self,"_source_adapter") and not result.get("ok"):
                mark_incomplete(getattr(self,"run_context",None))
            return result
        except BaseException as exc:
            error_type = type(exc).__name__
            # Same payload-free identity the backend receipt carries: class
            # module, raising frame, innermost project frame. No message text.
            location = {"error_" + k.split("_", 1)[1]: v
                        for k, v in model_telemetry.failure_location(exc).items()}
            raise
        finally:
            u = self._generation_usage
            r = result or {}
            items = (r.get("parsed") or {}).get("items", []) if isinstance(r.get("parsed"), dict) else []
            accepted = bool(r.get("ok")) and u.get("truncated") is False
            row = dict(schema_version=1, agent=self.name, backend=self.backend, model=self.model,
                       call_id=r.get("call_id") or self._generation_call_id, task_id=getattr(self, "_observation_task", None),
                       wave_id=getattr(self, "_observation_wave", None),
                       lane=getattr(self, "_observation_lane", None),
                       phase=kwargs.get("phase"), doc_id=kwargs.get("doc_id"),
                       total_call_seconds=time.perf_counter()-started,
                       backend_success=u.get("backend_success"), input_tokens=u.get("input_tokens"),
                       output_tokens=u.get("output_tokens"),
                       requested_max_output_tokens=u.get("requested_max_output_tokens",self._requested_output_budget),
                       finish_reason=u.get("finish_reason"), truncated=u.get("truncated"),
                       generation_seconds=u.get("generation_seconds"),
                       time_to_first_token_seconds=u.get("time_to_first_token_seconds"),
                       complete_response=None if u.get("truncated") is None else not u["truncated"],
                       contract_valid=self._observed_contract_valid,
                       accepted_semantic_output=accepted, output_item_count=len(items),
                       useful_accepted_item_count=len(items) if accepted and not kwargs.get("items_are_advisory") else 0,
                       useful_accepted_tokens=None, semantic_quality="unmeasured",
                       retry_count=getattr(self, "_partition_attempt", 0) if self.backend in
                           {"local_producer","local_auditor","qwen_local"} else u.get("backend_retry_count"),
                       retry_reason=getattr(self, "_partition_retry_reason", None),
                       error_type=error_type, resource_sample_link="audit/execution_topology.jsonl:task_id",
                       **location)
            row.update(u)
            append(getattr(self, "run_context", None), row)
            model_telemetry.call_record(self, result, started, started_at, error_type)
    return run


def prompt_identity(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
