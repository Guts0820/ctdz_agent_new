@echo off
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0"
set "VENV_PYTHON=D:\ctdz_agent_venv\Scripts\python.exe"
set "NEO4J_HOME=D:\Neo4j\server\neo4j-community-5.26.6"
set "JAVA_HOME=C:\Program Files\Java\jdk-24"

echo.
echo ========================================
echo   CTDZ Agent full demo launcher
echo ========================================
echo.

if not exist "%VENV_PYTHON%" (
  echo [ERROR] Python environment not found: %VENV_PYTHON%
  echo Create it first with Python 3.11 in D:.
  pause
  exit /b 1
)

if not exist "%NEO4J_HOME%\bin\neo4j.bat" (
  echo [ERROR] Neo4j not found: %NEO4J_HOME%
  pause
  exit /b 1
)

if not exist "%JAVA_HOME%\bin\java.exe" (
  set "JAVA_HOME="
  for /d %%J in ("D:\Java\jdk-*" "D:\Neo4j\java\jdk-*" "C:\Program Files\Eclipse Adoptium\jdk-*") do if exist "%%~J\bin\java.exe" if not defined JAVA_HOME set "JAVA_HOME=%%~J"
)

if not defined JAVA_HOME (
  echo [ERROR] A Java 17 or 21 JDK was not found.
  echo Install one and set JAVA_HOME before running this script.
  pause
  exit /b 1
)

set "PATH=%JAVA_HOME%\bin;%PATH%"
if not exist "%PROJECT_ROOT%backend\logs" mkdir "%PROJECT_ROOT%backend\logs" >nul 2>&1

for %%P in (7474 7687) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$c=Get-NetTCPConnection -LocalPort %%P -State Listen -ErrorAction SilentlyContinue; if($c){exit 0}else{exit 1}" >nul 2>&1
  if errorlevel 1 (
    echo Starting Neo4j...
    start "CTDZ Neo4j" /D "%NEO4J_HOME%" cmd /c "set JAVA_HOME=%JAVA_HOME%&& set PATH=%JAVA_HOME%\bin;%%PATH%%&& bin\neo4j.bat console"
    goto :neo4j_started
  )
)
:neo4j_started

powershell -NoProfile -ExecutionPolicy Bypass -Command "$c=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if($c){exit 0}else{exit 1}" >nul 2>&1
if errorlevel 1 (
  echo Starting backend services...
  start "CTDZ Backend" /D "%PROJECT_ROOT%" cmd /k ""%VENV_PYTHON%" backend\start_all.py"
) else (
  echo Backend already running on port 8000.
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$c=Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue; if($c){exit 0}else{exit 1}" >nul 2>&1
if errorlevel 1 (
  echo Starting frontend...
  start "CTDZ Frontend" /D "%PROJECT_ROOT%frontend" cmd /k ""%VENV_PYTHON%" -m http.server 3000"
) else (
  echo Frontend already running on port 3000.
)

echo Waiting for the frontend...
timeout /t 5 /nobreak >nul
start "" http://127.0.0.1:3000/
echo.
echo CTDZ Agent is starting. Keep the Neo4j, Backend and Frontend windows open.
echo Frontend: http://127.0.0.1:3000/
echo API:      http://127.0.0.1:8000/
pause
