"""Focused integration gate; never chains into multi-round or a model workload."""
import builtins
import io
import json
from pathlib import Path
import socket
import sys
import types
import unittest
from unittest.mock import patch


def main():
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.split('.')[0] in {'torch','transformers','sentence_transformers','anthropic','openai','easyocr'}:
            raise AssertionError('Model/provider import prohibited by deterministic gate')
        return original(name,*args,**kwargs)
    original_connect=socket.socket.connect
    def denied(sock, address):
        # Windows asyncio uses a loopback socketpair for its wakeup pipe.
        if isinstance(address,tuple) and address[0] in {'127.0.0.1','::1'}:
            return original_connect(sock,address)
        raise AssertionError('Network prohibited by deterministic gate')
    out=Path(__file__).resolve().parents[1]/'docs/fix/final_model_integration'
    out.mkdir(parents=True,exist_ok=True)
    with patch.object(builtins,'__import__',guarded),patch.object(socket.socket,'connect',denied), \
         patch.dict(sys.modules,ontology_gnn=types.ModuleType('ontology_gnn')):
        modules=['final_integration_checks','auditor_pair_checks','compact_contract_checks','execution_topology_checks','report_recommendations_checks','decoding_policy_checks','ordinary_final_correction_checks']
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(__import__(name)) for name in modules)
        stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        (out/'no_generation_tests.log').write_text(stream.getvalue(),encoding='utf8')
        import final_integration_checks as checks
        import final_models
        import model_telemetry
        def run_test(name):
            log=io.StringIO()
            return unittest.TextTestRunner(stream=log).run(checks.IntegrationChecks(name)).wasSuccessful()
        proofs=[]
        for name,neutralizer in [
            ('test_wrong_producer_checkpoint_refuses',lambda:patch.object(final_models,'require',lambda *a:None)),
            ('test_overlap_and_handoff',lambda:patch.object(model_telemetry,'union',lambda intervals:sum(b-a for a,b in intervals))),
            ('test_ordinary_final_admission_requires_valid_pair_contract',lambda:patch.object(final_models,'admit_ordinary',lambda:None))]:
            before=run_test(name)
            with neutralizer(): broken=run_test(name)
            restored=run_test(name)
            proofs.append(dict(check=name,baseline_pass=before,neutralized_test_failed=not broken,restored_pass=restored))
        # The frozen decoding policy at both local generate sites: each proof
        # neutralizes the one mechanism that produces the asserted behaviour and
        # counts that the neutralized branch actually ran (THIRTEEN-B).
        import decoding_policy
        import decoding_policy_checks
        def run_decoding_test(name):
            return unittest.TextTestRunner(stream=io.StringIO()).run(decoding_policy_checks.DecodingPolicyChecks(name)).wasSuccessful()
        for name,owner,attribute,mutant in decoding_policy_checks.NEUTRALIZATIONS:
            invocations=[]
            def replacement(*a,_mutant=mutant,**k):
                invocations.append(1)
                return _mutant(*a,**k)
            before=run_decoding_test(name)
            with patch.object(owner,attribute,replacement): broken=run_decoding_test(name)
            restored=run_decoding_test(name)
            proofs.append(dict(check=name,baseline_pass=before,neutralized_test_failed=not broken,
                               restored_pass=restored,mutated_branch_invocations=len(invocations)))
            if not invocations:
                proofs[-1]['neutralized_test_failed']=False
        # The four v5 corrections (grounding, validated prompt shape, core-field
        # alias, typed-record example and the no-draft VERIFIER skip): the same
        # neutralize/fail/restore/pass with invocation counting.
        import ordinary_final_correction_checks as corrections
        def run_correction_test(name):
            return unittest.TextTestRunner(stream=io.StringIO()).run(corrections.CorrectionChecks(name)).wasSuccessful()
        for name,owner,attribute,mutant in corrections.NEUTRALIZATIONS:
            invocations=[]
            def replacement(*a,_mutant=mutant,**k):
                invocations.append(1)
                return _mutant(*a,**k)
            before=run_correction_test(name)
            with patch.object(owner,attribute,replacement): broken=run_correction_test(name)
            restored=run_correction_test(name)
            proofs.append(dict(check=name,baseline_pass=before,neutralized_test_failed=not broken,
                               restored_pass=restored,mutated_branch_invocations=len(invocations)))
            if not invocations:
                proofs[-1]['neutralized_test_failed']=False
        import activation_checks
        activation_status,activation_detail=activation_checks.check()
        import auditor_pairs
        import auditor_pair_checks
        original_compare=auditor_pairs.compare
        def broadcast(wrapper,result):
            original_compare(wrapper,result)
            for finding in result['parsed']['items']:
                finding['finding']=wrapper._auditor_pair_state[0]['auditor_relation']
        def forged_sources(item,producer,spans,references,document_id):
            span=next(iter(spans.values()))
            return [dict(source_span_id=span.id,source_unit_id=span.unit_id or None,source_ref_ids=[],
                source_hash=auditor_pairs.extraction.digest(span.text),text=span.text,
                producer_call_id=producer.get('call_id'),ownership='invalid_fixture_fallback')]
        for name,neutralizer in [
            ('test_ownership_excludes_invalid_span_and_foreign_ref',lambda:patch.object(auditor_pairs,'owned_sources',forged_sources)),
            ('test_stale_revision_excluded',lambda:patch.object(auditor_pairs,'current_revision',lambda *a:True)),
            ('test_no_guess_from_paragraph_or_prose',lambda:patch.object(auditor_pairs,'owned_sources',forged_sources)),
            ('test_multiple_findings_not_relabelled_and_join_only_explicit',lambda:patch.object(auditor_pairs,'compare',broadcast))]:
            def run_pair_test():
                return unittest.TextTestRunner(stream=io.StringIO()).run(auditor_pair_checks.PairChecks(name)).wasSuccessful()
            before=run_pair_test()
            with neutralizer():broken=run_pair_test()
            restored=run_pair_test()
            proofs.append(dict(check=name,baseline_pass=before,neutralized_test_failed=not broken,restored_pass=restored))
        receipt=dict(passed=result.wasSuccessful() and activation_status=='PASS' and all(all(p[k] for k in
            ['baseline_pass','neutralized_test_failed','restored_pass']) for p in proofs),tests=result.testsRun,
            failures=len(result.failures),errors=len(result.errors),activation_status=activation_status,
            activation_detail=activation_detail,neutralize_fail_restore_pass=proofs,
            model_loads=0,network_allowed=False,multi_round_executed=False)
        (out/'validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
        print(json.dumps(receipt,indent=2))
        return 0 if receipt['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
