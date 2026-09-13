"""Shared backend and privacy arguments for human and server entry points."""

from __future__ import annotations


def resolve_backend_profile(value, *, legacy_default=False):
    """Validate a human choice, or preserve the direct server's legacy default.

    Desktop and wizard callers require an explicit value. Existing API clients
    retain the server contract: only the exact value 'local' selects Local.
    """
    if legacy_default:
        return "local" if value == "local" else "cloud"
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
