"""Small offline source/contract/concurrency probe, never a pipeline runner.

Synthetic dispatch latency measures scheduler behavior only. Tokenizer inspection
uses already cached assets without Transformers, weights, downloads or network.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import statistics
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"scripts"))
import bounded_extraction as ex
from report_recommendations_checks import wire


def resources():
    out={"gpu_utilization_percent":None,"vram_used_mib":None,"cpu_percent":None,"ram_used_gib":None}
    try:
        import psutil
        out.update(cpu_percent=psutil.cpu_percent(),ram_used_gib=psutil.virtual_memory().used/2**30,
                   available_ram_gib=psutil.virtual_memory().available/2**30,
                   process_rss_mib=psutil.Process().memory_info().rss/2**20)
    except ImportError:pass
    try:
        p=subprocess.run(["nvidia-smi","--query-gpu=utilization.gpu,memory.used","--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=3)
        if p.returncode==0:
            util,mem=p.stdout.strip().splitlines()[0].split(",")
            out.update(gpu_utilization_percent=float(util),vram_used_mib=float(mem))
    except (OSError,ValueError,subprocess.TimeoutExpired):pass
    return out


def concurrency_probe(call, capacities=(1,2,4), count=4):
    """Injected bounded backend boundary; measure one family, at most four calls.

Real-serving adapters must supply independent request handling with one model
owner. Never invoke the old shared Transformers model concurrently through this.
"""
    if count<1 or count>4 or any(n not in (1,2,4) for n in capacities):
        raise ValueError("Probe exceeds short-burst admission")
    runs=[]
    for capacity in capacities:
        before=resources();started=time.perf_counter()
        def measured(i):
            t=time.perf_counter();r=call(i)
            return dict(latency_seconds=time.perf_counter()-t,**r)
        with ThreadPoolExecutor(max_workers=capacity) as pool:rows=list(pool.map(measured,range(count)))
        elapsed=time.perf_counter()-started;after=resources()
        runs.append(dict(concurrency=capacity,wall_seconds=elapsed,calls=rows,
                         calls_per_second=count/elapsed,resource_before=before,resource_after=after,
                         model_load_events=0,resource_sampling="boundary_samples_not_peak_guarantee"))
        if any(not r.get("ok") or r.get("truncated") is not False for r in rows):
            runs[-1]["stopped_reason"]="validity_or_completeness_regressed";break
        if len(runs)>1 and elapsed>=runs[-2]["wall_seconds"]:
            runs[-1]["stopped_reason"]="aggregate_latency_did_not_improve";break
        if len(runs)>1:
            previous=runs[-2]["calls"]
            if [r.get("quality_signature") for r in rows]!=[r.get("quality_signature") for r in previous] or [r.get("accepted_items") for r in rows]!=[r.get("accepted_items") for r in previous]:
                runs[-1]["stopped_reason"]="accepted_output_changed";break
            if statistics.median(r["latency_seconds"] for r in rows)>1.25*statistics.median(r["latency_seconds"] for r in previous):
                runs[-1]["stopped_reason"]="per_call_latency_regressed";break
        if any(r.get("quality_signature") is None for r in rows):
            runs[-1]["stopped_reason"]="quality_equivalence_signature_unavailable";break
        if after.get("available_ram_gib",99)<3:
            runs[-1]["stopped_reason"]="low_available_ram";break
    return runs


def tokenizer_measurement(mono,compact):
    try:
        from tokenizers import Tokenizer
    except ImportError:return {"status":"unavailable","reason":"tokenizers_not_installed"}
    cfg=json.loads((ROOT/"config/local_models.json").read_text())
    cache=Path(os.environ.get("HF_HUB_CACHE",str(Path.home()/".cache/huggingface/hub")))
    model=cache/("models--"+cfg["active_producer"].replace("/","--"))
    snapshots=sorted((model/"snapshots").glob("*/tokenizer.json"))
    if len(snapshots)!=1:return {"status":"unavailable","reason":"cached_snapshot_missing_or_ambiguous"}
    tokenizer=Tokenizer.from_file(str(snapshots[0]))
    counts={k:len(tokenizer.encode(json.dumps(v,ensure_ascii=False,separators=(",",":")),add_special_tokens=False).ids)
            for k,v in [("monolithic_output_tokens",mono),("compact_output_tokens",compact)]}
    return dict(status="measured_tokenization_only",model=cfg["active_producer"],**counts)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    # Authored source only, independent of benchmark answer keys and operator data.
    source="\n\n".join("## Section %d\n"%i+("A source sentence with its original wording. "*12) for i in range(4))
    started=time.perf_counter();spans=ex.ledger(source,"probe");parts=ex.partitions(spans)
    compact=wire(spans,"probe")
    monolithic=dict(compact,items=[dict(item,draft_text=span.text) for item,span in zip(compact["items"],spans)])
    restored="".join(i["draft_text"] for i in ex.hydrate(compact,spans,"probe")["items"])
    cpu=time.perf_counter()-started
    def synthetic(i):
        time.sleep(.03)
        return dict(ok=True,contract_valid=True,truncated=False,accepted_items=1,
                    generation_seconds=None,measurement_kind="synthetic_dispatch",quality_signature="authored_fixture")
    result=dict(classification="SHORT_BURST_FIXTURE_NOT_MODEL_BENCHMARK",
                directly_measured=dict(source_chars=len(source),source_spans=len(spans),partitions=len(parts),
                                       ledger_merge_seconds=cpu,source_reconstructed_exactly=restored==source,
                                       output_item_count=len(monolithic["items"])),
                tokenization=tokenizer_measurement(monolithic,compact),
                concurrency=concurrency_probe(synthetic),
                assumptions=["Synthetic 30 ms service calls demonstrate scheduling only."],
                remaining_uncertainty=["Real model latency, TTFT, semantic completeness and quality",
                                       "GPU concurrency capacity and resident model resource peaks"],
                projected_full_run_effect=None)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(a.output),"source_integrity":restored==source,"tokenization":result["tokenization"]}))


if __name__=="__main__":main()
