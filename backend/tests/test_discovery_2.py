import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.search.lexical import LexicalIndex, normalize_genres, normalize_string, tokenize
from app.search.query_parser import QueryParser
from app.search.ranker import Ranker, ParsedQuery
from app.services.igdb_service import IGDBEnrichmentService, GameEnrichment
from app.schemas.discovery import DiscoverySearchRequest, MoreLikeThisRequest


@pytest.fixture(scope="module")
def mock_catalog():
    return [
        {
            "id": 413150,
            "external_id": "413150",
            "source": "steam",
            "title": "Stardew Valley",
            "description": "You've inherited your grandfather's old farm plot in Stardew Valley. Armed with hand-me-down tools and a few coins, you set out to begin your new life.",
            "genres": ["Инди", "Ролевые игры", "Симуляторы"],
            "tags": ["Farming Sim", "Cozy", "Pixel Graphics", "Agriculture", "2D"],
            "player_modes": ["Single-player", "Co-op", "Multi-player"],
            "platforms": ["PC", "Mac", "Linux"],
            "release_year": 2016,
            "is_free": False,
            "total_reviews": 769000,
            "positive_percent": 98.0,
            "review_score_desc": "Overwhelmingly Positive",
        },
        {
            "id": 1091500,
            "external_id": "1091500",
            "source": "steam",
            "title": "Cyberpunk 2077",
            "description": "Cyberpunk 2077 is an open-world, action-adventure RPG set in the megalopolis of Night City.",
            "genres": ["Action", "RPG"],
            "tags": ["Cyberpunk", "Open World", "Sci-Fi", "Action RPG", "Atmospheric"],
            "player_modes": ["Single-player"],
            "platforms": ["PC"],
            "release_year": 2020,
            "is_free": False,
            "total_reviews": 769000,
            "positive_percent": 84.0,
            "review_score_desc": "Very Positive",
        },
        {
            "id": 374320,
            "external_id": "374320",
            "source": "steam",
            "title": "DARK SOULS™ III",
            "description": "Dark Souls continues to push the boundaries with the latest, ambitious chapter in the critically-acclaimed and genre-defining series.",
            "genres": ["Action", "RPG"],
            "tags": ["Souls-like", "Dark Fantasy", "Difficult", "Action RPG"],
            "player_modes": ["Single-player", "Co-op", "PvP"],
            "platforms": ["PC"],
            "release_year": 2016,
            "is_free": False,
            "total_reviews": 395000,
            "positive_percent": 94.0,
            "review_score_desc": "Very Positive",
        },
    ]


# =========================================================================
# 1. LEXICAL INDEX TESTS
# =========================================================================

def test_genre_normalization():
    cyrillic_genres = ["Инди", "Ролевые игры", "Симуляторы", "Бесплатные"]
    canonical = normalize_genres(cyrillic_genres)
    assert "Indie" in canonical
    assert "RPG" in canonical
    assert "Simulation" in canonical
    assert "Free to Play" in canonical


def test_lexical_index_initialization(mock_catalog):
    idx = LexicalIndex(mock_catalog)
    # Check alias resolution
    stardew = idx.resolve_entity("stardew")
    assert stardew is not None
    assert stardew["title"] == "Stardew Valley"

    # Check exact title match
    cp = idx.resolve_entity("cyberpunk 2077")
    assert cp is not None
    assert cp["id"] == 1091500

    # Check safe alias for Witcher 3 (fallback check)
    assert "stardew" in idx.resolve_entity("stardew")["title"].lower()


def test_compound_tag_lexical_search(mock_catalog):
    idx = LexicalIndex(mock_catalog)
    # Search for "soulslike" should match "Souls-like" tag in DARK SOULS III
    results = idx.search_lexical("soulslike", limit=5, query_type="TOPIC_TAG")
    assert len(results) > 0
    top_game, score, details = results[0]
    assert top_game["title"] == "DARK SOULS™ III"
    assert "Souls-like" in details.get("matched_tags", [])


# =========================================================================
# 2. QUERY PARSER TESTS
# =========================================================================

def test_query_parser_classification(mock_catalog):
    idx = LexicalIndex(mock_catalog)
    parser = QueryParser(idx)

    # 1. ENTITY
    res_entity = parser.parse("Cyberpunk 2077")
    assert res_entity.query_type == "ENTITY"
    assert res_entity.target_entity == "Cyberpunk 2077"

    # 2. SIMILARITY
    res_sim = parser.parse("games like Stardew Valley")
    assert res_sim.query_type == "SIMILARITY"
    assert res_sim.target_entity == "Stardew Valley"

    # 3. TOPIC_TAG
    res_tag = parser.parse("soulslike")
    assert res_tag.query_type == "TOPIC_TAG"

    # 4. MIXED
    res_mixed = parser.parse("co-op roguelike")
    assert res_mixed.query_type == "MIXED"
    assert "Co-op" in res_mixed.extracted_player_modes

    # 5. CONCEPT
    res_concept = parser.parse("whimsical pastel farming adventure in space")
    assert res_concept.query_type == "CONCEPT"


# =========================================================================
# 3. RANKER & CALIBRATION TESTS
# =========================================================================

def test_score_calibration():
    # Exact entity match
    assert Ranker.calibrate_score(1.0, "ENTITY", is_exact_entity=True) == 0.98

    # Strong match band
    strong = Ranker.calibrate_score(0.80, "CONCEPT")
    assert strong >= 0.85

    # Good match band
    good = Ranker.calibrate_score(0.60, "CONCEPT")
    assert 0.70 <= good <= 0.84

    # Possible match band
    possible = Ranker.calibrate_score(0.40, "CONCEPT")
    assert 0.50 <= possible <= 0.69


def test_evidence_extraction():
    parsed = ParsedQuery(
        raw_query="co-op cyberpunk RPG",
        clean_search_query="cyberpunk RPG",
        normalized_query="co-op cyberpunk rpg",
        query_type="MIXED",
        target_entity=None,
        target_game=None,
        extracted_genres=["RPG"],
        extracted_tags=["Cyberpunk"],
        extracted_player_modes=["Co-op"],
    )
    game = {
        "title": "Cyberpunk 2077",
        "genres": ["Action", "RPG"],
        "tags": ["Cyberpunk", "Open World"],
        "player_modes": ["Single-player"],
        "total_reviews": 769000,
        "positive_percent": 84.0,
        "review_score_desc": "Very Positive",
    }
    evidence = Ranker.extract_evidence(parsed, game)
    assert any("Cyberpunk" in e for e in evidence)
    assert any("RPG" in e for e in evidence)
    assert any("Steam" in e for e in evidence)


# =========================================================================
# 4. IGDB SERVICE FALLBACK & CACHING TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_igdb_graceful_fallback():
    service = IGDBEnrichmentService(db_path=":memory:")
    service.client_id = None
    service.client_secret = None
    assert not service.is_configured()

    # Enriching a batch should return UNAVAILABLE without error
    games = [{"id": "413150", "title": "Stardew Valley"}]
    enrichments = await service.enrich_results(games)
    assert "413150" in enrichments
    assert enrichments["413150"].status == "UNAVAILABLE"


# =========================================================================
# 5. INTEGRATION ENDPOINT TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_discovery_search_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/discovery/search", json={"prompt": "cyberpunk", "limit": 5})
        assert res.status_code == 200
        data = res.json()
        assert "results" in data
        assert len(data["results"]) > 0
        assert data["query_type"] == "TOPIC_TAG"
        # Check top result
        top = data["results"][0]
        assert top["game"]["title"] == "Cyberpunk 2077"
        assert top["score"] >= 0.85
        assert len(top["match_highlights"]) > 0


@pytest.mark.asyncio
async def test_discovery_similar_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Steam app id 413150 = Stardew Valley
        res = await ac.get("/api/discovery/similar/413150?limit=5")
        assert res.status_code == 200
        data = res.json()
        assert data["query_type"] == "SIMILARITY"
        assert data["target_entity"] == "Stardew Valley"
        assert len(data["results"]) > 0


@pytest.mark.asyncio
async def test_discovery_more_like_this_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/discovery/more-like-this", json={"seed_game_ids": ["413150"], "limit": 5})
        assert res.status_code == 200
        data = res.json()
        assert data["query_type"] == "SIMILARITY"
        assert len(data["results"]) > 0


@pytest.mark.asyncio
async def test_discovery_build_inspiration_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/discovery/build-inspiration/413150")
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == "Stardew Valley"
        assert "inferred_archetype" in data
        assert "suggested_modules" in data
        assert len(data["suggested_modules"]) > 0
        assert "recommended_prompt" in data
        assert "Stardew Valley" in data["recommended_prompt"]
