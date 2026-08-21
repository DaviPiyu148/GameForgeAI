import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from app.search.lexical import LexicalIndex, normalize_string, tokenize, MULTILINGUAL_QUERY_DICTIONARY, GENRE_TRANSLATIONS


logger = logging.getLogger(__name__)

SIMILARITY_PATTERNS = [
    re.compile(r"^(?:games?|titles?|recommendations?|anything|something)\s+(?:like|similar\s+to|comparable\s+to)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:similar\s+to|more\s+like|like)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(.+)\s+(?:alternatives?|clones?)$", re.IGNORECASE),
    # Russian patterns
    re.compile(r"^(?:игры?|проекты?|тайтлы?)\s+(?:похожие\s+на|в\s+стиле|в\s+духе)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:похоже\s+на|аналог(?:и)?)\s+(.+)$", re.IGNORECASE),
    # Chinese patterns
    re.compile(r"^(?:类似|像)\s*(.+?)(?:的(?:游戏)?)?$", re.IGNORECASE),
]

# Common single-topic keywords (genres, tags, archetypes in English and foreign terms)
TOPIC_KEYWORDS = {
    "cyberpunk", "soulslike", "souls-like", "roguelike", "rogue-like", "roguelite", "rogue-lite",
    "metroidvania", "deckbuilder", "deckbuilding", "farming", "farming sim", "farming game",
    "city builder", "survival horror", "tower defense", "sandbox", "stealth", "fps",
    "turn-based", "turn based", "grand strategy", "bullet hell", "boomer shooter",
    "visual novel", "battle royale", "autochess", "auto battler", "extraction shooter",
    "immersive sim", "walking simulator", "dating sim", "management", "crafting",
    "open world", "hack and slash", "beat em up", "point and click", "jumper",
    "dungeon crawler", "life sim", "colony sim", "puzzle platformer",
    # Multilingual terms
    "ферма", "рогалик", "метроидвания", "градостроительный", "песочница", "выживание",
    "киберпанк", "шутер", "стратегия", "симулятор", "пошаговая", "карточный",
    "农场", "种田", "肉鸽", "沙盒", "生存", "类银河恶魔城", "卡牌",
    "農業", "サバイバル", "ローグライク", "メトロイドヴァニア"
}

PLAYER_MODE_KEYWORDS: Dict[str, str] = {
    "co-op": "Co-op",
    "co op": "Co-op",
    "coop": "Co-op",
    "co operative": "Co-op",
    "cooperative": "Co-op",
    "multiplayer": "Multi-player",
    "multi player": "Multi-player",
    "multi-player": "Multi-player",
    "singleplayer": "Single-player",
    "single player": "Single-player",
    "single-player": "Single-player",
    "pvp": "PvP",
    "online pvp": "Online PvP",
    "split screen": "Shared/Split Screen",
    "splitscreen": "Shared/Split Screen",
    "local co-op": "Shared/Split Screen",
    "local co op": "Shared/Split Screen",
    # Multilingual player modes
    "кооператив": "Co-op",
    "кооперативный": "Co-op",
    "кооперативная": "Co-op",
    "кооп": "Co-op",
    "мультиплеер": "Multi-player",
    "многопользовательская": "Multi-player",
    "одиночная": "Single-player",
    "пвп": "PvP",
    "联机": "Co-op",
    "合作": "Co-op",
    "多人": "Multi-player",
    "单人": "Single-player",
    "協力": "Co-op",
    "マルチプレイ": "Multi-player",
    "シングルプレイ": "Single-player",
}


@dataclass
class ParsedQuery:
    """Structured representation of a parsed search query."""
    raw_query: str
    normalized_query: str
    query_type: str  # 'ENTITY', 'SIMILARITY', 'TOPIC_TAG', 'CONCEPT', 'MIXED'
    clean_search_query: str
    target_entity: Optional[str] = None
    target_game: Optional[Dict[str, Any]] = None
    extracted_tags: List[str] = field(default_factory=list)
    extracted_genres: List[str] = field(default_factory=list)
    extracted_player_modes: List[str] = field(default_factory=list)
    confidence: float = 1.0


class QueryParser:
    """Deterministic, local query understanding and intent classification engine."""

    def __init__(self, lexical_index: Optional[LexicalIndex] = None):
        self.lexical_index = lexical_index

    def parse(self, raw_query: str) -> ParsedQuery:
        """Parse natural language query into query type and structured metadata."""
        query = raw_query.strip()
        norm_q = normalize_string(query)
        tokens = tokenize(query)

        if not query or not norm_q:
            return ParsedQuery(
                raw_query=raw_query,
                normalized_query="",
                query_type="CONCEPT",
                clean_search_query="",
            )

        extracted_modes = self._extract_player_modes(norm_q)
        extracted_tags, extracted_genres = self._extract_tags_and_genres(tokens)

        # 1. Check for SIMILARITY query pattern
        for pattern in SIMILARITY_PATTERNS:
            match = pattern.match(query)
            if match:
                target_str = match.group(1).strip()
                target_game = None
                if self.lexical_index:
                    target_game = self.lexical_index.resolve_entity(target_str)
                
                clean_target = target_game["title"] if target_game else target_str
                return ParsedQuery(
                    raw_query=raw_query,
                    normalized_query=norm_q,
                    query_type="SIMILARITY",
                    clean_search_query=clean_target,
                    target_entity=clean_target,
                    target_game=target_game,
                    extracted_tags=extracted_tags,
                    extracted_genres=extracted_genres,
                    extracted_player_modes=extracted_modes,
                    confidence=0.95 if target_game else 0.80,
                )

        # 2. Check for ENTITY query (exact title or safe alias)
        if self.lexical_index:
            entity_game = self.lexical_index.resolve_entity(query)
            if entity_game:
                # If the query is an exact match for a landmark title
                return ParsedQuery(
                    raw_query=raw_query,
                    normalized_query=norm_q,
                    query_type="ENTITY",
                    clean_search_query=entity_game["title"],
                    target_entity=entity_game["title"],
                    target_game=entity_game,
                    extracted_tags=extracted_tags,
                    extracted_genres=extracted_genres,
                    extracted_player_modes=extracted_modes,
                    confidence=1.0,
                )
        
        # Compute translated clean search query for embedding
        norm_dict = {normalize_string(k): v for k, v in MULTILINGUAL_QUERY_DICTIONARY.items()}
        expanded_search_tokens = []
        for t in tokens:
            t_clean = normalize_string(t)
            if t_clean in norm_dict:
                expanded_search_tokens.append(norm_dict[t_clean])
            else:
                expanded_search_tokens.append(t)
        translated_search_query = " ".join(expanded_search_tokens)
        clean_search_q = translated_search_query if translated_search_query != " ".join(tokens) else query

        # 3. Check for TOPIC_TAG query (single genre, tag, or topic keyword)
        if norm_q in TOPIC_KEYWORDS or (len(tokens) <= 2 and (extracted_tags or extracted_genres)):
            return ParsedQuery(
                raw_query=raw_query,
                normalized_query=norm_q,
                query_type="TOPIC_TAG",
                clean_search_query=clean_search_q,
                extracted_tags=extracted_tags,
                extracted_genres=extracted_genres,
                extracted_player_modes=extracted_modes,
                confidence=0.90,
            )

        # 4. Check for MIXED query (explicit topic/entity combined with player modes or disparate mechanics)
        has_mode = len(extracted_modes) > 0
        has_topic = any(t in TOPIC_KEYWORDS for t in [norm_q] + tokens + expanded_search_tokens)
        
        if has_mode and (extracted_tags or extracted_genres or has_topic):
            return ParsedQuery(
                raw_query=raw_query,
                normalized_query=norm_q,
                query_type="MIXED",
                clean_search_query=clean_search_q,
                extracted_tags=extracted_tags,
                extracted_genres=extracted_genres,
                extracted_player_modes=extracted_modes,
                confidence=0.85,
            )

        if has_topic and len(tokens) >= 3 and (len(extracted_genres) > 0 or "rpg" in tokens or "fps" in tokens or "2d" in tokens or "3d" in tokens):
            return ParsedQuery(
                raw_query=raw_query,
                normalized_query=norm_q,
                query_type="MIXED",
                clean_search_query=clean_search_q,
                extracted_tags=extracted_tags,
                extracted_genres=extracted_genres,
                extracted_player_modes=extracted_modes,
                confidence=0.85,
            )

        # 5. Default to CONCEPT query (natural language descriptive concept)
        return ParsedQuery(
            raw_query=raw_query,
            normalized_query=norm_q,
            query_type="CONCEPT",
            clean_search_query=clean_search_q,
            extracted_tags=extracted_tags,
            extracted_genres=extracted_genres,
            extracted_player_modes=extracted_modes,
            confidence=0.75,
        )

    def _extract_player_modes(self, normalized_query: str) -> List[str]:
        """Extract explicit player mode mentions from query string."""
        modes = []
        norm_mode_dict = {normalize_string(k): v for k, v in PLAYER_MODE_KEYWORDS.items()}
        for phrase, mode_label in norm_mode_dict.items():
            pattern = r"\b" + re.escape(phrase) + r"\b"
            if re.search(pattern, normalized_query, re.IGNORECASE):
                if mode_label not in modes:
                    modes.append(mode_label)
        return modes

    def _extract_tags_and_genres(self, tokens: List[str]) -> Tuple[List[str], List[str]]:
        """Extract matching genres and tags from token list."""
        extracted_tags = []
        extracted_genres = []
        norm_dict = {normalize_string(k): v for k, v in MULTILINGUAL_QUERY_DICTIONARY.items()}
        
        # Expand tokens with multilingual translations
        expanded_tokens = list(tokens)
        for t in tokens:
            t_clean = normalize_string(t)
            if t_clean in norm_dict:
                for exp_t in norm_dict[t_clean].split():
                    exp_norm = normalize_string(exp_t)
                    if exp_norm and exp_norm not in expanded_tokens:
                        expanded_tokens.append(exp_norm)

        if self.lexical_index:
            for t in expanded_tokens:
                t_norm = normalize_string(t)
                if t_norm in self.lexical_index._all_genres_lower:
                    extracted_genres.append(GENRE_TRANSLATIONS.get(t_norm, t.title()))
                if t_norm in self.lexical_index._all_tags_lower:
                    extracted_tags.append(t.title())

        return list(dict.fromkeys(extracted_tags)), list(dict.fromkeys(extracted_genres))
