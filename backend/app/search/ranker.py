import logging
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.discovery import (
    DiscoveryFilters,
    DiscoverySearchResult,
    GameDiscoveryItem,
)
from app.search.lexical import normalize_string, tokenize
from app.search.query_parser import ParsedQuery


logger = logging.getLogger(__name__)

MIN_MATCH_SCORE_THRESHOLD = 0.30
STRONG_MATCH_THRESHOLD = 0.70


class Ranker:
    """Hybrid Ranker integrating Reciprocal Rank Fusion, query-type dynamic weighting, calibrated scoring, and evidence explanations."""

    @staticmethod
    def passes_filters(game: Dict[str, Any], filters: Optional[DiscoveryFilters]) -> bool:
        """Evaluate deterministic boolean and categorical hard constraints."""
        if not filters:
            return True

        # 1-4. Categorical intersection filters (platforms, player_modes, genres, tags):
        # each requires at least one case-insensitive overlap between the requested set
        # and the game's set for that field.
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

        # 5. Free-to-play filter
        if filters.is_free is not None:
            if game.get("is_free", False) != filters.is_free:
                return False

        # 6. Release year filter. A game with unknown release_year (0) is excluded from
        # any year-bounded search rather than silently passing through — an unverified
        # year cannot be said to satisfy an explicit min_year/max_year constraint. This
        # previously let ~23% of the catalog (all unknown-year records) bypass explicit
        # year filters entirely.
        if filters.min_year is not None or filters.max_year is not None:
            year = game.get("release_year", 0)
            if year <= 0:
                return False
            if filters.min_year is not None and year < filters.min_year:
                return False
            if filters.max_year is not None and year > filters.max_year:
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
        
        if parsed.query_type == "ENTITY":
            return f"Matches canonical game '{game_dict.get('title')}' across {genre_str}."
        elif parsed.query_type == "SIMILARITY" and parsed.target_entity:
            return f"Recommended for fans of {parsed.target_entity} based on {traits_str}."
        elif parsed.query_type == "TOPIC_TAG":
            return f"Strong match for '{parsed.raw_query}' with {traits_str}."
        else:
            rev_desc = game_dict.get("review_score_desc", "")
            if rev_desc and rev_desc not in ("\\N", ""):
                return f"Matches your concept with {traits_str}, {rev_desc} on Steam across {genre_str}."
            return f"Matches your concept across {genre_str} with {traits_str}."

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
    def calibrate_score(
        cls,
        raw_hybrid_score: float,
        query_type: str,
        is_exact_entity: bool = False,
    ) -> float:
        """
        Calibrate hybrid score to a defined 0.0 - 1.0 relevance scale:
        >= 0.85 : STRONG MATCH (85% - 98%)
        0.70 - 0.84 : GOOD MATCH (70% - 84%)
        0.50 - 0.69 : POSSIBLE MATCH (50% - 69%)
        < 0.50 : WEAK MATCH
        """
        if is_exact_entity:
            return 0.98

        # S-curve calibration to map dense cosine + lexical scores cleanly
        clamped = max(0.0, min(1.0, raw_hybrid_score))
        
        # Scaling function: boost scores in the 0.40-0.75 range into intuitive relevance bands
        if clamped >= 0.75:
            calibrated = 0.85 + (clamped - 0.75) * 0.52  # 0.75 -> 0.85, 1.0 -> 0.98
        elif clamped >= 0.50:
            calibrated = 0.70 + (clamped - 0.50) * 0.60  # 0.50 -> 0.70, 0.75 -> 0.85
        elif clamped >= 0.30:
            calibrated = 0.50 + (clamped - 0.30) * 1.00  # 0.30 -> 0.50, 0.50 -> 0.70
        else:
            calibrated = clamped * 1.66  # 0.0 -> 0.0, 0.30 -> 0.50

        return round(max(0.0, min(0.99, calibrated)), 4)

    @classmethod
    def rank_hybrid(
        cls,
        semantic_candidates: List[Tuple[Dict[str, Any], float]],
        lexical_candidates: List[Tuple[Dict[str, Any], float, Dict[str, Any]]],
        parsed_query: ParsedQuery,
        filters: Optional[DiscoveryFilters] = None,
        limit: int = 12,
        min_threshold: float = MIN_MATCH_SCORE_THRESHOLD,
    ) -> List[DiscoverySearchResult]:
        """
        Combine lexical and semantic candidates using Reciprocal Rank Fusion (RRF)
        and query-type dynamic weighting, then filter, calibrate, and format results.
        """
        candidate_pool: Dict[str, Dict[str, Any]] = {}
        sem_ranks: Dict[str, int] = {}
        sem_scores: Dict[str, float] = {}
        lex_ranks: Dict[str, int] = {}
        lex_scores: Dict[str, float] = {}
        lex_details_map: Dict[str, Dict[str, Any]] = {}

        # 1. Ingest Semantic Candidates
        for rank, (game, score) in enumerate(semantic_candidates, 1):
            gid = str(game.get("id"))
            candidate_pool[gid] = game
            sem_ranks[gid] = rank
            sem_scores[gid] = max(0.0, float(score))

        # 2. Ingest Lexical Candidates
        for rank, (game, score, details) in enumerate(lexical_candidates, 1):
            gid = str(game.get("id"))
            candidate_pool[gid] = game
            lex_ranks[gid] = rank
            lex_scores[gid] = max(0.0, float(score))
            lex_details_map[gid] = details

        # 3. Dynamic Query Weights
        q_type = parsed_query.query_type
        if q_type == "ENTITY":
            w_sem = 0.20
            w_lex = 0.65
            w_pop = 0.15
        elif q_type == "SIMILARITY":
            w_sem = 0.55
            w_lex = 0.30
            w_pop = 0.15
        elif q_type == "TOPIC_TAG":
            w_sem = 0.35
            w_lex = 0.45
            w_pop = 0.20
        elif q_type == "MIXED":
            w_sem = 0.40
            w_lex = 0.45
            w_pop = 0.15
        else:  # CONCEPT
            w_sem = 0.55
            w_lex = 0.35
            w_pop = 0.10

        # 4. RRF + Hybrid Score Computation
        RRF_K = 60.0
        scored_candidates: List[Tuple[str, float, bool]] = []

        norm_target = normalize_string(parsed_query.target_entity or "")
        norm_query = parsed_query.normalized_query

        for gid, game in candidate_pool.items():
            if not cls.passes_filters(game, filters):
                continue

            game_title_norm = normalize_string(game.get("title", ""))
            
            # Reciprocal Rank Score
            r_sem = sem_ranks.get(gid, 200)
            r_lex = lex_ranks.get(gid, 200)
            rrf_score = (1.0 / (RRF_K + r_sem)) + (1.0 / (RRF_K + r_lex))

            # Direct weighted score
            s_sem = sem_scores.get(gid, 0.0)
            s_lex = lex_scores.get(gid, 0.0)

            # Popularity / Review Acclaim signal (log-scaled)
            reviews = game.get("total_reviews", 0)
            pos_pct = game.get("positive_percent", 0.0) / 100.0
            pop_signal = 0.0
            if reviews > 0:
                # Log-scale review count up to 100,000
                log_rev = min(1.0, math.log10(max(1, reviews)) / 5.0)
                pop_signal = log_rev * pos_pct

            # Title exact match check
            has_substantial_reviews = reviews >= 2000
            is_exact_title = (
                (q_type == "ENTITY" and ((norm_target and game_title_norm == norm_target) or (norm_query and game_title_norm == norm_query)))
                or (lex_details_map.get(gid, {}).get("exact_title", False) and has_substantial_reviews)
            )

            # Check if this game is the exact entity for an ENTITY query
            if q_type == "ENTITY" and is_exact_title:
                hybrid_score = 1.0
            else:
                # Weighted combination
                direct_score = (w_sem * s_sem) + (w_lex * s_lex) + (w_pop * pop_signal)
                # Combine normalized RRF with direct score
                norm_rrf = min(1.0, rrf_score * (RRF_K / 2.0))
                hybrid_score = (0.60 * direct_score) + (0.40 * norm_rrf)

                # Bonus for topic tag match on landmark titles
                if q_type == "TOPIC_TAG":
                    norm_q_comp = re.sub(r"[\s-]", "", norm_query)
                    tags_comp = {re.sub(r"[\s-]", "", normalize_string(t)) for t in game.get("tags", [])}
                    genres_comp = {re.sub(r"[\s-]", "", normalize_string(g)) for g in game.get("genres", [])}
                    
                    if norm_q_comp in tags_comp or norm_q_comp in genres_comp:
                        if reviews >= 50000:
                            hybrid_score += 0.25
                        elif reviews >= 10000:
                            hybrid_score += 0.15
                        elif reviews >= 1000:
                            hybrid_score += 0.08
                        else:
                            hybrid_score += 0.04

            scored_candidates.append((gid, hybrid_score, is_exact_title))

        # Sort candidates descending by hybrid score
        scored_candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)

        # 5. Format Results
        results: List[DiscoverySearchResult] = []
        for gid, raw_score, is_exact in scored_candidates:
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
            explanation = cls.generate_explanation(parsed_query, game, evidence)

            display_desc = game.get("display_description") or game.get("description") or game.get("original_description", "")
            desc_lang = game.get("description_language", "en")
            desc_source = game.get("description_source", "steam")

            item = GameDiscoveryItem(
                id=str(game.get("id")),
                external_id=str(game.get("external_id", game.get("id"))),
                source=game.get("source", "steam"),
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
            )

            results.append(
                DiscoverySearchResult(
                    game=item,
                    score=calibrated,
                    match_highlights=evidence,
                    explanation=explanation,
                )
            )

            if len(results) >= limit:
                break

        return results
