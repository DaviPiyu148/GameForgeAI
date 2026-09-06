# GameForge AI — Complete Setup Guide

> Follow every section in order. The whole process takes **~15–25 minutes** on a clean machine.

---

## Prerequisites

Install these tools **before** cloning the repo. All must be accessible from your terminal (`PATH`).

| Tool | Minimum Version | Download |
|---|---|---|
| **Python** | 3.11+ | https://python.org/downloads |
| **Node.js** | 18+ (LTS) | https://nodejs.org |
| **Git** | Any recent | https://git-scm.com |
| **curl** | Any | Pre-installed on Win 10/11 |

> **Windows tip:** When installing Python, tick **"Add Python to PATH"** on the first installer screen.

---

## Step 1 — Clone the Repository

```powershell
git clone <your-repo-url>
cd "AI Game"
```

---

## Step 2 — Backend Setup

### 2a. Create the Python virtual environment

```powershell
cd backend
python -m venv .venv
```

### 2b. Activate the virtual environment

**PowerShell (recommended on Windows):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Command Prompt:**
```cmd
.venv\Scripts\activate.bat
```

**Linux / macOS:**
```bash
source .venv/bin/activate
```

> Your prompt should now start with `(.venv)`.

### 2c. Install Python dependencies

```powershell
pip install -r requirements.txt
```

> This installs FastAPI, Uvicorn, SQLAlchemy, Sentence Transformers, FAISS, PyJWT, and all other backend packages.
> `sentence-transformers` will also download a small model (~90 MB) on first run.

### 2d. Configure environment variables

```powershell
copy .env.example .env
```

Open `backend\.env` in any text editor and fill in the required values:

```env
# REQUIRED — Get a free key at https://aistudio.google.com/
# For multi-account project isolation / failover, provide comma-separated keys or use GEMINI_API_KEYS
GEMINI_API_KEY=your-actual-gemini-api-key-here

# REQUIRED — Generate a strong secret (run this once):
# python -c "import secrets; print(secrets.token_hex(32))"
AUTH_JWT_SECRET=paste-the-output-here
```

Everything else in `.env` can stay at its default value for local development.

### 2e. Run database migrations

```powershell
python -m alembic upgrade head
```

This creates `backend\gameforge.db` (SQLite) with all tables.

---

## Step 3 — Download & Build the Discovery Index

The game catalog (~448 MB) and FAISS vector index (~30 MB) are **not** stored in Git (too large). You must build them once.

### 3a. Download the raw Steam dataset

Run this from inside the `backend/` folder with `.venv` active:

```powershell
python -c "
import os, urllib.request, zipfile
raw_dir = 'data/raw'
os.makedirs(raw_dir, exist_ok=True)
files = ['games.zip', 'genres.zip', 'categories.zip', 'tags.zip', 'descriptions.zip']
base_url = 'https://raw.githubusercontent.com/NewbieIndieGameDev/steam-insights/main/'
for f in files:
    target = os.path.join(raw_dir, f)
    if not os.path.exists(target):
        print(f'Downloading {f}...')
        urllib.request.urlretrieve(base_url + f, target)
    print(f'Extracting {f}...')
    with zipfile.ZipFile(target, 'r') as zf:
        zf.extractall(raw_dir)
print('Dataset ready in data/raw/')
"
```

> Downloads ~107 MB total (compressed). Extraction produces ~588 MB of CSV files.

### 3b. Ingest the catalog

```powershell
python scripts/bootstrap/ingest_catalog.py
```

Produces `data/processed/games_catalog.json` (~448 MB).

### 3c. Build the FAISS vector index

```powershell
python scripts/bootstrap/build_index.py --max-records 20000
```

Produces `data/processed/games_index.faiss` and `data/processed/index_meta.json`.
This step uses `sentence-transformers` to embed game descriptions — takes a few minutes on first run.

---

## Step 4 — Frontend Setup

```powershell
# From the repo root:
cd gameforge-ai
npm install
```

All frontend dependencies are tracked in `package-lock.json`, so this is fully reproducible.

---

## Step 5 — Run the Application

### Option A — One-click launcher (Windows only)

From the repo root, double-click **`start.bat`** or run it from a terminal:

```cmd
start.bat
```

This script automatically:
- Verifies the Python venv exists (errors with instructions if missing)
- Copies `.env.example` to `.env` if `.env` is missing
- Runs `npm install` if `node_modules` is missing
- Runs Alembic migrations
- Clears ports 8000 / 5173 of any stale processes
- Launches Backend and Frontend in separate windows
- Health-checks the backend and opens the browser

### Option B — Manual (cross-platform)

**Terminal 1 — Backend:**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
# OR: source .venv/bin/activate       # Linux / macOS
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```powershell
cd gameforge-ai
npm run dev -- --host 127.0.0.1 --port 5173
```

Then open **http://127.0.0.1:5173/#/** in your browser.

---

## Verify Everything Works

| Check | URL / Command |
|---|---|
| Backend health | http://127.0.0.1:8000/api/health |
| API docs (Swagger) | http://127.0.0.1:8000/docs |
| Frontend app | http://127.0.0.1:5173/#/ |
| Backend tests | `cd backend && pytest -v` (430 passing tests) |

---

## What Is and Isn't in Git

| Included in Git ✅ | Must be created locally ❌ |
|---|---|
| All source code | `backend/.venv/` — Python virtual environment |
| `requirements.txt` | `backend/.env` — secrets and API keys |
| `package.json` + `package-lock.json` | `gameforge-ai/node_modules/` — npm packages |
| Alembic migration scripts | `backend/gameforge.db` — SQLite database |
| `start.bat` one-click launcher | `backend/data/raw/*.csv` — raw Steam CSV data |
| `.env.example` template | `backend/data/processed/` — catalog JSON + FAISS index |

---

## Troubleshooting

### `python` not recognized
Install Python 3.11+ and make sure **"Add Python to PATH"** was checked during installation. Restart your terminal.

### PowerShell execution policy error (`Activate.ps1`)
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### `pip install` fails on `faiss-cpu`
Use Python 3.11 or 3.12. Pre-built `faiss-cpu` wheels are not yet published for Python 3.13+.

### `npm` not recognized
Install Node.js 18 LTS from https://nodejs.org and restart your terminal.

### Backend starts but discovery search returns no results
The FAISS index was not built. Complete Steps 3a–3c.

### `GEMINI_API_KEY` error at startup
Ensure `backend/.env` exists and contains a real Gemini API key (or `GEMINI_API_KEYS` list).

### Port already in use (8000 or 5173)
`start.bat` clears stale processes automatically. For manual runs, kill the conflicting process or choose a different port number.

### `sentence-transformers` downloads models on first run
This is expected. The default model is ~90 MB and is cached in `~/.cache/huggingface/`. Subsequent runs use the cache.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` / `GEMINI_API_KEYS` | **Yes** | — | Google Gemini API key(s) for AI generation (supports comma-separated multi-account failover) |
| `AUTH_JWT_SECRET` | **Yes** | — | Secret for signing JWT auth tokens (min 16 chars) |
| `AI_TRANSPORT` | No | `interactions` | `interactions` (Google Gemini Interactions API) or `legacy_http` |
| `APP_ENV` | No | `development` | `development` or `production` |
| `DATABASE_URL` | No | `sqlite:///./gameforge.db` | SQLAlchemy database URL |
| `CORS_ORIGINS` | No | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed CORS origins |
| `GEMINI_MODEL` | No | `gemini-3.7-flash` | Default Gemini model (superseded by task model chains) |
| `AI_TIMEOUT_SECONDS` | No | `60` | AI per-attempt request timeout in seconds |
| `AI_OVERALL_DEADLINE_SECONDS` | No | `60` | Overall budget deadline across all key and model fallback attempts |
| `AI_MAX_RETRIES` | No | `2` | Max AI retry attempts |
| `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | JWT token lifetime in minutes |
