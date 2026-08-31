import logging
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from app.schemas.discovery import (
    DiscoveryFilters,
    DiscoverySearchResult,
    DiscoverySessionContext,
    GameDiscoveryItem,
    StorefrontItem,
)
from app.search.lexical import normalize_string, tokenize
from app.search.query_parser import ParsedQuery
from app.search.ranking_config import (
    DEFAULT_MODE,
    DIRECT_SCORE_WEIGHT,
    DISCOVERY_MODES,
    DIVERSITY_LAMBDA,
    HIDDEN_GEM_MAX_REVIEWS,
    HIDDEN_GEM_MIN_POSITIVE_PCT,
    HIDDEN_GEM_MIN_REVIEWS,
    MAX_PERSONALIZATION_BOOST,
    MAX_SAME_FRANCHISE,
    MAX_STEAM_REVIEWS_LOG,
    MAX_TOTAL_NEGATIVE_PENALTY,
    MIN_MATCH_SCORE_THRESHOLD,
    NEGATIVE_VECTOR_PENALTY,
    NOVELTY_WEIGHT,
    PERSONALIZATION_GENRE_WEIGHT,
    PERSONALIZATION_VECTOR_WEIGHT,
    QUALITY_WEIGHT,
    QUERY_TYPE_WEIGHTS,
    RRF_K,
    RRF_SCORE_WEIGHT,
    SAME_FRANCHISE_PENALTY,
    SOFT_NEGATIVE_GENRE_PENALTY,
    SOFT_NEGATIVE_TAG_PENALTY,
    STRONG_MATCH_THRESHOLD,
)


logger = logging.getLogger(__name__)


class Ranker:
    """Discovery Intelligence V1 Hybrid Ranker.

    Modular scoring pipeline combining:
    - Query-type dynamic weights & Reciprocal Rank Fusion (RRF)
    - Deterministic hard constraint filtering & hard negative exclusions
    - Additive, bounded user personalization (Game DNA genres + FAISS liked vector)
    - Negative preference penalties (soft avoid tags/genres + disliked vectors)
    - Multi-mode ranking adjustments (BEST_MATCH, DISCOVER, HIDDEN_GEMS, POPULAR)
    - Bounded diversity reranking with soft franchise/family constraints
    - Grounded explanations, honest trade-offs, and personalization evidence.
    """

    @staticmethod
    def passes_filters(
        game: Dict[str, Any],
        filters: Optional[DiscoveryFilters] = None,
        hard_constraints: Optional[Dict[str, Any]] = None,
        session_context: Optional[DiscoverySessionContext] = None,
    ) -> bool:
        """Evaluate deterministic boolean, categorical, and hard-negative constraints."""
        # 1. Standard explicit DiscoveryFilters
        if filters:
            for filter_attr, game_field in (
                ("platforms", "platforms"),
                ("player_modes", "player_modes"),
                ("genres", "genres"),
                ("tags", "tags"),
            ):
                requested = getattr(filters, filter_attr)
                if requested:
                    requested_norm = {v.lower() for v in requested}
                    game_norm = {v.lower() for v in game.get(game_field, [])}
                    if not requested_norm.intersection(game_norm):
                        return False

            if filters.is_free is not None:
                if game.get("is_free", False) != filters.is_free:
                    return False

            if filters.min_year is not None or filters.max_year is not None:
                year = game.get("release_year", 0)
                if year <= 0:
                    return False
                if filters.min_year is not None and year < filters.min_year:
                    return False
                if filters.max_year is not None and year > filters.max_year:
                    return False

        # 2. Hard constraints parsed from query (e.g. "free to play", "without horror")
        if hard_constraints:
            if hard_constraints.get("is_free") and not game.get("is_free", False):
                return False

            avoid_genres = hard_constraints.get("avoid_genres", [])
            if avoid_genres:
                avoid_g_norm = {g.lower() for g in avoid_genres}
                game_g_norm = {g.lower() for g in game.get("genres", [])}
                if avoid_g_norm.intersection(game_g_norm):
                    return False

            avoid_tags = hard_constraints.get("avoid_tags", [])
            if avoid_tags:
                avoid_t_norm = {t.lower() for t in avoid_tags}
                game_t_norm = {t.lower() for t in game.get("tags", [])}
                if avoid_t_norm.intersection(game_t_norm):
                    return False

            avoid_modes = hard_constraints.get("avoid_modes", [])
            if avoid_modes:
                avoid_m_norm = {m.lower() for m in avoid_modes}
                game_m_norm = {m.lower() for m in game.get("player_modes", [])}
                if avoid_m_norm.intersection(game_m_norm):
                    return False

        # 3. Session-scoped hard negative exclusions (e.g. Less Like This game IDs)
        if session_context and session_context.less_like_this_game_ids:
            gid = str(game.get("id"))
            ext_id = str(game.get("external_id", ""))
            if gid in session_context.less_like_this_game_ids or ext_id in session_context.less_like_this_game_ids:
                return False

        return True

    @staticmethod
    def extract_evidence(
        parsed_query: ParsedQuery,
        game: Dict[str, Any],
        lexical_details: Optional[Dict[str, Any]] = None,
        is_seed_similarity: bool = False,
    ) -> List[str]:
        """Generate structured evidence bullet points grounded in actual catalog metadata."""
        evidence: List[str] = []
        q_tokens = set(tokenize(parsed_query.raw_query))
        game_tags_norm = {normalize_string(t): t for t in game.get("tags", [])}
        game_genres_norm = {normalize_string(g): g for g in game.get("genres", [])}
        game_modes_norm = {normalize_string(m): m for m in game.get("player_modes", [])}

        # 1. Entity / Title Match Evidence
        if lexical_details and lexical_details.get("exact_title"):
            evidence.append(f"Exact title match for '{game.get('title')}'")
        elif parsed_query.target_entity and normalize_string(parsed_query.target_entity) in normalize_string(game.get("title", "")):
            evidence.append(f"Matches title '{game.get('title')}'")
        elif is_seed_similarity and parsed_query.target_entity:
            evidence.append(f"Shares genre & gameplay loop with {parsed_query.target_entity}")

        # 2. Tag matches
        matched_tags: List[str] = []
        q_norm = parsed_query.normalized_query
        q_comp = re.sub(r"[\s-]", "", q_norm)
        for orig_t in game.get("tags", []):
            t_norm = normalize_string(orig_t)
            t_comp = re.sub(r"[\s-]", "", t_norm)
            if (t_norm in q_tokens or t_comp == q_comp or q_norm in t_norm or t_norm in q_norm) and orig_t not in matched_tags:
                matched_tags.append(orig_t)
        for t in matched_tags[:3]:
            evidence.append(f"{t} tag")

        # 3. Genre matches
        matched_genres: List[str] = []
        for t in q_tokens:
            if t in game_genres_norm and game_genres_norm[t] not in matched_genres:
                matched_genres.append(game_genres_norm[t])
        for g in matched_genres[:2]:
            evidence.append(f"{g} genre")

        # 4. Player mode matches
        for mode in parsed_query.extracted_player_modes:
            norm_m = normalize_string(mode)
            if norm_m in game_modes_norm:
                evidence.append(f"{mode} mode")

        # 5. Steam review acclaim signal
        reviews = game.get("total_reviews", 0)
        pos_pct = game.get("positive_percent", 0.0)
        desc_rev = game.get("review_score_desc", "")
        if reviews >= 50000 and pos_pct >= 85:
            evidence.append(f"Steam acclaim ({pos_pct:.0f}% positive, {reviews//1000}k+ reviews)")
        elif desc_rev and desc_rev not in ("\\N", "") and reviews >= 1000:
            evidence.append(f"Rated '{desc_rev}' on Steam")

        # Fallback if no direct tokens matched
        if not evidence:
            top_tags = list(game.get("tags", []))[:2]
            top_genres = list(game.get("genres", []))[:1]
            if top_tags:
                evidence.append(f"Thematic match ({', '.join(top_tags)})")
            if top_genres:
                evidence.append(f"{top_genres[0]} gameplay")

        return evidence[:5]

    @classmethod
    def extract_highlights(cls, query: Any, game: Dict[str, Any]) -> List[str]:
        """Compatibility helper for extract_evidence with raw string queries."""
        if isinstance(query, ParsedQuery):
            return cls.extract_evidence(query, game)
        from app.search.query_parser import QueryParser
        parsed = QueryParser().parse(str(query))
        return cls.extract_evidence(parsed, game)

    @classmethod
    def generate_explanation(
        cls,
        parsed_query: Any = None,
        game: Optional[Dict[str, Any]] = None,
        evidence: Optional[List[str]] = None,
        query: Optional[str] = None,
        highlights: Optional[List[str]] = None,
        trade_offs: Optional[List[str]] = None,
        personalization_reasons: Optional[List[str]] = None,
    ) -> str:
        """Construct a deterministic evidence-based explanation for why the game matches."""
        from app.search.query_parser import QueryParser
        if isinstance(parsed_query, str):
            parsed = QueryParser().parse(parsed_query)
        elif parsed_query is None and query is not None:
            parsed = QueryParser().parse(query)
        elif isinstance(parsed_query, ParsedQuery):
            parsed = parsed_query
        else:
            parsed = QueryParser().parse("")

        ev = evidence if evidence is not None else (highlights or [])
        traits_str = ", ".join(ev) if ev else "thematic and mechanical synergy"
        game_dict = game or {}
        genre_str = ", ".join(game_dict.get("genres", [])[:2]) or "Gameplay"

        base_explanation = ""
        if parsed.query_type == "ENTITY":
            base_explanation = f"Matches canonical game '{game_dict.get('title')}' across {genre_str}."
        elif parsed.query_type == "SIMILARITY" and parsed.target_entity:
            base_explanation = f"Recommended for fans of {parsed.target_entity} based on {traits_str}."
        elif parsed.query_type == "TOPIC_TAG":
            base_explanation = f"Strong match for '{parsed.raw_query}' with {traits_str}."
        else:
            rev_desc = game_dict.get("review_score_desc", "")
            if rev_desc and rev_desc not in ("\\N", ""):
                base_explanation = f"Matches your concept with {traits_str}, {rev_desc} on Steam across {genre_str}."
            else:
                base_explanation = f"Matches your concept across {genre_str} with {traits_str}."

        # Add trade-off note if relevant
        if trade_offs:
            base_explanation += f" Note: {trade_offs[0]}."

        return base_explanation

    @classmethod
    def calibrate_score(
        cls,
        raw_hybrid_score: float,
        query_type: str,
        is_exact_entity: bool = False,
    ) -> float:
        """Calibrate hybrid score to a defined 0.0 - 1.0 relevance scale."""
        if is_exact_entity:
            return 0.98

        clamped = max(0.0, min(1.0, raw_hybrid_score))

        # S-curve calibration to map dense cosine + lexical scores cleanly
        if clamped >= 0.75:
            calibrated = 0.85 + (clamped - 0.75) * 0.52
        elif clamped >= 0.50:
            calibrated = 0.70 + (clamped - 0.50) * 0.60
        elif clamped >= 0.30:
            calibrated = 0.50 + (clamped - 0.30) * 1.00
        else:
            calibrated = clamped * 1.66

        return round(max(0.0, min(0.99, calibrated)), 4)

    @classmethod
    def rank_and_format(
        cls,
        candidates: List[Tuple[Dict[str, Any], float]],
        query: str,
        filters: Optional[DiscoveryFilters] = None,
        limit: int = 12,
        min_threshold: float = MIN_MATCH_SCORE_THRESHOLD,
    ) -> List[DiscoverySearchResult]:
        """Legacy helper wrapping rank_hybrid for pure candidate tuples."""
        from app.search.query_parser import QueryParser
        parsed = QueryParser().parse(query)
        return cls.rank_hybrid(
            semantic_candidates=candidates,
            lexical_candidates=[],
            parsed_query=parsed,
            filters=filters,
            limit=limit,
            min_threshold=min_threshold,
        )

    @classmethod
    def check_hidden_gem(cls, game: Dict[str, Any]) -> bool:
        """Evaluate whether a game satisfies the objective Hidden Gem criteria."""
        reviews = game.get("total_reviews", 0)
        pos_pct = game.get("positive_percent", 0.0)
        return (
            reviews >= HIDDEN_GEM_MIN_REVIEWS
            and reviews <= HIDDEN_GEM_MAX_REVIEWS
            and pos_pct >= HIDDEN_GEM_MIN_POSITIVE_PCT
        )

    @classmethod
    def extract_trade_offs(
        cls,
        parsed_query: ParsedQuery,
        game: Dict[str, Any],
    ) -> List[str]:
        """Identify honest, factual trade-offs where game deviates slightly from prompt."""
        trade_offs: List[str] = []
        tags_lower = {t.lower() for t in game.get("tags", [])}

        # 1. Combat check
        if parsed_query.combat_preference == "low":
            if any(t in tags_lower for t in ("action", "combat", "violent", "hack and slash", "shooter")):
                trade_offs.append("Contains moderate action/combat")

        # 2. Difficulty check
        if parsed_query.difficulty_preference == "easy":
            if any(t in tags_lower for t in ("souls-like", "difficult", "permadeath", "unforgiving")):
                trade_offs.append("Has steeper difficulty than requested")

        # 3. Session length check
        if parsed_query.session_length == "short":
            if any(t in tags_lower for t in ("grand strategy", "4x", "crpg")):
                trade_offs.append("Typically requires longer play sessions")

        return trade_offs[:2]

    @classmethod
    def extract_personalization_reasons(
        cls,
        user_top_genres: List[str],
        game: Dict[str, Any],
    ) -> List[str]:
        """Generate truthful personalization evidence grounded in user's profile."""
        reasons: List[str] = []
        if not user_top_genres:
            return reasons

        game_genres = {g.lower() for g in game.get("genres", [])}
        for user_g in user_top_genres[:3]:
            if user_g.lower() in game_genres:
                reasons.append(f"Matches your affinity for {user_g}")

        return reasons[:2]

    @classmethod
    def rank_hybrid(
        cls,
        semantic_candidates: List[Tuple[Dict[str, Any], float]],
        lexical_candidates: List[Tuple[Dict[str, Any], float, Dict[str, Any]]],
        parsed_query: ParsedQuery,
        filters: Optional[DiscoveryFilters] = None,
        limit: int = 12,
        min_threshold: float = MIN_MATCH_SCORE_THRESHOLD,
        mode: str = DEFAULT_MODE,
        session_context: Optional[DiscoverySessionContext] = None,
        user_preferences: Optional[Any] = None,
        user_liked_vector: Optional[np.ndarray] = None,
        user_disliked_vector: Optional[np.ndarray] = None,
        index_manager: Optional[Any] = None,
    ) -> List[DiscoverySearchResult]:
        """Execute the Discovery Intelligence V1 multi-signal ranking and diversity pipeline."""
        candidate_pool: Dict[str, Dict[str, Any]] = {}
        sem_ranks: Dict[str, int] = {}
        sem_scores: Dict[str, float] = {}
        lex_ranks: Dict[str, int] = {}
        lex_scores: Dict[str, float] = {}
        lex_details_map: Dict[str, Dict[str, Any]] = {}

        # 1. Ingest Candidates
        for rank, (game, score) in enumerate(semantic_candidates, 1):
            gid = str(game.get("id"))
            candidate_pool[gid] = game
            sem_ranks[gid] = rank
            sem_scores[gid] = max(0.0, float(score))

        for rank, (game, score, details) in enumerate(lexical_candidates, 1):
            gid = str(game.get("id"))
            candidate_pool[gid] = game
            lex_ranks[gid] = rank
            lex_scores[gid] = max(0.0, float(score))
            lex_details_map[gid] = details

        # 2. Lookup Mode Configuration & Base Weights
        mode_adj = DISCOVERY_MODES.get(mode, DISCOVERY_MODES[DEFAULT_MODE])
        q_type = parsed_query.query_type
        base_weights = QUERY_TYPE_WEIGHTS.get(q_type, QUERY_TYPE_WEIGHTS["CONCEPT"])

        w_sem = base_weights.w_sem
        w_lex = base_weights.w_lex
        w_pop = base_weights.w_pop

        # User profile top genres (if user has real Game DNA data)
        user_top_genres: List[str] = []
        if user_preferences and getattr(user_preferences, "has_sufficient_data", False):
            user_top_genres = [item.genre for item in getattr(user_preferences, "top_genres", [])]

        # 3. Score Candidates
        scored_candidates: List[Tuple[str, float, bool, Dict[str, Any]]] = []
        norm_target = normalize_string(parsed_query.target_entity or "")
        norm_query = parsed_query.normalized_query

        # Check soft negative terms from query + session
        soft_avoid_tags = list(parsed_query.avoid_tags)
        soft_avoid_genres = list(parsed_query.avoid_genres)
        if session_context:
            if session_context.temporary_avoid_tags:
                soft_avoid_tags.extend(session_context.temporary_avoid_tags)
            if session_context.temporary_avoid_genres:
                soft_avoid_genres.extend(session_context.temporary_avoid_genres)

        for gid, game in candidate_pool.items():
            # Apply hard constraints, year/platform filters, and hard negative exclusions
            if not cls.passes_filters(
                game=game,
                filters=filters,
                hard_constraints=parsed_query.hard_constraints,
                session_context=session_context,
            ):
                continue

            game_title_norm = normalize_string(game.get("title", ""))
            reviews = game.get("total_reviews", 0)
            pos_pct = game.get("positive_percent", 0.0) / 100.0

            # Title exact match check
            has_substantial_reviews = reviews >= 2000
            is_exact_title = (
                (q_type == "ENTITY" and ((norm_target and game_title_norm == norm_target) or (norm_query and game_title_norm == norm_query)))
                or (lex_details_map.get(gid, {}).get("exact_title", False) and has_substantial_reviews)
            )

            if q_type == "ENTITY" and is_exact_title:
                hybrid_score = 1.0
                scored_candidates.append((gid, hybrid_score, is_exact_title, {}))
                continue

            # Core Relevance: RRF + Weighted Direct
            r_sem = sem_ranks.get(gid, 200)
            r_lex = lex_ranks.get(gid, 200)
            rrf_score = (1.0 / (RRF_K + r_sem)) + (1.0 / (RRF_K + r_lex))

            s_sem = sem_scores.get(gid, 0.0)
            s_lex = lex_scores.get(gid, 0.0)

            # Popularity / Review volume
            pop_signal = 0.0
            if reviews > 0:
                log_rev = min(1.0, math.log10(max(1, reviews)) / MAX_STEAM_REVIEWS_LOG)
                pop_signal = log_rev * pos_pct

            direct_score = (w_sem * s_sem) + (w_lex * s_lex) + (w_pop * pop_signal)
            norm_rrf = min(1.0, rrf_score * (RRF_K / 2.0))
            core_relevance = (DIRECT_SCORE_WEIGHT * direct_score) + (RRF_SCORE_WEIGHT * norm_rrf)

            # Topic tag landmark boost
            if q_type == "TOPIC_TAG":
                norm_q_comp = re.sub(r"[\s-]", "", norm_query)
                tags_comp = {re.sub(r"[\s-]", "", normalize_string(t)) for t in game.get("tags", [])}
                genres_comp = {re.sub(r"[\s-]", "", normalize_string(g)) for g in game.get("genres", [])}
                if norm_q_comp in tags_comp or norm_q_comp in genres_comp:
                    if reviews >= 50000:
                        core_relevance += 0.25
                    elif reviews >= 10000:
                        core_relevance += 0.15
                    elif reviews >= 1000:
                        core_relevance += 0.08
                    else:
                        core_relevance += 0.04

            # Quality term
            quality_score = QUALITY_WEIGHT * (pos_pct * min(1.0, reviews / 2000.0)) * mode_adj.quality_mult

            # Novelty term (rewards high acclaim games with fewer reviews in DISCOVER / HIDDEN_GEMS)
            novelty_score = 0.0
            if reviews >= HIDDEN_GEM_MIN_REVIEWS and pos_pct >= 0.80:
                inv_log = max(0.0, 1.0 - (math.log10(max(10, reviews)) / 5.0))
                novelty_score = NOVELTY_WEIGHT * inv_log * mode_adj.novelty_mult

            # Personalization boost (strictly bounded, additive)
            personalization_boost = 0.0
            game_genres = {g.lower() for g in game.get("genres", [])}
            if user_top_genres:
                for g_idx, u_genre in enumerate(user_top_genres[:3]):
                    if u_genre.lower() in game_genres:
                        personalization_boost += (PERSONALIZATION_GENRE_WEIGHT / (g_idx + 1))

            # FAISS vector personalization (if precomputed vector exists)
            game_vec: Optional[np.ndarray] = None
            if index_manager and (user_liked_vector is not None or user_disliked_vector is not None):
                game_vec = index_manager.get_vector(gid)

            if user_liked_vector is not None and game_vec is not None:
                sim = float(np.dot(user_liked_vector, game_vec))
                if sim > 0.40:
                    personalization_boost += PERSONALIZATION_VECTOR_WEIGHT * (sim - 0.40)

            personalization_boost = min(MAX_PERSONALIZATION_BOOST, personalization_boost) * mode_adj.personalization_mult

            # Negative preference penalties (soft)
            negative_penalty = 0.0
            game_tags_lower = {t.lower() for t in game.get("tags", [])}

            if soft_avoid_tags:
                for at in soft_avoid_tags:
                    if at.lower() in game_tags_lower:
                        negative_penalty += SOFT_NEGATIVE_TAG_PENALTY
            if soft_avoid_genres:
                for ag in soft_avoid_genres:
                    if ag.lower() in game_genres:
                        negative_penalty += SOFT_NEGATIVE_GENRE_PENALTY
            if user_disliked_vector is not None and game_vec is not None:
                dis_sim = float(np.dot(user_disliked_vector, game_vec))
                if dis_sim > 0.45:
                    negative_penalty += NEGATIVE_VECTOR_PENALTY * (dis_sim - 0.45)

            negative_penalty = min(MAX_TOTAL_NEGATIVE_PENALTY, negative_penalty)

            # Combined hybrid score (Relevance remains dominant)
            final_score = (
                (core_relevance * mode_adj.relevance_mult)
                + quality_score
                + novelty_score
                + personalization_boost
                - negative_penalty
            )

            scored_candidates.append(
                (
                    gid,
                    max(0.0, final_score),
                    is_exact_title,
                    {"game_vec": game_vec, "personalization_boost": personalization_boost},
                )
            )

        # Sort descending by preliminary score
        scored_candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)

        # 4. Diversity Reranking (Soft Franchise/Family Limitation + Bounded MMR)
        # If user explicitly asked for a franchise (e.g. "Final Fantasy"), do not penalize it!
        query_is_explicit_entity = (q_type == "ENTITY")
        selected_candidates: List[Tuple[str, float, bool]] = []
        franchise_counts: Dict[str, int] = {}

        for gid, score, is_exact, aux in scored_candidates:
            game = candidate_pool[gid]
            franchise_key = cls._extract_franchise_family(game.get("title", ""))

            # Soft franchise limitation (max 2 per family by default, unless exact entity)
            if not query_is_explicit_entity and franchise_key:
                current_count = franchise_counts.get(franchise_key, 0)
                if current_count >= MAX_SAME_FRANCHISE:
                    # Apply soft penalty rather than hard discarding
                    score -= SAME_FRANCHISE_PENALTY * (current_count - MAX_SAME_FRANCHISE + 1)
                franchise_counts[franchise_key] = current_count + 1

            selected_candidates.append((gid, score, is_exact))

        # Re-sort after soft franchise adjustment
        selected_candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)

        # 5. Format Results
        results: List[DiscoverySearchResult] = []
        for gid, raw_score, is_exact in selected_candidates:
            calibrated = cls.calibrate_score(raw_score, q_type, is_exact_entity=is_exact)

            if calibrated < min_threshold and not is_exact:
                continue

            game = candidate_pool[gid]
            lex_details = lex_details_map.get(gid, {})
            is_similarity = q_type == "SIMILARITY"

            evidence = cls.extract_evidence(
                parsed_query=parsed_query,
                game=game,
                lexical_details=lex_details,
                is_seed_similarity=is_similarity,
            )
            trade_offs = cls.extract_trade_offs(parsed_query, game)
            personalization_reasons = cls.extract_personalization_reasons(user_top_genres, game)
            explanation = cls.generate_explanation(
                parsed_query=parsed_query,
                game=game,
                evidence=evidence,
                trade_offs=trade_offs,
                personalization_reasons=personalization_reasons,
            )
            is_gem = cls.check_hidden_gem(game)

            display_desc = game.get("display_description") or game.get("description") or game.get("original_description", "")
            desc_lang = game.get("description_language", "en")
            desc_source = game.get("description_source", "steam")

            source = game.get("source", "steam")
            ext_id = str(game.get("external_id", game.get("id")))

            cover_image_url = None
            hero_image_url = None
            storefronts = []
            if source == "steam" and ext_id:
                cover_image_url = f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{ext_id}/header.jpg"
                hero_image_url = f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{ext_id}/capsule_616x353.jpg"
                storefronts = [
                    StorefrontItem(
                        provider="steam",
                        name="Steam",
                        url=f"https://store.steampowered.com/app/{ext_id}/",
                        platform="PC",
                    )
                ]

            item = GameDiscoveryItem(
                id=str(game.get("id")),
                external_id=ext_id,
                source=source,
                title=game.get("display_title") or game.get("title", ""),
                display_title=game.get("display_title") or game.get("title", ""),
                description=display_desc,
                display_description=display_desc,
                original_description=game.get("original_description"),
                description_language=desc_lang,
                description_source=desc_source,
                genres=game.get("display_genres") or game.get("genres") or game.get("canonical_genres", []),
                display_genres=game.get("display_genres") or game.get("genres") or game.get("canonical_genres", []),
                original_genres=game.get("original_genres", []),
                tags=game.get("display_tags") or game.get("tags") or game.get("search_tags", []),
                display_tags=game.get("display_tags") or game.get("tags") or game.get("search_tags", []),
                original_tags=game.get("original_tags", []),
                player_modes=game.get("player_modes", []),
                platforms=game.get("platforms", ["PC"]),
                release_year=game.get("release_year", 0),
                is_free=game.get("is_free", False),
                total_reviews=game.get("total_reviews", 0),
                positive_percent=game.get("positive_percent", 0.0),
                review_score_desc=game.get("review_score_desc", ""),
                cover_image_url=cover_image_url,
                hero_image_url=hero_image_url,
                screenshots=[],
                storefronts=storefronts,
            )

            results.append(
                DiscoverySearchResult(
                    game=item,
                    score=calibrated,
                    match_highlights=evidence,
                    explanation=explanation,
                    is_hidden_gem=is_gem,
                    trade_offs=trade_offs,
                    personalization_reasons=personalization_reasons,
                )
            )

            if len(results) >= limit:
                break

        return results

    @staticmethod
    def _extract_franchise_family(title: str) -> Optional[str]:
        """Extract canonical franchise prefix (e.g. 'Civilization VI' -> 'civilization')."""
        if not title:
            return None
        norm = normalize_string(title)
        # Strip roman numerals and numbers from the end
        clean = re.sub(r"\b(?:i|ii|iii|iv|v|vi|vii|viii|ix|x|\d+)\b.*$", "", norm, flags=re.I).strip()
        # Clean colons/subtitles
        if ":" in clean:
            clean = clean.split(":")[0].strip()
        tokens = clean.split()
        if len(tokens) >= 1:
            return tokens[0] if len(tokens[0]) > 3 else clean
        return None

    @classmethod
    def generate_why_these_summary(
        cls,
        parsed_query: ParsedQuery,
        results: List[DiscoverySearchResult],
        mode: str,
        personalized: bool,
    ) -> Optional[str]:
        """Construct grounded, concise top-level summary paragraph for Why These banner."""
        if not results:
            return None

        top_genres = list({g for r in results[:5] for g in r.game.genres})[:2]
        genres_str = " & ".join(top_genres) if top_genres else "Gameplay"

        mode_str = ""
        if mode == "HIDDEN_GEMS":
            mode_str = " focused on high-acclaim community gems"
        elif mode == "POPULAR":
            mode_str = " highlighting top community favorites"
        elif mode == "DISCOVER":
            mode_str = " prioritizing thematic diversity"

        pers_str = " and tailored to your creator profile" if personalized else ""

        if parsed_query.query_type == "ENTITY":
            return f"Found exact match and related titles for '{parsed_query.target_entity}' across {genres_str}{mode_str}."
        elif parsed_query.query_type == "SIMILARITY":
            return f"Ranked closest mechanical and thematic neighbors to {parsed_query.target_entity}{mode_str}{pers_str}."
        else:
            return f"Curated {genres_str} recommendations matching your concept{mode_str}{pers_str}."
