@echo off
rem Blog tool launcher: used by blogtool:// protocol, or double-click to open web mode.
setlocal
set "SCRIPT=%~dp0blog_tool.py"
set "RUNNER=%BLOG_TOOL_PY%"
if not defined RUNNER set "RUNNER=C:\Users\MCRYII\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
if not exist "%RUNNER%" (
    echo [ERROR] Python not found: %RUNNER%
    echo Set env var BLOG_TOOL_PY to python.exe or pythonw.exe and retry.
    pause
    exit /b 1
)
if "%~1"=="" (
    start "" "%RUNNER%" "%SCRIPT%" --web
) else (
    start "" "%RUNNER%" "%SCRIPT%" --web "%~1"
)
exit /b 0
