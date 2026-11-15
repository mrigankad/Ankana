from nakshatra_core.time import julian_day, to_utc_datetime


def test_julian_day_matches_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        meta = chart["artifact"]["calculationMetadata"]
        inp = chart["input"]
        dt = to_utc_datetime(inp["birthDate"], inp["birthTime"], inp["timezoneName"])
        assert abs(julian_day(dt) - meta["julianDay"]) < 1e-6, chart["label"]


def test_utc_iso_matches_golden(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        meta = chart["artifact"]["calculationMetadata"]
        inp = chart["input"]
        dt = to_utc_datetime(inp["birthDate"], inp["birthTime"], inp["timezoneName"])
        iso = dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"
        assert iso == meta["utcDateTime"], chart["label"]


def test_local_time_status_flags_dst_gaps_and_folds() -> None:
    from nakshatra_core.time import local_time_status as st

    assert st("2024-03-10", "02:30", "America/New_York") == "gap"       # spring forward
    assert st("2024-11-03", "01:30", "America/New_York") == "ambiguous"  # fall back
    assert st("2024-06-01", "12:00", "America/New_York") == "ok"
    assert st("1990-05-15", "10:30", "Asia/Kolkata") == "ok"
    assert st("2024-11-03", "03:00", "America/New_York") == "ok"
