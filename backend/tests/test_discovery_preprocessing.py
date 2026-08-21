import os
import tempfile
import json
import pytest

from scripts.ingest_catalog import (
    clean_text,
    extract_year,
    build_semantic_profile,
    ingest_catalog,
)


def test_clean_text_strips_html_and_normalizes_whitespace():
    raw_html = "<p>This is a <b>great</b> game!<br>Enjoy the <i>action</i>.</p>"
    assert clean_text(raw_html) == "This is a great game! Enjoy the action."

    raw_whitespace = "  Multiple    spaces   \n\n and tabs \t here. "
    assert clean_text(raw_whitespace) == "Multiple spaces and tabs here."

    assert clean_text("") == ""
    assert clean_text(None) == ""


def test_extract_year_handles_various_formats():
    assert extract_year("2023-05-12") == 2023
    assert extract_year("1999/11/01") == 1999
    assert extract_year("Dec 2018") == 2018
    assert extract_year("2011") == 2011
    assert extract_year("invalid_date") == 0
    assert extract_year("") == 0
    assert extract_year(None) == 0


def test_build_semantic_profile_deterministic():
    profile1 = build_semantic_profile(
        title="Terraria",
        genres=["Action", "Adventure", "RPG"],
        tags=["Sandbox", "Survival", "2D", "Crafting"],
        player_modes=["Single-player", "Multi-player"],
        platforms=["PC"],
        description="Dig, fight, explore, build! Nothing is impossible.",
    )
    profile2 = build_semantic_profile(
        title="Terraria",
        genres=["Action", "Adventure", "RPG"],
        tags=["Sandbox", "Survival", "2D", "Crafting"],
        player_modes=["Single-player", "Multi-player"],
        platforms=["PC"],
        description="Dig, fight, explore, build! Nothing is impossible.",
    )
    assert profile1 == profile2
    assert "Title: Terraria" in profile1
    assert "Genres: Action, Adventure, RPG" in profile1
    assert "Tags: Sandbox, Survival, 2D, Crafting" in profile1
    assert "Modes: Single-player, Multi-player" in profile1
    assert "Platforms: PC" in profile1
    assert "Description: Dig, fight, explore, build!" in profile1


def test_ingest_catalog_on_mock_csvs():
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = os.path.join(tmpdir, "raw")
        out_file = os.path.join(tmpdir, "processed", "games_catalog.json")
        os.makedirs(raw_dir, exist_ok=True)

        # Write mock games.csv
        with open(os.path.join(raw_dir, "games.csv"), "w", encoding="utf-8") as f:
            f.write("app_id,name,release_date,is_free\n")
            f.write("100,Cyber Quest,2022-04-01,0\n")
            f.write("200,Space Miner,2021-09-15,1\n")
            f.write("300,No Tags Game,2020-01-01,0\n")

        # Write mock genres.csv
        with open(os.path.join(raw_dir, "genres.csv"), "w", encoding="utf-8") as f:
            f.write("app_id,genre\n")
            f.write("100,Action\n")
            f.write("100,RPG\n")
            f.write("200,Strategy\n")

        # Write mock categories.csv
        with open(os.path.join(raw_dir, "categories.csv"), "w", encoding="utf-8") as f:
            f.write("app_id,category\n")
            f.write("100,Single-player\n")
            f.write("100,Multi-player\n")
            f.write("200,Single-player\n")

        # Write mock tags.csv
        with open(os.path.join(raw_dir, "tags.csv"), "w", encoding="utf-8") as f:
            f.write("app_id,tag\n")
            f.write("100,Cyberpunk\n")
            f.write("100,Story Rich\n")
            f.write("200,Space\n")

        # Write mock descriptions.csv
        with open(os.path.join(raw_dir, "descriptions.csv"), "w", encoding="utf-8") as f:
            f.write("app_id,summary,extensive,about\n")
            f.write("100,A thrilling cyberpunk RPG story.,detailed,about\n")
            f.write("200,A space mining strategy simulator.,detailed,about\n")
            f.write("300,A short game without tags.,detailed,about\n")

        # Write mock reviews.csv
        with open(os.path.join(raw_dir, "reviews.csv"), "w", encoding="utf-8") as f:
            f.write("app_id,review_score,review_score_description,positive,negative,total\n")
            f.write("100,9,Overwhelmingly Positive,950,50,1000\n")
            f.write("200,7,Positive,400,100,500\n")

        stats = ingest_catalog(raw_dir=raw_dir, output_file=out_file, min_desc_len=10, min_tags_or_genres=1)

        assert stats["total_scanned"] == 3
        # Game 300 has no tags/genres, so it's filtered out
        assert stats["catalog_count"] == 2

        with open(out_file, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        assert len(catalog) == 2
        g1 = catalog[0]
        assert g1["id"] == "100"
        assert g1["title"] == "Cyber Quest"
        assert g1["genres"] == ["Action", "RPG"]
        assert g1["tags"] == ["Cyberpunk", "Story Rich"]
        assert g1["player_modes"] == ["Single-player", "Multi-player"]
        assert g1["release_year"] == 2022
        assert g1["is_free"] is False
        assert g1["total_reviews"] == 1000
        assert g1["positive_percent"] == 95.0
