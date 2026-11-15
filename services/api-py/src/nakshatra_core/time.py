"""Birth time handling: local wall-clock -> UTC instant -> Julian day.

Port of packages/astrology-core/src/time.ts.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def to_utc_datetime(birth_date: str, birth_time: str, timezone_name: str) -> datetime:
    year, month, day = (int(part) for part in birth_date.split("-"))
    hour, minute = (int(part) for part in birth_time.split(":"))
    local = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(timezone_name))
    return local.astimezone(UTC)


def julian_day(dt: datetime) -> float:
    return dt.timestamp() / 86_400 + 2_440_587.5


def local_time_status(birth_date: str, birth_time: str, timezone_name: str) -> str:
    """"ok", "ambiguous" (wall time happens twice when clocks go back; the engine takes the
    first occurrence, fold=0) or "gap" (wall time never happened when clocks went forward)."""
    year, month, day = (int(part) for part in birth_date.split("-"))
    hour, minute = (int(part) for part in birth_time.split(":"))
    zone = ZoneInfo(timezone_name)
    naive = datetime(year, month, day, hour, minute)
    first, second = naive.replace(tzinfo=zone, fold=0), naive.replace(tzinfo=zone, fold=1)
    if first.utcoffset() == second.utcoffset():
        return "ok"
    back = first.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    return "ambiguous" if back == naive else "gap"
