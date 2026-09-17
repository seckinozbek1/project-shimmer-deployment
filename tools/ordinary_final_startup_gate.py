"""Run cache/startup preparation regressions with model and network imports blocked."""
import argparse
import builtins
import io
import json
from pathlib import Path
import socket
import sys
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def main(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        level=kwargs.get('level',args[3] if len(args)>3 else 0)
        if level == 0 and name.split('.')[0] in {'torch','transformers','sentence_transformers','anthropic','openai','easyocr'}:
            raise AssertionError('Model/provider import prohibited')
        return original(name,*args,**kwargs)
    def denied(*args,**kwargs):raise AssertionError('Network prohibited')
    with patch.object(builtins,'__import__',guarded),patch.object(socket.socket,'connect',denied), \
         patch.object(socket,'create_connection',denied),patch.dict(sys.modules,ontology_gnn=types.ModuleType('ontology_gnn')):
        import ordinary_final_startup_checks as startup
        import ordinary_final_preparation_checks as preparation
        import ordinary_final_run as run
        import semantic_waves
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (startup,preparation))
        stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        proofs=[]
        def single(name):
            return unittest.TextTestRunner(stream=stream,verbosity=2).run(startup.StartupChecks(name)).wasSuccessful()
        def old_admission(directory,model):
            run.require((Path(directory)/'refs/main').read_text().strip()==model['revision'],'Cache revision mismatch')
        for name,mutation in [
            ('test_exact_ref_admission_rejects_whitespace',lambda:patch.object(run,'admit_cache_ref',old_admission)),
            ('test_asset_builder_ref_bytes_reconcile_with_real_resolver',lambda:patch.object(startup,'build_assets',
                broken_builder(startup.build_assets))),
            ('test_same_family_still_refuses',lambda:patch.object(semantic_waves,'validate_model_families',lambda *a:None))]:
            before=single(name)
            with mutation():failed=not single(name)
            after=single(name)
            proofs.append(dict(check=name,baseline_pass=before,neutralized_fail=failed,restored_pass=after))
        (out/'startup_tests.log').write_text(stream.getvalue(),encoding='utf8')
        receipt=dict(passed=result.wasSuccessful() and all(all(p[k] for k in ('baseline_pass','neutralized_fail','restored_pass')) for p in proofs),
            tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),effect_proofs=proofs,
            model_loads=0,network_allowed=False,multi_round_executed=False)
        (out/'startup_validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt,indent=2))
        return 0 if receipt['passed'] else 1


def broken_builder(original):
    def build(path,models,wheels,cache,wheelhouse):
        import prepare_ordinary_final_assets as assets
        actual=assets.cache_ref_bytes
        with patch.object(assets,'cache_ref_bytes',lambda m:actual(m)+b'\n'):
            return original(path,models,wheels,cache,wheelhouse)
    return build


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    raise SystemExit(main(parser.parse_args().output_dir))
