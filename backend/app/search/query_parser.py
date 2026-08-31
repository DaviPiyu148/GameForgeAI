import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from app.search.lexical import LexicalIndex, normalize_string, tokenize, MULTILINGUAL_QUERY_DICTIONARY, GENRE_TRANSLATIONS


logger = logging.getLogger(__name__)

SIMILARITY_PATTERNS = [
    re.compile(r"^(?:games?|titles?|recommendations?|anything|something)\s+(?:like|similar\s+to|comparable\s+to)\s+(.+?)(?:\s+(?:but|without|except|with|for)\s+(.+))?$", re.IGNORECASE),
    re.compile(r"^(?:similar\s+to|more\s+like|like)\s+(.+?)(?:\s+(?:but|without|except|with|for)\s+(.+))?$", re.IGNORECASE),
    re.compile(r"^(.+?)\s+(?:alternatives?|clones?)(?:\s+(?:but|without|except|with|for)\s+(.+))?$", re.IGNORECASE),
    # Russian patterns
    re.compile(r"^(?:игры?|проекты?|тайтлы?)\s+(?:похожие\s+на|в\s+стиле|в\s+духе)\s+(.+?)(?:\s+(?:но|без)\s+(.+))?$", re.IGNORECASE),
    re.compile(r"^(?:похоже\s+на|аналог(?:и)?)\s+(.+?)(?:\s+(?:но|без)\s+(.+))?$", re.IGNORECASE),
    # Chinese patterns
    re.compile(r"^(?:类似|像)\s*(.+?)(?:的(?:游戏)?)?(?:\s*(?:但是|除了|不含)\s*(.+))?$", re.IGNORECASE),
]

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
    "solo": "Single-player",
    "pvp": "PvP",
    "online pvp": "Online PvP",
    "split screen": "Shared/Split Screen",
    "splitscreen": "Shared/Split Screen",
    "local co-op": "Shared/Split Screen",
    "local co op": "Shared/Split Screen",
    "with friends": "Co-op",
    "play with friends": "Co-op",
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

# Controlled mood/tone mappings
MOOD_KEYWORDS: Dict[str, str] = {
    "relaxing": "relaxing",
    "relaxed": "relaxing",
    "chill": "relaxing",
    "cozy": "relaxing",
    "peaceful": "relaxing",
    "calm": "relaxing",
    "intense": "intense",
    "hectic": "intense",
    "adrenaline": "intense",
    "fast-paced": "intense",
    "fast paced": "intense",
    "dark": "dark",
    "grim": "dark",
    "gloomy": "dark",
    "scary": "scary",
    "spooky": "scary",
    "creepy": "scary",
    "terrifying": "scary",
    "atmospheric": "atmospheric",
    "immersive": "atmospheric",
    "competitive": "competitive",
}

# Negation trigger patterns (hard vs soft)
HARD_NEGATION_PATTERNS = [
    re.compile(r"\b(?:no|without|not|never|don't want|dont want|exclude)\s+([a-z0-9\s-]+?)(?:,|\.|$|\band\b|\bwith\b|\bfor\b)", re.I),
]

SOFT_NEGATION_PATTERNS = [
    re.compile(r"\b(?:less|avoid|rather avoid|prefer no|low)\s+([a-z0-9\s-]+?)(?:,|\.|$|\band\b|\bwith\b|\bfor\b)", re.I),
]

# Session duration triggers
SESSION_LENGTH_PATTERNS = [
    (re.compile(r"\b(?:10|15|20|30|45)\s*(?:mins?|minutes?)\b", re.I), "short"),
    (re.compile(r"\b(?:short|quick|bite-sized|snackable|casual)\s*(?:sessions?|runs?)?\b", re.I), "short"),
    (re.compile(r"\b(?:60|90|120)\s*(?:mins?|minutes?)\b", re.I), "medium"),
    (re.compile(r"\b(?:medium|moderate)\s*(?:sessions?|runs?)?\b", re.I), "medium"),
    (re.compile(r"\b(?:long|lengthy|deep|epic|hours)\s*(?:sessions?|runs?)?\b", re.I), "long"),
]


@dataclass
class ParsedQuery:
    """Rich structured representation of a parsed search query."""
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

    # Rich Intent Dimensions (Discovery Intelligence V1)
    wanted_tags: List[str] = field(default_factory=list)
    wanted_genres: List[str] = field(default_factory=list)
    avoid_tags: List[str] = field(default_factory=list)
    avoid_genres: List[str] = field(default_factory=list)
    avoid_modes: List[str] = field(default_factory=list)
    is_negative_hard: bool = False
    session_length: Optional[str] = None  # "short", "medium", "long"
    moods: List[str] = field(default_factory=list)
    combat_preference: Optional[str] = None  # "low", "normal", "high"
    difficulty_preference: Optional[str] = None  # "easy", "medium", "hard", "punishing"
    price_preference: Optional[str] = None  # "free", "budget", "any"
    hard_constraints: Dict[str, Any] = field(default_factory=dict)
    soft_preferences: Dict[str, Any] = field(default_factory=dict)


class QueryParser:
    """Deterministic, local query understanding and rich intent classification engine."""

    def __init__(self, lexical_index: Optional[LexicalIndex] = None):
        self.lexical_index = lexical_index

    def parse(self, raw_query: str) -> ParsedQuery:
        """Parse natural language query into rich structured intent object."""
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

        # 1. Extract negations & preferences
        avoid_tags, avoid_genres, avoid_modes, is_neg_hard, clean_query_text = self._extract_negations(query)
        norm_clean = normalize_string(clean_query_text)
        clean_tokens = tokenize(clean_query_text)

        # 2. Extract dimensions
        extracted_modes = self._extract_player_modes(norm_q)
        # Filter out modes if they were explicitly negated
        if avoid_modes:
            extracted_modes = [m for m in extracted_modes if m not in avoid_modes]

        extracted_tags, extracted_genres = self._extract_tags_and_genres(clean_tokens)
        moods = self._extract_moods(norm_q, clean_query_text=clean_query_text)
        combat_pref = self._extract_combat_preference(norm_q, avoid_tags=avoid_tags)
        diff_pref = self._extract_difficulty_preference(norm_q)

        session_len = self._extract_session_length(norm_q)
        price_pref, is_free_req = self._extract_price_preference(norm_q)

        # Build hard constraints and soft preferences
        hard_constraints: Dict[str, Any] = {}
        soft_preferences: Dict[str, Any] = {}

        if is_free_req:
            hard_constraints["is_free"] = True

        if is_neg_hard:
            if avoid_genres:
                hard_constraints["avoid_genres"] = list(avoid_genres)
            if avoid_tags:
                hard_constraints["avoid_tags"] = list(avoid_tags)
            if avoid_modes:
                hard_constraints["avoid_modes"] = list(avoid_modes)
        else:
            if avoid_genres:
                soft_preferences["avoid_genres"] = list(avoid_genres)
            if avoid_tags:
                soft_preferences["avoid_tags"] = list(avoid_tags)

        if moods:
            soft_preferences["moods"] = list(moods)
        if combat_pref:
            soft_preferences["combat"] = combat_pref
        if diff_pref:
            soft_preferences["difficulty"] = diff_pref
        if session_len:
            soft_preferences["session_length"] = session_len

        # 3. Check for SIMILARITY query pattern
        for pattern in SIMILARITY_PATTERNS:
            match = pattern.match(query)
            if match:
                target_str = match.group(1).strip()
                modifier_str = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else ""
                
                target_game = None
                if self.lexical_index:
                    target_game = self.lexical_index.resolve_entity(target_str)

                clean_target = target_game["title"] if target_game else target_str
                
                # Check modifier if present (e.g. "but less combat", "without horror")
                if modifier_str:
                    mod_avoid_t, mod_avoid_g, mod_avoid_m, mod_hard, _ = self._extract_negations(f"without {modifier_str}")
                    avoid_tags = list(dict.fromkeys(avoid_tags + mod_avoid_t))
                    avoid_genres = list(dict.fromkeys(avoid_genres + mod_avoid_g))
                    avoid_modes = list(dict.fromkeys(avoid_modes + mod_avoid_m))
                    if "less combat" in modifier_str.lower() or "low combat" in modifier_str.lower():
                        combat_pref = "low"
                        soft_preferences["combat"] = "low"

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
                    wanted_tags=extracted_tags,
                    wanted_genres=extracted_genres,
                    avoid_tags=avoid_tags,
                    avoid_genres=avoid_genres,
                    avoid_modes=avoid_modes,
                    is_negative_hard=is_neg_hard,
                    session_length=session_len,
                    moods=moods,
                    combat_preference=combat_pref,
                    difficulty_preference=diff_pref,
                    price_preference=price_pref,
                    hard_constraints=hard_constraints,
                    soft_preferences=soft_preferences,
                )

        # 4. Check for ENTITY query (exact title or safe alias)
        if self.lexical_index and not avoid_tags and not avoid_genres:
            entity_game = self.lexical_index.resolve_entity(query)
            if entity_game:
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
                    wanted_tags=extracted_tags,
                    wanted_genres=extracted_genres,
                    avoid_tags=avoid_tags,
                    avoid_genres=avoid_genres,
                    avoid_modes=avoid_modes,
                    is_negative_hard=is_neg_hard,
                    session_length=session_len,
                    moods=moods,
                    combat_preference=combat_pref,
                    difficulty_preference=diff_pref,
                    price_preference=price_pref,
                    hard_constraints=hard_constraints,
                    soft_preferences=soft_preferences,
                )

        # Compute translated clean search query for embedding
        norm_dict = {normalize_string(k): v for k, v in MULTILINGUAL_QUERY_DICTIONARY.items()}
        expanded_search_tokens = []
        for t in clean_tokens:
            t_clean = normalize_string(t)
            if t_clean in norm_dict:
                expanded_search_tokens.append(norm_dict[t_clean])
            else:
                expanded_search_tokens.append(t)
        translated_search_query = " ".join(expanded_search_tokens)
        clean_search_q = translated_search_query if translated_search_query != " ".join(clean_tokens) else clean_query_text

        # 5. Check for TOPIC_TAG query
        if (norm_clean in TOPIC_KEYWORDS or (len(clean_tokens) <= 2 and (extracted_tags or extracted_genres))) and not avoid_tags:
            return ParsedQuery(
                raw_query=raw_query,
                normalized_query=norm_q,
                query_type="TOPIC_TAG",
                clean_search_query=clean_search_q,
                extracted_tags=extracted_tags,
                extracted_genres=extracted_genres,
                extracted_player_modes=extracted_modes,
                confidence=0.90,
                wanted_tags=extracted_tags,
                wanted_genres=extracted_genres,
                avoid_tags=avoid_tags,
                avoid_genres=avoid_genres,
                avoid_modes=avoid_modes,
                is_negative_hard=is_neg_hard,
                session_length=session_len,
                moods=moods,
                combat_preference=combat_pref,
                difficulty_preference=diff_pref,
                price_preference=price_pref,
                hard_constraints=hard_constraints,
                soft_preferences=soft_preferences,
            )

        # 6. Check for MIXED query
        has_mode = len(extracted_modes) > 0
        has_topic = any(t in TOPIC_KEYWORDS for t in [norm_clean] + clean_tokens + expanded_search_tokens)

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
                wanted_tags=extracted_tags,
                wanted_genres=extracted_genres,
                avoid_tags=avoid_tags,
                avoid_genres=avoid_genres,
                avoid_modes=avoid_modes,
                is_negative_hard=is_neg_hard,
                session_length=session_len,
                moods=moods,
                combat_preference=combat_pref,
                difficulty_preference=diff_pref,
                price_preference=price_pref,
                hard_constraints=hard_constraints,
                soft_preferences=soft_preferences,
            )

        if has_topic and len(clean_tokens) >= 3 and (len(extracted_genres) > 0 or "rpg" in clean_tokens or "fps" in clean_tokens or "2d" in clean_tokens or "3d" in clean_tokens):
            return ParsedQuery(
                raw_query=raw_query,
                normalized_query=norm_q,
                query_type="MIXED",
                clean_search_query=clean_search_q,
                extracted_tags=extracted_tags,
                extracted_genres=extracted_genres,
                extracted_player_modes=extracted_modes,
                confidence=0.85,
                wanted_tags=extracted_tags,
                wanted_genres=extracted_genres,
                avoid_tags=avoid_tags,
                avoid_genres=avoid_genres,
                avoid_modes=avoid_modes,
                is_negative_hard=is_neg_hard,
                session_length=session_len,
                moods=moods,
                combat_preference=combat_pref,
                difficulty_preference=diff_pref,
                price_preference=price_pref,
                hard_constraints=hard_constraints,
                soft_preferences=soft_preferences,
            )

        # 7. Default to CONCEPT query
        return ParsedQuery(
            raw_query=raw_query,
            normalized_query=norm_q,
            query_type="CONCEPT",
            clean_search_query=clean_search_q,
            extracted_tags=extracted_tags,
            extracted_genres=extracted_genres,
            extracted_player_modes=extracted_modes,
            confidence=0.75,
            wanted_tags=extracted_tags,
            wanted_genres=extracted_genres,
            avoid_tags=avoid_tags,
            avoid_genres=avoid_genres,
            avoid_modes=avoid_modes,
            is_negative_hard=is_neg_hard,
            session_length=session_len,
            moods=moods,
            combat_preference=combat_pref,
            difficulty_preference=diff_pref,
            price_preference=price_pref,
            hard_constraints=hard_constraints,
            soft_preferences=soft_preferences,
        )

    def _extract_negations(self, query: str) -> Tuple[List[str], List[str], List[str], bool, str]:
        """
        Extract negated tags, genres, and player modes with hard vs soft distinction.
        Returns: (avoid_tags, avoid_genres, avoid_modes, is_hard, cleaned_positive_query)
        """
        avoid_tags: List[str] = []
        avoid_genres: List[str] = []
        avoid_modes: List[str] = []
        is_hard = False
        cleaned_text = query

        # Process hard negations first
        for pat in HARD_NEGATION_PATTERNS:
            for match in pat.finditer(query):
                term = match.group(1).strip()
                if term:
                    is_hard = True
                    self._classify_negated_term(term, avoid_tags, avoid_genres, avoid_modes)
                    # Strip the negation from cleaned query text
                    cleaned_text = pat.sub(" ", cleaned_text)

        # Process soft negations
        for pat in SOFT_NEGATION_PATTERNS:
            for match in pat.finditer(query):
                term = match.group(1).strip()
                if term:
                    self._classify_negated_term(term, avoid_tags, avoid_genres, avoid_modes)
                    cleaned_text = pat.sub(" ", cleaned_text)

        # Clean up whitespace
        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()
        if not cleaned_text:
            cleaned_text = query

        return (
            list(dict.fromkeys(avoid_tags)),
            list(dict.fromkeys(avoid_genres)),
            list(dict.fromkeys(avoid_modes)),
            is_hard,
            cleaned_text,
        )

    def _classify_negated_term(
        self,
        term: str,
        avoid_tags: List[str],
        avoid_genres: List[str],
        avoid_modes: List[str],
    ) -> None:
        """Classify a negated phrase into tags, genres, or player modes."""
        sub_terms = re.split(r"\s+(?:or|and)\s+", term, flags=re.IGNORECASE)
        for sub in sub_terms:
            sub_clean = sub.strip()
            if not sub_clean:
                continue
            norm = normalize_string(sub_clean)

            # 1. Player mode check
            norm_mode_dict = {normalize_string(k): v for k, v in PLAYER_MODE_KEYWORDS.items()}
            for k, v in norm_mode_dict.items():
                if k == norm or k in norm:
                    avoid_modes.append(v)

            # 2. Known genre / tag taxonomy
            if norm in ("horror", "scary", "terror"):
                avoid_genres.append("Horror")
                avoid_tags.extend(["Horror", "Survival Horror", "Psychological Horror"])
            elif norm in ("action", "combat", "intense combat", "heavy combat", "fighting"):
                avoid_genres.append("Action")
                avoid_tags.extend(["Action", "Combat", "Violent"])
            elif norm in ("rpg", "role playing", "role-playing"):
                avoid_genres.append("RPG")
            elif norm in ("strategy", "rts", "tactical"):
                avoid_genres.append("Strategy")
            elif norm in ("puzzle", "logic"):
                avoid_genres.append("Puzzle")
            elif norm in ("racing", "driving"):
                avoid_genres.append("Racing")
            elif norm in ("pvp", "competitive"):
                avoid_modes.append("PvP")
                avoid_tags.append("PvP")
            else:
                avoid_tags.append(sub_clean.title())


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

    def _extract_moods(self, normalized_query: str, clean_query_text: str = "") -> List[str]:
        """Extract explicit mood/tone descriptors from positive query portion without over-inferring."""
        target = normalize_string(clean_query_text) if clean_query_text else normalized_query
        found = []
        for word, mood in MOOD_KEYWORDS.items():
            pattern = r"\b" + re.escape(word) + r"\b"
            if re.search(pattern, target, re.IGNORECASE) and mood not in found:
                found.append(mood)
        return found

    def _extract_combat_preference(self, normalized_query: str, avoid_tags: Optional[List[str]] = None) -> Optional[str]:
        """Extract combat preference (low, high) from explicit query mentions."""
        if avoid_tags and any(t in ("Action", "Combat", "Violent") for t in avoid_tags):
            return "low"
        if re.search(r"\b(?:no combat|without combat|less combat|low combat|peaceful|non-violent|no fighting)\b", normalized_query, re.I):
            return "low"
        if re.search(r"\b(?:heavy combat|intense combat|lots of combat|hack and slash|fighting)\b", normalized_query, re.I):
            return "high"
        return None


    def _extract_difficulty_preference(self, normalized_query: str) -> Optional[str]:
        """Extract explicit difficulty preference without over-inferring."""
        if re.search(r"\b(?:punishing|soulslike|rage game|unforgiving|brutal|hardcore)\b", normalized_query, re.I):
            return "punishing"
        if re.search(r"\b(?:hard|difficult|challenging|tough)\b", normalized_query, re.I):
            return "hard"
        if re.search(r"\b(?:easy|casual|relaxing|chill|simple)\b", normalized_query, re.I):
            return "easy"
        return None

    def _extract_session_length(self, normalized_query: str) -> Optional[str]:
        """Extract session length preference from time mentions."""
        for pattern, length in SESSION_LENGTH_PATTERNS:
            if pattern.search(normalized_query):
                return length
        return None

    def _extract_price_preference(self, normalized_query: str) -> Tuple[Optional[str], bool]:
        """Extract price preference and boolean is_free requirement."""
        if re.search(r"\b(?:free to play|free-to-play|free game|free games|f2p|zero cost)\b", normalized_query, re.I):
            return "free", True
        if re.search(r"\b(?:under ₹?\d+|cheap|budget|affordable)\b", normalized_query, re.I):
            return "budget", False
        return None, False
