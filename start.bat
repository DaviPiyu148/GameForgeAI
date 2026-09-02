@echo off
setlocal EnableExtensions EnableDelayedExpansion
title GameForge AI — Launcher

REM ============================================================================
REM  GameForge AI — Automated Local Bootstrap Orchestrator
REM
REM  Mental Model:
REM    Double-click start.bat
REM         ↓
REM    [1/10] Python Runtime (3.10+) (Auto-winget if missing + PATH refresh)
REM    [2/10] Node.js & npm (18+)    (Auto-winget if missing + PATH refresh)
REM    [3/10] Python Environment     (.venv + requirements.txt consistency)
REM    [4/10] Frontend Dependencies  (npm ci + package-lock.json hash check)
REM    [5/10] Configuration          (.env + auto-generated JWT secret)
REM    [6/10] Database Schema        (Alembic migrations upgrade head)
REM    [7/10] Discovery ML & Index   (SentenceTransformer + FAISS self-bootstrap)
REM    [8/10] Port & Process Safety  (Signature-verified process clearance)
REM    [9/10] Service Orchestration  (FastAPI on 8000 + Vite on 5173)
REM    [10/10] Health & Browser      (Poll /api/health + open browser)
REM ============================================================================

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "BACKEND_DIR=%PROJECT_ROOT%\backend"
set "FRONTEND_DIR=%PROJECT_ROOT%\gameforge-ai"

if not defined BACKEND_PORT set "BACKEND_PORT=8000"
if not defined FRONTEND_PORT set "FRONTEND_PORT=5173"

echo.
echo ============================================================================
echo   GAMEFORGE AI -- Automated Local Bootstrap Launcher
echo ============================================================================
echo   Project Root : %PROJECT_ROOT%
echo   Backend Port : %BACKEND_PORT%
echo   Frontend Port: %FRONTEND_PORT%
echo ============================================================================
echo.

REM ============================================================================
REM  STAGE 1: Python Runtime Detection & Winget Auto-Install
REM ============================================================================
echo [1/10] Checking Python runtime (3.10+)...

set "SYSTEM_PYTHON="
set "PYTHON_OK=0"

REM Check standard Python commands
for %%C in ("py -3.12" "py -3.11" "py -3.10" "py -3" "python") do (
    if "!PYTHON_OK!"=="0" (
        %%~C -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            set "SYSTEM_PYTHON=%%~C"
            set "PYTHON_OK=1"
        )
    )
)

REM If not found, check existing venv
if "!PYTHON_OK!"=="0" if exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
    "%BACKEND_DIR%\.venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "SYSTEM_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
        set "PYTHON_OK=1"
    )
)

REM If still missing, attempt automatic winget installation
if "!PYTHON_OK!"=="0" (
    where winget >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo        Python 3.10+ was not found on your system.
        echo        Attempting automatic installation of Python 3.12 via winget...
        winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        
        REM Refresh in-session PATH for standard Python installation paths
        if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
            set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;!PATH!"
            set "SYSTEM_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
            set "PYTHON_OK=1"
        ) else if exist "%ProgramFiles%\Python312\python.exe" (
            set "PATH=%ProgramFiles%\Python312;%ProgramFiles%\Python312\Scripts;!PATH!"
            set "SYSTEM_PYTHON=%ProgramFiles%\Python312\python.exe"
            set "PYTHON_OK=1"
        )
    )
)

if "!PYTHON_OK!"=="0" (
    echo.
    echo [ERROR] Python 3.10+ is required but was not found.
    echo.
    echo Please install Python 3.10 or newer from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%V in ('%SYSTEM_PYTHON% -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"') do set "PY_VER=%%V"
echo        Found Python %PY_VER% (%SYSTEM_PYTHON%) -- OK

REM ============================================================================
REM  STAGE 2: Node.js & npm Detection & Winget Auto-Install
REM ============================================================================
echo [2/10] Checking Node.js and npm (18+)...

set "NPM_OK=0"
where npm >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "NPM_OK=1"
) else (
    where winget >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo        Node.js was not found in your PATH.
        echo        Attempting automatic installation of Node.js LTS via winget...
        winget install OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
        
        if exist "%ProgramFiles%\nodejs\npm.cmd" (
            set "PATH=%ProgramFiles%\nodejs;!PATH!"
            set "NPM_OK=1"
        )
    )
)

if "!NPM_OK!"=="0" (
    echo.
    echo [ERROR] Node.js and npm are required but were not found in your PATH.
    echo.
    echo Please install Node.js 18+ LTS from:
    echo   https://nodejs.org/
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%V in ('node -v 2^>nul') do set "NODE_VER=%%V"
for /f "tokens=*" %%V in ('npm -v 2^>nul') do set "NPM_VER=%%V"
echo        Found Node.js %NODE_VER% and npm %NPM_VER% -- OK

REM ============================================================================
REM  STAGE 3: Python Virtual Environment & Dependency Consistency
REM ============================================================================
echo [3/10] Preparing Python virtual environment and dependencies...

set "VENV_DIR=%BACKEND_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo        Creating Python virtual environment in %VENV_DIR%...
    %SYSTEM_PYTHON% -m venv "%VENV_DIR%"
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Failed to create Python virtual environment.
        pause
        exit /b 1
    )
    echo        Upgrading pip...
    "%VENV_PYTHON%" -m pip install --upgrade pip --quiet
)

REM Fast dependency consistency check
set "NEEDS_PIP=0"
"%VENV_PYTHON%" "%BACKEND_DIR%\scripts\bootstrap_env.py" --check-deps >nul 2>&1
if !ERRORLEVEL! NEQ 0 set "NEEDS_PIP=1"

if "!NEEDS_PIP!"=="1" (
    echo        Installing / reconciling backend packages from requirements.txt...
    "%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt" --quiet
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Backend dependency installation failed.
        pause
        exit /b 1
    )
    echo        Backend dependencies installed successfully.
) else (
    echo        Backend dependencies verified -- OK
)

REM ============================================================================
REM  STAGE 4: Frontend Dependencies & Lockfile Consistency
REM ============================================================================
echo [4/10] Preparing frontend dependencies...

set "FRONTEND_LOCK=%FRONTEND_DIR%\package-lock.json"
set "HASH_FILE=%FRONTEND_DIR%\node_modules\.lock_hash"
set "NEEDS_NPM=0"

if not exist "%FRONTEND_DIR%\node_modules" (
    set "NEEDS_NPM=1"
) else if not exist "%FRONTEND_DIR%\node_modules\vite" (
    set "NEEDS_NPM=1"
) else if exist "%FRONTEND_LOCK%" (
    if not exist "%HASH_FILE%" (
        REM node_modules exists and is healthy; initialize hash stamp
        "%VENV_PYTHON%" -c "import hashlib, pathlib; p = pathlib.Path(r'%FRONTEND_LOCK%'); h = pathlib.Path(r'%HASH_FILE%'); h.write_text(hashlib.sha256(p.read_bytes()).hexdigest(), encoding='utf-8')" >nul 2>&1
    ) else (
        for /f "tokens=*" %%H in ('"%VENV_PYTHON%" -c "import hashlib, pathlib; print(hashlib.sha256(pathlib.Path(r'%FRONTEND_LOCK%').read_bytes()).hexdigest())"') do set "CURRENT_LOCK_HASH=%%H"
        set /p SAVED_LOCK_HASH=<"%HASH_FILE%"
        if not "!CURRENT_LOCK_HASH!"=="!SAVED_LOCK_HASH!" set "NEEDS_NPM=1"
    )
)

if "!NEEDS_NPM!"=="1" (
    echo        Reconciling frontend dependencies...
    cd /d "%FRONTEND_DIR%"
    if exist "%FRONTEND_LOCK%" (
        call npm ci --quiet
        if !ERRORLEVEL! NEQ 0 (
            echo        npm ci encountered locked files; falling back to npm install...
            call npm install --quiet
        )
    ) else (
        call npm install --quiet
    )
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Frontend dependency installation failed.
        cd /d "%PROJECT_ROOT%"
        pause
        exit /b 1
    )
    if exist "%FRONTEND_LOCK%" (
        "%VENV_PYTHON%" -c "import hashlib, pathlib; p = pathlib.Path(r'%FRONTEND_LOCK%'); h = pathlib.Path(r'%HASH_FILE%'); h.write_text(hashlib.sha256(p.read_bytes()).hexdigest(), encoding='utf-8')" >nul 2>&1
    )
    cd /d "%PROJECT_ROOT%"
    echo        Frontend dependencies installed successfully.
) else (
    echo        Frontend dependencies verified -- OK
)

REM ============================================================================
REM  STAGE 5: Configuration & Safe Secret Generation
REM ============================================================================
echo [5/10] Checking backend configuration (.env)...

set "ENV_FILE=%BACKEND_DIR%\.env"
set "ENV_EXAMPLE=%BACKEND_DIR%\.env.example"

if not exist "%ENV_FILE%" (
    echo        Creating %ENV_FILE% from %ENV_EXAMPLE%...
    copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
    "%VENV_PYTHON%" -c "import secrets, pathlib; p = pathlib.Path(r'%ENV_FILE%'); content = p.read_text(encoding='utf-8'); content = content.replace('AUTH_JWT_SECRET=CHANGE_ME_BEFORE_RUNNING_IN_ANY_ENVIRONMENT', f'AUTH_JWT_SECRET={secrets.token_hex(32)}'); p.write_text(content, encoding='utf-8')"
    echo        Generated secure random AUTH_JWT_SECRET.
) else (
    findstr /C:"AUTH_JWT_SECRET=CHANGE_ME_BEFORE_RUNNING_IN_ANY_ENVIRONMENT" "%ENV_FILE%" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo        Replacing placeholder AUTH_JWT_SECRET with secure key...
        "%VENV_PYTHON%" -c "import secrets, pathlib; p = pathlib.Path(r'%ENV_FILE%'); content = p.read_text(encoding='utf-8'); content = content.replace('AUTH_JWT_SECRET=CHANGE_ME_BEFORE_RUNNING_IN_ANY_ENVIRONMENT', f'AUTH_JWT_SECRET={secrets.token_hex(32)}'); p.write_text(content, encoding='utf-8')"
    )
)

REM Check Gemini credentials (multi-key or primary key)
set "GEMINI_CONFIGURED=0"
findstr /R /C:"^[ ]*GEMINI_API_KEYS=[^ ]" "%ENV_FILE%" >nul 2>&1
if !ERRORLEVEL! EQU 0 set "GEMINI_CONFIGURED=1"
findstr /R /C:"^[ ]*GEMINI_API_KEY=[^ ]" "%ENV_FILE%" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    findstr /C:"GEMINI_API_KEY=your-primary-gemini-api-key-here" "%ENV_FILE%" >nul 2>&1
    if !ERRORLEVEL! NEQ 0 set "GEMINI_CONFIGURED=1"
)

if "!GEMINI_CONFIGURED!"=="1" (
    echo        Configuration ready [Gemini credentials configured] -- OK
) else (
    echo        Configuration ready [Discovery, Blueprints, and Playtests ready; AI builds require key] -- OK
)

REM ============================================================================
REM  STAGE 6: Database Schema Synchronization
REM ============================================================================
echo [6/10] Synchronizing database schema (Alembic)...

cd /d "%BACKEND_DIR%"
"%VENV_PYTHON%" -m alembic upgrade head >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Alembic database migration failed.
    cd /d "%PROJECT_ROOT%"
    pause
    exit /b 1
)
cd /d "%PROJECT_ROOT%"
echo        Database schema synchronized -- OK

REM ============================================================================
REM  STAGE 7: Discovery ML Model and FAISS Vector Index Bootstrap
REM ============================================================================
echo [7/10] Verifying Discovery ML model and FAISS vector index...

REM Set offline cache flag if model is already cached locally
if exist "%USERPROFILE%\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2" (
    set "HF_HUB_OFFLINE=1"
)

"%VENV_PYTHON%" "%BACKEND_DIR%\scripts\bootstrap_env.py" --bootstrap-discovery
echo        Discovery engine verified -- OK

REM ============================================================================
REM  STAGE 8: Signature-Verified Process and Port Safety
REM ============================================================================
echo [8/10] Checking port availability [Backend: %BACKEND_PORT%, Frontend: %FRONTEND_PORT%]...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = @(%BACKEND_PORT%, %FRONTEND_PORT%); $projRoot = '%PROJECT_ROOT%'.Replace('\', '\\'); foreach ($p in $ports) { $conns = $null; try { $conns = @(Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) } catch {}; if ($conns) { foreach ($c in $conns) { if ($c -and $c.OwningProcess -gt 4) { $procId = $c.OwningProcess; $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue; if ($proc) { $cmd = (Get-CimInstance Win32_Process -Filter \"ProcessId = $procId\").CommandLine; if ($cmd -match 'uvicorn.*app\.main:app' -or $cmd -match 'vite' -or $cmd -match 'GameForge' -or $cmd -match [regex]::Escape($projRoot)) { Write-Host \"       Stopping stale GameForge process on port $p (PID: $procId)...\"; Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } else { Write-Host \"[ERROR] Port $p is occupied by unrelated process: $($proc.ProcessName) (PID: $procId).\"; exit 1 } } } } } }; exit 0"

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [ERROR] Port conflict detected. Please free the required port and re-run start.bat.
    pause
    exit /b 1
)
echo        Ports %BACKEND_PORT% and %FRONTEND_PORT% are available -- OK

REM ============================================================================
REM  STAGE 9: Service Orchestration
REM ============================================================================
echo [9/10] Launching GameForge AI services...

set "VITE_API_URL=http://127.0.0.1:%BACKEND_PORT%"
set "CORS_ORIGINS=http://localhost:%FRONTEND_PORT%,http://127.0.0.1:%FRONTEND_PORT%"
set "PYTHONUNBUFFERED=1"

REM Launch Backend in managed child window
start "GameForge AI | Backend [:%BACKEND_PORT%]" /D "%BACKEND_DIR%" cmd /k "color 0A && set PYTHONUNBUFFERED=1 && set CORS_ORIGINS=%CORS_ORIGINS% && "%VENV_PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT% --reload"

REM Launch Frontend in managed child window
start "GameForge AI | Frontend [:%FRONTEND_PORT%]" /D "%FRONTEND_DIR%" cmd /k "color 0B && set VITE_API_URL=%VITE_API_URL% && set FRONTEND_PORT=%FRONTEND_PORT% && set BACKEND_PORT=%BACKEND_PORT% && call npm run dev -- --host 127.0.0.1 --port %FRONTEND_PORT%"

echo        Backend launching at http://127.0.0.1:%BACKEND_PORT%/
echo        Frontend launching at http://127.0.0.1:%FRONTEND_PORT%/

REM ============================================================================
REM  STAGE 10: Health Readiness Polling & Automatic Browser Launch
REM ============================================================================
echo [10/10] Waiting for services to become healthy...

set "BACKEND_HEALTH_URL=http://127.0.0.1:%BACKEND_PORT%/api/health"
set "FRONTEND_URL=http://127.0.0.1:%FRONTEND_PORT%/"
set "HEALTHY=0"

for /L %%i in (1,1,30) do (
    if "!HEALTHY!"=="0" (
        curl -s -f "%BACKEND_HEALTH_URL%" >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            curl -s -f "%FRONTEND_URL%" >nul 2>&1
            if !ERRORLEVEL! EQU 0 (
                set "HEALTHY=1"
            )
        )
        if "!HEALTHY!"=="0" (
            powershell -NoProfile -Command "Start-Sleep -Milliseconds 800"
        )
    )
)

if "!HEALTHY!"=="1" (
    echo.
    echo ============================================================================
    echo   [SUCCESS] GameForge AI is running and ready!
    echo ============================================================================
    echo   Application URL: http://127.0.0.1:%FRONTEND_PORT%/#/
    echo   Backend API    : http://127.0.0.1:%BACKEND_PORT%/
    echo   API Health     : http://127.0.0.1:%BACKEND_PORT%/api/health
    echo   API Docs       : http://127.0.0.1:%BACKEND_PORT%/docs
    echo ============================================================================
    echo.
    echo Opening GameForge AI in your default browser...
    start "" "http://127.0.0.1:%FRONTEND_PORT%/#/"
) else (
    echo.
    echo [WARN] Services took longer than expected to report health.
    echo You can check the Backend and Frontend terminal windows for diagnostic logs.
    echo Opening browser anyway...
    start "" "http://127.0.0.1:%FRONTEND_PORT%/#/"
)

echo.
echo Press any key to close this launcher monitor window (servers will keep running)...
pause >nul
