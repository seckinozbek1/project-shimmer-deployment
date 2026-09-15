"""Ordinary local comparison path with explicit sibling context and ordered posts."""
import asyncio
import copy
from dataclasses import replace
from functools import wraps
import inspect
import math
import json
from pathlib import Path
import generation_observation

import bounded_extraction as extraction
import execution_topology as topology
from execution_scheduler import Edge, Task
from message_bus import MessageBus


class WaveBus(MessageBus):
    def __init__(self, live, snapshot):
        self.live, self.snapshot, self.posts = live, snapshot, []

    def read_all(self):
        return copy.deepcopy(self.snapshot)

    def post(self, message):
        validated = self.live._validate(message)
        self.posts.append(validated)
        return validated


def enabled():
    return bool(getattr(topology.ACTIVE.get(), "optimized", False))


def validate_model_families(profile, resolve_checkpoint):
    families={"local_producer":set(),"local_auditor":set()}
    for backend,model in set(profile.values()):
        if backend not in families:
            continue
        config=json.loads((Path(resolve_checkpoint(model))/"config.json").read_text(encoding="utf-8"))
        family=config.get("model_type")
        if not isinstance(family,str) or not family:
            raise ValueError("Cannot establish local model family")
        families[backend].add(family)
    if not all(families.values()) or families["local_producer"] & families["local_auditor"]:
        raise ValueError("LAW-III requires independently established producer and auditor families")
    return {k:sorted(v) for k,v in families.items()}


def exact_comparison_plan(plan):
    """Only already-computed unconditional numeric defects need no prose call.

This consumes the existing planner's typed proof. It does not classify text,
decide scope, or replace conditional interpretation or independent auditing.
"""
    if plan.get("kind") not in {"computed", "band"} or not plan.get("checks"):
        return False
    for check in plan["checks"]:
        if check.get("agrees") is True:
            continue
        if check.get("agrees") is not False or check.get("conditional_on"):
            return False
        if check.get("relation") not in {"sum_mismatch", "product_mismatch", "above_band", "below_band"}:
            return False
        if not check.get("basis") or not (check.get("ref_id") or check.get("ref_ids")):
            return False
        values = [check.get("computed")]
        values += [check["stated"]] if check.get("stated") is not None else [check.get("band_low"),check.get("band_high")]
        if any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) for x in values):
            return False
    return any(c.get("agrees") is False for c in plan["checks"])


def run_wave(runtime, calls, reason):
    """A complete sibling group, one wrapper per call, no shared model replicas.

Governance checks still run in every wrapper. No sibling consumes another's
output. Source and parent results are supplied explicitly before admission.
All receipts, including failures, publish in source order after the wave drains.
"""
    if not calls:
        return []
    if len({id(w) for w,k in calls}) != len(calls):
        raise ValueError("A wave requires distinct wrapper instances")
    if any(w.backend not in {"local_producer", "local_auditor"} for w,k in calls):
        raise ValueError("Optimized waves are local only")
    with runtime.lock:
        live = calls[0][0].bus
        if any(w.bus is not live for w,k in calls):
            raise ValueError("Wave calls must share one run bus")
        snapshot = live.read_all()
        start = len(runtime.scheduler.tasks)
        wave_id = "wave-%06d" % start
        parents = getattr(runtime, "frontier", ()) or ((runtime.previous,) if runtime.previous else ())
        tasks, proxies = [], []
        for offset, (wrapper, kwargs) in enumerate(calls):
            task_id = "task-%06d" % (start + offset)
            proxy = WaveBus(live, snapshot)
            proxies.append(proxy)
            def action(context, w=wrapper, k=kwargs, bus=proxy):
                old_bus = w.bus
                w.bus = bus
                w._observation_task = context.task.id
                w._observation_lane = context.worker.lane.name
                w._observation_wave = wave_id
                topology.WORK.context = context
                try:
                    return w._reference_run_task(**k)
                finally:
                    w.bus = old_bus
                    topology.WORK.context = None
            tasks.append(Task(task_id, action, sequence=start+offset, agent=wrapper.name,
                              phase=str(kwargs.get("phase", "")), document=str(kwargs.get("doc_id", "")),
                              model=wrapper.model, family=wrapper.backend,
                              memory_gib=float(wrapper.spec.get("execution_memory_gib", 0)),
                              edges=tuple(Edge(p, reason, False) for p in parents)))
        try:
            outcomes = runtime.scheduler.run(tasks)
        finally:
            for proxy in proxies:
                for message in proxy.posts:
                    live.post(message)
            runtime.frontier = tuple(t.id for t in tasks)
            runtime.previous = tasks[-1].id
            runtime.write()
        results = []
        for task in tasks:
            result = outcomes[task.id]
            if result.state not in {"completed", "refused"}:
                if result.exception is not None:
                    raise result.exception
                raise RuntimeError("Semantic wave task " + result.state)
            results.append(result.value)
        return results


class PlannedCall:
    def __init__(self, function, args, kwargs):
        self.function, self.args, self.kwargs = function, args, kwargs
        self.bound = inspect.signature(function).bind(*args, **kwargs)
        self.bound.apply_defaults()

    def __await__(self):
        async def single():
            if enabled() and self.bound.arguments["wrapper"].name == "PROCESSOR" and "document_text" in self.bound.arguments["work_payload"]:
                return (await execute_plans([self]))[0]
            return await self.function(*self.args, **self.kwargs)
        return single().__await__()

    def close(self):
        pass


def planned(function):
    @wraps(function)
    def call(*args, **kwargs):
        plan = PlannedCall(function, args, kwargs)
        return plan
    return call


def call_kwargs(plan):
    a = plan.bound.arguments
    progress = a.get("_progress")
    payload = a["work_payload"]
    return dict(work_payload=payload, run_objectives=a["run_objectives"], channel=a["channel"],
                max_tokens=a["max_tokens"], convention_registry=a["convention_registry"],
                reference_index_excerpt=a["reference_index_excerpt"],
                phase=str(progress[0]) if progress else "",
                doc_id=str(payload.get("document_id") or (a["activation"] or {}).get("doc_id") or
                           (progress[1] if progress else "") or ""),
                items_are_advisory=a["items_are_advisory"], activation=a["activation"])


async def execute_plans(plans):
    runtime = topology.ACTIVE.get()
    calls, groups = [], []
    for plan in plans:
        progress=plan.bound.arguments.get("_progress")
        if progress:
            phase,doc,docs,agent=progress
            plan.function.__globals__["_emit_progress"](phase=phase,doc=doc,docs=docs,agent=agent,status="running")
    for plan in plans:
        w = plan.bound.arguments["wrapper"]
        k = call_kwargs(plan)
        base = k["work_payload"]
        begin = len(calls)
        if w.name == "PROCESSOR" and "document_text" in base:
            cache_hits=extraction.ledger.cache_info().hits
            spans = extraction.ledger(base["document_text"], base.get("document_id", ""))
            generation_observation.append(w.run_context, dict(
                schema_version=1, event="source_ledger", document_id=base.get("document_id", ""),
                source_hash=extraction.digest(base["document_text"]),
                input_dependency_fingerprint=extraction.digest([base, k["run_objectives"], k["convention_registry"], k["reference_index_excerpt"],
                                                   w.contract, w.model, [w.constitution.seed_laws(),w.constitution.amendments(),
                                                             w.constitution.precedents(),w.constitution.task_force_laws()]]),
                spans=[dict(id=s.id,start=s.start,end=s.end,unit_id=s.unit_id,unit_index=s.unit_index)
                       for s in spans], semantic_cache_reused=False,
                deterministic_ledger_cache_hit=extraction.ledger.cache_info().hits>cache_hits,
                semantic_reuse_key_complete=False))
            for owned in extraction.partitions(spans):
                clone = runtime.attach(replace(w))
                clone._bounded_output_budget = 1536
                import compact_contracts
                compact_contracts.bind_producer(clone, owned, base.get("document_id", ""))
                calls.append((clone, dict(k, work_payload=extraction.payload(base,owned,spans))))
        else:
            calls.append((w,k))
        groups.append((begin,len(calls),w.name,base.get("document_id", "")))
    # Scheduler admission is bounded. Keep one shared snapshot per admitted wave.
    if len(calls) > runtime.scheduler.max_pending:
        raise ValueError("Extraction exceeds bounded wave admission; no source silently omitted")
    results = await asyncio.to_thread(run_wave, runtime, calls, "explicit_parent_results_and_wave_snapshot")
    # Retry a technical partition failure once; never retry semantic refusal/empty.
    retries=0
    for i, ((w,k),r) in enumerate(zip(calls,results)):
        if not hasattr(w,"_source_adapter") or r.get("ok"):
            continue
        if isinstance(r.get("parsed"),dict) and r["parsed"].get("items") == []:
            continue
        if r.get("truncated") is True or r.get("error") == "contract_violation":
            w._partition_attempt = 1
            w._partition_retry_reason = "truncation" if r.get("truncated") else "malformed_contract"
            results[i] = (await asyncio.to_thread(run_wave,runtime,[(w,k)],"failed_partition_only"))[0]
            retries+=1
    out = []
    for plan,(begin,end,name,doc_id) in zip(plans,groups):
        if name == "PROCESSOR" and (begin == end or hasattr(calls[begin][0],"_source_adapter")):
            merged=extraction.merge(results[begin:end],doc_id)
            wrapper=plan.bound.arguments["wrapper"]
            merged.update(backend=wrapper.backend,model=wrapper.model,raw_text="",
                          contract_missing=[] if merged["ok"] else ["incomplete_partition_coverage"])
            if not merged["ok"]:
                generation_observation.mark_incomplete(runtime.run_context)
            generation_observation.append(runtime.run_context,dict(event="extraction_merge",doc_id=doc_id,
                complete=merged["complete"],item_count=merged["item_count"],
                missing_partitions=merged["missing_partitions"],partition_calls=merged["partition_calls"]))
            out.append(merged)
        else:
            out.append(results[begin])
    if plans:
        scope=plans[0].function.__globals__
        if scope.get("_is_local_profile",lambda:False)() and "_LOCAL_PROGRESS_LOCK" in scope:
            with scope["_LOCAL_PROGRESS_LOCK"]:
                scope["_LOCAL_PROGRESS"]["completed"]+=len(calls)+retries
                scope["_LOCAL_PROGRESS"]["expected"]=max(scope["_LOCAL_PROGRESS"]["expected"],scope["_LOCAL_PROGRESS"]["completed"])
            scope["_emit_local_progress"](event="semantic_wave_done",physical_calls=len(calls)+retries,
                                            completed=scope["_LOCAL_PROGRESS"]["completed"])
    for plan in plans:
        progress=plan.bound.arguments.get("_progress")
        if progress:
            phase,doc,docs,agent=progress
            plan.function.__globals__["_emit_progress"](phase=phase,doc=doc,docs=docs,agent=agent,status="done")
    return out


def gather(function):
    @wraps(function)
    async def run(tasks):
        if enabled() and tasks and all(isinstance(t,PlannedCall) for t in tasks):
            return await execute_plans(tasks)
        return await function(tasks)
    return run
