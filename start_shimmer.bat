@echo off
setlocal
cd /d "%~dp0"
echo Opening Start Shimmer. Use its window to start and stop the console.
call tools\resolve_python.bat
if errorlevel 1 exit /b 1
"%SHIMMER_PYTHON%" -X utf8 scripts\desktop_launcher.py %*

:finished
set "SHIMMER_EXIT=%errorlevel%"
if not "%SHIMMER_EXIT%"=="0" echo Shimmer stopped with a failure. See the startup window or output\startup logs.
exit /b %SHIMMER_EXIT%
