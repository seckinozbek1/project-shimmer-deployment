"""Shared backend and privacy arguments for human and server entry points."""

from __future__ import annotations


def environment_profile(value):
    """The backend profile a SHIMMER_BACKEND_PROFILE value means (D-487 item 1).

    Unset means Local. Only the exact value 'cloud' selects Cloud; 'local', an
    empty value and any unknown value are Local, so nothing but an explicit
    'cloud' opens a provider path or the web (NO-WEB-LOCAL-A). The one rule for
    every reader of the variable: the pipeline (apply_backend_profile,
    _is_local_profile), the server (and the profile it passes to the child), the
    preflight, the search router, the intake wizard's preset, the role anchor in
    agent_wrapper, the claim extractor and the embedding device.
    """
    return "cloud" if value == "cloud" else "local"


def resolve_backend_profile(value, *, from_environment=False):
    """Validate a human choice, or read the environment's value.

    Desktop and wizard callers require an explicit value. A value read from
    SHIMMER_BACKEND_PROFILE (the direct server) follows environment_profile:
    unset is Local, only the exact value 'cloud' selects Cloud.
    """
    if from_environment:
        return environment_profile(value)
    if value not in ("local", "cloud"):
        raise ValueError("Choose Local or Cloud explicitly before continuing.")
    return value


def privacy_flags(sensitive):
    """Normal explicitly declares a non-sensitive run; Sensitive waives nothing."""
    if sensitive is True:
        return []
    if sensitive is False:
        return ["--sensitivity-layer-inactive-override", "--no-redaction-override"]
    raise ValueError("Choose Normal or Sensitive explicitly before continuing.")
