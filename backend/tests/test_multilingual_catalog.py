import json
import os
import pytest
from typing import Any, Dict, List

from scripts.ingest_catalog import normalize_genres_list, build_semantic_profile, EXPANDED_GENRE_MAP


def test_genre_normalization_mappings():
    """Verify Russian, Ukrainian, Chinese, Japanese, Spanish mappings convert accurately to English canonicals."""
    # Russian / Ukrainian
    assert normalize_genres_list(["Инди", "Ролевые игры", "Симуляторы"]) == ["Indie", "RPG", "Simulation"]
    assert normalize_genres_list(["Экшены", "Приключенческие игры"]) == ["Action", "Adventure"]
    assert normalize_genres_list(["Бесплатные", "Стратегии", "Гонки"]) == ["Free to Play", "Strategy", "Racing"]
    assert normalize_genres_list(["інді", "пригоди"]) == ["Indie", "Adventure"]

    # Chinese
    assert normalize_genres_list(["角色扮演", "独立", "动作"]) == ["RPG", "Indie", "Action"]
    assert normalize_genres_list(["冒险", "模拟", "策略"]) == ["Adventure", "Simulation", "Strategy"]

    # Japanese
    assert normalize_genres_list(["アドベンチャー", "インディー", "アクション"]) == ["Adventure", "Indie", "Action"]
    assert normalize_genres_list(["シミュレーション", "ロールプレイング"]) == ["Simulation", "RPG"]

    # Spanish / European
    assert normalize_genres_list(["Acción", "Rol", "Aventura"]) == ["Action", "RPG", "Adventure"]
    assert normalize_genres_list(["Simuladores", "Estrategia"]) == ["Simulation", "Strategy"]


def test_genre_normalization_deduplication_and_passthrough():
    """Verify unknown English or clean genres pass through without duplicate pollution."""
    mixed = ["Action", "экшены", "Action", "RPG", "ролевые игры"]
    normalized = normalize_genres_list(mixed)
    assert normalized == ["Action", "RPG"]


def test_build_semantic_profile_multilingual():
    """Verify semantic profile contains title, canonical genres, tags, modes, platforms, and clean description."""
    profile = build_semantic_profile(
        title="Stardew Valley",
        genres=["Indie", "RPG", "Simulation"],
        tags=["Farming Sim", "Cozy", "Pixel Graphics", "2D", "Crafting"],
        player_modes=["Single-player", "Multi-player", "Co-op"],
        platforms=["PC"],
        description="Вам досталась старая дедушкина ферма в долине Стардью. Сможете ли вы превратить заросшее поле в цветущий сад?",
    )
    assert "Title: Stardew Valley" in profile
    assert "Genres: Indie, RPG, Simulation" in profile
    assert "Tags: Farming Sim, Cozy, Pixel Graphics, 2D, Crafting" in profile
    assert "Modes: Single-player, Multi-player, Co-op" in profile
    assert "Platforms: PC" in profile
    assert "Description:" in profile


def test_catalog_data_preservation_and_fields():
    """Verify games_catalog.json retains original_* fields alongside canonical search fields."""
    catalog_path = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "games_catalog.json")
    if not os.path.exists(catalog_path):
        pytest.skip("games_catalog.json not present; run ingestion first.")

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    assert len(catalog) >= 20000, "Catalog should have at least 20,000 ingested games"

    # Lookup landmark test cases
    catalog_by_id = {str(g.get("id")): g for g in catalog}

    # 1. Stardew Valley (413150)
    if "413150" in catalog_by_id:
        stardew = catalog_by_id["413150"]
        assert stardew["title"] == "Stardew Valley"
        assert stardew["original_title"] == "Stardew Valley"
        assert "original_genres" in stardew
        assert "original_description" in stardew
        assert "genres" in stardew
        assert "Indie" in stardew["genres"]
        assert "RPG" in stardew["genres"]
        assert "Simulation" in stardew["genres"]
        assert "Farming Sim" in stardew["tags"] or "Agriculture" in stardew["tags"]

    # 2. Terraria (105600)
    if "105600" in catalog_by_id:
        terraria = catalog_by_id["105600"]
        assert terraria["title"] == "Terraria"
        assert "Indie" in terraria["genres"]
        assert "Action" in terraria["genres"]
        assert "Adventure" in terraria["genres"]
        assert "Sandbox" in terraria["tags"] or "2D" in terraria["tags"]

    # 3. Hollow Knight (367520)
    if "367520" in catalog_by_id:
        hollow = catalog_by_id["367520"]
        assert hollow["title"] == "Hollow Knight"
        assert "Action" in hollow["genres"]
        assert "Adventure" in hollow["genres"]
        assert "Indie" in hollow["genres"]
        assert "Metroidvania" in hollow["tags"] or "2D" in hollow["tags"]
