#!/usr/bin/env bash
# ===========================================================================
# Project Shimmer master launcher (macOS / Linux). Takes you from a fresh clone
# to a running review. One script, three entry paths: CLI review, chat, server.
#
# ALL it does, in order: find Python, build/activate a local .venv, install
# dependencies, run the readiness preflight (API keys + Qwen + models, reused
# from scripts/preflight.py so nothing is duplicated), then show a plain menu.
#
# It never prints an API key value. The Windows twin is shimmer.bat.
# ===========================================================================

set -u
cd "$(dirname "$0")"

# --- 1. Bootstrap discovery only; the contract selects the executable ------
PYTHON_CMD=""
for bootstrap in python3 python; do
    command -v "$bootstrap" >/dev/null 2>&1 || continue
    PYTHON_CMD=$("$bootstrap" tools/runtime_contract.py --resolve --path-only) && break
done
if [ -z "$PYTHON_CMD" ]; then
    echo "No compatible Python found. See tools/cloud_run/runtime.json." >&2
    exit 1
fi
echo "Using Python: $PYTHON_CMD"

# --- 2. Virtual environment (.venv in the repo root) -----------------------
if [ ! -f ".venv/bin/activate" ]; then
    echo "Creating a local virtual environment in .venv ..."
    if ! "$PYTHON_CMD" -m venv .venv; then
        echo "Failed to create the virtual environment. See the error above."
        exit 1
    fi
fi
PYTHON_CMD=$("$PYTHON_CMD" tools/runtime_contract.py --resolve --candidate "$PWD/.venv/bin/python" --path-only) || exit 1
"$PYTHON_CMD" tools/runtime_contract.py --source . || exit 1
# venv activate scripts can touch unset vars on older shells; relax nounset here.
set +u
# shellcheck disable=SC1091
. ".venv/bin/activate"
set -u

# --- 3. Dependencies -------------------------------------------------------
echo "Installing dependencies (this is quick after the first run) ..."
if ! "$PYTHON_CMD" -m pip install -r requirements.txt --quiet; then
    echo "Dependency installation failed. See the error above."
    exit 1
fi

# --- 3b. CUDA torch swap (only when a GPU is present but torch is CPU-only) -
# A bare `torch==2.5.1` from PyPI installs the CPU-only wheel, which makes the local
# Qwen redactor run on CPU (slow). If a CUDA GPU is physically present (nvidia-smi
# succeeds) but torch reports no CUDA, replace the CPU wheel with the CUDA build.
# Probe exit codes: 0 = CUDA already available (skip), 1 = torch present but CPU-only
# (swap if GPU present), 2 = torch absent (skip).
torch_rc=0
"$PYTHON_CMD" -c "import importlib.util,sys; sys.exit(2) if importlib.util.find_spec('torch') is None else sys.exit(0 if __import__('torch').cuda.is_available() else 1)" || torch_rc=$?
if [ "$torch_rc" -eq 1 ]; then
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
        echo "A CUDA GPU is present but torch is CPU-only. Installing the CUDA build (large download, one time) ..."
        if "$PYTHON_CMD" -m pip install "torch==2.5.1+cu121" --index-url https://download.pytorch.org/whl/cu121; then
            echo "CUDA torch installed. The Qwen redactor will use the GPU."
        else
            echo "CUDA torch install failed; continuing with CPU-only torch. Redaction will be slow."
        fi
    else
        echo "No NVIDIA GPU detected by nvidia-smi; keeping the CPU-only torch build."
    fi
fi

# --- 4. Backend profile ----------------------------------------------------
# Asked BEFORE the preflight because it decides what readiness even means. A
# local run uses the machine's own models and calls no provider, so cloud API
# keys are irrelevant to it. The launcher used to run the cloud preflight
# unconditionally and exit on its keyless code 2, so a local-only operator
# could not reach the menu at all and never learned whether their local stack
# was ready. The profile is passed to the preflight and to every run started
# from this menu.
echo
echo "Which backend will you run on?"
echo "  [C] Cloud  (Claude / GPT via your API keys; costs money per run)"
echo "  [L] Local  (models on this machine; no provider is called, no API cost)"
printf "Choose [C/L, Enter for Cloud]: "
read -r profile_choice
case "$profile_choice" in
    l|L) BACKEND_PROFILE="local" ;;
    *)   BACKEND_PROFILE="cloud" ;;
esac
# Exported so the intake wizard emits --backend-profile for it instead of asking
# the same question a second time. The wizard owns the flag (chat drives the same
# wizard, so both entry paths get it from one place).
export SHIMMER_BACKEND_PROFILE="$BACKEND_PROFILE"
echo "Backend profile: $BACKEND_PROFILE"

# --- 5. Readiness preflight (reuses scripts/preflight.py) ------------------
# preflight checks API keys (loaded from the external config, never the repo),
# Qwen redaction reachability, the GPU, and live model ids. Exit codes:
#   2 = no config / keys found (cloud profile only; cannot continue)
#   1 = some check FAILED (review the bill of health, then decide)
#   0 = ready
echo
echo "Running the readiness preflight ..."
"$PYTHON_CMD" -X utf8 scripts/preflight.py --backend-profile "$BACKEND_PROFILE"
PREFLIGHT_RC=$?
if [ "$PREFLIGHT_RC" -eq 2 ]; then
    echo
    echo "Cannot continue: API keys / config were not found. Follow the"
    echo "instructions printed above, then run this script again."
    echo "(A local run needs no API keys: restart and choose [L].)"
    exit 1
elif [ "$PREFLIGHT_RC" -ne 0 ]; then
    echo
    printf "Preflight reported issues above. Continue to the menu anyway? [y/N]: "
    read -r cont
    case "$cont" in
        y|Y) ;;
        *) exit 0 ;;
    esac
fi

# --- Server start, with a URL that actually serves something ---------------
# The launcher used to print the host root with no path, where NO route exists:
# the app registers no bare "/" handler, so the first thing an operator saw was
# a 404. Every console screen lives at /console, and /health is the one route
# that needs no token. The port follows SHIMMER_PORT rather than being
# hardcoded, since the server reads it from there.
_shimmer_start_server() {
    _port="${SHIMMER_PORT:-8000}"
    echo "Starting the server ..."
    echo "  Console:  http://localhost:${_port}/console"
    echo "  Health:   http://localhost:${_port}/health   (the only route with no token)"
    echo "  There is no page at / , the console is the entry point."
    echo "Press Ctrl+C to stop it and return here."
    "$PYTHON_CMD" scripts/server.py
}

# --- 6. Menu ---------------------------------------------------------------
while true; do
    echo
    echo "========================================="
    echo "  Project Shimmer"
    echo "========================================="
    echo "  [1] Run a review (CLI)"
    echo "  [2] Open the chat interface"
    echo "  [3] Start the server"
    echo "  [4] Run the verify gate"
    echo "  [5] Import documents (set up files and cutoff, no run)"
    echo "  [Q] Quit"
    echo
    printf "Choose an option [1-5, Q]: "
    read -r choice
    case "$choice" in
        1)
            # Two task modes: review an existing document, or draft a memo from a question.
            printf "What would you like to do? [R] Review existing documents  [D] Draft a memo from a question  [R/D]: "
            read -r taskmode
            case "$taskmode" in
                d|D)
                    # Draft mode skips document intake: grounding is already in
                    # input/context/ (import it via [5] first if needed). The question
                    # is one quoted argument, so spaces are fine. Normal mode default.
                    printf "Enter your question or brief for the memo: "
                    read -r draftq
                    if [ -z "$draftq" ]; then
                        echo "No question entered. Returning to the menu."
                    else
                        # The draft path ASKS the sensitivity question rather than
                        # answering it. It used to hardcode both override flags,
                        # declaring every launcher draft non-sensitive with no
                        # prompt, while the review path asked. A draft memo can
                        # quote the same grounding corpus, so it is the same
                        # decision and it belongs to the operator.
                        DRAFT_FLAGS_FILE="${TMPDIR:-/tmp}/shimmer_draft_flags.$$"
                        rm -f "$DRAFT_FLAGS_FILE"
                        if "$PYTHON_CMD" scripts/intake_wizard.py --mode-only \
                                --emit-flags "$DRAFT_FLAGS_FILE"; then
                            DRAFT_FLAGS=""
                            [ -f "$DRAFT_FLAGS_FILE" ] && DRAFT_FLAGS="$(cat "$DRAFT_FLAGS_FILE")"
                            rm -f "$DRAFT_FLAGS_FILE"
                            echo
                            echo "Drafting a memo, then reviewing it ..."
                            echo "(Add --help for all options.)"
                            # DRAFT_FLAGS word-splits into separate simple tokens.
                            # shellcheck disable=SC2086
                            "$PYTHON_CMD" scripts/pipeline.py --task draft --question "$draftq" \
                                $DRAFT_FLAGS "$@"
                        else
                            echo "Draft setup cancelled. Returning to the menu."
                            rm -f "$DRAFT_FLAGS_FILE"
                        fi
                    fi
                    ;;
                *)
                    # The intake wizard scans/classifies/places documents, sets the cutoff,
                    # and collects the run flags (mode, parallelism, caps). It writes the flags
                    # to a temp file; a non-zero exit means the operator cancelled, no run.
                    WIZ_FLAGS_FILE="${TMPDIR:-/tmp}/shimmer_review_flags.$$"
                    rm -f "$WIZ_FLAGS_FILE"
                    if "$PYTHON_CMD" scripts/intake_wizard.py --emit-flags "$WIZ_FLAGS_FILE"; then
                        WIZ_FLAGS=""
                        [ -f "$WIZ_FLAGS_FILE" ] && WIZ_FLAGS="$(cat "$WIZ_FLAGS_FILE")"
                        rm -f "$WIZ_FLAGS_FILE"
                        echo
                        echo "Running the review ..."
                        echo "(Add --help for all options.)"
                        # WIZ_FLAGS is intentionally unquoted: it word-splits into separate
                        # simple flag tokens (no spaces within any token).
                        # The wizard already emitted --backend-profile into
                        # WIZ_FLAGS (from SHIMMER_BACKEND_PROFILE), so it is not
                        # repeated here.
                        # shellcheck disable=SC2086
                        "$PYTHON_CMD" scripts/pipeline.py $WIZ_FLAGS "$@"
                    else
                        echo "Review setup cancelled. Returning to the menu."
                        rm -f "$WIZ_FLAGS_FILE"
                    fi
                    ;;
            esac
            ;;
        2)
            echo
            echo "Opening the chat interface. Close its window to return here."
            "$PYTHON_CMD" scripts/chat.py
            ;;
        3)
            echo
            # The launcher generates the token AND holds the hash, then starts the
            # server in the same step. It used to print the hash and send the
            # operator away to set it by hand before returning to this menu: a
            # handshake the launcher can complete itself, since it is the process
            # that will start the server. The token is printed once (it is the only
            # copy; the server stores only its hash) and the hash never needs to
            # pass through the terminal at all.
            if [ -z "${SHIMMER_TOKEN_HASH:-}" ]; then
                echo "No server access token is configured (SHIMMER_TOKEN_HASH is not set)."
                echo "An open server would let anyone in, so one is required."
                printf "Generate one and start the server now? [Y/n]: "
                read -r gen
                case "$gen" in
                    n|N)
                        echo "No token generated. The server was not started."
                        ;;
                    *)
                        echo
                        # Token to stdout for the operator, hash to a file the shell
                        # reads: the hash never goes through the terminal, and the
                        # token is shown once and never stored.
                        TOKEN_HASH_FILE="${TMPDIR:-/tmp}/shimmer_token_hash.$$"
                        rm -f "$TOKEN_HASH_FILE"
                        if "$PYTHON_CMD" -c "import secrets, hashlib, sys; t=secrets.token_hex(32); h=hashlib.sha256(t.encode()).hexdigest(); open(sys.argv[1],'w').write(h); print('Access token (shown ONCE, keep it private):'); print(); print('   ', t); print(); print('Send this token in the Authorization header: Bearer <token>')" "$TOKEN_HASH_FILE"; then
                            SHIMMER_TOKEN_HASH="$(cat "$TOKEN_HASH_FILE")"
                            export SHIMMER_TOKEN_HASH
                            rm -f "$TOKEN_HASH_FILE"
                            echo
                            echo "Token configured for this session. The server stores only its hash."
                            _shimmer_start_server
                        else
                            rm -f "$TOKEN_HASH_FILE"
                            echo "Could not generate a token. The server was not started."
                        fi
                        ;;
                esac
            else
                _shimmer_start_server
            fi
            ;;
        4)
            echo
            echo "Running the verify gate ..."
            "$PYTHON_CMD" -X utf8 scripts/verify_session1.py
            ;;
        5)
            echo
            "$PYTHON_CMD" scripts/intake_wizard.py --import-only
            ;;
        q|Q)
            echo
            echo "Goodbye."
            exit 0
            ;;
        *)
            echo "Not a valid choice. Please pick 1, 2, 3, 4, 5, or Q."
            ;;
    esac
done
