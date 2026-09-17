"""No-generation regression of the exact final-profile offline startup guard."""
import argparse
import ast
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/fix/ordinary_final_cloud_run'
sys.path[:0] = [str(ROOT/'scripts'), str(next((ROOT/'output/cloud_wheels/ordinary_final_cp312').glob('huggingface_hub-*.whl')))]
import huggingface_hub
import huggingface_hub.constants
import agent_activation
import agent_wrapper
import execution_topology
import semantic_waves
import ordinary_final_run as admission
from prepare_ordinary_final_assets import build_assets


def selected_functions(source, names, scope):
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'executed-source','exec'),scope)


class StartupChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name);self.cache = self.base/'hub'
        self.models = json.loads((BASE/'execution_manifest.json').read_text())['models']
        self.refs = []
        with tarfile.open(ROOT/'.tmp/ordinary_final_assets.tar') as archive:
            for model in self.models:
                folder = 'models--'+model['model_id'].replace('/','--')
                directory = self.cache/folder
                snapshot = directory/'snapshots'/model['revision']
                snapshot.mkdir(parents=True);(directory/'refs').mkdir()
                prefix = 'hf_cache/hub/'+folder
                original = archive.extractfile(prefix+'/refs/main').read()
                self.assertEqual(original,model['revision'].encode()+b'\n')
                config = archive.extractfile(prefix+'/snapshots/'+model['revision']+'/config.json').read()
                self.assertEqual(hashlib.sha256(config).hexdigest(),model['files']['config.json']['sha256'])
                (snapshot/'config.json').write_bytes(config)
                (directory/'refs/main').write_bytes(original)
                model['cache_ref'] = dict(bytes=40,sha256=hashlib.sha256(model['revision'].encode()).hexdigest())
                self.refs.append((directory,model))
        with tarfile.open(BASE/'project.tar.gz') as archive:
            def content(name):return archive.extractfile(name).read()
            source = content('scripts/pipeline.py').decode()
            self.assertEqual(content('scripts/execution_topology.py'),(ROOT/'scripts/execution_topology.py').read_bytes().replace(b'\r\n',b'\n'))
            config = json.loads(content('config/local_models.json'))
            self.final = json.loads(content('config/final_models.json'))
        (self.base/'config').mkdir();(self.base/'config/local_models.json').write_text(json.dumps(config))
        scope = dict(Path=Path,json=json,argparse=argparse,agent_activation=agent_activation)
        selected_functions(source,{'_resolve_local_models','_build_arg_parser'},scope)
        assignments = [n for n in ast.parse(source).body if isinstance(n,ast.Assign)
                       and any(isinstance(t,ast.Name) and t.id=='_LOCAL_PROFILE' for t in n.targets)
                       and isinstance(n.value,ast.Dict)]
        self.assertEqual(len(assignments),1)
        profile = ast.literal_eval(assignments[0].value)
        self.profile = scope['_resolve_local_models'](profile,self.base)
        self.scope = dict(_build_arg_parser=scope['_build_arg_parser'],_LOCAL_PROFILE=self.profile,reached=[])
        exec('def body(argv=None):\n reached.append(True)\n return 0',self.scope)
        self.entry = execution_topology.entrypoint(self.scope['body'])
        self.topology = self.base/'topology.json';self.topology.write_text(json.dumps(admission.TOPOLOGY))
        self.args = list(admission.ARGV);self.args[self.args.index('--topology-config')+1] = str(self.topology)
        cache_patch=patch.object(huggingface_hub.constants,'HF_HUB_CACHE',str(self.cache))
        cache_patch.start();self.addCleanup(cache_patch.stop)
        self.assertEqual(huggingface_hub.__version__,'0.30.2')

    def invoke(self):
        # Replace scheduler construction/body only: actual parser, final profile,
        # topology guard, family detector and pinned resolver all execute.
        with patch.object(execution_topology,'Runtime',return_value=SimpleNamespace(close=lambda:None)), \
             patch.dict('os.environ',SHIMMER_MODEL_MODE='final',HF_HUB_OFFLINE='1'), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            try:return self.entry(self.args),errors.getvalue()
            except SystemExit as error:return error.code,errors.getvalue()

    def correct_refs(self):
        for directory,model in self.refs:
            (directory/'refs/main').write_bytes(admission.cache_ref_bytes(model))

    def test_exact_failed_configuration_and_causal_correction(self):
        identities = set(self.profile.values())
        self.assertEqual(identities,{('local_producer',self.final['producer']['model_id']),
                                    ('local_auditor',self.final['auditor']['model_id'])})
        self.assertEqual(self.profile['VERIFIER'][1],self.final['auditor']['model_id'])
        code,error = self.invoke()
        self.assertEqual(code,2);self.assertIn('Cannot establish independent cached local model families',error)
        self.assertFalse(self.scope['reached'])
        self.correct_refs()
        families = semantic_waves.validate_model_families(self.profile,agent_wrapper._local_checkpoint_path)
        self.assertEqual(families,dict(local_producer=['qwen2'],local_auditor=['llama']))
        self.assertEqual(self.invoke(),(0,''));self.assertEqual(self.scope['reached'],[True])

    def test_same_family_still_refuses(self):
        self.correct_refs()
        auditor = self.final['auditor']
        config = self.cache/('models--'+auditor['model_id'].replace('/','--'))/'snapshots'/auditor['revision']/'config.json'
        value=json.loads(config.read_text());value['model_type']='qwen2';config.write_text(json.dumps(value))
        code,error = self.invoke()
        self.assertEqual(code,2);self.assertIn('Cannot establish independent cached local model families',error)
        self.assertFalse(self.scope['reached'])

    def test_exact_ref_admission_rejects_whitespace(self):
        for directory,model in self.refs:
            for suffix in (b'\n',b'\r\n',b' '):
                (directory/'refs/main').write_bytes(model['revision'].encode()+suffix)
                with self.assertRaisesRegex(RuntimeError,'exact pinned revision'):
                    admission.admit_cache_ref(directory,model)
            (directory/'refs/main').write_bytes(admission.cache_ref_bytes(model))
            admission.admit_cache_ref(directory,model)

    def test_asset_builder_ref_bytes_reconcile_with_real_resolver(self):
        models = copy.deepcopy(self.models)
        for model in models:model['files']={'config.json':model['files']['config.json']}
        receipt=build_assets(self.base/'assets.tar',models,{},self.cache,self.base)
        with tarfile.open(self.base/'assets.tar') as archive:
            for directory,model in self.refs:
                name='hf_cache/hub/'+directory.name+'/refs/main'
                data=archive.extractfile(name).read()
                self.assertEqual(len(data),40)
                self.assertEqual(hashlib.sha256(data).hexdigest(),receipt['members'][name]['sha256'])
                (directory/'refs/main').write_bytes(data)
                admission.admit_cache_ref(directory,model)
        self.assertEqual(self.invoke(),(0,''))


if __name__=='__main__':unittest.main(verbosity=2)
