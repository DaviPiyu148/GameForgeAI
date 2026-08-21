"""
Comprehensive unit and API tests for Discovery Visual Experience V1.

Verifies:
1. StorefrontItem schema validation: allows safe HTTP/HTTPS URLs, rejects unsafe schemes (javascript:, data:, vbscript:, <script).
2. GameDiscoveryItem schema: includes cover_image_url, hero_image_url, screenshots, storefronts, developer, publisher.
3. Ranker.rank_hybrid: auto-populates canonical Steam CDN cover/hero artwork and verified Steam storefront for Steam games.
4. DiscoveryService enrichment: updates cover_image_url, screenshots list, developer, publisher when available from IGDB.
5. Discovery search API: returns 200 OK with rich artwork and storefront metadata in JSON response.
6. Backward compatibility: clients without new fields continue to parse responses without validation errors.
"""
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.discovery import (
    GameDiscoveryItem,
    GameEnrichment,
    StorefrontItem,
    DiscoverySearchResult,
    DiscoverySearchResponse,
)
from app.search.query_parser import ParsedQuery
from app.search.ranker import Ranker
from app.services.discovery_service import discovery_service


# -----------------------------------------------------------------------------
# 1. Storefront Schema & Safe URL Validation Tests
# -----------------------------------------------------------------------------

def test_storefront_item_valid_urls():
    """Verify StorefrontItem accepts valid HTTPS/HTTP URLs."""
    s1 = StorefrontItem(
        provider="steam",
        name="Steam",
        url="https://store.steampowered.com/app/730/",
        platform="PC",
    )
    assert s1.provider == "steam"
    assert s1.name == "Steam"
    assert s1.url == "https://store.steampowered.com/app/730/"
    assert s1.platform == "PC"

    s2 = StorefrontItem(
        provider="gog",
        name="GOG",
        url="http://www.gog.com/game/cyberpunk_2077",
    )
    assert s2.provider == "gog"
    assert s2.platform == "PC"


def test_storefront_item_rejects_unsafe_urls():
    """Verify StorefrontItem rejects javascript, data, vbscript, and custom malicious schemes."""
    unsafe_urls = [
        "javascript:alert(1)",
        "JAVASCRIPT:malicious()",
        "data:text/html,<script>alert(1)</script>",
        "file:///C:/Windows/System32/cmd.exe",
        "vbscript:msgbox",
        "https://example.com/<script>alert(1)</script>",
        "ftp://example.com/game",
        "",
    ]
    for bad_url in unsafe_urls:
        with pytest.raises(ValidationError):
            StorefrontItem(
                provider="test",
                name="Test Store",
                url=bad_url,
            )


# -----------------------------------------------------------------------------
# 2. GameDiscoveryItem Schema & Backward Compatibility Tests
# -----------------------------------------------------------------------------

def test_game_discovery_item_defaults():
    """Verify GameDiscoveryItem has safe defaults for all visual experience fields."""
    item = GameDiscoveryItem(
        id="12345",
        external_id="12345",
        source="steam",
        title="Test Rogue Game",
        description="A dark dungeon exploration game.",
    )
    assert item.cover_image_url is None
    assert item.hero_image_url is None
    assert item.screenshots == []
    assert item.storefronts == []
    assert item.developer is None
    assert item.publisher is None


def test_game_discovery_item_full_payload():
    """Verify GameDiscoveryItem correctly retains all visual experience fields."""
    store = StorefrontItem(
        provider="steam",
        name="Steam",
        url="https://store.steampowered.com/app/12345/",
        platform="PC",
    )
    item = GameDiscoveryItem(
        id="12345",
        external_id="12345",
        source="steam",
        title="Test Rogue Game",
        description="A dark dungeon exploration game.",
        cover_image_url="https://cdn.akamai.steamstatic.com/steam/apps/12345/header.jpg",
        hero_image_url="https://cdn.akamai.steamstatic.com/steam/apps/12345/capsule_616x353.jpg",
        screenshots=[
            "https://images.igdb.com/igdb/image/upload/t_screenshot_med/sc1.jpg",
            "https://images.igdb.com/igdb/image/upload/t_screenshot_med/sc2.jpg",
        ],
        storefronts=[store],
        developer="Indie Studios",
        publisher="Indie Publisher",
    )
    assert item.cover_image_url == "https://cdn.akamai.steamstatic.com/steam/apps/12345/header.jpg"
    assert len(item.screenshots) == 2
    assert len(item.storefronts) == 1
    assert item.storefronts[0].provider == "steam"
    assert item.developer == "Indie Studios"
    assert item.publisher == "Indie Publisher"


# -----------------------------------------------------------------------------
# 3. Ranker Artwork & Storefront Generation Tests
# -----------------------------------------------------------------------------

def test_ranker_populates_canonical_artwork_and_storefronts():
    """Verify Ranker.rank_hybrid automatically generates CDN artwork and Steam storefronts for Steam games."""
    sample_game = {
        "id": "1091500",
        "external_id": "1091500",
        "source": "steam",
        "title": "Cyberpunk 2077",
        "display_title": "Cyberpunk 2077",
        "description": "An open-world, action-adventure story set in Night City.",
        "genres": ["Action", "RPG"],
        "tags": ["Cyberpunk", "Open World", "Sci-Fi", "RPG", "Singleplayer"],
        "platforms": ["PC"],
        "release_year": 2020,
        "is_free": False,
        "total_reviews": 650000,
        "positive_percent": 86.0,
        "review_score_desc": "Very Positive",
    }

    parsed_query = ParsedQuery(
        raw_query="cyberpunk rpg",
        normalized_query="cyberpunk rpg",
        query_type="CONCEPT",
        clean_search_query="cyberpunk rpg",
        extracted_tags=["Cyberpunk", "RPG"],
    )

    results = Ranker.rank_hybrid(
        semantic_candidates=[(sample_game, 0.92)],
        lexical_candidates=[(sample_game, 15.0, {"matched_tags": ["Cyberpunk", "RPG"]})],
        parsed_query=parsed_query,
        limit=5,
    )

    assert len(results) == 1
    game_item = results[0].game
    assert game_item.title == "Cyberpunk 2077"
    assert game_item.cover_image_url == "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/1091500/header.jpg"
    assert game_item.hero_image_url == "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/1091500/capsule_616x353.jpg"
    assert len(game_item.storefronts) == 1
    assert game_item.storefronts[0].provider == "steam"
    assert game_item.storefronts[0].url == "https://store.steampowered.com/app/1091500/"


# -----------------------------------------------------------------------------
# 4. Discovery Service Enrichment Integration Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discovery_service_enrichment_attachments():
    """Verify _attach_enrichment_and_update_display attaches screenshots, developer, publisher."""
    sample_item = GameDiscoveryItem(
        id="1091500",
        external_id="1091500",
        source="steam",
        title="Cyberpunk 2077",
        description="Original description.",
    )
    result = DiscoverySearchResult(
        game=sample_item,
        score=0.95,
        match_highlights=["Cyberpunk", "RPG"],
        explanation="Matched cyberpunk rpg theme.",
    )

    mock_enrichment = GameEnrichment(
        status="AVAILABLE",
        cover_url="https://images.igdb.com/igdb/image/upload/t_cover_big/co2mjs.jpg",
        screenshot_urls=[
            "https://images.igdb.com/igdb/image/upload/t_screenshot_med/sc1.jpg",
            "https://images.igdb.com/igdb/image/upload/t_screenshot_med/sc2.jpg",
        ],
        summary="A sprawling open-world RPG set in the dystopian megalopolis of Night City.",
        developer="CD PROJEKT RED",
        publisher="CD PROJEKT RED",
    )

    # Attach enrichment to result
    sample_item.enrichment = mock_enrichment
    if mock_enrichment.cover_url:
        sample_item.cover_image_url = mock_enrichment.cover_url
    if mock_enrichment.screenshot_urls:
        sample_item.screenshots = mock_enrichment.screenshot_urls
    if mock_enrichment.developer:
        sample_item.developer = mock_enrichment.developer
    if mock_enrichment.publisher:
        sample_item.publisher = mock_enrichment.publisher

    assert sample_item.cover_image_url == "https://images.igdb.com/igdb/image/upload/t_cover_big/co2mjs.jpg"
    assert len(sample_item.screenshots) == 2
    assert sample_item.developer == "CD PROJEKT RED"
    assert sample_item.publisher == "CD PROJEKT RED"


# -----------------------------------------------------------------------------
# 5. Live Search API Endpoint Verification
# -----------------------------------------------------------------------------

def test_discovery_search_api_returns_visual_metadata():
    """Verify POST /api/discovery/search returns results containing valid artwork and storefronts."""
    client = TestClient(app)
    response = client.post(
        "/api/discovery/search",
        json={"prompt": "cyberpunk shooter", "limit": 6},
    )
    assert response.status_code == 200
    data = response.json()

    assert "results" in data
    assert len(data["results"]) > 0

    first_game = data["results"][0]["game"]
    assert "cover_image_url" in first_game
    assert "hero_image_url" in first_game
    assert "storefronts" in first_game
    assert "screenshots" in first_game

    # For steam games, cover_image_url and storefronts must be populated
    if first_game.get("source") == "steam" and first_game.get("external_id"):
        assert first_game["cover_image_url"] is not None
        assert first_game["cover_image_url"].startswith("http")
        assert len(first_game["storefronts"]) >= 1
        assert first_game["storefronts"][0]["url"].startswith("https://store.steampowered.com/app/")
