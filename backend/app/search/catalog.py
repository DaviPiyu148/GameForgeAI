import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

from app.search.lexical import LexicalIndex, normalize_genres


logger = logging.getLogger(__name__)


def resolve_catalog_path(default_rel_path: str = "data/processed/games_catalog.json") -> str:
    """Resolve catalog path whether running from root, backend, or installed location."""
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", default_rel_path)),
        os.path.join("backend", default_rel_path),
        default_rel_path,
    ]
    for p in candidates:
        norm_p = os.path.normpath(p)
        if os.path.exists(norm_p):
            return norm_p
    return os.path.normpath(default_rel_path)


class CatalogManager:
    """In-memory catalog manager for normalized game discovery metadata and lexical indexing."""

    _instance: Optional["CatalogManager"] = None
    _lock = threading.Lock()

    def __init__(self, catalog_path: str = "data/processed/games_catalog.json"):
        self.catalog_path = resolve_catalog_path(catalog_path)
        self._games_by_id: Dict[str, Dict[str, Any]] = {}
        self._catalog_list: List[Dict[str, Any]] = []
        self._lexical_index: Optional[LexicalIndex] = None
        self._load_catalog()

    def _load_catalog(self) -> None:
        if not os.path.exists(self.catalog_path):
            logger.warning(f"Catalog file not found at {self.catalog_path}. Catalog will be empty.")
            return

        logger.info(f"Loading game catalog from {self.catalog_path}...")
        catalog_list: List[Dict[str, Any]] = []
        current_lines: List[str] = []

        with open(self.catalog_path, "r", encoding="utf-8") as f:
            for line in f:
                st = line.strip()
                if st == "[" or st == "]":
                    continue
                if st == "{":
                    current_lines = ["{"]
                elif (st == "}" or st == "},") and current_lines:
                    current_lines.append("}")
                    try:
                        obj = json.loads("\n".join(current_lines))
                        catalog_list.append(obj)
                    except Exception:
                        pass
                    current_lines = []
                elif current_lines:
                    current_lines.append(line)

        # Normalize genres and ensure three-layer display defaults across all catalog records
        for game in catalog_list:
            if "genres" in game:
                game["genres"] = normalize_genres(game["genres"])
            
            # Ensure display fields exist with robust fallbacks. `game.get(key, default)`
            # only applies `default` when `key` is MISSING — if a source record has an
            # explicit `"description": null`, `.get("description", "")` still returns
            # None, which then propagates into a non-Optional Pydantic response field
            # and raises a ValidationError for the whole request. `or ""` / `or []`
            # guards against both the missing-key and explicit-null cases.
            if not game.get("display_title"):
                game["display_title"] = game.get("title") or ""
            if not game.get("display_description"):
                game["display_description"] = game.get("description") or ""
            if not game.get("display_genres"):
                game["display_genres"] = game.get("genres") or []
            if not game.get("display_tags"):
                game["display_tags"] = game.get("tags") or []
            if "description_language" not in game:
                game["description_language"] = "en"
            if "description_source" not in game:
                game["description_source"] = "steam"
            if not game.get("original_description"):
                game["original_description"] = game.get("description") or ""
            if not game.get("original_genres"):
                game["original_genres"] = game.get("genres") or []
            if not game.get("original_tags"):
                game["original_tags"] = game.get("tags") or []

            # The ingested source data frequently stores display_description/
            # original_description/search_description as separately-parsed but
            # byte-for-byte identical copies of description (same for the *_title
            # variants) -- each is its own ~hundred-plus-char string object. Across
            # ~120k records that's real, avoidable resident memory. Strings are
            # immutable, so re-pointing an equal-content field at the canonical
            # object (letting the now-unreferenced duplicate get garbage collected)
            # is always safe -- unlike the genre/tag *lists* above, which are left
            # as separate objects since something downstream mutating one in place
            # would then silently corrupt the "same" list under a different key.
            description = game.get("description")
            for key in ("display_description", "original_description", "search_description"):
                if key in game and game[key] == description:
                    game[key] = description
            title = game.get("title")
            for key in ("display_title", "original_title"):
                if key in game and game[key] == title:
                    game[key] = title

        self._catalog_list = catalog_list
        self._games_by_id = {str(g["id"]): g for g in catalog_list if "id" in g}
        self._games_by_external_id = {str(g["external_id"]): g for g in catalog_list if "external_id" in g}
        logger.info(f"Catalog loaded successfully with {len(self._games_by_id)} games.")

    @classmethod
    def get_instance(cls, catalog_path: str = "data/processed/games_catalog.json") -> "CatalogManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(catalog_path=catalog_path)
        return cls._instance

    def get_game(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve single game metadata by string ID or Steam App external_id in O(1) time."""
        s_id = str(game_id)
        return self._games_by_id.get(s_id) or self._games_by_external_id.get(s_id)

    def get_lexical_index(self) -> Optional[LexicalIndex]:
        """Get the instantiated LexicalIndex (lazily initialized on first access)."""
        if self._lexical_index is None and self._catalog_list:
            with self._lock:
                if self._lexical_index is None and self._catalog_list:
                    self._lexical_index = LexicalIndex(self._catalog_list)
        return self._lexical_index

    def get_all_games(self) -> List[Dict[str, Any]]:
        """Return the full list of catalog games."""
        return self._catalog_list

    def count(self) -> int:
        return len(self._games_by_id)
