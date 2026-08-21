from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set
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
        Applies logarithmic diminishing returns scaling to prevent single-genre runaway.
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
                # Diminishing returns scaling: high existing scores grow more slowly
                diminishing_factor = 1.0 / (1.0 + 0.04 * pref.score)
                gain = weight * diminishing_factor
                pref.score = round(pref.score + gain, 2)
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
        logger.debug(
            "Recorded preference signal for user %s: genres=%s weight=%.1f source=%s",
            user_id,
            list(canonical_genres),
            weight,
            source,
        )

    @classmethod
    def get_preferences(cls, db: Session, user_id: str) -> UserPreferencesResponse:
        """Calculate and return calibrated Game DNA genre affinity distribution for user."""
        prefs = (
            db.query(UserGenrePreference)
            .filter(UserGenrePreference.user_id == user_id)
            .order_by(UserGenrePreference.score.desc())
            .all()
        )

        total_interactions = sum(p.interaction_count for p in prefs)
        total_score = sum(p.score for p in prefs)

        # Minimum data threshold for forming Game DNA: at least 2 interactions and 3.0 total score
        has_sufficient = len(prefs) > 0 and total_interactions >= 2 and total_score >= 3.0

        if not prefs or not has_sufficient:
            return UserPreferencesResponse(
                user_id=user_id,
                top_genres=[],
                total_interactions=total_interactions,
                strongest_match=None,
                recent_interest=None,
                confidence_level="LOW",
                summary_headline=None,
                has_sufficient_data=False,
            )

        items: List[GenreAffinityItem] = []
        for p in prefs:
            pct = round((p.score / total_score) * 100.0, 1)
            if pct >= 25.0:
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

        # Determine recent interest by latest interaction timestamp
        most_recent_pref = max(
            prefs,
            key=lambda p: p.last_interaction_at if p.last_interaction_at else datetime.min.replace(tzinfo=timezone.utc),
            default=None,
        )
        recent_genre = most_recent_pref.genre if most_recent_pref else None

        # Determine confidence level
        if total_interactions >= 6 and total_score >= 12.0:
            confidence = "HIGH"
        else:
            confidence = "MODERATE"

        # Determine descriptive title and summary headline
        top_genre = items[0].genre if items else None
        strongest = None
        headline = None
        if top_genre and len(items) >= 2 and items[0].percentage >= 40.0:
            strongest = f"{top_genre} Specialist"
            headline = f"{top_genre} & {items[1].genre} Focus"
        elif top_genre and len(items) >= 2:
            strongest = f"{top_genre} & {items[1].genre} Enthusiast"
            headline = f"{top_genre} / {items[1].genre}"
        elif top_genre:
            strongest = f"{top_genre} Explorer"
            headline = f"{top_genre} Focus"

        return UserPreferencesResponse(
            user_id=user_id,
            top_genres=items[:6],  # Top 6 ranked genres
            total_interactions=total_interactions,
            strongest_match=strongest,
            recent_interest=recent_genre,
            confidence_level=confidence,
            summary_headline=headline,
            has_sufficient_data=True,
        )

    @classmethod
    def get_generation_context(cls, db: Session, user_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Extract concise, structured Game DNA context for LLM generation prompt.
        Returns None if user is unauthenticated or has insufficient data.
        """
        if not user_id:
            return None

        prefs = cls.get_preferences(db, user_id)
        if not prefs.has_sufficient_data:
            return None

        return {
            "preferred_genres": [item.genre for item in prefs.top_genres[:3]],
            "confidence": prefs.confidence_level.lower(),
            "recent_interest": prefs.recent_interest,
            "has_sufficient_data": True,
        }


preference_service = PreferenceService()
