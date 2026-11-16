"""The runner's side of the vLLM route (D-630 part A, #217): one resident vLLM server per local
model, in the auxiliary environment's own Python, spoken to over its standard input and output.

Why pipes and not HTTP: the runner's network denial (cloud_run_observer.deny_network) refuses the
HTTP clients (requests, httpx, http.client) in every Python process it is applied to, and an HTTP
client is what a vLLM server is spoken to with (it lets a numeric loopback socket connect, so the
refusal is of the client, not the socket); and the call must stay inside the backend function that
holds the raw text (REPLIES-A), so the reply record is written exactly as for transformers. The server (scripts/vllm_server.py) never decides anything: it generates the
token ids a request asks for under the frozen decoding and the request's own constraint, and
the runner decodes, records and validates them as it always does.

Protocol `vllm-link-v1`, one JSON object per line, UTF-8:
  runner -> server, first line: the job
      {"protocol", "model", "tokenizer", "adapter", "lora_rank", "dtype", "max_model_len",
       "batch", "gpu_memory_utilization", "repetition_penalty", "observer", "token_table_sha256"}
  server -> runner, once the engine is up: hello
      {"op": "hello", "protocol", "versions", "loaded", "token_table_sha256",
       "import_seconds", "engine_seconds", "aux_env"}            (or {"op": "hello", "error"})
  runner -> server: {"op": "generate", "id", "token_ids", "max_new_tokens", "eos",
                     "constraint": null | {"prompt", "agent"} | {"prompt", "agent", "contract"}}
  server -> runner: {"op": "reply", "id", "token_ids", "finish_reason", "seconds",
                     "constraint": null | <the constraint's own record>}
                    or {"op": "reply", "id", "error"}
  runner -> server: {"op": "shutdown"}; the server exits 0.
Every server line on the protocol channel starts with MARK; anything else on that channel (a
library printing to the original standard output) is refused as a broken link, never parsed.

The card is held by one engine at a time (#297). Every model load on the server's card holds CARD_LOCK across
its hand-back and its load (card_for: agent_wrapper._load_qwen, execution_topology.resident_model,
final_models.resident and, on a GPU, embedding_store._load_model), and a server's start holds it across the
whole start (link_for), so no load runs beside a starting server and no server starts between a hand-back and
its load. The hand-back (yield_card) shuts every resident server down and waits for its exit; a server that
broke or exited is retired instead, never started again. The server of another model is shut down before a
server starts (vllm_route.start). A server shut down so is not a failure: the next routed call starts it again
(after vllm_route.free_gpu), so the order the run reaches its calls in decides when the card changes hands.
The server runs on SERVER_DEVICE, the first card its process sees (it inherits the runner's environment); a
load on the CPU or on another card does not take the card back. Lock order: CARD_LOCK (reentrant) is always
taken first, then _LINKS_LOCK, then a link's lock or a load site's own lock (agent_wrapper._QWEN_LOAD_LOCK,
final_models._LOAD_LOCK); free_gpu takes those load locks inside a start, under CARD_LOCK and _LINKS_LOCK, and
no load site takes _LINKS_LOCK or CARD_LOCK while it holds its own lock, so the order never inverts.

The route is OFF unless SHIMMER_VLLM_AGENTS, SHIMMER_VLLM_JOB and SHIMMER_VLLM_PYTHON are all set. In a
sealed bundle only the runner sets them (the first two from the manifest, the third to venv_aux's
Python; it removes every inherited SHIMMER_ name first). Outside a bundle (a laptop or harness run)
nothing sets them: setting all three by hand is the operator's own switch, as any SHIMMER_ setting is. A
failure on the route is a failed call, recorded as one; it never falls back to transformers.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

PROTOCOL = "vllm-link-v1"
MARK = "VLLM_LINK "
AGENTS_ENV = "SHIMMER_VLLM_AGENTS"
PYTHON_ENV = "SHIMMER_VLLM_PYTHON"
JOB_ENV = "SHIMMER_VLLM_JOB"            # the sealed job fields (JSON): dtype, batch, memory share, lengths
HELLO_SECONDS = 1800                    # engine start measured at 112 to 176 s on the A10; a generous bound
JOB_FIELDS = ("protocol", "model", "tokenizer", "adapter", "lora_rank", "dtype", "max_model_len", "batch",
              "gpu_memory_utilization", "repetition_penalty", "observer", "token_table_sha256")
REQUEST_FIELDS = ("op", "id", "token_ids", "max_new_tokens", "eos", "constraint")
REPLY_FIELDS = ("op", "id", "token_ids", "finish_reason", "seconds", "constraint")
SERVER = Path(__file__).resolve().with_name("vllm_server.py")


class LinkError(RuntimeError):
    """The link cannot answer: the server failed, closed, broke the protocol or ran past its time."""


class Yielded(LinkError):
    """The server was shut down to give the card back (yield_card); this request was never sent. A
    later call starts the server again."""


class RequestFailed(LinkError):
    """The server answered one request with an error (its text is the server's exception, e.g. an
    out-of-memory); the link still holds."""

    def __init__(self, error):
        super().__init__("the server failed the request: %s" % error)
        self.server_error = error


def agents():
    """The agents the sealed switch routes to vLLM; empty (off) unless the runner set it."""
    raw = os.environ.get(AGENTS_ENV, "")
    return tuple(a for a in (x.strip() for x in raw.split(",")) if a)


def routed(name):
    """True when this agent's local generate calls go to vLLM. A switch with no Python named is
    refused, never read as off."""
    listed = agents()
    if name not in listed:
        return False
    if not os.environ.get(PYTHON_ENV):
        raise LinkError("%s names %s but %s is not set" % (AGENTS_ENV, name, PYTHON_ENV))
    return True


def sealed_job():
    """The sealed job fields the runner passed (dtype, batch, memory share, context length)."""
    raw = os.environ.get(JOB_ENV)
    if not raw:
        raise LinkError("%s is not set" % JOB_ENV)
    found = json.loads(raw)
    if not isinstance(found, dict):
        raise LinkError("%s is not an object" % JOB_ENV)
    return found


def encode(message):
    return json.dumps(message, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def server_line(message):
    """A server's protocol line."""
    return MARK + encode(message)


def decode_line(line):
    """A protocol line from the server, or LinkError."""
    if not line.startswith(MARK):
        raise LinkError("the server wrote outside the protocol: %r" % line[:120])
    try:
        found = json.loads(line[len(MARK):])
    except ValueError as exc:
        raise LinkError("the server wrote a line that is not JSON: %s" % exc) from None
    if not isinstance(found, dict) or "op" not in found:
        raise LinkError("the server wrote a line with no op")
    return found


def job_error(job):
    """Why a job cannot be sent, or None."""
    missing = [f for f in JOB_FIELDS if f not in job]
    extra = sorted(set(job) - set(JOB_FIELDS))
    if missing or extra:
        return "job fields: missing %s, undeclared %s" % (missing, extra)
    if job["protocol"] != PROTOCOL:
        return "job protocol %r is not %s" % (job["protocol"], PROTOCOL)
    return None


def request_error(request):
    """Why a request cannot be sent, or None."""
    if set(request) != set(REQUEST_FIELDS) or request.get("op") != "generate":
        return "request fields %s" % sorted(request)
    ids, eos = request["token_ids"], request["eos"]
    if not (isinstance(ids, list) and ids and all(type(i) is int for i in ids)):
        return "token_ids must be a non-empty list of integers"
    if not (isinstance(eos, list) and eos and all(type(i) is int for i in eos)):
        return "eos must be a non-empty list of integers (the frozen policy's stop ids)"
    if type(request["max_new_tokens"]) is not int or request["max_new_tokens"] < 1:
        return "max_new_tokens must be a positive integer"
    constraint = request["constraint"]
    if constraint is not None and (not isinstance(constraint, dict) or
                                   set(constraint) not in ({"prompt", "agent"}, {"prompt", "agent", "contract"})):
        return "a constraint is {prompt, agent} or {prompt, agent, contract}"
    if constraint is not None and "contract" in constraint and not isinstance(constraint["contract"], dict):
        return "a constraint's contract is the agent's contract object"
    return None


def reply_error(reply, request_id):
    """Why a reply cannot be read, or None. A reply carrying an error is read by the caller."""
    if reply.get("op") != "reply" or reply.get("id") != request_id:
        return "a reply to another request (%r, %r)" % (reply.get("op"), reply.get("id"))
    if "error" in reply:
        return None
    if set(reply) != set(REPLY_FIELDS):
        return "reply fields %s" % sorted(reply)
    if not isinstance(reply["token_ids"], list) or not all(type(i) is int for i in reply["token_ids"]):
        return "reply token_ids must be a list of integers"
    return None


def server_log(path):
    """The server's log file (appended), or None when no file is named."""
    return open(path, "a", encoding="utf-8") if path else None


def stderr_target(log):
    """Where the server's stderr goes: its log file, or nowhere (never the runner's own stderr)."""
    return log if log is not None else subprocess.DEVNULL


def close_log(log):
    if log is not None:
        log.close()


def hello_error(hello, job):
    """Why a hello is not a started server of this job, or None."""
    if hello.get("op") != "hello" or "error" in hello:
        return "the server did not start: %s" % hello.get("error", hello.get("op"))
    if hello.get("protocol") != PROTOCOL:
        return "the server speaks %r" % hello.get("protocol")
    if hello.get("token_table_sha256") != job["token_table_sha256"]:
        return "the server's token table differs from the runner's"
    return None


class Link:
    """One server process. Calls are serialised (part A); the protocol carries ids so that a later
    part can keep several in flight."""

    def __init__(self, python, job, script=None, popen=subprocess.Popen, env=None, hello_seconds=HELLO_SECONDS,
                 stderr_path=None):
        problem = job_error(job)
        if problem:
            raise LinkError(problem)
        self.job = dict(job)
        self.lock = threading.Lock()
        self.lines = queue.Queue()
        self.count = 0
        self.broken = None
        self.yielded = None
        started = time.perf_counter()
        # The server's own log (vLLM's startup lines, a traceback) goes to its file in the run's logs, or is
        # discarded with no file named; never into the workload's stderr, whose Traceback and out-of-memory
        # markers the live view counts.
        self.stderr = server_log(stderr_path)
        try:
            self.process = popen([python, "-u", str(script or SERVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=stderr_target(self.stderr), text=True, encoding="utf-8", bufsize=1, env=env)
        except BaseException:
            close_log(self.stderr)
            raise
        threading.Thread(target=self._read, daemon=True).start()
        try:      # any failure to start (an error hello, a timeout, a closed output, a stray line) closes it
            self._send(self.job)
            self.hello = self._receive(hello_seconds)
            self.hello["start_seconds"] = round(time.perf_counter() - started, 3)
            problem = hello_error(self.hello, job)
            if problem:
                raise LinkError(problem)
        except LinkError:
            self.close(graceful=False)
            raise

    def _read(self):
        for line in self.process.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def _send(self, message):
        try:
            self.process.stdin.write(encode(message))
            self.process.stdin.flush()
        except (OSError, ValueError) as exc:
            raise LinkError("the server's input is closed: %s" % type(exc).__name__) from None

    def _receive(self, seconds):
        try:
            line = self.lines.get(timeout=seconds)
        except queue.Empty:
            raise LinkError("no answer from the server in %d s" % seconds) from None
        if line is None:
            # The output closes a moment before the process is reaped: wait briefly for its exit code.
            try:
                code = self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                code = "not yet known"
            raise LinkError("the server closed its output (exit %s)" % code)
        return decode_line(line.rstrip("\n"))

    def generate(self, token_ids, max_new_tokens, eos, constraint=None, seconds=HELLO_SECONDS):
        with self.lock:
            if self.yielded:
                raise Yielded("the server was shut down to give the card back (%s); the request was not sent"
                              % self.yielded)
            self.count += 1
            request = {"op": "generate", "id": "r%d" % self.count, "token_ids": list(token_ids),
                       "max_new_tokens": max_new_tokens, "eos": list(eos), "constraint": constraint}
            problem = request_error(request)
            if problem:
                raise LinkError(problem)
            try:      # a link that broke (a timeout, a closed output, a stray line, another id) is closed for good
                self._send(request)
                reply = self._receive(seconds)
                problem = reply_error(reply, request["id"])
                if problem:
                    raise LinkError(problem)
            except LinkError as exc:
                self.broken = str(exc)
                self.close(graceful=False)
                raise
            if "error" in reply:      # the server answered: one request failed, the link holds
                raise RequestFailed(reply["error"])
            return reply

    def close(self, graceful=True):
        """Shut the server down (or kill it after 60 s) and close both pipes, so the reader thread
        ends and nothing is left open (a failed start included). A server that broke the link is
        killed at once: it cannot be asked to shut down."""
        try:
            if graceful and self.process.poll() is None:
                self._send({"op": "shutdown"})
                self.process.wait(timeout=60)
        except Exception:
            pass
        if self.process.poll() is None:
            self.process.kill()
            try:
                self.process.wait(timeout=30)
            except Exception:
                pass
        for pipe in (self.process.stdin, self.process.stdout, self.stderr):
            try:
                if pipe is not None:
                    pipe.close()
            except Exception:
                pass


_LINKS = {}
_FAILED = {}
_STARTS = {}        # key -> how many times this model's server was started in this process
YIELDS = []         # one record per server shut down to give the card back (also a telemetry event)
_LINKS_LOCK = threading.Lock()
CARD_LOCK = threading.RLock()     # held across a hand-back and its load, and across a server's start
SERVER_DEVICE = "cuda:0"
YIELD_EVENT = "vllm_server_yield"


def unusable(link):
    """Why a server can never serve again (it broke the link or exited), or None."""
    if link.broken:
        return link.broken
    code = link.process.poll()
    return None if code is None else "it exited (%s)" % code


def link_for(key, make):
    """The one link of this model in this process, started on first use by `make()`. A server that
    failed to start, broke or exited is never started again in this process: every later call is
    refused at once with the first failure's reason (no second engine start, no second GPU share).
    The start holds CARD_LOCK, so no model loads on the card while a server is starting."""
    with CARD_LOCK, _LINKS_LOCK:
        if key in _FAILED:
            raise LinkError("the server of this model failed earlier in this run: %s" % _FAILED[key])
        found = _LINKS.get(key)
        if found is not None and unusable(found):
            _FAILED[key] = unusable(found)
            _LINKS.pop(key).close()
            raise LinkError("the server of this model failed earlier in this run: %s" % _FAILED[key])
        if found is None:
            try:
                found = _LINKS[key] = make()
            except Exception as exc:
                _FAILED[key] = "%s: %s" % (type(exc).__name__, str(exc)[:300])
                raise
            _STARTS[key] = _STARTS.get(key, 0) + 1
            found.start_number = _STARTS[key]
        return found


def yield_card(kind, for_model, keep=None):
    """Shut down every resident server but `keep` and wait for each to exit, so its card share is free.
    The servers are taken out of _LINKS under _LINKS_LOCK; the waits run outside it, under CARD_LOCK only.
    The wait is a call in flight on the server first (its lock is taken), which can last up to that
    request's sealed request_seconds (600), then the shutdown (killed after 60 s). Meanwhile every load
    and every server start on the card waits for CARD_LOCK: intended, since the card cannot be given
    back during a call. Not a failure: the server is not marked failed, and the next routed call of its
    model starts it again. A server that broke or exited is retired as link_for retires it (never
    started again in the run). `kind` is a short name (transformers_load, server_start). Returns the
    records, each kept in YIELDS as soon as its server is down and written as one telemetry event into
    the link's run (a telemetry error is recorded on the record, never stops the hand-back)."""
    records = []
    with CARD_LOCK:
        with _LINKS_LOCK:
            taken = [(k, _LINKS.pop(k)) for k in [k for k in _LINKS if k != keep]]
        error = None
        for key, link in taken:      # every server taken out is brought down, even when one close fails
            try:
                if unusable(link):
                    with _LINKS_LOCK:
                        _FAILED[key] = unusable(link)
                    link.close(graceful=False)
                    continue
                started = time.perf_counter()
                with link.lock:
                    link.yielded = kind
                    link.close()
                record = {"model": key[0], "kind": kind, "for_model": for_model, "requests": link.count,
                          "start_number": getattr(link, "start_number", None), "exit": link.process.poll(),
                          "close_seconds": round(time.perf_counter() - started, 3)}
                records.append(record)
                record_yield(link, record)
            except BaseException as exc:
                error = error or exc
            finally:
                ensure_down(link)
        if error is not None:
            raise error
    return records


def ensure_down(link):
    """A server taken out of _LINKS whose close failed is killed here: no process is left that close_all
    cannot reach."""
    if link.process.poll() is None:
        link.process.kill()
        try:
            link.process.wait(timeout=30)
        except Exception:
            pass


def record_yield(link, record):
    """The hand-back's record: in YIELDS first, then its telemetry event; a telemetry error is noted on
    the record and never stops the hand-back of the servers after it."""
    YIELDS.append(record)
    try:
        emit_yield(getattr(link, "run_context", None), record)
    except Exception as exc:
        record["telemetry_error"] = type(exc).__name__


def emit_yield(run_context, record):
    """One bounded telemetry event per hand-back: ids, counts and seconds only, never content."""
    if run_context is None:
        return
    import model_telemetry
    model_telemetry.emit(run_context, YIELD_EVENT, **record)


def on_server_card(device):
    """True when a load on `device` shares the server's card ("cuda" is the current card, the first)."""
    if not device:
        return False
    device = str(device)
    return (device + ":0" if device == "cuda" else device) == SERVER_DEVICE


class card_for:
    """Held around one model load: on the server's card it takes CARD_LOCK and hands the card back
    (yield_card) before the body runs; on the CPU or another card it does nothing."""

    def __init__(self, model, device):
        self.model, self.held = model, on_server_card(device)

    def __enter__(self):
        if self.held:
            CARD_LOCK.acquire()
            try:
                yield_card("transformers_load", self.model)
            except BaseException:
                self.__exit__(None, None, None)      # the one release, also on a failed hand-back
                raise
        return self

    def __exit__(self, *exc):
        if self.held:
            CARD_LOCK.release()
        return False


def retire(key, reason):
    """A started server the runner refuses (it loaded something other than what was sealed): closed, and
    never started again in this run."""
    with _LINKS_LOCK:
        _FAILED[key] = reason
        found = _LINKS.pop(key, None)
    if found is not None:
        found.broken = reason
        found.close(graceful=False)


def close_all():
    with _LINKS_LOCK:
        for link in _LINKS.values():
            link.close()
        _LINKS.clear()


import atexit  # noqa: E402

atexit.register(close_all)
