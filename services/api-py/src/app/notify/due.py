"""Pure time maths for reminders: practice-local dates, send times, quiet hours.

Everything takes an explicit `now` (aware UTC) so tests can pin time. Zones come from
IANA names via zoneinfo, so DST is handled by the tz database: a local "08:00" is a
different UTC instant before and after a transition, and a wall time that does not
exist (spring-forward gap) resolves to the first valid instant after the gap.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ = "Asia/Kolkata"
ENDING_SOON_DAYS_LEFT = 3  # day 40 of a 43 day cycle


def zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TZ)


def local_today(now: datetime, tz: str | None) -> date:
    return now.astimezone(zone(tz)).date()


def at_local(day: date, hour: int, tz: str | None, minute: int = 0) -> datetime:
    """UTC instant of `day hour:minute` on the practice's wall clock."""
    z = zone(tz)
    wall = datetime(day.year, day.month, day.day, hour, minute, tzinfo=z)
    # Round-trip through UTC so a non-existent wall time normalises to a valid one.
    return wall.astimezone(UTC).astimezone(z).astimezone(UTC)


def in_quiet_hours(t: time, start: time, end: time) -> bool:
    """Window [start, end); wraps midnight when start > end; empty when equal."""
    if start == end:
        return False
    if start < end:
        return start <= t < end
    return t >= start or t < end


def apply_quiet_hours(when: datetime, tz: str | None, start: time, end: time) -> datetime:
    """Push `when` to the end of the quiet window if it falls inside one."""
    z = zone(tz)
    local = when.astimezone(z)
    if not in_quiet_hours(local.time(), start, end):
        return when
    day = local.date()
    if start > end and local.time() >= start:  # evening part of a wrapping window
        day += timedelta(days=1)
    return at_local(day, end.hour, tz, end.minute)


def schedule_time(now: datetime, day: date, tz: str | None, hour: int, quiet_start: time,
                  quiet_end: time) -> tuple[datetime, str | None]:
    """When to send a notification belonging to local date `day`.

    Returns (run_at, skip_reason). Target is `hour:00` local, or now if that has passed;
    quiet hours push it later; if that lands on another local date the message is stale
    and the reason is 'quiet_hours'.
    """
    target = max(now, at_local(day, hour, tz))
    run_at = apply_quiet_hours(target, tz, quiet_start, quiet_end)
    if run_at.astimezone(zone(tz)).date() != day:
        return run_at, "quiet_hours"
    return run_at, None


def cycle_end(start: date, cycle_days: int) -> date:
    return start + timedelta(days=cycle_days - 1)


def day_number(start: date, today: date) -> int:
    return (today - start).days + 1
