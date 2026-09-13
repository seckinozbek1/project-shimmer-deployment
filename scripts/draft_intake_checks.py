"""Prove native Draft references retain their declared role through phase 0."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import effect_proof
import pipeline
import role_resolution

_QUESTION = "Summarize supplied references"
_REFERENCE = "reference-2026.md"
_REFERENCE_TEXT = "Reference material supplied as grounding.\n"
_CUTOFF = "2025-01-01"
# Five-digit synthetic REF suffix, as in check 84: the memo fixture is undated,
# so its promotion must be caused by the manifest rather than a numeric citation.
_MEMO = "# Memo\n\nReference summary cites REF-TEST-00001.\n"
_NOW = "2026-09-13T12:00:00+00:00"


def _valid_fixture():
    # The reference must be recent enough to expose accidental cutoff promotion.
    from document_dating import date_from_filename, date_from_text
    return (date_from_filename(_REFERENCE) > _CUTOFF and bool(_REFERENCE_TEXT.strip())
            and "REF-TEST-00001" in _MEMO and date_from_text(_MEMO) is None
            and bool(_QUESTION.strip()))


def _observe(source="system_draft", *, generate_text=_MEMO):
    with tempfile.TemporaryDirectory(prefix="shimmer_draft_roles_") as temporary:
        root = Path(temporary)
        context = root / "input" / "context"
        context.mkdir(parents=True)
        config = root / "config"
        config.mkdir()
        (config / "review_scope.json").write_text(json.dumps({
            "cutoff_type": "date", "cutoff_date": _CUTOFF}), encoding="utf-8")
        reference = context / _REFERENCE
        reference.write_text(_REFERENCE_TEXT, encoding="utf-8")
        memo_name = pipeline._draft_memo_filename(_QUESTION)
        # Include the future memo name to prove it cannot remain forced grounding.
        role_resolution.write_manifest(context, [], source,
                                       grounding=[_REFERENCE, memo_name], now_iso=_NOW)
        initial = role_resolution.read_manifest(context)
        if (not _valid_fixture() or initial["targets"] != []
                or set(initial["grounding"]) != {_REFERENCE, memo_name}
                or reference.read_text(encoding="utf-8") != _REFERENCE_TEXT):
            raise AssertionError("draft role fixture was not as declared")
        original_manifest = role_resolution.manifest_path(context).read_bytes()
        calls = []

        def retrieve(question):
            if question != _QUESTION:
                raise AssertionError("phase 0 changed the operator question")
            calls.append("retrieve")
            return [{"ref_id": "REF-TEST-00001", "text": _REFERENCE_TEXT}]

        def generate(stable, dynamic):
            if _QUESTION not in dynamic or "REF-TEST-00001" not in stable:
                raise AssertionError("the declared grounding did not reach the draft prompt")
            calls.append("generate")
            return generate_text

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            memo = pipeline.run_draft_phase0(root, _QUESTION, retrieve=retrieve,
                                             generate=generate, now_iso=_NOW)
            if memo is None:
                return {"memo": None, "calls": calls,
                        "manifest_unchanged": role_resolution.manifest_path(context).read_bytes() == original_manifest,
                        "reference_unchanged": reference.read_text(encoding="utf-8") == _REFERENCE_TEXT}
            manifest = role_resolution.read_manifest(context)
            forced_targets, forced_grounding = pipeline._forced_roles(manifest)
            grounding, operational = pipeline._populate_operational(root, None, mode="standalone")
            placed = sorted(path.name for path in (root / "input" / "operational").iterdir()
                            if path.is_file())
            cleared = role_resolution.clear_system_draft(context)
        return {"memo": memo.name, "calls": calls,
                "forced_targets": sorted(forced_targets), "forced_grounding": sorted(forced_grounding),
                "grounding": sorted(record["filename"] for record in grounding),
                "operational": sorted(record["filename"] for record in operational),
                "placed": placed, "cleanup_cleared": cleared,
                "memo_removed": not memo.exists(),
                "reference_unchanged": reference.read_text(encoding="utf-8") == _REFERENCE_TEXT}


def _expected(result):
    return (result["calls"] == ["retrieve", "generate"]
            and result["forced_targets"] == [result["memo"]]
            and result["forced_grounding"] == [_REFERENCE]
            and result["grounding"] == [_REFERENCE]
            and result["operational"] == [result["memo"]]
            and result["placed"] == [result["memo"]]
            and result["cleanup_cleared"] and result["memo_removed"]
            and result["reference_unchanged"])


def _collision_outcome(*, late=False):
    with tempfile.TemporaryDirectory(prefix="shimmer_draft_collision_") as temporary:
        root = Path(temporary)
        context = root / "input" / "context"
        context.mkdir(parents=True)
        memo_path = context / pipeline._draft_memo_filename(_QUESTION)
        role_resolution.write_manifest(context, [], "system_draft", grounding=[memo_path.name], now_iso=_NOW)
        original_manifest = role_resolution.manifest_path(context).read_bytes()
        if not late:
            memo_path.write_text(_REFERENCE_TEXT, encoding="utf-8")
            if memo_path.read_text(encoding="utf-8") != _REFERENCE_TEXT:
                raise AssertionError("collision fixture file was not as declared")
        calls = []

        def retrieve(question):
            calls.append("retrieve")
            return []

        def generate(stable, dynamic):
            calls.append("generate")
            if late:
                memo_path.write_text(_REFERENCE_TEXT, encoding="utf-8")
            return _MEMO

        diagnostics = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(diagnostics):
            result = pipeline.run_draft_phase0(root, _QUESTION, retrieve=retrieve,
                                               generate=generate, now_iso=_NOW)
        return {"refused": result is None, "calls": calls,
                "source_preserved": memo_path.read_text(encoding="utf-8") == _REFERENCE_TEXT,
                "manifest_preserved": role_resolution.manifest_path(context).read_bytes() == original_manifest,
                "human_error": "Draft cannot start" in diagnostics.getvalue()}


def check():
    """Run phase 0 with injected retrieval/generation, then real role consumers."""
    try:
        original_writer = role_resolution.write_manifest

        def drop_grounding(context, targets, source, **kwargs):
            # Neutralise the generated memo manifest only, preserving the input
            # fixture and every downstream reader. This reproduces the old writer.
            if source == "system_draft" and targets:
                kwargs.pop("grounding", None)
            return original_writer(context, targets, source, **kwargs)

        def verdict():
            return ("PASS" if _expected(_observe()) else "FAIL", "native Draft roles")

        effect_proof.prove_effect(
            name="Draft grounding survives generated memo manifest", validate=_valid_fixture,
            observe=_observe, check=verdict,
            neutralise=lambda: patch.object(role_resolution, "write_manifest", drop_grounding))
        original_exists = Path.exists

        def hide_collision(path):
            return False if path.name == pipeline._draft_memo_filename(_QUESTION) else original_exists(path)

        def collision_verdict():
            outcome = _collision_outcome()
            okay = (outcome["refused"] and not outcome["calls"] and outcome["source_preserved"]
                    and outcome["manifest_preserved"] and outcome["human_error"])
            return ("PASS" if okay else "FAIL", "draft collision refuses before work")

        effect_proof.prove_effect(
            name="existing Draft output refuses before retrieval or generation", validate=_valid_fixture,
            observe=_collision_outcome, check=collision_verdict,
            neutralise=lambda: patch.object(Path, "exists", hide_collision))
        late = _collision_outcome(late=True)
        if (not late["refused"] or late["calls"] != ["retrieve", "generate"]
                or not late["source_preserved"] or not late["manifest_preserved"]):
            return "FAIL", "a Draft filename collision during generation overwrote operator input"
        # This propagation is specific to native run-scoped Draft declarations;
        # older direct phase-0 treatment of other manifest provenance is unchanged.
        other = _observe(source="operator")
        if _REFERENCE not in other["operational"] or other["forced_grounding"]:
            return "FAIL", "phase 0 reinterpreted an unrelated operator manifest"
        empty = _observe(generate_text=" ")
        if (empty["memo"] is not None or not empty["manifest_unchanged"]
                or not empty["reference_unchanged"]):
            return "FAIL", "failed draft generation changed the declared input roles"
        return "PASS", ("native Draft references stay grounding after phase 0 while only the memo is reviewed; "
                        "actual operational copies prove the role, dropping grounding changes them, restoration passes; "
                        "filename collisions preserve input/manifest and refuse before work, early-refusal mutation restores; "
                        "cleanup preserves references and unrelated manifest behavior is unchanged")
    except effect_proof.ProofFailure as exc:
        return "FAIL", "draft role mutation: " + exc.category
    except AssertionError as exc:
        return "FAIL", str(exc)


if __name__ == "__main__":
    status, detail = check()
    print(status + ": " + detail)
    raise SystemExit(0 if status == "PASS" else 1)
