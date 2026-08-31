import pytest
from app.schemas.discovery import DiscoveryFilters, DiscoverySessionContext
from app.search.query_parser import QueryParser
from app.search.ranker import Ranker, MIN_MATCH_SCORE_THRESHOLD


@pytest.fixture
def sample_game():
    return {
        "id": "105600",
        "title": "Terraria",
        "description": "Dig, fight, explore, build! Nothing is impossible in this action-packed adventure game.",
        "genres": ["Action", "Adventure", "RPG"],
        "tags": ["Sandbox", "Survival", "2D", "Crafting", "Multiplayer"],
        "player_modes": ["Single-player", "Multi-player", "Co-op"],
        "platforms": ["PC"],
        "release_year": 2011,
        "is_free": False,
        "total_reviews": 50000,
        "positive_percent": 98.0,
        "review_score_desc": "Overwhelmingly Positive",
    }


def test_ranker_passes_all_filters_when_matching(sample_game):
    # Matching filters
    filters = DiscoveryFilters(
        platforms=["PC"],
        player_modes=["Co-op"],
        genres=["Action"],
        tags=["Sandbox"],
        is_free=False,
        min_year=2010,
        max_year=2015,
    )
    assert Ranker.passes_filters(sample_game, filters) is True


def test_ranker_rejects_non_matching_filters(sample_game):
    # Non-matching platform
    assert Ranker.passes_filters(sample_game, DiscoveryFilters(platforms=["PlayStation 5"])) is False

    # Non-matching player mode (e.g. MMO only)
    assert Ranker.passes_filters(sample_game, DiscoveryFilters(player_modes=["MMO"])) is False

    # Non-matching genre
    assert Ranker.passes_filters(sample_game, DiscoveryFilters(genres=["Racing"])) is False

    # Non-matching free-to-play constraint
    assert Ranker.passes_filters(sample_game, DiscoveryFilters(is_free=True)) is False

    # Out of year range
    assert Ranker.passes_filters(sample_game, DiscoveryFilters(min_year=2020)) is False
    assert Ranker.passes_filters(sample_game, DiscoveryFilters(max_year=2005)) is False


def test_ranker_hard_negative_constraints(sample_game):
    qp = QueryParser()
    parsed = qp.parse("farming game without action")
    assert "Action" in parsed.avoid_genres
    assert Ranker.passes_filters(sample_game, hard_constraints=parsed.hard_constraints) is False


def test_ranker_session_less_like_this(sample_game):
    session = DiscoverySessionContext(less_like_this_game_ids=["105600"])
    assert Ranker.passes_filters(sample_game, session_context=session) is False


def test_ranker_extract_highlights_finds_overlapping_words(sample_game):
    query = "2D sandbox survival with co-op building"
    highlights = Ranker.extract_highlights(query, sample_game)
    assert any("Sandbox" in h for h in highlights)
    assert any("Survival" in h for h in highlights)
    assert any("2D" in h for h in highlights)
    assert any("Co-op" in h for h in highlights)


def test_ranker_generate_explanation(sample_game):
    explanation = Ranker.generate_explanation(
        query="2D sandbox survival",
        game=sample_game,
        highlights=["Sandbox tag", "Survival tag"],
    )
    assert "Sandbox" in explanation
    assert "Survival" in explanation
    assert "Action" in explanation or "Adventure" in explanation or "RPG" in explanation
    assert "Overwhelmingly Positive" in explanation


def test_ranker_hidden_gem_detection():
    gem_game = {
        "id": "1",
        "title": "Indie Masterpiece",
        "total_reviews": 500,
        "positive_percent": 95.0,
    }
    assert Ranker.check_hidden_gem(gem_game) is True

    huge_game = {
        "id": "2",
        "title": "Mainstream Hit",
        "total_reviews": 150000,
        "positive_percent": 95.0,
    }
    assert Ranker.check_hidden_gem(huge_game) is False


def test_ranker_rank_and_format_applies_threshold_and_limit(sample_game):
    low_game = dict(sample_game, id="999", title="Low Match Game", total_reviews=0, positive_percent=0.0)
    candidates = [
        (sample_game, 0.85),
        (low_game, 0.05),
    ]

    results = Ranker.rank_and_format(
        candidates=candidates,
        query="sandbox adventure",
        filters=None,
        limit=10,
        min_threshold=0.60,
    )

    assert len(results) == 1
    assert results[0].game.id == "105600"
    assert results[0].score >= 0.70
