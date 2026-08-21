from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session

from app.models.preference import UserGenrePreference
from app.schemas.profile import GenreAffinityItem, UserPreferencesResponse

logger = logging.getLogger(__name__)

# Canonical standardized genre vocabulary
CANONICAL_GENRES: List[str] = [
    "Action",
    "Adventure",
    "RPG",
    "Strategy",
    "Shooter",
    "Platformer",
    "Survival",
    "Roguelike",
    "Arcade",
    "Puzzle",
    "Casual",
    "Horror",
    "Simulation",
]

# Keyword-to-canonical-genre synonym mapping
GENRE_SYNONYMS: Dict[str, str] = {
    "action": "Action",
    "hack and slash": "Action",
    "beat 'em up": "Action",
    "beat em up": "Action",
    "melee": "Action",
    "adventure": "Adventure",
    "story rich": "Adventure",
    "narrative": "Adventure",
    "exploration": "Adventure",
    "rpg": "RPG",
    "role-playing": "RPG",
    "action rpg": "RPG",
    "dungeon crawler": "RPG",
    "strategy": "Strategy",
    "tower defense": "Strategy",
    "tactical": "Strategy",
    "rts": "Strategy",
    "shooter": "Shooter",
    "fps": "Shooter",
    "tps": "Shooter",
    "bullet hell": "Shooter",
    "twin stick": "Shooter",
    "top-down shooter": "Shooter",
    "platformer": "Platformer",
    "2d platformer": "Platformer",
    "precision platformer": "Platformer",
    "metroidvania": "Platformer",
    "side scroller": "Platformer",
    "survival": "Survival",
    "survival horror": "Survival",
    "wave survival": "Survival",
    "arena survival": "Survival",
    "roguelike": "Roguelike",
    "roguelite": "Roguelike",
    "permadeath": "Roguelike",
    "arcade": "Arcade",
    "retro": "Arcade",
    "score attack": "Arcade",
    "puzzle": "Puzzle",
    "logic": "Puzzle",
    "physics puzzle": "Puzzle",
    "casual": "Casual",
    "cozy": "Casual",
    "relaxing": "Casual",
    "horror": "Horror",
    "psychological horror": "Horror",
    "simulation": "Simulation",
    "sandbox": "Simulation",
    "crafting": "Simulation",
}


class PreferenceService:
    """
    Service for tracking and aggregating user genre preferences from behavioral telemetry.
    Calculates normalized affinity profiles without black-box machine learning.
    """

    @classmethod
    def map_to_canonical_genres(cls, terms: List[str]) -> Set[str]:
        """Map raw tags, search tokens, or genre names into standardized canonical genres."""
        matched: Set[str] = set()
        for term in terms:
            norm = term.lower().strip()
            # Direct canonical match
            for canonical in CANONICAL_GENRES:
                if canonical.lower() == norm:
                    matched.add(canonical)
                    break
            # Synonym lookup
            if norm in GENRE_SYNONYMS:
                matched.add(GENRE_SYNONYMS[norm])
            else:
                # Substring match in synonyms
                for syn_key, target in GENRE_SYNONYMS.items():
                    if syn_key in norm or norm in syn_key:
                        matched.add(target)
                        break

        return matched

    @classmethod
    def record_signal(
        cls,
        db: Session,
        user_id: str,
        raw_genres_or_tags: List[str],
        weight: float,
        source: str = "generic",
    ) -> None:
        """
        Record behavioral interaction signal for user across identified genres.
        Applies incremental weight update to UserGenrePreference table.
        """
        if not raw_genres_or_tags or weight <= 0:
            return

        canonical_genres = cls.map_to_canonical_genres(raw_genres_or_tags)
        if not canonical_genres:
            return

        now = datetime.now(timezone.utc)

        for genre in canonical_genres:
            pref = (
                db.query(UserGenrePreference)
                .filter(
                    UserGenrePreference.user_id == user_id,
                    UserGenrePreference.genre == genre,
                )
                .first()
            )

            if pref:
                pref.score = round(pref.score + weight, 2)
                pref.interaction_count += 1
                pref.last_interaction_at = now
            else:
                pref = UserGenrePreference(
                    user_id=user_id,
                    genre=genre,
                    score=round(weight, 2),
                    interaction_count=1,
                    last_interaction_at=now,
                )
                db.add(pref)

        db.commit()
        logger.debug("Recorded preference signal for user %s: genres=%s weight=%.1f source=%s", user_id, list(canonical_genres), weight, source)

    @classmethod
    def get_preferences(cls, db: Session, user_id: str) -> UserPreferencesResponse:
        """Calculate and return calibrated genre affinity distribution for user."""
        prefs = (
            db.query(UserGenrePreference)
            .filter(UserGenrePreference.user_id == user_id)
            .order_by(UserGenrePreference.score.desc())
            .all()
        )

        total_interactions = sum(p.interaction_count for p in prefs)
        total_score = sum(p.score for p in prefs)

        if not prefs or total_score <= 0.5:
            return UserPreferencesResponse(
                user_id=user_id,
                top_genres=[],
                total_interactions=total_interactions,
                strongest_match=None,
                has_sufficient_data=False,
            )

        items: List[GenreAffinityItem] = []
        for p in prefs:
            pct = round((p.score / total_score) * 100.0, 1)
            if pct >= 28.0:
                tier = "High"
            elif pct >= 12.0:
                tier = "Moderate"
            else:
                tier = "Emerging"

            items.append(
                GenreAffinityItem(
                    genre=p.genre,
                    score=p.score,
                    percentage=pct,
                    interaction_count=p.interaction_count,
                    affinity_tier=tier,
                )
            )

        # Determine descriptive title for strongest affinity
        top_genre = items[0].genre if items else None
        strongest = None
        if top_genre and len(items) >= 2 and items[0].percentage >= 35.0:
            strongest = f"{top_genre} & {items[1].genre} Enthusiast"
        elif top_genre:
            strongest = f"{top_genre} Explorer"

        return UserPreferencesResponse(
            user_id=user_id,
            top_genres=items[:6],  # Top 6 genres
            total_interactions=total_interactions,
            strongest_match=strongest,
            has_sufficient_data=total_interactions >= 2,
        )


preference_service = PreferenceService()
