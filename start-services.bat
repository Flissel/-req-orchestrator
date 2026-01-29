@echo off
echo Starting Requirements Orchestrator Services...
echo.
echo This will open 3 terminal windows:
echo   1. arch_team service (port 8000)
echo   2. FastAPI backend (port 8087)
echo   3. Vite frontend (port 3003)
echo.
echo Press any key to continue...
pause >nul

cd /d "%~dp0"

echo Starting arch_team service...
start "arch_team (port 8000)" cmd /k "python -m arch_team.service"

timeout /t 2 /nobreak >nul

echo Starting FastAPI backend...
start "FastAPI backend (port 8087)" cmd /k "python -m uvicorn backend.main:fastapi_app --host 0.0.0.0 --port 8087 --reload"

timeout /t 2 /nobreak >nul

echo Starting Vite frontend...
start "Vite frontend (port 3003)" cmd /k "npx vite --port 3003"

echo.
echo All services started!
echo.
echo Services are running in separate windows:
echo   - arch_team: http://localhost:8000
echo   - FastAPI backend: http://localhost:8087
echo   - Vite frontend: http://localhost:3003
echo.
echo To stop a service, close its terminal window or press Ctrl+C in it.
echo.
echo Press any key to exit this window...
pause >nul
