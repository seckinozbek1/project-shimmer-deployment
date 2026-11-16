@echo off
REM Bootstrap only. The shared Python contract chooses the runtime executable.
set "SHIMMER_PYTHON="
for /f "delims=" %%P in ('py "%~dp0runtime_contract.py" --resolve --path-only 2^>nul') do set "SHIMMER_PYTHON=%%P"
if not defined SHIMMER_PYTHON for /f "delims=" %%P in ('python "%~dp0runtime_contract.py" --resolve --path-only 2^>nul') do set "SHIMMER_PYTHON=%%P"
if not defined SHIMMER_PYTHON (
    echo No Python 3.12 was found. Install Python 3.12 from python.org, then run this again.
    exit /b 1
)
exit /b 0
