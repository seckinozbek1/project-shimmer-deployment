"""Local fixture/regression/mutation gate. Never loads weights or calls providers."""
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/fix/compact_contract_ab'


def mutations():
    import compact_contracts as cc
    import bounded_extraction as ex
    from compact_contract_checks import FIXTURE,REFS,representative_producer,representative_auditor,wrapper
    from effect_proof import prove_effect
    proofs=[]
    doc=FIXTURE['doc']; spans=ex.ledger(FIXTURE['source'],doc)
    def source():
        return ''.join(i['draft_text'] for i in cc.producer(representative_producer(),spans,doc)['items'])
    proofs.append(prove_effect(name='compact_source_reconstruction',validate=lambda:bool(spans),
        observe=source,check=lambda:('PASS' if source()==FIXTURE['source'] else 'FAIL',''),
        neutralise=lambda:patch.object(ex,'hydrate',lambda obj,*a:obj)))
    w=wrapper('VERIFIER');cc.bind_auditor(w,doc,REFS)
    bad=representative_auditor();bad['items'][0]['ref_ids']=REFS[:1]
    original=cc.auditor
    def evidence():return bool(w.parse_contract_output(json.dumps(bad))[1])
    proofs.append(prove_effect(name='required_evidence',validate=lambda:len(REFS)==2,
        observe=evidence,check=lambda:('PASS' if evidence() else 'FAIL',''),
        neutralise=lambda:patch.object(cc,'auditor',lambda obj,doc,required,available,**k:original(obj,doc,[],available,**k))))
    raw=json.dumps(representative_auditor())+'{"items":['
    def complete():return bool(w.parse_contract_output(raw)[1])
    proofs.append(prove_effect(name='no_complete_prefix_recovery',validate=lambda:raw.endswith('['),
        observe=complete,check=lambda:('PASS' if complete() else 'FAIL',''),
        neutralise=lambda:patch.object(w,'_compact_contract',None)))
    def isolated():return 'CONV-001' not in w._output_contract_text()
    proofs.append(prove_effect(name='task_contract_isolation',validate=lambda:w.name=='VERIFIER',
        observe=isolated,check=lambda:('PASS' if isolated() else 'FAIL',''),
        neutralise=lambda:patch.object(w,'_compact_contract',None)))
    return proofs


def main():
    # Reuse maintained model/network barriers and baseline regression selection.
    import report_recommendations_no_generation_gate as base
    class Capture(io.StringIO):
        def reconfigure(self, **kwargs): pass
    capture=Capture()
    with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
        base_status=base.main()
        import compact_contract_checks as checks
        result=unittest.TextTestRunner(stream=capture,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(checks))
        import verify_session1 as legacy
        selected={'18','39','135','149','150','151','194'}
        regressions=[]
        for title,check in legacy.CHECKS:
            if title.split()[0] in selected:
                if title.split()[0]=='151':
                    # Exercise the live projection function without importing
                    # pipeline's unrelated GNN/model dependencies.
                    import ast, types, sys, finding_record
                    tree=ast.parse((ROOT/'scripts/pipeline.py').read_text(encoding='utf-8'))
                    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_typed_for_agent')
                    module=types.ModuleType('pipeline');module.finding_record=finding_record
                    exec(compile(ast.Module(body=[fn],type_ignores=[]),'live_typed_projection','exec'),module.__dict__)
                    with patch.dict(sys.modules,{'pipeline':module}):status,detail=check()
                    detail='Source-isolated live _typed_for_agent: '+detail
                else:status,detail=check()
                regressions.append(dict(check=title,status=status,detail=detail))
        proofs=mutations()
    import ast
    base_counts=ast.literal_eval(next(l.split('ORDINARY_SAFE_GATE ',1)[1] for l in capture.getvalue().splitlines() if l.startswith('ORDINARY_SAFE_GATE ')))
    report=dict(base_status=base_status,base_counts=base_counts,new_tests=result.testsRun,
                new_failures=len(result.failures)+len(result.errors),regressions=regressions,mutations=proofs,
                model_generation=False,cloud=False,paid_api=False,full_pipeline=False,multi_round=False)
    report['passed_checks']=base_counts['PASS']+result.testsRun-len(result.failures)-len(result.errors)+sum(r['status']=='PASS' for r in regressions)
    report['status']='PASS' if base_status==0 and result.wasSuccessful() and all(r['status']=='PASS' for r in regressions) else 'FAIL'
    (OUT/'validation.log').write_text(capture.getvalue(),encoding='utf-8')
    (OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
