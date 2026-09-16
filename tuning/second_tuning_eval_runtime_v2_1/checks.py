"""Local-only nullability regression, pinned-source effects and lifecycle tests."""
import ast
from collections import OrderedDict, UserDict
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace, MappingProxyType
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'tuning/second_tuning_eval_runtime_v2'
sys.path.insert(0,str(HERE))
import legacy_checks as legacy
from config_state import ConfigSnapshot, UnsupportedConfig
runtime=legacy.runtime
Model=legacy.Model
TorchFacade=legacy.TorchFacade
EFFECTS={}

def old_runtime():
    spec=importlib.util.spec_from_file_location('historical_runtime_v2',OLD/'eval_runtime.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def state(model):
    return dict(training=[x.training for x in model.modules()],
                parameters=runtime.parameter_state(model),adapters=list(model.active_adapters),
                configs=[(id(x),name,id(x.__dict__[name])) for x in model.modules() for name in ('config','generation_config') if name in x.__dict__])

class NullabilityChecks(unittest.TestCase):
    def test_51_exact_cloud_failure_neutralise_fail_restore_pass(self):
        model=Model();model.child.generation_config=None;before=state(model)
        fixed=runtime.evaluation_state
        runtime.evaluation_state=old_runtime().evaluation_state
        try:
            with self.assertRaisesRegex(TypeError,'vars\\(\\) argument must have __dict__ attribute'):
                with runtime.evaluation_state(model,TorchFacade()):self.fail('Old context entered')
        finally:runtime.evaluation_state=fixed
        with runtime.evaluation_state(model,TorchFacade()):self.assertFalse(model.training)
        self.assertEqual(state(model),before);self.assertEqual(model.calls,[])
        EFFECTS['nullable_regression']=dict(sequence=['neutralise: historical context','fail: identical TypeError','restore: corrected context','pass: exact state restored'],real_generations=0)

    def test_52_none_matrix(self):
        for name in ('config','generation_config'):
            model=Model();setattr(model,name,None);before=state(model)
            with runtime.evaluation_state(model,TorchFacade()):self.assertIsNone(getattr(model,name))
            self.assertEqual(state(model),before)

    def test_53_empty_mapping(self):
        value={};snap=ConfigSnapshot([value]);value['added']=1;snap.restore();self.assertEqual(value,{})

    def test_54_populated_mapping(self):
        value={'use_cache':False,'optional':None};snap=ConfigSnapshot([value]);snap.enable_cache()
        self.assertTrue(value['use_cache']);snap.restore();self.assertEqual(value,{'use_cache':False,'optional':None})

    def test_55_namespace_and_nested_none(self):
        child=SimpleNamespace(optional=None);value=SimpleNamespace(use_cache=False,child=child)
        snap=ConfigSnapshot([value]);value.child=object();child.optional=4;snap.enable_cache();snap.restore()
        self.assertIs(value.child,child);self.assertIsNone(child.optional);self.assertFalse(value.use_cache)

    def test_56_immutable_scalars(self):
        values=[None,False,12,1.2,'config',b'x',complex(2,1)]
        for value in values:
            snap=ConfigSnapshot([value]);snap.enable_cache();snap.restore();self.assertIs(snap.roots[0],value)

    def test_57_tuple_with_mutable_child(self):
        child=[None];value=(1,child);snap=ConfigSnapshot([value]);child.append(3);snap.restore()
        self.assertIs(value[1],child);self.assertEqual(child,[None])

    def test_58_nested_list_identity(self):
        child=[None,{'use_cache':False}];value={'children':child};snap=ConfigSnapshot([value])
        nested=child[1];nested['use_cache']=True;child.clear();snap.restore()
        self.assertIs(value['children'],child);self.assertIs(child[1],nested);self.assertFalse(nested['use_cache'])

    def test_59_dataclass(self):
        @dataclass
        class C: use_cache:bool=False; optional:object=None
        value=C();snap=ConfigSnapshot([value]);snap.enable_cache();self.assertTrue(value.use_cache)
        value.optional='changed';snap.restore();self.assertEqual(value,C())

    def test_60_slotted_dataclass(self):
        @dataclass(slots=True)
        class C: use_cache:bool=False; optional:object=None
        value=C();snap=ConfigSnapshot([value]);snap.enable_cache();snap.restore();self.assertFalse(value.use_cache)

    def test_61_frozen_dataclass(self):
        @dataclass(frozen=True,slots=True)
        class C: use_cache:bool=False; optional:object=None
        value=C();snap=ConfigSnapshot([value]);snap.enable_cache();snap.restore();self.assertEqual(value,C())

    def test_62_ordered_mapping(self):
        value=OrderedDict([('a',None),('use_cache',False)]);snap=ConfigSnapshot([value])
        value.move_to_end('a');snap.enable_cache();snap.restore();self.assertEqual(list(value),['a','use_cache'])

    def test_63_shared_graph_and_cycle(self):
        shared=[];value={'a':shared,'b':shared};shared.append(value);snap=ConfigSnapshot([value,value])
        value['b']=[];shared.clear();snap.restore();self.assertIs(value['a'],value['b']);self.assertIs(shared[0],value)

    def test_64_unsupported_mutable_matrix(self):
        class Slotted:
            __slots__=('hidden',)
            def __init__(self):self.hidden=[]
        class ListSubclass(list):pass
        for value in (set(),bytearray(b'a'),Slotted(),UserDict(),MappingProxyType({}),ListSubclass([1]),lambda:None):
            with self.subTest(type=type(value).__name__),self.assertRaises(UnsupportedConfig):ConfigSnapshot([value])

    def test_65_unsupported_before_transition(self):
        model=Model();model.config.optional=set();before=state(model)
        with self.assertRaises(UnsupportedConfig):
            with runtime.evaluation_state(model,TorchFacade()):self.fail('Unsupported entered')
        self.assertEqual(state(model),before);self.assertEqual(model.calls,[])
        EFFECTS['unsupported_before_transition']=dict(state_unchanged=True,generation_calls=0)

    def test_66_setup_exception_restores_partial_mutations(self):
        model=Model();model.child.generation_config=None;original=model.config;before=state(model)
        def broken_eval():
            model.training=False;model.child.training=True;model.config.use_cache=True
            model.generation_config=None;model.config=SimpleNamespace(use_cache=True)
            raise RuntimeError('setup injected')
        model.eval=broken_eval
        with self.assertRaisesRegex(RuntimeError,'setup injected'):
            with runtime.evaluation_state(model,TorchFacade()):pass
        self.assertEqual(state(model),before);self.assertIs(model.config,original);self.assertFalse(original.use_cache)
        EFFECTS['setup_exception_restoration']=dict(restored=True)

    def test_67_generation_exception_with_null_config(self):
        model=Model();model.child.generation_config=None;before=state(model)
        model.failure=RuntimeError('generation injected')
        case=legacy.RuntimeChecks();case.setUpClass()
        with self.assertRaisesRegex(RuntimeError,'generation injected'):
            case.invoke(model=model)
        self.assertEqual(state(model),before)
        self.assertEqual(len(model.calls),1)
        EFFECTS['generation_exception_restoration']=dict(restored=True,lifecycle_standin=True,standin_generate_calls=1)

    def test_68_early_termination_null_config(self):
        model=Model();model.generation_config=None;before=state(model)
        with self.assertRaises(KeyboardInterrupt):
            with runtime.evaluation_state(model,TorchFacade()):raise KeyboardInterrupt()
        self.assertEqual(state(model),before)
        EFFECTS['early_termination_restoration']=dict(restored=True)

    def test_69_nested_context_mixed_flags(self):
        model=Model();model.child.generation_config=None;before=state(model)
        with runtime.evaluation_state(model,TorchFacade()):
            outer=state(model)
            with runtime.evaluation_state(model,TorchFacade()):self.assertFalse(model.child.training)
            self.assertEqual(state(model),outer);self.assertTrue(model.config.use_cache)
        self.assertEqual(state(model),before)
        EFFECTS['nested_mixed_flags']=dict(restored=True)

    def test_70_initial_eval_restored(self):
        model=Model();model.eval();before=state(model)
        with runtime.evaluation_state(model,TorchFacade()):pass
        self.assertEqual(state(model),before)

    def test_71_checkpoint_function_and_flag_restored(self):
        model=Model();prior=model._gradient_checkpointing_func
        with runtime.evaluation_state(model,TorchFacade()):
            model._gradient_checkpointing_func=object();model.gradient_checkpointing=False
            model.child._gradient_checkpointing_func=object()
        self.assertIs(model._gradient_checkpointing_func,prior);self.assertTrue(model.gradient_checkpointing)
        self.assertNotIn('_gradient_checkpointing_func',model.child.__dict__)

    def test_72_adapter_activation_and_grad_flags_restored(self):
        model=Model();active=model.active_adapters
        with runtime.evaluation_state(model,TorchFacade()):
            model.active_adapters.append('wrong');model.parameter.requires_grad=False
        self.assertIs(model.active_adapters,active);self.assertEqual(active,['default']);self.assertTrue(model.parameter.requires_grad)

    def test_73_parameter_version_change_fails_closed(self):
        model=Model();before=state(model)
        with self.assertRaisesRegex(ValueError,'Parameter state/version changed'):
            with runtime.evaluation_state(model,TorchFacade()):model.parameter._version+=1
        self.assertEqual([x.training for x in model.modules()],before['training'])

    def test_74_parameter_identity_change_fails_closed(self):
        model=Model()
        with self.assertRaisesRegex(ValueError,'Parameter state/version changed'):
            with runtime.evaluation_state(model,TorchFacade()):model.parameter=legacy.Parameter()

    def test_75_required_preflight_blocks_generation(self):
        model=Model();case=legacy.RuntimeChecks();case.setUpClass()
        with self.assertRaisesRegex(ValueError,'REAL_RUNTIME_CONTEXT_PREFLIGHT required'):
            runtime.evaluate_records(model,None,TorchFacade(),case.records[:1],case.protocol,legacy.Sink(),None)
        self.assertEqual(model.calls,[])
        EFFECTS['mandatory_context_preflight']=dict(missing_preflight_denied=True,generation_calls=0)

    def test_76_preflight_null_inventory_zero_generation(self):
        model=Model();model.child.generation_config=None;before=state(model)
        result=runtime.real_runtime_context_preflight(model,TorchFacade())
        self.assertTrue(result['passed']);self.assertEqual(result['generation_calls'],0)
        self.assertTrue(any(x['attribute']=='generation_config' and x['is_none'] for x in result['owned_config_fields']))
        self.assertEqual(state(model),before);self.assertEqual(model.calls,[])

    def test_77_failed_preflight_cannot_generate_or_retry(self):
        model=Model();model.config.optional=set()
        with self.assertRaises(UnsupportedConfig):runtime.real_runtime_context_preflight(model,TorchFacade())
        del model.config.optional
        with self.assertRaisesRegex(ValueError,'No repeated'):runtime.real_runtime_context_preflight(model,TorchFacade())
        with self.assertRaises(ValueError):runtime.require_context_preflight(model)
        EFFECTS['failed_preflight_no_retry']=dict(generation_denied=True,retry_denied=True)

    def test_78_cache_admission_requires_context(self):
        case=legacy.RuntimeChecks();case.setUpClass();session=case.session();session.context_model=None
        with self.assertRaisesRegex(ValueError,'Context preflight required'):session.admit_cache(case.cache_observations())

    def test_79_preflight_not_transferable_to_another_model(self):
        model=Model();runtime.real_runtime_context_preflight(model,TorchFacade())
        with self.assertRaises(ValueError):runtime.require_context_preflight(Model())

    def test_80_frozen_semantics_exact(self):
        before=json.loads((OLD/'protocol.json').read_text());after=json.loads((HERE/'protocol.json').read_text())
        for key in ('name','runtime_parent_sha256','real_runtime_context_preflight'):after.pop(key,None);before.pop(key,None)
        self.assertEqual(before,after)

    def test_81_guarded_fresh_prompt_token_identity(self):
        _,records=legacy.prepare.tokenize()
        self.assertEqual(records,json.loads((OLD/'prepared_dev.json').read_text()))

    def test_82_metadata_only_weight_preservation(self):
        for name,expected in json.loads((HERE/'excluded_binary_metadata.json').read_text()).items():
            actual=(ROOT/name).stat()
            self.assertEqual((actual.st_size,actual.st_mtime_ns),(expected['size'],expected['mtime_ns']))

    def test_83_pinned_real_config_objects_without_weights(self):
        os.environ['USE_TORCH']='0'
        from transformers import Qwen2Config,GenerationConfig
        config=Qwen2Config.from_dict(json.loads((legacy.audit.frozen.old.cached('producer')/'config.json').read_text()))
        gen=GenerationConfig.from_model_config(config)
        model=Model();model.config=config;model.generation_config=gen;model.child.config=config;model.child.generation_config=None
        snapshot=ConfigSnapshot([config,gen]);receipt=runtime.real_runtime_context_preflight(model,TorchFacade())
        self.assertTrue(receipt['passed']);snapshot.verify();self.assertIs(model.child.config,config)

    def test_84_pinned_nullability_ast_effect(self):
        path=Path(legacy.importlib.metadata.distribution('transformers').locate_file('transformers/modeling_utils.py'))
        tree=ast.parse(path.read_text(encoding='utf8'))
        assignment=next(x for x in ast.walk(tree) if isinstance(x,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='generation_config' for t in x.targets) and isinstance(x.value,ast.IfExp))
        obj=SimpleNamespace(can_generate=lambda:False)
        namespace=dict(self=obj,config=object(),GenerationConfig=SimpleNamespace(from_model_config=lambda x:'generation_config'))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[assignment],type_ignores=[])),'<pinned-config-assignment>','exec'),namespace)
        self.assertIsNone(obj.generation_config)
        EFFECTS['pinned_nullability_assignment']=dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),line=assignment.lineno,result=None)

    def test_85_historical_no_training_optimizer_guards(self):
        tree=ast.parse((ROOT/'tools/checkpoint120_remote.py').read_text())
        execute=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='execute')
        guard=next(x for x in execute.body if isinstance(x,ast.FunctionDef) and x.name=='no_training')
        assignments=[x for x in execute.body if isinstance(x,ast.Assign) and isinstance(x.value,ast.Name) and x.value.id=='no_training']
        self.assertEqual(len(assignments),3)
        class Optimizer:pass
        class Tensor:pass
        fake=SimpleNamespace(optim=SimpleNamespace(Optimizer=Optimizer),Tensor=Tensor,autograd=SimpleNamespace())
        namespace=dict(torch=fake)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[guard,*assignments],type_ignores=[])),'<frozen-training-denials>','exec'),namespace)
        for call in (Optimizer,lambda:Tensor().backward(),fake.autograd.backward):
            with self.assertRaises(PermissionError):call()
        EFFECTS['no_training_optimizer_guards']=dict(denied_calls=3,torch_imported=False)

    def test_86_mapping_config_context_restores(self):
        model=Model();model.config={'use_cache':False,'nullable':None};model.generation_config={};prior=model.config
        with runtime.evaluation_state(model,TorchFacade()):self.assertTrue(model.config['use_cache'])
        self.assertIs(model.config,prior);self.assertFalse(model.config['use_cache'])

    def test_87_added_owned_config_removed(self):
        model=Model();self.assertNotIn('config',model.child.__dict__)
        with runtime.evaluation_state(model,TorchFacade()):model.child.config=SimpleNamespace(use_cache=True)
        self.assertNotIn('config',model.child.__dict__)

    def test_88_gradient_buffer_identity_restored(self):
        model=Model();gradient=SimpleNamespace(_version=0);model.parameter.grad=gradient
        with runtime.evaluation_state(model,TorchFacade()):model.parameter.grad=None
        self.assertIs(model.parameter.grad,gradient)

    def test_89_old_authorization_rejected(self):
        case=legacy.RuntimeChecks();case.setUpClass()
        permit=dict(operator_authorized=True,experiment='second-tuning-eval-runtime-v2',action='producer-checkpoint120-evaluation-only',role='producer',split='canonical',checkpoint=120,runtime_release_sha256='new',protocol_sha256=runtime.digest(case.protocol),adapter_sha256=case.protocol['adapter']['files']['adapter_model.safetensors'])
        with self.assertRaisesRegex(ValueError,'Authorization mismatch: experiment'):runtime.authorize(permit,case.protocol,'new')

    def test_90_unsupported_nested_form_restores_nothing_because_no_transition(self):
        model=Model();model.generation_config.optional={'bad':UserDict()};before=state(model)
        with self.assertRaises(UnsupportedConfig):
            with runtime.evaluation_state(model,TorchFacade()):pass
        self.assertEqual(state(model),before)

    def test_91_remote_preflight_failure_evidence_then_teardown(self):
        import remote_preflight
        case=legacy.RuntimeChecks();case.setUpClass();session=case.session()
        session.context_attempted=False;session.context_model=None
        model=Model();model.child.generation_config=set();events=[]
        with self.assertRaises(UnsupportedConfig):
            remote_preflight.run(session,model,TorchFacade(),lambda receipt:events.append(receipt),lambda:events.append('collect_and_terminate'))
        self.assertEqual(events[0]['decision'],'NO_GO');self.assertEqual(events[1],'collect_and_terminate')
        self.assertEqual(model.calls,[])
        EFFECTS['remote_preflight_no_go_handoff']=dict(evidence_before_teardown=True,generation_calls=0,callbacks_only=True)

    def test_92_remote_preflight_persistence_failure_still_terminates(self):
        import remote_preflight
        case=legacy.RuntimeChecks();case.setUpClass();session=case.session()
        session.context_attempted=False;session.context_model=None
        events=[]
        def fail(receipt):raise OSError('persistence failed')
        with self.assertRaises(OSError):remote_preflight.run(session,Model(),TorchFacade(),fail,lambda:events.append('terminate'))
        self.assertEqual(events,['terminate'])

if __name__=='__main__':
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(legacy.RuntimeChecks),unittest.defaultTestLoader.loadTestsFromTestCase(NullabilityChecks)])
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    summary=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful(),
        effect_proof_count=len(EFFECTS),effect_proofs=EFFECTS,real_model_generations=0,model_weight_reads=0,
        cloud_calls=0,torch_imported='torch' in sys.modules,limitation='Lifecycle uses explicit stand-ins; real pinned Qwen2Config/GenerationConfig objects and source AST only, no CUDA/model validation. Adapter bytes not reopened; preserved hash/tensor-verification evidence and file metadata bound.')
    (HERE/'test_results.json').write_text(json.dumps(summary,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
