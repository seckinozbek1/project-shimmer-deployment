"""Check 445 (speed plan v1, docs/loop/stages/SPEED_PLAN_V1.md): tools/launch_time_split.py attributes a
launch's billed seconds to its parts from the saved records alone, and prints no identifier.

On an invented session folder (two batch entries, a detached phase's start sub-step, a gap between phases,
a termination wait) each rule is proven: a start or collect sub-step is not counted twice; every billed
second lands in exactly one category, with nothing left over; a workload is split into time outside the
pipeline, model loads, generation and the rest; per agent the calls, generation and prefill seconds,
tokens, cap hits, retries, prompt characters and the bytes after a reply's closed object are summed (a
brace inside a string does not close it); no folder name, instance id or reply text reaches the output;
and two splits on different machine types are never compared or summed (FACTORS-A).

Each is neutralise, fail, restore, pass (scripts/effect_proof.py). No model, no network, no real record:
the fixture is written to a temporary folder.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "tools"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import launch_time_split as lts  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

CANARIES = ("CANARY_INSTANCE_9", "secretdoc", "otherdoc", "CANARY_TEXT_7", "CANARY_CALL_3")


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, list):
        path.write_text("".join(json.dumps(v) + "\n" for v in value), encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")


def _timing(folder: Path, name: str, start, seconds):
    _write(folder / (name + "_timing.json"), {"start_epoch": start, "seconds": seconds, "returncode": 0})


def build_session(root: Path, machine="gpu_1x_a10"):
    """Launch at 1000; boot 100; setup 100 (plus a 3 s start sub-step inside it); two workloads of 300 and
    200; 30 between entries; 25 in the tail; a 5 s controller gap; 40 s to the verified termination."""
    s = root / ("session_" + machine)
    _write(s / "launch.json", {"epoch": 1000.0, "hourly_rate": 1.2, "instance_id": "CANARY_INSTANCE_9",
                               "instance_type": machine, "region": "us-east-1"})
    _write(s / "TERMINATION_VERIFIED.json", {"epoch": 1800.0, "billable_duration_upper_bound_seconds": 800.0})
    _timing(s, "ssh_ready_0", 1100.0, 2.0)
    _timing(s, "python_gate", 1102.0, 8.0)
    _timing(s, "python_gate_start", 1102.0, 3.0)
    _timing(s, "asset_copy_probe", 1110.0, 90.0)
    e0, e1 = s / "batch" / "00_secretdoc_B3", s / "batch" / "01_otherdoc_B3"
    _timing(e0, "batch_workload_0", 1200.0, 300.0)
    _timing(e0, "batch_workload_collect_0", 1490.0, 2.0)
    _timing(e0, "batch_pack_evidence_0", 1500.0, 10.0)
    _timing(e1, "batch_transfer_1", 1515.0, 20.0)
    _timing(e1, "batch_workload_1", 1535.0, 200.0)
    _timing(e1, "batch_pack_evidence_1", 1735.0, 10.0)
    _timing(s, "stop_workload", 1745.0, 5.0)
    _timing(s, "evidence_download", 1750.0, 10.0)
    _write(e0 / "analysis" / "model_telemetry_summary.json", {
        "pipeline_wall_seconds": 280.0, "generation_wall_union_seconds": 200.0, "scheduler_wait_seconds": 9.0,
        "maximum_concurrency": 1, "per_agent_service": {"AGENT_A": 150.0, "AGENT_B": 60.0},
        "phase_latencies": [{"phase": "phase_a", "seconds": 100.0}, {"phase": "phase_b", "seconds": 170.0}],
        "model_lifecycle": [
            {"event": "model_load_start", "model": "m1", "monotonic_s": 10.0},
            {"event": "model_load_end", "model": "m1", "monotonic_s": 20.0},
            {"event": "model_resident", "model": "m1", "monotonic_s": 50.0},
            {"event": "model_load_start", "model": "m2", "monotonic_s": 100.0},
            {"event": "model_evicted", "model": "m2", "evicted_model": "m1", "monotonic_s": 100.0},
            {"event": "model_load_end", "model": "m2", "monotonic_s": 108.0},
            {"event": "model_load_start", "model": "m1", "monotonic_s": 200.0},
            {"event": "model_load_end", "model": "m1", "monotonic_s": 210.0}]})
    logs = e0 / "downloaded" / "evidence" / "run" / "logs"
    _write(logs / "generation_observation.jsonl", [
        {"agent": "AGENT_A", "call_id": "CANARY_CALL_3", "generation_seconds": 100.0, "input_tokens": 1000,
         "output_tokens": 500, "cap_hit": True, "retry_count": 0},
        {"agent": "AGENT_A", "generation_seconds": 50.0, "input_tokens": 500, "output_tokens": 200,
         "cap_hit": False, "retry_count": 0},
        {"agent": "AGENT_B", "generation_seconds": 50.0, "input_tokens": 2000, "output_tokens": 100,
         "cap_hit": False, "retry_count": 1},
        {"event": "source_ledger", "document_id": "secretdoc"}])
    _write(logs / "prompt_structure.jsonl", [{"agent": "AGENT_A", "static_chars": 300, "dynamic_chars": 700,
                                              "note": "CANARY_TEXT_7"}])
    replies = e0 / "downloaded" / "evidence" / "run" / "audit" / "model_replies"
    _write(replies / "000001_x.json", {"agent": "AGENT_A", "prefill": {"prefill_seconds": 2.5},
                                       "reply": {"text": '{"a": "CANARY_TEXT_7"} xx'}})
    _write(replies / "000002_y.json", {"agent": "AGENT_B", "prefill": {"prefill_seconds": 1.0},
                                       "reply": {"text": '{"b": "}"}'}})
    # The second entry's summary sits only in its downloaded evidence (the fallback path).
    _write(e1 / "downloaded" / "evidence" / "run" / "audit" / "model_telemetry_summary.json", {
        "pipeline_wall_seconds": 190.0, "generation_wall_union_seconds": 150.0, "per_agent_service": {"AGENT_A": 150.0},
        "model_lifecycle": [{"event": "model_load_start", "model": "m1", "monotonic_s": 1.0},
                            {"event": "model_load_end", "model": "m1", "monotonic_s": 11.0}]})
    return s


EXPECTED_CATEGORIES = {"provider_boot": 100.0, "setup": 100.0, "between_entries": 30.0, "workload": 500.0,
                       "tail": 25.0, "controller_gaps": 5.0, "termination_wait": 40.0, "unattributed": 0.0}


class LaunchTimeSplitChecks(unittest.TestCase):
    evidence = []

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.a10 = build_session(root)
        cls.other = build_session(root, machine="gpu_1x_a100_sxm4")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def prove(self, name, observe, expected, neutralise):
        self.assertEqual(observe(), expected)
        LaunchTimeSplitChecks.evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))

    def test_01_sub_steps_not_counted_twice(self):
        observe = lambda: lts.split(self.a10)["setup_phases"]
        self.prove("start_and_collect_sub_steps_not_counted_twice", observe,
                   {"ssh_ready": 2.0, "python_gate": 8.0, "asset_copy_probe": 90.0},
                   lambda: patch.object(lts, "SUB_STEP_ENDINGS", ("_never",)))

    def test_02_every_billed_second_attributed(self):
        observe = lambda: {k: v["seconds"] for k, v in lts.split(self.a10)["categories"].items()}
        self.prove("every_billed_second_in_one_category", observe, EXPECTED_CATEGORIES,
                   lambda: patch.object(lts, "WORKLOAD_PHASES", ("ordinary_workload",)))

    def test_03_workload_split(self):
        def observe():
            entries = lts.split(self.a10)["entries"]
            return [(e["parts"], e["model_loads"]) for e in entries]
        want = [({"outside_pipeline": 20.0, "model_load": 28.0, "generation": 200.0, "pipeline_other": 52.0}, 3),
                ({"outside_pipeline": 10.0, "model_load": 10.0, "generation": 150.0, "pipeline_other": 30.0}, 1)]
        self.prove("workload_split_outside_loads_generation_rest", observe, want,
                   lambda: patch.object(lts, "model_loads", lambda lifecycle: (0.0, 0)))

    def test_04_agents_summed(self):
        def observe():
            agents = lts.split(self.a10)["agents"]
            keys = ("calls", "generation_seconds", "prefill_seconds", "input_tokens", "output_tokens", "cap_hits",
                    "retries", "static_chars", "dynamic_chars", "replies", "tail_bytes_after_close",
                    "service_seconds")
            return {name: [agents[name][k] for k in keys] for name in sorted(agents)}
        want = {"AGENT_A": [2, 150.0, 2.5, 1500, 700, 1, 0, 300, 700, 1, 2, 300.0],
                "AGENT_B": [1, 50.0, 1.0, 2000, 100, 0, 1, 0, 0, 1, 0, 60.0]}
        self.prove("agents_summed_and_closed_object_tail_counted", observe, want,
                   lambda: patch.object(lts, "tail_after_close", lambda text: len(text)))

    def test_05_no_identifier_in_output(self):
        def observe():
            result = lts.aggregate([lts.split(self.a10)])
            text = lts.render(result) + json.dumps(result)
            return [c for c in CANARIES if c in text]
        original = lts.entry_split
        self.prove("no_folder_instance_call_or_reply_text_in_output", observe, [],
                   lambda: patch.object(lts, "entry_split",
                                        lambda i, folder, w: dict(original(i, folder, w), label=folder.name)))

    def test_06_one_machine_type_only(self):
        def observe():
            a, b = lts.split(self.a10), lts.split(self.other)
            outcome = []
            for call in (lambda: lts.compare(a, b), lambda: lts.aggregate([a, b])):
                try:
                    call()
                    outcome.append("allowed")
                except lts.SplitError:
                    outcome.append("refused")
            outcome.append(lts.compare(a, a)["billed_seconds"])
            return outcome
        self.prove("different_machine_types_never_compared_or_summed", observe, ["refused", "refused", 0.0],
                   lambda: patch.object(lts, "same_machine", lambda first, second: True))


def check():
    LaunchTimeSplitChecks.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(LaunchTimeSplitChecks).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:5])
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass, on an invented session: sub-steps not "
                    "counted twice, every billed second in one category, the workload split into outside the "
                    "pipeline, model loads, generation and the rest, per-agent sums with the closed-object tail, "
                    "no identifier or text in the output, and no comparison or sum across machine types"
                    % len(LaunchTimeSplitChecks.evidence))


def main():
    status, detail = check()
    for proof in LaunchTimeSplitChecks.evidence:
        print(proof.get("name"), proof.get("status"))
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
