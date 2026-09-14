"""Bounded task/replica scheduler. No model, provider, or network imports.

Actions run on dedicated lane threads. Actions with side effects must cooperate
with cancellation; staged results can instead use the coordinator-owned commit.
Timeouts drain running actions, never release a device while work still runs.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
import time


class Backpressure(RuntimeError):
    pass


class Cancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class Edge:
    parent: str
    reason: str
    require_success: bool = True


@dataclass(frozen=True)
class Lane:
    name: str
    device: str = "cpu"
    models: tuple = ()
    families: tuple = ()
    memory_gib: float = 0
    resident_limit: int = 1
    enabled: bool = True
    auxiliary: bool = False
    transport: str = "in_process"

    def __post_init__(self):
        if not self.name or self.resident_limit < 1 or self.memory_gib < 0:
            raise ValueError("Invalid lane capability")
        if self.device != "cpu" and not (self.device.startswith("cuda:") and self.device[5:].isdigit()):
            raise ValueError("Device must be cpu or an explicit cuda index")
        if self.transport not in {"in_process", "remote_reserved"}:
            raise ValueError("Unknown worker transport")
        if self.transport == "remote_reserved" and (self.enabled or not self.auxiliary):
            raise ValueError("Remote transport is reserved, disabled and auxiliary only")


@dataclass(frozen=True)
class Task:
    id: str
    action: object
    sequence: int = 0
    agent: str = ""
    phase: str = ""
    document: str = ""
    model: str = ""
    family: str = ""
    edges: tuple = ()
    memory_gib: float = 0
    preferred: tuple = ()
    priority: int = 0
    timeout_s: float | None = None
    allow_auxiliary: bool = False
    commit: object = None
    kind: str = "semantic"
    parent_finding: str = ""


@dataclass
class Outcome:
    state: str
    value: object = None
    error_type: str | None = None
    exception: object = field(default=None, repr=False)


class Worker:
    def __init__(self, lane, emit):
        self.lane, self.emit = lane, emit
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="shimmer-" + lane.name)
        self.residents = {}
        self.loads = {}
        self.healthy = True
        self.busy = False
        self.last_end = time.perf_counter()

    def close(self):
        # Residency is destroyed on its owning thread, after all work is drained.
        def release():
            import gc
            import sys
            self.residents.clear()
            gc.collect()
            torch = sys.modules.get("torch")
            if self.loads and torch is not None and self.lane.device.startswith("cuda:"):
                torch.cuda.set_device(int(self.lane.device.split(":")[1]))
                torch.cuda.empty_cache()
        try:
            self.pool.submit(release).result()
        finally:
            self.pool.shutdown(wait=True, cancel_futures=True)
            self.healthy = False


class TaskContext:
    def __init__(self, worker, task, stop, emit):
        self.worker, self.task, self.stop, self.emit = worker, task, stop, emit

    def checkpoint(self):
        if self.stop.is_set():
            raise Cancelled()

    def event(self, event, **fields):
        self.emit(event, task=self.task.id, worker=self.worker.lane.name,
                  device=self.worker.lane.device, **fields)


class Scheduler:
    def __init__(self, lanes, *, max_pending=256, sink=None):
        lanes = list(lanes)
        if not lanes or len({x.name for x in lanes}) != len(lanes) or max_pending < 1:
            raise ValueError("Invalid scheduler capacity or lane identities")
        self.max_pending, self.sink = max_pending, sink
        self.events, self.tasks, self.outcomes = [], {}, {}
        self._event_lock, self._run_lock = threading.RLock(), threading.RLock()
        self.workers = [Worker(x, self.emit) for x in lanes]
        self._inflight = {}
        self.closed = False
        self.emit("scheduler_started", lanes=[x.name for x in lanes])

    def emit(self, event, **fields):
        with self._event_lock:
            record = dict(event=event, monotonic_s=time.perf_counter(), event_index=len(self.events), **fields)
            record["utc"] = datetime.now(timezone.utc).isoformat()
            self.events.append(record)
            if self.sink is not None:
                self.sink(record)

    def _compatible(self, worker, task):
        lane = worker.lane
        return (worker.healthy and lane.enabled and lane.transport == "in_process"
                and (not lane.auxiliary or task.allow_auxiliary)
                and (not lane.models or task.model in lane.models)
                and (task.memory_gib == 0 or lane.memory_gib >= task.memory_gib)
                and (task.kind != "cpu" or lane.device == "cpu"))

    def _validate(self, tasks):
        ids = [t.id for t in tasks]
        if len(ids) != len(set(ids)) or set(ids) & self.tasks.keys():
            raise ValueError("Duplicate task identity")
        if len(tasks) > self.max_pending:
            raise Backpressure("Batch exceeds bounded ready queue; no task accepted")
        known = set(ids) | self.outcomes.keys()
        order = {t.id: t.sequence for t in tasks}
        for task in tasks:
            if not task.id or any(e.parent not in known or not e.reason for e in task.edges):
                raise ValueError("Missing dependency or edge reason")
            if any(e.parent in order and order[e.parent] >= task.sequence for e in task.edges):
                raise ValueError("Logical sequence must respect dependencies")
            if task.timeout_s is not None and task.timeout_s <= 0:
                raise ValueError("Timeout must be positive")
        remaining = {t.id: {e.parent for e in t.edges} - self.outcomes.keys() for t in tasks}
        while remaining:
            ready = {k for k, parents in remaining.items() if not parents}
            if not ready:
                raise ValueError("Dependency cycle")
            remaining = {k: parents - ready for k, parents in remaining.items() if k not in ready}

    def run(self, tasks, *, cancel=None):
        with self._run_lock:
            try:
                return self._run(tasks, cancel=cancel)
            except BaseException:
                # An interrupted coordinator cannot leave a lane reusable while an
                # action still runs. Drain, mark the admission terminal, then raise.
                for future, (task, worker, stop, assigned) in list(self._inflight.items()):
                    stop.set()
                for future, (task, worker, stop, assigned) in list(self._inflight.items()):
                    try:
                        future.result()
                    except BaseException:
                        pass
                    worker.busy, worker.last_end = False, time.perf_counter()
                self._inflight.clear()
                for key in self.tasks.keys() - self.outcomes.keys():
                    self.outcomes[key] = Outcome("interrupted")
                raise

    def _run(self, tasks, *, cancel=None):
        """One bounded graph admission. Results/commits use explicit logical order.

        Dependencies may reference an earlier drained batch. Failed completion
        edges remain traversable; success edges block. There are no retries.
        """
        with self._run_lock:
            if self.closed:
                raise RuntimeError("Scheduler closed")
            tasks = list(tasks)
            self._validate(tasks)
            if len({t.sequence for t in tasks}) != len(tasks):
                raise ValueError("Task sequences must be unique within a batch")
            admitted = time.perf_counter()
            pending = {t.id: t for t in tasks}
            self.tasks.update(pending)
            for task in tasks:
                self.emit("queued", task=task.id, sequence=task.sequence, agent=task.agent,
                          phase=task.phase, document=task.document, model=task.model,
                          kind=task.kind, parent_finding=task.parent_finding,
                          edges=[dict(parent=e.parent, reason=e.reason, require_success=e.require_success) for e in task.edges])
            running, ready_at, terminal_override = self._inflight, {}, {}
            committed = set()
            ordered = sorted(tasks, key=lambda t: (t.sequence, t.id))
            def publish_ready():
                for task in ordered:
                    if task.id in committed:
                        continue
                    if task.id not in self.outcomes:
                        break
                    result = self.outcomes[task.id]
                    if task.commit is not None and result.state == "completed":
                        try:
                            task.commit(result.value)
                        except Exception as exc:
                            self.outcomes[task.id] = Outcome("failed", error_type=type(exc).__name__)
                    committed.add(task.id)
                    self.emit("committed", task=task.id, state=self.outcomes[task.id].state)
            while pending or running:
                now = time.perf_counter()
                cancelled = cancel is not None and cancel.is_set()
                for future, (task, worker, stop, assigned) in list(running.items()):
                    if cancelled or (task.timeout_s is not None and now - assigned >= task.timeout_s):
                        terminal_override[task.id] = "cancelled" if cancelled else "timed_out"
                        stop.set()
                for task in sorted(list(pending.values()), key=lambda t: (-t.priority, t.sequence, t.id)):
                    if cancelled:
                        self.outcomes[task.id] = Outcome("cancelled")
                        del pending[task.id]
                        continue
                    if not all(e.parent in self.outcomes for e in task.edges):
                        continue
                    if any(e.require_success and self.outcomes[e.parent].state != "completed" for e in task.edges):
                        self.outcomes[task.id] = Outcome("blocked")
                        del pending[task.id]
                        continue
                    # Commit parents before consumers see their accepted evidence.
                    publish_ready()
                    if any(e.require_success and self.outcomes[e.parent].state != "completed" for e in task.edges):
                        self.outcomes[task.id] = Outcome("blocked")
                        del pending[task.id]
                        continue
                    if any(e.parent in {t.id for t in tasks} and e.parent not in committed for e in task.edges):
                        continue
                    if task.id not in ready_at:
                        ready_at[task.id] = now
                        self.emit("ready", task=task.id, dependency_wait_s=now-admitted,
                                  barrier_wait_s=now-admitted if task.kind == "barrier" else 0)
                    compatible = [w for w in self.workers if self._compatible(w, task)]
                    if not compatible:
                        self.outcomes[task.id] = Outcome("unavailable")
                        del pending[task.id]
                        continue
                    free = [w for w in compatible if not w.busy]
                    if not free:
                        continue
                    worker = min(free, key=lambda w: (w.lane.name not in task.preferred,
                                 task.family not in w.lane.families, task.model not in w.residents, w.lane.name))
                    worker.busy = True
                    stop = threading.Event()
                    self.emit("assigned", task=task.id, worker=worker.lane.name, device=worker.lane.device,
                              scheduler_wait_s=now-ready_at[task.id], worker_idle_s=now-worker.last_end,
                              concurrent_tasks=len(running)+1, ready_queue_depth=len(pending), priority=task.priority)
                    context = TaskContext(worker, task, stop, self.emit)
                    future = worker.pool.submit(self._execute, task, context)
                    running[future] = task, worker, stop, now
                    del pending[task.id]
                if running:
                    done, _ = wait(running, timeout=0.01, return_when=FIRST_COMPLETED)
                    for future in done:
                        task, worker, stop, assigned = running.pop(future)
                        worker.busy, worker.last_end = False, time.perf_counter()
                        outcome = future.result()
                        if cancel is not None and cancel.is_set():
                            terminal_override[task.id] = "cancelled"
                        elif task.timeout_s is not None and worker.last_end - assigned >= task.timeout_s:
                            terminal_override[task.id] = "timed_out"
                        if task.id in terminal_override:
                            outcome = Outcome(terminal_override[task.id])
                        self.outcomes[task.id] = outcome
                        self.emit("finished", task=task.id, state=outcome.state,
                                  error_type=outcome.error_type, drained=True)
                publish_ready()
            publish_ready()
            return {t.id: self.outcomes[t.id] for t in ordered}

    @staticmethod
    def _execute(task, context):
        context.event("task_start")
        try:
            context.checkpoint()
            value = task.action(context)
            context.checkpoint()
            state = "refused" if isinstance(value, dict) and value.get("ok") is False else "completed"
            return Outcome(state, value)
        except Cancelled:
            return Outcome("cancelled")
        except Exception as exc:
            return Outcome("failed", error_type=type(exc).__name__, exception=exc)
        finally:
            context.event("task_end")

    def summary(self):
        starts, durations, paths, lengths = {}, {}, {}, {}
        for event in self.events:
            if event["event"] == "task_start":
                starts[event["task"]] = event["monotonic_s"]
            if event["event"] == "task_end":
                durations[event["task"]] = event["monotonic_s"] - starts[event["task"]]
        pending = dict(self.tasks)
        while pending:
            for key, task in list(pending.items()):
                if any(e.parent not in lengths for e in task.edges):
                    continue
                parent = max((e.parent for e in task.edges), key=lambda p: lengths[p], default=None)
                lengths[key] = durations.get(key, 0) + (lengths[parent] if parent else 0)
                paths[key] = (paths[parent] if parent else []) + [key]
                del pending[key]
        end = max(lengths, key=lengths.get, default=None)
        return {"critical_path": paths[end] if end else [], "critical_path_service_s": lengths[end] if end else 0,
                "task_count": len(self.tasks), "states": {k: v.state for k, v in self.outcomes.items()},
                "interpretation": "Observed task-service weighted dependency path, excludes queue gaps; not a speedup claim"}

    def close(self):
        with self._run_lock:
            if not self.closed:
                errors = []
                for worker in self.workers:
                    try:
                        worker.close()
                    except Exception as exc:
                        errors.append(exc)
                self.closed = True
                self.emit("scheduler_closed", errors=[type(e).__name__ for e in errors], **self.summary())
                if errors:
                    raise errors[0]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
