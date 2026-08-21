import csv
import json
import os
import re
import time
from typing import Any, Dict, List, Set, Tuple


HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


PUNCT_SPACE_RE = re.compile(r"\s+([.,!?;:])")


def clean_text(text: str) -> str:
    """Strip HTML tags, normalize punctuation spacing, and normalize whitespace."""
    if not text:
        return ""
    stripped = HTML_TAG_RE.sub(" ", text)
    stripped = PUNCT_SPACE_RE.sub(r"\1", stripped)
    normalized = WHITESPACE_RE.sub(" ", stripped).strip()
    return normalized


def extract_year(date_str: str) -> int:
    """Extract 4-digit release year from date string (e.g. '2023-05-12' or '2023')."""
    if not date_str:
        return 0
    match = re.search(r"\b(19\d\d|20\d\d)\b", date_str)
    return int(match.group(1)) if match else 0


# Comprehensive multilingual genre map (Russian, Ukrainian, Chinese, Japanese, Spanish, French, German)
EXPANDED_GENRE_MAP = {
    # Russian / Ukrainian
    "инди": "Indie",
    "ролевые игры": "RPG",
    "симуляторы": "Simulation",
    "бесплатные": "Free to Play",
    "бесплатно": "Free to Play",
    "экшены": "Action",
    "приключенческие игры": "Adventure",
    "стратегии": "Strategy",
    "казуальные игры": "Casual",
    "гонки": "Racing",
    "спортивные игры": "Sports",
    "ммо": "Massively Multiplayer",
    "многопользовательские игры": "Massively Multiplayer",
    "ранний доступ": "Early Access",
    "насилие": "Violent",
    "мясо": "Gore",
    "пригоди": "Adventure",
    "бойовики": "Action",
    "казуальні ігри": "Casual",
    "інді": "Indie",
    # Chinese (Simplified & Traditional)
    "角色扮演": "RPG",
    "独立": "Indie",
    "獨立": "Indie",
    "獨立製作": "Indie",
    "动作": "Action",
    "動作": "Action",
    "冒险": "Adventure",
    "冒險": "Adventure",
    "模拟": "Simulation",
    "模擬": "Simulation",
    "策略": "Strategy",
    "休闲": "Casual",
    "休閒": "Casual",
    "免费开玩": "Free to Play",
    "抢先体验": "Early Access",
    "搶先體驗": "Early Access",
    "体育": "Sports",
    "競速": "Racing",
    "大型多人連線": "Massively Multiplayer",
    # Japanese
    "アドベンチャー": "Adventure",
    "インディー": "Indie",
    "アクション": "Action",
    "カジュアル": "Casual",
    "ストラテジー": "Strategy",
    "無料プレイ": "Free to Play",
    "シミュレーション": "Simulation",
    "ロールプレイング": "RPG",
    "レース": "Racing",
    "スポーツ": "Sports",
    # Spanish / French / German
    "acción": "Action",
    "rol": "RPG",
    "aventura": "Adventure",
    "simuladores": "Simulation",
    "estrategia": "Strategy",
    "carreras": "Racing",
    "deportes": "Sports",
    "multijugador masivo": "Massively Multiplayer",
    "acceso anticipado": "Early Access",
    "gratuit": "Free to Play",
    "kostenlos": "Free to Play",
}


def normalize_genres_list(raw_genres: List[str]) -> List[str]:
    """Map localized genre strings to canonical English genres while preserving uniqueness."""
    canonical = []
    for g in raw_genres:
        g_clean = g.strip().lower()
        if g_clean in EXPANDED_GENRE_MAP:
            norm = EXPANDED_GENRE_MAP[g_clean]
            if norm not in canonical:
                canonical.append(norm)
        else:
            if g.strip() and g.strip() not in canonical:
                canonical.append(g.strip())
    return canonical


def build_semantic_profile(
    title: str,
    genres: List[str],
    tags: List[str],
    player_modes: List[str],
    platforms: List[str],
    description: str,
) -> str:
    """Construct deterministic semantic profile text for embedding generation."""
    parts = [f"Title: {title}"]
    if genres:
        parts.append(f"Genres: {', '.join(genres)}")
    if tags:
        parts.append(f"Tags: {', '.join(tags[:15])}")
    if player_modes:
        parts.append(f"Modes: {', '.join(player_modes)}")
    if platforms:
        parts.append(f"Platforms: {', '.join(platforms)}")
    if description:
        # Take first 400 characters of description for dense, focused semantics
        parts.append(f"Description: {description[:400]}")
    return ". ".join(parts)


SPANISH_DISTINCT_WORDS = {"el", "los", "las", "del", "por", "con", "una", "para", "al", "lo", "como", "mas", "pero", "sus", "nuevo", "nueva", "juego", "mundo", "tierra", "tierras", "gracia", "poder", "este", "esta", "estos", "estas"}
FRENCH_DISTINCT_WORDS = {"vous", "nous", "votre", "vos", "notre", "nos", "les", "des", "du", "dans", "qui", "sur", "avec", "sont", "ont", "leur", "leurs", "cette", "ces", "mais", "tout", "tous", "toutes", "jeu", "tueur", "devant"}
GERMAN_DISTINCT_WORDS = {"der", "die", "das", "und", "den", "dem", "des", "von", "zu", "mit", "sich", "auf", "fur", "für", "ist", "im", "nicht", "ein", "eine", "einer", "einem", "spiel", "welt", "dass"}
ENGLISH_COMMON_WORDS = {"the", "is", "and", "a", "an", "in", "of", "to", "for", "with", "on", "you", "your", "by", "from", "as", "at", "it", "this", "that", "are", "be", "game", "world", "set", "play", "player", "through", "into", "more", "can", "all", "new"}
LOW_SIGNAL_TAGS = {"2d", "3d", "singleplayer", "multiplayer", "casual", "controller", "cute", "great soundtrack", "steam achievements", "full controller support", "indie", "pvp"}


def detect_description_language(text: str) -> str:
    """
    Detect the dominant language of a description string.
    Returns ISO code: 'en', 'ru', 'zh', 'es', 'fr', 'de', etc.
    """
    if not text:
        return "en"
    cyrillic_chars = len(re.findall(r'[\u0400-\u04FF]', text))
    cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', text))
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    total_alpha = cyrillic_chars + cjk_chars + latin_chars
    if total_alpha == 0:
        return "en"
    if cyrillic_chars / total_alpha > 0.20:
        return "ru"
    if cjk_chars / total_alpha > 0.20:
        return "zh"

    # Latin-script language detection via distinct stopwords
    words = [w.lower() for w in re.findall(r'[a-zA-Z\u00C0-\u024F]+', text)]
    if len(words) >= 4:
        es_matches = sum(1 for w in words if w in SPANISH_DISTINCT_WORDS)
        fr_matches = sum(1 for w in words if w in FRENCH_DISTINCT_WORDS)
        de_matches = sum(1 for w in words if w in GERMAN_DISTINCT_WORDS)
        en_matches = sum(1 for w in words if w in ENGLISH_COMMON_WORDS)

        best_score = max(es_matches, fr_matches, de_matches, en_matches)
        if best_score >= 2:
            if en_matches == best_score:
                return "en"
            if fr_matches == best_score:
                return "fr"
            if es_matches == best_score:
                return "es"
            if de_matches == best_score:
                return "de"

    return "en"


def build_display_description(
    title: str,
    raw_desc: str,
    canonical_genres: List[str],
    tags: List[str],
    player_modes: List[str],
    total_reviews: int = 0,
    positive_percent: float = 0.0,
) -> Tuple[str, str, str]:
    """
    Constructs the user-facing display description, language tag, and source.
    Returns (display_description, description_language, description_source)
    where description_source is 'steam' | 'normalized' | 'original'.
    """
    detected_lang = detect_description_language(raw_desc)

    # 1. Native English source description
    if detected_lang == "en" and raw_desc and len(raw_desc.strip()) >= 15:
        return (raw_desc.strip(), "en", "steam")

    # 2. Non-English source: generate clean structured English normalized synopsis if metadata is available
    genre_lower = [g.lower() for g in canonical_genres]
    filtered_tags = [t for t in tags if t.lower() not in genre_lower and t.lower() not in LOW_SIGNAL_TAGS]
    key_tags = filtered_tags[:4] if filtered_tags else ([t for t in tags if t.lower() not in genre_lower][:4] or tags[:4] or ["gameplay"])
    key_genres = canonical_genres[:3] if canonical_genres else ["Action", "Adventure"]

    # Format genre string: e.g. "RPG, and Simulation" or "Indie"
    if len(key_genres) == 1:
        genres_str = key_genres[0]
    elif len(key_genres) == 2:
        genres_str = f"{key_genres[0]} and {key_genres[1]}"
    else:
        genres_str = f"{', '.join(key_genres[:-1])}, and {key_genres[-1]}"

    # Format tag traits: e.g. "Farming Sim, Life Sim, and Crafting"
    if len(key_tags) == 1:
        tags_str = key_tags[0]
    elif len(key_tags) == 2:
        tags_str = f"{key_tags[0]} and {key_tags[1]}"
    else:
        tags_str = f"{', '.join(key_tags[:-1])}, and {key_tags[-1]}"

    # Player mode qualifier: e.g. "Co-op", "Single-player", or ""
    mode_qualifier = ""
    if player_modes:
        top_modes = [m for m in player_modes if m.lower() in ("co-op", "multi-player", "single-player", "mmo", "pvp")]
        if top_modes:
            mode_qualifier = f"{top_modes[0]} "

    if total_reviews >= 500 and positive_percent >= 80.0:
        acclaim_str = "an acclaimed "
    elif total_reviews >= 100:
        acclaim_str = "a popular "
    else:
        acclaim_str = "a "

    # Assemble clean normalized description
    if tags or canonical_genres:
        normalized_desc = f"{title} is {acclaim_str}{mode_qualifier}{genres_str} game featuring {tags_str}."
        return (normalized_desc, "en", "normalized")

    # Fallback to raw description if no tags or genres exist
    return (raw_desc.strip() if raw_desc else "No catalog synopsis available.", detected_lang, "original")


DEFAULT_RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
DEFAULT_OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "games_catalog.json")


def ingest_catalog(
    raw_dir: str = DEFAULT_RAW_DIR,
    output_file: str = DEFAULT_OUTPUT_FILE,
    min_desc_len: int = 20,
    min_tags_or_genres: int = 1,
    sort_by_popularity: bool = True,
) -> Dict[str, Any]:
    if raw_dir is None:
        raw_dir = DEFAULT_RAW_DIR if os.path.exists(DEFAULT_RAW_DIR) else "backend/data/raw"
    if output_file is None:
        output_file = DEFAULT_OUTPUT_FILE
    
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    start_time = time.time()
    print("=" * 60)
    print("Starting Steam Catalog Ingestion...")
    print("=" * 60)

    # 1. Load genres
    genres_path = os.path.join(raw_dir, "genres.csv")
    app_genres: Dict[str, List[str]] = {}
    if os.path.exists(genres_path):
        print(f"Reading {genres_path}...")
        with open(genres_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 2 and row[0] and row[1]:
                    app_id = row[0].strip()
                    genre = row[1].strip()
                    if genre:
                        app_genres.setdefault(app_id, []).append(genre)

    # 2. Load categories & extract player modes
    categories_path = os.path.join(raw_dir, "categories.csv")
    app_categories: Dict[str, List[str]] = {}
    app_modes: Dict[str, List[str]] = {}
    PLAYER_MODE_KEYWORDS = {
        "single-player",
        "multi-player",
        "online pvp",
        "pvp",
        "co-op",
        "online co-op",
        "shared/split screen",
        "cross-platform multiplayer",
        "mmo",
    }

    if os.path.exists(categories_path):
        print(f"Reading {categories_path}...")
        with open(categories_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 2 and row[0] and row[1]:
                    app_id = row[0].strip()
                    cat = row[1].strip()
                    if cat:
                        app_categories.setdefault(app_id, []).append(cat)
                        if cat.lower() in PLAYER_MODE_KEYWORDS:
                            app_modes.setdefault(app_id, []).append(cat)

    # 3. Load tags
    tags_path = os.path.join(raw_dir, "tags.csv")
    app_tags: Dict[str, List[str]] = {}
    if os.path.exists(tags_path):
        print(f"Reading {tags_path}...")
        with open(tags_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 2 and row[0] and row[1]:
                    app_id = row[0].strip()
                    tag = row[1].strip()
                    if tag:
                        app_tags.setdefault(app_id, []).append(tag)

    # 4. Load reviews & quality signals
    reviews_path = os.path.join(raw_dir, "reviews.csv")
    app_reviews: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(reviews_path):
        print(f"Reading {reviews_path}...")
        with open(reviews_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 6 and row[0]:
                    app_id = row[0].strip()
                    desc_score = row[2].strip() if len(row) > 2 else ""
                    try:
                        pos = int(row[3])
                        tot = int(row[5])
                        pct = round((pos / tot) * 100, 1) if tot > 0 else 0.0
                    except (ValueError, TypeError):
                        tot = 0
                        pct = 0.0
                    app_reviews[app_id] = {
                        "total_reviews": tot,
                        "positive_percent": pct,
                        "review_score_desc": desc_score,
                    }

    # 5. Load descriptions
    descriptions_path = os.path.join(raw_dir, "descriptions.csv")
    app_descriptions: Dict[str, str] = {}
    if os.path.exists(descriptions_path):
        print(f"Reading {descriptions_path}...")
        with open(descriptions_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 2 and row[0]:
                    app_id = row[0].strip()
                    summary = clean_text(row[1]) if len(row) > 1 else ""
                    about = clean_text(row[3]) if len(row) > 3 else ""
                    desc = summary if summary else about
                    if desc:
                        app_descriptions[app_id] = desc

    # 6. Load games and assemble normalized catalog
    games_path = os.path.join(raw_dir, "games.csv")
    catalog: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    total_games_scanned = 0
    filtered_out_no_desc = 0
    filtered_out_no_tags = 0

    if os.path.exists(games_path):
        print(f"Joining base games from {games_path}...")
        with open(games_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if not row or len(row) < 2:
                    continue
                total_games_scanned += 1
                app_id = row[0].strip()
                title = clean_text(row[1])
                release_date_raw = row[2].strip() if len(row) > 2 else ""
                is_free_raw = row[3].strip() if len(row) > 3 else "0"

                if not app_id or app_id in seen_ids or not title:
                    continue

                desc = app_descriptions.get(app_id, "")
                if len(desc) < min_desc_len:
                    filtered_out_no_desc += 1
                    continue

                raw_genres = list(dict.fromkeys(app_genres.get(app_id, [])))
                canonical_genres = normalize_genres_list(raw_genres)
                tags = list(dict.fromkeys(app_tags.get(app_id, [])))
                categories = list(dict.fromkeys(app_categories.get(app_id, [])))
                player_modes = list(dict.fromkeys(app_modes.get(app_id, [])))

                if (len(raw_genres) + len(tags)) < min_tags_or_genres:
                    filtered_out_no_tags += 1
                    continue

                seen_ids.add(app_id)
                year = extract_year(release_date_raw)
                is_free = is_free_raw == "1"
                platforms = ["PC"]

                rev_info = app_reviews.get(app_id, {"total_reviews": 0, "positive_percent": 0.0, "review_score_desc": ""})

                display_desc, desc_lang, desc_source = build_display_description(
                    title=title,
                    raw_desc=desc,
                    canonical_genres=canonical_genres,
                    tags=tags,
                    player_modes=player_modes,
                    total_reviews=rev_info["total_reviews"],
                    positive_percent=rev_info["positive_percent"],
                )

                # For dense semantic profile, prioritize English text
                profile_desc = desc if desc_lang == "en" else f"{desc} {display_desc}"
                semantic_profile = build_semantic_profile(
                    title=title,
                    genres=canonical_genres,
                    tags=tags,
                    player_modes=player_modes,
                    platforms=platforms,
                    description=profile_desc,
                )

                item = {
                    "id": app_id,
                    "external_id": app_id,
                    "source": "steam",
                    # Display layer
                    "title": title,
                    "display_title": title,
                    "description": display_desc,
                    "display_description": display_desc,
                    "description_language": desc_lang,
                    "description_source": desc_source,
                    "genres": canonical_genres,
                    "display_genres": canonical_genres,
                    "tags": tags,
                    "display_tags": tags,
                    # Original provenance layer (immutable)
                    "original_title": title,
                    "original_description": desc,
                    "original_genres": raw_genres,
                    "original_tags": tags,
                    "original_categories": categories,
                    # Search optimization layer
                    "canonical_genres": canonical_genres,
                    "search_tags": tags,
                    "search_description": profile_desc,
                    "player_modes": player_modes,
                    "platforms": platforms,
                    "release_year": year,
                    "is_free": is_free,
                    "total_reviews": rev_info["total_reviews"],
                    "positive_percent": rev_info["positive_percent"],
                    "review_score_desc": rev_info["review_score_desc"],
                    "semantic_profile": semantic_profile,
                }
                catalog.append(item)

    if sort_by_popularity:
        # Sort catalog so highest review count and tag density appear first
        catalog.sort(key=lambda g: (g.get("total_reviews", 0), len(g.get("tags", []))), reverse=True)

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(catalog, out, indent=2, ensure_ascii=False)

    elapsed = time.time() - start_time
    file_size_mb = os.path.getsize(output_file) / (1024 * 1024)

    stats = {
        "total_scanned": total_games_scanned,
        "catalog_count": len(catalog),
        "filtered_no_desc": filtered_out_no_desc,
        "filtered_no_tags": filtered_out_no_tags,
        "file_size_mb": round(file_size_mb, 2),
        "elapsed_seconds": round(elapsed, 2),
    }

    print("=" * 60)
    print(f"Ingestion Complete in {stats['elapsed_seconds']}s!")
    print(f"Games Scanned:     {stats['total_scanned']}")
    print(f"Normalized Output: {stats['catalog_count']} games")
    print(f"JSON File Size:    {stats['file_size_mb']} MB -> {output_file}")
    print("=" * 60)
    return stats


if __name__ == "__main__":
    ingest_catalog()
