"""Ordinary local comparison path with explicit sibling context and ordered posts."""
import asyncio
import copy
from dataclasses import replace
from functools import wraps
import inspect
import math
import json
from pathlib import Path
import decoding_policy
import generation_observation
import reply_records

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


# The relations Python computes to a figure on both sides, so a disagreeing check of one of them
# needs no prose call. Open item 78, D-S57 item 1 (lane/auditor): RELATIONS-A's four relations are
# computed the same way (relation_checks, every figure read from the units' own text) and joined
# them; before, a rate, copy, carry or unit plan still made one judging call whose note was the
# only thing it could add.
EXACT_RELATIONS = ("sum_mismatch", "product_mismatch", "above_band", "below_band",
                   "rate_mismatch", "copy_mismatch", "carry_mismatch", "unit_mismatch")


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
        if check.get("relation") not in EXACT_RELATIONS:
            return False
        if not check.get("basis") or not (check.get("ref_id") or check.get("ref_ids")):
            return False
        values = [check.get("computed")]
        values += [check["stated"]] if check.get("stated") is not None else [check.get("band_low"),check.get("band_high")]
        if any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) for x in values):
            return False
    return any(c.get("agrees") is False for c in plan["checks"])


def _admissible(calls):
    if len({id(w) for w,k in calls}) != len(calls):
        raise ValueError("A wave requires distinct wrapper instances")
    if any(w.backend not in {"local_producer", "local_auditor"} for w,k in calls):
        raise ValueError("Optimized waves are local only")
    live = calls[0][0].bus
    if any(w.bus is not live for w,k in calls):
        raise ValueError("Wave calls must share one run bus")
    return live


def _parents(runtime):
    return getattr(runtime, "frontier", ()) or ((runtime.previous,) if runtime.previous else ())


def run_wave(runtime, calls, reason, snapshot=None, parents=None):
    """A complete sibling group, one wrapper per call, no shared model replicas.

Governance checks still run in every wrapper. No sibling consumes another's
output. Source and parent results are supplied explicitly before admission.
All receipts, including failures, publish in source order after the wave drains.
A chunk of a larger gather passes the gather's own snapshot and parents (run_waves);
with neither passed both are read here, as for every wave below the bound.
"""
    if not calls:
        return []
    with runtime.lock:
        live = _admissible(calls)
        snapshot = live.read_all() if snapshot is None else snapshot
        start = len(runtime.scheduler.tasks)
        wave_id = "wave-%06d" % start
        parents = _parents(runtime) if parents is None else parents
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


def run_waves(runtime, calls, reason):
    """D-076 (INC-019): a gather over the scheduler's bound runs as consecutive waves
of at most max_pending calls, in source order, never refused. Every chunk shares the
ONE snapshot and the ONE parent set read before the first, so no sibling in any chunk
sees another sibling's posts. Each chunk's posts publish after it drains, so the bus
still receives them in source order; the next wave depends on every chunk's tasks.
A gather at or below the bound is exactly one run_wave, as before.
"""
    bound = runtime.scheduler.max_pending
    if len(calls) <= bound:
        return run_wave(runtime, calls, reason)
    with runtime.lock:
        snapshot = _admissible(calls).read_all()
        parents = _parents(runtime)
        results, frontier = [], ()
        for begin in range(0, len(calls), bound):
            results += run_wave(runtime, calls[begin:begin+bound], reason, snapshot, parents)
            frontier += runtime.frontier
        runtime.frontier = frontier
        runtime.write()
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


RETRY_SKIPPED_DETERMINISTIC = "retry_skipped_deterministic"


def skip_deterministic_retry(runtime, wrapper, result, reason):
    """D-061 (c), P13: a failed partition whose call decoded deterministically (greedy, one
    beam: decoding_policy.deterministic on the kwargs the call recorded) is not retried, since
    the same request can only repeat the same reply (L2: 9 of 9 retries reproduced their request
    and reply bytes). The skip is recorded on the generation observation and as the call's reply
    outcome, `retry_skipped_deterministic`, with the reason the retry would have had; the
    partition's failure stands. Returns True when the retry is skipped."""
    kwargs = (result.get("generation") or {}).get("decoding_kwargs")
    if not decoding_policy.deterministic(kwargs):
        return False
    context = getattr(runtime, "run_context", None) or getattr(wrapper, "run_context", None)
    generation_observation.append(context, dict(
        event="partition_retry_skipped", outcome=RETRY_SKIPPED_DETERMINISTIC, retry_skipped_deterministic=True,
        retry_reason=reason, call_id=result.get("call_id"), agent=getattr(wrapper, "name", None),
        doc_id=result.get("doc_id") or getattr(wrapper, "_cost_doc_id", "") or ""))
    reply_records.write_outcome(context, result.get("call_id"), RETRY_SKIPPED_DETERMINISTIC,
                                source="semantic_waves", retry_reason=reason)
    return True


REFUSAL_MARK = "refusal is not acceptance"   # compact_contracts.envelope's refusal of a refusal object
CHANGED_INPUT_RETRY = "changed_input_retry"


def partition_refused(result):
    """The validator refused the reply as a refusal object (compact_contracts.envelope)."""
    return any(REFUSAL_MARK in str(m) for m in (result.get("contract_missing") or []))


def retry_plan(spans, owned, result):
    """D-575, D-577: the changed-input retry of one failed PROCESSOR partition, decided from
    its owned spans and how it failed, before any call. Returns (kind, [(request, keep)]) where
    each request is the owned spans of one new call and `keep` the spans whose items stand,
    or (reason, []) when no retry with other input exists. Never three spans: every request
    is one or two spans, the shape checkpoint 168's DEV rows carry (EXTRACTION-C).
      - a refused or truncated two-span request: one call per span;
      - a refused one-span request: that span with the span before it, keeping only its own
        items (post_only_kept; the span before keeps its first answer);
      - a truncated one-span request, or a refused first span: no smaller or other input."""
    truncated, refused = result.get("truncated") is True, partition_refused(result)
    if result.get("ok") or not (truncated or refused):
        return "not_failed", []
    if len(owned) >= 2:
        return "split_to_single_spans", [((s,), (s,)) for s in owned]
    if refused and not truncated:
        ids = [s.id for s in spans]
        at = ids.index(owned[0].id)
        if at == 0:
            return "retry_not_possible_first_span", []
        return "with_previous_span", [((spans[at - 1], owned[0]), tuple(owned))]
    return "retry_not_possible_single_span_cap", []


def post_only_kept(clone, keep):
    """Before the re-ask is dispatched: its validated items are cut to the `keep` spans inside
    the source adapter, so the reply's envelope, its bus post and its ownership receipts carry
    the refused span's items alone. The span before keeps its first answer, which is already on
    the bus; posting it again at the same revision would put one item id there twice.

    The ownership the call is decoded and validated under (`_owned_source_spans`, which the
    decoding constraint reads, and the adapter's own two spans, which hydrate requires in full)
    stays the whole request: the cut comes only after hydration. D-634: narrowing it to the kept
    span held the model to one item while hydrate required both, so every honest re-ask failed
    "Incomplete partition coverage" (5 of 5 ContraDoc re-asks of the 15 November quick read).
    The receipts (auditor_pairs.stamp_ownership) are made from the cut items, so they name the
    kept span alone."""
    ids = {s.id for s in keep}
    adapter = clone._source_adapter

    def kept(obj):
        out = adapter(obj)
        return dict(out, items=[i for i in out.get("items", []) if i.get("source_span_id") in ids])
    clone._source_adapter = kept


VERIFIER_HALVES = "verifier_halves"


def verifier_halves(wrapper, kwargs):
    """D-575, D-577 (#246): the two halves of a VERIFIER call's own input, or None when it has
    fewer than two draft items. The producer delivery's items are split in two in their order;
    each half carries its own items, the ownership receipts of those items alone and the draft
    view of the same items, so every pair is built and seen in exactly one half."""
    request = getattr(wrapper, "_auditor_pair_request", None)
    payload = kwargs.get("work_payload") or {}
    producer = (request or {}).get("producer") or {}
    items = list(((producer.get("parsed") or {}).get("items")) or [])
    if request is None or len(items) < 2:
        return None
    middle = len(items) // 2
    halves = []
    for part in (items[:middle], items[middle:]):
        ids = {i.get("item_id") for i in part}
        half_producer = dict(producer, parsed=dict(producer["parsed"], items=part),
                             source_ownership=[e for e in producer.get("source_ownership", []) if e.get("producer_item_id") in ids])
        half_payload = dict(payload)
        draft = payload.get("processor_draft")
        if isinstance(draft, dict) and isinstance(draft.get("items"), list):
            half_payload["processor_draft"] = dict(draft, items=[i for i in draft["items"]
                                                                 if not isinstance(i, dict) or i.get("item_id") in ids])
        halves.append((dict(request, producer=half_producer), half_payload))
    return halves


def merged_halves(wrapper, first, second):
    """One result from the two halves: their items together, held to the agent's unchanged
    validator; incomplete when either half failed, was truncated or the whole is invalid."""
    ok = all(r.get("ok") and r.get("truncated") is False for r in (first, second))
    items = [i for r in (first, second) for i in ((r.get("parsed") or {}).get("items") or [])]
    parsed = dict(first.get("parsed") or {}, items=items)
    missing = wrapper._contract_missing(parsed) if ok else ["verifier_half_incomplete"]
    return dict(first, ok=ok and not missing, parsed=parsed, truncated=any(r.get("truncated") is True for r in (first, second)),
                contract_missing=missing, error=None if ok and not missing else "contract_violation",
                half_calls=[first.get("call_id"), second.get("call_id")])


async def changed_input_retry(runtime, calls, results, groups):
    """Each failed PROCESSOR partition gets at most one retry whose input differs from the
    first ask (retry_plan); deterministic decoding would repeat a same-input re-ask byte for
    byte (D-061). A valid partition is never asked again. Every decision is one generation
    observation (`changed_input_retry`) with the original call, the kind, the request sizes
    and each new call's outcome. Returns the calls, results and groups with each retried
    partition replaced by its new requests, and the number of new calls."""
    import compact_contracts
    out_calls, out_results, out_groups, made = [], [], [], 0
    for begin, end, name, doc_id in groups:
        start = len(out_calls)
        for i in range(begin, end):
            w, k = calls[i]
            r = results[i]
            meta = getattr(w, "_retry_meta", None)
            if meta is None and w.name == "VERIFIER" and r.get("truncated") is True and not r.get("ok"):
                halves = verifier_halves(w, k)
                generation_observation.append(runtime.run_context, dict(
                    event=CHANGED_INPUT_RETRY, kind=VERIFIER_HALVES if halves else "retry_not_possible_one_item",
                    call_id=r.get("call_id"), doc_id=doc_id))
                if halves:
                    done = []
                    for request, payload in halves:
                        clone = runtime.attach(replace(w))
                        clone._auditor_pair_request = request
                        clone._partition_retry_reason = VERIFIER_HALVES
                        done.append((await asyncio.to_thread(run_wave, runtime, [(clone, dict(k, work_payload=payload))],
                                                             CHANGED_INPUT_RETRY))[0])
                        made += 1
                    r = merged_halves(w, *done)
                    generation_observation.append(runtime.run_context, dict(
                        event=CHANGED_INPUT_RETRY + "_call", kind=VERIFIER_HALVES, retry_of=results[i].get("call_id"),
                        call_ids=r["half_calls"], doc_id=doc_id, ok=bool(r["ok"]), truncated=r["truncated"],
                        contract_missing=r["contract_missing"]))
                out_calls.append((w, k))
                out_results.append(r)
                continue
            kind, pieces = retry_plan(meta["spans"], meta["owned"], r) if meta else ("not_partition", [])
            if kind != "not_failed" and meta:
                generation_observation.append(runtime.run_context, dict(
                    event=CHANGED_INPUT_RETRY, kind=kind, call_id=r.get("call_id"), doc_id=doc_id,
                    owned_spans=[s.id for s in meta["owned"]], requests=[[s.id for s in q] for q, _ in pieces]))
            if not pieces:
                out_calls.append((w, k))
                out_results.append(r)
                continue
            base, spans = meta["base"], meta["spans"]
            for request, keep in pieces:
                clone = runtime.attach(replace(meta["wrapper"]))
                clone._bounded_output_budget = 1536
                system, user, citable, supplied = compact_contracts.validated_messages(
                    base["document_text"], request, spans, meta["kwargs"].get("reference_index_excerpt") or [])
                compact_contracts.bind_producer(clone, request, base.get("document_id", ""),
                                                citable=citable, messages=(system, user, supplied))
                clone._partition_retry_reason = kind
                if tuple(keep) != tuple(request):
                    post_only_kept(clone, keep)
                kwargs = dict(meta["kwargs"], work_payload=json.loads(user))
                new = (await asyncio.to_thread(run_wave, runtime, [(clone, kwargs)], CHANGED_INPUT_RETRY))[0]
                made += 1
                kept = new
                generation_observation.append(runtime.run_context, dict(
                    event=CHANGED_INPUT_RETRY + "_call", kind=kind, retry_of=r.get("call_id"), call_id=new.get("call_id"),
                    doc_id=doc_id, request=[s.id for s in request], kept=[s.id for s in keep],
                    ok=bool(kept.get("ok")), truncated=kept.get("truncated"), contract_missing=kept.get("contract_missing")))
                out_calls.append((clone, kwargs))
                out_results.append(kept)
        out_groups.append((start, len(out_calls), name, doc_id))
    return out_calls, out_results, out_groups, made


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
            import compact_contracts
            # Requests carry the validated number of owned spans (one or two), read
            # from the declaration; the four-span default is never used on this path.
            for owned in extraction.partitions(spans, compact_contracts.request_size()):
                clone = runtime.attach(replace(w))
                clone._bounded_output_budget = 1536
                # The validated prompt shape (config/compact_extraction_prompt.json):
                # the contract as the system message, one canonical payload as the
                # user message, indexed passages marked with their own ids. The
                # work payload recorded for the call is that user object, so the
                # call evidence names exactly the keys the model was sent.
                system, user, citable, supplied = compact_contracts.validated_messages(
                    base["document_text"], owned, spans, k.get("reference_index_excerpt") or [])
                compact_contracts.bind_producer(clone, owned, base.get("document_id", ""),
                                                citable=citable, messages=(system, user, supplied))
                clone._retry_meta = dict(wrapper=w, kwargs=k, base=base, spans=spans, owned=tuple(owned))
                calls.append((clone, dict(k, work_payload=json.loads(user))))
        else:
            calls.append((w,k))
        groups.append((begin,len(calls),w.name,base.get("document_id", "")))
    # Scheduler admission is bounded: an over-bound gather runs as consecutive waves
    # sharing one snapshot and one parent set, every call admitted once (D-076).
    results = await asyncio.to_thread(run_waves, runtime, calls, "explicit_parent_results_and_wave_snapshot")
    # Retry a technical partition failure once; never retry semantic refusal/empty.
    retries=0
    for i, ((w,k),r) in enumerate(zip(calls,results)):
        if not hasattr(w,"_source_adapter") or r.get("ok"):
            continue
        if isinstance(r.get("parsed"),dict) and r["parsed"].get("items") == []:
            continue
        if r.get("truncated") is True or r.get("error") == "contract_violation":
            reason = "truncation" if r.get("truncated") else "malformed_contract"
            if skip_deterministic_retry(runtime, w, r, reason):
                continue
            w._partition_attempt = 1
            w._partition_retry_reason = reason
            results[i] = (await asyncio.to_thread(run_wave,runtime,[(w,k)],"failed_partition_only"))[0]
            retries+=1
    calls, results, groups, changed = await changed_input_retry(runtime, calls, results, groups)
    retries += changed
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
