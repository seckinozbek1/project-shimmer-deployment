"""Explicit adapters around the preserved reference pipeline.

Reference review calls retain their rolling-bus completion chain. The explicit
report_optimized path uses semantic_waves to admit inspected sibling groups with
shared starting context and ordered publication. Worker ownership is common.
"""
from __future__ import annotations

from contextvars import ContextVar
from functools import wraps
import json
import inspect
from pathlib import Path
import threading

from execution_scheduler import Edge, Lane, Scheduler, Task

ACTIVE = ContextVar("shimmer_execution_topology", default=None)
WORK = threading.local()


def rebind_run(run_context):
    runtime = ACTIVE.get()
    if runtime is not None:
        runtime.run_context = run_context


def reference_prewarm_enabled():
    """A DAG worker loads on demand; never race the old global GPU-0 cache."""
    return ACTIVE.get() is None


def artifact_stamp(timestamp):
    context = getattr(WORK, "context", None)
    return timestamp + "_" + context.task.id if context is not None else timestamp


def read_lanes(path):
    if path is None:
        # One explicitly assigned device, one resident at a time. Operator opts
        # into larger residency/multiple lanes using measured memory headroom.
        return [Lane("primary", device="cuda:0")]
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(value) != {"schema_version", "lanes"} or value["schema_version"] != 1:
        raise ValueError("Invalid topology configuration")
    lanes = []
    for item in value["lanes"]:
        item = dict(item)
        for key in ("models", "families"):
            if key in item:
                item[key] = tuple(item[key])
        lanes.append(Lane(**item))
    if not any(l.enabled and not l.auxiliary for l in lanes):
        raise ValueError("An enabled primary lane is required")
    # Sharing a device across separate residency owners could overcommit memory.
    # Multiple models on one GPU use one lane with a configured resident_limit.
    devices = [l.device for l in lanes if l.enabled and l.device != "cpu"]
    if len(devices) != len(set(devices)):
        raise ValueError("Use one residency owner per CUDA device")
    return lanes


class Runtime:
    def __init__(self, lanes):
        self.scheduler = Scheduler(lanes)
        self.lock = threading.RLock()
        self.previous = None
        self.frontier = ()
        self.optimized = False
        self.run_context = None
        self.written = 0

    def write(self):
        if self.run_context is None:
            return
        directory = self.run_context.audit_dir()
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "execution_topology.jsonl").open("a", encoding="utf-8") as stream:
            for event in self.scheduler.events[self.written:]:
                stream.write(json.dumps(event, sort_keys=True) + "\n")
        self.written = len(self.scheduler.events)
        summary = dict(schema_version=1, execution_topology="report_optimized" if self.optimized else "dependency_dag",
                       run_id=self.run_context.run_id, **self.scheduler.summary())
        path = directory / "execution_topology.json"
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)

    def attach(self, wrapper):
        original = wrapper.run_task
        wrapper._reference_run_task = original
        wrapper._optimized_semantics = self.optimized
        original_dispatch = wrapper.dispatch
        self.run_context = wrapper.run_context

        @wraps(original_dispatch)
        def dispatch(*args, **kwargs):
            context = getattr(WORK, "context", None)
            if context is None:
                return original_dispatch(*args, **kwargs)
            context.event("dispatch_start", call_id=getattr(wrapper, "_cost_call_id", ""))
            try:
                return original_dispatch(*args, **kwargs)
            finally:
                context.event("dispatch_end")

        @wraps(original)
        def call(*args, **kwargs):
            # Context assembly, evidence, contract parsing and the bus post form
            # ONE ordered transaction. No global lock on unrelated schedulers.
            with self.lock:
                number = len(self.scheduler.tasks)
                task_id = f"task-{number:06d}"
                payload = kwargs.get("work_payload", args[0] if args else {})
                payload = payload if isinstance(payload, dict) else {}
                finding = payload.get("finding", {})
                parent = finding.get("item_id", "") if isinstance(finding, dict) else ""
                activation = kwargs.get("activation") or {}
                parent = (activation.get("evidence") or {}).get("item_id", parent)
                parents = self.frontier or ((self.previous,) if self.previous else ())
                edges = tuple(Edge(p, "rolling_bus_visibility_and_governance_order", False) for p in parents)
                def action(context):
                    WORK.context = context
                    wrapper._observation_task = context.task.id
                    wrapper._observation_lane = context.worker.lane.name
                    wrapper._observation_wave = "serial-" + context.task.id
                    try:
                        return original(*args, **kwargs)
                    finally:
                        WORK.context = None
                task = Task(task_id, action, sequence=number, agent=wrapper.name,
                            phase=str(kwargs.get("phase") or activation.get("source_phase") or payload.get("task", "")),
                            document=str(kwargs.get("doc_id") or payload.get("document_id", "")),
                            model=wrapper.model, family=wrapper.backend, edges=edges,
                            memory_gib=float(getattr(wrapper, "spec", {}).get("execution_memory_gib", 0)),
                            parent_finding=str(parent))
                result = self.scheduler.run([task])[task_id]
                self.previous = task_id
                self.frontier = (task_id,)
                self.write()
                if result.state in {"completed", "refused"}:
                    return result.value
                if result.exception is not None:
                    raise result.exception
                raise RuntimeError("Execution task " + result.state + ": " + (result.error_type or task_id))
        wrapper.run_task = call
        wrapper.dispatch = dispatch
        return wrapper

    def close(self):
        try:
            self.scheduler.close()
        finally:
            self.write()


def wrapper_factory(function):
    @wraps(function)
    def build(*args, **kwargs):
        wrapper = function(*args, **kwargs)
        runtime = ACTIVE.get()
        return runtime.attach(wrapper) if runtime is not None else wrapper
    return build


def ordered_calls(function):
    @wraps(function)
    async def gather(tasks):
        if ACTIVE.get() is None:
            return await function(tasks)
        # Creation order is the reference local order, never completion order.
        try:
            return [await task for task in tasks]
        finally:
            for task in tasks:
                if hasattr(task, "close"):
                    task.close()
    return gather


def ordered_documents(function):
    @wraps(function)
    async def gather(op_docs, process_doc, max_concurrent_docs):
        if ACTIVE.get() is None:
            return await function(op_docs, process_doc, max_concurrent_docs)
        return [await process_doc(doc) for doc in op_docs]
    return gather


def phase_boundary(function):
    """Record existing barriers without moving context-dependent CPU work."""
    def begin():
        runtime = ACTIVE.get()
        if runtime is not None:
            runtime.scheduler.emit("phase_enter", phase=function.__name__,
                                   required_tasks=list(runtime.scheduler.tasks),
                                   reason="prior_phase_results_bus_and_governance_must_be_complete")
        return runtime
    def finish(runtime, state):
        if runtime is not None:
            runtime.scheduler.emit("phase_exit", phase=function.__name__, state=state)
            runtime.write()
    if inspect.iscoroutinefunction(function):
        @wraps(function)
        async def asynchronous(*args, **kwargs):
            runtime, state = begin(), "failed"
            try:
                result = await function(*args, **kwargs)
                state = "completed"
                return result
            finally:
                finish(runtime, state)
        return asynchronous
    @wraps(function)
    def synchronous(*args, **kwargs):
        runtime, state = begin(), "failed"
        try:
            result = function(*args, **kwargs)
            state = "completed"
            return result
        finally:
            finish(runtime, state)
    return synchronous


def entrypoint(function):
    @wraps(function)
    def run(argv=None):
        # Locate the original module's parser through the completion decorator.
        target = function
        while hasattr(target, "__wrapped__"):
            target = target.__wrapped__
        parser = target.__globals__["_build_arg_parser"]()
        args = parser.parse_args(argv)
        if args.execution_topology == "reference_serial":
            if args.topology_config:
                parser.error("--topology-config requires --execution-topology dependency_dag")
            return function(argv)
        if args.task != "review" or args.multi_round or args.multi_round_manifest:
            parser.error("dependency_dag currently supports ordinary Review; multi-round remains separately gated")
        try:
            lanes = read_lanes(args.topology_config)
        except (OSError, ValueError, TypeError):
            parser.error("Invalid topology lane configuration")
        import agent_wrapper
        if agent_wrapper._QWEN_MODELS:
            parser.error("dependency_dag requires a fresh process without a reference model cache")
        if args.execution_topology == "report_optimized" and getattr(args, "backend_profile", None) != "local":
            parser.error("report_optimized requires explicit --backend-profile local")
        if args.execution_topology == "report_optimized":
            import semantic_waves
            try:
                semantic_waves.validate_model_families(target.__globals__["_LOCAL_PROFILE"],
                                                       agent_wrapper._local_checkpoint_path)
            except (OSError, ValueError, KeyError):
                parser.error("Cannot establish independent cached local model families")
        runtime = Runtime(lanes)
        runtime.optimized = args.execution_topology == "report_optimized"
        token = ACTIVE.set(runtime)
        try:
            return function(argv)
        finally:
            try:
                runtime.close()
            finally:
                ACTIVE.reset(token)
    return run


def resident_model(model_id):
    """None outside a worker. Preserve the checkpoint and reference quantisation.

    No model import occurs until an authorized runtime calls this function.
    Each lane owns its own cache and initializes it on its dedicated thread.
    """
    context = getattr(WORK, "context", None)
    if context is None:
        return None
    worker = context.worker
    if model_id in worker.residents:
        context.event("model_resident", model=model_id)
        return worker.residents[model_id]
    import importlib
    import gc
    import agent_wrapper
    context.checkpoint()
    context.event("model_load_start", model=model_id, reload=worker.loads.get(model_id, 0) > 0)
    try:
        torch = importlib.import_module("torch")
        transformers = importlib.import_module("transformers")
        device = worker.lane.device
        if device.startswith("cuda:"):
            index = int(device.split(":")[1])
            if not torch.cuda.is_available() or index >= torch.cuda.device_count():
                raise RuntimeError("Configured CUDA device unavailable")
            torch.cuda.set_device(index)
            if hasattr(torch.cuda, "mem_get_info"):
                free, total = torch.cuda.mem_get_info(index)
                context.event("device_memory", free_bytes=int(free), total_bytes=int(total))
        checkpoint = agent_wrapper._local_checkpoint_path(model_id)
        if len(worker.residents) >= worker.lane.resident_limit:
            evicted = next(iter(worker.residents))
            del worker.residents[evicted]
            gc.collect()
            if device.startswith("cuda:"):
                torch.cuda.empty_cache()
            context.event("model_evicted", model=evicted)
        tokenizer = transformers.AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
        options = {"local_files_only": True}
        if device.startswith("cuda:"):
            options["device_map"] = {"": index}
            if not agent_wrapper._checkpoint_is_prequantised(transformers, checkpoint):
                options["quantization_config"] = transformers.BitsAndBytesConfig(
                    load_in_4bit=True, bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
        else:
            options["torch_dtype"] = torch.float16
        model = transformers.AutoModelForCausalLM.from_pretrained(checkpoint, **options)
        # Generation events bracket the actual generate call, not load/tokenize.
        generate = model.generate
        def measured_generate(*args, **kwargs):
            active = getattr(WORK, "context", None)
            if active is None:
                raise RuntimeError("Resident model used outside its owner")
            active.checkpoint()
            active.event("generation_start", model=model_id)
            try:
                return generate(*args, **kwargs)
            finally:
                active.event("generation_end", model=model_id)
        model.generate = measured_generate
        worker.residents[model_id] = tokenizer, model
        worker.loads[model_id] = worker.loads.get(model_id, 0) + 1
        context.event("model_load_end", model=model_id, resident_models=sorted(worker.residents))
        return worker.residents[model_id]
    except Exception:
        worker.healthy = False
        context.event("worker_unhealthy", reason="model_initialization_failed", model=model_id)
        raise
