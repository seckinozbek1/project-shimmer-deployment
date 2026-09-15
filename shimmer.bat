@echo off
REM ===========================================================================
REM Project Shimmer master launcher (Windows). Takes you from a fresh clone to a
REM running review. One script, three entry paths: CLI review, chat, or server.
REM
REM ALL it does, in order: find Python, build/activate a local .venv, install
REM dependencies, run the readiness preflight (API keys + Qwen + models, reused
REM from scripts\preflight.py so nothing is duplicated), then show a plain menu.
REM
REM It never prints an API key value. The macOS/Linux twin is shimmer.sh.
REM ===========================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM --- 1. Resolve the shared runtime contract ------------------------------
call tools\resolve_python.bat
if errorlevel 1 goto :end_fail
set "PYTHON_CMD=!SHIMMER_PYTHON!"
echo Using Python: !PYTHON_CMD!

REM --- 2. Virtual environment (.venv in the repo root) -----------------------
if not exist ".venv\Scripts\activate.bat" (
    echo Creating a local virtual environment in .venv ...
    "!PYTHON_CMD!" -m venv .venv
    if errorlevel 1 (
        echo Failed to create the virtual environment. See the error above.
        goto :end_fail
    )
)
REM An existing incompatible venv is refused, never silently reused/rebuilt.
set "PYTHON_CMD="
for /f "delims=" %%P in ('"!SHIMMER_PYTHON!" tools\runtime_contract.py --resolve --candidate "%CD%\.venv\Scripts\python.exe" --path-only') do set "PYTHON_CMD=%%P"
if not defined PYTHON_CMD goto :end_fail
"!PYTHON_CMD!" tools\runtime_contract.py --source .
if errorlevel 1 goto :end_fail
call ".venv\Scripts\activate.bat"

REM --- 3. Dependencies -------------------------------------------------------
echo Installing dependencies (this is quick after the first run) ...
"!PYTHON_CMD!" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo Dependency installation failed. See the error above.
    goto :end_fail
)

REM --- 3b. CUDA torch swap (only when a GPU is present but torch is CPU-only) -
REM A bare `torch==2.5.1` from PyPI installs the CPU-only wheel, which makes the
REM local Qwen redactor run on CPU (slow). If a CUDA GPU is physically present
REM (nvidia-smi succeeds) but torch reports no CUDA, replace the CPU wheel with the
REM CUDA build. Exit codes from the probe: 0 = CUDA already available (skip),
REM 1 = torch present but CPU-only (swap if GPU present), 2 = torch absent (skip).
"!PYTHON_CMD!" -c "import importlib.util,sys; sys.exit(2) if importlib.util.find_spec('torch') is None else sys.exit(0 if __import__('torch').cuda.is_available() else 1)"
set "TORCHRC=!errorlevel!"
if "!TORCHRC!"=="1" (
    nvidia-smi >nul 2>&1
    if errorlevel 1 (
        echo No NVIDIA GPU detected by nvidia-smi; keeping the CPU-only torch build.
    ) else (
        echo A CUDA GPU is present but torch is CPU-only. Installing the CUDA build ^(large download, one time^) ...
        "!PYTHON_CMD!" -m pip install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
        if errorlevel 1 (
            echo CUDA torch install failed; continuing with CPU-only torch. Redaction will be slow.
        ) else (
            echo CUDA torch installed. The Qwen redactor will use the GPU.
        )
    )
)

REM --- 4. Backend profile ----------------------------------------------------
REM Asked BEFORE the preflight because it decides what readiness even means. A
REM local run uses the machine's own models and calls no provider, so cloud API
REM keys are irrelevant to it. The launcher used to run the cloud preflight
REM unconditionally and exit on its keyless code 2, so a local-only operator
REM could not reach the menu at all and never learned whether their local stack
REM was ready. The profile is passed to the preflight and to every run started
REM from this menu.
echo.
echo Which backend will you run on?
echo   [C] Cloud  (Claude / GPT via your API keys; costs money per run)
echo   [L] Local  (models on this machine; no provider is called, no API cost)
set "profile_choice="
set /p profile_choice="Choose [C/L, Enter for Cloud]: "
if /i "!profile_choice!"=="l" (set "BACKEND_PROFILE=local") else (set "BACKEND_PROFILE=cloud")
REM Exported so the intake wizard emits --backend-profile for it instead of
REM asking the same question twice. The wizard owns the flag (chat drives the
REM same wizard, so both entry paths get it from one place).
set "SHIMMER_BACKEND_PROFILE=!BACKEND_PROFILE!"
echo Backend profile: !BACKEND_PROFILE!

REM --- 5. Readiness preflight (reuses scripts\preflight.py) ------------------
REM preflight checks API keys (loaded from the external config, never the repo),
REM Qwen redaction reachability, the GPU, and live model ids. Exit codes:
REM   2 = no config / keys found (cloud profile only; cannot continue)
REM   1 = some check FAILED (review the bill of health, then decide)
REM   0 = ready
echo.
echo Running the readiness preflight ...
"!PYTHON_CMD!" -X utf8 scripts\preflight.py --backend-profile !BACKEND_PROFILE!
set "PREFLIGHT_RC=!errorlevel!"
if "!PREFLIGHT_RC!"=="2" (
    echo.
    echo Cannot continue: API keys / config were not found. Follow the
    echo instructions printed above, then run this script again.
    echo ^(A local run needs no API keys: restart and choose [L].^)
    goto :end_fail
)
if not "!PREFLIGHT_RC!"=="0" (
    echo.
    set "cont="
    set /p cont="Preflight reported issues above. Continue to the menu anyway? [y/N]: "
    if /i not "!cont!"=="y" goto :end_ok
)

REM --- 6. Menu ---------------------------------------------------------------
:menu
echo.
echo =========================================
echo   Project Shimmer
echo =========================================
echo   [1] Run a review (CLI)
echo   [2] Open the chat interface
echo   [3] Start the server
echo   [4] Run the verify gate
echo   [5] Import documents (set up files and cutoff, no run)
echo   [Q] Quit
echo.
set "choice="
set /p choice="Choose an option [1-5, Q]: "

if /i "!choice!"=="1" goto :opt_review
if /i "!choice!"=="2" goto :opt_chat
if /i "!choice!"=="3" goto :opt_server
if /i "!choice!"=="4" goto :opt_gate
if /i "!choice!"=="5" goto :opt_import
if /i "!choice!"=="Q" goto :end_ok
echo Not a valid choice. Please pick 1, 2, 3, 4, 5, or Q.
goto :menu

:opt_review
echo.
REM Two task modes: review an existing document, or draft a memo from a question.
set "TASKMODE="
set /p TASKMODE="What would you like to do? [R] Review existing documents  [D] Draft a memo from a question  [R/D]: "
if /i "!TASKMODE!"=="D" goto :opt_draft
REM The intake wizard scans/classifies/places documents, sets the cutoff, and
REM collects the run flags (mode, parallelism, caps). It writes the flags here;
REM a non-zero exit means the operator cancelled, so no run happens.
set "WIZ_FLAGS_FILE=%TEMP%\shimmer_review_flags.txt"
if exist "%WIZ_FLAGS_FILE%" del "%WIZ_FLAGS_FILE%"
"!PYTHON_CMD!" scripts\intake_wizard.py --emit-flags "%WIZ_FLAGS_FILE%"
if errorlevel 1 (
    echo Review setup cancelled. Returning to the menu.
    if exist "%WIZ_FLAGS_FILE%" del "%WIZ_FLAGS_FILE%"
    goto :menu
)
set "WIZ_FLAGS="
if exist "%WIZ_FLAGS_FILE%" set /p WIZ_FLAGS=<"%WIZ_FLAGS_FILE%"
if exist "%WIZ_FLAGS_FILE%" del "%WIZ_FLAGS_FILE%"
echo.
echo Running the review ...
echo (Add --help for all options.)
REM The wizard already emitted --backend-profile into WIZ_FLAGS (from
REM SHIMMER_BACKEND_PROFILE), so it is not repeated here.
"!PYTHON_CMD!" scripts\pipeline.py !WIZ_FLAGS! %*
goto :menu

:opt_draft
echo.
REM Draft mode skips document intake: the grounding is already in input/context/
REM (import it via [5] first if needed). The question is passed as one quoted
REM argument, so spaces are fine. Defaults to normal mode (no redaction).
set "DRAFTQ="
set /p DRAFTQ="Enter your question or brief for the memo: "
if "!DRAFTQ!"=="" (
    echo No question entered. Returning to the menu.
    goto :menu
)
echo.
echo Drafting a memo, then reviewing it ...
echo (Add --help for all options.)
REM The draft path ASKS the sensitivity question rather than answering it. It
REM used to hardcode both override flags, declaring every launcher draft
REM non-sensitive with no prompt, while the review path asked. A draft memo can
REM quote the same grounding corpus, so it is the same decision and it belongs
REM to the operator.
set "DRAFT_FLAGS_FILE=%TEMP%\shimmer_draft_flags.txt"
if exist "!DRAFT_FLAGS_FILE!" del "!DRAFT_FLAGS_FILE!"
"!PYTHON_CMD!" scripts\intake_wizard.py --mode-only --emit-flags "!DRAFT_FLAGS_FILE!"
if errorlevel 1 (
    echo Draft setup cancelled. Returning to the menu.
    if exist "!DRAFT_FLAGS_FILE!" del "!DRAFT_FLAGS_FILE!"
    goto :menu
)
set "DRAFT_FLAGS="
if exist "!DRAFT_FLAGS_FILE!" set /p DRAFT_FLAGS=<"!DRAFT_FLAGS_FILE!"
if exist "!DRAFT_FLAGS_FILE!" del "!DRAFT_FLAGS_FILE!"
echo.
echo Drafting a memo, then reviewing it ...
echo (Add --help for all options.)
"!PYTHON_CMD!" scripts\pipeline.py --task draft --question "!DRAFTQ!" !DRAFT_FLAGS! %*
goto :menu

:opt_import
echo.
"!PYTHON_CMD!" scripts\intake_wizard.py --import-only
goto :menu

:opt_chat
echo.
echo Opening the chat interface. Close its window to return here.
"!PYTHON_CMD!" scripts\chat.py
goto :menu

:opt_server
echo.
REM The launcher generates the token AND holds the hash, then starts the server
REM in the same step. It used to print the hash and send the operator away to set
REM it by hand before returning to this menu: a handshake the launcher can
REM complete itself, since it is the process that will start the server. The
REM token is printed once (it is the only copy; the server stores only its hash).
if "%SHIMMER_TOKEN_HASH%"=="" (
    echo No server access token is configured ^(SHIMMER_TOKEN_HASH is not set^).
    echo An open server would let anyone in, so one is required.
    set "gen="
    set /p gen="Generate one and start the server now? [Y/n]: "
    if /i "!gen!"=="n" (
        echo No token generated. The server was not started.
        goto :menu
    )
    echo.
    set "TOKEN_HASH_FILE=%TEMP%\shimmer_token_hash.txt"
    if exist "!TOKEN_HASH_FILE!" del "!TOKEN_HASH_FILE!"
    "!PYTHON_CMD!" -c "import secrets, hashlib, sys; t=secrets.token_hex(32); h=hashlib.sha256(t.encode()).hexdigest(); open(sys.argv[1],'w').write(h); print('Access token (shown ONCE, keep it private):'); print(); print('   ', t); print(); print('Send this token in the Authorization header: Bearer <token>')" "!TOKEN_HASH_FILE!"
    if errorlevel 1 (
        if exist "!TOKEN_HASH_FILE!" del "!TOKEN_HASH_FILE!"
        echo Could not generate a token. The server was not started.
        goto :menu
    )
    set /p SHIMMER_TOKEN_HASH=<"!TOKEN_HASH_FILE!"
    del "!TOKEN_HASH_FILE!"
    echo.
    echo Token configured for this session. The server stores only its hash.
)
REM A URL that actually serves something: the app registers no bare "/" handler,
REM so the host root with no path was a 404. Every console screen is at /console.
REM The port follows SHIMMER_PORT, which is where the server reads it from.
set "SHIMMER_UI_PORT=%SHIMMER_PORT%"
if "!SHIMMER_UI_PORT!"=="" set "SHIMMER_UI_PORT=8000"
echo Starting the server ...
echo   Console:  http://localhost:!SHIMMER_UI_PORT!/console
echo   Health:   http://localhost:!SHIMMER_UI_PORT!/health   ^(the only route with no token^)
echo   There is no page at / , the console is the entry point.
echo Press Ctrl+C to stop it and return here.
"!PYTHON_CMD!" scripts\server.py
goto :menu

:opt_gate
echo.
echo Running the verify gate ...
"!PYTHON_CMD!" -X utf8 scripts\verify_session1.py
goto :menu

:end_ok
echo.
echo Goodbye.
endlocal
exit /b 0

:end_fail
echo.
endlocal
exit /b 1
