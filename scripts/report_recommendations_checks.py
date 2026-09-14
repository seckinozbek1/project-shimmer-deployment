"""Bounded mechanism fixtures. No pipeline execution or model loading."""
import asyncio
import ast
from types import SimpleNamespace
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import bounded_extraction as ex
import generation_observation as observation
import semantic_waves as waves
import execution_topology as topology
from execution_scheduler import Lane
from agent_wrapper import AgentWrapper, CallResult, current_items
from constitution import Constitution
from message_bus import MessageBus
from run_context import for_run_dir

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "Preamble retained.\n\n## Alpha\nA source statement.\n\n## Beta\nAnother statement.\n"


def wire(spans, doc_id="fixture"):
    return dict(agent="PROCESSOR", doc_id=doc_id, items=[
        dict(section_id=ex.wire_id(s),draft_text=ex.wire_id(s),extraction_method="source_span",
             claims_referenced=[],open_questions=[],ref="document-level",kind="extraction",
             confidence="UNCERTAIN",ref_ids=[]) for s in spans])


class RecommendationChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ctx = for_run_dir(ROOT,Path(self.temp.name))
        self.bus = MessageBus.open(Path(self.temp.name)/"bus.jsonl")
        self.c = Constitution.load(ROOT/"config/constitution.json")
        self.contracts = json.loads((ROOT/"config/agent_contracts.json").read_text())["contracts"]

    def wrapper(self, name="PROCESSOR"):
        return AgentWrapper(name,self.c,self.bus,
                            {name:dict(backend="local_auditor" if name in {"VERIFIER","FACT_CHECKER"} else "local_producer",
                                       model="fixture_a" if name in {"VERIFIER","FACT_CHECKER"} else "fixture_p")},
                            self.contracts,keys={"fixture":True},run_context=self.ctx)

    def runtime(self,n=2):
        r=topology.Runtime([Lane("fixture_%d"%i) for i in range(n)])
        r.optimized=True
        self.addCleanup(r.close)
        return r

    def test_ledger_covers_preamble_tables_and_unicode(self):
        for text in [SOURCE,"Before\n| X | Y |\n|---|---|\n| a | b |\nAfter\n", "İlk metin\nSon"]:
            spans=ex.ledger(text,"fixture",max_chars=9)
            self.assertTrue(spans)
            self.assertEqual("".join(s.text for s in spans),text)
            self.assertEqual([(s.start,s.end) for s in spans],[(0,spans[0].end)]+[(spans[i-1].end,s.end) for i,s in enumerate(spans) if i])
            self.assertEqual(spans,ex.ledger(text,"fixture",max_chars=9))

    def test_hydrate_requires_complete_coverage_and_correct_identity(self):
        spans=ex.ledger(SOURCE,"fixture")
        value=wire(spans)
        restored=ex.hydrate(value,spans,"fixture")
        self.assertEqual("".join(i["draft_text"] for i in restored["items"]),SOURCE)
        self.assertEqual(len(current_items(restored["items"])),len(spans))
        for bad in [dict(value,items=value["items"][:-1]),dict(value,doc_id="wrong"),dict(value,items=[])]:
            with self.assertRaises(ValueError): ex.hydrate(bad,spans,"fixture")

    def test_deduplicate_exact_but_refuse_conflicting_or_context_items(self):
        spans=ex.ledger(SOURCE,"fixture"); value=wire(spans)
        duplicate=copy.deepcopy(value);duplicate["items"].append(copy.deepcopy(value["items"][0]))
        self.assertEqual(len(ex.hydrate(duplicate,spans,"fixture")["items"]),len(spans))
        duplicate["items"][-1]["confidence"]="CONFIDENT"
        with self.assertRaises(ValueError):ex.hydrate(duplicate,spans,"fixture")
        with self.assertRaises(ValueError):ex.hydrate(value,spans[1:],"fixture")

    def test_merge_order_and_incomplete_not_success(self):
        spans=ex.ledger(SOURCE,"fixture"); parts=ex.partitions(spans,1)
        rows=[dict(ok=True,truncated=False,parsed=ex.hydrate(wire(p),p,"fixture")) for p in parts]
        merged=ex.merge(list(reversed(rows)),"fixture")
        self.assertTrue(merged["ok"])
        self.assertEqual("".join(i["draft_text"] for i in merged["parsed"]["items"]),SOURCE)
        rows[0]["truncated"]=True
        self.assertFalse(ex.merge(rows,"fixture")["ok"])

    def test_eos_at_cap_is_complete_unknown_is_unknown(self):
        self.assertEqual(observation.local_stop(9,[8,9],128,128),("eos",False))
        self.assertEqual(observation.local_stop(7,[9],128,128),("length",True))
        self.assertEqual(observation.local_stop(7,None,10,128),("unknown",None))

    def test_wave_overlaps_freezes_context_and_posts_in_order(self):
        runtime=self.runtime(); barrier=threading.Barrier(2); seen=[]
        wrappers=[runtime.attach(self.wrapper(n)) for n in ["VERIFIER","FACT_CHECKER"]]
        def response(w):
            def call(**kwargs):
                seen.append(len(w.bus.read_all()));barrier.wait(timeout=2)
                if w.name=="VERIFIER":time.sleep(.025)
                w.post_to_bus(recipient="ORCHESTRATOR",channel="main",msg_type="INFORM",
                              body={"agent":w.name},constitution_check={"result":"RESOLVED"})
                return {"ok":w.name=="VERIFIER"}
            return call
        for w in wrappers:w._reference_run_task=response(w)
        result=waves.run_wave(runtime,[(w,{}) for w in wrappers],"same_source")
        self.assertEqual(seen,[0,0]);self.assertEqual([r["ok"] for r in result],[True,False])
        self.assertEqual([m["sender"] for m in self.bus.read_all()],["VERIFIER","FACT_CHECKER"])
        self.assertEqual(len(runtime.frontier),2)
        self.assertEqual(runtime.scheduler.summary()["task_count"],2)
        self.assertEqual(runtime.scheduler.outcomes["task-000001"].state,"refused")

    def test_live_wrapper_keeps_contract_valid_separate_from_complete(self):
        w=self.wrapper();w._optimized_semantics=True
        w.dispatch=lambda *a,**k: self.fake_result(w,dict(agent="PROCESSOR",doc_id="fixture",items=[]),True)
        r=w.run_task(work_payload={"document_id":"fixture"})
        self.assertFalse(r["ok"])
        rows=[json.loads(x) for x in (self.ctx.logs_dir()/"generation_observation.jsonl").read_text().splitlines()]
        self.assertTrue(rows[-1]["backend_success"])
        self.assertTrue(rows[-1]["contract_valid"])
        self.assertFalse(rows[-1]["complete_response"])

    def fake_result(self,w,value,truncated=False):
        r=CallResult(w.backend,w.model,json.dumps(value),usage=dict(truncated=truncated,output_tokens=40,requested_max_output_tokens=80))
        w._record_cost(r)
        return r

    def test_processor_live_adapter_merges_and_retries_only_failed_partition(self):
        tree=ast.parse((ROOT/"scripts/pipeline.py").read_text(encoding="utf-8"))
        fn=next(x for x in tree.body if isinstance(x,ast.AsyncFunctionDef) and x.name=="_run_one")
        namespace=dict(semantic_waves=waves,asyncio=asyncio,time=time,
                       _is_local_profile=lambda:False,_emit_progress=lambda **k:None)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),"live_run_one","exec"),namespace)
        pipeline=SimpleNamespace(_run_one=namespace["_run_one"])
        runtime=self.runtime(1); w=runtime.attach(self.wrapper()); counts=[]
        def dispatch(instance,stable,dynamic="",**kwargs):
            owned=instance._fixture_spans if hasattr(instance,"_fixture_spans") else None
            # Read only the explicitly bounded work payload sent by the live wrapper.
            raw=dynamic.split("## Work payload\n",1)[1]
            payload,_=json.JSONDecoder().raw_decode(raw)
            ids=[s["span_id"] for s in payload["source_spans"]]; counts.append(ids)
            items=[dict(section_id=x,draft_text=x,extraction_method="source_span",claims_referenced=[],
                        open_questions=[],ref="document-level",kind="extraction",confidence="UNCERTAIN") for x in ids]
            self.assertEqual(kwargs["max_new_tokens"],1536)
            return self.fake_result(instance,dict(agent="PROCESSOR",doc_id="fixture",items=items),len(counts)==1)
        state=topology.ACTIVE.set(runtime)
        try:
            with patch.object(AgentWrapper,"dispatch",dispatch):
                # Build after patch so the topology dispatch wrapper captures it.
                w=runtime.attach(self.wrapper())
                result=asyncio.run(self._one(pipeline,w,SOURCE*30))
        finally:topology.ACTIVE.reset(state)
        self.assertTrue(result["ok"])
        self.assertEqual("".join(i["draft_text"] for i in result["parsed"]["items"]),SOURCE*30)
        self.assertEqual(counts.count(counts[0]),2)
        self.assertTrue(all(counts.count(x)==1 for x in counts[1:-1]))

    async def _one(self,pipeline,w,text):
        return await pipeline._run_one(w,dict(document_id="fixture",document_text=text),"fixture")

    def test_exact_comparison_requires_typed_unconditional_proof(self):
        check=dict(relation="above_band",agrees=False,computed=13,computed_unit="m",
                   band_low=2,band_high=11,basis="declared comparison",ref_id="REF-1234")
        plan=dict(kind="band",checks=[check])
        self.assertTrue(waves.exact_comparison_plan(plan))
        for changes in [dict(conditional_on=["declared condition"]),dict(ref_id=""),dict(computed=float("nan")),dict(relation="missing_field")]:
            self.assertFalse(waves.exact_comparison_plan(dict(plan,checks=[dict(check,**changes)])))

    def test_exact_comparison_live_branch_emits_record_without_dispatch(self):
        import paired_review
        tree=ast.parse((ROOT/"scripts/pipeline.py").read_text(encoding="utf-8"))
        branch=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and
                    ast.unparse(n.test)=="semantic_waves.enabled() and semantic_waves.exact_comparison_plan(plan)")
        # Execute the actual optimized branch inside its enclosing loop shape.
        tree=ast.Module(body=[ast.For(target=ast.Name(id="once",ctx=ast.Store()),
                                     iter=ast.List(elts=[ast.Constant(1)],ctx=ast.Load()),body=[branch],orelse=[])],type_ignores=[])
        check=dict(relation="above_band",agrees=False,computed=13,computed_unit="m",band_low=2,band_high=11,
                   basis="declared comparison",ref_id="REF-1234")
        records={}; events=[]
        scope=dict(semantic_waves=waves,paired_review_mod=paired_review,plan=dict(kind="band",checks=[check]),
                   checks=[check],unit={"unit_id":"u01-fixture"},rule={"id":"CONV-1234"},agent="PRACTICE_AUDITOR",
                   computed_items_by_agent=records,source_rule_id="fixture-rule",refs=["REF-1234"],
                   agent_activation=SimpleNamespace(not_called=lambda *a,**k:events.append(k)),
                   orch=SimpleNamespace(run_context=self.ctx),doc={"id":"fixture"},plan_index=0)
        with patch.object(waves,"enabled",return_value=True):exec(compile(ast.fix_missing_locations(tree),"live_exact_branch","exec"),scope)
        self.assertEqual(len(events),1)
        item=records["PRACTICE_AUDITOR"][0]
        self.assertEqual((item["value_a"],item["value_b"],item["rule_id"],item["source_refs"]),(13,11,"CONV-1234",["REF-1234"]))
        self.assertIn("13",item["explanation"])

    def test_incomplete_extraction_prevents_completed_status(self):
        from run_completion import RunCompletion
        c=RunCompletion(self.ctx);c.reached_end(document_count=1,amendment_count=0)
        observation.mark_incomplete(self.ctx);c.finish(0)
        self.assertEqual(c.record["state"],"stopped")
        self.assertFalse(c.record["semantic_complete"])

    def test_projection_critical_path_capacity_and_missing_measurements(self):
        from run_projection import project,schedule,costs
        nodes=[dict(id="p",parents=[],seconds=dict(low=2,high=3)),
               dict(id="a",parents=["p"],seconds=dict(low=4,high=5)),
               dict(id="b",parents=["p"],seconds=dict(low=4,high=5))]
        self.assertEqual(schedule(nodes,1),10)
        self.assertEqual(schedule(nodes,2),6)
        self.assertEqual(project(dict(nodes=nodes))["target_assessment"],"LOCAL_TARGET_INDETERMINATE")
        with self.assertRaises(ValueError):schedule([dict(id="x",parents=["x"],seconds={"low":1})],1)
        self.assertAlmostEqual(costs(rate=1.99,active_seconds=120)["marginal_cost_per_accepted_run"],1.99/30)

    def test_effect_proof_rejects_lost_source_text(self):
        from effect_proof import prove_effect
        spans=ex.ledger(SOURCE,"fixture");valid=wire(spans)
        def observe():return [x["draft_text"] for x in ex.hydrate(valid,spans,"fixture")["items"]]
        def check():return ("PASS" if "".join(observe())==SOURCE else "FAIL","")
        mutated=lambda obj,owned,doc:obj
        proof=prove_effect(name="source_reconstruction",validate=lambda:len(valid["items"])==len(spans),
                           observe=observe,check=check,neutralise=lambda:patch.object(ex,"hydrate",mutated))
        self.assertEqual(proof["status"],"PASS")

    def test_effect_proof_eos_boundary(self):
        from effect_proof import prove_effect
        def observe():return observation.local_stop(9,[9],128,128)[1]
        proof=prove_effect(name="eos_at_cap",validate=lambda:True,observe=observe,
                           check=lambda:("PASS" if observe() is False else "FAIL",""),
                           neutralise=lambda:patch.object(observation,"local_stop",lambda *a:("length",True)))
        self.assertEqual(proof["status"],"PASS")

    def test_deterministic_reuse_invalidates_on_source_identity_or_budget(self):
        first=ex.ledger(SOURCE,"fixture")
        self.assertIs(first,ex.ledger(SOURCE,"fixture"))
        self.assertNotEqual(first,ex.ledger(SOURCE+"changed","fixture"))
        self.assertNotEqual(first,ex.ledger(SOURCE,"another_document"))
        self.assertNotEqual(first,ex.ledger(SOURCE,"fixture",max_chars=10))

    def test_family_separation_reads_model_configuration(self):
        root=Path(self.temp.name)
        for name,family in [("producer","family_p"),("auditor","family_a")]:
            (root/name).mkdir();(root/name/"config.json").write_text(json.dumps({"model_type":family}))
        profile={"P":("local_producer","producer"),"A":("local_auditor","auditor")}
        self.assertEqual(waves.validate_model_families(profile,lambda m:root/m)["local_auditor"],["family_a"])
        (root/"auditor/config.json").write_text(json.dumps({"model_type":"family_p"}))
        with self.assertRaises(ValueError):waves.validate_model_families(profile,lambda m:root/m)

    def test_native_template_and_eos_telemetry_on_local_call(self):
        import agent_wrapper
        from contextlib import nullcontext
        calls=[]
        class Inputs(dict):
            def to(self,device):return self
        class Tokenizer:
            chat_template="configured"
            def apply_chat_template(self,messages,**kw):
                calls.append(("template",messages,kw));return "TEMPLATED"
            def __call__(self,prompt,**kw):
                calls.append(("tokenize",prompt,kw));return Inputs(input_ids=SimpleNamespace(shape=(1,2)))
            def decode(self,ids,**kw):return "{}"
        class Output:
            shape=(1,4)
            def __getitem__(self,key):return [1,2,3,9]
        model=SimpleNamespace(device="cpu",generation_config=SimpleNamespace(eos_token_id=[9]),generate=lambda **kw:Output())
        torch=SimpleNamespace(no_grad=nullcontext,cuda=SimpleNamespace(is_available=lambda:False))
        w=self.wrapper();w._optimized_semantics=True
        with patch.object(agent_wrapper,"_load_qwen",return_value=(Tokenizer(),model)),patch.object(agent_wrapper.importlib,"import_module",side_effect=lambda n:torch if n=="torch" else object()):
            result=w.call_local("source",max_new_tokens=2)
        self.assertTrue(result.ok);self.assertFalse(result.usage["truncated"])
        self.assertEqual(result.usage["finish_reason"],"eos")
        self.assertTrue(result.usage["cap_hit"])
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[1][1],"TEMPLATED")
        self.assertFalse(calls[1][2]["add_special_tokens"])


if __name__=="__main__":unittest.main()
