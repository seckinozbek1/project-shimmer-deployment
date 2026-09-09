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

REM --- 1. Find Python (py -3.9 preferred, then python) -----------------------
set "PYTHON_CMD="
py -3.9 --version >nul 2>&1 && set "PYTHON_CMD=py -3.9"
if not defined PYTHON_CMD ( python --version >nul 2>&1 && set "PYTHON_CMD=python" )
if not defined PYTHON_CMD (
    echo.
    echo Could not find Python 3.9 or newer on this machine.
    echo Install it from https://www.python.org/downloads/ , make sure it is on
    echo your PATH, then run this script again.
    goto :end_fail
)
echo Using Python: !PYTHON_CMD!

REM --- 2. Virtual environment (.venv in the repo root) -----------------------
if not exist ".venv\Scripts\activate.bat" (
    echo Creating a local virtual environment in .venv ...
    !PYTHON_CMD! -m venv .venv
    if errorlevel 1 (
        echo Failed to create the virtual environment. See the error above.
        goto :end_fail
    )
)
call ".venv\Scripts\activate.bat"

REM --- 3. Dependencies -------------------------------------------------------
echo Installing dependencies (this is quick after the first run) ...
python -m pip install -r requirements.txt --quiet
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
python -c "import importlib.util,sys; sys.exit(2) if importlib.util.find_spec('torch') is None else sys.exit(0 if __import__('torch').cuda.is_available() else 1)"
set "TORCHRC=!errorlevel!"
if "!TORCHRC!"=="1" (
    nvidia-smi >nul 2>&1
    if errorlevel 1 (
        echo No NVIDIA GPU detected by nvidia-smi; keeping the CPU-only torch build.
    ) else (
        echo A CUDA GPU is present but torch is CPU-only. Installing the CUDA build ^(large download, one time^) ...
        python -m pip install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
        if errorlevel 1 (
            echo CUDA torch install failed; continuing with CPU-only torch. Redaction will be slow.
        ) else (
            echo CUDA torch installed. The Qwen redactor will use the GPU.
        )
    )
)

REM --- 4. Readiness preflight (reuses scripts\preflight.py) ------------------
REM preflight checks API keys (loaded from the external config, never the repo),
REM Qwen redaction reachability, the GPU, and live model ids. Exit codes:
REM   2 = no config / keys found (cannot continue)
REM   1 = some check FAILED (review the bill of health, then decide)
REM   0 = ready
echo.
echo Running the readiness preflight ...
python -X utf8 scripts\preflight.py
set "PREFLIGHT_RC=!errorlevel!"
if "!PREFLIGHT_RC!"=="2" (
    echo.
    echo Cannot continue: API keys / config were not found. Follow the
    echo instructions printed above, then run this script again.
    goto :end_fail
)
if not "!PREFLIGHT_RC!"=="0" (
    echo.
    set "cont="
    set /p cont="Preflight reported issues above. Continue to the menu anyway? [y/N]: "
    if /i not "!cont!"=="y" goto :end_ok
)

REM --- 5. Menu ---------------------------------------------------------------
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
python scripts\intake_wizard.py --emit-flags "%WIZ_FLAGS_FILE%"
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
python scripts\pipeline.py !WIZ_FLAGS! %*
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
python scripts\pipeline.py --task draft --question "!DRAFTQ!" --sensitivity-layer-inactive-override --no-redaction-override %*
goto :menu

:opt_import
echo.
python scripts\intake_wizard.py --import-only
goto :menu

:opt_chat
echo.
echo Opening the chat interface. Close its window to return here.
python scripts\chat.py
goto :menu

:opt_server
echo.
if "%SHIMMER_TOKEN_HASH%"=="" (
    echo No server access token is configured ^(SHIMMER_TOKEN_HASH is not set^).
    echo An open server would let anyone in, so one is required.
    set "gen="
    set /p gen="Generate a token now? [Y/n]: "
    if /i not "!gen!"=="n" (
        echo.
        python -c "import secrets, hashlib; t=secrets.token_hex(32); print('Token (share once, keep private):', t); print('Hash (set as SHIMMER_TOKEN_HASH):', hashlib.sha256(t.encode()).hexdigest())"
        echo.
        echo Copy the hash above and set it, then choose [3] again:
        echo     set SHIMMER_TOKEN_HASH=^<the hash^>
    )
    goto :menu
)
echo Starting the server on http://localhost:8000 ...
echo Press Ctrl+C to stop it and return here.
python scripts\server.py
goto :menu

:opt_gate
echo.
echo Running the verify gate ...
python -X utf8 scripts\verify_session1.py
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
