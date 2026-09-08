@echo off
rem Open local blog site: starts hugo server in WSL if needed, then opens the browser.
setlocal
set "PORT=1313"
set "URL=http://localhost:%PORT%/"
set "WSL_BLOG=/home/mcryii/myblog-new"

rem Already running? Just open the browser.
curl -s -o nul --max-time 1 "%URL%"
if %ERRORLEVEL%==0 goto open

rem Start hugo server inside WSL in background.
wsl.exe -d Ubuntu-24.04 --cd "%WSL_BLOG%" bash ./run.sh --daemon

rem Wait up to ~20 seconds for the server to come up.
set /a tries=0
:waitloop
curl -s -o nul --max-time 1 "%URL%"
if %ERRORLEVEL%==0 goto open
set /a tries+=1
if %tries% LSS 20 (
    timeout /t 1 /nobreak >nul
    goto waitloop
)
echo [ERROR] hugo server did not start in time in WSL.
pause
exit /b 1

:open
start "" "%URL%"
exit /b 0

