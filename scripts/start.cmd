@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Create .venv and install requirements following README.md first.
  exit /b 1
)
.venv\Scripts\python.exe scripts\init_env.py
if errorlevel 1 exit /b 1
docker compose config --quiet
if errorlevel 1 exit /b 1
docker compose build api-tests
if errorlevel 1 exit /b 1
docker compose run --rm --no-deps api-tests
if errorlevel 1 exit /b 1
docker compose up -d --build --wait --wait-timeout 300
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe scripts\verify_infra.py
if errorlevel 1 exit /b 1
