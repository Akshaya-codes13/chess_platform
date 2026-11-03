from datetime import date, datetime, timedelta, timezone


def activity_date(value: datetime) -> date:
    """Activity days are UTC calendar days."""
    return value.astimezone(timezone.utc).date()


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def calculate_streaks(dates) -> tuple[int, int]:
    """Return (current, longest) runs of consecutive activity days.

    The current streak is the run ending on the most recent activity day.
    """
    current = longest = 0
    previous = None

    for day in sorted(dates):
        if previous is not None and day - previous == timedelta(days=1):
            current += 1
        else:
            current = 1

        longest = max(longest, current)
        previous = day

    return current, longest


def active_streak(dates, today: date | None = None) -> int:
    """Current streak as of ``today``.

    A run still counts while its last day is today or yesterday; after a
    missed day the streak is broken and reported as zero.
    """
    dates = sorted(set(dates))

    if not dates:
        return 0

    today = today or today_utc()

    if dates[-1] < today - timedelta(days=1):
        return 0

    current, _ = calculate_streaks(dates)
    return current
