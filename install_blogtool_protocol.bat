@echo off
rem Register blogtool:// protocol so edit buttons on the local site auto-start the tool.
set "BAT=%~dp0start_blog_tool.bat"
reg add "HKCU\Software\Classes\blogtool" /ve /d "URL:BlogTool Protocol" /f
reg add "HKCU\Software\Classes\blogtool" /v "URL Protocol" /d "" /f
reg add "HKCU\Software\Classes\blogtool\DefaultIcon" /ve /d "\"%BAT%\",0" /f
reg add "HKCU\Software\Classes\blogtool\shell\open\command" /ve /d "\"%BAT%\" \"%1\"" /f
echo.
echo blogtool:// protocol registered. Edit buttons will auto-start the local tool.
pause
