"""Shared server address resolution for direct and desktop entry points."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ServerSettings:
    host: str
    port: int
    console_url: str


def resolve_server_settings(env=None, *, desktop=False):
    """Typed form used by the desktop process controller."""
    return ServerSettings(*server_endpoint(env, desktop=desktop))


def server_endpoint(env=None, *, desktop=False):
    """Return (bind host, port, console URL), without changing the environment.

    Direct-server parsing preserves its historical blank/invalid-port fallback.
    The desktop surface deliberately binds only to this computer, regardless of
    an inherited server host, and refuses invalid explicit ports before spawning.
    """
    env = os.environ if env is None else env
    raw = env.get("SHIMMER_PORT")
    if desktop and raw is not None and not raw.strip():
        raise ValueError("The console port must be a whole number from 1 to 65535.")
    if raw is None or not raw.strip():
        port = 8000
    else:
        try:
            port = int(raw.strip())
        except ValueError:
            if desktop:
                raise ValueError("The console port must be a whole number from 1 to 65535.") from None
            port = 8000
    if desktop and not 1 <= port <= 65535:
        raise ValueError("The console port must be a whole number from 1 to 65535.")
    host = "127.0.0.1" if desktop else env.get("SHIMMER_HOST", "0.0.0.0")
    browser_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    if ":" in browser_host and not browser_host.startswith("["):
        browser_host = "[" + browser_host + "]"
    return host, port, "http://%s:%d/console" % (browser_host, port)
