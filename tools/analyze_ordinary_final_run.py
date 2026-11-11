"""Verify collected bytes and derive ordinary-run results. No model/provider access."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile

from ordinary_final_run import read, write, sha, require, DISK_USAGE
from ordinary_final_summary import supplement, rows

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/'scripts') not in sys.path:
    sys.path.insert(0,str(ROOT/'scripts'))
# Annex B.4: both reasons, every report, whenever the bundle's own review scope withholds it.
# One copy, shared with the console's GET /runs/{run_id}/switches (loop S7, DS7-3).
from run_report_text import FACT_CHECKER_REASONS
import factor_record

BASE=ROOT/'docs/fix/ordinary_final_cloud_run'
EXPOSED_NO_MANIFEST='exposed, no manifest'
ROLE_SEPARATION=('Role separation: separate sessions and folders on one Windows account; not enforced by the '
                 'operating system (Annex A, 11.2 options not in place; Annex B.11).')
NOT_SCORED=('not computed by this tool: scoring belongs to the scorer (role C for a sealed test, '
            'tools/score_corpus.py for an exposed one); this report makes no quality claim')
DOES_NOT_SHOW=('This report shows run health and cost only. It shows no quality: no recall, attribution or '
               'false-positive figure is computed here, one run is not a measurement of variation, and a '
               'greedy repeat of the same run measures nothing (11.11).')


# D-058 condition vi as D-060, D-061 and D-063 amend it: the producer's attention and prefill,
# stated in every report's backend field.
PRODUCER_SDPA_TEXT=('producer sdpa (memory-efficient, pinned); differs from v5 to v12, which ran the '
                    'producer eager')
# D-063, the default from D-063 on: the producer and B1 both run it.
DEFAULT_DECISION='D-063'
PRODUCER_DEFAULT_TEXT=('producer and B1 sdpa, prefilled in one shot, memory-efficient backend pinned (D-063); '
                       'differs from v5 to v12, which ran the producer eager')
OVER_CONTEXT_EVENT='prompt_over_context'
# D-067, D-068: what became of the judging calls on plans Python could compute nothing for.
UNCOMPUTABLE_PLAN='uncomputable'
UNCOMPUTABLE_DOES_NOT_SHOW=("What this does not show: a kept record is a model's answer, not checked by Python and "
                            "never promoted to an amendment; these counts say nothing about whether any answer is "
                            "right, and a score on the items such records decide measures the model's reading, "
                            "not a computation by Python.")


def uncomputable_judging(run_dir):
    """Per run, from audit/pairing_map.json: the judging calls on plans Python could compute
    nothing for, by outcome, and the answers D-068 kept and refused (counts only), or None
    when the run left no pairing map."""
    path=Path(run_dir)/'audit'/'pairing_map.json'
    if not path.is_file():
        return None
    pairing=read(path)
    calls=[c for entry in (pairing.values() if isinstance(pairing,dict) else []) if isinstance(entry,dict)
           for c in entry.get('judging_calls') or [] if isinstance(c,dict) and c.get('plan_kind')==UNCOMPUTABLE_PLAN]
    return dict(calls=len(calls),
                advisory_not_kept=sum(c.get('outcome')=='advisory_not_kept' for c in calls),
                judged_uncomputable=sum(c.get('outcome')=='judged_uncomputable' for c in calls),
                reply_failed=sum(c.get('outcome')=='reply_failed' for c in calls),
                kept_model_records=sum(int(c.get('judged_listed') or 0) for c in calls),
                refused=sum(int(c.get('judged_refused') or 0) for c in calls))


def multi_round_timings(target):
    """The `timings` a multi-round run saved in audit/multi_round.json (open item 39), or None."""
    found=list(Path(target).rglob('audit/multi_round.json'))
    if len(found)!=1:
        return None
    try:
        timings=read(found[0]).get('timings')
    except (OSError,ValueError,AttributeError):
        return None
    return timings if isinstance(timings,dict) else None


def multi_round_step_times_text(manifest, timings):
    """The report row for open item 39: under the multi-round argv no topology runtime exists,
    so phase_latencies are empty and the run's own step times are reported instead."""
    if not manifest.get('multi_round'):
        return 'not applicable: no multi-round run was declared'
    if not isinstance(timings,dict):
        return ('not recorded: the run\'s audit/multi_round.json carries no step times (a run before open item 39, '
                'or a phase that wrote no record)')
    def text(value):
        return '%.6f s'%value if isinstance(value,(int,float)) and not isinstance(value,bool) else 'not measured'
    rounds='; '.join('%s %s'%(r.get('round_id'),text(r.get('seconds'))) for r in timings.get('rounds') or [] if isinstance(r,dict))
    return ('round review %s (%s), record computation %s, whole phase %s (time.perf_counter, measured by the phase '
            'itself; the multi-round run has no topology runtime, so its phase_latencies are empty)'
            %(text(timings.get('round_review')),rounds or 'no round measured',text(timings.get('records')),
              text(timings.get('phase'))))


def uncomputable_text(arm, status):
    """The report row for D-067 and D-068: the calls discarded as advisory, the D-068 records
    kept, and what the counts do not show."""
    if arm=='G':
        return 'not applicable: an arm G entry runs the gate, no paired judging call'
    if arm=='B1':
        return 'not applicable: B1 makes no paired judging call'
    if arm=='L':
        return 'not reported for arm L: each menu run keeps its own audit/pairing_map.json under evidence/launcher'
    if not status.get('pipeline_started'):
        return 'not determined: the pipeline did not start'
    counts=status.get('uncomputable_judging')
    if counts is None:
        return 'not determined: the run left no audit/pairing_map.json (a multi-round run writes none)'
    return ('%d judging calls on plans Python could compute nothing for: %d discarded as advisory '
            '(advisory_not_kept, the outcome before D-068); %d returned under D-068, keeping %d answers as a '
            "model's records and refusing %d; %d failed. %s"%(
                counts['calls'],counts['advisory_not_kept'],counts['judged_uncomputable'],
                counts['kept_model_records'],counts['refused'],counts['reply_failed'],UNCOMPUTABLE_DOES_NOT_SHOW))


def producer_prefill_text(environment):
    """The producer's prefill as the sealed environment set it (D-061, D-063)."""
    chunk=environment.get('SHIMMER_PRODUCER_PREFILL_CHUNK')
    decision=environment.get('SHIMMER_PRODUCER_PREFILL_DECISION')
    if chunk is None:
        return 'prefilled in one shot (sealed before D-061 named the prefill)'
    if chunk=='one_shot':
        if decision==DEFAULT_DECISION:
            return 'prefilled in one shot (D-063)'
        return 'prefilled in one shot under decision %s (a measurement run)'%decision
    if decision=='D-061' and chunk=='512':
        return ('prefilled in chunks of 512 tokens through the KV cache, 2 tokens left to generation (E, D-061, '
                'the default before D-063); differs from v5 to v12, which prefilled in one shot')
    return 'prefilled in chunks of %s tokens under decision %s (a measurement run)'%(chunk,decision)


def producer_attention_text(manifest):
    """The producer's attention and prefill as the sealed environment set them (D-058, D-060,
    D-061, D-063): from D-063 on, sdpa pinned to the memory-efficient backend and one-shot
    prefill by default, for the producer and B1; eager or chunked prefill only under a recorded
    decision (a measurement run). Earlier manifests read as they were sealed: eager with
    chunked prefill under D-061; a manifest without the attention setting was sealed before
    D-058 and its producer ran eager, as v5 to v12 did, in one shot."""
    environment=manifest.get('environment') or {}
    value=environment.get('SHIMMER_PRODUCER_ATTENTION')
    prefill=producer_prefill_text(environment)
    if value=='sdpa':
        decision=environment.get('SHIMMER_PRODUCER_ATTENTION_DECISION')
        if decision==DEFAULT_DECISION:
            if (environment.get('SHIMMER_PRODUCER_PREFILL_CHUNK'),
                    environment.get('SHIMMER_PRODUCER_PREFILL_DECISION'))==('one_shot',DEFAULT_DECISION):
                return PRODUCER_DEFAULT_TEXT
            return PRODUCER_SDPA_TEXT+' (D-063), %s'%prefill
        if decision:
            return 'producer sdpa (memory-efficient, pinned) under decision %s (a measurement run), %s'%(decision,prefill)
        return PRODUCER_SDPA_TEXT+' (sealed under D-058, before D-060 returned the producer to eager)'
    if value=='eager':
        decision=environment.get('SHIMMER_PRODUCER_ATTENTION_DECISION')
        if decision:
            return ('producer eager under decision %s (a measurement run; eager is the kernel the producer was '
                    'trained with, and v5 to v12 ran it eager), %s'%(decision,prefill))
        return ('producer eager, the kernel it was trained and evaluated with (D-060, the default before D-063), '
                '%s'%prefill)
    if value is None:
        return 'producer eager (sealed before D-058 named the producer attention; v5 to v12 also ran it eager), '+prefill
    return 'producer attention %r: not one the runtime admits'%value


# D-061 (b): what each assessment reason means, stated in the report's execution row.
REASON_TEXT={
    'semantic_incomplete':('the pipeline reached its end with exit code 0, and its completion record marks the '
                           'semantic work incomplete (a producer partition or a delivery failed its contract; '
                           'PAIRING-A): the run finished, its output is incomplete'),
    'pipeline_not_completed':'the pipeline did not reach its end with exit code 0',
}


def assessment_text(result):
    """The runner's execution assessment (evidence/result.json) in words: passed, or each reason."""
    if not isinstance(result,dict):
        return 'not determined: no assessment collected'
    if result.get('execution_integrity_passed'):
        return 'passed'
    reasons=result.get('reasons') or []
    return 'failed: '+'; '.join('%s (%s)'%(r,REASON_TEXT[r]) if r in REASON_TEXT else r for r in reasons)


def over_context_text(arm, status, events):
    """D-058 condition v: B3 calls whose prompt and output allowance exceeded the model's
    context, refused before generating; each such document is a declared exclusion."""
    if arm=='G':
        return 'not applicable: an arm G entry runs the gate, no B3 entry'
    if arm=='B1':
        return 'not applicable: B1 checks every prompt against the context before generating (section 5.3)'
    if arm=='L':
        return 'not applicable: arm L runs no B3 entry; each menu run keeps its own telemetry under evidence/launcher'
    if not status.get('pipeline_started'):
        return 'not determined: the pipeline did not start'
    if not events:
        return "none: every B3 prompt fit its model's context with its output allowance"
    documents=sorted({str(e.get('doc_id') or 'no document id') for e in events})
    return ('%d calls on %d documents (%s), refused before generating, never truncated: each such document is '
            'a declared exclusion of B3, counted and never scored (D-058)'%(len(events),len(documents),', '.join(documents)))


ARM_TEXT={'B3':'B3: the full pipeline',
          'B1':'B1: the bare-model baseline (benchmark/baselines/bare_model.py), one fixed prompt per item, no pipeline',
          'L':('L: the launcher menu as shipped (shimmer.sh once: a review, then a draft, then quit), answered only from '
               'the sealed prompt map'),
          'G':'G: the gate (scripts/verify_session1.py, or the declared side gates) on the bound commit\'s tracked tree'}
# D-S13 item 6d: what an arm L report says of every quality figure, and of its models.
GATE_NOT_COMPARABLE='the gate on the bound commit, an integrity result only; not comparable with B3, B1 or L'
LAUNCHER_NOT_COMPARABLE=('base models as shipped (SHIMMER_MODEL_MODE=base, the checkpoints config/local_models.json '
                         'names), under the topology the menu uses; not comparable with B3 or B1, and no quality claim')


def launcher_status(target,result):
    """An arm L entry's session and its two runs, from the runner's assessment and the session's
    own transcript (evidence/launcher/transcript.json). Counts, states and seconds only."""
    transcript=Path(target)/'evidence'/'launcher'/'transcript.json'
    transcript=read(transcript) if transcript.is_file() else None
    observation=(result or {}).get('launcher') or {}
    return dict(transcript=transcript is not None,
                answers=len((transcript or {}).get('steps') or []),
                answer_ids=sorted({s.get('id') for s in (transcript or {}).get('steps') or []}),
                seconds=(transcript or {}).get('seconds'),session=observation.get('session') or {},
                runs=observation.get('runs') or {},network=observation.get('network') or {},
                context=observation.get('context') or {},semantic=(result or {}).get('semantic_complete') or {})


def launcher_text(status):
    """The report row of an arm L entry: the session, each task's run, the children's network."""
    seen=status.get('launcher')
    if not seen or not seen['transcript']:
        return 'no session transcript collected: the menu did not run or its evidence was not packed'
    session=seen['session']
    parts=['the menu %s with exit code %s after %s answers from the sealed map (%s s; %s)'%(
        'stopped (%s%s)'%(session.get('stop_reason'),': '+str(session.get('unknown_prompt')) if session.get('unknown_prompt') else '')
        if session.get('stop_reason') else 'ended by itself',session.get('exit_code'),seen['answers'],seen['seconds'],
        'every sealed answer given' if not session.get('unused') else 'not given: '+', '.join(session['unused']))]
    for task in ('review','draft'):
        found=seen['runs'].get(task) or []
        if len(found)!=1:
            parts.append('%s: %d run folders'%(task,len(found)))
            continue
        run=found[0];completion=run.get('completion') or {}
        parts.append('%s: state %s, reached its end %s, exit code %s, semantic work %s, pipeline_start %s and pipeline_end %s%s'%(
            task,completion.get('state'),completion.get('reached_end'),completion.get('exit_code'),
            'complete' if completion.get('semantic_complete') is True else 'incomplete' if completion.get('semantic_complete') is False
            else 'not recorded',run.get('pipeline_starts'),run.get('pipeline_ends'),
            ', run summary written' if run.get('run_summary') else ', memo written' if run.get('memos')==1 else ''))
    network=seen['network']
    parts.append('children: %s network logs, %s processes (%s of %s pipeline processes with the denial in full), '
                 'denial installed in full in %s, at the socket layer only in %s, partial in %s; %s blocked attempts, '
                 '%s loopback connections'%(network.get('logs'),network.get('processes'),network.get('pipelines_installed'),
                                           network.get('pipelines'),network.get('denial_installed'),
                                           network.get('denial_sockets_only'),network.get('denial_partial'),
                                           network.get('blocked'),network.get('loopback')))
    return '; '.join(parts)
# The counts a B1 report row carries per checkpoint, read from its b1_summary.json (no text).
B1_COUNTS=('items','parsed','abstain','undecided','backend_failures','repaired','length_reached_allowance')


def b1_models(status):
    """The B1 'Models and checkpoints' row: each sealed pass's model, digest and adapter (and
    the checkpoint it loaded when the pass's name is not that checkpoint's)."""
    parts=[]
    for name,seen in status['b1_checkpoints'].items():
        if seen.get('replay') and seen.get('kind')=='doc_judge':
            parts.append('%s: document-level judging (G1), %s'%(name,', '.join(
                '%s %s digest %s'%(group,m.get('model_id'),m.get('digest')) for group,m in sorted((seen.get('models') or {}).items()))
                or 'no model recorded'))
            continue
        if seen.get('replay'):
            parts.append('%s: replay of B3 prompts on the tuned producer'%name)
            continue
        if not seen['summary_written']:
            parts.append('%s: no b1_summary.json collected'%name)
            continue
        label=name if seen.get('checkpoint') in (None,name) else '%s (checkpoint %s)'%(name,seen['checkpoint'])
        parts.append('%s: %s, digest %s, adapter %s'%(label,seen['model_id'],seen['digest'],
                     'applied' if seen['adapter_applied'] else 'not applied'))
    return '; '.join(parts) or 'no checkpoint sealed'


def gib(value):
    return '%.2f GiB'%(value/2**30)


def disk_record(base, target):
    """Open item 37: the disk readings of the run root's filesystem, from the runner's
    evidence/disk_usage.json (before the workload, the sampled peak, after it) and the
    controller's disk_after_evidence.json (after evidence packing). A missing file is None."""
    def load(path):
        try:
            return read(path) if Path(path).is_file() else None
        except (OSError, ValueError):
            return None
    usage=load(Path(target)/'evidence'/DISK_USAGE)
    usage=usage if isinstance(usage,dict) else {}
    return dict(before_workload=usage.get('before_workload'),peak=usage.get('peak'),peak_kind=usage.get('peak_kind'),
                after_workload=usage.get('after_workload'),readings=usage.get('readings'),
                after_evidence=load(Path(base)/'disk_after_evidence.json'),
                runner_file=bool(usage))


def disk_reading_text(reading, absent):
    if not isinstance(reading,dict):
        return 'not recorded (%s)'%absent
    if 'used_bytes' not in reading:
        return 'unavailable (%s)'%reading.get('unavailable','no reason recorded')
    return '%s in use of %s, %s available'%(gib(reading['used_bytes']),gib(reading['total_bytes']),gib(reading['available_bytes']))


def disk_text(disk):
    """The report row: disk in use before the workload, at its sampled peak, after it, and
    after evidence packing; a reading that is missing or failed says so."""
    runner='no evidence/disk_usage.json: the runner predates open item 37 or never reached the workload'
    peak=disk_reading_text(disk['peak'],runner)
    if isinstance(disk['peak'],dict) and 'used_bytes' in disk['peak']:
        peak+=' (%s readings; %s)'%(disk['readings'],disk['peak_kind'])
    return ('before the workload: %s; peak: %s; after the workload: %s; after evidence packing: %s'
            %(disk_reading_text(disk['before_workload'],runner),peak,disk_reading_text(disk['after_workload'],runner),
              disk_reading_text(disk['after_evidence'],'no disk_after_evidence.json: the controller predates open '
                                'item 37 or the evidence was not packed')))


def b1_measures_text(seen):
    """A pass's attention, prefill, peak GPU memory and prefill time (D-056 condition 6, D-061),
    as its summary recorded them."""
    attention=seen.get('attention_implementation') or 'not recorded'
    if seen.get('attention_implementation')=='sdpa' and seen.get('attention_decision')==DEFAULT_DECISION:
        attention+=' (memory-efficient backend pinned, D-063)'
    elif seen.get('attention_decision'):
        attention+=' (measurement pass, %s)'%seen['attention_decision']
    prefill=seen.get('prefill')
    if prefill=='chunked':
        attention+=', chunked prefill of %s tokens (%s)'%(seen.get('prefill_chunk_tokens'),seen.get('prefill_decision'))
    elif prefill=='one_shot':
        attention+=', one-shot prefill (%s)'%(seen.get('prefill_decision') or 'sealed before D-061')
    timing=seen.get('prefill_time') or {}
    if timing.get('seconds_measured'):
        attention+=', longest prefill %s s'%timing.get('seconds_max')
    memory=seen.get('gpu_memory')
    if not isinstance(memory,dict):
        peak='peak GPU memory not recorded'
    elif not memory.get('measured'):
        peak='peak GPU memory not measured (no CUDA)'
    else:
        peak='peak GPU memory %s allocated, %s reserved'%(gib(memory['peak_allocated_bytes']),
                                                          gib(memory['peak_reserved_bytes']))
    return 'attention %s, %s'%(attention,peak)


def b1_counts(status):
    """The B1 'B1 checkpoints' row: per sealed pass, the runner's exit code, the counts, the
    attention and the peak GPU memory."""
    parts=[]
    for name,seen in status['b1_checkpoints'].items():
        if seen.get('replay'):
            parts.append(replay_text(name,seen))
            continue
        counts=', '.join('%s %s'%(k.replace('_',' '),seen['counts'].get(k)) for k in B1_COUNTS)+', '+b1_measures_text(seen) \
            if seen['summary_written'] else 'no b1_summary.json collected'
        parts.append('%s (exit %s): %s'%(name,seen['exit_code'],counts))
    return '; '.join(parts) or 'no checkpoint sealed'


def b1_pass_measures(summary):
    """What a pass's b1_summary.json says it loaded and measured: the checkpoint, the attention
    (and the decision of a measurement pass) and the peak GPU memory. Counts and names only."""
    summary=summary or {}
    attention=summary.get('attention') or {}
    return dict(checkpoint=(summary.get('reader') or {}).get('checkpoint') or (summary.get('checkpoint') or {}).get('checkpoint'),
                attention_implementation=attention.get('attention_implementation'),
                attention_decision=attention.get('attention_decision'),gpu_memory=summary.get('gpu_memory'),
                prefill=attention.get('prefill'),prefill_chunk_tokens=attention.get('prefill_chunk_tokens'),
                prefill_decision=attention.get('prefill_decision'),prefill_time=summary.get('prefill_time'))


def replay_pass_status(path,name,result):
    """A replay pass (D-061 item 4), from its replay_measurement.json: per path the peak GPU
    memory and prefill seconds, the failures, and per pair of paths the byte-identical counts.
    Counts, hashes and seconds only."""
    measurement=read(path) if path.is_file() else None
    exit_code=(((result or {}).get('checkpoints') or {}).get(name) or {}).get('exit_code')
    if measurement is None:
        return dict(replay=True,summary_written=False,exit_code=exit_code)
    return dict(replay=True,summary_written=True,exit_code=exit_code,prompts=measurement.get('prompts'),
                paths=list(measurement.get('paths') or {}),decision=measurement.get('decision'),
                gpu_memory=measurement.get('gpu_memory'),prefill_seconds=measurement.get('prefill_seconds'),
                failures=measurement.get('failures'),comparisons=measurement.get('comparisons'),
                kind=measurement.get('kind'),models=measurement.get('models'),
                comparator_prompts=measurement.get('comparator_prompts'))


def replay_text(name,seen):
    """One replay pass in the report's B1 row."""
    if not seen['summary_written']:
        return '%s (exit %s): replay, no replay_measurement.json collected'%(name,seen['exit_code'])
    parts=[]
    for path in seen['paths']:
        memory=(seen.get('gpu_memory') or {}).get(path) or {}
        peak=gib(memory['peak_allocated_bytes']) if memory.get('measured') else 'not measured'
        seconds=((seen.get('prefill_seconds') or {}).get(path) or {}).get('max')
        parts.append('%s peak %s, longest prefill %s s, failures %s'%(path,peak,seconds,(seen.get('failures') or {}).get(path)))
    pairs=['%s %s of %s byte-identical (%s of %s at three chunks or more)'%(
        pair,(c.get('all') or {}).get('byte_identical'),(c.get('all') or {}).get('compared'),
        (c.get('three_chunks_or_more') or {}).get('byte_identical'),(c.get('three_chunks_or_more') or {}).get('compared'))
        for pair,c in (seen.get('comparisons') or {}).items()]
    if seen.get('kind')=='doc_judge':
        comparator=seen.get('comparator_prompts') or 0
        return '%s (exit %s): document-level judging (G1) of %s prompts, one per model group, document and rule%s; %s'%(
            name,seen['exit_code'],(seen.get('prompts') or 0)-comparator,
            ', and %s with B1\'s own prompt'%comparator if comparator else '','; '.join(parts))
    return '%s (exit %s): replay of %s B3 producer prompts under decision %s; %s; %s'%(
        name,seen['exit_code'],seen.get('prompts'),seen.get('decision'),'; '.join(parts),'; '.join(pairs))


def b1_checkpoint_status(manifest,target,result):
    """Per sealed pass, in sealed order and by its name: its exit code from the runner's
    assessment, the counts of its collected b1_summary.json, summed over the benchmarks it
    holds, and what the summary measured (b1_pass_measures)."""
    seen={}
    for entry in (manifest.get('b1') or {}).get('checkpoints') or []:
        name=entry['name']
        if entry.get('replay') is True:
            seen[name]=replay_pass_status(target/'evidence'/'b1'/name/'replay_measurement.json',name,result)
            continue
        path=target/'evidence'/'b1'/name/'b1_summary.json'
        summary=read(path) if path.is_file() else None
        per_benchmark=list(((summary or {}).get('benchmarks') or {}).values())
        loaded=(summary or {}).get('loaded') or {}
        checkpoint=(summary or {}).get('checkpoint') or {}
        seen[name]=dict(summary_written=summary is not None,
            exit_code=(((result or {}).get('checkpoints') or {}).get(name) or {}).get('exit_code'),
            model_id=loaded.get('model_id'),digest=loaded.get('digest'),adapter_applied=checkpoint.get('adapter_applied'),
            counts={k:sum(int(r.get(k) or 0) for r in per_benchmark) for k in B1_COUNTS},
            **b1_pass_measures(summary))
    return seen


def analyze_b1(base,manifest,target,analysis,launch,run_record,copy_receipt,record,api,result,failure):
    """A B1 entry's status and report. B1 never runs the pipeline, so there is no
    run_completion.json or model telemetry to read: the entry completed when the runner's own
    arm-aware assessment (evidence/result.json, arm B1) passed and every sealed checkpoint left
    its b1_summary.json; its report rows come from those summaries."""
    sys.path.insert(0,str(ROOT/'scripts'))
    import model_telemetry
    stages={p.stem.removesuffix('_timing'):read(p) for p in base.glob('*_timing.json')}
    write(analysis/'stages.json',stages)
    checkpoints=b1_checkpoint_status(manifest,target,result)
    completed=bool(result and result.get('arm')=='B1' and result.get('execution_integrity_passed') and checkpoints
                   and all(c['summary_written'] for c in checkpoints.values()))
    costs=model_telemetry.cost([record,api])
    status=dict(status='ORDINARY_FINAL_CLOUD_RUN_COMPLETED' if completed else 'ORDINARY_FINAL_CLOUD_RUN_FAILED',
        arm='B1',pipeline_started=False,pipeline_completion=None,remote_result=result,terminal_error=failure,
        disk=disk_record(base,target),b1_checkpoints=checkpoints,b1_reply_records=sum(int(c.get('reply_records') or 0)
                                                        for c in ((result or {}).get('checkpoints') or {}).values()),
        semantic_call_receipts=None,producer168_receipts=None,auditor896_receipts=None,
        cost_estimates=costs,within_hard_ceiling=costs['combined_estimate']<=manifest['hard_ceiling_usd'],
        exactly_one_instance=True,maximum_one_workload_invocation=True,full_run_retried=False,
        protected_data_accessed=bool(manifest.get('protected_test')),
        multi_round_declared=False,multi_round_executed=False,
        inventory_empty=True,temporary_ssh_removed=True,
        evidence_verified=True,quality_claim=None,subsequent_roadmap_work_started=False)
    report_rows=report_fields(base,manifest,run_record,launch,status,copy_receipt)
    status['report']={k:v for k,v in report_rows}
    write(base/'FINAL_STATUS.json',status)
    write_report(base,report_rows)
    print(json.dumps(status,indent=2))


def gate_text(manifest,result):
    """The report row of an arm G entry: what ran, its counts, known red apart, and its minutes."""
    gate=manifest.get('gate') or {}
    if not result or result.get('arm')!='G':
        return 'no gate result collected: the gate did not run or its evidence was not packed'
    counts=result.get('counts') or {}
    if result.get('form')=='side':
        said='side gates: %s exited 0, %s did not'%(counts.get('passed'),counts.get('failed'))
    else:
        said='checks %s; %s'%(gate.get('checks'),', '.join('%s %s'%(k,counts.get(k,0)) for k in
                                                       ('PASS','WARN','SKIP','FAIL','ERROR','BADFIXTURE')))
    parts=[said,'known red %s, of them failing %s, now green %s'%(gate.get('known_red') or 'none',
                                                                   result.get('known_red_failed') or 'none',
                                                                   result.get('now_green') or 'none'),
           'failing outside known red %s'%(result.get('failing') or 'none'),
           'not run %s'%(result.get('not_run') or 'none'),
           '%.1f minutes of gate'%(float(result.get('gate_seconds') or 0)/60)]
    return '; '.join(parts)


def analyze_gate(base,manifest,target,analysis,launch,run_record,copy_receipt,record,api,result,failure):
    """An arm G entry's status and report: it completed when the runner's assessment (evidence/
    result.json, arm G) passed. Integrity only; never compared with B3, B1 or L."""
    sys.path.insert(0,str(ROOT/'scripts'))
    import model_telemetry
    stages={p.stem.removesuffix('_timing'):read(p) for p in base.glob('*_timing.json')}
    write(analysis/'stages.json',stages)
    completed=bool(result and result.get('arm')=='G' and result.get('execution_integrity_passed'))
    costs=model_telemetry.cost([record,api])
    status=dict(status='ORDINARY_FINAL_CLOUD_RUN_COMPLETED' if completed else 'ORDINARY_FINAL_CLOUD_RUN_FAILED',
        arm='G',pipeline_started=False,pipeline_completion=None,remote_result=result,terminal_error=failure,
        disk=disk_record(base,target),b1_checkpoints={},gate=result,
        semantic_call_receipts=None,producer168_receipts=None,auditor896_receipts=None,
        cost_estimates=costs,within_hard_ceiling=costs['combined_estimate']<=manifest['hard_ceiling_usd'],
        exactly_one_instance=True,maximum_one_workload_invocation=True,full_run_retried=False,
        protected_data_accessed=False,multi_round_declared=False,multi_round_executed=False,
        inventory_empty=True,temporary_ssh_removed=True,
        evidence_verified=True,quality_claim=None,subsequent_roadmap_work_started=False)
    report_rows=report_fields(base,manifest,run_record,launch,status,copy_receipt)
    status['report']={k:v for k,v in report_rows}
    write(base/'FINAL_STATUS.json',status)
    write_report(base,report_rows)
    print(json.dumps(status,indent=2))


def analyze_launcher(base,manifest,target,analysis,launch,run_record,copy_receipt,record,api,result,failure):
    """An arm L entry's status and report: it completed when the runner's own arm-aware
    assessment (evidence/result.json, arm L) passed and its transcript was collected. Integrity
    only; base models as shipped, never compared with B3 or B1."""
    sys.path.insert(0,str(ROOT/'scripts'))
    import model_telemetry
    stages={p.stem.removesuffix('_timing'):read(p) for p in base.glob('*_timing.json')}
    write(analysis/'stages.json',stages)
    seen=launcher_status(target,result)
    completed=bool(result and result.get('arm')=='L' and result.get('execution_integrity_passed') and seen['transcript'])
    costs=model_telemetry.cost([record,api])
    status=dict(status='ORDINARY_FINAL_CLOUD_RUN_COMPLETED' if completed else 'ORDINARY_FINAL_CLOUD_RUN_FAILED',
        arm='L',pipeline_started=bool(seen['runs']),pipeline_completion=None,remote_result=result,terminal_error=failure,
        disk=disk_record(base,target),launcher=seen,b1_checkpoints={},
        semantic_call_receipts=None,producer168_receipts=None,auditor896_receipts=None,
        cost_estimates=costs,within_hard_ceiling=costs['combined_estimate']<=manifest['hard_ceiling_usd'],
        exactly_one_instance=True,maximum_one_workload_invocation=True,full_run_retried=False,
        protected_data_accessed=False,multi_round_declared=False,multi_round_executed=False,
        inventory_empty=True,temporary_ssh_removed=True,
        evidence_verified=True,quality_claim=None,subsequent_roadmap_work_started=False)
    report_rows=report_fields(base,manifest,run_record,launch,status,copy_receipt)
    status['report']={k:v for k,v in report_rows}
    write(base/'FINAL_STATUS.json',status)
    write_report(base,report_rows)
    print(json.dumps(status,indent=2))


def withheld_agents(bundle):
    """The audit agents the bundle's OWN review scope withholds, read from its project archive."""
    archive=Path(bundle)/'project.tar.gz'
    if not archive.exists() and (Path(bundle)/'seal_entry.json').exists():
        # A batch run folder: the archive stays in the entry's own bundle.
        archive=Path(read(Path(bundle)/'seal_entry.json').get('bundle',''))/'project.tar.gz'
    try:
        with tarfile.open(archive) as tar:
            scope=json.loads(tar.extractfile('config/review_scope.json').read())
        return list(scope.get('withheld_audit_agents') or [])
    except (OSError, KeyError, ValueError, tarfile.TarError):
        return None


def recorded_inst_finder(target):
    """INST_FINDER's setting as each pipeline run of this entry saved it at start-up
    (audit/agent_switches.json, the pipeline's own record of the decision it made), read
    from the collected evidence. One entry per saved record, in path order; a record that
    cannot be read is kept as setting None, never guessed (issue #133, D-184)."""
    found=[]
    for path in sorted(Path(target).rglob('audit/agent_switches.json')):
        try:
            saved=json.loads(path.read_text(encoding='utf8'))
        except (OSError,ValueError):
            saved=None
        if isinstance(saved,dict) and saved.get('setting') in ('on','off'):
            found.append(dict(setting=saved['setting'],refused=bool(saved.get('refusal')),ratified_by=saved.get('ratified_by')))
        else:
            found.append(dict(setting=None,refused=False,ratified_by=None))
    return found


def inst_finder_comparison(manifest, arm, recorded):
    """The sealed INST_FINDER setting beside the one the run recorded: the sealed value as the
    pipeline reads it (`off` is off, anything else on), the recorded settings, and whether
    any recorded setting differs from the sealed one or could not be read. The report states
    both and names a difference; it never reports the sealed value alone (issue #133)."""
    value=manifest.get('environment',{}).get('SHIMMER_INST_FINDER')
    sealed='off' if value=='off' else 'on'
    settings=[r['setting'] for r in recorded]
    differs=any(s!=sealed for s in settings)
    if arm=='B1':
        run_text='not recorded by the run: a B1 entry runs bare_model.py, not the pipeline'
    elif not recorded:
        run_text='not recorded by the run: the collected evidence holds no audit/agent_switches.json'
    elif None in settings:
        run_text='DIFFERS FROM THE SEAL: %d of %d saved records (audit/agent_switches.json) cannot be read'%(
            settings.count(None),len(settings))
    elif differs:
        run_text='DIFFERS FROM THE SEAL: the run recorded %s (audit/agent_switches.json)'%', '.join(settings)
    else:
        run_text='the run recorded %s (audit/agent_switches.json)'%', '.join(settings)
    if any(r['refused'] for r in recorded):
        run_text+='; the run refused the setting at start (no ratified amendment)'
    return dict(sealed_value=value,sealed=sealed,recorded=settings,differs=differs,
                text='%s (sealed in the manifest); %s'%(str(value),run_text))


def report_fields(bundle, manifest, record, launch, status, receipt):
    """Every field 11.12 lists, plus B.1's purpose and sealed-or-exposed lines, the
    SHIMMER_INST_FINDER value, B.4's FACT_CHECKER withholding with both reasons, the
    instance type and price, and IV.10's role-separation sentence for a sealed run. A field
    that does not apply says why."""
    record=record or {}
    report=record.get('report') or {}
    exposure=record.get('exposure') or 'exposed'
    sealed=exposure=='sealed'
    withheld=withheld_agents(bundle)
    if withheld is None:
        fact_checker='not determined: the bundle has no readable config/review_scope.json'
    elif 'FACT_CHECKER' in withheld:
        fact_checker='FACT_CHECKER withheld for this run. '+'; '.join(FACT_CHECKER_REASONS)+'.'
    else:
        fact_checker='FACT_CHECKER ran: not withheld in this bundle\'s config/review_scope.json'
    authors=report.get('authors') or {}
    arm=manifest.get('arm','B3')
    inst_finder=inst_finder_comparison(manifest,arm,recorded_inst_finder(Path(bundle)/'downloaded'))
    status['inst_finder']={k:v for k,v in inst_finder.items() if k!='text'}
    # D-S82: the result's factor record, written by Python from its own sealed records.
    seal_path=Path(bundle)/'seal.json'
    status['factors']=factor_record.record(manifest,launch,read(seal_path) if seal_path.is_file() else None)
    # D-436 item 5b: a run whose figures are compared (B3 or B1, not sealed --uncompared) names the
    # machine type it ran on, read from its own controller records; unrecorded, its report is refused.
    status['machine_type']=factor_record.selected_type(bundle)
    require(status['machine_type'] is not None or manifest.get('arm','B3') not in ('B3','B1') or manifest.get('uncompared'),
            'A compared run names its machine type in its controller records; this one does not')
    from datetime import datetime, timezone
    rows=[
        ('Purpose',record.get('purpose') or 'not recorded: the launch predates the S2 launch record'),
        ('Sealed or exposed','Sealed test' if sealed else 'Exposed test, development only'),
        ('Date and time (UTC)',datetime.fromtimestamp(launch['epoch'],timezone.utc).isoformat()),
        ('Code commit',manifest['source_commit']),
        ('Test version',report.get('test_version') or manifest.get('workload',{}).get('name') or 'not declared at launch'),
        ('Test manifest hash',record.get('test_manifest_sha256') or EXPOSED_NO_MANIFEST),
        ('Authors (test, key, scorer)',', '.join(str(authors.get(k) or 'not declared at launch') for k in ('test','key','scorer'))),
        ('Scorer version',report.get('scorer_version') or NOT_SCORED),
        ('Arm',ARM_TEXT[arm]),
        ('Models and checkpoints',b1_models(status) if arm=='B1' else
            '; '.join(m['model_id']+'@'+m['revision'][:12] for m in manifest.get('models',[]))+'; '+LAUNCHER_NOT_COMPARABLE
            if arm=='L' else
            '; '.join(m['model_id']+'@'+m['revision'][:12] for m in manifest.get('models',[]))+'; '+GATE_NOT_COMPARABLE
            if arm=='G' else
            '; '.join(m['model_id']+'@'+m['revision'][:12] for m in manifest.get('models',[]))
            +'; adapter receipts: Producer 168 x%s, Auditor 896 x%s'%(status['producer168_receipts'],status['auditor896_receipts'])),
        ('B1 checkpoints',b1_counts(status) if arm=='B1' else
            'not applicable: an arm L entry runs the launcher menu, not bare_model.py' if arm=='L' else
            'not applicable: an arm G entry runs the gate, not bare_model.py' if arm=='G' else
            'not applicable: a B3 entry runs the pipeline, not bare_model.py'),
        ('Launcher session',launcher_text(status) if arm=='L' else 'not applicable: only arm L runs the launcher menu'),
        ('Gate',gate_text(manifest,status.get('remote_result')) if arm=='G' else 'not applicable: only arm G runs the gate'),
        ('Decoding settings','; '.join('%s: %s'%(k,v.get('status')) for k,v in sorted((manifest.get('decoding_policy') or {}).items()))
            or 'not recorded in the manifest'),
        ('Backend and machine','local open-weight models on one rented GPU; %s in %s; %s'%(launch.get('instance_type','gpu_1x_a10'),
            launch.get('region','us-east-1'),LAUNCHER_NOT_COMPARABLE if arm=='L' else GATE_NOT_COMPARABLE if arm=='G'
            else producer_attention_text(manifest))),
        ('B3 prompts over the model context',over_context_text(arm,status,status.get('b3_prompts_over_context') or [])),
        ('Judging calls Python could compute nothing for',uncomputable_text(arm,status)),
        ('Execution assessment',assessment_text(status.get('remote_result'))),
        ('Disk on the instance',disk_text(status['disk']) if status.get('disk') else 'not recorded: no disk readings were read'),
        ('Instance type and price','%s at %s dollars an hour (type rule %s)'%(launch.get('instance_type','gpu_1x_a10'),
            launch['hourly_rate'],manifest.get('type_order') or manifest.get('type_rule','a10_first'))),
        ('Cost','%.4f dollars estimated (infrastructure, from launch to confirmed empty inventory; not an invoice)%s'
            %(status['cost_estimates']['combined_estimate'],
              '; this is the whole instance session, shared by every bundle of its batch, not the cost of this bundle alone'
              if (Path(bundle)/'seal_entry.json').exists() else '')),
        ('Location and reason-confirmed recall',NOT_SCORED),
        ('Attribution',NOT_SCORED),
        ('False positives in every deliverable',NOT_SCORED),
        ('Clean-twin result',NOT_SCORED),
        ('Layer that produced each catch',NOT_SCORED),
        ('Catches that depended on a directive',NOT_SCORED),
        ('Model-text review verdicts','not part of this tool: every model text is reviewed by the scorer\'s review (11.8, B.1)'),
        ('Agents withheld or settings changed',fact_checker+' SHIMMER_INST_FINDER='+inst_finder['text']+'.'),
        ('SHIMMER_INST_FINDER',inst_finder['text']),
        ('Multi-round','declared and sealed with case manifest '+str(manifest.get('case_manifest_sha256'))
            if manifest.get('multi_round') else 'not applicable: no multi-round run was declared'),
        ('Multi-round step times',multi_round_step_times_text(manifest,status.get('multi_round_timings'))),
        ('Asset copy','MATCH: the sealed archive was read from the operator-declared copy' if receipt.get('used')
            else 'no MATCH (%s): the archive was uploaded'%(receipt.get('state') or 'no declaration for this bundle')),
        ('Role separation',ROLE_SEPARATION if sealed else 'not applicable: an exposed run claims no role separation'),
        ('Factor record',factor_record.summary_line(status['factors'])+' (D-S82: compare two results with '
            'tools/factor_record.py compare; a gain goes to one factor only when it alone changed)'),
        ('What the result does not show',DOES_NOT_SHOW),
    ]
    return rows


def write_report(bundle, rows):
    # B.1: the report starts with the purpose line and the sealed-or-exposed line.
    lines=['Purpose: '+rows[0][1],rows[1][1]+'.','','# Run report','']
    lines.extend('- **%s.** %s'%(k,v) for k,v in rows[2:])
    (Path(bundle)/'RUN_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')


def analyze(bundle=BASE):
    global BASE
    BASE=Path(bundle).resolve()
    integrity=read(BASE/'collection_integrity.json')
    archive=BASE/'collected_evidence.tar.gz'
    require(sha(archive)==integrity['sha256'],'Collected archive integrity mismatch')
    expected=read(BASE/'remote_collection_manifest.json')
    target=BASE/'downloaded'
    target.mkdir(exist_ok=True)
    with tarfile.open(archive) as tar:
        members=tar.getmembers()
        require(len(members)==len(expected) and {m.name for m in members}==set(expected),'Evidence inventory mismatch')
        for member in members:
            path=(target/member.name).resolve()
            require(member.isfile() and path.is_relative_to(target.resolve()),'Unsafe evidence member')
            content=tar.extractfile(member).read()
            require(hashlib.sha256(content).hexdigest()==expected[member.name]['sha256'],'Evidence member hash mismatch')
            require(len(content)==expected[member.name]['bytes'],'Evidence length mismatch')
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():require(sha(path)==expected[member.name]['sha256'],'Existing preserved evidence changed')
            else:path.write_bytes(content)
    require(sha(target/'execution_manifest.json')==sha(BASE/'execution_manifest.json'),'Remote execution manifest differs')
    write(BASE/'verified_evidence.json',dict(passed=True,members=len(expected),archive_sha256=integrity['sha256'],originals_unmodified=True))
    cleanup=read(BASE/'independent_inventory_confirmation.json')
    require(cleanup['instances']==[] and cleanup['temporary_ssh_registration_absent'] and cleanup['local_key_material_absent'],'Cleanup not established')
    launch=read(BASE/'launch.json')
    manifest=read(BASE/'execution_manifest.json')
    run_record=read(BASE/'run_record.json') if (BASE/'run_record.json').exists() else None
    copy_receipt=read(BASE/'asset_copy_receipt.json') if (BASE/'asset_copy_receipt.json').exists() else {}
    record=dict(event='infrastructure_cost',provider='Lambda',instance_type=launch.get('instance_type','gpu_1x_a10'),hourly_rate=launch['hourly_rate'],
        active_start_epoch=launch['epoch'],active_end_epoch=cleanup['epoch'],
        interpretation='Conservative launch request through independent empty-inventory confirmation; estimate, not invoice')
    api=dict(event='api_cost',estimated_cost=0,interpretation='Approved all-local model profile; no paid model/API execution authorized or invoked')
    analysis=BASE/'analysis';analysis.mkdir(exist_ok=True)
    (analysis/'cost_records.jsonl').write_text(json.dumps(record)+'\n'+json.dumps(api)+'\n',encoding='utf8')
    completions=list(target.rglob('audit/run_completion.json'))
    result=read(target/'evidence/result.json') if (target/'evidence/result.json').exists() else None
    failure=read(target/'evidence/terminal_error.json') if (target/'evidence/terminal_error.json').exists() else None
    if manifest.get('arm','B3')=='G':
        require(not completions,'An arm G entry runs no pipeline workload')
        return analyze_gate(BASE,manifest,target,analysis,launch,run_record,copy_receipt,record,api,result,failure)
    if manifest.get('arm','B3')=='L':
        # The menu's two runs live under evidence/launcher/<task>/, one each; nowhere else.
        launcher=(target/'evidence'/'launcher').resolve()
        require(all(p.resolve().is_relative_to(launcher) for p in completions) and len(completions)<=2,
                'An arm L entry keeps its two menu runs under evidence/launcher, and no other pipeline run')
        return analyze_launcher(BASE,manifest,target,analysis,launch,run_record,copy_receipt,record,api,result,failure)
    require(len(completions)<=1,'More than one pipeline run observed')
    if manifest.get('arm','B3')=='B1':
        require(not completions,'A B1 entry never runs the pipeline')
        return analyze_b1(BASE,manifest,target,analysis,launch,run_record,copy_receipt,record,api,result,failure)
    summary=None;raw=[];scheduler=[];completion=None;uncomputable=None
    sys.path.insert(0,str(ROOT/'scripts'))
    import model_telemetry
    if completions:
        completion=read(completions[0]);directory=completions[0].parent.parent
        raw=rows(directory/'logs/model_telemetry.jsonl');scheduler=rows(directory/'audit/execution_topology.jsonl')
        summary=model_telemetry.summarize(raw+[record,api],scheduler)
        uncomputable=uncomputable_judging(directory)
        write(analysis/'model_telemetry_summary.json',summary)
        write(analysis/'ordinary_final_summary.json',supplement(raw,scheduler))
    summary=summary if completions else {}
    stages={p.stem.removesuffix('_timing'):read(p) for p in BASE.glob('*_timing.json')}
    write(analysis/'stages.json',stages)
    completed=bool(completion and completion.get('state')=='completed' and result and result.get('execution_integrity_passed'))
    costs=model_telemetry.cost([record,api])
    calls=[r for r in raw if r['event']=='model_call']
    status=dict(status='ORDINARY_FINAL_CLOUD_RUN_COMPLETED' if completed else 'ORDINARY_FINAL_CLOUD_RUN_FAILED',
        pipeline_started=bool(completions),pipeline_completion=completion,remote_result=result,terminal_error=failure,
        semantic_call_receipts=len(calls),producer168_receipts=sum(r.get('adapter_checkpoint')==168 for r in calls),
        auditor896_receipts=sum(r.get('adapter_checkpoint')==896 for r in calls),
        auditor896_pairs=(summary.get('auditor_pairing',{}).get('pairs_constructed') if completions else None),
        auditor896_pairs_from_partial_delivery=(summary.get('auditor_pairing',{}).get('pairs_from_partial_delivery') if completions else None),
        cost_estimates=costs,within_hard_ceiling=costs['combined_estimate']<=manifest['hard_ceiling_usd'],
        exactly_one_instance=True,maximum_one_workload_invocation=True,full_run_retried=False,
        protected_data_accessed=bool(manifest.get('protected_test')) and bool(completions),
        multi_round_declared=bool(manifest.get('multi_round')),
        multi_round_executed=bool(manifest.get('multi_round')) and bool(list(target.rglob('audit/multi_round.json'))),
        multi_round_timings=multi_round_timings(target) if manifest.get('multi_round') else None,
        uncomputable_judging=uncomputable,disk=disk_record(BASE,target),
        b3_prompts_over_context=[{k:r.get(k) for k in ('call_id','agent','doc_id','prompt_tokens','max_new_tokens','model_context')}
                                 for r in raw if r.get('event')==OVER_CONTEXT_EVENT],
        inventory_empty=True,temporary_ssh_removed=True,
        evidence_verified=True,quality_claim=None,subsequent_roadmap_work_started=False)
    # Named apart from the imported rows() reader: one local `rows` in this function would make
    # every use of the reader above it an unbound local (the S5 smoke run's UnboundLocalError).
    report_rows=report_fields(BASE,manifest,run_record,launch,status,copy_receipt)
    status['report']={k:v for k,v in report_rows}
    write(BASE/'FINAL_STATUS.json',status)
    write_report(BASE,report_rows)
    print(json.dumps(status,indent=2))


def pair_machine_types(folders):
    """D-S95 item 5, D-401 item 1 (b): the arms of each item (its B3 and B1 entries) ran on one
    machine type, read from each entry's controller records (factor_record.require_same_type); a
    figure whose arms differ is refused here, before any report is written."""
    by_item={}
    for folder in folders:
        entry=read(Path(folder)/'seal_entry.json') if (Path(folder)/'seal_entry.json').is_file() else {}
        by_item.setdefault(entry.get('item') or Path(folder).name,[]).append(folder)
    return {item:factor_record.require_same_type(arms) for item,arms in sorted(by_item.items())}


def analyze_batch(bundle):
    """One report per batch run folder that collected its evidence, in schedule order, after the
    arms of every item are held to one machine type (`pair_machine_types`, written to
    `batch_machine_types.json`)."""
    folders=sorted(p for p in (Path(bundle)/'batch').iterdir() if (p/'collection_integrity.json').exists())
    write(Path(bundle)/'batch_machine_types.json',pair_machine_types(folders))
    for folder in folders:
        analyze(folder)
    return folders


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=BASE)
    parser.add_argument('--batch',action='store_true',help='analyse every batch run folder of this session')
    arguments=parser.parse_args()
    if arguments.batch:analyze_batch(arguments.bundle)
    else:analyze(arguments.bundle)
