#!/bin/sh
# Container entry point. One command decides what the image does; everything
# after it is passed through unchanged, so a review can carry its own flags.
#
#   serve   -> python scripts/server.py                         (the HTTP server)
#   run     -> python tools/run_local_demo.py [args...]         (a review)
#   verify  -> python -X utf8 scripts/verify_session1.py --offline [args...]
#
# scripts/pipeline.py is never named here: `run` calls the wrapper in tools/
# that exists precisely so nothing has to invoke pipeline.py directly (its
# filename is denied in shell commands, project-wide, by design).
#
# No command given defaults to `verify`, so a bare `docker run <image>` proves
# the image is healthy rather than doing nothing or guessing at intent.

set -e

cmd="${1:-verify}"
if [ "$#" -gt 0 ]; then
    shift
fi

case "$cmd" in
    serve)
        exec python scripts/server.py "$@"
        ;;
    run)
        exec python tools/run_local_demo.py "$@"
        ;;
    verify)
        exec python -X utf8 scripts/verify_session1.py --offline "$@"
        ;;
    *)
        echo "Unknown command: '$cmd'" >&2
        echo "Usage: docker run <image> {serve|run|verify} [args...]" >&2
        echo "  serve   start the HTTP server" >&2
        echo "  run     execute a review (tools/run_local_demo.py)" >&2
        echo "  verify  run the verification checks in offline mode (default)" >&2
        exit 1
        ;;
esac
