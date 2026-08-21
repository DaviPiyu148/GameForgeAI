# GameForge AI — Discovery Dataset Provenance

## Selected Dataset
**Steam Catalog Insights (October 2024)**

- **Source Repository**: `NewbieIndieGameDev/steam-insights` (GitHub)
- **Source URL**: `https://github.com/NewbieIndieGameDev/steam-insights`
- **Author / Maintainer**: `NewbieIndieGameDev`
- **Retrieval Date**: October 2024 / Ingested August 2026
- **License**: Public / Open community dataset exported from official Steam Store Web API and SteamSpy API.
- **Raw Archive Files**:
  - `games.zip` (4.1 MB compressed, 33.6 MB CSV uncompressed)
  - `genres.zip` (1.05 MB compressed, 7.0 MB CSV uncompressed)
  - `categories.zip` (1.7 MB compressed, 14.3 MB CSV uncompressed)
  - `tags.zip` (6.5 MB compressed, 38.2 MB CSV uncompressed)
  - `descriptions.zip` (93.3 MB compressed, 495 MB CSV uncompressed)
- **Total Record Count**: 140,082 unique Steam games (`app_id`)

---

## Source-Derived Facts vs. Project Decisions

### Source-Derived Facts
1. The dataset contains 140,082 games with titles, release dates, and free-to-play flags in `games.csv`.
2. Relational tables link games to 121 unique genres (353,339 mappings), 315 unique categories (522,582 mappings), and 447 unique community tags (1,744,632 mappings).
3. `descriptions.csv` provides summary and full overview text for 140,594 games.
4. Categories explicitly include player mode flags (`Single-player`, `Multi-player`, `Online PvP`, `Co-op`, `Shared/Split Screen`) and input capabilities (`Full controller support`, `VR Supported`).

### Project Decisions
1. **Primary Catalog**: We select `NewbieIndieGameDev/steam-insights` as the primary offline catalog for Phase B4.
2. **Offline Preprocessing**: In B4, we will filter for games with valid names, descriptions, genres, and tags, filtering out non-game assets and empty entries.
3. **Reproducibility**: Raw zip/csv files and generated vector embeddings (`.npy`, `.faiss`) are excluded from Git via `.gitignore` to maintain a lightweight repository.
4. **Secondary Enrichment**: IGDB API is designated as an optional future secondary enrichment layer (Phase B7/B8) and is **not** a dependency for core B4 discovery search.

---

## Directory Layout

```text
backend/data/
├── README.md               # Dataset provenance and instructions (this file)
├── dataset_audit.md        # Detailed audit, statistics, and field mapping
├── raw/                    # Raw downloaded and extracted CSV/ZIP files (git-ignored)
│   ├── games.csv
│   ├── genres.csv
│   ├── categories.csv
│   ├── tags.csv
│   └── descriptions.csv
└── processed/              # Normalized catalog JSON and precomputed embeddings (git-ignored)
    ├── games_catalog.json
    ├── games_embeddings.npy
    └── games_index.faiss
```

---

## How to Reproduce / Download Data

To download the raw dataset tables into `backend/data/raw/`:

```powershell
cd backend
python -c "
import os, urllib.request, zipfile
raw_dir = 'data/raw'
os.makedirs(raw_dir, exist_ok=True)
files = ['games.zip', 'genres.zip', 'categories.zip', 'tags.zip', 'descriptions.zip', 'reviews.zip']
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
