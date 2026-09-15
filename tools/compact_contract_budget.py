"""Reproducible local cached-tokenizer capacity evidence. No weights or network."""
import os
os.environ['USE_TORCH'] = '0'
os.environ['USE_TF'] = '0'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
import hashlib
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/fix/compact_contract_ab'
sys.path.insert(0,str(ROOT/'scripts'))


def main():
    def denied(*a, **k): raise AssertionError('Network prohibited in tokenizer gate')
    socket.socket.connect = denied
    socket.create_connection = denied
    from transformers import AutoTokenizer, AutoConfig
    import transformers, tokenizers
    import bounded_extraction as ex
    import compact_contracts as cc
    from compact_contract_checks import FIXTURE, REFS, representative_producer, representative_auditor, wrapper
    doc, source = FIXTURE['doc'], FIXTURE['source']
    spans = ex.ledger(source,doc)
    producer = representative_producer()
    auditor = representative_auditor()
    old_producer = dict(agent='PROCESSOR',doc_id=doc,items=[dict(
        section_id=ex.wire_id(spans[0]),draft_text=ex.wire_id(spans[0]),extraction_method='source_span',
        claims_referenced=producer['items'][0]['claims'],open_questions=producer['items'][0]['questions'],
        ref='REF-0001',kind='extraction',confidence='UNCERTAIN',ref_ids=REFS)])
    old_auditor = dict(agent='VERIFIER',doc_id=doc,items=[dict(
        auditor['items'][0],paragraph=1,ref='REF-0001',kind='finding')])
    # Old representative outputs are authored VALID compact/fidelity answers,
    # not the failed remote outputs and not padded with optional numeric records.
    for name,obj in [('PROCESSOR',old_producer),('VERIFIER',old_auditor)]:
        assert not wrapper(name).parse_contract_output(json.dumps(obj))[1]
    assert ex.hydrate(old_producer,spans,doc)['items'][0]['draft_text']==source
    records=json.loads((OUT/'checkpoint_and_old_prompt.json').read_text())
    report=dict(generation=False,network=False,transformers=transformers.__version__,tokenizers=tokenizers.__version__,
                ceiling=384,max_time_seconds=25,counts={},assertions=[])
    prompts=dict(producer=cc.producer_prompt(spans,spans,doc),
                 auditor=cc.auditor_prompt(source,FIXTURE['extraction'],REFS))
    for role, old_obj, new_obj in [('producer',old_producer,producer),('auditor',old_auditor,auditor)]:
        metadata=records[role]
        assert json.loads((ROOT/'config/local_models.json').read_text())['active_'+role]==metadata['model']
        assert json.loads((ROOT/'tools/cloud_run/models.json').read_text())[metadata['model']]==metadata['revision']
        path=Path.home()/'.cache/huggingface/hub'/('models--'+metadata['model'].replace('/','--'))/'snapshots'/metadata['revision']
        config=AutoConfig.from_pretrained(str(path),local_files_only=True)
        tok=AutoTokenizer.from_pretrained(str(path),local_files_only=True)
        count=lambda s:len(tok.encode(s,add_special_tokens=False))
        old_user=(OUT/f'old_{role}_user.txt').read_bytes().decode()
        render=lambda s:tok.apply_chat_template([dict(role='user',content=s)],tokenize=False,add_generation_prompt=True)
        old_render=render(old_user)
        assert hashlib.sha256(old_render.encode()).hexdigest()==metadata['rendered_sha256']
        assert count(old_render)==metadata['input_tokens']
        new_render=render(prompts[role])
        for suffix,value in [('user',prompts[role]),('rendered',new_render)]:
            (OUT/f'new_{role}_{suffix}.txt').write_bytes(value.encode())
        outputs={}
        for version,obj in [('old',old_obj),('new',new_obj)]:
            text=json.dumps(obj,separators=(',',':'))
            (OUT/f'{version}_{role}_representative.json').write_bytes(text.encode())
            outputs[version]=count(text)
        if role=='producer':
            old_min=json.loads(json.dumps(old_obj)); new_min=json.loads(json.dumps(new_obj))
            old_min['items'][0].update(claims_referenced=[],open_questions=[],ref_ids=[],ref='document-level')
            new_min['items'][0].update(claims=[],questions=[],uncertainty=[],status='empty',refs=[])
        else:
            old_min=dict(agent='VERIFIER',doc_id=doc,items=[]);new_min=dict(items=[])
        minimum={v:count(json.dumps(o,separators=(',',':'))) for v,o in [('old',old_min),('new',new_min)]}
        assert outputs['new'] < 256, 'Representative must leave at least 128 tokens margin'
        assert outputs['new'] < outputs['old']
        assert count(new_render)<count(old_render)
        report['counts'][role]=dict(prompt_before=count(old_render),prompt_after=count(new_render),
            representative_before=outputs['old'],representative_after=outputs['new'],
            minimal_before=minimum['old'],minimal_after=minimum['new'],
            output_margin=384-outputs['new'],new_rendered_sha256=hashlib.sha256(new_render.encode()).hexdigest())
        report['counts'][role]['checkpoint']=dict(model_type=config.model_type,config_class=type(config).__name__,
            architectures=config.architectures,tokenizer_class=type(tok).__name__,
            metadata_sha256={name:hashlib.sha256((path/name).read_bytes()).hexdigest()
                             for name in ('config.json','tokenizer_config.json','generation_config.json')})
        report['assertions'].append(role+': exact old hash/count, smaller prompt/output, representative <256')
        if role=='auditor':
            verbose=json.loads(json.dumps(new_obj))
            verbose['items'][0]['reasoning'] += ' The extraction retains the planned label, reported label, units, quantities and unanswered date question.'*12
            cc.auditor(verbose,doc,REFS,REFS)
            report['verbose_auditor_tokens']=count(json.dumps(verbose,separators=(',',':')))
            assert report['verbose_auditor_tokens'] <384
        else:
            copy_user=('Extract every explicit CLM-* claim id and missing information without inventing facts.\n'
                +(OUT/'old_producer_contract.txt').read_bytes().decode()+'\nDocument id: '+doc
                +'\nReturn one item for the paragraph, section_id=paragraph-1, extraction_method=verbatim. Copy all source exactly into draft_text.\nSOURCE:\n'+source)
            copy_render=render(copy_user)
            assert count(copy_render)==482
            copy_hash=hashlib.sha256(copy_render.encode()).hexdigest()
            assert copy_hash=='dea857a71db6db817dce4af130762405a19858e6a2bda813d59cd3c0c17f4cb2'
            for suffix,value in [('user',copy_user),('rendered',copy_render)]:
                (OUT/f'old_source_copy_{suffix}.txt').write_bytes(value.encode())
            report['source_copy_reference']=dict(input_tokens=482,rendered_sha256=copy_hash)
    report['readiness_capacity']='PASS'
    (OUT/'token_budget.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
