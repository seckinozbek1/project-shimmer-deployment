"""Proofs of the vLLM link (D-630 part A, P0): the protocol against the stand-in server
(scripts/fixtures/vllm_link_stub.py), a real subprocess with real pipes, no vLLM and no model.

CardHandback (#297): the card is held by one engine at a time. A fake card of the A10's 22 GiB counts a
stand-in server's share (0.72, the 15.8 GiB A5 saw) while its process lives, and a model load of 7 GiB
beside it runs out of memory, as the producer did in A5. Each real load site on the server's card
(agent_wrapper._load_qwen, execution_topology.resident_model, final_models.resident, a GPU
embedding_store._load_model) must shut the server down first; a load on the CPU or another card must not;
a broken or exited server is retired, never started again; no load runs while a server is still starting;
each hand-back is one telemetry event; the server of another model is shut down before a server starts.

    py -3.12 -X utf8 scripts/vllm_link_checks.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vllm_link  # noqa: E402
from unittest.mock import patch  # noqa: E402

STUB = HERE / "fixtures" / "vllm_link_stub.py"


def job(**over):
    found = {"protocol": vllm_link.PROTOCOL, "model": "m", "tokenizer": "m", "adapter": None, "lora_rank": None,
             "dtype": "float16", "max_model_len": 4096, "batch": 1, "gpu_memory_utilization": 0.4,
             "repetition_penalty": 1.0, "observer": "o.py", "token_table_sha256": "a" * 64}
    found.update(over)
    return found


def link(mode="", reply=(11, 12), log=None, **over):
    env = dict(os.environ, VLLM_STUB_MODE=mode, VLLM_STUB_REPLY=json.dumps(list(reply)))
    if log:
        env["VLLM_STUB_LOG"] = str(log)
    return vllm_link.Link(sys.executable, job(**over), script=STUB, env=env, hello_seconds=60)


class Protocol(unittest.TestCase):
    def test_a_request_round_trips_and_the_server_sees_exactly_it(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "requests.jsonl"
            l = link(log=log)
            try:
                self.assertEqual(l.hello["protocol"], vllm_link.PROTOCOL)
                got = l.generate([1, 2, 3], 8, [7], {"prompt": "p", "agent": "VERIFIER"})
                self.assertEqual((got["token_ids"], got["finish_reason"]), ([11, 12, 7], "stop"))
                self.assertEqual(got["constraint"], {"stub": True, "agent": "VERIFIER"})
                again = l.generate([4], 1, [7])
                self.assertEqual((again["token_ids"], again["finish_reason"]), ([11], "length"))
            finally:
                l.close()
            sent = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([s["token_ids"] for s in sent], [[1, 2, 3], [4]])
            self.assertEqual(sorted(sent[0]), sorted(vllm_link.REQUEST_FIELDS))
            self.assertEqual(l.process.returncode, 0)   # shutdown answered, not killed

    def test_every_broken_link_is_a_LinkError_never_a_reply(self):
        for mode, words in (("badhello", "did not start"), ("table", "token table"), ("die", "closed its output (exit 4)"),
                            ("noise", "outside the protocol"), ("otherid", "another request")):
            with self.subTest(mode=mode):
                try:
                    l = link(mode)
                except vllm_link.LinkError as exc:
                    self.assertIn(words, str(exc))
                    continue
                try:
                    with self.assertRaises(vllm_link.LinkError) as caught:
                        l.generate([1], 4, [7])
                    self.assertIn(words, str(caught.exception))
                finally:
                    l.close()

    def test_a_link_that_failed_to_start_leaves_no_pipe_open(self):
        import subprocess
        started = []

        def popen(*args, **kwargs):
            started.append(subprocess.Popen(*args, **kwargs))
            return started[-1]
        env = dict(os.environ, VLLM_STUB_MODE="badhello")
        with self.assertRaises(vllm_link.LinkError):
            vllm_link.Link(sys.executable, job(), script=STUB, env=env, hello_seconds=60, popen=popen)
        (process,) = started
        self.assertTrue(process.stdin.closed and process.stdout.closed)
        self.assertIsNotNone(process.returncode)          # ended (killed after its error hello)

    def test_the_servers_log_goes_to_the_named_file(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "server.stderr.log"
            l = vllm_link.Link(sys.executable, job(), script=STUB, env=dict(os.environ), hello_seconds=60, stderr_path=log)
            l.close()
            self.assertIn("stub server log line", log.read_text(encoding="utf-8"))

    def test_a_popen_that_fails_leaves_no_log_file_open(self):
        opened = []
        real = vllm_link.server_log

        def recording(path):
            opened.append(real(path))
            return opened[-1]

        def failing(*args, **kwargs):
            raise OSError("no such python")
        with tempfile.TemporaryDirectory() as d, patch.object(vllm_link, "server_log", recording):
            with self.assertRaises(OSError):
                vllm_link.Link(sys.executable, job(), script=STUB, popen=failing, stderr_path=Path(d) / "log")
            self.assertTrue(opened[0].closed)

    def test_with_no_log_file_named_the_servers_stderr_is_discarded(self):
        seen = {}

        def recording(*args, **kwargs):
            seen.update(kwargs)
            raise OSError("recorded, not started")
        with self.assertRaises(OSError):
            vllm_link.Link(sys.executable, job(), script=STUB, popen=recording)
        import subprocess
        self.assertIs(seen["stderr"], subprocess.DEVNULL)

    def test_a_request_or_job_outside_the_protocol_is_refused_before_it_is_sent(self):
        self.assertIn("undeclared", vllm_link.job_error(dict(job(), extra=1)))
        self.assertIn("protocol", vllm_link.job_error(job(protocol="v0")))
        base = {"op": "generate", "id": "r1", "token_ids": [1], "max_new_tokens": 4, "eos": [7], "constraint": None}
        self.assertIsNone(vllm_link.request_error(base))
        for bad in ({"token_ids": []}, {"token_ids": [1.0]}, {"eos": []}, {"eos": [True]}, {"max_new_tokens": 0},
                    {"constraint": {"prompt": "p"}}, {"op": "stop"}):
            with self.subTest(bad=bad):
                self.assertIsNotNone(vllm_link.request_error(dict(base, **bad)))

    def test_the_switch_is_off_unless_set_and_refused_without_a_python(self):
        saved = {k: os.environ.pop(k, None) for k in (vllm_link.AGENTS_ENV, vllm_link.PYTHON_ENV)}
        try:
            self.assertFalse(vllm_link.routed("VERIFIER"))
            os.environ[vllm_link.AGENTS_ENV] = "VERIFIER, PRACTICE_AUDITOR"
            self.assertFalse(vllm_link.routed("PROCESSOR"))
            with self.assertRaises(vllm_link.LinkError):
                vllm_link.routed("VERIFIER")
            os.environ[vllm_link.PYTHON_ENV] = sys.executable
            self.assertTrue(vllm_link.routed("PRACTICE_AUDITOR"))
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None)
                if v is not None:
                    os.environ[k] = v


class Lifetime(unittest.TestCase):
    def setUp(self):
        import subprocess
        self.spawned = []
        real = subprocess.Popen

        def popen(*args, **kwargs):
            self.spawned.append(real(*args, stderr=subprocess.DEVNULL, **{k: v for k, v in kwargs.items() if k != "stderr"}))
            return self.spawned[-1]
        self.popen = popen

    def tearDown(self):
        for process in self.spawned:     # a neutralised close leaves its stub running: end it here
            if process.poll() is None:
                process.kill()
                process.wait()
        vllm_link._LINKS.clear()
        vllm_link._FAILED.clear()

    def test_a_server_that_never_says_hello_is_closed_not_left_holding_its_share(self):
        env = dict(os.environ, VLLM_STUB_MODE="hanghello")
        with self.assertRaises(vllm_link.LinkError) as caught:
            vllm_link.Link(sys.executable, job(), script=STUB, env=env, hello_seconds=2, popen=self.popen)
        self.assertIn("no answer from the server in 2 s", str(caught.exception))
        self.assertIsNotNone(self.spawned[0].poll())    # killed, not left running

    def test_a_link_that_hangs_on_a_request_is_closed_and_retired_for_the_run(self):
        env = dict(os.environ, VLLM_STUB_MODE="hang")
        made = []

        def make():
            made.append(vllm_link.Link(sys.executable, job(), script=STUB, env=env, hello_seconds=60, popen=self.popen))
            return made[-1]
        first = vllm_link.link_for("m", make)
        with self.assertRaises(vllm_link.LinkError):
            first.generate([1], 4, [7], seconds=2)
        self.assertIsNotNone(first.process.poll())       # closed: its GPU share is given back
        with self.assertRaises(vllm_link.LinkError) as caught:
            vllm_link.link_for("m", make)
        self.assertIn("failed earlier in this run", str(caught.exception))
        self.assertEqual(len(made), 1)                   # never a second engine start

    def test_a_failed_start_is_never_started_again(self):
        calls = []

        def make():
            calls.append(1)
            raise vllm_link.LinkError("the server did not start: engine failed")
        for _ in range(3):
            with self.assertRaises(vllm_link.LinkError):
                vllm_link.link_for("n", make)
        self.assertEqual(len(calls), 1)


def _no_close(self):
    return None


def _restarting_link_for(key, make):
    found = vllm_link._LINKS.get(key)
    if found is None or found.process.poll() is not None or found.broken:
        found = vllm_link._LINKS[key] = make()
    return found


NEUTRALIZATIONS = [
    (Protocol, "test_a_link_that_failed_to_start_leaves_no_pipe_open", vllm_link.Link, "close", _no_close),
    (Lifetime, "test_a_server_that_never_says_hello_is_closed_not_left_holding_its_share", vllm_link.Link, "close",
     _no_close),
    (Lifetime, "test_a_link_that_hangs_on_a_request_is_closed_and_retired_for_the_run", vllm_link, "link_for",
     _restarting_link_for),
    (Lifetime, "test_a_failed_start_is_never_started_again", vllm_link, "link_for",
     lambda key, make: make()),
    (Protocol, "test_every_broken_link_is_a_LinkError_never_a_reply", vllm_link, "hello_error", lambda hello, job: None),
    (Protocol, "test_every_broken_link_is_a_LinkError_never_a_reply", vllm_link, "decode_line",
     lambda line: __import__("json").loads(line[len(vllm_link.MARK):]) if line.startswith(vllm_link.MARK) else
     {"op": "reply", "id": "r1", "token_ids": [], "finish_reason": "stop", "seconds": 0, "constraint": None}),
    (Protocol, "test_every_broken_link_is_a_LinkError_never_a_reply", vllm_link, "reply_error", lambda reply, rid: None),
    (Lifetime, "test_a_link_that_hangs_on_a_request_is_closed_and_retired_for_the_run", vllm_link.Link, "close", _no_close),
    (Protocol, "test_the_servers_log_goes_to_the_named_file", vllm_link, "server_log", lambda path: None),
    (Protocol, "test_with_no_log_file_named_the_servers_stderr_is_discarded", vllm_link, "stderr_target", lambda log: log),
    (Protocol, "test_a_popen_that_fails_leaves_no_log_file_open", vllm_link, "close_log", lambda log: None),
    (Protocol, "test_the_switch_is_off_unless_set_and_refused_without_a_python", vllm_link, "agents",
     lambda: ("VERIFIER",)),
]


CARD_GIB, SHARE, LOAD_GIB = 22.0, 0.72, 7.0
AUDITOR = ("fixture-auditor", "/models/fixture-auditor")


class Card:
    """A fake card: each live stand-in server holds SHARE of it; a load on it needs LOAD_GIB."""

    def __init__(self):
        import subprocess
        self.servers, self.loaded, self._popen = [], [], subprocess.Popen

    def popen(self, *args, **kwargs):
        import subprocess
        kwargs["stderr"] = subprocess.DEVNULL
        self.servers.append(self._popen(*args, **kwargs))
        return self.servers[-1]

    def live(self):
        return [p for p in self.servers if p.poll() is None]

    def load(self, what):
        free = CARD_GIB * (1 - SHARE * len(self.live()))
        if free < LOAD_GIB:
            raise RuntimeError("CUDA out of memory: %s needs %.1f GiB, %.1f GiB free" % (what, LOAD_GIB, free))
        self.loaded.append(what)
        from types import SimpleNamespace
        return SimpleNamespace(generate=lambda *a, **k: None, parameters=lambda: iter(()))

    def make(self):
        return lambda: vllm_link.Link(sys.executable, job(), script=STUB, env=dict(os.environ), hello_seconds=60,
                                      popen=self.popen)

    def end(self):
        for process in self.servers:
            if process.poll() is None:
                process.kill()
                process.wait()


def fake_ml(card):
    """Stand-in torch and transformers modules (a CUDA card, no weights) whose model load asks the card."""
    from types import ModuleType, SimpleNamespace
    torch = ModuleType("torch")
    torch.float16 = "float16"
    torch.cuda = SimpleNamespace(is_available=lambda: True, is_initialized=lambda: False, empty_cache=lambda: None,
                                 device_count=lambda: 1, set_device=lambda i: None, memory_allocated=lambda i: 0)
    transformers = ModuleType("transformers")
    transformers.AutoTokenizer = SimpleNamespace(from_pretrained=lambda path, **k: "tokenizer")
    transformers.AutoModelForCausalLM = SimpleNamespace(from_pretrained=lambda path, **k: card.load(path))
    return {"torch": torch, "transformers": transformers}


def load_by_final_models(card):
    import final_models
    final_models._RESIDENTS.pop("final-producer", None)
    try:
        with patch.object(final_models, "load", lambda role, device: ("tokenizer", card.load(role))):
            final_models.resident("producer")
    finally:
        final_models._RESIDENTS.pop("final-producer", None)


def load_by_load_qwen(card):
    import agent_wrapper
    with patch.dict(sys.modules, fake_ml(card)), \
            patch.object(agent_wrapper, "_local_checkpoint_path", lambda m: "/models/" + m), \
            patch.object(agent_wrapper, "_checkpoint_is_prequantised", lambda t, c: True):
        try:
            agent_wrapper._load_qwen("fixture-producer")
        finally:
            agent_wrapper._QWEN_MODELS.pop("fixture-producer", None)


def load_by_worker(card):
    from types import SimpleNamespace
    import agent_wrapper
    import execution_topology
    worker = SimpleNamespace(residents={}, loads={}, healthy=True,
                             lane=SimpleNamespace(device="cuda:0", resident_limit=1))
    context = SimpleNamespace(worker=worker, checkpoint=lambda: None, event=lambda *a, **k: None)
    saved = getattr(execution_topology.WORK, "context", None)
    execution_topology.WORK.context = context
    try:
        with patch.dict(sys.modules, fake_ml(card)), \
                patch.object(agent_wrapper, "_local_checkpoint_path", lambda m: "/models/" + m), \
                patch.object(agent_wrapper, "_checkpoint_is_prequantised", lambda t, c: True):
            execution_topology.resident_model("fixture-producer")
    finally:
        execution_topology.WORK.context = saved


def load_by_embedding(card, device):
    from types import SimpleNamespace
    import embedding_store
    st = SimpleNamespace(SentenceTransformer=lambda name, device=None, **k: card.load(name) if device != "cpu"
                         else SimpleNamespace())
    embedding_store._MODEL_CACHE.pop("fixture-embedding", None)
    try:
        with patch.object(embedding_store, "_embed_device", lambda: device),                 patch.object(embedding_store, "_ensure_safetensors", lambda name: None):
            embedding_store._load_model(st, "fixture-embedding")
    finally:
        embedding_store._MODEL_CACHE.pop("fixture-embedding", None)


class FakeRun:
    def __init__(self, folder):
        self.run_id, self.folder = "fixture-run", Path(folder)

    def logs_dir(self):
        return self.folder / "logs"


class CardHandback(unittest.TestCase):
    def setUp(self):
        self.card = Card()
        for table in (vllm_link._LINKS, vllm_link._FAILED, vllm_link._STARTS):
            table.clear()
        del vllm_link.YIELDS[:]

    def tearDown(self):
        lock = vllm_link.CARD_LOCK      # a neutralised release leaves the card lock held by this thread: free it
        while getattr(lock, "_is_owned", lambda: False)():
            lock.release()
        vllm_link.close_all()
        self.card.end()
        for table in (vllm_link._FAILED, vllm_link._STARTS):
            table.clear()
        del vllm_link.YIELDS[:]

    def prove(self, site):
        card = self.card
        first = vllm_link.link_for(AUDITOR, card.make())
        self.assertEqual(first.generate([1], 4, [7])["token_ids"], [11, 12, 7])
        self.assertEqual(len(card.live()), 1)
        site(card)                                      # out of memory while the server holds its share
        self.assertEqual(len(card.loaded), 1)
        self.assertEqual(first.process.returncode, 0)  # asked to shut down and answered, not killed
        (record,) = vllm_link.YIELDS
        self.assertEqual((record["model"], record["kind"], record["requests"], record["start_number"], record["exit"]),
                         (AUDITOR[0], "transformers_load", 1, 1, 0))
        with self.assertRaises(vllm_link.Yielded):     # the old link sends nothing more
            first.generate([1], 4, [7])
        self.assertNotIn(AUDITOR, vllm_link._FAILED)    # not a failure: the next routed call starts it again
        again = vllm_link.link_for(AUDITOR, card.make())
        self.assertIsNot(again, first)
        self.assertEqual((again.start_number, again.generate([2], 4, [7])["token_ids"]), (2, [11, 12, 7]))

    def test_the_server_gives_the_card_back_before_final_models_loads_the_producer(self):
        self.prove(load_by_final_models)

    def test_the_server_gives_the_card_back_before_load_qwen_loads_a_model(self):
        self.prove(load_by_load_qwen)

    def test_the_server_gives_the_card_back_before_a_worker_loads_its_resident(self):
        self.prove(load_by_worker)

    def test_the_server_gives_the_card_back_before_an_embedding_model_loads_on_the_gpu(self):
        self.prove(lambda card: load_by_embedding(card, "cuda"))

    def test_with_no_server_resident_a_load_is_as_before(self):
        load_by_final_models(self.card)
        self.assertEqual((len(self.card.loaded), vllm_link.YIELDS), (1, []))

    def test_a_load_on_the_cpu_or_another_card_leaves_the_server_running(self):
        first = vllm_link.link_for(AUDITOR, self.card.make())
        load_by_embedding(self.card, "cpu")             # the local profile's embedding device
        for device in ("cpu", "cuda:1", None):
            with vllm_link.card_for("elsewhere", device):
                pass
        self.assertEqual((self.card.live(), vllm_link.YIELDS), ([first.process], []))
        self.assertIs(vllm_link.link_for(AUDITOR, self.card.make()), first)

    def test_a_broken_or_exited_server_is_retired_by_the_hand_back_not_started_again(self):
        first = vllm_link.link_for(AUDITOR, self.card.make())
        first.process.kill()
        first.process.wait()
        load_by_final_models(self.card)
        self.assertEqual(vllm_link.YIELDS, [])           # a retirement, not a hand-back
        with self.assertRaises(vllm_link.LinkError) as caught:
            vllm_link.link_for(AUDITOR, self.card.make())
        self.assertIn("failed earlier in this run", str(caught.exception))
        self.assertEqual(len(self.card.servers), 1)      # never a second engine start

    def test_no_load_runs_beside_a_server_that_is_still_starting(self):
        import threading
        spawned, release, outcome = threading.Event(), threading.Event(), {}

        def slow_make():
            link = self.card.make()()                    # the engine holds its share before link_for returns
            spawned.set()
            release.wait(30)
            return link

        def start():
            outcome["link"] = vllm_link.link_for(AUDITOR, slow_make)

        def load():
            try:
                load_by_final_models(self.card)
                outcome["load"] = "loaded"
            except Exception as exc:
                outcome["load"] = str(exc)
        starter = threading.Thread(target=start)
        starter.start()
        self.assertTrue(spawned.wait(60))
        loader = threading.Thread(target=load)
        loader.start()
        try:
            loader.join(1.0)
            self.assertTrue(loader.is_alive(), outcome.get("load"))   # it waits for the start
        finally:
            release.set()
            starter.join(60)
            loader.join(60)
        self.assertEqual(outcome["load"], "loaded")
        self.assertEqual(outcome["link"].process.returncode, 0)    # then the card went back
        self.assertEqual([r["model"] for r in vllm_link.YIELDS], [AUDITOR[0]])

    def test_no_server_starts_between_a_hand_back_and_its_load(self):
        import threading
        import final_models
        loading, finish, outcome = threading.Event(), threading.Event(), {}

        def slow_load(role, device):
            loading.set()
            finish.wait(30)
            return "tokenizer", self.card.load(role)    # out of memory if a server started meanwhile

        def load():
            try:
                with patch.object(final_models, "load", slow_load):
                    final_models._RESIDENTS.pop("final-producer", None)
                    final_models.resident("producer")
                outcome["load"] = "loaded"
            except Exception as exc:
                outcome["load"] = str(exc)
            finally:
                final_models._RESIDENTS.pop("final-producer", None)

        def start():
            outcome["link"] = vllm_link.link_for(AUDITOR, self.card.make())
        loader = threading.Thread(target=load)
        loader.start()
        self.assertTrue(loading.wait(60))
        starter = threading.Thread(target=start)
        starter.start()
        try:
            starter.join(1.0)
            self.assertTrue(starter.is_alive())          # the start waits for the load
        finally:
            finish.set()
            loader.join(60)
            starter.join(60)
        self.assertEqual(outcome["load"], "loaded")
        self.assertIsNone(outcome["link"].process.poll())   # then it started

    def test_each_hand_back_is_one_bounded_telemetry_event_in_the_run(self):
        with tempfile.TemporaryDirectory() as d:
            first = vllm_link.link_for(AUDITOR, self.card.make())
            first.run_context = FakeRun(d)
            load_by_final_models(self.card)
            rows = [json.loads(x) for x in (Path(d) / "logs" / "model_telemetry.jsonl").read_text(
                encoding="utf-8").splitlines()]
        (row,) = rows
        self.assertEqual(row["event"], vllm_link.YIELD_EVENT)
        self.assertEqual(set(row), {"schema_version", "run_id", "event", "monotonic_s", "utc", "model", "kind",
                                    "for_model", "requests", "start_number", "exit", "close_seconds"})
        self.assertEqual((row["model"], row["kind"], row["for_model"], row["exit"]),
                         (AUDITOR[0], "transformers_load", "final-producer", 0))

    def test_a_telemetry_error_never_stops_the_hand_back(self):
        a = vllm_link.link_for(AUDITOR, self.card.make())
        b = vllm_link.link_for(("fixture-other", "/models/other"), self.card.make())

        class Unwritable:
            run_id = "fixture-run"

            def logs_dir(self):
                raise OSError("telemetry folder unwritable")
        a.run_context = b.run_context = Unwritable()
        load_by_final_models(self.card)
        self.assertEqual((a.process.returncode, b.process.returncode, len(self.card.loaded)), (0, 0, 1))
        self.assertEqual([r.get("telemetry_error") for r in vllm_link.YIELDS], ["OSError", "OSError"])

    def test_the_card_lock_is_free_after_a_failed_load_or_a_failed_hand_back(self):
        import threading
        import final_models

        def free_elsewhere():
            got = []
            t = threading.Thread(target=lambda: got.append(vllm_link.CARD_LOCK.acquire(timeout=2) and
                                                           (vllm_link.CARD_LOCK.release() or True)))
            t.start()
            t.join(10)
            return got == [True]

        def failing_load(role, device):
            raise RuntimeError("load failed")
        with patch.object(final_models, "load", failing_load), self.assertRaises(RuntimeError):
            final_models.resident("producer")
        self.assertTrue(free_elsewhere(), "the card lock is still held after a failed load")
        vllm_link.link_for(AUDITOR, self.card.make())

        def failing_close(self, graceful=True):
            raise RuntimeError("close failed")
        with patch.object(vllm_link.Link, "close", failing_close), self.assertRaises(RuntimeError):
            load_by_final_models(self.card)
        self.assertTrue(free_elsewhere(), "the card lock is still held after a failed hand-back")

    def test_a_failed_close_leaves_no_server_running(self):
        vllm_link.link_for(AUDITOR, self.card.make())
        vllm_link.link_for(("fixture-other", "/models/other"), self.card.make())
        real, calls = vllm_link.Link.close, []

        def first_fails(link, graceful=True):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("close failed")
            return real(link, graceful)
        with patch.object(vllm_link.Link, "close", first_fails), self.assertRaises(RuntimeError):
            load_by_final_models(self.card)
        self.assertEqual(self.card.live(), [])              # neither server is left holding its share
        self.assertEqual(len(calls), 2)                      # the second server was still shut down

    def test_the_server_of_another_model_is_shut_down_before_a_server_starts(self):
        import vllm_route
        from types import SimpleNamespace
        env = {vllm_link.PYTHON_ENV: sys.executable, vllm_link.JOB_ENV: json.dumps({"batch_invariant": True})}
        with patch.dict(os.environ, env), patch.object(vllm_link, "SERVER", STUB), \
                patch.object(vllm_route, "job_for", lambda *a: job()), patch.object(vllm_route, "free_gpu", lambda: None), \
                patch.object(vllm_route, "_replay", lambda: SimpleNamespace(child_env=lambda py, inv: dict(os.environ))):
            a = vllm_route.start("model-a", "/models/a", None, popen=self.card.popen)
            self.assertIs(vllm_route.start("model-a", "/models/a", None, popen=self.card.popen), a)
            b = vllm_route.start("model-b", "/models/b", None, popen=self.card.popen)
        self.assertEqual(a.process.returncode, 0)
        self.assertEqual(self.card.live(), [b.process])
        self.assertEqual([(r["model"], r["kind"]) for r in vllm_link.YIELDS], [("model-a", "server_start")])


def _no_yield(kind, for_model, keep=None):
    return []


class _NoLock:
    def acquire(self, *a, **k):
        return True

    def release(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


NEUTRALIZATIONS += [
    (CardHandback, "test_the_server_gives_the_card_back_before_final_models_loads_the_producer", vllm_link,
     "yield_card", _no_yield),
    (CardHandback, "test_the_server_gives_the_card_back_before_load_qwen_loads_a_model", vllm_link,
     "yield_card", _no_yield),
    (CardHandback, "test_the_server_gives_the_card_back_before_a_worker_loads_its_resident", vllm_link,
     "yield_card", _no_yield),
    (CardHandback, "test_the_server_gives_the_card_back_before_an_embedding_model_loads_on_the_gpu", vllm_link,
     "on_server_card", lambda device: False),
    (CardHandback, "test_a_load_on_the_cpu_or_another_card_leaves_the_server_running", vllm_link,
     "on_server_card", lambda device: True),
    (CardHandback, "test_the_server_gives_the_card_back_before_final_models_loads_the_producer", vllm_link.Link,
     "close", _no_close),
    (CardHandback, "test_the_server_gives_the_card_back_before_load_qwen_loads_a_model", vllm_link,
     "yield_card", lambda kind, for_model, keep=None: [vllm_link.retire(k, kind) for k in list(vllm_link._LINKS)]),
    (CardHandback, "test_a_broken_or_exited_server_is_retired_by_the_hand_back_not_started_again", vllm_link,
     "unusable", lambda link: None),
    (CardHandback, "test_no_load_runs_beside_a_server_that_is_still_starting", vllm_link, "link_for",
     lambda key, make: vllm_link._LINKS.setdefault(key, make())),
    (CardHandback, "test_no_server_starts_between_a_hand_back_and_its_load", vllm_link, "CARD_LOCK", _NoLock()),
    (CardHandback, "test_each_hand_back_is_one_bounded_telemetry_event_in_the_run", vllm_link, "emit_yield",
     lambda run_context, record: None),
    (CardHandback, "test_the_server_of_another_model_is_shut_down_before_a_server_starts", vllm_link,
     "yield_card", _no_yield),
    (CardHandback, "test_a_telemetry_error_never_stops_the_hand_back", vllm_link, "record_yield",
     lambda link, record: (vllm_link.YIELDS.append(record), vllm_link.emit_yield(link.run_context, record))),
    (CardHandback, "test_a_failed_close_leaves_no_server_running", vllm_link, "ensure_down", lambda link: None),
    (CardHandback, "test_the_card_lock_is_free_after_a_failed_load_or_a_failed_hand_back", vllm_link.card_for,
     "__exit__", lambda self, *exc: False),
]


class Neutralizations(unittest.TestCase):
    def test_each_proof_fails_when_its_rule_is_neutralised_and_passes_restored(self):
        import io
        from unittest.mock import patch
        for case, name, owner, attribute, broken in NEUTRALIZATIONS:
            with self.subTest(name=name):
                with patch.object(owner, attribute, broken):
                    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(case(name))
                self.assertFalse(result.wasSuccessful(), "%s still passes neutralised" % name)
                restored = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(case(name))
                self.assertTrue(restored.wasSuccessful(), name)


if __name__ == "__main__":
    unittest.main(verbosity=1)
