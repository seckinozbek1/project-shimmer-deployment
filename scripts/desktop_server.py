"""Owned server process for the desktop starter. No review is submitted here."""
from __future__ import annotations

import os
import sys
import threading


def serve() -> int:
    if not os.environ.get("SHIMMER_TOKEN_HASH"):
        print("Cannot start: no access token was configured.", file=sys.stderr)
        return 1
    import server
    import uvicorn

    app_server = uvicorn.Server(uvicorn.Config(
        server.app, host=server.HOST, port=server.PORT,
        log_level=server.LOG_LEVEL, access_log=False))

    def watch_owner():
        # A stop command or the owner's pipe closing (including owner crash)
        # ends this session. No detached server is intentionally left behind.
        sys.stdin.readline()
        app_server.should_exit = True

    watcher = threading.Thread(target=watch_owner, name="desktop-owner", daemon=True)
    watcher.start()
    try:
        app_server.run()
        return 0 if app_server.started else 1
    finally:
        if not server.shutdown_jobs():
            raise RuntimeError("Shimmer could not stop all of its review processes.")


if __name__ == "__main__":
    sys.exit(serve())
