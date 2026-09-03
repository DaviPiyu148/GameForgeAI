from typing import Any, Dict, List, Optional
import pytest
from app.search.candidate_pool import DiscoveryCandidatePool, get_candidate_pool_for_mode, MODE_CANDIDATE_POOLS
from app.search.lexical import LexicalIndex
from app.search.index import FAISSIndexManager
from app.schemas.discovery import DiscoverySearchRequest
from app.services.discovery_service import DiscoveryService


def test_candidate_pool_mode_mappings():
    assert get_candidate_pool_for_mode("BEST_MATCH") == DiscoveryCandidatePool.POPULAR_20K
    assert get_candidate_pool_for_mode("popular") == DiscoveryCandidatePool.POPULAR_20K
    assert get_candidate_pool_for_mode("DISCOVER") == DiscoveryCandidatePool.REVIEWED_ONLY
    assert get_candidate_pool_for_mode("discover") == DiscoveryCandidatePool.REVIEWED_ONLY
    assert get_candidate_pool_for_mode("HIDDEN_GEMS") == DiscoveryCandidatePool.REVIEWED_ONLY
    assert get_candidate_pool_for_mode("hidden_gems") == DiscoveryCandidatePool.REVIEWED_ONLY
    assert get_candidate_pool_for_mode(None) == DiscoveryCandidatePool.POPULAR_20K
    assert get_candidate_pool_for_mode("UNKNOWN_MODE") == DiscoveryCandidatePool.POPULAR_20K

def test_lexical_index_candidate_pool_filtering():
    mock_catalog = [
        {"id": "g1", "title": "Epic Deckbuilder", "tags": ["deckbuilder"], "genres": ["Strategy"], "total_reviews": 500},
        {"id": "g2", "title": "Indie Deckbuilder", "tags": ["deckbuilder"], "genres": ["Strategy"], "total_reviews": 15},
        {"id": "g3", "title": "Zero Review Deckbuilder", "tags": ["deckbuilder"], "genres": ["Strategy"], "total_reviews": 0},
    ]
    lex_idx = LexicalIndex(mock_catalog)
    lex_idx._twenty_k_game_ids = {"g1"}
    lex_idx._reviewed_game_ids = {"g1", "g2"}
    res5_20k = lex_idx.search_lexical("deckbuilder", limit=10, candidate_pool=DiscoveryCandidatePool.POPULAR_20K)
    gids20k = [str(g["id"]) for g, _, _ in res5_20k]
    assert "g1" in gids20k and "g2" not in gids20k and "g3" not in gids20k    
    res5_rev = lex_idx.search_lexical("deckbuilder", limit=10, candidate_pool=DiscoveryCandidatePool.REVIEWED_ONLY)
    gids_rev = [str(g["id"]) for g, _, _ in res5_rev]
    assert "g1" in gids_rev and "g2" in gids_rev and "g3" not in gids_rev

    res5_full = lex_idx.search_lexical("deckbuilder", limit=10, candidate_pool=DiscoveryCandidatePool.FULL_CATALOG)
    gids_full = [str(g["id"]) for g, _, _ in res5_full]
    assert "g3" in gids_full


@pytest.mark.asyncio
async def test_multi_pool_discovery_service_invariants():
    service = DiscoveryService()
    req_best = DiscoverySearchRequest(prompt="cyberpunk rpg", limit=5, mode="BEST_MATCH")
    res_best = await service.search(req_best)
    assert len(res_best.results) > 0
    for r in res_best.results:
        assert r.game.total_reviews > 0

    req_hg = DiscoverySearchRequest(prompt="cyberpunk rpg", limit=5, mode="HIDDEN_GEMS")
    res_hg = await service.search(req_hg)
    assert len(res_hg.results) > 0
    for r in res_hg.results:
        assert r.game.total_reviews > 0

    req_disc = DiscoverySearchRequest(prompt="deckbuilder", limit=5, mode="DISCOVER")
    res_disc = await service.search(req_disc)
    assert len(res_disc.results) > 0
    for r in res_disc.results:
        assert r.game.total_reviews > 0


def test_reviewed_only_fallback_when_file_absent(monkeypatch):
    """When reviewed-only FAISS index is absent, index manager falls back to POPULAR_20K gracefully."""
    import os
    mgr = FAISSIndexManager()
    mgr._pool_cache.clear()

    original_exists = os.path.exists

    def mock_exists(path):
        if "reviewed_only" in str(path):
            return False
        return original_exists(path)

    monkeypatch.setattr(os.path, "exists", mock_exists)

    pool_data = mgr._get_or_load_pool(DiscoveryCandidatePool.REVIEWED_ONLY)
    assert pool_data is not None
    assert pool_data["index"].ntotal == 20000
    assert len(pool_data["id_mapping"]) == 20000


@pytest.mark.asyncio
async def test_discover_candidate_pool_isolation_and_experimental_override():
    """Verify DISCOVER default production pool is REVIEWED_ONLY and override uses POPULAR_20K with 0 zero-review titles."""
    service = DiscoveryService()

    # 1. Production default DISCOVER -> REVIEWED_ONLY
    req_prod = DiscoverySearchRequest(prompt="cozy automation with trains", limit=5, mode="DISCOVER")
    res_prod = await service.search(req_prod)
    assert len(res_prod.results) > 0
    for r in res_prod.results:
        assert r.game.total_reviews > 0

    # 2. Candidate pool override DISCOVER -> POPULAR_20K
    res_override = await service.search(req_prod, candidate_pool_override=DiscoveryCandidatePool.POPULAR_20K)
    assert len(res_override.results) > 0
    for r in res_override.results:
        assert r.game.total_reviews > 0


@pytest.mark.asyncio
async def test_single_channel_rrf_damping_invariants():
    """Verify single-channel RRF damping discounts lexical-only candidates while preserving dual-channel and dense-only."""
    service = DiscoveryService()
    req = DiscoverySearchRequest(prompt="cyberpunk detective game without heavy combat", limit=10, mode="DISCOVER")

    # Run without damping (damping=0.0)
    res_undamped = await service.search(
        req,
        candidate_pool_override=DiscoveryCandidatePool.REVIEWED_ONLY,
        single_channel_damping=0.0,
    )
    # Run with 50% single-channel damping (damping=0.5)
    res_damped = await service.search(
        req,
        candidate_pool_override=DiscoveryCandidatePool.REVIEWED_ONLY,
        single_channel_damping=0.5,
    )

    assert len(res_undamped.results) > 0
    assert len(res_damped.results) > 0

    # Verify that all results have > 0 reviews (Zero-Review Invariant)
    for r in res_damped.results:
        assert r.game.total_reviews > 0


def test_discover_low_review_confidence_floor_boundaries_and_isolation():
    """Verify exact boundary behavior and mode isolation for the low-review confidence floor."""
    from app.search.query_parser import ParsedQuery
    from app.search.ranker import Ranker

    parsed_q = ParsedQuery(
        raw_query="test query",
        normalized_query="test query",
        clean_search_query="test query",
        query_type="CONCEPT",
    )

    def make_game(gid: str, title: str, reviews: int, pos_pct: float) -> Dict[str, Any]:
        return {
            "id": gid,
            "title": title,
            "display_title": title,
            "total_reviews": reviews,
            "positive_percent": pos_pct,
            "genres": ["Action"],
            "tags": ["Action", "Adventure"],
            "description": "Test description",
        }

    # Test each boundary cleanly with 5 filler games
    # Fillers: 5000 reviews, 90% positive, base score 0.50
    fillers = [(make_game(f"filler_{i}", f"Filler {i}", 5000, 90.0), 0.50) for i in range(1, 6)]

    # 1. Test 75.0% boundary:
    # A) 99 reviews, 74.9% -> should be deferred to rank 6 behind 5 fillers
    g_749 = (make_game("test_749", "Test 74.9%", 99, 74.9), 0.99)
    res_749 = Ranker.rank_hybrid(
        semantic_candidates=[g_749] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=75.0,
    )
    assert res_749[0].game.id != "test_749", "99 revs @ 74.9% must not occupy Top-5 at 75% floor"
    assert res_749[5].game.id == "test_749", "99 revs @ 74.9% must be deferred to rank 6"

    # B) 99 reviews, 75.0% -> should be eligible for Top-5 (Rank 1)
    g_750 = (make_game("test_750", "Test 75.0%", 99, 75.0), 0.99)
    res_750 = Ranker.rank_hybrid(
        semantic_candidates=[g_750] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=75.0,
    )
    assert res_750[0].game.id == "test_750", "99 revs @ 75.0% must occupy Rank 1 (eligible)"

    # C) 100 reviews, 74.9% -> exempt from floor, eligible for Top-5 (Rank 1)
    g_100_749 = (make_game("test_100_749", "Test 100 74.9%", 100, 74.9), 0.99)
    res_100_749 = Ranker.rank_hybrid(
        semantic_candidates=[g_100_749] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=75.0,
    )
    assert res_100_749[0].game.id == "test_100_749", "100 revs @ 74.9% must be exempt from floor (Rank 1)"

    # 2. Test 80.0% boundary:
    # A) 99 reviews, 79.9% -> deferred to rank 6 at 80% floor
    g_799 = (make_game("test_799", "Test 79.9%", 99, 79.9), 0.99)
    res_799 = Ranker.rank_hybrid(
        semantic_candidates=[g_799] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=80.0,
    )
    assert res_799[0].game.id != "test_799", "99 revs @ 79.9% must not occupy Top-5 at 80% floor"
    assert res_799[5].game.id == "test_799", "99 revs @ 79.9% must be deferred to rank 6"

    # B) 99 reviews, 80.0% -> eligible for Rank 1
    g_800 = (make_game("test_800", "Test 80.0%", 99, 80.0), 0.99)
    res_800 = Ranker.rank_hybrid(
        semantic_candidates=[g_800] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=80.0,
    )
    assert res_800[0].game.id == "test_800", "99 revs @ 80.0% must occupy Rank 1 (eligible)"

    # C) 100 reviews, 79.9% -> exempt from floor (Rank 1)
    g_100_799 = (make_game("test_100_799", "Test 100 79.9%", 100, 79.9), 0.99)
    res_100_799 = Ranker.rank_hybrid(
        semantic_candidates=[g_100_799] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=80.0,
    )
    assert res_100_799[0].game.id == "test_100_799", "100 revs @ 79.9% must be exempt from floor (Rank 1)"

    # 3. Test 85.0% boundary:
    # A) 99 reviews, 84.9% -> deferred to rank 6 at 85% floor
    g_849 = (make_game("test_849", "Test 84.9%", 99, 84.9), 0.99)
    res_849 = Ranker.rank_hybrid(
        semantic_candidates=[g_849] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=85.0,
    )
    assert res_849[0].game.id != "test_849", "99 revs @ 84.9% must not occupy Top-5 at 85% floor"
    assert res_849[5].game.id == "test_849", "99 revs @ 84.9% must be deferred to rank 6"

    # B) 99 reviews, 85.0% -> eligible for Rank 1
    g_850 = (make_game("test_850", "Test 85.0%", 99, 85.0), 0.99)
    res_850 = Ranker.rank_hybrid(
        semantic_candidates=[g_850] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=85.0,
    )
    assert res_850[0].game.id == "test_850", "99 revs @ 85.0% must occupy Rank 1 (eligible)"

    # C) 100 reviews, 84.9% -> exempt from floor (Rank 1)
    g_100_849 = (make_game("test_100_849", "Test 100 84.9%", 100, 84.9), 0.99)
    res_100_849 = Ranker.rank_hybrid(
        semantic_candidates=[g_100_849] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=85.0,
    )
    assert res_100_849[0].game.id == "test_100_849", "100 revs @ 84.9% must be exempt from floor (Rank 1)"

    # 4. Mode isolation: In BEST_MATCH, low_review_confidence_floor must NOT apply
    res_bm = Ranker.rank_hybrid(
        semantic_candidates=[g_749] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="BEST_MATCH",
        low_review_confidence_floor=85.0,
    )
    assert res_bm[0].game.id == "test_749", "BEST_MATCH must not be affected by DISCOVER floor"

    # 5. Direct ranker call with floor=None: ranking is completely unconstrained
    res_none = Ranker.rank_hybrid(
        semantic_candidates=[g_749] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=None,
    )
    assert res_none[0].game.id == "test_749", "Direct ranker call with floor=None must preserve original ranking"


def test_discover_floor_override_semantics():
    """Verify explicit override semantics (floor=None -> 80, floor=0.0 -> 0.0, floor=75 -> 75, non-DISCOVER -> None)."""
    from app.search.query_parser import ParsedQuery
    from app.search.ranker import Ranker

    parsed_q = ParsedQuery(
        raw_query="test query",
        normalized_query="test query",
        clean_search_query="test query",
        query_type="CONCEPT",
    )

    def make_game(gid: str, title: str, reviews: int, pos_pct: float) -> Dict[str, Any]:
        return {
            "id": gid,
            "title": title,
            "display_title": title,
            "total_reviews": reviews,
            "positive_percent": pos_pct,
            "genres": ["Action"],
            "tags": ["Action"],
        }

    fillers = [(make_game(f"filler_{i}", f"Filler {i}", 5000, 90.0), 0.50) for i in range(1, 6)]
    g_low = (make_game("test_low", "Low Review Weak", 99, 74.9), 0.99)

    # 1. floor = 80.0 (DISCOVER default in service) -> blocks test_low from Top-5
    res_80 = Ranker.rank_hybrid(
        semantic_candidates=[g_low] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=80.0,
    )
    assert res_80[0].game.id != "test_low"
    assert res_80[5].game.id == "test_low"

    # 2. floor = 0.0 (explicit override) -> MUST NOT clobber to 80.0; test_low must be admitted to Rank 1
    res_zero = Ranker.rank_hybrid(
        semantic_candidates=[g_low] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=0.0,
    )
    assert res_zero[0].game.id == "test_low", "Explicit floor=0.0 must be preserved and admit test_low to Rank 1"

    # 3. floor = 75.0 (explicit override) -> 74.9% is blocked
    res_75 = Ranker.rank_hybrid(
        semantic_candidates=[g_low] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="DISCOVER",
        low_review_confidence_floor=75.0,
    )
    assert res_75[0].game.id != "test_low"
    assert res_75[5].game.id == "test_low"

    # 4. Mode isolation: BEST_MATCH with floor=None has no floor
    res_bm = Ranker.rank_hybrid(
        semantic_candidates=[g_low] + fillers,
        lexical_candidates=[],
        parsed_query=parsed_q,
        limit=6,
        min_threshold=0.0,
        mode="BEST_MATCH",
        low_review_confidence_floor=None,
    )
    assert res_bm[0].game.id == "test_low"
