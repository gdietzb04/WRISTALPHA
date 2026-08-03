@echo off
setlocal
powershell.exe -NoLogo -NoProfile -File "%~dp0wristalpha.ps1" start
if errorlevel 1 (
  echo.
  echo WRISTALPHA did not start. Review the error above.
  pause
)
