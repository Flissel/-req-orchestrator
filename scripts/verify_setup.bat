@echo off
REM Setup Verification Script for Windows
REM Checks if all required services are running

echo.
echo ======================================================================
echo   arch_team Setup Verification
echo ======================================================================
echo.

set ERROR_COUNT=0

echo ======================================================================
echo   1. Environment Configuration
echo ======================================================================
echo.

if exist ".env" (
    echo [OK] .env file exists
) else (
    echo [FAIL] .env file not found
    echo   Run: copy .env.example .env
    set /a ERROR_COUNT+=1
)

echo.
echo ======================================================================
echo   2. Dependencies
echo ======================================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Python is installed
) else (
    echo [FAIL] Python not found in PATH
    set /a ERROR_COUNT+=1
)

where node >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Node.js is installed
) else (
    echo [FAIL] Node.js not found in PATH
    set /a ERROR_COUNT+=1
)

if exist "node_modules" (
    echo [OK] Node.js packages installed
) else (
    echo [FAIL] node_modules not found
    echo   Run: npm install
    set /a ERROR_COUNT+=1
)

echo.
echo ======================================================================
echo   3. Services
echo ======================================================================
echo.

REM Check Qdrant (port 6401)
curl -s http://localhost:6401/collections >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Qdrant is running on port 6401
) else (
    echo [FAIL] Qdrant not reachable on port 6401
    echo   Run: docker-compose -f docker-compose.qdrant.yml up -d
    set /a ERROR_COUNT+=1
)

REM Check arch_team service (port 8000)
curl -s http://localhost:8000/health >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] arch_team service is running on port 8000
) else (
    echo [FAIL] arch_team service not reachable on port 8000
    echo   Run: python -m arch_team.service
    set /a ERROR_COUNT+=1
)

echo.
echo ======================================================================
echo   Summary
echo ======================================================================
echo.

if %ERROR_COUNT% EQU 0 (
    echo [OK] All checks passed!
    echo.
    echo You can start the React frontend:
    echo   npm run dev
    echo.
    echo Access the UI at: http://localhost:3000
) else (
    echo [FAIL] %ERROR_COUNT% check(s) failed. Please fix the issues above.
    echo.
    echo Quick start commands:
    echo   1. copy .env.example .env  ^(Then edit .env to add OPENAI_API_KEY^)
    echo   2. pip install -r requirements.txt
    echo   3. npm install
    echo   4. docker-compose -f docker-compose.qdrant.yml up -d
    echo   5. python -m arch_team.service
    echo   6. npm run dev
)

echo.
exit /b %ERROR_COUNT%
