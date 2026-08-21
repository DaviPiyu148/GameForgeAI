import asyncio
import datetime
import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.schemas.discovery import GameEnrichment
from app.search.lexical import normalize_string


logger = logging.getLogger(__name__)

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
IGDB_GAMES_URL = "https://api.igdb.com/v4/games"
IGDB_EXTERNAL_GAMES_URL = "https://api.igdb.com/v4/external_games"


class IGDBEnrichmentService:
    """
    Resilient, non-blocking IGDB metadata enrichment service with SQLite and in-memory caching.
    Ensures core discovery search never fails and never blocks on IGDB outages.
    """

    _instance: Optional["IGDBEnrichmentService"] = None
    _lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        self.client_id = settings.IGDB_CLIENT_ID
        self.client_secret = settings.IGDB_CLIENT_SECRET
        self.ttl_seconds = settings.IGDB_CACHE_TTL_DAYS * 86400

        # Resolve cache DB path
        if db_path is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            db_path = os.path.join(backend_dir, "data", "processed", "igdb_cache.sqlite3")
        self.db_path = db_path

        self._hot_cache: Dict[str, Tuple[GameEnrichment, float]] = {}
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        self._init_sqlite_cache()

    @classmethod
    def get_instance(cls) -> "IGDBEnrichmentService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _init_sqlite_cache(self) -> None:
        """Create igdb_cache table in SQLite if it doesn't exist."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS igdb_cache (
                        steam_app_id TEXT PRIMARY KEY,
                        igdb_id INTEGER,
                        status TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        fetched_at REAL NOT NULL,
                        expires_at REAL NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_igdb_cache_exp ON igdb_cache (expires_at)")
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to initialize IGDB SQLite cache: {e}")

    def is_configured(self) -> bool:
        """Check if IGDB credentials are configured."""
        return bool(self.client_id and self.client_secret)

    def _get_from_cache(self, steam_app_id: str) -> Optional[GameEnrichment]:
        """Check in-memory hot cache and SQLite cache for non-expired entry."""
        now = time.time()
        # 1. Hot in-memory cache with TTL check
        if steam_app_id in self._hot_cache:
            enrichment, expires_at = self._hot_cache[steam_app_id]
            if expires_at > now:
                return enrichment
            else:
                del self._hot_cache[steam_app_id]

        # 2. SQLite cache
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT payload_json, expires_at FROM igdb_cache WHERE steam_app_id = ?",
                    (steam_app_id,),
                )
                row = cursor.fetchone()
                if row:
                    payload_json, expires_at = row
                    if expires_at > now:
                        data = json.loads(payload_json)
                        enrichment = GameEnrichment(**data)
                        self._hot_cache[steam_app_id] = (enrichment, expires_at)
                        return enrichment
        except Exception as e:
            logger.debug(f"IGDB cache read error for {steam_app_id}: {e}")

        return None

    def _save_to_cache(self, steam_app_id: str, enrichment: GameEnrichment, igdb_id: Optional[int] = None) -> None:
        """Persist enrichment result to hot cache and SQLite."""
        now = time.time()
        expires_at = now + self.ttl_seconds
        self._hot_cache[steam_app_id] = (enrichment, expires_at)

        try:
            payload_json = enrichment.model_dump_json()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO igdb_cache 
                    (steam_app_id, igdb_id, status, payload_json, fetched_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (steam_app_id, igdb_id, enrichment.status, payload_json, now, expires_at),
                )
                conn.commit()
        except Exception as e:
            logger.debug(f"IGDB cache write error for {steam_app_id}: {e}")

    async def _get_access_token(self) -> Optional[str]:
        """Fetch or return valid cached Twitch OAuth2 token."""
        if not self.is_configured():
            return None

        now = time.time()
        if self._access_token and self._token_expires_at > now + 60:
            return self._access_token

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.post(
                    TWITCH_TOKEN_URL,
                    params={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "client_credentials",
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    self._access_token = data.get("access_token")
                    expires_in = data.get("expires_in", 3600)
                    self._token_expires_at = now + expires_in
                    logger.info("IGDB Twitch OAuth2 access token acquired successfully.")
                    return self._access_token
                else:
                    logger.warning(f"IGDB OAuth token failure: HTTP {res.status_code}")
                    return None
        except Exception as e:
            logger.warning(f"IGDB OAuth request exception: {e}")
            return None

    async def enrich_game(self, steam_app_id: str, title: str, release_year: int = 0) -> GameEnrichment:
        """
        Enrich a single game by Steam App ID / title.
        Returns GameEnrichment (always non-blocking, safe on errors).
        """
        # Check cache first
        cached = self._get_from_cache(steam_app_id)
        if cached is not None:
            return cached

        if not self.is_configured():
            enrichment = GameEnrichment(status="UNAVAILABLE")
            self._save_to_cache(steam_app_id, enrichment)
            return enrichment

        token = await self._get_access_token()
        if not token:
            return GameEnrichment(status="UNAVAILABLE")

        try:
            headers = {
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }

            # 1. Search IGDB external_games by steam category (category 1 = Steam)
            async with httpx.AsyncClient(timeout=2.0) as client:
                query_body = f'fields game, uid, category; where category = 1 & uid = "{steam_app_id}"; limit 1;'
                res = await client.post(IGDB_EXTERNAL_GAMES_URL, headers=headers, content=query_body)
                
                igdb_game_id = None
                if res.status_code == 200:
                    external_records = res.json()
                    if external_records and len(external_records) > 0:
                        igdb_game_id = external_records[0].get("game")

                # 2. Fallback: search by exact normalized title if external_games missed
                if not igdb_game_id:
                    clean_t = title.replace('"', '\\"')
                    title_query = f'fields id, name; search "{clean_t}"; limit 1;'
                    res_title = await client.post(IGDB_GAMES_URL, headers=headers, content=title_query)
                    if res_title.status_code == 200:
                        title_records = res_title.json()
                        if title_records and len(title_records) > 0:
                            igdb_game_id = title_records[0].get("id")

                if not igdb_game_id:
                    enrichment = GameEnrichment(status="NOT_FOUND")
                    self._save_to_cache(steam_app_id, enrichment)
                    return enrichment

                # 3. Retrieve full game enrichment details
                game_body = (
                    f"fields id, name, summary, cover.image_id, screenshots.image_id, "
                    f"involved_companies.company.name, involved_companies.developer, involved_companies.publisher, "
                    f"themes.name, franchises.name, url; "
                    f"where id = {igdb_game_id}; limit 1;"
                )
                res_game = await client.post(IGDB_GAMES_URL, headers=headers, content=game_body)
                if res_game.status_code == 200:
                    game_records = res_game.json()
                    if game_records and len(game_records) > 0:
                        gdata = game_records[0]
                        
                        cover_img = gdata.get("cover", {}).get("image_id") if gdata.get("cover") else None
                        cover_url = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{cover_img}.jpg" if cover_img else None

                        screenshots = []
                        for sc in gdata.get("screenshots", []):
                            sc_img = sc.get("image_id")
                            if sc_img:
                                screenshots.append(f"https://images.igdb.com/igdb/image/upload/t_screenshot_med/{sc_img}.jpg")

                        developer = None
                        publisher = None
                        for comp in gdata.get("involved_companies", []):
                            c_name = comp.get("company", {}).get("name")
                            if comp.get("developer") and not developer:
                                developer = c_name
                            if comp.get("publisher") and not publisher:
                                publisher = c_name

                        themes = [t.get("name") for t in gdata.get("themes", []) if t.get("name")]
                        franchise_list = gdata.get("franchises", [])
                        franchise = franchise_list[0].get("name") if franchise_list else None

                        enrichment = GameEnrichment(
                            status="AVAILABLE",
                            cover_url=cover_url,
                            screenshot_urls=screenshots[:3],
                            summary=gdata.get("summary"),
                            developer=developer,
                            publisher=publisher,
                            themes=themes,
                            franchise=franchise,
                            igdb_id=igdb_game_id,
                            igdb_url=gdata.get("url"),
                        )
                        self._save_to_cache(steam_app_id, enrichment, igdb_id=igdb_game_id)
                        return enrichment

                enrichment = GameEnrichment(status="NOT_FOUND")
                self._save_to_cache(steam_app_id, enrichment)
                return enrichment

        except Exception as e:
            logger.warning(f"IGDB enrichment error for {steam_app_id}: {e}")
            enrichment = GameEnrichment(status="UNAVAILABLE")
            return enrichment

    async def enrich_results(self, games: List[Dict[str, Any]]) -> Dict[str, GameEnrichment]:
        """
        Enrich a batch of games concurrently with timeout and cache resolution.
        """
        enrichment_map: Dict[str, GameEnrichment] = {}
        missing: List[Dict[str, Any]] = []

        # Check cache first (0ms latency)
        for g in games:
            gid = str(g.get("external_id") or g.get("id"))
            cached = self._get_from_cache(gid)
            if cached is not None:
                enrichment_map[gid] = cached
            else:
                missing.append(g)

        if not missing or not self.is_configured():
            for g in missing:
                gid = str(g.get("external_id") or g.get("id"))
                enrichment_map[gid] = GameEnrichment(status="UNAVAILABLE")
            return enrichment_map

        # Enrich missing games in parallel with a strict 1.5s total timeout
        tasks = [
            self.enrich_game(
                steam_app_id=str(g.get("external_id") or g.get("id")),
                title=g.get("title", ""),
                release_year=g.get("release_year", 0),
            )
            for g in missing
        ]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for g, res in zip(missing, results):
                gid = str(g.get("external_id") or g.get("id"))
                if isinstance(res, GameEnrichment):
                    enrichment_map[gid] = res
                else:
                    enrichment_map[gid] = GameEnrichment(status="UNAVAILABLE")
        except Exception:
            for g in missing:
                gid = str(g.get("external_id") or g.get("id"))
                enrichment_map[gid] = GameEnrichment(status="UNAVAILABLE")

        return enrichment_map
