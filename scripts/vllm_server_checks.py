"""Proofs of the resident vLLM server (D-630 part A, A1): the REAL scripts/vllm_server.py run as a
subprocess through vllm_link.Link, on a fake `vllm`, `torch` and `transformers` in a temporary folder
(no vLLM, no GPU, no model). Proofs (a), (b) and (e) each carry a neutralisation: the server copied
with one line broken, the same proof run on it must fail.

    py -3.12 -X utf8 scripts/vllm_server_checks.py
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for _p in (str(HERE), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import vllm_link  # noqa: E402

SERVER = HERE / "vllm_server.py"
OBSERVER = ROOT / "tools" / "cloud_run_observer.py"
EOS = [7]

FAKE_TOK = '''
class FakeTok:
    chars = ["{", '"', "a", "b", "c", "d", "e", "}"]
    def __len__(self):
        return len(self.chars)
    def encode(self, text, add_special_tokens=False):
        return [self.chars.index(c) for c in text]
    def decode(self, ids, skip_special_tokens=True):
        return "".join(self.chars[i] for i in ids)
    def batch_decode(self, rows, skip_special_tokens=True):
        return [self.decode(r) for r in rows]
'''
FAKE_TRANSFORMERS = FAKE_TOK + '''
class AutoTokenizer:
    @staticmethod
    def from_pretrained(path, local_files_only=True):
        return FakeTok()
'''
FAKE_TORCH = '__version__ = "fake-torch"\n'
FAKE_VLLM = '''
import json, os, sys, types
__version__ = "fake-vllm"
if os.environ.get("FAKE_PRINT"):
    print("library chatter at import")
def _log(row):
    with open(os.environ["FAKE_VLLM_LOG"], "a") as log:
        log.write(json.dumps(row) + "\\n")
class SamplingParams:
    def __init__(self, **kw):
        self.kw = kw
class _Out:
    def __init__(self, ids):
        self.token_ids, self.finish_reason, self.text = ids, "stop", "t"
class _Req:
    def __init__(self, ids):
        self.outputs = [_Out(ids)]
class LLM:
    def __init__(self, **kw):
        if os.environ.get("FAKE_PRINT"):
            print("library chatter at engine start")
            os.write(1, b"native chatter at engine start\\n")
        if os.environ.get("FAKE_FAIL_ENGINE"):
            assert False, "engine refused"
        self.llm_engine = types.SimpleNamespace(model_config=types.SimpleNamespace(quantization=None, dtype="float16"))
    def generate(self, prompts, params, lora_request=None, use_tqdm=False):
        import vllm_constraint
        out = []
        for prompt, sp in zip(prompts, params):
            ids = prompt["prompt_token_ids"]
            kw = sp.kw
            _log({"ids": ids, "max_tokens": kw.get("max_tokens"), "stop_token_ids": kw.get("stop_token_ids"),
                  "ignore_eos": kw.get("ignore_eos", False), "temperature": kw.get("temperature"),
                  "extra_args": kw.get("extra_args"), "lora": lora_request,
                  "repetition_penalty": kw.get("repetition_penalty"), "skip_special_tokens": kw.get("skip_special_tokens")})
            if 999 in ids:
                raise RuntimeError("request refused")
            if os.environ.get("FAKE_PRINT"):
                print("library chatter at generate")
                os.write(1, b"native chatter at generate\\n")
            extra = kw.get("extra_args")
            if extra:
                vllm_constraint.COUNTS[extra["shimmer_constraint"]["key"]] = {"steps": 3, "interventions": 1}
            out.append(_Req([s + 100 for s in ids][:kw["max_tokens"]]))
        return out
'''
FAKE_FILES = {
    "vllm/__init__.py": FAKE_VLLM,
    "vllm/inputs/__init__.py": "class TokensPrompt(dict):\n    def __init__(self, prompt_token_ids):\n"
                               "        super().__init__(prompt_token_ids=prompt_token_ids)\n",
    "vllm/model_executor/__init__.py": "", "vllm/model_executor/determinism/__init__.py": "",
    "vllm/model_executor/determinism/batch_invariant.py": "_batch_invariant_MODE = True\n",
    "torch/__init__.py": FAKE_TORCH,
    "transformers/__init__.py": FAKE_TRANSFORMERS,
    # a small prefix, so the auxiliary environment's size is read in a moment, not over a whole Python
    "sitecustomize.py": "import os, sys" + chr(10) + "sys.prefix = os.path.join(os.path.dirname(__file__), 'prefix')" + chr(10),
    "prefix/lib/file.txt": "x" * 10,
}


def table_digest():
    import vllm_constraint
    ns = {}
    exec(FAKE_TOK, ns)
    return vllm_constraint.table_digest(ns["FakeTok"]())


def job(**over):
    found = {"protocol": vllm_link.PROTOCOL, "model": "m", "tokenizer": "fake-tok", "adapter": None, "lora_rank": None,
             "dtype": "float16", "max_model_len": 64, "batch": 1, "gpu_memory_utilization": 0.4,
             "repetition_penalty": 1.0, "observer": str(OBSERVER), "token_table_sha256": table_digest()}
    found.update(over)
    return found


def edited(folder, old, new):
    """A copy of the real server with one line replaced (it must exist), for a neutralisation."""
    text = SERVER.read_text(encoding="utf-8")
    assert old in text, old
    text = text.replace("Path(__file__).resolve().parents[1]", "Path(%r)" % str(ROOT), 1).replace(old, new, 1)
    path = Path(folder) / "scripts" / "vllm_server.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@contextlib.contextmanager
def session(server=SERVER, folder=None, env=None, **over):
    """A started Link on the fake packages, and the fake engine's request log (rows, one per request)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        d = Path(d)
        for name, text in FAKE_FILES.items():
            (d / "fake" / name).parent.mkdir(parents=True, exist_ok=True)
            (d / "fake" / name).write_text(text, encoding="utf-8")
        environ = dict(os.environ, PYTHONPATH=str(d / "fake"), FAKE_VLLM_LOG=str(d / "fake.log"),
                       SHIMMER_VLLM_LOG_DIR=str(d), HF_HUB_OFFLINE="1", VLLM_BATCH_INVARIANT="1")
        environ.update(env or {})
        link = vllm_link.Link(sys.executable, job(**over), script=server, env=environ, hello_seconds=120)

        def rows():
            log = d / "fake.log"
            return [json.loads(x) for x in log.read_text().splitlines()] if log.is_file() else []
        try:
            yield link, rows
        finally:
            link.close()


def prove_round_trip(server=SERVER):
    with session(server, repetition_penalty=1.05) as (link, rows):
        reply = link.generate([5, 6, 7], 2, EOS)
        assert reply["token_ids"] == [105, 106], reply
        assert set(reply) == set(vllm_link.REPLY_FIELDS), sorted(reply)
        row = rows()[0]
        assert row["ids"] == [5, 6, 7] and row["max_tokens"] == 2, row
        assert row["stop_token_ids"] == EOS and row["ignore_eos"] is True and row["temperature"] == 0.0, row
        assert row["extra_args"] is None and row["lora"] is None, row
        assert row["repetition_penalty"] == 1.05, row      # the checkpoint's own setting, carried


def prove_stdout_noise(server=SERVER):
    with session(server, env={"FAKE_PRINT": "1"}) as (link, rows):
        assert link.generate([1, 2], 4, EOS)["token_ids"] == [101, 102]
        assert link.generate([3], 4, EOS)["token_ids"] == [103]


def prove_table_mismatch(server=SERVER):
    try:
        with session(server, token_table_sha256="0" * 64):
            pass
    except vllm_link.LinkError as exc:
        # the SERVER refuses (a hello with an error); the link's own comparison of the hello is a second net
        assert "did not start: RuntimeError: the token table differs" in str(exc), exc
        return
    raise AssertionError("a token table that differs was accepted")


class ServerProof(unittest.TestCase):
    def test_a_generate_round_trip_reaches_the_engine_as_asked(self):
        prove_round_trip()

    def test_a_library_print_does_not_break_the_link(self):
        prove_stdout_noise()

    def test_a_constrained_request_passes_its_constraint_and_returns_the_counts(self):
        with session() as (link, rows):
            reply = link.generate([1, 2, 3], 4, EOS, constraint={"prompt": "p", "agent": "A"})
            plain = link.generate([1], 4, EOS)
            extra = rows()[0]["extra_args"]["shimmer_constraint"]
            self.assertEqual(extra, {"prompt": "p", "agent": "A", "key": "link:r1", "prompt_tokens": 3, "eos": EOS})
            self.assertEqual(reply["constraint"], {"steps": 3, "interventions": 1})
            self.assertIsNone(plain["constraint"])

    def test_an_engine_start_failure_is_a_hello_with_an_error(self):
        with self.assertRaises(vllm_link.LinkError) as caught:
            with session(env={"FAKE_FAIL_ENGINE": "1"}):
                pass
        self.assertIn("the server did not start", str(caught.exception))
        self.assertIn("AssertionError", str(caught.exception))

    def test_another_token_table_is_refused_at_start(self):
        prove_table_mismatch()

    def test_a_job_with_a_missing_field_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            bad = job()
            del bad["batch"]
            import subprocess
            done = subprocess.run([sys.executable, str(SERVER)], input=json.dumps(bad) + "\n", capture_output=True,
                                  text=True, timeout=120, cwd=d)
            self.assertEqual(done.returncode, 3)
            self.assertIn("job fields", vllm_link.decode_line(done.stdout.splitlines()[0])["error"])

    def test_a_failing_request_is_an_error_reply_and_the_next_one_succeeds(self):
        with session() as (link, rows):
            with self.assertRaises(vllm_link.LinkError) as caught:
                link.generate([999], 4, EOS)
            self.assertIn("RuntimeError: request refused", str(caught.exception))
            self.assertEqual(link.generate([1], 4, EOS)["token_ids"], [101])

    def test_the_hello_carries_the_start_figures(self):
        with session() as (link, rows):
            hello = link.hello
            for key in ("import_seconds", "engine_seconds"):
                self.assertIsInstance(hello[key], float)
            self.assertGreater(hello["aux_env"]["bytes"], 0)
            self.assertGreater(hello["aux_env"]["files"], 0)
            self.assertEqual(hello["versions"], {"vllm": "fake-vllm", "torch": "fake-torch", "batch_invariant": "1"})
            self.assertEqual(hello["token_table_sha256"], table_digest())
            self.assertEqual(hello["loaded"]["dtype"], "float16")

    # Neutralisations: the server with one line broken; the same proof must fail on it.
    def test_neutralised_ignore_eos_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            broken = edited(d, "[vllm_child.params(job, p)]",
                            '[__import__("vllm").SamplingParams(temperature=0.0, max_tokens=p["max_new_tokens"], stop_token_ids=p["eos"])]')
            with self.assertRaises(AssertionError):
                prove_round_trip(broken)
        prove_round_trip()

    def test_neutralised_private_channel_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            broken = edited(d, "os.dup2(2, 1)", "pass")
            with self.assertRaises((AssertionError, vllm_link.LinkError)) as caught:
                prove_stdout_noise(broken)
            self.assertIn("outside the protocol", str(caught.exception))
        prove_stdout_noise()

    def test_neutralised_table_check_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            broken = edited(d, 'if digest != job["token_table_sha256"]:', "if False:")
            with self.assertRaises(AssertionError) as caught:
                prove_table_mismatch(broken)
            self.assertIn("the server's token table differs", str(caught.exception))
        prove_table_mismatch()


if __name__ == "__main__":
    unittest.main()
