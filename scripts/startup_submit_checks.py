"""Fixture-only proofs of the console's real submission and shutdown consumer.

No provider is called and no pipeline is launched. The fake child observes the
real argv, placed inputs and role-resolution result at the process boundary.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch


def _isolated_server(root):
    source = Path(__file__).with_name("server.py")
    spec = importlib.util.spec_from_file_location("shimmer_startup_test_server", source)
    server = importlib.util.module_from_spec(spec)
    # Server import performs restart recovery; confine its run scan AND its
    # orphan staging scan before executing any module-level code.
    with patch.dict(os.environ, {"SHIMMER_OUTPUT_DIR": str(root / "runs")}), \
            patch.object(tempfile, "gettempdir", return_value=str(root)):
        spec.loader.exec_module(server)
    server.ROOT = root
    server.CONTEXT_DIR = root / "input" / "context"
    server.CONTEXT_DIR.mkdir(parents=True)
    server.RUNS_DIR = root / "runs"
    server.AUTO_CLEAR = True
    server.MODE = "integrated"
    server.SENSITIVE = False
    return server


def _fixture(root):
    import intake_wizard
    source = root / "source"
    source.mkdir()
    files = {
        "sample.md": "# Synthetic document\n\nA labelled field is present.\n",
        "earlier.md": "# Synthetic earlier version\n\nA labelled field was present.\n",
        "reference.md": "# Synthetic reference\n\nReference material.\n",
        "review_conventions.md": "# Synthetic review rules\n\n## CONV-X01 [required]\nThe labelled field must be present.\n",
    }
    for name, content in files.items():
        (source / name).write_text(content, encoding="utf-8")
    assert intake_wizard.classify(source / "sample.md")[0] == "DOCUMENT"
    assert intake_wizard.classify(source / "review_conventions.md")[0] == "CONVENTIONS"
    assert intake_wizard.summarize_conventions([source / "review_conventions.md"])["rules"] > 0
    return files


class _FinishedChild:
    def __init__(self):
        self.returncode = 0
        self.stdout = iter(())

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode


def _exercise():
    from fastapi.testclient import TestClient
    import preflight
    import role_resolution
    with tempfile.TemporaryDirectory(prefix="shimmer_startup_submit_") as tmp:
        root = Path(tmp)
        server = _isolated_server(root)
        files = _fixture(root)
        access = secrets.token_urlsafe(24)
        headers = {"Authorization": "Bearer " + access}
        calls = []
        original_start = server._start_next_job
        server._start_next_job = lambda: None

        def child(argv, **kwargs):
            roles = role_resolution.resolve_review_roles(root)
            calls.append({
                "task": argv[argv.index("--task") + 1],
                "mode": argv[argv.index("--mode") + 1],
                "backend": argv[argv.index("--backend-profile") + 1],
                "question": argv[argv.index("--question") + 1] if "--question" in argv else "",
                "waivers": [flag for flag in ("--sensitivity-layer-inactive-override", "--no-redaction-override") if flag in argv],
                "targets": roles["targets"], "prior": roles["prior"],
                "grounding": roles["grounding"],
                "rules_present": (root / "input" / "conventions" / "review_conventions.md").is_file(),
            })
            return _FinishedChild()

        server.subprocess = SimpleNamespace(Popen=child, run=subprocess.run,
                                            PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT,
                                            TimeoutExpired=subprocess.TimeoutExpired)
        data = {"task": "review", "intake_mode": "standalone", "confirmed": "true",
                "sensitive": "false", "question": "Check this synthetic document.",
                "review_targets": json.dumps(["sample.md"]),
                "prior_files": json.dumps(["earlier.md"])}

        def post(**changes):
            upload = changes.pop("upload", files)
            return client.post("/submit", headers=headers, data=dict(data, **changes),
                               files=[("files", (name, content.encode(), "text/plain")) for name, content in upload.items()])

        with patch.dict(os.environ, {"SHIMMER_TOKEN_HASH": hashlib.sha256(access.encode()).hexdigest(),
                                     "SHIMMER_BACKEND_PROFILE": "local"}), \
                patch.object(preflight, "sensitive_readiness", return_value=(False, "Sensitive work requires the inactive privacy layer to be activated.")):
            client = TestClient(server.app)
            declined = post(confirmed="false")
            no_privacy = post(sensitive="")
            inactive = post(sensitive="true")
            before_jobs = len(server.JOBS)
            accepted = post()
            if accepted.status_code == 202:
                server._run_job(accepted.json()["run_id"])
            outcome = {"declined": declined.status_code, "no_privacy": no_privacy.status_code,
                       "inactive": inactive.status_code, "before_jobs": before_jobs,
                       "accepted": accepted.status_code, "calls": calls[:],
                       "cleaned": not role_resolution.manifest_path(server.CONTEXT_DIR).exists()
                                  and not (server.CONTEXT_DIR / "sample.md").exists()}
            # Native clients cannot bypass roles, filename safety or protected
            # operator instructions; integrated clients still hit the validator.
            outcome["bad_target"] = post(review_targets='["missing.md"]').status_code
            outcome["metadata"] = post(upload={"review_scope.json": "{}"}).status_code
            outcome["traversal"] = post(upload={"../outside.md": "text"}).status_code
            outcome["duplicate"] = client.post("/submit", headers=headers, data=data,
                files=[("files", ("sample.md", b"one")), ("files", ("SAMPLE.md", b"two"))]).status_code
            (server.CONTEXT_DIR / "sample.md").write_text("Existing operator document", encoding="utf-8")
            outcome["collision"] = post().status_code
            outcome["preserved"] = (server.CONTEXT_DIR / "sample.md").read_text() == "Existing operator document"
            (server.CONTEXT_DIR / "sample.md").unlink()
            role_resolution.write_manifest(server.CONTEXT_DIR, ["operator.md"], "operator")
            original = role_resolution.manifest_path(server.CONTEXT_DIR).read_bytes()
            outcome["manifest_conflict"] = post().status_code
            outcome["manifest_preserved"] = role_resolution.manifest_path(server.CONTEXT_DIR).read_bytes() == original
            role_resolution.manifest_path(server.CONTEXT_DIR).unlink()
            outcome["integrated_validation"] = post(intake_mode="integrated", review_targets="[]", prior_files="[]").status_code
            # Both tasks and both privacy outcomes reach the actual argument
            # boundary; activation is a fixture, never a production change.
            with patch.object(preflight, "sensitive_readiness", return_value=(True, "Fixture privacy layer active")), \
                    patch.dict(os.environ, {"SHIMMER_BACKEND_PROFILE": "cloud"}):
                accepted_draft = post(task="draft", sensitive="true", review_targets="[]", prior_files="[]", upload={})
                if accepted_draft.status_code == 202:
                    server._run_job(accepted_draft.json()["run_id"])
                outcome["draft"] = calls[-1] if accepted_draft.status_code == 202 else accepted_draft.status_code
            server._start_next_job = original_start
            server.shutdown_jobs()
            client.close()
        return outcome


def _valid(out):
    expected = {"declined": 400, "no_privacy": 400, "inactive": 409, "before_jobs": 0,
                "accepted": 202, "cleaned": True, "bad_target": 400, "metadata": 400,
                "traversal": 400, "duplicate": 400, "collision": 409, "preserved": True,
                "manifest_conflict": 409, "manifest_preserved": True, "integrated_validation": 400}
    if any(out.get(k) != value for k, value in expected.items()):
        return False
    if len(out["calls"]) != 1:
        return False
    call = out["calls"][0]
    return (call["task"] == "review" and call["backend"] == "local" and call["mode"] == "standalone"
            and call["targets"] == ["sample.md"] and call["prior"] == ["earlier.md"]
            and call["grounding"] == ["earlier.md", "reference.md"] and call["rules_present"]
            and len(call["waivers"]) == 2 and call["question"] == "Check this synthetic document."
            and out["draft"]["task"] == "draft" and out["draft"]["backend"] == "cloud"
            and out["draft"]["waivers"] == [] and out["draft"]["mode"] == "standalone")


def _shutdown_proof():
    with tempfile.TemporaryDirectory(prefix="shimmer_startup_stop_") as tmp:
        server = _isolated_server(Path(tmp))
        entered = threading.Event()
        finished = threading.Event()
        children = []

        class WaitingChild:
            returncode = None

            def __init__(self, *args, **kwargs):
                self.stdout = self.lines()
                children.append(self)
                entered.set()

            def lines(self):
                finished.wait(5)
                if not finished.is_set():
                    raise RuntimeError("fixture child did not receive a stop")
                return
                yield ""

            def poll(self):
                return self.returncode

            def terminate(self):
                self.returncode = -1
                finished.set()

            kill = terminate

            def wait(self, timeout=None):
                if not finished.wait(timeout):
                    raise subprocess.TimeoutExpired("fixture", timeout)
                return self.returncode

        server.subprocess = SimpleNamespace(Popen=WaitingChild, PIPE=subprocess.PIPE,
                                            STDOUT=subprocess.STDOUT, TimeoutExpired=subprocess.TimeoutExpired)
        for question in ("First synthetic question", "Second synthetic question"):
            server.JOBS.append({"run_id": server._new_run_id(), "status": "queued", "task": "draft",
                                "question": question, "submitted_at": server._now_iso()})
        server._start_next_job()
        assert entered.wait(3), "fixture worker did not start"
        assert server.shutdown_jobs(3), "shutdown did not finish"
        assert len(children) == 1 and children[0].poll() is not None
        assert not server._THREADS and not server._PROCS
        assert all(job["status"] == "cancelled" for job in server.JOBS)
        server._start_next_job()
        assert len(children) == 1, "shutdown started another queued review"


def _placement_preservation_proof():
    import role_resolution
    with tempfile.TemporaryDirectory(prefix="shimmer_startup_preserve_") as tmp:
        root = Path(tmp)
        server = _isolated_server(root)
        _fixture(root)
        existing = server.CONTEXT_DIR / "operator_reference.md"
        existing.write_text("Existing operator reference", encoding="utf-8")
        created = []
        server._place_standalone(root / "source", "review", ["sample.md"], ["earlier.md"], created)
        assert existing.name in role_resolution.read_manifest(server.CONTEXT_DIR)["grounding"]
        edited = server.CONTEXT_DIR / "sample.md"
        edited.write_text("Operator edited this after import", encoding="utf-8")
        server._clear_standalone(created)
        assert edited.read_text() == "Operator edited this after import"
        assert existing.read_text() == "Existing operator reference"
        # A manifest can change after queue acceptance. Worker revalidation
        # must refuse without deleting a draft/manifest it did not create.
        edited.unlink()
        memo = server.CONTEXT_DIR / "draft_memo_fixture.md"
        memo.write_text("Existing generated draft", encoding="utf-8")
        role_resolution.write_manifest(server.CONTEXT_DIR, [memo.name], "system_draft")
        original = role_resolution.manifest_path(server.CONTEXT_DIR).read_bytes()
        run_id = server._new_run_id()
        server.JOBS.append({"run_id": run_id, "status": "queued", "task": "review",
                            "sensitive": False, "native_intake": True, "intake_mode": "standalone",
                            "review_targets": ["sample.md"], "prior_files": ["earlier.md"]})
        server._STAGING[run_id] = root / "source"
        with patch.object(server.subprocess, "Popen", side_effect=AssertionError("review must not start")) as child:
            server._run_job(run_id)
            assert not child.called
        assert role_resolution.manifest_path(server.CONTEXT_DIR).read_bytes() == original
        assert memo.read_text() == "Existing generated draft"
        assert server.JOBS[0]["status"] == "failed"


def _recovery_proof():
    """Lost queued uploads and missing native staging never reach a child."""
    import role_resolution
    with tempfile.TemporaryDirectory(prefix="shimmer_startup_recovery_") as tmp:
        root = Path(tmp)
        server = _isolated_server(root)
        operator_file = server.CONTEXT_DIR / "operator_document.md"
        operator_file.write_text("Preserved operator content", encoding="utf-8")
        role_resolution.write_manifest(server.CONTEXT_DIR, [operator_file.name], "system_draft")
        manifest = role_resolution.manifest_path(server.CONTEXT_DIR)
        original_manifest = manifest.read_bytes()
        job = {"run_id": server._new_run_id(), "status": "queued", "task": "review",
               "sensitive": False, "native_intake": True, "intake_mode": "standalone",
               "review_targets": ["sample.md"], "prior_files": [], "files": ["sample.md"],
               "submitted_at": server._now_iso()}
        server._write_status(job)
        stale = root / ("ingest_" + job["run_id"] + "_fixture")
        stale.mkdir()
        (stale / "sample.md").write_text("Queued document", encoding="utf-8")
        assert json.loads(server._status_path(job["run_id"]).read_text())["status"] == "queued"
        assert not server._STAGING
        with patch.object(tempfile, "gettempdir", return_value=str(root)):
            server._rebuild_jobs_from_disk()
        disk = json.loads(server._status_path(job["run_id"]).read_text())
        assert server.JOBS[0]["status"] == disk["status"] == "interrupted"
        assert "submit" in disk["error"] and not stale.exists()
        assert operator_file.read_text() == "Preserved operator content"
        assert manifest.read_bytes() == original_manifest

        launched = []
        def child(argv, **kwargs):
            launched.append(argv)
            return _FinishedChild()
        with patch.object(server.subprocess, "Popen", side_effect=child):
            server._start_next_job()
            assert not launched and not server._THREADS
            # Both a lost map entry and a mapped but removed folder must fail
            # before document placement, process creation or unrelated cleanup.
            for staging in (None, root / "absent_staging"):
                missing = dict(job, run_id=server._new_run_id(), status="running")
                server.JOBS.append(missing)
                if staging is not None:
                    server._STAGING[missing["run_id"]] = staging
                server._run_job(missing["run_id"])
                assert missing["status"] == "failed" and "uploaded files are unavailable" in missing["error"]
                assert not launched
        assert operator_file.read_text() == "Preserved operator content"
        assert manifest.read_bytes() == original_manifest


def _recover_queue(server):
    server._rebuild_jobs_from_disk()


def _run_missing(server, run_id):
    server._run_job(run_id)


def _recovery_fixture(server, *, native):
    """A persisted accepted job; native upload loss is the declared fault."""
    marker = server.CONTEXT_DIR / "operator_reference.md"
    marker.write_text("Preserved synthetic operator reference", encoding="utf-8")
    job = {"run_id": server._new_run_id(), "status": "queued", "task": "review" if native else "draft",
           "question": "Summarize the synthetic reference.", "sensitive": False,
           "native_intake": native, "intake_mode": "standalone" if native else "integrated",
           "review_targets": ["sample.md"] if native else [], "prior_files": [],
           "files": ["sample.md"] if native else [], "submitted_at": server._now_iso()}
    server._write_status(job)
    return job, marker


def _valid_recovery_fixture(native):
    with tempfile.TemporaryDirectory(prefix="shimmer_recovery_valid_") as tmp:
        server = _isolated_server(Path(tmp))
        job, marker = _recovery_fixture(server, native=native)
        record = json.loads(server._status_path(job["run_id"]).read_text())
        return (record["status"] == "queued" and record["native_intake"] is native
                and record["files"] == record["review_targets"]
                and bool(record["question"]) and marker.is_file() and not server._STAGING)


def _observe_recovery(*, native=False):
    """Observe real queue drain or worker dispatch, with an inert child only."""
    with tempfile.TemporaryDirectory(prefix="shimmer_recovery_effect_") as tmp:
        root = Path(tmp)
        server = _isolated_server(root)
        server.AUTO_CLEAR = False
        job, marker = _recovery_fixture(server, native=native)
        original = marker.read_bytes()
        children = []
        def child(argv, **kwargs):
            children.append(argv)
            return _FinishedChild()
        server.subprocess = SimpleNamespace(Popen=child, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT,
                                            TimeoutExpired=subprocess.TimeoutExpired)
        if native:
            server.JOBS.append(job)
            _run_missing(server, job["run_id"])
            recovered = None
        else:
            with patch.object(tempfile, "gettempdir", return_value=str(root)):
                _recover_queue(server)
            recovered = server.JOBS[0]["status"]
            server._start_next_job()
            with server.JOBS_LOCK:
                workers = list(server._THREADS.values())
            for worker in workers:
                worker.join(5)
                if worker.is_alive():
                    raise AssertionError("fixture queue worker did not finish")
        result = {"recovered": recovered, "status": server.JOBS[0]["status"], "children": len(children),
                  "preserved": marker.read_bytes() == original,
                  "disk_status": json.loads(server._status_path(job["run_id"]).read_text())["status"]}
        if not server.shutdown_jobs():
            raise AssertionError("fixture server did not stop")
        return result


def _recovery_mutations():
    """Remove the actual guards while keeping fixture inputs and readers fixed."""
    import effect_proof
    def changed_function(original, branch):
        tree = ast.parse(inspect.getsource(original))
        if branch == "queued":
            target = next(node for node in ast.walk(tree)
                          if isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                          and isinstance(node.test.left, ast.Call)
                          and isinstance(node.test.left.func, ast.Attribute)
                          and isinstance(node.test.left.func.value, ast.Name)
                          and node.test.left.func.value.id == "job"
                          and any(isinstance(value, ast.Constant) and value.value == "queued"
                                  for value in node.test.comparators))
            target.test = ast.Constant(value=False)
        else:
            target = next(node for node in ast.walk(tree)
                          if isinstance(node, ast.If) and isinstance(node.test, ast.Name)
                          and node.test.id == "native_intake"
                          and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                                  and child.func.id == "_place_standalone" for child in ast.walk(node)))
            target.test = ast.BoolOp(op=ast.And(), values=[ast.Name(id="native_intake", ctx=ast.Load()),
                                                         ast.Name(id="staging", ctx=ast.Load())])
        ast.fix_missing_locations(tree)
        namespace = {}
        exec(compile(tree, "<startup recovery mutation>", "exec"), original.__globals__, namespace)
        return namespace[original.__name__]

    def leave_queued(server):
        changed_function(server._rebuild_jobs_from_disk, "queued")()

    def bypass_missing(server, run_id):
        changed_function(server._run_job, "missing")(run_id)

    def expected(result, native):
        status = "failed" if native else "interrupted"
        return (result["children"] == 0 and result["preserved"]
                and result["status"] == result["disk_status"] == status
                and (native or result["recovered"] == "interrupted"))

    proofs = []
    for native, hook, mutation, name in (
            (False, "_recover_queue", leave_queued, "recovered queued jobs do not drain without their uploads"),
            (True, "_run_missing", bypass_missing, "native missing uploads refuse before child dispatch")):
        observe = lambda native=native: _observe_recovery(native=native)
        verdict = lambda native=native, observe=observe: ("PASS" if expected(observe(), native) else "FAIL", "recovery consumer")
        proof = effect_proof.prove_effect(name=name,
            validate=lambda native=native: _valid_recovery_fixture(native), observe=observe, check=verdict,
            neutralise=lambda hook=hook, mutation=mutation: patch.dict(globals(), {hook: mutation}))
        if (proof["before"]["children"] != 0 or proof["mutated"]["children"] != 1
                or proof["restored"]["children"] != 0):
            raise AssertionError("recovery mutation did not change the child-dispatch boundary")
        proofs.append(proof)
    return proofs


def check():
    """Gate entry point, with an independently observed target-role mutation."""
    import effect_proof
    import role_resolution
    original = role_resolution.write_manifest

    def validate_inputs():
        with tempfile.TemporaryDirectory(prefix="shimmer_startup_valid_") as tmp:
            declared = _fixture(Path(tmp))
            return set(declared) == {"sample.md", "earlier.md", "reference.md", "review_conventions.md"}

    def no_targets(context_dir, targets, source, **kwargs):
        return original(context_dir, [], source, **kwargs)

    def verdict():
        return ("PASS", "real submission consumer") if _valid(_exercise()) else ("FAIL", "submission behavior changed")

    try:
        outcome = _exercise()
        if not _valid(outcome):
            return "FAIL", "startup submission fixture failed: " + json.dumps(outcome, sort_keys=True)
        _shutdown_proof()
        _placement_preservation_proof()
        _recovery_proof()
        _recovery_mutations()
        import draft_intake_checks
        draft_status, draft_detail = draft_intake_checks.check()
        if draft_status != "PASS":
            return draft_status, draft_detail
        effect_proof.prove_effect(name="operator targets reach role resolution",
            validate=validate_inputs, observe=_exercise, check=verdict,
            neutralise=lambda: patch.object(role_resolution, "write_manifest", no_targets))
    except Exception as exc:
        return "FAIL", "startup submission proof failed: " + type(exc).__name__
    return "PASS", "native intake, explicit confirmation/privacy, task/backend argv, Review/Draft role preservation, integrated validation, restart refusal and owned-worker shutdown; target, Draft and recovery mutations changed consumers and were killed/restored"


if __name__ == "__main__":
    result, detail = check()
    print(result + ": " + detail)
    raise SystemExit(0 if result == "PASS" else 1)
