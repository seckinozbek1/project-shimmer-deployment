"""Ordinary fidelity advisory pairs. Ownership is structural, never inferred."""
import copy
import json
import time
import uuid

import bounded_extraction as extraction
import final_models
import model_telemetry as telemetry

VERSION = 1
RELATIONS = ('MATCH', 'DIVERGENCE', 'OMISSION', 'ADDITION')
TASK = 'verify_draft_against_source'


def semantic_item(item):
    # Runtime-hydrated draft_text is the original, not a new Producer claim.
    keys = ('claims_referenced', 'open_questions', 'uncertainty', 'extraction_status')
    value = {k: copy.deepcopy(item[k]) for k in keys if k in item}
    if item.get('provenance') != 'source_span_reconstruction' and 'draft_text' in item:
        value['draft_text'] = item['draft_text']
    return value


def item_hash(item):
    return extraction.digest(semantic_item(item))


def stamp_ownership(wrapper, result):
    """Called after successful compact hydration, never from model-owned JSON."""
    spans = getattr(wrapper, '_owned_source_spans', None)
    if spans is None or not result.get('ok') or result.get('truncated') is not False:
        return
    by_id = {s.id:s for s in spans}
    receipts = []
    for item in (result.get('parsed') or {}).get('items', []):
        span = by_id.get(item.get('source_span_id'))
        if span is None:
            raise ValueError('Hydrated source ownership missing')
        receipts.append(dict(producer_item_id=item['item_id'], producer_revision=item['revision'],
            producer_call_id=result.get('call_id'), item_hash=item_hash(item), source_span_ids=[span.id]))
    result['source_ownership'] = receipts


def current_revision(item, items):
    revision = item.get('revision')
    current = type(revision) is int and revision >= 1 and revision == max(
        (other.get('revision', 0) for other in items if other.get('item_id') == item.get('item_id')
         and type(other.get('revision')) is int), default=0)
    same = [other for other in items if other.get('item_id') == item.get('item_id') and other.get('revision') == revision]
    return current and len({item_hash(other) for other in same}) == 1


def owned_sources(item, producer, spans, references, document_id):
    """Exact runtime receipts, or explicit REF IDs resolved in the source index."""
    receipts = [r for r in producer.get('source_ownership', []) if r.get('producer_item_id') == item.get('item_id')]
    if receipts:
        result = []
        for r in receipts:
            if r.get('producer_revision') != item.get('revision') or r.get('item_hash') != item_hash(item):
                continue
            for identifier in r.get('source_span_ids', []):
                span = spans.get(identifier)
                if span is not None:
                    result.append(dict(source_span_id=span.id, source_unit_id=span.unit_id or None,
                        source_ref_ids=[], source_hash=extraction.digest(span.text), text=span.text,
                        producer_call_id=r.get('producer_call_id'), ownership='compact_partition'))
        return result
    # A reference is explicit only in its structured field, never paragraph/prose.
    result = []
    explicit_refs=list(item.get('ref_ids', [])) if isinstance(item.get('ref_ids'), list) else []
    if isinstance(item.get('ref'),str) and item['ref'] not in explicit_refs:
        explicit_refs.append(item['ref'])
    for ref in explicit_refs:
        if not isinstance(ref,str):
            continue
        entry = references.get(ref)
        if entry and entry.get('document_id') == document_id and entry.get('input_type') == 'operational' and entry.get('text_excerpt'):
            result.append(dict(source_span_id=None, source_unit_id=entry.get('location', {}).get('unit_id'),
                source_ref_ids=[ref], source_hash=extraction.digest(entry['text_excerpt']), text=entry['text_excerpt'],
                producer_call_id=producer.get('call_id'), ownership='reference_index'))
    return result


def delivery_scope(producer):
    """('single', False) for one PROCESSOR call; ('merged', partial) for a
    partition-merged delivery (bounded_extraction.merge carries missing_partitions),
    partial when a partition is missing."""
    if isinstance(producer, dict) and 'missing_partitions' in producer:
        return 'merged', producer.get('complete') is False
    return 'single', False


def build(run_id, document, producer, references):
    """Return private pair inputs and payload-free unavailability receipts."""
    producer = producer or {}
    items = (producer.get('parsed') or {}).get('items', [])
    refs = {r['ref_id']:r for r in references}
    try:
        spans = {s.id:s for s in extraction.ledger(document['text'], document['id'])}
    except ValueError:
        # Failed structural span reconstruction grants no ownership. Explicit
        # reference-index units remain independently usable; never guess offsets.
        spans = {}
    pairs, unavailable, seen = [], [], set()
    scope, partial = delivery_scope(producer)
    for item in items:
        reason = None
        # The delivery-level refusal (ok, truncated, complete) applies to a SINGLE
        # PROCESSOR call, whose best-effort object is not a draft. A partition-merged
        # delivery already contains only the items of accepted, untruncated partitions
        # (bounded_extraction.merge), each bound to its span by an ownership receipt,
        # and the fidelity comparison is span-local by construction; a missing
        # partition is a document-level fact that run completion and the integrity
        # assessment already refuse (semantic_incomplete, pipeline_not_completed). The
        # gate used to read the whole delivery per item, so one refused partition
        # discarded every accepted one, and the advisory classifier had no pairs.
        # Pairs from a partial delivery are marked, and require a receipt.
        if scope == 'single' and (not producer.get('ok') or producer.get('truncated') is not False
                                  or producer.get('complete') is False):
            reason = 'incomplete_producer_delivery'
        elif not item.get('item_id') or not current_revision(item, items):
            reason = 'stale_or_invalid_producer_revision'
        else:
            sources = owned_sources(item, producer, spans, refs, document['id'])
            if not sources:
                reason = 'no_explicit_current_source_pair'
            elif partial and any(s.get('ownership') != 'compact_partition' for s in sources):
                reason = 'partial_delivery_without_receipt'
        if reason:
            unavailable.append(dict(status='AUDITOR_PAIR_UNAVAILABLE', producer_item_id=item.get('item_id'),
                producer_revision=item.get('revision'), reason=reason))
            continue
        for source in sources:
            identity = dict(run_id=run_id, document_id=document['id'], producer_agent='PROCESSOR',
                producer_item_id=item['item_id'], producer_revision=item['revision'],
                source_span_id=source['source_span_id'], source_unit_id=source['source_unit_id'],
                source_ref_ids=source['source_ref_ids'], source_hash=source['source_hash'])
            identifier = 'auditor-pair-' + extraction.digest(identity)
            if identifier in seen:
                continue
            seen.add(identifier)
            record = dict(identity, schema_version=VERSION, pair_id=identifier,
                producer_call_id=source['producer_call_id'], ownership=source['ownership'],
                producer_checkpoint=168, producer_adapter_sha256=final_models.PINS['producer']['adapter'],
                auditor_checkpoint=896, auditor_adapter_sha256=final_models.PINS['auditor']['adapter'],
                auditor_relation=None, classifier_status='pending',
                delivery='partial' if partial else 'complete')
            pairs.append(dict(record=record, source_text=source['text'], producer_item=semantic_item(item)))
    if not items:
        unavailable.append(dict(status='AUDITOR_PAIR_UNAVAILABLE', producer_item_id=None,
            producer_revision=None, reason='no_producer_items'))
    return pairs, unavailable, len(items)


def validate(record):
    if (record.get('schema_version') != VERSION or record.get('auditor_checkpoint') != 896 or
        record.get('producer_checkpoint') != 168 or type(record.get('producer_revision')) is not int or
        not record.get('producer_item_id') or not record.get('source_hash') or
        not (record.get('source_span_id') or record.get('source_ref_ids'))):
        raise ValueError('Invalid Auditor pair contract')
    identity = {k:record[k] for k in ('run_id','document_id','producer_agent','producer_item_id','producer_revision',
        'source_span_id','source_unit_id','source_ref_ids','source_hash')}
    if record['pair_id'] != 'auditor-pair-' + extraction.digest(identity):
        raise ValueError('Auditor pair identity mismatch')


def predict(pair, context):
    pair['_forward_attempted'] = False
    record = pair['record']
    validate(record)
    value = dict(role='auditor', production_contract='semantic-task-v1',
        source_spans=[dict(alias='s0', text=pair['source_text'])], context_only_spans=[],
        extraction=json.dumps(pair['producer_item'], sort_keys=True, ensure_ascii=False),
        supplied_refs=record['source_ref_ids'], required_refs=record['source_ref_ids'],
        delivery_complete=True, routed_rules=[])
    messages, _ = final_models.classifier_messages(value)
    tokenizer, classifier = final_models.resident('auditor', context)
    ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    if len(ids) > classifier.model.config.max_position_embeddings:
        raise ValueError('Auditor pair exceeds context; no truncation')
    directory = context.audit_dir()/'feature_admission'/record['pair_id'] if context else None
    pair['_forward_attempted'] = True
    return classifier.predict(ids, directory), len(ids)


def eligible(wrapper, payload):
    return (final_models.mode() == 'final' and wrapper.name == 'VERIFIER' and
        wrapper.backend == 'local_auditor' and payload.get('task') == TASK and
        getattr(wrapper, '_auditor_pair_request', None) is not None)


def prepare_context(wrapper, payload):
    wrapper._auditor_pair_state = None
    if not eligible(wrapper, payload):
        return payload
    request = wrapper._auditor_pair_request
    context = wrapper.run_context
    run_id = context.run_id if context else 'unscoped'
    begin = time.perf_counter()
    pairs, unavailable, items = build(run_id, request['document'], request['producer'], request['references'])
    records, calls = [], []
    for pair in pairs:
        record = pair['record']
        call_id = uuid.uuid4().hex
        start, stamp, tokens, failure = time.perf_counter(), telemetry.now(), None, None
        with telemetry.LOCK:
            if context is not None:
                context._active_model_calls = getattr(context,'_active_model_calls',0)+1
        try:
            validate(record)
            relation, tokens = predict(pair, context)
            if relation not in RELATIONS:
                raise ValueError('Invalid classifier relation')
            record.update(auditor_relation=relation, classifier_status='classified')
        except Exception as exc:
            failure = type(exc).__name__
            record.update(classifier_status='failed', failure_category=failure)
        finally:
            with telemetry.LOCK:
                if context is not None:
                    context._active_model_calls -= 1
        end = time.perf_counter()
        record['classifier_call_id'] = call_id
        record['forward_attempted'] = pair.get('_forward_attempted')
        records.append(record); calls.append(call_id)
        telemetry.emit(context, 'auditor_pair', **{k:v for k,v in record.items() if k not in {'schema_version','run_id'}})
        telemetry.emit(context, 'model_call', call_id=call_id, agent='AUDITOR896', logical_role='pair_classifier',
            backend='local_auditor_classifier', **final_models.identity('auditor'),
            task_id=getattr(wrapper,'_observation_task',None), wave_id=getattr(wrapper,'_observation_wave',None),
            phase='5', pair_id=record['pair_id'], parent_call_ids=[record['producer_call_id']] if record['producer_call_id'] else [],
            start_monotonic_s=start, end_monotonic_s=end, started_at=stamp, completed_at=telemetry.now(),
            total_service_seconds=end-start, input_tokens=tokens, output_tokens=0,
            backend_success=failure is None, failure_category=failure, contract_valid=failure is None,
            emitted_count=0, retained_count=0, truncated=False, cap_hit=False,
            retry_count=0, finish_reason='classification' if failure is None else None,
            unavailable={'semantically_complete':'No quality oracle','confidence':'Classifier exposes only a four-way label',
                         'first_token_at':'Non-generative invocation'})
    for record in unavailable:
        telemetry.emit(context, 'auditor_pair_unavailable', document_id=request['document']['id'], **record)
    scope, partial = delivery_scope(request['producer'] or {})
    telemetry.emit(context, 'auditor_pair_coverage', document_id=request['document']['id'],
        producer_items=items, pairs_constructed=len(records), unavailable_items=len(unavailable),
        eligible_producer_items=len({(r['producer_item_id'],r['producer_revision']) for r in records}),
        classifier_calls=len(calls), failed_pairs=sum(r['classifier_status']=='failed' for r in records),
        delivery='partial' if partial else 'complete',
        pairs_from_partial_delivery=sum(r.get('delivery')=='partial' for r in records))
    wrapper._auditor_pair_state = records
    producer=request['producer'] or {}
    parents=([producer['call_id']] if producer.get('call_id') else list(producer.get('partition_calls',[])))
    wrapper._parent_call_ids = list(dict.fromkeys(parents + calls))
    telemetry.emit(context, 'auditor_pair_barrier', document_id=request['document']['id'],
        classifier_call_ids=calls, start_monotonic_s=begin, end_monotonic_s=time.perf_counter(),
        consumer='VERIFIER', reason='advisory_pair_context_ready')
    result = dict(payload)
    context_pairs = [dict(record, producer_item=pair['producer_item'],
        source_evidence=dict(text=pair['source_text'], source_hash=record['source_hash'],
                             source_span_id=record['source_span_id'], source_ref_ids=record['source_ref_ids']))
        for pair,record in zip(pairs,records)]
    result['auditor_pair_context'] = dict(schema_version=VERSION, pairs=context_pairs, unavailable=unavailable,
        interpretation='Advisory pair classifications, not findings. Retain independent reasoning, evidence and refusal. Agreement is not required.')
    return result


def finding_pair(item, records):
    # Explicit pair identifier, or the complete Producer revision/source identity.
    found = []
    for r in records:
        direct = item.get('auditor_pair_id') == r['pair_id']
        for key in ('producer_item_id','producer_revision','source_span_id','source_ref_ids'):
            if key in item and item[key] != r[key]:
                direct = False
        owned = (item.get('producer_item_id') == r['producer_item_id'] and
            item.get('producer_revision') == r['producer_revision'] and
            (bool(r['source_span_id']) and item.get('source_span_id') == r['source_span_id'] or
             bool(r['source_ref_ids']) and item.get('source_ref_ids') == r['source_ref_ids']))
        if direct or owned:
            found.append(r)
    return found[0] if len(found) == 1 else None


def compare(wrapper, result):
    records = getattr(wrapper, '_auditor_pair_state', None)
    if records is None:
        return
    parsed = (result or {}).get('parsed') or {}
    try:
        wire=json.loads((result or {}).get('raw_text',''))
    except (ValueError,TypeError):
        wire={}
    refused=parsed.get('status')=='refused' or isinstance(wire,dict) and wire.get('status')=='refused'
    findings = parsed.get('items', [])
    joins = []
    for item in findings:
        pair = finding_pair(item, records) if result.get('ok') else None
        comparable = pair is not None and pair['classifier_status']=='classified' and item.get('finding') in RELATIONS
        joins.append(dict(finding_id=item.get('item_id'), finding_revision=item.get('revision'),
            auditor_pair_id=pair['pair_id'] if pair else None, verifier_relation=item.get('finding'),
            agreement=('agree' if pair['auditor_relation']==item['finding'] else 'disagree') if comparable else 'not_comparable'))
    telemetry.emit(wrapper.run_context, 'auditor_verifier_join', verifier_call_id=(result or {}).get('call_id'),
        pair_ids=[r['pair_id'] for r in records], findings=joins, finding_count=len(findings),
        empty=not findings, refused=bool(refused), verifier_ok=bool((result or {}).get('ok')))
    # Do not modify parsed findings, acceptance, refusal or the bus contract.


def contract_self_check():
    source='structural fixture'
    spans=extraction.ledger(source,'fixture')
    item=dict(item_id='PROCESSOR:fixture:item',revision=1,claims_referenced=['fixture'])
    producer=dict(ok=True,truncated=False,parsed=dict(items=[item]),source_ownership=[dict(
        producer_item_id=item['item_id'],producer_revision=1,producer_call_id='fixture-call',
        item_hash=item_hash(item),source_span_ids=[spans[0].id])])
    pairs, missing, _ = build('fixture-run',dict(id='fixture',text=source),producer,[])
    if len(pairs)!=1 or missing:
        raise RuntimeError('Auditor pairing integration self-check failed')
    validate(pairs[0]['record'])
    unowned=copy.deepcopy(producer);unowned['source_ownership']=[]
    if build('fixture-run',dict(id='fixture',text=source),unowned,[])[0]:
        raise RuntimeError('Auditor missing ownership gate guesses pairs')
    changed=copy.deepcopy(producer);changed['parsed']['items'][0]['revision']=2
    if build('fixture-run',dict(id='fixture',text=source),changed,[])[0]:
        raise RuntimeError('Auditor stale revision gate missing')
    if finding_pair(dict(paragraph=1,finding='MATCH'),[pairs[0]['record']]) is not None:
        raise RuntimeError('Auditor finding join guesses ownership')
    return True


def record_unavailable(context, document_id, reason):
    """The two coverage events prepare_context emits, for a document whose VERIFIER
    call was never made (no PROCESSOR draft to verify): the analyzer's pairing
    figures then say unavailable with the reason instead of saying nothing."""
    telemetry.emit(context, 'auditor_pair_unavailable', document_id=document_id,
        status='AUDITOR_PAIR_UNAVAILABLE', producer_item_id=None, producer_revision=None, reason=reason)
    telemetry.emit(context, 'auditor_pair_coverage', document_id=document_id, producer_items=0,
        pairs_constructed=0, unavailable_items=1, eligible_producer_items=0, classifier_calls=0, failed_pairs=0,
        delivery='none', pairs_from_partial_delivery=0)
