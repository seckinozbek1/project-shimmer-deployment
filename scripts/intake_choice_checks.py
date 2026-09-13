"""Execute wizard choice and confirm-before-write behavior on disposable inputs."""

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import effect_proof
import intake_wizard as wizard
import run_choices

_DOCUMENT_TEXT = "Plain fixture document.\n"
_ORIGINAL_SCOPE = '{"cutoff_date":"2001-01-01","scope_note":"preserve fixture"}'
_IMPORTED_SCOPE = '{"cutoff_date":"2002-01-01"}'
_PROPOSED_DATE = "2003-01-01"


def _declared_fixture_valid():
    from datetime import datetime
    dates = [json.loads(_ORIGINAL_SCOPE)["cutoff_date"],
             json.loads(_IMPORTED_SCOPE)["cutoff_date"], _PROPOSED_DATE]
    return (len(set(dates)) == 3 and bool(_DOCUMENT_TEXT.strip())
            and all(datetime.strptime(date, "%Y-%m-%d") for date in dates))


def _input(answers):
    pending = iter(answers)

    def read(_prompt):
        try:
            return next(pending)
        except StopIteration:
            raise EOFError from None
    return read


def mode_outcome(answers, *, profile="local", sensitive_ready=False):
    """Run the real mode-only writer; model readiness alone is a declared fixture."""
    with tempfile.TemporaryDirectory(prefix="shimmer_choice_") as directory:
        flags = Path(directory) / "flags.txt"
        with patch.dict(os.environ), patch("builtins.input", _input(answers)), \
                redirect_stdout(io.StringIO()), patch.object(wizard.preflight, "sensitive_readiness",
                    return_value=(sensitive_ready, "Declared privacy readiness fixture.")):
            if profile is None:
                os.environ.pop("SHIMMER_BACKEND_PROFILE", None)
            else:
                os.environ["SHIMMER_BACKEND_PROFILE"] = profile
            code = wizard.run_mode_only(str(flags))
        return {"exit_code": code, "flags_written": flags.is_file(),
                "flags": flags.read_text(encoding="utf-8").split() if flags.exists() else []}


def _import_outcome(confirm="n", *, full=False):
    with tempfile.TemporaryDirectory(prefix="shimmer_intake_") as directory:
        root = Path(directory) / "workspace"
        source = Path(directory) / "source"
        source.mkdir()
        root.mkdir()
        config = root / "config"
        config.mkdir()
        scope = config / "review_scope.json"
        scope.write_text(_ORIGINAL_SCOPE, encoding="utf-8")
        (source / "document.txt").write_text(_DOCUMENT_TEXT, encoding="utf-8")
        # An imported scope must not erase the pending explicit date after yes.
        (source / "review_scope.json").write_text(_IMPORTED_SCOPE, encoding="utf-8")
        flags = root / "flags.txt"
        answers = [str(source), _PROPOSED_DATE]
        if full:
            answers += ["1", "", ""]  # Normal, default parallelism and cap
        answers += ["p", confirm, "all"]
        before = {str(path.relative_to(root)): path.read_bytes()
                  for path in root.rglob("*") if path.is_file()}
        _require(_declared_fixture_valid()
                 and scope.read_text(encoding="utf-8") == _ORIGINAL_SCOPE
                 and (source / "document.txt").read_text(encoding="utf-8") == _DOCUMENT_TEXT,
                 "intake fixture was not as declared")
        with patch.object(wizard, "ROOT", root), patch.object(wizard, "SCOPE_PATH", scope), \
                patch.dict(os.environ, {"SHIMMER_BACKEND_PROFILE": "local"}), \
                patch("builtins.input", _input(answers)), redirect_stdout(io.StringIO()):
            code = wizard.run(str(flags), import_only=not full)
        after = {str(path.relative_to(root)): path.read_bytes()
                 for path in root.rglob("*") if path.is_file()}
        manifest = root / "input" / "context" / "_review_targets.json"
        return {"exit_code": code, "unchanged": before == after,
                "placed": (root / "input" / "context" / "document.txt").is_file(),
                "cutoff": json.loads(scope.read_text(encoding="utf-8"))["cutoff_date"],
                "flags": flags.read_text(encoding="utf-8").split() if flags.exists() else [],
                "manifest": json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else None}


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _proof(name, observe, expected, neutralise):
    def check_result():
        return ("PASS" if expected(observe()) else "FAIL", name)
    return effect_proof.prove_effect(name=name, validate=_declared_fixture_valid, observe=observe,
                                    check=check_result, neutralise=neutralise)


def check():
    try:
        normal = run_choices.privacy_flags(False)
        sensitive = run_choices.privacy_flags(True)
        _require(len(normal) == 2 and sensitive == [], "privacy argument contract changed")
        for profile in ("local", "cloud"):
            expected = ["--backend-profile", profile]
            result = mode_outcome(["1", "yes"], profile=profile)
            _require(result["exit_code"] == 0 and result["flags"] == expected + normal,
                     "explicit Normal did not reach emitted arguments")
            result = mode_outcome(["2", "yes"], profile=profile, sensitive_ready=True)
            _require(result["exit_code"] == 0 and result["flags"] == expected,
                     "ready Sensitive emitted a privacy waiver")
            result = mode_outcome(["2", "yes"], profile=profile)
            _require(result["exit_code"] == 1 and not result["flags_written"],
                     "unready Sensitive emitted runnable flags")
        for choice in ("", "invalid"):
            _require(mode_outcome([choice, "yes"])["exit_code"] == 1, "invalid privacy silently selected Normal")
            _require(mode_outcome([choice, "1", "yes"], profile=None)["exit_code"] == 1,
                     "invalid backend silently selected Cloud")
        _require(mode_outcome(["1", "yes"], profile="invalid")["exit_code"] == 1,
                 "invalid inherited backend silently selected Cloud")
        _require(mode_outcome(["2", "1", "yes"], profile=None)["flags"] ==
                 ["--backend-profile", "local"] + normal, "explicit backend prompt did not reach arguments")
        for confirm in ("n", "", "yodel"):
            outcome = mode_outcome(["1", confirm])
            _require(outcome["exit_code"] == 1 and not outcome["flags_written"], "unconfirmed draft emitted flags")
            outcome = _import_outcome(confirm)
            _require(outcome["exit_code"] == 1 and outcome["unchanged"], "declined import changed files or cutoff")
        success = _import_outcome("yes", full=True)
        _require(success["exit_code"] == 0 and success["placed"] and success["cutoff"] == "2003-01-01",
                 "confirmed import did not save files and explicit cutoff")
        _require(success["flags"] == ["--backend-profile", "local"] + normal,
                 "review choice did not reach its actual emitted flags")
        _require(success["manifest"] is not None, "confirmed review target was not written")

        _proof("privacy refusal reaches draft exit and flags",
               lambda: mode_outcome(["2", "yes"]),
               lambda outcome: outcome["exit_code"] == 1 and not outcome["flags_written"],
               lambda: patch.object(wizard, "_sensitive_flags", return_value=("Normal", normal)))
        _proof("shared privacy flags reach Sensitive draft arguments",
               lambda: mode_outcome(["2", "yes"], sensitive_ready=True),
               lambda outcome: outcome["exit_code"] == 0 and outcome["flags"] == ["--backend-profile", "local"],
               lambda: patch.object(wizard, "privacy_flags", return_value=normal))
        original_cutoff = wizard._explain_and_maybe_update_cutoff

        def eager_cutoff():
            proposal = original_cutoff()
            if proposal:
                wizard._write_cutoff(proposal)
            return proposal

        _proof("cutoff remains unchanged when import is declined", _import_outcome,
               lambda outcome: outcome["exit_code"] == 1 and outcome["unchanged"],
               lambda: patch.object(wizard, "_explain_and_maybe_update_cutoff", eager_cutoff))
        original_ask = wizard._ask

        def automatic_confirmation(prompt):
            response = original_ask(prompt)
            return "y" if prompt.startswith("Proceed?") and not response else response

        _proof("blank import confirmation writes nothing", lambda: _import_outcome(""),
               lambda outcome: outcome["exit_code"] == 1 and outcome["unchanged"],
               lambda: patch.object(wizard, "_ask", automatic_confirmation))
        return "PASS", ("wizard requires explicit backend/privacy and yes before writes; Sensitive refuses without waivers; "
                        "confirmed review and draft choices reach emitted arguments; four observed mutations restore")
    except effect_proof.ProofFailure as exc:
        return "FAIL", "wizard mutation: " + exc.category
    except AssertionError as exc:
        return "FAIL", str(exc)


if __name__ == "__main__":
    status, detail = check()
    print(status + ": " + detail)
    raise SystemExit(0 if status == "PASS" else 1)
