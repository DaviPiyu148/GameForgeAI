@echo off
setlocal EnableDelayedExpansion

title GameForge AI ^| Dev Launcher

echo.
echo  ==========================================
echo    GameForge AI  ^|  Dev Server Launcher
echo  ==========================================
echo.

:: ── Resolve project root (strip trailing backslash) ────────────────────────
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\gameforge-ai"
set "VENV_DIR=%BACKEND_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"
set "VENV_ALEMBIC=%VENV_DIR%\Scripts\alembic.exe"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

:: Suppress HuggingFace cache symlink noise on Windows
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

echo  Checking prerequisites ...
echo.

:: ══════════════════════════════════════════════════════════════════════
:: CHECK 1  Python virtual environment
:: ══════════════════════════════════════════════════════════════════════
echo [1/6] Python virtual environment ...
if not exist "%VENV_PYTHON%" (
    echo.
    echo  [ERROR] Python virtual environment not found.
    echo.
    echo         Run these commands to create it:
    echo.
    echo           cd /d "%BACKEND_DIR%"
    echo           python -m venv .venv
    echo           .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo        OK  (.venv found)

:: ══════════════════════════════════════════════════════════════════════
:: CHECK 2  Core packages installed (fast smoke-test: import fastapi)
:: ══════════════════════════════════════════════════════════════════════
echo [2/6] Python packages ...
"%VENV_PYTHON%" -c "import fastapi, uvicorn, alembic, sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo        Packages missing or incomplete -- running pip install ...
    "%VENV_PIP%" install -r "%BACKEND_DIR%\requirements.txt"
    if errorlevel 1 (
        echo.
        echo  [ERROR] pip install failed. Fix the errors above and re-run start.bat.
        pause
        exit /b 1
    )
)
echo        OK  (packages ready)

:: ══════════════════════════════════════════════════════════════════════
:: CHECK 3  .env file + required secrets
:: ══════════════════════════════════════════════════════════════════════
echo [3/6] Backend configuration (.env) ...
if not exist "%BACKEND_DIR%\.env" (
    if exist "%BACKEND_DIR%\.env.example" (
        echo        .env missing -- copying from .env.example ...
        copy "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
        echo        Copied. You MUST edit "%BACKEND_DIR%\.env" and set:
        echo          GEMINI_API_KEY=^<your key^>
        echo          AUTH_JWT_SECRET=^<run: python -c "import secrets;print(secrets.token_hex(32))"^>
        echo.
        pause
        exit /b 1
    ) else (
        echo.
        echo  [ERROR] No .env or .env.example found in "%BACKEND_DIR%".
        echo          Create a .env file before running this launcher.
        pause
        exit /b 1
    )
)

:: Check that AUTH_JWT_SECRET is not the placeholder value
findstr /C:"CHANGE_ME_BEFORE_RUNNING" "%BACKEND_DIR%\.env" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo  [ERROR] AUTH_JWT_SECRET in .env is still the placeholder value.
    echo.
    echo          Generate a real secret key:
    echo            "%VENV_PYTHON%" -c "import secrets; print(secrets.token_hex(32))"
    echo          Then set AUTH_JWT_SECRET=^<output^> in "%BACKEND_DIR%\.env"
    echo.
    pause
    exit /b 1
)

:: Warn if GEMINI_API_KEY looks like a placeholder
findstr /C:"your-gemini-api-key" "%BACKEND_DIR%\.env" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo  [WARN] GEMINI_API_KEY in .env appears to be a placeholder.
    echo         AI game generation will fail until you add a real key.
    echo         Get a free key at: https://aistudio.google.com/
    echo.
)
echo        OK  (.env ready)

:: ══════════════════════════════════════════════════════════════════════
:: CHECK 4  Node.js / npm + frontend dependencies
:: ══════════════════════════════════════════════════════════════════════
echo [4/6] Node.js and frontend dependencies ...
where npm >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] npm not found in PATH.
    echo          Install Node.js 18+ from https://nodejs.org then re-run.
    pause
    exit /b 1
)
if not exist "%FRONTEND_DIR%\node_modules" (
    echo        node_modules missing -- running npm install ...
    pushd "%FRONTEND_DIR%"
    npm install
    if errorlevel 1 (
        echo.
        echo  [ERROR] npm install failed.
        popd
        pause
        exit /b 1
    )
    popd
)
echo        OK  (Node and node_modules ready)

:: ══════════════════════════════════════════════════════════════════════
:: CHECK 5  Database migrations
:: ══════════════════════════════════════════════════════════════════════
echo [5/6] Database migrations (alembic upgrade head) ...
pushd "%BACKEND_DIR%"
"%VENV_PYTHON%" -m alembic upgrade head
if errorlevel 1 (
    echo.
    echo  [WARN] Alembic returned a non-zero exit code.
    echo         Check the error above. The app may not start correctly.
    echo.
)
popd
echo        OK  (database schema up to date)

:: ══════════════════════════════════════════════════════════════════════
:: CHECK 6  Port conflict clearance
:: ══════════════════════════════════════════════════════════════════════
echo [6/6] Clearing ports %BACKEND_PORT% and %FRONTEND_PORT% ...
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr /R ":%BACKEND_PORT% .*LISTENING"') do (
    echo        Stopping stale process %%P on port %BACKEND_PORT% ...
    taskkill /F /PID %%P >nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr /R ":%FRONTEND_PORT% .*LISTENING"') do (
    echo        Stopping stale process %%P on port %FRONTEND_PORT% ...
    taskkill /F /PID %%P >nul 2>&1
)
echo        OK  (ports clear)

:: ══════════════════════════════════════════════════════════════════════
:: LAUNCH  Backend
:: Uses full venv python path — no activation needed
:: Path is double-quoted to handle spaces in directory names
:: ══════════════════════════════════════════════════════════════════════
echo.
echo  Starting Backend API  ^>  http://127.0.0.1:%BACKEND_PORT%
echo  Starting Frontend UI  ^>  http://127.0.0.1:%FRONTEND_PORT%/#/
echo.

set "BACKEND_CMD=cd /d "%BACKEND_DIR%" && "%VENV_PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT% --reload"
set "FRONTEND_CMD=cd /d "%FRONTEND_DIR%" && npm run dev -- --port %FRONTEND_PORT%"

start "GameForge AI | Backend [:%BACKEND_PORT%]" cmd /k "color 0A && title GameForge AI ^| Backend [:%BACKEND_PORT%] && %BACKEND_CMD%"
start "GameForge AI | Frontend [:%FRONTEND_PORT%]" cmd /k "color 0B && title GameForge AI ^| Frontend [:%FRONTEND_PORT%] && %FRONTEND_CMD%"

:: ══════════════════════════════════════════════════════════════════════
:: HEALTH CHECK  (backend — max ~40 s)
:: ══════════════════════════════════════════════════════════════════════
echo  Waiting for backend to become healthy (up to 40 s) ...
set "TRIES=20"
set "CURL_OK=0"

:: Test whether curl is available
where curl >nul 2>&1
if errorlevel 1 (
    echo  [INFO] curl not found -- skipping health check, opening browser now.
    timeout /t 5 /nobreak >nul
    goto :open
)

:wait
timeout /t 2 /nobreak >nul
curl -s -f "http://127.0.0.1:%BACKEND_PORT%/api/health" >nul 2>&1
if not errorlevel 1 (
    set "CURL_OK=1"
    goto :ready
)
set /a TRIES=TRIES-1
if %TRIES%==0 goto :timeout
echo        Still waiting ... (%TRIES% attempts left)
goto :wait

:timeout
echo.
echo  [WARN] Backend did not respond within 40 s.
echo         Check the "GameForge AI ^| Backend" window for errors.
echo.
goto :open

:ready
echo  Backend is healthy and responding!

:: ══════════════════════════════════════════════════════════════════════
:: WAIT for Vite to finish its first compilation before opening browser
:: ══════════════════════════════════════════════════════════════════════
:open
echo.
echo  Giving Vite a moment to finish its initial build ...
timeout /t 4 /nobreak >nul

echo  Opening GameForge AI in your default browser ...
start "" "http://127.0.0.1:%FRONTEND_PORT%/#/"

echo.
echo  ==========================================
echo    GameForge AI  ^|  Running
echo  ------------------------------------------
echo    Backend API   :  http://127.0.0.1:%BACKEND_PORT%
echo    API Swagger   :  http://127.0.0.1:%BACKEND_PORT%/docs
echo    Frontend App  :  http://127.0.0.1:%FRONTEND_PORT%/#/
echo.
echo    Features live:
echo    - Discovery   :  Lexical + Semantic Search
echo    - Builder     :  AI Game Compilation + Phaser
echo    - Game DNA    :  Preference Telemetry
echo    - Creator XP  :  Levels, Badges, Milestones
echo.
echo    To stop: close the Backend and Frontend terminal windows.
echo  ==========================================
echo.
pause
