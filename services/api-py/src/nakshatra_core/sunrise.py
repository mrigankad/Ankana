"""Sunrise/sunset search via Astronomy Engine.

The vara (weekday) runs sunrise to sunrise in the panchang; the TS engine
documents calendar-weekday as a v1 approximation. Here we find the last
sunrise at or before birth so pre-dawn births get the previous vara.
"""

from datetime import UTC, datetime, timedelta

from astronomy import Body, Direction, Observer, SearchRiseSet

from .time import julian_day


def _astro_time(dt: datetime):
    from astronomy import Time

    return Time(julian_day(dt) - 2_451_545.0)


def _to_datetime(time) -> datetime:
    # astronomy.Time.ut is days since J2000 UT.
    # epoch + timedelta: fromtimestamp() fails on Windows for pre-1970 instants
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
        days=time.ut + 2_451_545.0 - 2_440_587.5
    )


def last_sunrise_and_next_sunset(
    birth_utc: datetime, latitude: float, longitude: float
) -> tuple[datetime, datetime]:
    """Return (last sunrise <= birth, first sunset after that sunrise)."""
    observer = Observer(latitude, longitude, 0.0)
    search_start = birth_utc - timedelta(hours=30)

    sunrise = None
    cursor = search_start
    for _ in range(4):
        found = SearchRiseSet(
            Body.Sun, observer, Direction.Rise, _astro_time(cursor), 2.0
        )
        if found is None:
            break
        found_dt = _to_datetime(found)
        if found_dt > birth_utc:
            break
        sunrise = found_dt
        cursor = found_dt + timedelta(minutes=1)

    if sunrise is None:  # polar edge case: fall back to calendar midnight
        sunrise = birth_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    sunset_time = SearchRiseSet(
        Body.Sun, observer, Direction.Set, _astro_time(sunrise), 2.0
    )
    sunset = (
        _to_datetime(sunset_time)
        if sunset_time is not None
        else sunrise + timedelta(hours=12)
    )
    return sunrise, sunset
