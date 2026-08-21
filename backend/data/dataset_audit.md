# GameForge AI — B4 Dataset Audit & Discovery Field Map

## 1. Candidate Datasets Evaluation

| Candidate | Size & Format | Metadata Richness | Descriptions / Tags / Categories | License & Access | Verdict |
|---|---|---|---|---|---|
| **A. Steam Insights (`NewbieIndieGameDev/steam-insights`)** | ~110 MB compressed ZIPs, relational CSVs | **High**: Titles, genres, tags, categories, descriptions, release dates, SteamSpy stats | **Full**: Complete summary descriptions, 121 genres, 315 categories (multiplayer, coop), 447 tags | Open public GitHub repository; direct download; zero credentials required | **SELECTED PRIMARY SOURCE** |
| **B. Crawlora Steam Catalog (`Crawlora-org/crawlora-mcp`)** | Hosted remote MCP tool | Moderate | Variable per MCP query | Requires live MCP / network connection; not an offline static dataset | Rejected as primary offline catalog |
| **C. Steam Games Complete (`trolukovich/steam-games-complete-dataset`)** | ~80 MB CSV | Moderate: ~40k games (older snapshot) | Decent descriptions and tags | Kaggle account / API authentication required; occasionally unavailable | Rejected in favor of direct GitHub download |
| **D. IGDB API** | Remote REST / GraphQL | High commercial metadata | Full IGDB taxonomy | Requires Twitch/Amazon OAuth credentials and rate-limited live queries | Designated for optional future enrichment (B7/B8), not core B4 |

---

## 2. Selected Dataset Audit (`NewbieIndieGameDev/steam-insights`)

### Raw Table Metrics

| Table File | Raw Size | Total Rows | Unique Games (`app_id`) | Description & Coverage |
|---|---|---|---|---|
| `games.csv` | 33.6 MB | 140,082 | 140,082 | Base game metadata (App ID, title, release date, is_free, price info). **0 null titles**. |
| `genres.csv` | 7.0 MB | 353,339 | 122,458 | 121 unique genres (Action, RPG, Strategy, Indie, Casual, Adventure, etc.). |
| `categories.csv` | 14.3 MB | 522,582 | 134,393 | 315 unique categories (Single-player, Multi-player, Online PvP, Co-op, Full controller support). |
| `tags.csv` | 38.2 MB | 1,744,632 | 117,505 | 447 unique community tags (Roguelike, Cyberpunk, Soulslike, Pixel Graphics, 2D Platformer, etc.). |
| `descriptions.csv` | 495.4 MB | 141,363 | 140,594 | Summary and detailed gameplay overview text for 140,594 games. |

---

## 3. Discovery Field Map

The mapping below outlines how raw table columns will be consumed across preprocessing, semantic embeddings, structured hard filters, and discovery response envelopes:

| Raw Source Column | Normalized Field | In Semantic Profile / Embedding | In Hard Filter | In Search Response | Notes |
|---|---|---|---|---|---|
| `games.csv:app_id` | `id` / `external_id` | No | No | **Yes** | Server-owned / Steam App ID for external link / identification |
| `games.csv:name` | `title` | **Yes** (Primary header) | No | **Yes** | Trimmed, non-empty text |
| `games.csv:release_date` | `release_year` | No | **Yes** (`min_year`, `max_year`) | **Yes** | Extracted 4-digit year (e.g. 2023) |
| `games.csv:is_free` | `is_free` | **Yes** ("Free to Play") | **Yes** (Boolean flag) | **Yes** | Useful for price constraints |
| `descriptions.csv:summary` | `description` | **Yes** (Core narrative) | No | **Yes** | Cleaned plain text summary (HTML tags stripped) |
| `genres.csv:genre` | `genres` | **Yes** (Genre list) | **Yes** (Exact genre filter) | **Yes** | Normalized list of strings (e.g. `["Action", "RPG"]`) |
| `tags.csv:tag` | `tags` | **Yes** (Community tags) | **Yes** (Tag match / bonus) | **Yes** | Top community tags (e.g. `["Cyberpunk", "Roguelite"]`) |
| `categories.csv:category` | `player_modes` / `platforms` | **Yes** (Player modes & features) | **Yes** (`multiplayer`, `single_player`, `coop`, `controller`) | **Yes** | Categorized into structured boolean capabilities and platform flags |

---

## 4. Semantic Profile Construction Specification

For each game, the deterministic text profile used to generate Sentence Transformer embeddings will be structured as:

```text
Title: {title}
Genres: {", ".join(genres)}
Tags: {", ".join(tags[:10])}
Modes: {", ".join(player_modes)}
Description: {clean_summary}
```

This ensures semantic queries such as *"fast paced cyberpunk roguelite with multiplayer support"* match against title, tags, modes, and description with high cosine similarity.

---

## 5. Licensing & Provenance Statement

- **Data Origin**: Public game metadata indexed from the official Steam Store Web API and SteamSpy public API.
- **Redistribution Policy**: Raw compressed archives and full uncompressed CSV files are stored locally in `backend/data/raw/` and excluded from Git via `.gitignore`.
- **Derived Artifacts**: Preprocessing scripts and lightweight evaluation fixtures are tracked in the repository to guarantee 100% reproducible catalog generation.
