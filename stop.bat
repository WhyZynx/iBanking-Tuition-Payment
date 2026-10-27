@echo off
setlocal
cd /d "%~dp0"
where docker >nul 2>nul || (echo Docker CLI was not found.& exit /b 1)
if not exist ".env.docker" (echo .env.docker is missing; nothing was stopped.& exit /b 1)
docker compose --env-file .env.docker -p ibanking-demo stop
if errorlevel 1 exit /b 1
echo iBanking services stopped. Database volume and .env.docker were preserved.
endlocal
