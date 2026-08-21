"""
Progression Service for GameForge AI.

Server-authoritative engine managing:
1. Experience Points (XP) with atomic concurrency-safe increments.
2. Anti-spam rate limiting and deduplication policies.
3. Level progression curve and deterministic creator titles.
4. Idempotent milestone/badge evaluations and unlocks.
5. Recent activity audit history.
"""
from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.models.progression import UserProgress, XPEvent, UserMilestone
from app.models.user import User
from app.models.preference import UserGenrePreference
from app.models.project import Project
from app.schemas.profile import UserProgressResponse, XPEventItem, MilestoneItem

logger = logging.getLogger(__name__)

# Base XP amounts per event type
DEFAULT_XP_AMOUNTS = {
    "SEARCH": 10,
    "SAVE_DISCOVERY": 25,
    "BUILD_SIMILAR": 25,
    "START_BUILD": 20,
    "COMPLETE_BUILD": 50,
    "COMPLETE_CAMPAIGN": 75,
    "PLAYTEST": 35,
    "PLAYTEST_WIN": 50,
    "IMPROVE_GAME": 40,
    "AI_ANALYSIS": 40,
}

# Level threshold definitions: Level N requires LEVEL_THRESHOLDS[N-1] cumulative XP
LEVEL_THRESHOLDS = [
    0,     # Level 1
    100,   # Level 2
    250,   # Level 3
    450,   # Level 4
    700,   # Level 5
    1000,  # Level 6
    1350,  # Level 7
    1750,  # Level 8
    2200,  # Level 9
    2700,  # Level 10
]

# Canonical 8 Creator Milestones
CANONICAL_MILESTONES: Dict[str, Dict[str, Any]] = {
    "FIRST_BUILD": {
        "title": "First Creation",
        "description": "Created your first playable game prototype",
        "icon": "construction",
        "xp_bonus": 50,
    },
    "FIRST_CAMPAIGN": {
        "title": "Campaign Architect",
        "description": "Generated a multi-stage/level campaign game",
        "icon": "layers",
        "xp_bonus": 75,
    },
    "FIRST_PLAYTEST": {
        "title": "Field Tester",
        "description": "Completed your first gameplay test session",
        "icon": "sports_esports",
        "xp_bonus": 35,
    },
    "FIRST_WIN": {
        "title": "Victor",
        "description": "Achieved victory in a generated game",
        "icon": "emoji_events",
        "xp_bonus": 50,
    },
    "FIRST_AI_ANALYSIS": {
        "title": "AI Analyst",
        "description": "Analyzed playtest session telemetry with AI",
        "icon": "psychology",
        "xp_bonus": 40,
    },
    "GENRE_EXPLORER": {
        "title": "Genre Explorer",
        "description": "Interacted meaningfully across 3+ distinct genres",
        "icon": "explore",
        "xp_bonus": 50,
    },
    "BUILD_SIMILAR_PRO": {
        "title": "Inspiration Seeker",
        "description": "Used Build Similar to craft an inspired prototype",
        "icon": "auto_awesome",
        "xp_bonus": 40,
    },
    "CREATOR_10": {
        "title": "Master Forger",
        "description": "Built 10 game prototypes",
        "icon": "military_tech",
        "xp_bonus": 100,
    },
}


def calculate_level_bounds(total_xp: int) -> Tuple[int, int, int]:
    """
    Given total XP, compute:
    - current_level (1-indexed)
    - current_level_base_xp (XP needed to reach current level)
    - next_level_xp (XP needed to reach next level)
    """
    if total_xp < 0:
        total_xp = 0

    level = 1
    for lvl_idx, threshold in enumerate(LEVEL_THRESHOLDS):
        if total_xp >= threshold:
            level = lvl_idx + 1
        else:
            break

    if level <= len(LEVEL_THRESHOLDS):
        base_xp = LEVEL_THRESHOLDS[level - 1]
        if level < len(LEVEL_THRESHOLDS):
            next_xp = LEVEL_THRESHOLDS[level]
        else:
            next_xp = LEVEL_THRESHOLDS[-1] + 500
    else:
        # Extrapolate beyond defined level table (+500 per level)
        extra_levels = level - len(LEVEL_THRESHOLDS)
        base_xp = LEVEL_THRESHOLDS[-1] + extra_levels * 500
        next_xp = base_xp + 500

    return level, base_xp, next_xp


def get_creator_title(level: int) -> str:
    """Derive cosmetic creator title deterministically from server level."""
    if level >= 20:
        return "World Architect"
    elif level >= 15:
        return "Systems Architect"
    elif level >= 10:
        return "Game Designer"
    elif level >= 5:
        return "Game Builder"
    return "Novice Creator"


class ProgressionService:
    """
    Server-authoritative progression engine managing user experience points (XP),
    gamification level progression curves, anti-spam rate limiting, creator titles,
    and milestone awards.
    """

    @classmethod
    def get_or_create_progress(cls, db: Session, user_id: str) -> UserProgress:
        """Fetch or initialize UserProgress row for a user."""
        progress = db.query(UserProgress).filter(UserProgress.user_id == user_id).first()
        if not progress:
            user = db.query(User).filter(User.id == user_id).first()
            user_lvl = user.level if user and user.level else 1
            base_xp = LEVEL_THRESHOLDS[min(user_lvl - 1, len(LEVEL_THRESHOLDS) - 1)] if user_lvl > 1 else 0

            progress = UserProgress(
                user_id=user_id,
                total_xp=base_xp,
                current_level=user_lvl,
            )
            db.add(progress)
            try:
                db.commit()
                db.refresh(progress)
            except IntegrityError:
                db.rollback()
                progress = db.query(UserProgress).filter(UserProgress.user_id == user_id).first()

        return progress

    @classmethod
    def check_anti_spam(
        cls,
        db: Session,
        user_id: str,
        event_type: str,
        source_ref: Optional[str] = None,
    ) -> bool:
        """
        Evaluate anti-spam policy. Returns True if event is permitted to earn XP,
        or False if event is suppressed/rate-limited.
        """
        now = datetime.now(timezone.utc)

        if event_type == "SEARCH":
            # Rule 1: No identical search query within 10 minutes
            if source_ref:
                cutoff = now - timedelta(minutes=10)
                recent_same = (
                    db.query(XPEvent)
                    .filter(
                        XPEvent.user_id == user_id,
                        XPEvent.event_type == "SEARCH",
                        XPEvent.source_reference == source_ref,
                        XPEvent.created_at >= cutoff,
                    )
                    .first()
                )
                if recent_same:
                    return False

            # Rule 2: Daily cap of 100 XP from searches
            day_cutoff = now - timedelta(hours=24)
            daily_search_xp = (
                db.query(func.sum(XPEvent.xp_amount))
                .filter(
                    XPEvent.user_id == user_id,
                    XPEvent.event_type == "SEARCH",
                    XPEvent.created_at >= day_cutoff,
                )
                .scalar()
                or 0
            )
            if daily_search_xp >= 100:
                return False

        elif event_type in ("SAVE_DISCOVERY", "BUILD_SIMILAR"):
            # Max 1 award per source reference (e.g. steam_app_id)
            if source_ref:
                prior = (
                    db.query(XPEvent)
                    .filter(
                        XPEvent.user_id == user_id,
                        XPEvent.event_type == event_type,
                        XPEvent.source_reference == source_ref,
                    )
                    .first()
                )
                if prior:
                    return False

        elif event_type in ("COMPLETE_BUILD", "COMPLETE_CAMPAIGN"):
            # Max 1 award per build_id
            if source_ref:
                prior = (
                    db.query(XPEvent)
                    .filter(
                        XPEvent.user_id == user_id,
                        XPEvent.event_type.in_(("COMPLETE_BUILD", "COMPLETE_CAMPAIGN")),
                        XPEvent.source_reference == source_ref,
                    )
                    .first()
                )
                if prior:
                    return False

        elif event_type in ("PLAYTEST", "PLAYTEST_WIN"):
            # Max 1 per playtest session
            if source_ref:
                prior = (
                    db.query(XPEvent)
                    .filter(
                        XPEvent.user_id == user_id,
                        XPEvent.event_type == event_type,
                        XPEvent.source_reference == source_ref,
                    )
                    .first()
                )
                if prior:
                    return False

        elif event_type in ("IMPROVE_GAME", "AI_ANALYSIS"):
            # Max 1 award per session/version
            if source_ref:
                prior = (
                    db.query(XPEvent)
                    .filter(
                        XPEvent.user_id == user_id,
                        XPEvent.event_type == event_type,
                        XPEvent.source_reference == source_ref,
                    )
                    .first()
                )
                if prior:
                    return False

        elif event_type == "MILESTONE_UNLOCK":
            # Max 1 award per milestone key
            if source_ref:
                prior = (
                    db.query(XPEvent)
                    .filter(
                        XPEvent.user_id == user_id,
                        XPEvent.event_type == "MILESTONE_UNLOCK",
                        XPEvent.source_reference == source_ref,
                    )
                    .first()
                )
                if prior:
                    return False

        return True

    @classmethod
    def grant_xp(
        cls,
        db: Session,
        user_id: str,
        event_type: str,
        xp_amount: Optional[int] = None,
        source_ref: Optional[str] = None,
    ) -> Tuple[UserProgress, bool, int]:
        """
        Grant experience points to user if allowed by anti-spam policies.
        Uses atomic transactional updates to protect against concurrency issues.
        Returns (progress, did_level_up, granted_xp_amount).
        """
        amount = xp_amount if xp_amount is not None else DEFAULT_XP_AMOUNTS.get(event_type, 10)

        # Check anti-spam
        if not cls.check_anti_spam(db, user_id, event_type, source_ref):
            progress = cls.get_or_create_progress(db, user_id)
            return progress, False, 0

        # Ensure user progress row exists
        cls.get_or_create_progress(db, user_id)

        # Record discrete XP audit event
        event = XPEvent(
            user_id=user_id,
            event_type=event_type,
            xp_amount=amount,
            source_reference=source_ref[:255] if source_ref else None,
        )
        db.add(event)

        # Perform atomic database update on total_xp
        db.query(UserProgress).filter(UserProgress.user_id == user_id).update(
            {
                UserProgress.total_xp: UserProgress.total_xp + amount,
                UserProgress.updated_at: datetime.now(timezone.utc),
            },
            synchronize_session="fetch",
        )
        db.commit()

        # Refresh progress to inspect updated XP
        progress = cls.get_or_create_progress(db, user_id)
        old_level = progress.current_level
        new_level, _, _ = calculate_level_bounds(progress.total_xp)
        leveled_up = new_level > old_level

        if leveled_up:
            progress.current_level = new_level
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.level != new_level:
                user.level = new_level
            db.commit()
            db.refresh(progress)
            logger.info("User %s leveled up from %d to %d (total XP: %d)", user_id, old_level, new_level, progress.total_xp)

        return progress, leveled_up, amount

    @classmethod
    def unlock_milestone(
        cls,
        db: Session,
        user_id: str,
        milestone_key: str,
    ) -> Optional[UserMilestone]:
        """
        Idempotently unlock a milestone for a user.
        If milestone was not previously unlocked, records UserMilestone and grants XP bonus.
        Returns the UserMilestone object if newly unlocked, or None if already unlocked.
        """
        if milestone_key not in CANONICAL_MILESTONES:
            logger.warning("Attempted to unlock non-canonical milestone key: %s", milestone_key)
            return None

        # Check if already unlocked
        existing = (
            db.query(UserMilestone)
            .filter(UserMilestone.user_id == user_id, UserMilestone.milestone_key == milestone_key)
            .first()
        )
        if existing:
            return None

        spec = CANONICAL_MILESTONES[milestone_key]
        milestone = UserMilestone(
            user_id=user_id,
            milestone_key=milestone_key,
            title=spec["title"],
            description=spec["description"],
            icon=spec["icon"],
            unlocked_at=datetime.now(timezone.utc),
        )

        try:
            db.add(milestone)
            db.commit()
            db.refresh(milestone)
        except IntegrityError:
            db.rollback()
            return None

        # Grant milestone XP bonus
        xp_bonus = spec.get("xp_bonus", 0)
        if xp_bonus > 0:
            cls.grant_xp(
                db=db,
                user_id=user_id,
                event_type="MILESTONE_UNLOCK",
                xp_amount=xp_bonus,
                source_ref=milestone_key,
            )

        logger.info("User %s unlocked milestone: %s (+%d XP)", user_id, milestone_key, xp_bonus)
        return milestone

    @classmethod
    def evaluate_milestones(
        cls,
        db: Session,
        user_id: str,
        trigger_event: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[UserMilestone]:
        """
        Evaluate milestone criteria based on user actions and grant eligible milestones.
        """
        ctx = context or {}
        unlocked: List[UserMilestone] = []

        # 1. Project / Build Creation Milestones
        if trigger_event in ("COMPLETE_BUILD", "COMPLETE_CAMPAIGN"):
            # FIRST_BUILD: requires successful playable prototype creation
            m = cls.unlock_milestone(db, user_id, "FIRST_BUILD")
            if m:
                unlocked.append(m)

            # FIRST_CAMPAIGN: requires multi-level / campaign structure
            if ctx.get("is_campaign") or ctx.get("stages_count", 1) > 1 or ctx.get("phases_count", 0) > 1:
                m_camp = cls.unlock_milestone(db, user_id, "FIRST_CAMPAIGN")
                if m_camp:
                    unlocked.append(m_camp)

            # CREATOR_10: 10 distinct successful projects
            project_count = db.query(Project).filter(Project.user_id == user_id).count()
            if project_count >= 10:
                m_10 = cls.unlock_milestone(db, user_id, "CREATOR_10")
                if m_10:
                    unlocked.append(m_10)

        # 2. Playtest Milestones
        elif trigger_event in ("PLAYTEST", "PLAYTEST_WIN"):
            # FIRST_PLAYTEST: any completed playtest session
            m_pt = cls.unlock_milestone(db, user_id, "FIRST_PLAYTEST")
            if m_pt:
                unlocked.append(m_pt)

            # FIRST_WIN: won a generated game
            if trigger_event == "PLAYTEST_WIN" or ctx.get("outcome") == "WIN":
                m_win = cls.unlock_milestone(db, user_id, "FIRST_WIN")
                if m_win:
                    unlocked.append(m_win)

        # 3. AI Analysis & Improvement Milestones
        elif trigger_event in ("AI_ANALYSIS", "IMPROVE_GAME"):
            m_ai = cls.unlock_milestone(db, user_id, "FIRST_AI_ANALYSIS")
            if m_ai:
                unlocked.append(m_ai)

        # 4. Build Similar Milestone
        elif trigger_event == "BUILD_SIMILAR":
            m_sim = cls.unlock_milestone(db, user_id, "BUILD_SIMILAR_PRO")
            if m_sim:
                unlocked.append(m_sim)

        # 5. Genre Explorer: check if user has interacted across >= 3 distinct genres
        pref_count = (
            db.query(UserGenrePreference)
            .filter(UserGenrePreference.user_id == user_id, UserGenrePreference.score >= 1.0)
            .count()
        )
        if pref_count >= 3:
            m_genre = cls.unlock_milestone(db, user_id, "GENRE_EXPLORER")
            if m_genre:
                unlocked.append(m_genre)

        return unlocked

    @classmethod
    def get_progress_response(cls, db: Session, user_id: str) -> UserProgressResponse:
        """Construct full UserProgressResponse with calculated level bounds, creator title, milestones, and recent events."""
        progress = cls.get_or_create_progress(db, user_id)
        current_lvl, base_xp, next_xp = calculate_level_bounds(progress.total_xp)

        xp_into = progress.total_xp - base_xp
        span = next_xp - base_xp
        pct = round(min(100.0, max(0.0, (xp_into / span) * 100.0 if span > 0 else 100.0)), 1)
        needed = max(0, next_xp - progress.total_xp)
        title = get_creator_title(current_lvl)

        # Fetch unlocked milestones for this user
        unlocked_db = (
            db.query(UserMilestone)
            .filter(UserMilestone.user_id == user_id)
            .all()
        )
        unlocked_map = {m.milestone_key: m.unlocked_at for m in unlocked_db}

        # Build complete list of canonical milestones with unlock status
        milestone_items: List[MilestoneItem] = []
        for key, spec in CANONICAL_MILESTONES.items():
            is_unlocked = key in unlocked_map
            unlocked_at = unlocked_map.get(key)
            milestone_items.append(
                MilestoneItem(
                    milestone_key=key,
                    title=spec["title"],
                    description=spec["description"],
                    icon=spec["icon"],
                    xp_bonus=spec.get("xp_bonus", 0),
                    is_unlocked=is_unlocked,
                    unlocked_at=unlocked_at,
                )
            )

        # Fetch recent 10 events
        events = (
            db.query(XPEvent)
            .filter(XPEvent.user_id == user_id)
            .order_by(XPEvent.created_at.desc())
            .limit(10)
            .all()
        )

        event_items = [
            XPEventItem(
                id=e.id,
                event_type=e.event_type,
                xp_amount=e.xp_amount,
                source_reference=e.source_reference,
                created_at=e.created_at,
            )
            for e in events
        ]

        return UserProgressResponse(
            user_id=user_id,
            total_xp=progress.total_xp,
            current_level=current_lvl,
            creator_title=title,
            current_level_base_xp=base_xp,
            next_level_xp=next_xp,
            xp_into_level=xp_into,
            xp_needed_for_next=needed,
            progress_percentage=pct,
            milestones=milestone_items,
            unlocked_milestone_count=len(unlocked_map),
            total_milestone_count=len(CANONICAL_MILESTONES),
            recent_events=event_items,
        )


progression_service = ProgressionService()
