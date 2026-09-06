"""
GameForge AI — Environment & Discovery Bootstrap Helper (bootstrap_env.py)

Purpose:
  Internal helper called by start.bat to handle project-specific Python validation,
  dependency consistency checks, model caching, and FAISS vector index bootstrapping.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"
RAW_DIR = BACKEND_DIR / "data" / "raw"
CATALOG_PATH = PROCESSED_DIR / "games_catalog.json"
INDEX_PATH = PROCESSED_DIR / "games_index.faiss"
META_PATH = PROCESSED_DIR / "index_meta.json"
REVIEWED_INDEX_PATH = PROCESSED_DIR / "games_index_reviewed_only.faiss"
REVIEWED_META_PATH = PROCESSED_DIR / "index_meta_reviewed_only.json"
REQUIREMENTS_PATH = BACKEND_DIR / "requirements.txt"
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# Dataset source: NewbieIndieGameDev/steam-insights (Steam Store & SteamSpy open export)
# Pinned immutable revision: 5c47942127ef6905a415ff6815cf137803e73507 (October 2024 export)
PINNED_DATASET_URL_BASE = "https://raw.githubusercontent.com/NewbieIndieGameDev/steam-insights/5c47942127ef6905a415ff6815cf137803e73507/"


def compute_catalog_fingerprint(catalog_file: Path) -> Optional[str]:
    """
    Compute a stable, fast catalog fingerprint combining file size,
    first 8KB hash, and last 8KB hash. Does not change on simple file copy/mtime change.
    """
    if not catalog_file.exists():
        return None
    try:
        size = catalog_file.stat().st_size
        if size == 0:
            return None
        hasher = hashlib.sha256()
        hasher.update(str(size).encode("utf-8"))
        with open(catalog_file, "rb") as f:
            hasher.update(f.read(8192))
            if size > 16384:
                f.seek(size - 8192)
                hasher.update(f.read(8192))
        return hasher.hexdigest()
    except Exception as e:
        print(f"[WARN] Failed to compute catalog fingerprint: {e}")
        return None


def check_python_dependencies() -> bool:
    """
    Verify that all distributions in requirements.txt are installed and version-compatible.
    Returns True if healthy, False if any package is missing or outdated.
    """
    if not REQUIREMENTS_PATH.exists():
        print(f"[WARN] requirements.txt not found at {REQUIREMENTS_PATH}")
        return True

    try:
        import importlib.metadata
    except ImportError:
        return False

    all_satisfied = True
    with open(REQUIREMENTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue

            # Strip extras and comments for packaging lookup
            clean_spec = raw.split("#")[0].strip()
            pkg_name = clean_spec.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip()

            try:
                dist = importlib.metadata.distribution(pkg_name)
                # Check version constraint if pinned with ==
                if "==" in clean_spec:
                    required_ver = clean_spec.split("==")[1].strip()
                    if dist.version != required_ver:
                        print(f"[WARN] Dependency version mismatch for {pkg_name}: installed {dist.version}, required == {required_ver}")
                        all_satisfied = False
            except importlib.metadata.PackageNotFoundError:
                print(f"[WARN] Required Python package missing: {pkg_name}")
                all_satisfied = False

    return all_satisfied


def ensure_model(model_name: str = DEFAULT_MODEL_NAME) -> Tuple[bool, Optional[int]]:
    """
    Load the SentenceTransformer embedding model, downloading it if not present in cache.
    Returns (success, embedding_dimension).
    """
    print(f"Checking SentenceTransformer embedding model: {model_name}...")
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        if hasattr(model, "get_embedding_dimension"):
            dim = model.get_embedding_dimension()
        elif hasattr(model, "get_sentence_embedding_dimension"):
            dim = model.get_sentence_embedding_dimension()
        else:
            dim = 384
        print(f"Embedding model loaded successfully (dimension={dim}).")
        return True, dim
    except Exception as e:
        print(f"[WARN] Model load failed: {e}. Attempting online download/repair...")
        try:
            # Temporarily unset offline mode for download
            old_offline = os.environ.pop("HF_HUB_OFFLINE", None)
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(model_name)
            dim = model.get_sentence_embedding_dimension() if hasattr(model, "get_sentence_embedding_dimension") else 384
            if old_offline is not None:
                os.environ["HF_HUB_OFFLINE"] = old_offline
            print(f"Embedding model downloaded and verified successfully (dimension={dim}).")
            return True, dim
        except Exception as dl_err:
            print(f"[ERROR] Failed to download SentenceTransformer model: {dl_err}")
            return False, None


def ensure_raw_and_catalog() -> bool:
    """
    Ensure games_catalog.json exists. If missing, attempts ingestion from raw/ or downloads raw zips.
    """
    if CATALOG_PATH.exists() and CATALOG_PATH.stat().st_size > 1024:
        return True

    print(f"Catalog file not found at {CATALOG_PATH}. Checking raw data in {RAW_DIR}...")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    games_csv = RAW_DIR / "games.csv"
    if not games_csv.exists():
        print(f"Raw dataset CSVs missing. Downloading pinned archives from {PINNED_DATASET_URL_BASE}...")
        import urllib.request
        import zipfile
        files = ["games.zip", "genres.zip", "categories.zip", "tags.zip", "descriptions.zip", "reviews.zip"]
        for f in files:
            target_zip = RAW_DIR / f
            if not target_zip.exists():
                url = PINNED_DATASET_URL_BASE + f
                print(f"  Downloading {f}...")
                try:
                    urllib.request.urlretrieve(url, str(target_zip))
                except Exception as e:
                    print(f"[ERROR] Failed to download {url}: {e}")
                    return False
            print(f"  Extracting {f}...")
            try:
                with zipfile.ZipFile(str(target_zip), "r") as zf:
                    zf.extractall(str(RAW_DIR))
            except Exception as e:
                print(f"[ERROR] Failed to extract {target_zip}: {e}")
                return False

    print("Running catalog ingestion script (ingest_catalog.py)...")
    try:
        from backend.scripts.bootstrap.ingest_catalog import ingest_catalog  # type: ignore
        ingest_catalog()
    except Exception:
        # Fallback to subprocess in case of relative path issues
        import subprocess
        res = subprocess.run([sys.executable, str(BACKEND_DIR / "scripts" / "bootstrap" / "ingest_catalog.py")], cwd=str(BACKEND_DIR))
        if res.returncode != 0:
            print("[ERROR] ingest_catalog.py failed.")
            return False

    return CATALOG_PATH.exists() and CATALOG_PATH.stat().st_size > 1024


def validate_faiss_index(
    model_dim: int,
    catalog_fp: str,
    index_file: Optional[Path] = None,
    meta_file: Optional[Path] = None,
) -> bool:
    """
    Perform a complete health and freshness validation of a FAISS index.
    """
    target_index = index_file or INDEX_PATH
    target_meta = meta_file or META_PATH

    if not target_index.exists() or not target_meta.exists():
        return False

    try:
        import faiss
        index = faiss.read_index(str(target_index))
        with open(target_meta, "r", encoding="utf-8") as f:
            meta = json.load(f)

        record_count = meta.get("record_count", 0)
        id_mapping = meta.get("id_mapping", [])
        stored_fp = meta.get("catalog_fingerprint")

        # 1. Vector count match
        if index.ntotal == 0 or index.ntotal != record_count or len(id_mapping) != index.ntotal:
            print(f"[WARN] FAISS vector count mismatch for {target_index.name}: index.ntotal={index.ntotal}, meta={record_count}")
            return False

        # 2. Embedding dimension match
        if index.d != model_dim:
            print(f"[WARN] FAISS dimension mismatch for {target_index.name}: index.d={index.d}, model_dim={model_dim}")
            return False

        # 3. Catalog freshness match
        if stored_fp and catalog_fp and stored_fp != catalog_fp:
            print(f"[INFO] Catalog fingerprint changed for {target_index.name}. Vector index is stale.")
            return False

        # 4. Search probe test
        import numpy as np
        probe_vec = np.zeros((1, index.d), dtype=np.float32)
        _, indices = index.search(probe_vec, 1)
        if indices.shape != (1, 1):
            return False

        return True
    except Exception as e:
        print(f"[WARN] FAISS index validation failed for {target_index.name}: {e}")
        return False


def build_faiss_index() -> bool:
    """
    Build primary FAISS vector index (20,000 records) and save with catalog fingerprint.
    """
    print("Building primary FAISS Discovery vector index (20,000 records)...")
    import subprocess
    res = subprocess.run(
        [sys.executable, str(BACKEND_DIR / "scripts" / "build_index.py"), "--max-records", "20000"],
        cwd=str(BACKEND_DIR),
    )
    return res.returncode == 0 and INDEX_PATH.exists() and META_PATH.exists()


def build_reviewed_faiss_index() -> bool:
    """
    Build reviewed-only FAISS vector index (87,890 records) and save with catalog fingerprint.
    """
    print("Building reviewed-only FAISS Discovery vector index (87,890 records)...")
    import subprocess
    res = subprocess.run(
        [sys.executable, str(BACKEND_DIR / "scripts" / "build_index.py"), "--reviewed-only"],
        cwd=str(BACKEND_DIR),
    )
    return res.returncode == 0 and REVIEWED_INDEX_PATH.exists() and REVIEWED_META_PATH.exists()


def bootstrap_discovery() -> bool:
    """
    Full self-healing Discovery bootstrap pipeline:
      Model -> Raw Data -> Catalog -> Primary Index (20k) -> Reviewed Index (87,890).
    """
    # 1. Verify / Download Model
    model_ok, model_dim = ensure_model()
    if not model_ok or model_dim is None:
        print("[WARN] Discovery model unavailable. Core application will start, but Discovery search will be degraded.")
        return False

    # 2. Verify / Ingest Catalog
    catalog_ok = ensure_raw_and_catalog()
    if not catalog_ok:
        print("[WARN] Discovery catalog unavailable. Discovery search will be degraded.")
        return False

    catalog_fp = compute_catalog_fingerprint(CATALOG_PATH) or ""

    # 3. Validate / Build Primary FAISS Index (20k)
    if not validate_faiss_index(model_dim, catalog_fp, INDEX_PATH, META_PATH):
        print("Primary FAISS index (20k) missing, corrupted, or stale. Rebuilding...")
        build_ok = build_faiss_index()
        if not build_ok:
            print("[WARN] Failed to build primary FAISS index. Discovery search will use lexical fallback.")
            return False

        # Re-verify after build
        if not validate_faiss_index(model_dim, catalog_fp, INDEX_PATH, META_PATH):
            print("[WARN] Primary FAISS index post-build validation failed.")
            return False

    # 4. Validate / Self-Heal Reviewed-Only FAISS Index (87,890 records for HIDDEN_GEMS)
    if not validate_faiss_index(model_dim, catalog_fp, REVIEWED_INDEX_PATH, REVIEWED_META_PATH):
        # Check if legacy benchmark path exists to avoid unnecessary rebuild
        legacy_reviewed = BACKEND_DIR / "data" / "benchmark_indexes" / "games_index_reviewed_only.faiss"
        legacy_meta = BACKEND_DIR / "data" / "benchmark_indexes" / "index_meta_reviewed_only.json"
        if legacy_reviewed.exists() and legacy_meta.exists():
            print("[INFO] Migrating reviewed-only FAISS index from benchmark directory to processed/...")
            import shutil
            shutil.copy2(legacy_reviewed, REVIEWED_INDEX_PATH)
            shutil.copy2(legacy_meta, REVIEWED_META_PATH)

        if not validate_faiss_index(model_dim, catalog_fp, REVIEWED_INDEX_PATH, REVIEWED_META_PATH):
            print("[INFO] Reviewed-only FAISS index missing or stale. Generating (87,890 records)...")
            build_rev_ok = build_reviewed_faiss_index()
            if not build_rev_ok:
                print("[WARN] Reviewed-only FAISS index generation failed; HIDDEN_GEMS will fall back to primary 20k index safely.")
            else:
                print("Reviewed-only FAISS index successfully built and verified.")
        else:
            print("Reviewed-only FAISS index verified and ready.")
    else:
        print("Reviewed-only FAISS index verified and ready.")

    print("Discovery vector indexes & embedding pipeline verified and ready.")
    return True



FRONTEND_DIR = PROJECT_ROOT / "gameforge-ai"
FRONTEND_LOCK = FRONTEND_DIR / "package-lock.json"
NODE_MODULES_DIR = FRONTEND_DIR / "node_modules"
LOCK_HASH_FILE = NODE_MODULES_DIR / ".lock_hash"


def compute_lockfile_hash() -> Optional[str]:
    """Compute SHA-256 hash of gameforge-ai/package-lock.json."""
    if not FRONTEND_LOCK.exists():
        return None
    try:
        return hashlib.sha256(FRONTEND_LOCK.read_bytes()).hexdigest()
    except Exception as e:
        print(f"[WARN] Failed to read package-lock.json: {e}")
        return None


def check_frontend_dependencies() -> bool:
    """
    Verify frontend dependencies:
    Returns True if node_modules exists, contains vite, and .lock_hash matches package-lock.json.
    Returns False if node_modules is missing/corrupted or package-lock.json hash has changed.
    """
    if not NODE_MODULES_DIR.exists():
        return False
    if not (NODE_MODULES_DIR / "vite").exists():
        return False
    if not FRONTEND_LOCK.exists():
        return True
    if not LOCK_HASH_FILE.exists():
        return False

    current_hash = compute_lockfile_hash()
    if not current_hash:
        return False

    try:
        saved_hash = LOCK_HASH_FILE.read_text(encoding="utf-8").strip()
        return current_hash == saved_hash
    except Exception:
        return False


def stamp_frontend_dependencies() -> bool:
    """
    Record current SHA-256 hash of package-lock.json into node_modules/.lock_hash.
    Must be called only after successful npm ci/install.
    """
    if not FRONTEND_LOCK.exists():
        return True
    current_hash = compute_lockfile_hash()
    if not current_hash:
        return False
    try:
        NODE_MODULES_DIR.mkdir(parents=True, exist_ok=True)
        LOCK_HASH_FILE.write_text(current_hash, encoding="utf-8")
        return True
    except Exception as e:
        print(f"[WARN] Failed to write .lock_hash: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="GameForge AI Bootstrap & Environment Helper")
    parser.add_argument("--check-deps", action="store_true", help="Check Python dependency consistency against requirements.txt")
    parser.add_argument("--check-frontend-deps", action="store_true", help="Check frontend node_modules & lockfile consistency")
    parser.add_argument("--stamp-frontend-deps", action="store_true", help="Record current lockfile hash to node_modules/.lock_hash")
    parser.add_argument("--bootstrap-discovery", action="store_true", help="Ensure embedding model, catalog, and FAISS index are initialized")
    parser.add_argument("--check-discovery", action="store_true", help="Diagnostic check of discovery components")
    args = parser.parse_args()

    if args.check_deps:
        is_ok = check_python_dependencies()
        sys.exit(0 if is_ok else 1)

    if args.check_frontend_deps:
        is_ok = check_frontend_dependencies()
        sys.exit(0 if is_ok else 1)

    if args.stamp_frontend_deps:
        is_ok = stamp_frontend_dependencies()
        sys.exit(0 if is_ok else 1)

    if args.bootstrap_discovery:
        is_ok = bootstrap_discovery()
        # Return 0 so launcher can proceed even if Discovery is gracefully degraded
        sys.exit(0)

    if args.check_discovery:
        model_ok, model_dim = ensure_model()
        catalog_fp = compute_catalog_fingerprint(CATALOG_PATH) or ""
        index_ok = validate_faiss_index(model_dim or 384, catalog_fp) if model_ok else False
        print(f"Discovery Health Summary: Model={model_ok} (dim={model_dim}), Catalog={CATALOG_PATH.exists()}, FAISS={index_ok}")
        sys.exit(0 if (model_ok and index_ok) else 1)

    print("No mode specified. Use --check-deps, --check-frontend-deps, or --bootstrap-discovery.")
    sys.exit(0)


if __name__ == "__main__":
    main()
