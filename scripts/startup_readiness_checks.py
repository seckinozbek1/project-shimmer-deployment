"""Hermetic desktop-readiness proofs through the report and CLI consumers."""

from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import effect_proof
import preflight
import startup_settings


def _cli(profile="local"):
    output = io.StringIO()
    with redirect_stdout(output):
        code = preflight.main(["--check-startup", "--backend-profile", profile, "--json"])
    return {"exit_code": code, "report": json.loads(output.getvalue())}


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _proof(name, validate, observe, expected, neutralise):
    def verdict():
        return ("PASS" if expected(observe()) else "FAIL", name)
    return effect_proof.prove_effect(name=name, validate=validate, observe=observe,
                                    check=verdict, neutralise=neutralise)


def check():
    """No provider, subprocess, real model, GPU workload or operator-state write."""
    try:
        with tempfile.TemporaryDirectory(prefix="shimmer_startup_") as temporary:
            root = Path(temporary)
            first = root / "producer"
            second = root / "auditor"
            for snapshot in (first, second):
                snapshot.mkdir()
                (snapshot / "config.json").write_text('{"model_type":"fixture"}', encoding="utf-8")
                # Presence fixtures, never asserted to be executable weights.
                (snapshot / "model.safetensors").write_bytes(b"declared nonempty fixture")
                (snapshot / "tokenizer.json").write_text("{}", encoding="utf-8")
            models = {"fixture/producer": first, "fixture/auditor": second}
            profile = {"PROCESSOR": ("local_producer", "fixture/producer"),
                       "VERIFIER": ("local_auditor", "fixture/auditor")}
            model_calls = []
            config_calls = []

            def tokenizer(model, *, local_files_only):
                _require(local_files_only is True, "tokenizer attempted an online lookup")
                model_calls.append(model)
                location = models.get(model, Path(model))
                if not (location / "tokenizer.json").is_file():
                    raise OSError("declared absent tokenizer")
                return object()

            def load_keys():
                config_calls.append(True)
                return {name: object() for name in preflight._REQUIRED_KEYS}

            fake_agent = SimpleNamespace(_local_checkpoint_path=lambda name: str(models[name]),
                                         load_api_keys=load_keys)
            fake_redaction = SimpleNamespace(qwen_backend_status=lambda _: {
                "configured": True, "gpu": False, "model_id": "fixture/producer"})
            fake_layer = SimpleNamespace(is_active=lambda: False)
            fake_transformers = SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=tokenizer))
            modules = {name: SimpleNamespace() for name in (
                "fastapi", "uvicorn", "python_multipart", "torch", "accelerate",
                "bitsandbytes", "anthropic", "openai")}
            modules.update(agent_wrapper=fake_agent, redaction_gate=fake_redaction,
                           sensitivity_layer=fake_layer, transformers=fake_transformers,
                           pipeline=SimpleNamespace(_LOCAL_PROFILE=profile))
            with ExitStack() as stack:
                stack.enter_context(patch.dict(sys.modules, modules))
                forbidden = []

                def refuse(*args, **kwargs):
                    forbidden.append(True)
                    raise AssertionError("startup reached a forbidden operation")

                stack.enter_context(patch.object(socket, "create_connection", refuse))
                stack.enter_context(patch.object(subprocess, "Popen", refuse))
                for operation in ("step_config", "step_dependencies", "step_qwen", "step_models",
                                  "_pull_qwen_weights", "_attempt_lib_pull", "_scaffold_template"):
                    stack.enter_context(patch.object(preflight, operation, refuse))
                before = {str(path.relative_to(root)): path.read_bytes()
                          for path in root.rglob("*") if path.is_file()}
                result = _cli()
                _require(result["exit_code"] == 0 and result["report"]["ready"], "valid Local fixture refused")
                _require(not config_calls, "Local readiness loaded cloud credentials")
                _require(set(model_calls) == {str(first), str(second)}, "configured local models were not checked")
                _require(any(row["id"] == "gpu" and row["status"] == "WARN"
                             for row in result["report"]["checks"]), "absent GPU is not a soft warning")
                _require(result["report"]["sensitive_ready"] is False, "inactive Sensitive was advertised ready")
                after = {str(path.relative_to(root)): path.read_bytes()
                         for path in root.rglob("*") if path.is_file()}
                _require(before == after and not forbidden, "readiness mutated its inputs or started work")

                # A tokenizable snapshot with missing weights used to look ready.
                (second / "model.safetensors").unlink()
                _proof("missing weights reaches a failing startup exit",
                       lambda: (second / "tokenizer.json").is_file()
                       and not (second / "model.safetensors").exists(),
                       _cli, lambda observed: observed["exit_code"] == 1
                       and not observed["report"]["ready"],
                       lambda: patch.object(preflight, "_checkpoint_files_ready", return_value=True))
                (second / "model.safetensors").write_bytes(b"declared nonempty fixture")

                # Every referenced shard must exist. Restoring it restores readiness.
                (second / "model.safetensors.index.json").write_text(
                    '{"weight_map":{"fixture":"missing-shard.safetensors"}}', encoding="utf-8")
                _require(_cli()["exit_code"] == 1, "missing indexed shard passed")
                (second / "missing-shard.safetensors").write_bytes(b"declared shard fixture")
                _require(_cli()["exit_code"] == 0, "complete indexed shard fixture refused")

                # Package detection must alter what the launcher receives.
                with patch.dict(sys.modules, {"fastapi": None}):
                    _proof("broken server dependency reaches failing startup exit", lambda: sys.modules["fastapi"] is None,
                           _cli, lambda observed: observed["exit_code"] == 1,
                           lambda: patch.object(preflight, "_package_problems", return_value=[]))

                cloud = _cli("cloud")
                _require(cloud["exit_code"] == 0 and config_calls, "Cloud did not use existing key loader")
                _require(any(row["id"] == "cloud_models" and row["status"] == "WARN"
                             for row in cloud["report"]["checks"]), "live model approval was claimed verified")
                with patch.object(fake_agent, "load_api_keys", return_value={}):
                    _require(_cli("cloud")["exit_code"] == 1, "absent Cloud credentials passed")
                    _require(_cli("local")["exit_code"] == 0, "absent Cloud credentials blocked Local")

                def broken_config():
                    print("fixture private diagnostic")
                    print("fixture private diagnostic", file=sys.stderr)
                    raise RuntimeError("fixture private diagnostic")

                with patch.object(fake_agent, "load_api_keys", broken_config):
                    code = _cli("cloud")
                    _require(code["exit_code"] == 1, "unreadable config did not fail")
                    _require("fixture private diagnostic" not in json.dumps(code), "raw config content leaked")

                # The existing sensitivity switch changes the real CLI metadata.
                _proof("inactive privacy reaches the console metadata", lambda: fake_layer.is_active() is False,
                       lambda: _cli()["report"]["sensitive_ready"], lambda ready: ready is False,
                       lambda: patch.object(fake_layer, "is_active", return_value=True))
                with patch.object(fake_redaction, "qwen_backend_status", refuse):
                    _require(preflight.sensitive_readiness(root)[0] is False,
                             "inactive privacy failed its cheap health path")
                _require(not forbidden, "sensitive health imported a model probe while inactive")

                with patch.dict("os.environ", {"SHIMMER_BACKEND_PROFILE": "local"}):
                    ok, _ = preflight.check_local_model_availability()
                    _require(ok, "existing server availability contract broke")
                with patch.dict("os.environ", {"SHIMMER_BACKEND_PROFILE": "cloud"}):
                    _require(preflight.check_local_model_availability() == (True, "not in local mode"),
                             "cloud server availability started local checks")
                _require(not preflight.startup_report(None)["ready"], "missing backend silently selected one")

            for env, expected in (({}, ("0.0.0.0", 8000, "http://127.0.0.1:8000/console")),
                                  ({"SHIMMER_PORT": "bad"}, ("0.0.0.0", 8000, "http://127.0.0.1:8000/console")),
                                  ({"SHIMMER_HOST": "::1", "SHIMMER_PORT": " 8014 "},
                                   ("::1", 8014, "http://[::1]:8014/console"))):
                _require(startup_settings.server_endpoint(env) == expected, "legacy server endpoint changed")
            env = {"SHIMMER_HOST": "0.0.0.0", "SHIMMER_PORT": "8014"}
            resolved = startup_settings.resolve_server_settings(env, desktop=True)
            _require((resolved.host, resolved.port, resolved.console_url) ==
                     ("127.0.0.1", 8014, "http://127.0.0.1:8014/console"), "desktop endpoint is not local")
            _require(env["SHIMMER_HOST"] == "0.0.0.0", "endpoint mutated caller environment")
            for port in ("bad", "0", "65536", "-1", "", " "):
                try:
                    startup_settings.server_endpoint({"SHIMMER_PORT": port}, desktop=True)
                except ValueError:
                    pass
                else:
                    raise AssertionError("invalid desktop port accepted")
        return "PASS", ("read-only CLI checks chosen backend, dependencies, cached weight shards and privacy; "
                        "missing weights/dependencies/inactive privacy have observed mutation effects and restore; "
                        "GPU stays soft, config output stays private, server URL settings agree")
    except effect_proof.ProofFailure as exc:
        return "FAIL", "startup readiness mutation: " + exc.category
    except AssertionError as exc:
        return "FAIL", str(exc)


if __name__ == "__main__":
    status, detail = check()
    print(status + ": " + detail)
    raise SystemExit(0 if status == "PASS" else 1)
