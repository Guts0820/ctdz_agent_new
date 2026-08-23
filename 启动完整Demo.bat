@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV_PYTHON=D:\ctdz_agent_venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"

echo.
echo ========================================
echo   CTDZ Agent full demo launcher
echo ========================================
echo.

if not exist "%VENV_PYTHON%" (
  echo [ERROR] Python environment not found.
  echo Checked: D:\ctdz_agent_venv\Scripts\python.exe
  echo Checked: %~dp0.venv\Scripts\python.exe
  pause
  exit /b 1
)

rem start_demo.py owns Neo4j and all backend services. Do not start Neo4j
rem separately here, otherwise two startup attempts can race each other.
"%VENV_PYTHON%" -u "%~dp0start_demo.py"

echo.
echo CTDZ Agent has stopped. Review the Backend window if startup failed.
pause
