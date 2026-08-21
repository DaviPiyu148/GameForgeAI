import logging
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.discovery import (
    BuildInspirationResponse,
    DiscoverySearchRequest,
    DiscoverySearchResponse,
    DiscoverySearchResult,
    MoreLikeThisRequest,
)
from app.search.catalog import CatalogManager
from app.search.embedder import QueryEmbedder
from app.search.index import FAISSIndexManager
from app.search.lexical import LexicalIndex, normalize_string
from app.search.query_parser import ParsedQuery, QueryParser
from app.search.ranker import MIN_MATCH_SCORE_THRESHOLD, STRONG_MATCH_THRESHOLD, Ranker
from app.services.igdb_service import IGDBEnrichmentService


logger = logging.getLogger(__name__)


class DiscoveryService:
    """
    Discovery 2.0 Engine orchestrating Query Understanding, Hybrid Retrieval
    (Lexical + Semantic FAISS), Reciprocal Rank Fusion, Calibrated Relevance Scoring,
    Recommendation Pivots, and IGDB Metadata Enrichment.
    """

    def __init__(
        self,
        embedder: Optional[QueryEmbedder] = None,
        index_manager: Optional[FAISSIndexManager] = None,
        catalog_manager: Optional[CatalogManager] = None,
        igdb_service: Optional[IGDBEnrichmentService] = None,
    ):
        self._embedder = embedder
        self._index_manager = index_manager
        self._catalog_manager = catalog_manager
        self._igdb_service = igdb_service
        self._lexical_index: Optional[LexicalIndex] = None
        self._query_parser: Optional[QueryParser] = None

    @property
    def embedder(self) -> QueryEmbedder:
        if self._embedder is None:
            self._embedder = QueryEmbedder.get_instance()
        return self._embedder

    @property
    def index_manager(self) -> FAISSIndexManager:
        if self._index_manager is None:
            self._index_manager = FAISSIndexManager.get_instance()
        return self._index_manager

    @property
    def catalog_manager(self) -> CatalogManager:
        if self._catalog_manager is None:
            self._catalog_manager = CatalogManager.get_instance()
        return self._catalog_manager

    @property
    def lexical_index(self) -> Optional[LexicalIndex]:
        if self._lexical_index is None:
            self._lexical_index = self.catalog_manager.get_lexical_index()
        return self._lexical_index

    @property
    def query_parser(self) -> QueryParser:
        if self._query_parser is None:
            self._query_parser = QueryParser(lexical_index=self.lexical_index)
        return self._query_parser

    @property
    def igdb_service(self) -> IGDBEnrichmentService:
        if self._igdb_service is None:
            self._igdb_service = IGDBEnrichmentService.get_instance()
        return self._igdb_service

    async def search(self, request: DiscoverySearchRequest) -> DiscoverySearchResponse:
        """
        Execute deterministic hybrid discovery search combining lexical full-catalog matching
        and dense FAISS semantic similarity with calibrated evidence-based ranking.
        """
        raw_prompt = request.prompt.strip()
        if not raw_prompt:
            return DiscoverySearchResponse(
                query=request.prompt,
                match_count=0,
                no_strong_match=True,
                query_type="CONCEPT",
                target_entity=None,
                results=[],
            )

        top_k = max(request.limit * 5, 50)
        semantic_candidates: List[Tuple[Dict[str, Any], float]] = []

        # 1. Deterministic Query Understanding
        parsed_query = self.query_parser.parse(raw_prompt)
        logger.info("Parsed query '%s' as %s (target=%s)", raw_prompt, parsed_query.query_type, parsed_query.target_entity)

        # 2. Semantic Retrieval via SentenceTransformer + FAISS (if index ready)
        if self.index_manager.is_ready():
            try:
                # For SIMILARITY queries, if a target game was identified, embed its rich semantic profile
                if parsed_query.query_type == "SIMILARITY" and parsed_query.target_game:
                    embed_text = parsed_query.target_game.get("semantic_profile") or parsed_query.target_game.get("title")
                else:
                    embed_text = parsed_query.clean_search_query or raw_prompt

                query_vec = self.embedder.embed_query(embed_text)
                raw_sem_matches: List[Tuple[str, float]] = self.index_manager.search(query_vec, top_k=top_k)

                for gid, score in raw_sem_matches:
                    game = self.catalog_manager.get_game(gid)
                    if game is not None:
                        semantic_candidates.append((game, score))
            except Exception as e:
                logger.warning(f"DiscoveryService: Semantic search failed, falling back to lexical: {e}")
        else:
            logger.warning("DiscoveryService: FAISS index is not initialized or index file missing; using lexical fallback.")
            if not self.lexical_index:
                raise RuntimeError("Discovery vector index and lexical catalog are both unavailable.")

        # 3. Lexical Retrieval over Full Catalog (121k+ records)
        lexical_candidates: List[Tuple[Dict[str, Any], float, Dict[str, Any]]] = []
        if self.lexical_index:
            lexical_candidates = self.lexical_index.search_lexical(
                query=parsed_query.clean_search_query or raw_prompt,
                limit=top_k,
                query_type=parsed_query.query_type,
            )

        # 4. Candidate Fusion & Hybrid Ranking
        results: List[DiscoverySearchResult] = Ranker.rank_hybrid(
            semantic_candidates=semantic_candidates,
            lexical_candidates=lexical_candidates,
            parsed_query=parsed_query,
            filters=request.filters,
            limit=request.limit,
            min_threshold=MIN_MATCH_SCORE_THRESHOLD,
        )

        # 5. Enrich Top Results with IGDB Media & Summaries (Non-blocking / cached)
        await self._attach_enrichment_and_update_display(results)

        no_strong_match = len(results) == 0 or (len(results) > 0 and results[0].score < STRONG_MATCH_THRESHOLD)

        return DiscoverySearchResponse(
            query=request.prompt,
            match_count=len(results),
            no_strong_match=no_strong_match,
            query_type=parsed_query.query_type,
            target_entity=parsed_query.target_entity,
            results=results,
        )

    async def get_similar_games(self, steam_app_id: str, limit: int = 12) -> DiscoverySearchResponse:
        """
        Find games similar to a given canonical game by Steam App ID using its semantic profile and metadata.
        """
        seed_game = self.catalog_manager.get_game(steam_app_id)
        if not seed_game:
            raise KeyError(f"Game with Steam App ID '{steam_app_id}' not found in catalog.")

        title = seed_game.get("title", "")
        semantic_profile = seed_game.get("semantic_profile") or title

        # Build parsed SIMILARITY query
        parsed_query = ParsedQuery(
            raw_query=f"games like {title}",
            normalized_query=normalize_string(f"games like {title}"),
            query_type="SIMILARITY",
            clean_search_query=title,
            target_entity=title,
            target_game=seed_game,
            extracted_tags=seed_game.get("tags", [])[:5],
            extracted_genres=seed_game.get("genres", [])[:3],
            extracted_player_modes=seed_game.get("player_modes", []),
        )

        top_k = max(limit * 5, 50)
        semantic_candidates: List[Tuple[Dict[str, Any], float]] = []

        # Semantic retrieval with seed profile (if index ready)
        if self.index_manager.is_ready():
            try:
                query_vec = self.embedder.embed_query(semantic_profile)
                raw_sem = self.index_manager.search(query_vec, top_k=top_k)

                for gid, score in raw_sem:
                    if str(gid) != str(seed_game.get("id")):  # Exclude seed game from similarity results
                        game = self.catalog_manager.get_game(gid)
                        if game:
                            semantic_candidates.append((game, score))
            except Exception as e:
                logger.warning(f"DiscoveryService: Semantic search failed for similar games, using lexical fallback: {e}")

        # Lexical search using seed tags and genres
        lexical_query = f"{title} {' '.join(seed_game.get('genres', []))} {' '.join(seed_game.get('tags', [])[:3])}"
        lexical_candidates: List[Tuple[Dict[str, Any], float, Dict[str, Any]]] = []
        if self.lexical_index:
            raw_lex = self.lexical_index.search_lexical(query=lexical_query, limit=top_k, query_type="SIMILARITY")
            for g, s, d in raw_lex:
                if str(g.get("id")) != str(seed_game.get("id")):
                    lexical_candidates.append((g, s, d))

        results = Ranker.rank_hybrid(
            semantic_candidates=semantic_candidates,
            lexical_candidates=lexical_candidates,
            parsed_query=parsed_query,
            limit=limit,
            min_threshold=MIN_MATCH_SCORE_THRESHOLD,
        )

        # Enrich top results with IGDB media & summaries
        await self._attach_enrichment_and_update_display(results)

        return DiscoverySearchResponse(
            query=f"Similar to {title}",
            match_count=len(results),
            no_strong_match=len(results) == 0,
            query_type="SIMILARITY",
            target_entity=title,
            results=results,
        )

    async def more_like_this(self, request: MoreLikeThisRequest) -> DiscoverySearchResponse:
        """
        Find related games given multiple canonical game IDs.
        """
        seed_games: List[Dict[str, Any]] = []
        seed_ids = set()
        for gid in request.get_ids():
            g = self.catalog_manager.get_game(gid)
            if g:
                seed_games.append(g)
                seed_ids.add(str(g.get("id")))

        if not seed_games:
            raise KeyError("None of the requested game IDs were found in the catalog.")

        combined_titles = ", ".join([g.get("title", "") for g in seed_games])
        combined_profiles = " ".join([g.get("semantic_profile", "") for g in seed_games])

        parsed_query = ParsedQuery(
            raw_query=f"More like {combined_titles}",
            normalized_query=normalize_string(combined_titles),
            query_type="SIMILARITY",
            clean_search_query=combined_titles,
            target_entity=combined_titles,
            target_game=seed_games[0],
        )

        top_k = max(request.limit * 5, 50)
        semantic_candidates: List[Tuple[Dict[str, Any], float]] = []

        if self.index_manager.is_ready():
            try:
                query_vec = self.embedder.embed_query(combined_profiles[:1000])
                raw_sem = self.index_manager.search(query_vec, top_k=top_k)

                semantic_candidates = [
                    (self.catalog_manager.get_game(gid), score)
                    for gid, score in raw_sem
                    if str(gid) not in seed_ids and self.catalog_manager.get_game(gid) is not None
                ]
            except Exception as e:
                logger.warning(f"DiscoveryService: Semantic search failed for more_like_this, using lexical fallback: {e}")

        lexical_candidates: List[Tuple[Dict[str, Any], float, Dict[str, Any]]] = []
        if self.lexical_index:
            raw_lex = self.lexical_index.search_lexical(query=combined_titles, limit=top_k, query_type="SIMILARITY")
            for g, s, d in raw_lex:
                if str(g.get("id")) not in seed_ids:
                    lexical_candidates.append((g, s, d))

        results = Ranker.rank_hybrid(
            semantic_candidates=semantic_candidates,
            lexical_candidates=lexical_candidates,
            parsed_query=parsed_query,
            filters=request.filters,
            limit=request.limit,
            min_threshold=MIN_MATCH_SCORE_THRESHOLD,
        )

        # Enrich top results with IGDB media & summaries
        await self._attach_enrichment_and_update_display(results)

        return DiscoverySearchResponse(
            query=f"More like {combined_titles}",
            match_count=len(results),
            no_strong_match=len(results) == 0,
            query_type="SIMILARITY",
            target_entity=combined_titles,
            results=results,
        )

    async def _attach_enrichment_and_update_display(self, results: List[DiscoverySearchResult]) -> None:
        """
        Enriches top search results with IGDB media and uses IGDB English summary
        as display_description when available.
        """
        if not results:
            return
        try:
            games_to_enrich = [
                {"id": r.game.id, "external_id": r.game.external_id, "title": r.game.title, "release_year": r.game.release_year}
                for r in results
            ]
            enrichment_map = await self.igdb_service.enrich_results(games_to_enrich)
            for r in results:
                gid = r.game.external_id or r.game.id
                if gid in enrichment_map:
                    enrichment = enrichment_map[gid]
                    r.game.enrichment = enrichment
                    if enrichment.cover_url and (enrichment.cover_url.startswith("http://") or enrichment.cover_url.startswith("https://")):
                        r.game.cover_image_url = enrichment.cover_url
                    if enrichment.screenshot_urls:
                        r.game.screenshots = [
                            s for s in enrichment.screenshot_urls
                            if s and (s.startswith("http://") or s.startswith("https://"))
                        ]
                    if enrichment.developer:
                        r.game.developer = enrichment.developer
                    if enrichment.publisher:
                        r.game.publisher = enrichment.publisher
                    if enrichment.summary and len(enrichment.summary.strip()) >= 15:
                        r.game.display_description = enrichment.summary.strip()
                        r.game.description = enrichment.summary.strip()
                        r.game.description_source = "igdb"
                        r.game.description_language = "en"
        except Exception as e:
            logger.warning(f"Discovery enrichment non-fatal warning: {e}")

    def get_build_inspiration(self, steam_app_id: str) -> BuildInspirationResponse:
        """
        Extract structured design metadata (inferred 2D archetype, theme, parameter recommendations)
        from a canonical game to prepopulate the /build compiler pipeline.
        """
        game = self.catalog_manager.get_game(steam_app_id)
        if not game:
            for g in self.catalog_manager.get_all_games():
                if str(g.get("external_id")) == str(steam_app_id) or str(g.get("id")) == str(steam_app_id):
                    game = g
                    break

        if not game:
            raise KeyError(f"Game with ID '{steam_app_id}' not found in catalog.")

        title = game.get("title", "")
        tags_lower = {t.lower() for t in game.get("tags", [])}
        genres_lower = {g.lower() for g in game.get("genres", [])}

        # 1. Infer Archetype
        if any(t in tags_lower for t in ["survival", "open world survival craft", "crafting", "colony sim", "farming sim", "farming"]):
            archetype = "survival"
        elif any(t in tags_lower for t in ["shooter", "bullet hell", "top-down shooter", "fps", "shmup", "action roguelike"]):
            archetype = "shooter"
        elif any(t in tags_lower for t in ["platformer", "2d platformer", "metroidvania", "precision platformer"]):
            archetype = "platformer"
        else:
            archetype = "collector"

        # 2. Infer Theme
        if any(t in tags_lower for t in ["cyberpunk", "sci-fi", "space", "futuristic", "robots"]):
            theme = "Cyberpunk / Sci-Fi"
        elif any(t in tags_lower for t in ["cozy", "relaxing", "cute", "casual", "nature", "farming"]):
            theme = "Cozy Pastoral"
        elif any(t in tags_lower for t in ["dark fantasy", "soulslike", "horror", "gothic", "grimdark"]):
            theme = "Dark Fantasy"
        elif any(t in tags_lower for t in ["dungeon crawler", "fantasy", "magic", "medieval"]):
            theme = "High Fantasy"
        else:
            theme = "Retro Arcade"

        # 3. Recommended Parameters
        art_density = 75 if "pixel graphics" in tags_lower or "retro" in tags_lower else 50
        physics = 70 if archetype in ("platformer", "shooter") else 40

        modules = ["InventorySystem"]
        if archetype == "survival":
            modules.extend(["HealthBar", "CraftingBench", "DayNightCycle"])
        elif archetype == "shooter":
            modules.extend(["HealthBar", "WeaponUpgrade", "ScoreTracker"])
        elif archetype == "platformer":
            modules.extend(["DoubleJump", "Checkpoints", "ScoreTracker"])
        else:
            modules.extend(["ScoreTracker", "ItemMagnet"])

        recommended_prompt = (
            f"A 2D {theme.lower()} {archetype} prototype inspired by {title}. "
            f"Featuring {', '.join(game.get('tags', [])[:3])} mechanics, responsive controls, and arcade challenge."
        )

        return BuildInspirationResponse(
            source_game_id=str(game.get("id")),
            title=title,
            inferred_archetype=archetype,
            inferred_theme=theme,
            recommended_prompt=recommended_prompt,
            suggested_art_density=art_density,
            suggested_physics=physics,
            suggested_modules=list(dict.fromkeys(modules)),
            tags=game.get("tags", []),
            genres=game.get("genres", []),
            player_modes=game.get("player_modes", []),
        )

    def get_game_by_steam_id(self, steam_app_id: str) -> Optional[Dict[str, Any]]:
        """Look up single game by steam app id."""
        try:
            return self.catalog_manager.get_game(steam_app_id)
        except Exception:
            return None


discovery_service = DiscoveryService()
