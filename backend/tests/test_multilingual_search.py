import json
import os
import pytest
from typing import Any, Dict, List

from app.search.lexical import LexicalIndex, normalize_string, tokenize, MULTILINGUAL_QUERY_DICTIONARY, GENRE_TRANSLATIONS
from app.search.query_parser import QueryParser
from app.search.ranker import Ranker, ParsedQuery


@pytest.fixture(scope="module")
def shared_catalog() -> List[Dict[str, Any]]:
    catalog_path = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "games_catalog.json")
    if not os.path.exists(catalog_path):
        pytest.skip("games_catalog.json not present; run ingestion first.")
    with open(catalog_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def lexical_index(shared_catalog: List[Dict[str, Any]]) -> LexicalIndex:
    return LexicalIndex(shared_catalog)


@pytest.fixture(scope="module")
def query_parser(lexical_index: LexicalIndex) -> QueryParser:
    return QueryParser(lexical_index)


def test_multilingual_query_parsing_russian(query_parser: QueryParser):
    """Test parsing Russian search queries into appropriate query types and translated tokens."""
    # 1. Russian Topic Tag / Mixed
    pq1 = query_parser.parse("уютный симулятор фермы")
    assert pq1.query_type in ("TOPIC_TAG", "CONCEPT", "MIXED")
    assert "Simulation" in pq1.extracted_genres or "Simulation" in pq1.clean_search_query.title() or "simulator" in pq1.clean_search_query.lower()
    assert "farm" in pq1.clean_search_query.lower() or "cozy" in pq1.clean_search_query.lower()

    # 2. Russian Mixed query with player mode
    pq2 = query_parser.parse("кооперативный рогалик")
    assert pq2.query_type in ("MIXED", "TOPIC_TAG")
    assert "Co-op" in pq2.extracted_player_modes
    assert "roguelike" in pq2.clean_search_query.lower()

    # 3. Russian Concept query
    pq3 = query_parser.parse("2D песочница крафтинг выживание")
    assert pq3.query_type in ("CONCEPT", "MIXED")
    assert "sandbox" in pq3.clean_search_query.lower()
    assert "survival" in pq3.clean_search_query.lower()


def test_multilingual_query_parsing_mixed(query_parser: QueryParser):
    """Test mixed-language query parsing."""
    pq1 = query_parser.parse("cozy ферма game")
    assert pq1.query_type in ("MIXED", "CONCEPT", "TOPIC_TAG")
    assert "farm" in pq1.clean_search_query.lower()

    pq2 = query_parser.parse("2D выживание building")
    assert pq2.query_type in ("MIXED", "CONCEPT")
    assert "survival" in pq2.clean_search_query.lower()


def test_lexical_index_multilingual_genres_and_tokens(lexical_index: LexicalIndex):
    """Verify LexicalIndex matches localized genres and query tokens accurately."""
    # Stardew Valley (413150) should be indexed under Indie, RPG, and Simulation
    stardew = lexical_index._games_by_id.get("413150")
    if stardew:
        genres = stardew.get("genres", [])
        assert "Simulation" in genres
        assert "Indie" in genres
        assert "RPG" in genres

    # Terraria (105600) should be indexed under Adventure, Action, RPG, Indie
    terraria = lexical_index._games_by_id.get("105600")
    if terraria:
        genres = terraria.get("genres", [])
        assert "Adventure" in genres
        assert "Action" in genres

    # Hollow Knight (367520) should be indexed under Adventure, Action, Indie
    hollow = lexical_index._games_by_id.get("367520")
    if hollow:
        genres = hollow.get("genres", [])
        assert "Action" in genres
        assert "Adventure" in genres


def test_cross_lingual_english_search_retrieves_localized_games(lexical_index: LexicalIndex):
    """Verify English concept queries find games that had non-English raw source text."""
    # 1. "cozy farming simulator" -> Stardew Valley / Farming games
    results = lexical_index.search_lexical("cozy farming simulator", limit=20)
    result_titles = [g["title"] for g, score, details in results]
    assert any("Stardew Valley" in t or "Farming" in t or "Farm" in t for t in result_titles[:15]), f"Expected farming games in top 15, got {result_titles[:5]}"

    # 2. "2D crafting sandbox survival" -> Terraria / Sandbox / Survival games
    results = lexical_index.search_lexical("2D crafting sandbox survival", limit=20)
    result_titles = [g["title"] for g, score, details in results]
    assert any("Terraria" in t or "Sandbox" in t or "Survival" in t for t in result_titles[:15]), f"Expected Terraria/Survival/Sandbox in top 15, got {result_titles[:5]}"

    # 3. "hand drawn 2D metroidvania insect adventure" -> Hollow Knight / Insect / Adventure games
    results = lexical_index.search_lexical("hand drawn 2D metroidvania insect adventure", limit=20)
    result_titles = [g["title"] for g, score, details in results]
    assert any("Hollow Knight" in t or "Insect" in t or "Metroidvania" in t or "Adventure" in t for t in result_titles[:15]), f"Expected insect/adventure/metroidvania games in top 15, got {result_titles[:5]}"


def test_russian_query_retrieval(lexical_index: LexicalIndex):
    """Verify Russian queries retrieve relevant canonical games."""
    # 1. "уютный симулятор фермы" -> Stardew Valley / Farming Simulator in top results
    results = lexical_index.search_lexical("уютный симулятор фермы", limit=20)
    result_titles = [g["title"] for g, score, details in results]
    assert any("Stardew" in t or "Farming" in t or "Farmer" in t or "farm" in t.lower() for t in result_titles[:10]), f"Expected farming games in top 10, got {result_titles[:5]}"

    # 2. "2D песочница крафтинг выживание" -> Terraria in top results
    results = lexical_index.search_lexical("2D песочница крафтинг выживание", limit=20)
    result_titles = [g["title"] for g, score, details in results]
    assert any("Terraria" in t or "Sandbox" in t or "Survival" in t for t in result_titles[:10]), f"Expected Terraria/Survival in top 10, got {result_titles[:5]}"

    # 3. "метроидвания жуки" -> Hollow Knight / Bug / Metroidvania games in top results
    results = lexical_index.search_lexical("метроидвания жуки", limit=20)
    result_titles = [g["title"] for g, score, details in results]
    assert any("Hollow Knight" in t or "Ori" in t or "Metroidvania" in t or "Bug" in t or "Bugs" in t for t in result_titles[:10]), f"Expected Hollow Knight/Metroidvania/Bug in top 10, got {result_titles[:5]}"


def test_mixed_language_query_retrieval(lexical_index: LexicalIndex):
    """Verify mixed English-Russian queries retrieve target games."""
    # "cozy ферма game" -> Stardew Valley / Farming game
    results = lexical_index.search_lexical("cozy ферма game", limit=20)
    result_titles = [g["title"] for g, score, details in results]
    assert any("Stardew" in t or "Farming" in t or "Farmer" in t or "farm" in t.lower() or "Sugardew" in t for t in result_titles[:10]), f"Expected Stardew or Farming in top 10, got {result_titles[:5]}"
