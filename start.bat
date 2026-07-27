@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

rem Double-click launcher for Windows.
rem Extra switches such as -NoBrowser are forwarded to start.ps1.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo [00SWIFT] Startup failed with exit code %EXIT_CODE%.
  if not "%SWIFT_NO_PAUSE%"=="1" (
    echo [00SWIFT] Review the error above, then press any key to close.
    pause >nul
  )
)

exit /b %EXIT_CODE%
