"""Operator preflight / setup bootstrap for Project Shimmer.

Desktop mode (--check-startup) uses the non-mutating startup_report API and
bypasses every setup step below. It never installs, downloads, contacts a
provider, creates a key template, or records a privacy waiver.

Double-clicked via setup.bat (or a future setup.sh / setup.command — each a thin
wrapper that only launches this module). ALL real logic lives here so the OS
launchers stay trivial and cross-platform.

What it does, in order, printing a clear pass/fail line for each step:
  (a) locate + load the external config (API keys) via the documented resolution
      order; if none is found, scaffold a clearly-marked template at the expected
      location, print exactly what to fill, and FAIL cleanly (never fabricate keys);
  (b) install beautifulsoup4 + langdetect if missing, then confirm they import;
  (c) Qwen reachability — REUSES the existing INFRA-035 gate
      (redaction_gate.qwen_backend_status); deploy-if-missing with a bounded pull
      attempt; if still unreachable, refuse to silently bypass — require an
      explicit per-run operator override that is logged to the governance ledger;
  (d) GPU soft check — REUSES the same gate's GPU probe; warns on absent / CPU-only
      torch; never blocks, never records;
  (e) live models.list() per provider (REUSES model_registry) — reports the exact
      Claude producer and GPT auditor model ids, confirms none are deprecated,
      confirms gpt-4o is present, and lists any stronger reasoning-grade auditor as
      an APPROVAL CANDIDATE only. Never swaps a model.

It NEVER prints an API-key value (only present / absent), never runs the paid
pipeline, and never edits a tracked file. It ends with an honest readiness bill of
health that separates what is ready now from what stays UNPROVEN until a paid run.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import importlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from run_choices import resolve_backend_profile

# scripts/ is sys.path[0] when launched as `python scripts/preflight.py`, so the
# sibling framework modules import by bare name (same convention as pipeline.py).
# Optional application dependencies load inside the operation that needs them.
# In particular the desktop JSON check must survive a partially installed Python.


class _QuietStream(io.StringIO):
    def reconfigure(self, **kwargs):
        pass


@contextmanager
def _quiet_readiness():
    """Keep imported diagnostics and external-config output out of the report.

    No exception text from a key file is safe to print. Disabling bytecode also
    prevents the key resolver's Python import from writing beside operator keys.
    """
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        with redirect_stdout(_QuietStream()), redirect_stderr(_QuietStream()):
            yield
    finally:
        sys.dont_write_bytecode = previous


def _package_problems(names):
    problems = []
    with _quiet_readiness():
        for name in names:
            try:
                __import__(name)
            except Exception:
                problems.append(name)
    return problems


def _local_model_ids():
    # This is the real resolved profile, including operator local_models.json.
    # Importing the server here would create its queue and runtime directories.
    with _quiet_readiness():
        from pipeline import _LOCAL_PROFILE
    return sorted(set(model for _, model in _LOCAL_PROFILE.values()))


def check_local_model_availability():
    """Keep the direct server's original package/tokenizer availability contract."""
    if os.environ.get("SHIMMER_BACKEND_PROFILE") != "local":
        return True, "not in local mode"
    missing = _package_problems(("torch", "transformers"))
    if missing:
        return False, "; ".join(name + " is not installed or cannot import" for name in missing)
    try:
        model_ids = _local_model_ids()
    except Exception:
        return False, "The configured local model profile could not be read. Repair the Python environment."
    problems = []
    with _quiet_readiness():
        transformers = importlib.import_module("transformers")
        for model_id in model_ids:
            try:
                transformers.AutoTokenizer.from_pretrained(model_id, local_files_only=True)
            except Exception:
                problems.append("model %s not found in local cache" % model_id)
    if problems:
        return False, "; ".join(problems)
    return True, "packages ok, models cached: %s" % model_ids


def _checkpoint_files_ready(model_id):
    """Read the real loader's offline snapshot, tokenizer and weight-file set.

    This is presence checking, never a model load, conversion or integrity claim.
    An index that references absent/empty shards is not an available checkpoint.
    """
    try:
        with _quiet_readiness():
            import agent_wrapper
            snapshot = Path(agent_wrapper._local_checkpoint_path(model_id))
            config = json.loads((snapshot / "config.json").read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                return False
            index = next((snapshot / name for name in
                          ("model.safetensors.index.json", "pytorch_model.bin.index.json")
                          if (snapshot / name).is_file()), None)
            if index:
                weight_map = json.loads(index.read_text(encoding="utf-8")).get("weight_map")
                if not isinstance(weight_map, dict) or not weight_map:
                    return False
                files = set(weight_map.values())
            else:
                files = {name for name in ("model.safetensors", "pytorch_model.bin")
                         if (snapshot / name).is_file()}
            if not files:
                return False
            for name in files:
                # Hub snapshots link to blobs outside snapshots/. Validate the
                # declared relative filename, then follow the cache's own link.
                if (not isinstance(name, str) or Path(name).is_absolute()
                        or Path(name).drive or ".." in Path(name).parts):
                    return False
                candidate = snapshot / name
                if not candidate.is_file() or candidate.stat().st_size == 0:
                    return False
            transformers = importlib.import_module("transformers")
            transformers.AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True)
        return True
    except Exception:
        return False


def sensitive_readiness(project_root=None):
    """Report the existing Sensitive gates without activating or waiving them.

    The inactive-layer fast path is safe for a server health request. Full
    redaction rule compilation and model execution remain pipeline checks.
    """
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parent.parent
    try:
        with _quiet_readiness():
            import sensitivity_layer
            if not sensitivity_layer.is_active():
                return False, ("Sensitive cannot start because the required LAW-IV privacy layer is inactive. "
                               "It requires operator activation; do not submit sensitive documents.")
            import redaction_gate
            status = redaction_gate.qwen_backend_status(root)
        if not status.get("configured"):
            return False, "Sensitive cannot start because the local redaction backend is unavailable. Complete its setup first."
        if _package_problems(("accelerate", "bitsandbytes")):
            return False, "Sensitive cannot start because local model-loading packages are missing or broken. Complete its setup first."
        if not _checkpoint_files_ready(status.get("model_id")):
            return False, "Sensitive cannot start because the configured local redaction model is not fully cached. Complete its setup first."
    except Exception:
        return False, "Sensitive readiness could not be checked. Repair the Python environment before submitting sensitive documents."
    return True, ("Privacy layer active and local redaction files present. The pipeline still checks operator redaction "
                  "rules and actual model execution before accepting a Sensitive run.")


def startup_report(profile):
    """Non-mutating readiness for an explicitly selected desktop backend.

    No install, template creation, download, provider call, waiver or run starts
    here. A ready console is not evidence of a successful review or model load.
    """
    checks = []

    def add(identifier, status, message, detail=""):
        checks.append({"id": identifier, "status": status, "message": message, "detail": detail})

    try:
        profile = resolve_backend_profile(profile)
    except ValueError:
        add("backend", "FAIL", "Choose Local or Cloud before starting Shimmer.")
        return {"ready": False, "backend_profile": profile, "checks": checks,
                "sensitive_ready": False, "sensitive_detail": "Choose a backend first."}
    missing = _package_problems(("fastapi", "uvicorn", "python_multipart"))
    add("server", "FAIL" if missing else "PASS",
        "The console needs missing or broken Python packages. Complete the prerequisite setup, then try again."
        if missing else "Python environment ready for the operator console.",
        ", ".join(missing) if missing else "fastapi, uvicorn, python-multipart imported")
    if profile == "local":
        missing = _package_problems(("torch", "transformers", "accelerate", "bitsandbytes"))
        add("local_packages", "FAIL" if missing else "PASS",
            "Local model packages are missing or broken. Complete the local prerequisite setup, then try again."
            if missing else "Local model packages are available.", ", ".join(missing))
        if not missing:
            try:
                model_ids = _local_model_ids()
            except Exception:
                add("local_models", "FAIL", "Local model settings could not be loaded. Repair the Python environment and local model configuration.")
            else:
                available = bool(model_ids) and all(_checkpoint_files_ready(model_id) for model_id in model_ids)
                add("local_models", "PASS" if available else "FAIL",
                    "Required local model files and tokenizers are cached." if available else
                    "A required local model is missing or incomplete. Complete model setup before starting.",
                    ", ".join(model_ids) + "; actual model loading and available memory remain unverified")
        add("credentials", "PASS", "Local was selected. Cloud credentials are not required or checked.")
    else:
        missing = _package_problems(("anthropic", "openai"))
        add("cloud_packages", "FAIL" if missing else "PASS",
            "Cloud provider packages are missing or broken. Complete the prerequisite setup, then try again."
            if missing else "Cloud provider packages are available.", ", ".join(missing))
        presence = {}
        try:
            with _quiet_readiness():
                import agent_wrapper
                loaded = agent_wrapper.load_api_keys()
                presence = {name: bool(loaded.get(name)) and loaded.get(name) != placeholder
                            for name, placeholder in zip(_REQUIRED_KEYS,
                                ("PUT_YOUR_ANTHROPIC_KEY_HERE", "PUT_YOUR_OPENAI_KEY_HERE"))}
                del loaded
        except Exception:
            pass
        available = all(presence.get(name, False) for name in _REQUIRED_KEYS)
        add("credentials", "PASS" if available else "FAIL",
            "Required Cloud credentials are present." if available else
            "Cloud needs readable Anthropic and OpenAI credentials in the external key configuration. Complete setup, then try again.",
            "; ".join(name + ": " + ("present" if presence.get(name) else "absent") for name in _REQUIRED_KEYS))
        add("cloud_models", "WARN", "Live cloud model availability and operator approval are checked when you start a task. No provider was contacted.")
    try:
        with _quiet_readiness():
            import redaction_gate
            gpu = redaction_gate.qwen_backend_status(Path(__file__).resolve().parent.parent).get("gpu", False)
    except Exception:
        gpu = False
    add("gpu", "PASS" if gpu else "WARN",
        "CUDA GPU available." if gpu else "A CUDA GPU is unavailable or could not be checked. Local work can be very slow on CPU; this warning does not block startup.")
    sensitive_ok, sensitive_detail = sensitive_readiness()
    add("sensitive", "PASS" if sensitive_ok else "WARN", sensitive_detail)
    add("scope", "WARN", "Startup checks do not run a review, load generation models, or verify all document-specific dependencies. Task and privacy decisions remain in the console.")
    return {"ready": not any(check["status"] == "FAIL" for check in checks),
            "backend_profile": profile, "checks": checks,
            "sensitive_ready": sensitive_ok, "sensitive_detail": sensitive_detail}


# --- tiny report helpers -------------------------------------------------------

_RESULTS: "list[tuple[str, str]]" = []  # (status, line) for the final tally


def _emit(status: str, msg: str) -> None:
    """Print one status line and record it for the closing bill of health."""
    print(f"[{status:>5}] {msg}")
    _RESULTS.append((status, msg))


def _ok(msg: str) -> None: _emit("PASS", msg)
def _warn(msg: str) -> None: _emit("WARN", msg)
def _fail(msg: str) -> None: _emit("FAIL", msg)
def _info(msg: str) -> None: print(f"        {msg}")


def _section(title: str) -> None:
    print()
    print(f"=== {title} ===")


# Tracked the same way the rest of the codebase tracks key names: ANTHROPIC /
# OPENAI required, BRAVE optional. Mirrors load_api_keys' allowlist.
_REQUIRED_KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")
_OPTIONAL_KEYS = ("BRAVE_API_KEY",)

_CONFIG_TEMPLATE = '''\
# Project Shimmer -- external API key file. NEVER commit this file.
#
# It is resolved at runtime by scripts/agent_wrapper.py in this order:
#   1. $SHIMMER_CONFIG_PATH   2. ../api_keys/config.py   3. .env_path pointer
#
# This file holds API KEYS ONLY. Any `model = ...` line here is IGNORED by the
# key reader; model selection is owned solely by config/agent_registry.json.
# Replace each placeholder below with your real key, then re-run setup.

ANTHROPIC_API_KEY = "PUT_YOUR_ANTHROPIC_KEY_HERE"
OPENAI_API_KEY = "PUT_YOUR_OPENAI_KEY_HERE"
BRAVE_API_KEY = "PUT_YOUR_BRAVE_KEY_HERE"   # optional, free tier; leave as-is if unused
'''


def _truthy(val: "str | None") -> bool:
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"} if val else False


# --- step (a): config + keys ---------------------------------------------------

def step_config() -> dict:
    """Locate + load the external config. Scaffold a template and FAIL cleanly if
    none is found. Returns the loaded keys dict (empty only on the FAIL path,
    where main() stops)."""
    import agent_wrapper
    _section("(a) Config + API keys")
    for src, path in agent_wrapper.candidate_config_paths():
        marker = "<- FOUND" if path.exists() else "(absent)"
        _info(f"candidate [{src}]: {path}  {marker}")

    target = agent_wrapper.resolve_config_path()
    if target is None:
        expected = agent_wrapper.project_root().parent / agent_wrapper.CONFIG_DIRNAME / agent_wrapper.CONFIG_FILENAME
        scaffolded = _scaffold_template(expected)
        _fail(f"no config found via any resolution method.")
        if scaffolded:
            _info(f"scaffolded a template at: {expected}")
            _info("Fill it in (real key values), then re-run setup:")
        else:
            _info(f"expected config location: {expected}")
            _info("Create it (or point $SHIMMER_CONFIG_PATH at it) with:")
        for k in _REQUIRED_KEYS:
            _info(f"    {k} = \"<your key>\"   (required)")
        for k in _OPTIONAL_KEYS:
            _info(f"    {k} = \"<your key>\"   (optional)")
        _info("Keys live OUTSIDE the repo and are never committed.")
        return {}

    keys = agent_wrapper.load_api_keys()
    _ok(f"config loaded from: {target}")
    # Report presence only -- NEVER a key value.
    all_present = True
    for k in _REQUIRED_KEYS:
        present = bool(keys.get(k))
        (_ok if present else _fail)(f"  {k}: {'present' if present else 'ABSENT (required)'}")
        all_present = all_present and present
    for k in _OPTIONAL_KEYS:
        present = bool(keys.get(k))
        _info(f"  {k}: {'present' if present else 'absent (optional)'}")
    if not all_present:
        _info("Required keys missing -- live model checks below will be skipped where keyless.")
    return keys


def _scaffold_template(expected: Path) -> bool:
    """Write the placeholder template at `expected` if nothing is there. Returns
    True if a file was written. Never overwrites an existing file; never writes a
    real key (placeholders only)."""
    try:
        if expected.exists():
            return False
        expected.parent.mkdir(parents=True, exist_ok=True)
        expected.write_text(_CONFIG_TEMPLATE, encoding="utf-8")
        return True
    except OSError as e:
        _info(f"could not scaffold template ({e}); create it manually.")
        return False


# --- step (b): pip dependencies ------------------------------------------------

def step_dependencies() -> None:
    """Install beautifulsoup4 + langdetect if missing; confirm they import."""
    _section("(b) Python dependencies (beautifulsoup4, langdetect)")
    # (pip distribution name, importable module name)
    wanted = [("beautifulsoup4", "bs4"), ("langdetect", "langdetect")]
    for dist, mod in wanted:
        if importlib.util.find_spec(mod) is not None:
            _ok(f"{dist} already installed (import {mod} OK)")
            continue
        _info(f"{dist} missing -- installing into {Path(sys.executable).name} ...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dist],
                                  stdout=sys.stdout, stderr=sys.stderr)
        except (subprocess.CalledProcessError, OSError) as e:
            _fail(f"{dist} install failed: {e}")
            continue
        importlib.invalidate_caches()
        if importlib.util.find_spec(mod) is not None:
            _ok(f"{dist} installed and import {mod} confirmed")
        else:
            _fail(f"{dist} installed but import {mod} still fails")


# --- step (c): Qwen reachability (reuses INFRA-035 gate) ------------------------

def step_qwen() -> dict:
    """Reuse redaction_gate.qwen_backend_status. Deploy-if-missing with a bounded
    pull attempt; if still unreachable, require a logged per-run override rather
    than silently bypassing. Returns the final status dict (carries gpu flag for
    step d)."""
    import agent_wrapper
    import redaction_gate
    import sensitivity_layer
    _section("(c) Qwen redaction backend (reuses INFRA-035 gate)")
    root = agent_wrapper.project_root()
    qstat = redaction_gate.qwen_backend_status(root)

    if qstat["configured"]:
        _ok(f"Qwen reachable: {qstat['detail']}")
        _info(f"verified now: {qstat['verified_now']}")
        _info(f"deferred to first call (unproven until paid run): {qstat['verified_at_first_call']}")
        if _truthy(os.environ.get("SHIMMER_QWEN_PULL")):
            _pull_qwen_weights(qstat.get("model_id"))
        return qstat

    # Unreachable -> deploy-if-missing: bounded pull of the missing gate libraries.
    _warn(f"Qwen not reachable yet: {qstat['detail']}")
    if qstat["missing_libs"]:
        _attempt_lib_pull(qstat["missing_libs"])
        qstat = redaction_gate.qwen_backend_status(root)  # re-check after the pull

    if qstat["configured"]:
        _ok(f"Qwen deployed and now reachable: {qstat['detail']}")
        return qstat

    # Still unreachable. Never silently bypass: require an explicit, logged override.
    if _truthy(os.environ.get("SHIMMER_REDACTION_OVERRIDE")):
        run_id = "preflight-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        ledger = sensitivity_layer.record_redaction_waiver(root, run_id, reason="qwen_unavailable")
        _warn("Qwen unreachable; operator override ACCEPTED and LOGGED. The next run will "
              "proceed with NO redaction (per-run only).")
        _info(f"waiver written to governance ledger: {ledger}")
    else:
        _fail(f"Qwen unreachable after pull attempt: {qstat['detail']}. Refusing to silently bypass.")
        _info("Either set up the backend (install torch + transformers and the model "
              "Qwen/Qwen2.5-7B-Instruct),")
        _info("or re-run with SHIMMER_REDACTION_OVERRIDE=1 to log a per-run redaction waiver "
              "and proceed without redaction.")
    return qstat


def _attempt_lib_pull(missing_libs) -> None:
    """Best-effort 'deploy' of the gate libraries the Qwen backend needs. torch is
    intentionally NOT force-installed here (its build is CUDA/platform-specific and
    a wrong pip wheel can break the environment) — it is reported for the operator."""
    for lib in missing_libs:
        if lib == "torch":
            _info("torch is missing — NOT auto-installing (CUDA/platform-specific build). "
                  "Install the correct torch wheel for your machine, then re-run.")
            continue
        _info(f"attempting to install {lib} ...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib],
                                  stdout=sys.stdout, stderr=sys.stderr)
        except (subprocess.CalledProcessError, OSError) as e:
            _info(f"{lib} install failed: {e}")


def _pull_qwen_weights(model_id) -> None:
    """Opt-in (SHIMMER_QWEN_PULL=1) pre-stage of the Qwen weights so the first
    redaction call does not pay the download. Heavy (multi-GB) — off by default."""
    if not model_id or importlib.util.find_spec("huggingface_hub") is None:
        _info("weight pre-pull skipped (no model id, or huggingface_hub not installed).")
        return
    _info(f"SHIMMER_QWEN_PULL set — pre-staging weights for {model_id} (may be large) ...")
    try:
        hf = importlib.import_module("huggingface_hub")
        hf.snapshot_download(model_id)
        _info("weights pre-staged.")
    except Exception as e:  # network / auth / disk — best effort only
        _info(f"weight pre-pull did not complete: {e} (will download at first call).")


# --- step (d): GPU soft check (reuses the same gate) ----------------------------

def step_gpu(qstat: dict) -> None:
    """Soft reminder only — reuses qstat['gpu'] (torch.cuda.is_available()). Never
    blocks, never records."""
    _section("(d) GPU soft check (soft reminder only)")
    if not importlib.util.find_spec("torch"):
        _warn("torch not importable — cannot probe GPU. Redaction will be CPU-bound if/when it runs.")
        return
    if qstat.get("gpu"):
        _ok("CUDA GPU available — redaction will use the GPU.")
    else:
        _warn("no CUDA GPU detected (absent or CPU-only torch) — redaction will run on CPU and be "
              "slow. Soft reminder only; never blocks, never recorded.")


# --- step (e): live model resolution (reuses model_registry) -------------------

# Heuristic markers of OpenAI reasoning-grade auditor models, used ONLY to surface
# approval CANDIDATES. Nothing is ever swapped automatically.
_REASONING_MARKERS = ("o1", "o3", "o4", "gpt-5", "reason")


def step_models(keys: dict) -> None:
    """Live models.list() per provider via model_registry. Self-resolves each
    configured FAMILY KEY to the concrete live id (exactly-one match -> bind), and
    reports the firewall outcome (zero / ambiguous -> operator approval). Confirms
    gpt-4o present, lists stronger reasoning-grade auditor candidates. NEVER swaps."""
    import agent_wrapper
    import model_registry
    _section("(e) Live model resolution (reuses model_registry; binds family keys, never swaps)")
    root = agent_wrapper.project_root()
    registry = json.loads((root / "config" / "agent_registry.json").read_text(encoding="utf-8"))
    agents = registry.get("agents", {})

    producer = sorted({s.get("model") for s in agents.values() if s.get("backend") == "claude_api"})
    auditor = sorted({s.get("model") for s in agents.values() if s.get("backend") == "openai_api"})
    _info(f"Claude producer family keys (config/agent_registry.json): {', '.join(producer)}")
    _info(f"GPT auditor family keys   (config/agent_registry.json): {', '.join(auditor)}")

    claude_live = model_registry.list_available_models("claude_api", keys)
    openai_live = model_registry.list_available_models("openai_api", keys)

    _resolve_backend("claude_api (producer)", producer, claude_live)
    _resolve_backend("openai_api (auditor)", auditor, openai_live)

    # gpt-4o specifically must be present + acceptable for the auditor role.
    if openai_live is None:
        _warn("gpt-4o presence UNVERIFIED — OpenAI live list unavailable (no key / SDK / network).")
    elif "gpt-4o" in openai_live:
        _ok("gpt-4o present in the live OpenAI list and acceptable as the auditor model.")
    else:
        _fail("gpt-4o NOT present in the live OpenAI list — the auditor model is unavailable.")

    # Stronger reasoning-grade auditor candidates — reported for operator approval
    # via the existing INFRA-026 model-gate. NOT swapped here.
    if openai_live:
        cands = sorted(m for m in openai_live
                       if any(mk in m.lower() for mk in _REASONING_MARKERS))
        if cands:
            _info("approval CANDIDATES (stronger reasoning-grade auditors, NOT swapped): "
                  + ", ".join(cands[:12]) + (" ..." if len(cands) > 12 else ""))
            _info("To adopt one, change config/agent_registry.json and approve via the "
                  "model-gate (INFRA-026). Preflight never swaps a model.")
        else:
            _info("no stronger reasoning-grade auditor candidate detected in the live list.")


def _resolve_backend(label: str, family_keys, live) -> None:
    """Report self-resolution of each configured family key against the live list."""
    import model_registry
    if live is None:
        _warn(f"{label}: resolution UNVERIFIED (live list unavailable — no key / SDK / network). "
              f"Configured: {', '.join(family_keys)}")
        return
    for key in family_keys:
        status, resolved, candidates = model_registry.resolve_model_id(key, live)
        if status == "exact":
            _ok(f"{label}: {key!r} present as-is (already a concrete live id).")
        elif status == "bound":
            _ok(f"{label}: {key!r} -> {resolved!r} (auto-resolved; exactly one live match).")
        elif status == "deprecated":
            _fail(f"{label}: {key!r} has ZERO live matches (gone/deprecated) — firewall: the "
                  f"run-time model-gate STOPS until the operator approves a replacement.")
        elif status == "ambiguous":
            _fail(f"{label}: {key!r} is AMBIGUOUS — multiple live snapshots {candidates}; firewall: "
                  f"operator must pin one in agent_registry.json. Never auto-picked.")


# --- closing bill of health ----------------------------------------------------

def bill_of_health() -> None:
    _section("Readiness bill of health")
    passes = sum(1 for s, _ in _RESULTS if s == "PASS")
    warns = sum(1 for s, _ in _RESULTS if s == "WARN")
    fails = sum(1 for s, _ in _RESULTS if s == "FAIL")
    print(f"Tally: PASS={passes}  WARN={warns}  FAIL={fails}")
    print()
    if fails:
        print("NOT READY — resolve the FAIL lines above before a paid run.")
    elif warns:
        print("READY WITH CAVEATS — the WARN lines above are non-blocking but real.")
    else:
        print("Structurally ready (no blocking failures).")

    print()
    print("Still UNPROVEN until an actual paid pipeline run (cannot be verified here):")
    print("  - Live producer->auditor calls (real Claude->GPT cross-family audit round-trip).")
    print("  - Real prompt-cache savings (Claude explicit / GPT structured caching, INFRA-036).")
    print("  - Arabic / RTL handling on a real document (direction-aware detection + output).")
    print("  - Actual Qwen weight download + GPU placement at first redaction call.")
    print("These are NOT green yet by design — they require spending on a real run to confirm.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Project Shimmer operator preflight (no paid run, no key value printed)")
    parser.add_argument("--backend-profile", choices=["cloud", "local"], default=None,
                        help="which backend the operator intends to run under. cloud "
                             "(default) requires the API keys and checks live model ids. "
                             "local runs on the machine's own models and never calls a "
                             "provider, so missing cloud keys are reported and are not a "
                             "stop: the local readiness checks below are what matter.")
    parser.add_argument("--check-startup", action="store_true",
                        help="read-only desktop readiness; no installation, downloads, provider calls or state writes")
    parser.add_argument("--json", action="store_true", help="return the startup report as JSON")
    args = parser.parse_args(argv)
    if args.json and not args.check_startup:
        parser.error("--json requires --check-startup")
    if args.check_startup:
        report = startup_report(args.backend_profile)
        if args.json:
            print(json.dumps(report))
        else:
            for row in report["checks"]:
                print("[%s] %s" % (row["status"], row["message"]))
                if row["detail"]:
                    print("  " + row["detail"])
        return 0 if report["ready"] else 1
    args.backend_profile = args.backend_profile or "cloud"
    local = args.backend_profile == "local"

    print("Project Shimmer -- operator preflight")
    print("(no paid pipeline is run; no API-key value is ever printed)")
    print(f"backend profile: {args.backend_profile}")

    keys = step_config()
    if not keys and not local:
        # Config missing or required keys absent: stop before live model calls.
        bill_of_health()
        return 2

    step_dependencies()
    qstat = step_qwen()
    step_gpu(qstat)
    if local:
        # A local run reaches no provider, so there are no live model ids to read
        # and no key to read them with. Saying so is the point: preflight used to
        # exit 2 here and the operator never learned whether the LOCAL stack was
        # ready, which is the only stack a local run uses.
        _info("local profile: provider model ids are not checked (no provider is called).")
        if not keys:
            _info("no API keys were found. A local run does not need them; a cloud run does.")
    else:
        step_models(keys)
    bill_of_health()

    return 1 if any(s == "FAIL" for s, _ in _RESULTS) else 0


if __name__ == "__main__":
    sys.exit(main())
