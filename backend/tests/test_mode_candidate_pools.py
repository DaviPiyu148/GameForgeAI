import pytest
from app.search.candidate_pool import DiscoveryCandidatePool, get_candidate_pool_for_mode, MODE_CANDIDATE_POOLS
from app.search.lexical import LexicalIndex
from app.search.index import FAISSIndexManager
from app.schemas.discovery import DiscoverySearchRequest
from app.services.discovery_service import DiscoveryService


def test_candidate_pool_mode_mappings():
    assert get_candidate_pool_for_mode("BEST_MATCH") == DiscoveryCandidatePool.POPULAR_20K
    assert get_candidate_pool_for_mode("popular") == DiscoveryCandidatePool.POPULAR_20K
    assert get_candidate_pool_for_mode("HIDDEN_GEMS") == DiscoveryCandidatePool.REVIEWED_ONLY
    assert get_candidate_pool_for_mode("discover") == DiscoveryCandidatePool.REVIEWED_ONLY
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
