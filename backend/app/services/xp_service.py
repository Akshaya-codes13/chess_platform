"""XP and badge rules shared by the seed script and the API.

* A student earns ``PUZZLE_SOLVED_XP`` the first time they solve a puzzle.
  Re-solving a puzzle they have already solved earns nothing.
* Badges are earned when a ``StudentProgress`` counter reaches the threshold
  in ``BADGE_REQUIREMENTS``; each badge is awarded once and grants its
  ``xp_reward`` once.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Badge, StudentBadge, StudentProgress, Submission, XPEvent

PUZZLE_SOLVED_XP = 10

# Granted once per assignment, when the student solves its last puzzle.
ASSIGNMENT_COMPLETED_XP = 25

GAME_RESULT_XP = {"win": 15, "draw": 10, "loss": 5}

# Badge code -> (progress counter, threshold) required to earn it. Counters
# are StudentProgress columns, except ``assignments_completed``, which is the
# student's number of assignment submissions.
BADGE_REQUIREMENTS = {
    "first-puzzle-solved": ("puzzles_solved", 1),
    "three-puzzles-solved": ("puzzles_solved", 3),
    "first-game-played": ("games_played", 1),
    "first-assignment-completed": ("assignments_completed", 1),
    "five-assignments-completed": ("assignments_completed", 5),
}

# Total XP needed to reach each level, starting at level 1. Beyond the table
# every further level costs LEVEL_STEP_XP more.
LEVEL_THRESHOLDS = (0, 50, 150, 300, 500, 750, 1050, 1400, 1800, 2250)
LEVEL_STEP_XP = 500


def _level_start(level: int) -> int:
    if level <= len(LEVEL_THRESHOLDS):
        return LEVEL_THRESHOLDS[level - 1]
    return LEVEL_THRESHOLDS[-1] + (level - len(LEVEL_THRESHOLDS)) * LEVEL_STEP_XP


def level_for_xp(total_xp: int) -> dict:
    """Describe the XP level reached with ``total_xp``."""
    total_xp = max(total_xp, 0)
    level = 1

    while _level_start(level + 1) <= total_xp:
        level += 1

    start, end = _level_start(level), _level_start(level + 1)

    return {
        "level": level,
        "total_xp": total_xp,
        "level_start_xp": start,
        "next_level_xp": end,
        "xp_into_level": total_xp - start,
        "xp_to_next_level": end - total_xp,
        "progress_percent": round((total_xp - start) / (end - start) * 100, 1),
    }


def badge_counters(db: Session, progress: StudentProgress) -> dict:
    """The values every badge requirement is measured against."""
    completed = db.scalar(
        select(func.count(func.distinct(Submission.assignment_id))).where(
            Submission.student_id == progress.student_id
        )
    ) or 0

    return {
        "puzzles_solved": progress.puzzles_solved,
        "games_played": progress.games_played,
        "assignments_completed": completed,
    }


def add_xp_event(
    db: Session,
    student_id: uuid.UUID,
    points: int,
    reason: str,
    source_type: str,
    source_id: uuid.UUID,
    created_at: datetime | None = None,
) -> XPEvent | None:
    """Record an XP event once per (student, source); return None if it exists."""
    existing = db.scalar(
        select(XPEvent.id).where(
            XPEvent.student_id == student_id,
            XPEvent.source_type == source_type,
            XPEvent.source_id == source_id,
        )
    )

    if existing is not None:
        return None

    event = XPEvent(
        student_id=student_id,
        points=points,
        reason=reason,
        source_type=source_type,
        source_id=source_id,
    )

    if created_at is not None:
        event.created_at = created_at

    db.add(event)
    return event


def award_earned_badges(
    db: Session,
    progress: StudentProgress,
    earned_at: datetime,
) -> list[tuple[Badge, XPEvent | None]]:
    """Award every badge whose threshold the progress counters now meet."""
    owned = set(
        db.scalars(
            select(StudentBadge.badge_id).where(
                StudentBadge.student_id == progress.student_id
            )
        )
    )
    badges = db.scalars(
        select(Badge).where(Badge.code.in_(list(BADGE_REQUIREMENTS)))
    ).all()
    counters = badge_counters(db, progress)

    awarded = []

    for badge in badges:
        counter, threshold = BADGE_REQUIREMENTS[badge.code]

        if badge.id in owned or counters[counter] < threshold:
            continue

        db.add(
            StudentBadge(
                student_id=progress.student_id,
                badge_id=badge.id,
                earned_at=earned_at,
            )
        )

        event = None

        if badge.xp_reward:
            event = add_xp_event(
                db,
                progress.student_id,
                badge.xp_reward,
                f"Earned badge {badge.name}",
                "badge",
                badge.id,
                earned_at,
            )

        awarded.append((badge, event))

    return awarded


def next_milestone(progress_values: dict, owned_codes: set, badges: list[Badge]):
    """Return the unearned badge with the most progress made, or None.

    Ranked by the fraction already reached, then by steps remaining, so a
    badge the student has started beats one they have not.
    """
    candidates = []

    for badge in badges:
        requirement = BADGE_REQUIREMENTS.get(badge.code)

        if requirement is None or badge.code in owned_codes:
            continue

        counter, threshold = requirement
        current = min(progress_values.get(counter, 0), threshold)
        candidates.append((badge, counter, current, threshold))

    if not candidates:
        return None

    badge, counter, current, threshold = min(
        candidates,
        key=lambda item: (
            -item[2] / item[3],
            item[3] - item[2],
            item[1] != "puzzles_solved",
            item[0].name,
        ),
    )

    return {
        "badge_code": badge.code,
        "badge_name": badge.name,
        "description": badge.description,
        "counter": counter,
        "current": current,
        "target": threshold,
    }
