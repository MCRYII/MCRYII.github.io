@echo off
rem Open local blog site: starts hugo server if needed, then opens the browser.
setlocal
set "PORT=1313"
set "URL=http://localhost:%PORT%/"
set "BLOG=D:\Downloads\Programs\myblog-new"

rem Already running? Just open the browser.
curl -s -o nul --max-time 1 "%URL%"
if %ERRORLEVEL%==0 goto open

cd /d "%BLOG%"
rem Start hugo server in a minimized window.
start "hugo server" /min cmd /c "hugo server -D --port %PORT% >nul 2>&1"

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
echo [ERROR] hugo server did not start in time. Is hugo installed?
pause
exit /b 1

:open
start "" "%URL%"
exit /b 0
