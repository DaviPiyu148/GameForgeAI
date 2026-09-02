import logging
import math
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple


logger = logging.getLogger(__name__)

# Generic genre/topic phrases that should not be treated as an exact ENTITY title match
# unless the catalog game carrying that literal title has substantial review counts —
# prevents a query like "space survival" from being hijacked by an obscure game
# literally titled "Space Survival" instead of being treated as a topic/genre search.
GENERIC_GENRE_PHRASES: Set[str] = {
    "space survival", "cozy simulator", "action rpg", "zombie survival",
    "tower defense", "farming game", "card game", "city builder",
    "open world", "space sim", "life sim", "dungeon crawler"
}

# Steam international genre mappings (Cyrillic, CJK, European translations)
GENRE_TRANSLATIONS: Dict[str, str] = {
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
    "action": "Action",
    "adventure": "Adventure",
    "rpg": "RPG",
    "simulation": "Simulation",
    "strategy": "Strategy",
    "indie": "Indie",
    "casual": "Casual",
    "racing": "Racing",
    "sports": "Sports",
    "massively multiplayer": "Massively Multiplayer",
    "early access": "Early Access",
}

# Multilingual query token dictionary (Russian, Chinese, Japanese query tokens -> English canonical search concepts)
MULTILINGUAL_QUERY_DICTIONARY: Dict[str, str] = {
    # Russian concepts
    "ферма": "farm farming",
    "фермы": "farm farming",
    "фермерство": "farm farming",
    "уютный": "cozy relaxing",
    "уютная": "cozy relaxing",
    "уютное": "cozy relaxing",
    "песочница": "sandbox",
    "песочницы": "sandbox",
    "крафтинг": "crafting",
    "крафт": "crafting",
    "выживание": "survival",
    "выживалка": "survival",
    "рогалик": "roguelike",
    "рогалики": "roguelike",
    "открытый": "open world",
    "открытом": "open world",
    "мир": "world",
    "мире": "world",
    "кооператив": "co-op",
    "кооперативный": "co-op",
    "кооперативная": "co-op",
    "метроидвания": "metroidvania",
    "жуки": "insects bugs",
    "жуках": "insects bugs",
    "фабрика": "automation factory",
    "завод": "automation factory",
    "строительство": "building",
    "строить": "building",
    "космос": "space",
    "космический": "space",
    "космическая": "space",
    "подводный": "underwater ocean",
    "океан": "underwater ocean",
    "приключение": "adventure",
    "приключения": "adventure",
    "стрелялка": "shooter fps",
    "шутер": "shooter fps",
    "стратегия": "strategy",
    "симулятор": "simulator simulation",
    "экшен": "action",
    "ролевая": "rpg",
    "киберпанк": "cyberpunk",
    "пошаговый": "turn-based",
    "пошаговая": "turn-based",
    "карточный": "card battler deckbuilding",
    "карточная": "card battler deckbuilding",
    "тактика": "tactical strategy",
    "тактическая": "tactical strategy",
    "тактический": "tactical strategy",
    "градостроительный": "city builder",
    "город": "city builder",
    # Chinese concepts
    "农场": "farm farming",
    "种田": "farm farming",
    "温馨": "cozy relaxing",
    "沙盒": "sandbox",
    "生存": "survival",
    "肉鸽": "roguelike",
    "开放世界": "open world",
    "联机": "co-op multiplayer",
    "合作": "co-op multiplayer",
    "类银河恶魔城": "metroidvania",
    "建造": "building",
    "卡牌": "card deckbuilding",
    "射击": "shooter fps",
    "回合制": "turn-based",
    # Japanese concepts
    "農業": "farm farming",
    "牧場": "farm farming",
    "サンドボックス": "sandbox",
    "サバイバル": "survival",
    "ローグライク": "roguelike",
    "オープンワールド": "open world",
    "協力プレイ": "co-op",
    "メトロイドヴァニア": "metroidvania",
    "建設": "building",
    # English semantic cross-aliases
    "simulator": "simulation",
    "simulation": "simulator",
    "rpg": "role playing",
}

# Common safe abbreviations / acronyms that deterministically map to landmark titles
SAFE_TITLE_ALIASES: Dict[str, str] = {
    "witcher 3": "The Witcher 3: Wild Hunt",
    "witcher 3 wild hunt": "The Witcher 3: Wild Hunt",
    "the witcher 3": "The Witcher 3: Wild Hunt",
    "stardew": "Stardew Valley",
    "stardew valley": "Stardew Valley",
    "cyberpunk 2077": "Cyberpunk 2077",
    "cp2077": "Cyberpunk 2077",
    "elden ring": "ELDEN RING",
    "dark souls 3": "DARK SOULS™ III",
    "dark souls iii": "DARK SOULS™ III",
    "dark souls": "DARK SOULS™ III",
    "ds3": "DARK SOULS™ III",
    "ror2": "Risk of Rain 2",
    "risk of rain 2": "Risk of Rain 2",
    "drg": "Deep Rock Galactic",
    "deep rock": "Deep Rock Galactic",
    "deep rock galactic": "Deep Rock Galactic",
    "hollow knight": "Hollow Knight",
    "slay the spire": "Slay the Spire",
    "sts": "Slay the Spire",
    "binding of isaac": "The Binding of Isaac: Rebirth",
    "isaac": "The Binding of Isaac: Rebirth",
    "subnautica": "Subnautica",
    "terraria": "Terraria",
    "rimworld": "RimWorld",
    "no mans sky": "No Man's Sky",
    "no man's sky": "No Man's Sky",
    "nms": "No Man's Sky",
    "valheim": "Valheim",
    "dead cells": "Dead Cells",
    "factorio": "Factorio",
}

ROMAN_NUMERALS: Dict[str, str] = {
    "i": "1",
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
    "x": "10",
}


def normalize_string(text: str) -> str:
    """Normalize text: strip accents, lowercase, remove special characters, collapse whitespace."""
    if not text:
        return ""
    # Normalize unicode
    nfkd_form = unicodedata.normalize("NFKD", text)
    only_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Remove trademark/copyright symbols
    cleaned = re.sub(r"[™®©]", "", only_ascii)
    # Convert punctuation to spaces
    cleaned = re.sub(r"[^\w\s]", " ", cleaned.lower())
    # Collapse whitespace
    return re.sub(r"\s+", " ", cleaned).strip()


def tokenize(text: str) -> List[str]:
    """Tokenize normalized string into significant keywords (length >= 2, numbers allowed)."""
    norm = normalize_string(text)
    tokens = [t for t in norm.split() if len(t) >= 2 or t.isdigit()]
    return tokens


def normalize_genres(raw_genres: List[str]) -> List[str]:
    """Translate international genres and standardize casing."""
    normalized: List[str] = []
    seen: Set[str] = set()
    for g in raw_genres:
        if not g:
            continue
        g_clean = g.strip().lower()
        translated = GENRE_TRANSLATIONS.get(g_clean, g.strip())
        if translated and translated.lower() not in seen:
            seen.add(translated.lower())
            normalized.append(translated)
    return normalized


from app.search.candidate_pool import DiscoveryCandidatePool


class LexicalIndex:
    """Fast in-memory inverted index supporting exact title matching, token BM25-style scoring, and tag/genre matching."""

    def __init__(self, catalog: List[Dict[str, Any]]):
        self._catalog = catalog
        self._games_by_id: Dict[str, Dict[str, Any]] = {str(g["id"]): g for g in catalog if "id" in g}
        
        # Precomputed candidate pool identifier sets
        self._twenty_k_game_ids: Set[str] = {str(g["id"]) for g in self._catalog[:20000] if "id" in g}
        self._reviewed_game_ids: Set[str] = {str(g["id"]) for g in self._catalog if "id" in g and g.get("total_reviews", 0) > 0}

        # Primary lookup tables
        self._exact_title_to_id: Dict[str, str] = {}
        self._normalized_title_to_id: Dict[str, str] = {}
        self._title_token_to_ids: Dict[str, Set[str]] = {}
        self._tag_to_ids: Dict[str, Set[str]] = {}
        self._genre_to_ids: Dict[str, Set[str]] = {}
        self._all_tags_lower: Set[str] = set()
        self._all_genres_lower: Set[str] = set()
        
        self._build_index()

    def _build_index(self) -> None:
        logger.info("Building LexicalIndex over %d games...", len(self._catalog))
        for game in self._catalog:
            gid = str(game.get("id", ""))
            if not gid:
                continue

            raw_title = str(game.get("title", "")).strip()
            norm_title = normalize_string(raw_title)
            
            # Exact title mapping (case-insensitive)
            if raw_title.lower() not in self._exact_title_to_id:
                self._exact_title_to_id[raw_title.lower()] = gid
            if norm_title not in self._normalized_title_to_id:
                self._normalized_title_to_id[norm_title] = gid

            # Index title tokens
            tokens = tokenize(raw_title)
            for t in tokens:
                self._title_token_to_ids.setdefault(t, set()).add(gid)
                # Map roman numeral to arabic digit if applicable
                if t in ROMAN_NUMERALS:
                    self._title_token_to_ids.setdefault(ROMAN_NUMERALS[t], set()).add(gid)

            # Normalize & Index genres (both canonical and raw localized)
            raw_genres = game.get("original_genres", []) or game.get("genres", [])
            canonical_genres = game.get("genres", [])
            all_genres_to_index = list(dict.fromkeys(raw_genres + canonical_genres))
            for genre in all_genres_to_index:
                g_norm = normalize_string(genre)
                if g_norm:
                    self._genre_to_ids.setdefault(g_norm, set()).add(gid)
                    self._all_genres_lower.add(g_norm)
                    g_comp = re.sub(r"[\s-]", "", g_norm)
                    if g_comp != g_norm:
                        self._genre_to_ids.setdefault(g_comp, set()).add(gid)
                        self._all_genres_lower.add(g_comp)
                    for sub_g in g_norm.split():
                        if len(sub_g) >= 3 and sub_g not in ("and", "the", "for", "game", "games"):
                            self._genre_to_ids.setdefault(sub_g, set()).add(gid)
                            self._all_genres_lower.add(sub_g)

            # Index tags (both standard normalized, compound-stripped, and individual tokens)
            for tag in game.get("tags", []):
                t_norm = normalize_string(tag)
                if t_norm:
                    self._tag_to_ids.setdefault(t_norm, set()).add(gid)
                    self._all_tags_lower.add(t_norm)
                    t_comp = re.sub(r"[\s-]", "", t_norm)
                    if t_comp != t_norm:
                        self._tag_to_ids.setdefault(t_comp, set()).add(gid)
                        self._all_tags_lower.add(t_comp)
                    for sub_t in t_norm.split():
                        if len(sub_t) >= 3 and sub_t not in ("and", "the", "for", "game", "games"):
                            self._tag_to_ids.setdefault(sub_t, set()).add(gid)
                            self._all_tags_lower.add(sub_t)

        logger.info("LexicalIndex ready: %d unique normalized titles, %d title tokens, %d tags, %d genres.",
                    len(self._normalized_title_to_id), len(self._title_token_to_ids),
                    len(self._tag_to_ids), len(self._genre_to_ids))

    def resolve_entity(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Check if query directly resolves to a canonical game title via exact match,
        normalized match, or safe alias.
        """
        clean_q = query.strip().lower()
        norm_q = normalize_string(query)
        
        # 1. Exact alias match (High confidence)
        if clean_q in SAFE_TITLE_ALIASES:
            target_title = SAFE_TITLE_ALIASES[clean_q]
            target_norm = normalize_string(target_title)
            gid = self._normalized_title_to_id.get(target_norm) or self._exact_title_to_id.get(target_title.lower())
            if gid and gid in self._games_by_id:
                return self._games_by_id[gid]

        if norm_q in SAFE_TITLE_ALIASES:
            target_title = SAFE_TITLE_ALIASES[norm_q]
            target_norm = normalize_string(target_title)
            gid = self._normalized_title_to_id.get(target_norm)
            if gid and gid in self._games_by_id:
                return self._games_by_id[gid]

        # 2. Check if the query is a generic genre phrase (e.g. "space survival", "action rpg")
        # In this case, do not hijack it as an ENTITY unless it has high acclaim
        if norm_q in GENERIC_GENRE_PHRASES:
            return None

        # 3. Exact match in catalog
        if clean_q in self._exact_title_to_id:
            game = self._games_by_id[self._exact_title_to_id[clean_q]]
            # If title is single common word without reviews, do not hijack
            if len(clean_q.split()) > 1 or game.get("total_reviews", 0) >= 500:
                return game

        # 4. Normalized match in catalog
        if norm_q in self._normalized_title_to_id:
            game = self._games_by_id[self._normalized_title_to_id[norm_q]]
            if len(norm_q.split()) > 1 or game.get("total_reviews", 0) >= 500:
                return game

        # 5. Check for subtitle-stripped matches (e.g. "Cyberpunk 2077: Phantom Liberty" -> "Cyberpunk 2077")
        if ":" in clean_q or "-" in clean_q:
            base_q = normalize_string(clean_q.split(":")[0].split("-")[0])
            if base_q in self._normalized_title_to_id:
                game = self._games_by_id[self._normalized_title_to_id[base_q]]
                if game.get("total_reviews", 0) >= 1000:
                    return game

        return None

    def search_lexical(
        self,
        query: str,
        limit: int = 50,
        query_type: str = "CONCEPT",
        candidate_pool: Optional[DiscoveryCandidatePool] = None,
        allowed_game_ids: Optional[Set[str]] = None,
    ) -> List[Tuple[Dict[str, Any], float, Dict[str, Any]]]:
        """
        Execute lexical candidate retrieval and scoring over normalized catalog,
        strictly respecting mode-specific candidate pool boundaries.
        Returns list of (game_dict, lexical_score, match_details).
        """
        norm_q = normalize_string(query)
        q_tokens = tokenize(query)
        if not norm_q or not q_tokens:
            return []

        # Determine effective candidate pool whitelist
        pool_filter_ids: Optional[Set[str]] = None
        if candidate_pool == DiscoveryCandidatePool.POPULAR_20K:
            pool_filter_ids = self._twenty_k_game_ids
        elif candidate_pool == DiscoveryCandidatePool.REVIEWED_ONLY:
            pool_filter_ids = self._reviewed_game_ids

        if allowed_game_ids is not None:
            if pool_filter_ids is not None:
                pool_filter_ids = pool_filter_ids.intersection(allowed_game_ids)
            else:
                pool_filter_ids = allowed_game_ids

        # Normalized multilingual query dictionary for robust accented key lookup
        norm_dict = {normalize_string(k): v for k, v in MULTILINGUAL_QUERY_DICTIONARY.items()}

        # Expand multilingual query tokens
        expanded_q_tokens = list(q_tokens)
        for t in q_tokens:
            t_clean = normalize_string(t)
            if t_clean in norm_dict:
                for exp_t in norm_dict[t_clean].split():
                    exp_norm = normalize_string(exp_t)
                    if exp_norm and exp_norm not in expanded_q_tokens:
                        expanded_q_tokens.append(exp_norm)

        candidate_scores: Dict[str, float] = {}
        candidate_details: Dict[str, Dict[str, Any]] = {}

        # 1. Exact / Normalized Entity Check (must respect candidate pool policy)
        entity_game = self.resolve_entity(query)
        if entity_game:
            gid = str(entity_game["id"])
            if pool_filter_ids is None or gid in pool_filter_ids:
                candidate_scores[gid] = 1.0
                candidate_details[gid] = {
                    "exact_title": True,
                    "matched_tags": [],
                    "matched_genres": [],
                    "token_overlap": 1.0,
                }

        # 2. Token Overlap Scoring
        # Find all games matching query tokens (and multilingual expansions) and rank by match multiplicity and reviews
        token_hit_counts: Dict[str, int] = {}
        for t in expanded_q_tokens:
            t_norm = normalize_string(t)
            t_comp = re.sub(r"[\s-]", "", t_norm)
            
            for gid in self._title_token_to_ids.get(t_norm, set()):
                if pool_filter_ids is None or gid in pool_filter_ids:
                    token_hit_counts[gid] = token_hit_counts.get(gid, 0) + 4
            for gid in self._tag_to_ids.get(t_norm, set()):
                if pool_filter_ids is None or gid in pool_filter_ids:
                    token_hit_counts[gid] = token_hit_counts.get(gid, 0) + 2
            if t_comp != t_norm:
                for gid in self._tag_to_ids.get(t_comp, set()):
                    if pool_filter_ids is None or gid in pool_filter_ids:
                        token_hit_counts[gid] = token_hit_counts.get(gid, 0) + 2
            for gid in self._genre_to_ids.get(t_norm, set()):
                if pool_filter_ids is None or gid in pool_filter_ids:
                    token_hit_counts[gid] = token_hit_counts.get(gid, 0) + 1

        # Prune candidate pool if large (e.g. > 300) by hit count and log reviews
        if len(token_hit_counts) > 300:
            def candidate_priority(gid: str) -> float:
                hits = token_hit_counts[gid]
                g = self._games_by_id.get(gid)
                revs = g.get("total_reviews", 0) if g else 0
                return hits * 10.0 + math.log10(max(1, revs))

            sorted_gids = sorted(token_hit_counts.keys(), key=candidate_priority, reverse=True)[:300]
            candidate_pool_gids = set(sorted_gids)
        else:
            candidate_pool_gids = set(token_hit_counts.keys())

        # Include exact entity if found (and passes pool filter)
        if entity_game:
            gid = str(entity_game["id"])
            if pool_filter_ids is None or gid in pool_filter_ids:
                candidate_pool_gids.add(gid)

        for gid in candidate_pool_gids:
            game = self._games_by_id.get(gid)
            if not game:
                continue

            game_title_norm = normalize_string(game.get("title", ""))
            game_title_tokens = set(tokenize(game.get("title", "")))

            score = candidate_scores.get(gid, 0.0)
            details = candidate_details.get(gid, {
                "exact_title": False,
                "matched_tags": [],
                "matched_genres": [],
                "token_overlap": 0.0,
            })

            # Check exact or prefix title match
            is_generic_phrase = norm_q in GENERIC_GENRE_PHRASES
            reviews = game.get("total_reviews", 0)

            if norm_q == game_title_norm and (not is_generic_phrase or reviews >= 2000):
                score = max(score, 0.95)
                details["exact_title"] = True
            elif norm_q == game_title_norm:
                score = max(score, 0.65)
            elif (game_title_norm.startswith(norm_q) or norm_q.startswith(game_title_norm)) and (not is_generic_phrase or reviews >= 1000):
                score = max(score, 0.85)
            elif norm_q in game_title_norm:
                score = max(score, 0.60)

            # Title token overlap (Jaccard-like)
            matched_title_tokens = game_title_tokens.intersection(set(expanded_q_tokens))
            if matched_title_tokens:
                overlap_ratio = len(matched_title_tokens) / max(len(q_tokens), 1)
                title_token_score = 0.4 * min(1.0, overlap_ratio)
                score = max(score, title_token_score)
                details["token_overlap"] = overlap_ratio

            # Tag matches (check against expanded query tokens)
            matched_tags: List[str] = []
            for t in expanded_q_tokens:
                t_comp = re.sub(r"[\s-]", "", t)
                for orig_t in game.get("tags", []):
                    orig_norm = normalize_string(orig_t)
                    orig_comp = re.sub(r"[\s-]", "", orig_norm)
                    orig_tokens = set(tokenize(orig_norm))
                    if (t == orig_norm or t_comp == orig_comp or t in orig_tokens or t_comp in orig_comp) and orig_t not in matched_tags:
                        matched_tags.append(orig_t)
            if matched_tags:
                tag_score = min(0.6, 0.2 * len(matched_tags))
                score += tag_score
                details["matched_tags"] = matched_tags

            # Genre matches (check against expanded query tokens)
            matched_genres: List[str] = []
            for t in expanded_q_tokens:
                t_comp = re.sub(r"[\s-]", "", t)
                for orig_g in (game.get("genres", []) + game.get("original_genres", [])):
                    orig_norm = normalize_string(orig_g)
                    orig_comp = re.sub(r"[\s-]", "", orig_norm)
                    orig_tokens = set(tokenize(orig_norm))
                    if (t == orig_norm or t_comp == orig_comp or t in orig_tokens or t_comp in orig_comp) and orig_g not in matched_genres:
                        matched_genres.append(orig_g)
            if matched_genres:
                genre_score = min(0.4, 0.15 * len(matched_genres))
                score += genre_score
                details["matched_genres"] = matched_genres

            # Multi-token concept coverage bonus
            if len(q_tokens) >= 2:
                matched_concept_count = 0
                for qt in q_tokens:
                    qt_norm = normalize_string(qt)
                    qt_expansions = [qt_norm] + norm_dict.get(qt_norm, "").split()
                    if any(exp in game_title_norm or any(exp in normalize_string(mt) for mt in matched_tags) or any(exp in normalize_string(mg) for mg in matched_genres) for exp in qt_expansions if exp):
                        matched_concept_count += 1
                
                concept_coverage = matched_concept_count / len(q_tokens)
                if concept_coverage >= 0.6:
                    score += 0.25 * concept_coverage
                if concept_coverage >= 1.0:
                    score += 0.20

            # Quality / Acclaim prior to prevent unreviewed keyword-stuffed titles from dominating landmarks
            log_revs = math.log10(max(1.0, float(reviews)))
            score += log_revs * 0.08
            if float(game.get("positive_percent", 0.0)) >= 85.0:
                score += 0.05

            candidate_scores[gid] = score
            candidate_details[gid] = details

        # Sort candidates by relevance score descending, tie-broken by log(reviews) and positive_percent
        def candidate_sort_key(item: Tuple[str, float]) -> Tuple[float, float, float]:
            gid, raw_score = item
            g = self._games_by_id.get(gid, {})
            revs = float(g.get("total_reviews", 0))
            pos = float(g.get("positive_percent", 0.0))
            return (raw_score, math.log10(max(1.0, revs)), pos)

        sorted_candidates = sorted(candidate_scores.items(), key=candidate_sort_key, reverse=True)
        results: List[Tuple[Dict[str, Any], float, Dict[str, Any]]] = []
        for gid, score in sorted_candidates[:limit]:
            game = self._games_by_id.get(gid)
            if game:
                clamped_score = min(1.0, max(0.0, score))
                results.append((game, clamped_score, candidate_details.get(gid, {})))

        return results
