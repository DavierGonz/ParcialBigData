@echo off
setlocal
cd /d "%~dp0.."
docker compose config --quiet
if errorlevel 1 exit /b 1
docker compose build api-tests
if errorlevel 1 exit /b 1
docker compose run --rm --no-deps api-tests
if errorlevel 1 exit /b 1
docker build --target runtime --label org.opencontainers.image.revision=working-tree-ui -f docker/api/Dockerfile -t parcialbigdata-api:ui-local .
if errorlevel 1 exit /b 1
set API_IMAGE=parcialbigdata-api:ui-local
docker compose up -d --no-deps --no-build --wait --wait-timeout 90 api
if errorlevel 1 exit /b 1
docker compose exec -T api python /app/scripts/smoke_geo.py http://127.0.0.1:5000
if errorlevel 1 exit /b 1
echo Open http://127.0.0.1:5000/
