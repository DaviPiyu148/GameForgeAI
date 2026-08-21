@echo off
setlocal EnableDelayedExpansion

title GameForge AI ^| Dev Launcher

echo.
echo  ==========================================
echo   GameForge AI  ^|  Dev Server Launcher
echo  ==========================================
echo.

:: Resolve project root (directory this .bat lives in)
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\gameforge-ai"
set "VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

:: 1. Python virtual environment check
echo [1/4] Checking Python virtual environment ...
if not exist "%VENV_PYTHON%" (
    echo  [ERROR] Python virtual environment not found at:
    echo          %VENV_PYTHON%
    echo.
    echo  Setup instructions:
    echo          cd backend
    echo          python -m venv .venv
    echo          .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo       OK (Python venv found)

:: 2. Node / npm check
echo [2/4] Checking Node / npm ...
where npm >nul 2>&1 || (
    echo  [ERROR] npm not found in PATH.
    echo          Please install Node.js 18+ from https://nodejs.org
    echo.
    pause
    exit /b 1
)
echo       OK (npm found)

:: 3. Frontend dependencies check
echo [3/4] Checking frontend dependencies ...
if not exist "%FRONTEND_DIR%\node_modules" (
    echo       node_modules missing -- running npm install ...
    pushd "%FRONTEND_DIR%"
    npm install || (
        echo  [ERROR] npm install failed.
        popd
        pause
        exit /b 1
    )
    popd
)
echo       OK (node_modules ready)

:: 4. Database migrations
echo [4/4] Checking database schema ^& migrations ...
pushd "%BACKEND_DIR%"
"%VENV_PYTHON%" -m alembic upgrade head || (
    echo  [WARN] Alembic upgrade returned non-zero. Check DB configuration if errors occur.
)
popd
echo       OK (Database ready)

:: Kill any stale processes listening on target ports
echo.
echo Clearing ports %BACKEND_PORT% and %FRONTEND_PORT% ...
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr /R ":%BACKEND_PORT% .*LISTENING"') do (
    taskkill /F /PID %%P >nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr /R ":%FRONTEND_PORT% .*LISTENING"') do (
    taskkill /F /PID %%P >nul 2>&1
)

:: Launch Backend in dedicated window
echo.
echo Starting Backend API (http://127.0.0.1:%BACKEND_PORT%) ...
start "GameForge AI ^| Backend" cmd /k "color 0A && title GameForge AI ^| Backend [:%BACKEND_PORT%] && cd /d "%BACKEND_DIR%" && "%VENV_PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT% --reload"

:: Brief pause so backend binds before Vite starts
timeout /t 3 /nobreak >nul

:: Launch Frontend in dedicated window
echo Starting Frontend UI (http://127.0.0.1:%FRONTEND_PORT%) ...
start "GameForge AI ^| Frontend" cmd /k "color 0B && title GameForge AI ^| Frontend [:%FRONTEND_PORT%] && cd /d "%FRONTEND_DIR%" && npm run dev -- --host 127.0.0.1 --port %FRONTEND_PORT%"

:: Health-check loop (max ~30 s)
echo.
echo Waiting for backend API to become healthy ...
set /a TRIES=15
:wait
timeout /t 2 /nobreak >nul
curl -s -f http://127.0.0.1:%BACKEND_PORT%/api/health >nul 2>&1 && goto :ready
set /a TRIES-=1
if %TRIES%==0 (
    echo  [WARN] Backend did not respond within timeout -- check the Backend window for details.
    goto :open
)
echo       Waiting for backend (%TRIES% attempts remaining) ...
goto :wait

:ready
echo  Backend is healthy and responding!

:open
echo.
echo Opening GameForge AI in default browser ...
start "" "http://127.0.0.1:%FRONTEND_PORT%/"

echo.
echo  ==========================================
echo   GameForge AI Services Running
echo  ------------------------------------------
echo   Backend API  : http://127.0.0.1:%BACKEND_PORT%
echo   API Docs     : http://127.0.0.1:%BACKEND_PORT%/docs
echo   Frontend App : http://127.0.0.1:%FRONTEND_PORT%
echo.
echo   Close the server terminal windows to stop services.
echo  ==========================================
echo.
pause
