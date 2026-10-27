@echo off
setlocal
cd /d "%~dp0"

where docker >nul 2>nul || (echo Setup failed: Docker CLI was not found. Install Docker Desktop.& exit /b 1)
docker compose version >nul 2>nul || (echo Setup failed: Docker Compose v2 is unavailable. Update Docker Desktop.& exit /b 1)
docker info >nul 2>nul || (echo Setup failed: Docker Engine is not running. Start Docker Desktop and retry.& exit /b 1)

if not exist ".env.docker" (
  where powershell >nul 2>nul || (echo Setup failed: Windows PowerShell is required to generate secure random secrets.& exit /b 1)
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-env.ps1"
  if errorlevel 1 (echo Setup failed while generating .env.docker.& exit /b 1)
  echo Created .env.docker with private random development secrets.
)

findstr /r /c:"^MYSQL_ROOT_PASSWORD=..*" ".env.docker" >nul || (echo Setup failed: MYSQL_ROOT_PASSWORD is missing from .env.docker.& exit /b 1)
findstr /r /c:"^JWT_SECRET_KEY=..*" ".env.docker" >nul || (echo Setup failed: JWT_SECRET_KEY is missing from .env.docker.& exit /b 1)
findstr /r /c:"^INTERNAL_API_KEY=..*" ".env.docker" >nul || (echo Setup failed: INTERNAL_API_KEY is missing from .env.docker.& exit /b 1)
findstr /c:"=GENERATE_WITH_SETUP_SCRIPT" /c:"=change_this" /c:"=change-this" ".env.docker" >nul && (echo Setup failed: .env.docker contains example secret placeholders. Replace only those values with secure random values.& exit /b 1)

docker compose --env-file .env.docker -p ibanking-demo config --quiet
if errorlevel 1 (echo Setup failed: check .env.docker and docker-compose.yml.& exit /b 1)

echo Building and starting iBanking services. Existing Docker volumes are preserved.
docker compose --env-file .env.docker -p ibanking-demo up --build --detach --wait --wait-timeout 240
if errorlevel 1 (
  echo Setup failed: a service did not become healthy. Run: docker compose --env-file .env.docker -p ibanking-demo logs --tail=80
  echo If a host port is occupied, change FRONTEND_PORT or MAILPIT_WEB_PORT in .env.docker.
  exit /b 1
)

for /f "tokens=1,* delims==" %%A in ('findstr /b "FRONTEND_PORT=" .env.docker') do set "FRONTEND_PORT=%%B"
for /f "tokens=1,* delims==" %%A in ('findstr /b "MAILPIT_WEB_PORT=" .env.docker') do set "MAILPIT_WEB_PORT=%%B"
if not defined FRONTEND_PORT set "FRONTEND_PORT=8080"
if not defined MAILPIT_WEB_PORT set "MAILPIT_WEB_PORT=8025"

powershell -NoProfile -Command "try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 'http://127.0.0.1:%FRONTEND_PORT%/').StatusCode -ne 200) { exit 1 } } catch { exit 1 }" >nul
if errorlevel 1 (echo Setup failed: Nginx/frontend did not answer on port %FRONTEND_PORT%. Check logs and port availability.& exit /b 1)
powershell -NoProfile -Command "try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 'http://127.0.0.1:%MAILPIT_WEB_PORT%/').StatusCode -lt 200) { exit 1 } } catch { exit 1 }" >nul
if errorlevel 1 (echo Setup failed: Mailpit did not answer on port %MAILPIT_WEB_PORT%. Check logs and port availability.& exit /b 1)
powershell -NoProfile -Command "try { $r=Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:%FRONTEND_PORT%/api/v1/auth/login' -ContentType 'application/json' -Body (@{username='user01';password='password123'} | ConvertTo-Json) -TimeoutSec 10; if ($r.access_token) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul
if errorlevel 1 (echo Setup failed: demo login check failed. Check database seeding and User Service logs.& exit /b 1)

echo.
echo ========================================
echo  iBanking Setup Completed Successfully
echo ========================================
echo.
echo Frontend: http://localhost:%FRONTEND_PORT%
echo Demo Email Inbox: http://localhost:%MAILPIT_WEB_PORT%
echo.
echo Services: User Service READY; Tuition Service READY; Payment Service READY; MySQL READY; Nginx READY; Mailpit READY
echo Demo Login: user01 / password123
echo.
echo To stop: stop.bat
echo To restart: setup.bat
echo.
if not exist "%~dp0setup-menu.ps1" (echo Setup succeeded, but setup-menu.ps1 is missing.& endlocal & exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-menu.ps1"
set "MENU_EXIT=%ERRORLEVEL%"
endlocal & exit /b %MENU_EXIT%
