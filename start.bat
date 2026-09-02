@echo off
setlocal EnableDelayedExpansion

title GameForge AI ^| Launcher

echo.
echo  ========================================================
echo                     GAMEFORGE AI
echo              Local Application Launcher
echo  ========================================================
echo.

:: ── Resolve project root (strip trailing backslash) ────────────────────────
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\gameforge-ai"
set "VENV_DIR=%BACKEND_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"

if "%BACKEND_PORT%"=="" set "BACKEND_PORT=8000"
if "%FRONTEND_PORT%"=="" set "FRONTEND_PORT=5173"

:: Direct API URL for local development: routes browser REST/SSE traffic directly to FastAPI,
:: eliminating dependence on the unstable Vite dev proxy (prevents ECONNRESET socket drops).
:: Preserves any custom VITE_API_URL if already set in the caller's environment.
if "%VITE_API_URL%"=="" set "VITE_API_URL=http://127.0.0.1:%BACKEND_PORT%"
if "%CORS_ORIGINS%"=="" set "CORS_ORIGINS=http://localhost:%FRONTEND_PORT%,http://127.0.0.1:%FRONTEND_PORT%"

:: Suppress HuggingFace cache symlink noise on Windows
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

:: The Discovery embedding model (sentence-transformers/all-MiniLM-L6-v2) is
:: fetched once and cached under %USERPROFILE%\.cache\huggingface\hub (or %HF_HOME%\hub).
:: If cached, we enable HF_HUB_OFFLINE=1 to prevent unauthenticated metadata pings on every load.
:: If not cached (clean machine / fresh clone), we leave HF_HUB_OFFLINE unset so huggingface_hub
:: can download the required embedding weights automatically on first run.
set "HF_MODEL_CACHE=%USERPROFILE%\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2"
if defined HF_HOME set "HF_MODEL_CACHE=%HF_HOME%\hub\models--sentence-transformers--all-MiniLM-L6-v2"

if exist "%HF_MODEL_CACHE%" (
    set "HF_HUB_OFFLINE=1"
) else (
    set "HF_HUB_OFFLINE="
)

:: ══════════════════════════════════════════════════════════════════════
:: STAGE 1  Python Runtime Detection & Verification
:: ══════════════════════════════════════════════════════════════════════
echo [1/8] Checking Python runtime ...
set "SYSTEM_PYTHON="

:: If virtualenv already exists, check that it's working
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        echo        OK  (.venv Python ready)
        goto :stage2
    )
)

:: Look for a compatible system Python (3.10+)
for %%C in ("py -3.12" "py -3.11" "py -3.10" "py -3" "python") do (
    if not defined SYSTEM_PYTHON (
        %%~C -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "SYSTEM_PYTHON=%%~C"
        )
    )
)

if not defined SYSTEM_PYTHON (
    echo.
    echo  [ERROR] Python 3.10+ was not found on your system.
    echo.
    echo         GameForge AI requires Python 3.10, 3.11, or 3.12.
    echo         Please download and install Python from:
    echo           https://www.python.org/downloads/
    echo.
    echo         IMPORTANT: Check the box "Add python.exe to PATH" during installation.
    echo.
    pause
    exit /b 1
)
echo        OK  (Found %SYSTEM_PYTHON%)

:stage2
:: ══════════════════════════════════════════════════════════════════════
:: STAGE 2  Node.js & npm Detection
:: ══════════════════════════════════════════════════════════════════════
echo [2/8] Checking Node.js and npm ...
where npm >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Node.js / npm was not found in your PATH.
    echo.
    echo         GameForge AI requires Node.js 18+ (LTS recommended).
    echo         Please download and install Node.js from:
    echo           https://nodejs.org/
    echo.
    pause
    exit /b 1
)
echo        OK  (npm found)

:: ══════════════════════════════════════════════════════════════════════
:: STAGE 3  Python Virtual Environment & Dependencies (.venv)
:: ══════════════════════════════════════════════════════════════════════
echo [3/8] Preparing Python environment ...

:: Create .venv if missing
if not exist "%VENV_PYTHON%" (
    echo        Creating Python virtual environment in .venv ...
    %SYSTEM_PYTHON% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo.
        echo  [ERROR] Failed to create virtual environment in "%VENV_DIR%".
        echo         Check permissions and disk space.
        echo.
        pause
        exit /b 1
    )
)

:: Smoke-test critical imports to determine if pip install is needed
"%VENV_PYTHON%" -c "import fastapi, uvicorn, alembic, sqlalchemy, google.genai, sentence_transformers, faiss, jwt, pwdlib" >nul 2>&1
if errorlevel 1 (
    echo        Installing backend dependencies (pip install -r requirements.txt) ...
    "%VENV_PIP%" install -r "%BACKEND_DIR%\requirements.txt"
    if errorlevel 1 (
        echo.
        echo  [ERROR] pip install failed. Please check your network connection and retry.
        echo.
        pause
        exit /b 1
    )
    "%VENV_PYTHON%" -c "import fastapi, uvicorn, alembic, sqlalchemy, google.genai, sentence_transformers, faiss, jwt, pwdlib" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  [ERROR] Backend packages could not be verified after installation.
        echo.
        pause
        exit /b 1
    )
)
echo        OK  (Python dependencies ready)

:: ══════════════════════════════════════════════════════════════════════
:: STAGE 4  Frontend Dependencies (node_modules)
:: ══════════════════════════════════════════════════════════════════════
echo [4/8] Preparing frontend dependencies ...
if not exist "%FRONTEND_DIR%\node_modules" (
    echo        Installing frontend dependencies (npm install) ...
    pushd "%FRONTEND_DIR%"
    call npm install
    if errorlevel 1 (
        echo.
        echo  [ERROR] npm install failed. Please check your network connection and retry.
        popd
        pause
        exit /b 1
    )
    popd
)
echo        OK  (Frontend packages ready)

:: ══════════════════════════════════════════════════════════════════════
:: STAGE 5  Backend Configuration & Secrets (.env)
:: ══════════════════════════════════════════════════════════════════════
echo [5/8] Checking configuration (.env) ...

:: If .env doesn't exist, create it from .env.example with an auto-generated JWT secret
if not exist "%BACKEND_DIR%\.env" (
    if exist "%BACKEND_DIR%\.env.example" (
        echo        Creating backend\.env from .env.example ...
        copy "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
        "%VENV_PYTHON%" -c "import secrets, pathlib; p = pathlib.Path(r'%BACKEND_DIR%\.env'); p.write_text(p.read_text(encoding='utf-8').replace('CHANGE_ME_BEFORE_RUNNING_IN_ANY_ENVIRONMENT', secrets.token_hex(32)), encoding='utf-8')"
    ) else (
        echo.
        echo  [ERROR] Neither .env nor .env.example was found in "%BACKEND_DIR%".
        echo.
        pause
        exit /b 1
    )
)

:: If AUTH_JWT_SECRET is still the template placeholder in an existing .env, automatically replace it
findstr /C:"CHANGE_ME_BEFORE_RUNNING" "%BACKEND_DIR%\.env" >nul 2>&1
if not errorlevel 1 (
    echo        Auto-generating secure AUTH_JWT_SECRET in .env ...
    "%VENV_PYTHON%" -c "import secrets, pathlib; p = pathlib.Path(r'%BACKEND_DIR%\.env'); p.write_text(p.read_text(encoding='utf-8').replace('CHANGE_ME_BEFORE_RUNNING_IN_ANY_ENVIRONMENT', secrets.token_hex(32)), encoding='utf-8')"
)

:: Check if GEMINI_API_KEY is configured
set "HAS_GEMINI_KEY=0"
findstr /C:"your-primary-gemini-api-key-here" "%BACKEND_DIR%\.env" >nul 2>&1
if errorlevel 1 (
    findstr /R /C:"^GEMINI_API_KEY=AIza[0-9A-Za-z_-]*" "%BACKEND_DIR%\.env" >nul 2>&1
    if not errorlevel 1 set "HAS_GEMINI_KEY=1"
    findstr /R /C:"^GEMINI_API_KEYS=.*" "%BACKEND_DIR%\.env" >nul 2>&1
    if not errorlevel 1 set "HAS_GEMINI_KEY=1"
)

if "%HAS_GEMINI_KEY%"=="0" (
    echo        [INFO] GEMINI_API_KEY not yet configured in backend\.env.
    echo               Discovery search, game blueprints, and local playtests work fully.
    echo               To enable generative AI builds, add a free key from https://aistudio.google.com/
)
echo        OK  (Configuration validated)

:: ══════════════════════════════════════════════════════════════════════
:: STAGE 6  Database Schema Synchronization (Alembic)
:: ══════════════════════════════════════════════════════════════════════
echo [6/8] Synchronizing database schema ...
pushd "%BACKEND_DIR%"
"%VENV_PYTHON%" -m alembic upgrade head >nul 2>&1
if errorlevel 1 (
    echo        [WARN] Database migration returned non-zero. Attempting startup with current schema ...
) else (
    echo        OK  (Database up to date)
)
popd

:: ══════════════════════════════════════════════════════════════════════
:: STAGE 7  Port Clearance & Service Startup
:: ══════════════════════════════════════════════════════════════════════
echo [7/8] Preparing ports and launching services ...

:: Safely clear stale GameForge processes on target ports (only PID > 4 and python/node)
for %%R in (%BACKEND_PORT% %FRONTEND_PORT%) do (
    for /f %%P in ('powershell -NoProfile -NonInteractive -Command "try { (Get-NetTCPConnection -LocalPort %%R -State Listen -ErrorAction Stop).OwningProcess | Select-Object -Unique | ForEach-Object { $proc = Get-Process -Id $_ -ErrorAction SilentlyContinue; if ($proc -and $_ -gt 4 -and ($proc.ProcessName -eq 'python' -or $proc.ProcessName -eq 'node')) { $_ } } } catch {}"') do (
        echo        Clearing stale process (PID %%P) on port %%R ...
        taskkill /F /PID %%P >nul 2>&1
    )
)

:: Launch Backend API
set "BACKEND_CMD=cd /d "%BACKEND_DIR%" && "%VENV_PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT% --reload"
start "GameForge AI | Backend [:%BACKEND_PORT%]" cmd /k "color 0A && title GameForge AI ^| Backend [:%BACKEND_PORT%] && %BACKEND_CMD%"

:: Launch Frontend UI
set "FRONTEND_CMD=cd /d "%FRONTEND_DIR%" && npm run dev -- --host 127.0.0.1 --port %FRONTEND_PORT%"
start "GameForge AI | Frontend [:%FRONTEND_PORT%]" cmd /k "color 0B && title GameForge AI ^| Frontend [:%FRONTEND_PORT%] && %FRONTEND_CMD%"

:: ══════════════════════════════════════════════════════════════════════
:: STAGE 8  Health Polling & Automatic Browser Launch
:: ══════════════════════════════════════════════════════════════════════
echo [8/8] Waiting for services to initialize ...

where curl >nul 2>&1
if not errorlevel 1 (
    set "USE_CURL=1"
) else (
    set "USE_CURL=0"
)

set "BACKEND_READY=0"
set "TRIES=30"

:poll_backend
if "%USE_CURL%"=="1" (
    curl -s -f "http://127.0.0.1:%BACKEND_PORT%/api/health" >nul 2>&1
) else (
    powershell -NoProfile -NonInteractive -Command "try { $res = Invoke-RestMethod -Uri 'http://127.0.0.1:%BACKEND_PORT%/api/health' -TimeoutSec 2 -ErrorAction Stop; if ($res.status -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
)
if not errorlevel 1 (
    set "BACKEND_READY=1"
    goto :poll_frontend
)
timeout /t 1 /nobreak >nul
set /a TRIES=TRIES-1
if %TRIES% GTR 0 goto :poll_backend

:poll_frontend
set "FRONTEND_READY=0"
set "FTRIES=20"

:poll_frontend_loop
if "%USE_CURL%"=="1" (
    curl -s -f "http://127.0.0.1:%FRONTEND_PORT%/" >nul 2>&1
) else (
    powershell -NoProfile -NonInteractive -Command "try { $res = Invoke-WebRequest -Uri 'http://127.0.0.1:%FRONTEND_PORT%/' -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop; if ($res.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
)
if not errorlevel 1 (
    set "FRONTEND_READY=1"
    goto :open_browser
)
timeout /t 1 /nobreak >nul
set /a FTRIES=FTRIES-1
if %FTRIES% GTR 0 goto :poll_frontend_loop

:open_browser
echo        Opening GameForge AI in default browser ...
start "" "http://127.0.0.1:%FRONTEND_PORT%/#/"

echo.
echo  ========================================================
echo                   GAMEFORGE AI IS READY
echo  ========================================================
echo    Frontend App         :  http://127.0.0.1:%FRONTEND_PORT%/#/
echo    Backend REST API     :  http://127.0.0.1:%BACKEND_PORT%
echo    API Documentation    :  http://127.0.0.1:%BACKEND_PORT%/docs
echo  --------------------------------------------------------
if "%HAS_GEMINI_KEY%"=="1" (
echo    AI Generation Engine :  Active (Gemini configured)
) else (
echo    AI Generation Engine :  Discovery & Local Playtests Ready
)
echo    Discovery Search     :  Active (Offline semantic + lexical)
echo    Project Studio       :  Active (Game blueprints, playtests, versions)
echo  --------------------------------------------------------
echo    To stop GameForge AI :  Close the Backend and Frontend
echo                            terminal windows.
echo  ========================================================
echo.
pause
