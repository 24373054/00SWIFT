@echo off
rem SWIFT Developer Testing System v2 - launcher.
rem Uses the Python that has the backend deps installed.
setlocal

rem 1) Prefer the conda "yz" env Python (where deps were installed).
set "PY=C:\Users\23157\.conda\envs\yz\python.exe"
if not exist "%PY%" (
  rem 2) Fall back to whatever python resolves to on PATH (must be 3.10+).
  for /f "delims=" %%i in ('where python 2^>nul') do (
    set "PY=%%i"
    goto :foundpy
  )
  echo [error] Python not found on PATH. Install Python 3.10+ and retry.
  pause
  exit /b 1
)
:foundpy

echo Using Python: %PY%
"%PY%" --version

rem 3) Sanity-check critical deps; install if missing.
"%PY%" -c "import fastapi, uvicorn, sqlalchemy, jwt, cryptography, lxml" >nul 2>&1
if errorlevel 1 (
  echo [warn] Some dependencies missing. Installing from requirements.txt...
  "%PY%" -m pip install -r "%~dp0backend\requirements.txt"
)

cd /d "%~dp0backend"
"%PY%" -m uvicorn main:app --host 127.0.0.1 --port 8765 --reload
pause
