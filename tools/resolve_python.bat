@echo off
REM Bootstrap only. The shared Python contract chooses the runtime executable.
set "SHIMMER_PYTHON="
for /f "delims=" %%P in ('py "%~dp0runtime_contract.py" --resolve --path-only 2^>nul') do set "SHIMMER_PYTHON=%%P"
if not defined SHIMMER_PYTHON for /f "delims=" %%P in ('python "%~dp0runtime_contract.py" --resolve --path-only 2^>nul') do set "SHIMMER_PYTHON=%%P"
if not defined SHIMMER_PYTHON (
    echo No compatible Python found. See tools/cloud_run/runtime.json.
    exit /b 1
)
exit /b 0
