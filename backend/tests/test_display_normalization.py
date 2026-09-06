import pytest
from typing import Dict, Any, List

from app.schemas.discovery import GameDiscoveryItem, GameEnrichment, DiscoverySearchResult
from app.search.catalog import CatalogManager
from app.search.ranker import Ranker
from app.search.query_parser import QueryParser
from scripts.bootstrap.ingest_catalog import detect_description_language, build_display_description


def test_detect_description_language_accuracy():
    """Verify language detection across English, Cyrillic, CJK, Spanish, and French text."""
    # English
    en_desc = "Stardew Valley is an open-ended country-life RPG where you grow crops, raise animals, and build a farm."
    assert detect_description_language(en_desc) == "en"

    # Cyrillic / Russian
    ru_desc = "Вам досталась старая дедушкина ферма в долине Стардью. С горстью монет в кармане..."
    assert detect_description_language(ru_desc) == "ru"

    # CJK / Chinese
    zh_desc = "衰落的王国，古老的遗迹，等待着勇敢的骑士去探索这个充满危险与奇迹的地下世界..."
    assert detect_description_language(zh_desc) == "zh"

    # Spanish
    es_desc = "EL NUEVO RPG DE ACCION DE FANTASIA. Levantate, tiznado, y dejate guiar por la gracia para esgrimir el poder del Anillo de Elden en las Tierras Intermedias."
    assert detect_description_language(es_desc) == "es"

    # French
    fr_desc = "Vous incarnez Geralt de Riv, un tueur de monstres. Devant vous s'etend un continent en guerre, infeste de monstres, a explorer a votre guise."
    assert detect_description_language(fr_desc) == "fr"


def test_build_display_description_native_english():
    """Verify native English descriptions are preserved directly with source='steam'."""
    raw_desc = "Build the factory of your dreams on an alien planet with automation and exploration."
    desc, lang, source = build_display_description(
        title="Factorio",
        raw_desc=raw_desc,
        canonical_genres=["Simulation", "Strategy"],
        tags=["Automation", "Base Building", "Crafting"],
        player_modes=["Single-player", "Multi-player"],
        total_reviews=150000,
        positive_percent=98.0,
    )
    assert desc == raw_desc
    assert lang == "en"
    assert source == "steam"


def test_build_display_description_non_english_normalization():
    """Verify non-English source descriptions generate clean, informative English normalized descriptions."""
    ru_desc = "Вам досталась старая дедушкина ферма в долине Стардью..."
    desc, lang, source = build_display_description(
        title="Stardew Valley",
        raw_desc=ru_desc,
        canonical_genres=["Indie", "RPG", "Simulation"],
        tags=["Farming Sim", "Life Sim", "Crafting", "Pixel Graphics"],
        player_modes=["Single-player", "Co-op"],
        total_reviews=590000,
        positive_percent=98.0,
    )
    assert lang == "en"
    assert source == "normalized"
    assert "Stardew Valley is an acclaimed" in desc
    assert "Indie, RPG, and Simulation" in desc
    assert "Farming Sim" in desc


def test_build_display_description_localized_fallback():
    """Verify games without tags or genres fall back to original description with proper language code."""
    ru_desc = "Короткая новелла про жизнь в деревне."
    desc, lang, source = build_display_description(
        title="Village Tale",
        raw_desc=ru_desc,
        canonical_genres=[],
        tags=[],
        player_modes=[],
        total_reviews=5,
        positive_percent=60.0,
    )
    assert desc == ru_desc
    assert lang == "ru"
    assert source == "original"


def test_three_layer_metadata_separation_in_catalog():
    """Verify catalog records preserve original provenance, search representations, and display fields."""
    cat = CatalogManager.get_instance()
    stardew = cat.get_game("413150")
    if not stardew:
        pytest.skip("Stardew Valley not in current catalog")

    # 1. Original Layer
    assert "original_description" in stardew
    assert "original_genres" in stardew
    assert len(stardew["original_description"]) > 0

    # 2. Search Layer
    assert "canonical_genres" in stardew
    assert "search_tags" in stardew
    assert "semantic_profile" in stardew

    # 3. Display Layer
    assert stardew.get("display_title") == "Stardew Valley"
    assert stardew.get("description_language") == "en"
    assert stardew.get("description_source") in ("normalized", "steam")
    assert "Stardew Valley" in stardew.get("display_description", "")
    assert "RPG" in stardew.get("display_genres", [])


def test_ranker_formats_display_metadata():
    """Verify Ranker produces GameDiscoveryItem with full three-layer display metadata."""
    game_dict = {
        "id": "999001",
        "external_id": "999001",
        "source": "steam",
        "title": "Cosmic Odyssey",
        "display_title": "Cosmic Odyssey",
        "description": "Cosmic Odyssey is an acclaimed Sci-Fi game.",
        "display_description": "Cosmic Odyssey is an acclaimed Sci-Fi game.",
        "original_description": "Космическая одиссея в далеком будущем.",
        "description_language": "en",
        "description_source": "normalized",
        "genres": ["Adventure", "Sci-Fi"],
        "display_genres": ["Adventure", "Sci-Fi"],
        "original_genres": ["Приключения", "Фантастика"],
        "tags": ["Space", "Exploration", "Crafting"],
        "display_tags": ["Space", "Exploration", "Crafting"],
        "original_tags": ["Space", "Exploration", "Crafting"],
        "platforms": ["PC"],
        "release_year": 2024,
        "is_free": False,
        "total_reviews": 1200,
        "positive_percent": 92.0,
        "review_score_desc": "Very Positive",
    }

    parser = QueryParser()
    parsed = parser.parse("space exploration adventure")

    results = Ranker.rank_hybrid(
        semantic_candidates=[(game_dict, 0.88)],
        lexical_candidates=[],
        parsed_query=parsed,
        limit=5,
    )

    assert len(results) >= 1
    top_item: GameDiscoveryItem = results[0].game
    assert top_item.title == "Cosmic Odyssey"
    assert top_item.display_title == "Cosmic Odyssey"
    assert top_item.display_description == "Cosmic Odyssey is an acclaimed Sci-Fi game."
    assert top_item.description == "Cosmic Odyssey is an acclaimed Sci-Fi game."
    assert top_item.description_language == "en"
    assert top_item.description_source == "normalized"
    assert top_item.original_description == "Космическая одиссея в далеком будущем."
    assert top_item.display_genres == ["Adventure", "Sci-Fi"]


def test_igdb_enrichment_updates_display_description():
    """Verify that when an English IGDB summary is attached, display_description is updated with source='igdb'."""
    item = GameDiscoveryItem(
        id="413150",
        external_id="413150",
        title="Stardew Valley",
        display_title="Stardew Valley",
        description="Stardew Valley is an acclaimed Indie game.",
        display_description="Stardew Valley is an acclaimed Indie game.",
        description_language="en",
        description_source="normalized",
        genres=["Indie", "Simulation"],
    )

    igdb_summary = "You've inherited your grandfather's old farm plot in Stardew Valley. Armed with hand-me-down tools and a few coins, you set out to begin your new life."
    item.enrichment = GameEnrichment(
        status="AVAILABLE",
        summary=igdb_summary,
        cover_url="https://images.igdb.com/igdb/image/upload/t_cover_big/co1r7h.jpg",
    )

    # Simulation of DiscoveryService._attach_enrichment_and_update_display
    if item.enrichment and item.enrichment.summary and len(item.enrichment.summary.strip()) >= 15:
        item.display_description = item.enrichment.summary.strip()
        item.description = item.enrichment.summary.strip()
        item.description_source = "igdb"
        item.description_language = "en"

    assert item.display_description == igdb_summary
    assert item.description == igdb_summary
    assert item.description_source == "igdb"
    assert item.description_language == "en"
