"""Neutralise each new mechanism check, require assertion failure, then restore."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"scripts"))
import report_recommendations_checks as checks
import bounded_extraction as ex
import semantic_waves as waves
import generation_observation as obs
import run_projection as projection
from agent_wrapper import AgentWrapper


def run(name):
    result=unittest.TestResult()
    checks.RecommendationChecks(name).run(result)
    return dict(failures=len(result.failures),errors=len(result.errors))


def main():
    original_ledger,original_hydrate,original_merge=ex.ledger,ex.hydrate,ex.merge
    original_task,original_local=AgentWrapper.run_task,AgentWrapper.call_local
    def no_hydrate(obj,*args):return obj
    def permit_bad(obj,*args):
        try:return original_hydrate(obj,*args)
        except ValueError:return obj
    def unordered(*args):
        r=original_merge(*args);r["parsed"]["items"].reverse();return r
    def lost(*args):
        r=original_merge(*args);r["parsed"]["items"]=[];return r
    def reference_task(w,*a,**k):
        w._optimized_semantics=False
        return original_task(w,*a,**k)
    def raw_local(w,*a,**k):
        w._optimized_semantics=False
        return original_local(w,*a,**k)
    mutations={
        "test_ledger_covers_preamble_tables_and_unicode":(ex,"ledger",lambda *a,**k:tuple(reversed(original_ledger(*a,**k)))),
        "test_hydrate_requires_complete_coverage_and_correct_identity":(ex,"hydrate",no_hydrate),
        "test_deduplicate_exact_but_refuse_conflicting_or_context_items":(ex,"hydrate",permit_bad),
        "test_merge_order_and_incomplete_not_success":(ex,"merge",unordered),
        "test_eos_at_cap_is_complete_unknown_is_unknown":(obs,"local_stop",lambda *a:("length",True)),
        "test_wave_overlaps_freezes_context_and_posts_in_order":(waves.WaveBus,"post",lambda self,m:self.live.post(m)),
        "test_live_wrapper_keeps_contract_valid_separate_from_complete":(AgentWrapper,"run_task",reference_task),
        "test_processor_live_adapter_merges_and_retries_only_failed_partition":(ex,"merge",lost),
        "test_exact_comparison_requires_typed_unconditional_proof":(waves,"exact_comparison_plan",lambda p:True),
        "test_exact_comparison_live_branch_emits_record_without_dispatch":(waves,"exact_comparison_plan",lambda p:False),
        "test_incomplete_extraction_prevents_completed_status":(obs,"mark_incomplete",lambda c:None),
        "test_projection_critical_path_capacity_and_missing_measurements":(projection,"schedule",lambda *a,**k:99),
        "test_deterministic_reuse_invalidates_on_source_identity_or_budget":(ex,"ledger",original_ledger.__wrapped__),
        "test_family_separation_reads_model_configuration":(waves,"validate_model_families",lambda *a:{"local_auditor":["family_a"]}),
        "test_native_template_and_eos_telemetry_on_local_call":(AgentWrapper,"call_local",raw_local),
    }
    rows=[]
    for name,(owner,attribute,mutant) in mutations.items():
        before=run(name);invocations=[]
        def replacement(*a,**k):
            invocations.append(1)
            return mutant(*a,**k)
        with patch.object(owner,attribute,replacement):during=run(name)
        after=run(name)
        passed=(before==after==dict(failures=0,errors=0) and during==dict(failures=1,errors=0) and bool(invocations))
        rows.append(dict(check=name,status="PASS" if passed else "FAIL",baseline=before,
                         neutralized=during,restored=after,mutated_branch_invocations=len(invocations)))
    path=ROOT/"docs/fix/report_recommendations/mutations.json"
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(rows,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"passed":sum(r["status"]=="PASS" for r in rows),"total":len(rows),
                      "failed_checks":[r["check"] for r in rows if r["status"]!="PASS"]}))
    return 0 if all(r["status"]=="PASS" for r in rows) else 1


if __name__=="__main__":sys.exit(main())
