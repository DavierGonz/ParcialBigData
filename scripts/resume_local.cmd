@echo off
setlocal
cd /d "%~dp0.."
rem Resume this host's existing containers; never build, replace the API or run ETL.
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker is not ready. Open Docker Desktop, wait for Engine running and retry.
  exit /b 1
)
docker compose -f docker-compose.yml -f ci\compose.webhook.yml config --quiet
if errorlevel 1 exit /b 1
docker compose -f docker-compose.yml -f ci\compose.webhook.yml start --wait --wait-timeout 240
if errorlevel 1 exit /b 1
docker compose exec -T api python /app/scripts/smoke_geo.py http://127.0.0.1:5000
if errorlevel 1 exit /b 1
echo Atlasvial: http://127.0.0.1:5000/
echo Compass: 127.0.0.1:27018 - existing application user and authentication database.
echo Quick Tunnel URL can change. GitHub is not modified by this script.
