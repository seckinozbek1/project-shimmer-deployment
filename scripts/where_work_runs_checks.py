"""Gate checks 502 and 503 (D-694 item 3, the 16 November 15:11 sweep): the product's no-internet rule and
where work runs are two rules, never mixed.

(a) The product rule (NO-WEB-LOCAL-A): under the local backend profile nothing in Shimmer sends anything to
the internet. (b) Where work runs (resources): the laptop or a rented Lambda machine, under the spending and
data rules. "Local" in (a) means inside Shimmer's own run with no internet access, never "on the laptop".

Check 502 runs `search_router.SearchRouter.search`, the one place web access is opened, as a run on a rented
Lambda instance sees itself: Linux, the loop instance's host name, the ubuntu home, the run root and model
cache on the persistent file system, and the runner's own variables (the seal attestation, the vLLM job). It
reuses check 316's network stand-ins (`web_access_checks`: urlopen, create_connection and connect record and
refuse; the ddgs package a recorder). Under the local profile (unset, `local`, empty or unknown) both a
may_use_web roster agent and a system caller must be refused with no non-local connection attempted; under
the cloud profile on the same machine every engine must be tried (a positive control: the refusal is the
profile's, not a side effect of the markers); and the profile, and whether the web is open, must come out
the same with and without the Lambda markers for every profile value. Neutralised: the rule opened on a
Lambda machine; the profile read from where the run executes; the rule closed for every profile.

Check 503 holds the same distinction on the sealed records: every tracked sealed Lambda bundle's manifest
(`docs/fix/ordinary_final_cloud_run*/execution_manifest.json`) seals `SHIMMER_BACKEND_PROFILE=local`, and with
each manifest's environment in force on a Lambda machine search() refuses. Neutralised: a manifest copy
sealed with `cloud` among them must be caught.

No network, no weights, temporary folders only."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path, PurePosixPath
from unittest.mock import patch

import search_router
import web_access_checks as wac

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
import declare_asset_copy  # noqa: E402  (the loop instance's declared mount lives in tools/)

MANIFESTS = sorted(ROOT.glob("docs/fix/ordinary_final_cloud_run*/execution_manifest.json"))
LAMBDA_HOST = "shimmer-loop-3daa1c3-0f562083"
# The environment imitates the loop instance. Its persistent file system is mounted at the declared
# declare_asset_copy.LOOP_MOUNT (the value the sealer and the runner use), the user's home is that mount's
# parent, and the run root, model cache, seal attestation and vLLM job sit under the mount. No machine path
# is written in scripts/ (check 21): it is read from the one place the instance layout is declared.
LAMBDA_MOUNT = PurePosixPath(declare_asset_copy.LOOP_MOUNT)
LAMBDA_HOME = LAMBDA_MOUNT.parent
LAMBDA_USER = LAMBDA_HOME.name
LAMBDA_RUN = LAMBDA_MOUNT / "runs" / "G1116_TIP_FULL"
LAMBDA_ENV = {
    "HOME": str(LAMBDA_HOME), "USER": LAMBDA_USER, "LOGNAME": LAMBDA_USER,
    "PWD": str(LAMBDA_RUN),
    "HF_HOME": str(LAMBDA_RUN / "hf_cache"),
    "HF_HUB_CACHE": str(LAMBDA_RUN / "hf_cache" / "hub"),
    "SHIMMER_SEAL_ATTESTATION": str(LAMBDA_MOUNT / "runs" / "S" / "seal_attestation.json"),
    "SHIMMER_VLLM_JOB": str(LAMBDA_RUN / "vllm_job"),
    "SSH_CONNECTION": "198.51.100.7 52144 192.0.2.10 22",
}
LOCAL_VALUES = (None, "local", "", "elsewhere", "Cloud")


@contextlib.contextmanager
def on_lambda():
    """The process as a run on a rented Lambda instance sees itself (where the work runs)."""
    with patch.dict(os.environ, LAMBDA_ENV), patch.object(sys, "platform", "linux"), \
            patch.object(socket, "gethostname", lambda: LAMBDA_HOST):
        yield


def _refused_everywhere(profile):
    """(non-local attempts, refusals, refusal events) for search() under `profile` on a Lambda machine."""
    with on_lambda():
        attempts, refusals, messages = wac._leg(search_router.SearchRouter, profile)
    return (wac._non_local(attempts), refusals,
            [m for m in messages if m.startswith("web_access_refused backend_profile=local")])


def proof_local_profile_refuses_on_lambda():
    """Under every local profile value, on a Lambda machine, both callers are refused, nothing is attempted."""
    for profile in LOCAL_VALUES:
        reached, refusals, events = _refused_everywhere(profile)
        assert not reached, f"profile {profile!r} on Lambda attempted {reached}"
        assert refusals == [wac.WEB_AGENT, "system"], f"profile {profile!r} on Lambda refused {refusals}"
        assert len(events) == 2, f"profile {profile!r} on Lambda logged {len(events)} refusal events"


def proof_cloud_profile_tries_on_lambda():
    """Positive control: on the same Lambda machine the cloud profile tries every engine (each refused by the
    stand-ins), so the local refusal above is the profile's and not a side effect of the markers."""
    with on_lambda():
        attempts, refusals, _ = wac._leg(search_router.SearchRouter, "cloud")
    hosts = {host for _, host in attempts}
    expected = {"records.example.org", "html.duckduckgo.com", "ddgs package"}
    assert not refusals and expected <= hosts, (refusals, sorted(hosts))


def proof_where_it_runs_never_moves_the_profile():
    """For every profile value the profile and the web rule read the same with and without the Lambda markers:
    where the work runs is no input to the product rule."""
    for profile in LOCAL_VALUES + ("cloud",):
        with patch.dict(os.environ):
            if profile is None:
                os.environ.pop("SHIMMER_BACKEND_PROFILE", None)
            else:
                os.environ["SHIMMER_BACKEND_PROFILE"] = profile
            laptop = (search_router.backend_profile(), search_router.web_access_open())
            with on_lambda():
                rented = (search_router.backend_profile(), search_router.web_access_open())
        assert laptop == rented, f"profile {profile!r}: laptop {laptop}, Lambda {rented}"
        assert laptop[1] is (profile == "cloud"), f"profile {profile!r}: web open is {laptop[1]}"


def _sealed_environments(paths):
    out = []
    for path in paths:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        out.append((Path(path).parent.name, dict(manifest.get("environment") or {})))
    return out


def proof_sealed_lambda_runs_are_local_profile_runs():
    """Every tracked sealed Lambda bundle seals the local profile, and with its environment in force on a
    Lambda machine search() refuses both callers with nothing attempted."""
    sealed = _sealed_environments(MANIFESTS)
    assert len(sealed) >= 1, "no sealed Lambda manifest found under docs/fix"
    for name, environment in sealed:
        assert environment.get("SHIMMER_BACKEND_PROFILE") == "local", \
            f"{name} seals SHIMMER_BACKEND_PROFILE={environment.get('SHIMMER_BACKEND_PROFILE')!r}"
        with patch.dict(os.environ, environment):
            reached, refusals, events = _refused_everywhere(environment["SHIMMER_BACKEND_PROFILE"])
        assert not reached and refusals == [wac.WEB_AGENT, "system"] and len(events) == 2, \
            f"{name}: under its sealed environment on Lambda: attempted {reached}, refused {refusals}"


PROOFS = {
    502: [proof_local_profile_refuses_on_lambda, proof_cloud_profile_tries_on_lambda,
          proof_where_it_runs_never_moves_the_profile],
    503: [proof_sealed_lambda_runs_are_local_profile_runs],
}

_open, _profile = search_router.web_access_open, search_router.backend_profile


def _patched(name, value):
    @contextlib.contextmanager
    def apply():
        with patch.object(search_router, name, value):
            yield
    return apply


@contextlib.contextmanager
def _a_cloud_manifest_among_them():
    global MANIFESTS
    saved = MANIFESTS
    with tempfile.TemporaryDirectory() as tmp:
        planted = Path(tmp) / "ordinary_final_cloud_run_planted" / "execution_manifest.json"
        planted.parent.mkdir()
        shutil.copyfile(saved[0], planted)
        manifest = json.loads(planted.read_text(encoding="utf-8"))
        manifest["environment"]["SHIMMER_BACKEND_PROFILE"] = "cloud"
        planted.write_text(json.dumps(manifest), encoding="utf-8")
        MANIFESTS = list(saved) + [planted]
        try:
            yield
        finally:
            MANIFESTS = saved


NEUTRALISE = {
    # the rule opened when the run executes on a Linux rented machine
    "proof_local_profile_refuses_on_lambda": _patched(
        "web_access_open", lambda profile=None: _open(profile) or sys.platform == "linux"),
    # the rule closed for every profile: the positive control must catch it
    "proof_cloud_profile_tries_on_lambda": _patched("web_access_open", lambda profile=None: False),
    # the profile read from where the run executes
    "proof_where_it_runs_never_moves_the_profile": _patched(
        "backend_profile", lambda: "cloud" if os.environ.get("HOME") == LAMBDA_ENV["HOME"] else _profile()),
    # a sealed Lambda bundle with the cloud profile among the records
    "proof_sealed_lambda_runs_are_local_profile_runs": _a_cloud_manifest_among_them,
}


def _fails(proof):
    with NEUTRALISE[proof.__name__]():
        try:
            proof()
        except AssertionError as exc:
            return str(exc)
    return None


def check(number):
    """(status, detail) for the gate."""
    notes = []
    for proof in PROOFS[number]:
        try:
            proof()
        except AssertionError as exc:
            return "FAIL", f"{proof.__name__}: {exc}"
        caught = _fails(proof)
        if caught is None:
            return "FAIL", f"{proof.__name__} still passes when neutralised; it proves nothing"
        try:
            proof()
        except AssertionError as exc:
            return "FAIL", f"{proof.__name__} after restoring: {exc}"
        notes.append(f"{proof.__name__} (neutralised: {caught[:90]})")
    what = {502: "on a Lambda machine (Linux, the loop host name, the file system run root, the runner's "
                 "variables) the local profile, unset, empty or unknown refuses both callers with 0 non-local "
                 "connections; the cloud profile there tries every engine; the profile and the web rule read "
                 "the same on the laptop and on Lambda",
            503: f"{len(MANIFESTS)} tracked sealed Lambda manifests seal the local profile and search() refuses "
                 "under each one's environment on Lambda"}[number]
    return "PASS", what + "; each proof neutralised, failed, restored, passed: " + " | ".join(notes)


if __name__ == "__main__":
    print(json.dumps(check(int(sys.argv[1]) if len(sys.argv) > 1 else 502)))
