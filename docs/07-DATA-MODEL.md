# 07 — Data Model

## Modeling Rule
Keep these distinct:
1. database models,
2. API schemas,
3. frontend interfaces,
4. Game DSL schema.

---

## Implemented Database Entities (B1–B7)

### User (SQLAlchemy Model: `users`, B7)
- `id`: String(36) (Primary Key, server-generated UUID)
- `email`: String(254), unique, non-null, indexed (stored lowercase)
- `username`: String(50), unique, non-null, indexed
- `password_hash`: String(255), non-null (Argon2 hash via `pwdlib`; NEVER returned in API responses)
- `level`: Integer, non-null, default: `1`
- `created_at`: DateTime(timezone=True), non-null, auto timestamp
- `updated_at`: DateTime(timezone=True), non-null, auto timestamp

### SavedDiscovery (SQLAlchemy Model: `saved_discoveries`, B7)
- `id`: String(36) (Primary Key, server-generated UUID)
- `user_id`: String(36), non-null, indexed (FK to `users.id` with `ondelete="CASCADE"`)
- `steam_app_id`: String(50), non-null (Steam catalog identifier)
- `created_at`: DateTime(timezone=True), non-null, auto timestamp
- Constraint: `UNIQUE(user_id, steam_app_id)`

### Project (SQLAlchemy Model: `projects`, B1, extended B5, B7, G12)
- `id`: String(36) (Primary Key, server-generated UUID)
- `user_id`: String(36), nullable, indexed (FK to `users.id` with `ondelete="SET NULL"`, added in B7)
- `title`: String(255), non-null
- `genre`: String(100), non-null, default: `"Generated Concept"`
- `prompt`: Text, non-null
- `status`: String(50), non-null, default: `"PLAYABLE"` (allowed: `PLAYABLE`, `COMPILING`, `ERROR`)
- `engine`: String(100), non-null, default: `"Top-Down Action"`
- `art_density`: Integer, non-null, default: `50` (0-100)
- `physics`: Integer, non-null, default: `80` (0-100)
- `modules`: JSON, non-null, default: `[]`
- `design_spec`: JSON, nullable (Structured GameDesignSpec added in G12)
- `game_dsl`: JSON, nullable (Accepted/current playable Game DSL snapshot, added in B5)
- `runtime_metadata`: JSON, nullable (Engine versioning and deterministic seed, added in B5)
- `current_version`: Integer, non-null, default: `1` (added in G12)
- `created_at`: DateTime(timezone=True), non-null, auto timestamp
- `updated_at`: DateTime(timezone=True), non-null, auto timestamp

### PlaytestSession (SQLAlchemy Model: `playtest_sessions`, G12)
- `id`: String(36) (Primary Key, server-generated UUID)
- `project_id`: String(36), non-null, indexed (FK to `projects.id` with `ondelete="CASCADE"`)
- `user_id`: String(36), non-null, indexed (FK to `users.id` with `ondelete="CASCADE"`)
- `duration_seconds`: Integer, non-null, default: `0`
- `score`: Integer, non-null, default: `0`
- `damage_taken`: Integer, non-null, default: `0`
- `damage_dealt`: Integer, non-null, default: `0`
- `enemies_defeated`: Integer, non-null, default: `0`
- `collectibles_gathered`: Integer, non-null, default: `0`
- `objectives_completed`: Integer, non-null, default: `0`
- `outcome`: String(50), non-null, default: `"PLAYED"` (`"WON"`, `"LOST"`, `"ABANDONED"`, `"PLAYED"`)
- `telemetry_events`: JSON, nullable (Recent event stream)
- `ai_analysis`: JSON, nullable (Cached AI Playtest Critique output)
- `created_at`: DateTime(timezone=True), non-null, auto timestamp

### ProjectVersion (SQLAlchemy Model: `project_versions`, G12)
- `id`: String(36) (Primary Key, server-generated UUID)
- `project_id`: String(36), non-null, indexed (FK to `projects.id` with `ondelete="CASCADE"`)
- `version_number`: Integer, non-null, default: `1`
- `game_dsl`: JSON, non-null
- `design_spec`: JSON, nullable
- `change_summary`: Text, nullable
- `created_at`: DateTime(timezone=True), non-null, auto timestamp

### BuildJob (SQLAlchemy Model: `build_jobs`, B2, extended B3 & B7)
- `id`: String(36) (Primary Key, server-generated UUID)
- `user_id`: String(36), nullable, indexed (FK to `users.id` with `ondelete="SET NULL"`, added in B7)
- `project_id`: String(36), nullable, indexed (populated upon SUCCESS)
- `prompt`: Text, non-null
- `engine`: String(100), non-null, default: `"Phaser"`
- `art_density`: Integer, non-null, default: `50` (0-100)
- `physics`: Integer, non-null, default: `80` (0-100)
- `modules`: JSON, non-null, default: `[]`
- `status`: String(50), non-null, indexed (`QUEUED`, `RUNNING`, `VALIDATING`, `SUCCESS`, `ERROR`)
- `error_code`: String(100), nullable
- `error_message`: Text, nullable
- `game_dsl`: JSON, nullable (Validated Game DSL Schema artifact added in B3)
- `created_at`: DateTime(timezone=True), non-null, auto timestamp
- `started_at`: DateTime(timezone=True), nullable
- `completed_at`: DateTime(timezone=True), nullable

### BuildLog (SQLAlchemy Model: `build_logs`, B2)
- `id`: String(36) (Primary Key, server-generated UUID)
- `build_id`: String(36), non-null, indexed
- `sequence_number`: Integer, non-null (1-indexed per build)
- `level`: String(20), non-null (`INFO`, `WARNING`, `ERROR`, `SUCCESS`)
- `message`: Text, non-null
- `timestamp`: DateTime(timezone=True), non-null, auto timestamp
- Unique index: `(build_id, sequence_number)`

---

## Three-Layer Discovery Catalog Metadata Model (Discovery 2.2)
To guarantee high-quality search retrieval while delivering clean English user-facing presentation and preserving data provenance, GameForge AI structures game catalog records into three decoupled layers:

### 1. ORIGINAL Layer (Provenance Preservation)
- `original_title`: Exact raw title as scraped from Steam.
- `original_description`: Exact raw description text (immutable source provenance).
- `original_genres`: Unmodified source genre list (e.g. `['Инди', 'Ролевые игры']` or `['冒险', '动作']`).
- `original_tags`: Raw Steam community tags.
- `original_categories`: Raw Steam category metadata.

### 2. SEARCH Layer (Retrieval Optimization)
- `canonical_genres`: Standardized English genre taxonomy (e.g. `['Indie', 'RPG']`).
- `search_tags`: Normalized, constituent-word split search tokens.
- `search_description`: Combined English profile text for dense semantic embeddings.
- `semantic_profile`: Rich profile string embedded into 384-dimensional FAISS vector space.

### 3. DISPLAY Layer (User-Facing Presentation)
- `display_title`: Canonical English title for clean UI rendering.
- `display_description`: Human-readable English description (native English source, normalized English synopsis, or enriched IGDB summary).
- `display_genres`: Clean English genre tags.
- `display_tags`: Informative, high-signal gameplay tags (with low-signal noise filtered).
- `description_language`: ISO language code (`"en"`, `"ru"`, `"zh"`, `"es"`, `"fr"`, etc.).
- `description_source`: Provenance of the active display description:
  - `"steam"`: Native English source description from Steam.
  - `"normalized"`: Structured English synopsis generated from canonical metadata.
  - `"igdb"`: Enriched English summary from verified IGDB mapping.
  - `"original"`: Raw localized description fallback when no English source or tags exist.

---

## Ownership & IDOR Protection (Phase B7)
All user-specific entities (`Project`, `BuildJob`, `SavedDiscovery`) enforce ownership via `user_id`. When querying by ID, owner mismatch returns `404 Not Found` (never `403 Forbidden`) to prevent resource enumeration.
