import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.discovery import get_discovery_service
from app.schemas.discovery import (
    DiscoverySearchRequest,
    DiscoverySearchResponse,
    DiscoverySearchResult,
    GameDiscoveryItem,
)
from app.services.discovery_service import DiscoveryService


@pytest.fixture
def mock_discovery_service():
    class MockService:
        async def search(self, request: DiscoverySearchRequest, **kwargs) -> DiscoverySearchResponse:
            if "nomatch" in request.prompt.lower() or "xyz" in request.prompt.lower():
                return DiscoverySearchResponse(
                    query=request.prompt,
                    match_count=0,
                    no_strong_match=True,
                    results=[],
                )

            item = GameDiscoveryItem(
                id="105600",
                external_id="105600",
                source="steam",
                title="Terraria",
                description="Dig, fight, explore, build!",
                genres=["Action", "Adventure", "RPG"],
                tags=["Sandbox", "Survival", "2D", "Crafting"],
                player_modes=["Single-player", "Multi-player", "Co-op"],
                platforms=["PC"],
                release_year=2011,
                is_free=False,
                total_reviews=50000,
                positive_percent=98.0,
                review_score_desc="Overwhelmingly Positive",
            )
            res = DiscoverySearchResult(
                game=item,
                score=0.88,
                match_highlights=["Sandbox", "Survival", "2D"],
                explanation="Matches your search with Sandbox, Survival across Action, Adventure.",
            )
            return DiscoverySearchResponse(
                query=request.prompt,
                match_count=1,
                no_strong_match=False,
                results=[res],
            )

    return MockService()


def test_discovery_search_success(mock_discovery_service):
    app.dependency_overrides[get_discovery_service] = lambda: mock_discovery_service
    client = TestClient(app)

    response = client.post(
        "/api/discovery/search",
        json={"prompt": "2D crafting survival sandbox", "limit": 5},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "2D crafting survival sandbox"
    assert data["match_count"] == 1
    assert data["no_strong_match"] is False
    assert len(data["results"]) == 1
    assert data["results"][0]["game"]["title"] == "Terraria"
    assert data["results"][0]["score"] == 0.88
    assert "Sandbox" in data["results"][0]["match_highlights"]


def test_discovery_search_no_match(mock_discovery_service):
    app.dependency_overrides[get_discovery_service] = lambda: mock_discovery_service
    client = TestClient(app)

    response = client.post(
        "/api/discovery/search",
        json={"prompt": "xyzqwk999zzzaaa non-existent game", "limit": 10},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["match_count"] == 0
    assert data["no_strong_match"] is True
    assert data["results"] == []


def test_discovery_search_validation_failures():
    client = TestClient(app)

    # Empty prompt
    resp_empty = client.post("/api/discovery/search", json={"prompt": ""})
    assert resp_empty.status_code == 422
    assert resp_empty.json()["error"]["code"] == "DISCOVERY_VALIDATION_FAILED"

    # Limit too large (>50)
    resp_large = client.post(
        "/api/discovery/search",
        json={"prompt": "action rpg", "limit": 100},
    )
    assert resp_large.status_code == 422
    assert resp_large.json()["error"]["code"] == "DISCOVERY_VALIDATION_FAILED"

    # Forbidden extra fields
    resp_extra = client.post(
        "/api/discovery/search",
        json={"prompt": "action rpg", "forbidden_field": True},
    )
    assert resp_extra.status_code == 422
    assert resp_extra.json()["error"]["code"] == "DISCOVERY_VALIDATION_FAILED"
