@echo off
setlocal
cd /d "%~dp0"
echo Opening Start Shimmer. Use its window to start and stop the console.
py -3.9 --version >nul 2>&1
if not errorlevel 1 (
    py -3.9 -X utf8 scripts\desktop_launcher.py %*
    goto :finished
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -X utf8 scripts\desktop_launcher.py %*
    goto :finished
)
python --version >nul 2>&1
if not errorlevel 1 (
    python -X utf8 scripts\desktop_launcher.py %*
    goto :finished
)
echo Shimmer could not find Python. Install the prerequisites in README section G,
echo then double-click start_shimmer.bat again.
pause
exit /b 1
:finished
set "SHIMMER_EXIT=%errorlevel%"
if not "%SHIMMER_EXIT%"=="0" echo Shimmer stopped with a failure. See the startup window or output\startup logs.
exit /b %SHIMMER_EXIT%
