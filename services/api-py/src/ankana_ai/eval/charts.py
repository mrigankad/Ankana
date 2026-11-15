"""Reference charts for the eval (ported TS fixtures plus the Ananya demo chart)."""

from datetime import UTC, datetime
from functools import cache

from nakshatra_core.chart import compute_vedic_chart_artifact

# Fixed reference time so dasha-dependent answers are reproducible.
EVAL_NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)

CHART_INPUTS: dict[str, dict] = {
    "ananya-1995": {  # Ananya Sharma, demo chart (Pisces lagna)
        "birthDate": "1995-03-15", "birthTime": "06:42", "timezoneName": "Asia/Kolkata",
        "latitude": 25.3176, "longitude": 82.9739,
        "placeLabel": "Varanasi, Uttar Pradesh, India",
    },
    "raiganj-2003": {
        "birthDate": "2003-08-29", "birthTime": "12:22", "timezoneName": "Asia/Kolkata",
        "latitude": 25.6167, "longitude": 88.1233,
        "placeLabel": "Raiganj, Uttar Dinajpur, West Bengal, India",
    },
    "varanasi-1990": {
        "birthDate": "1990-01-01", "birthTime": "10:30", "timezoneName": "Asia/Kolkata",
        "latitude": 25.3176, "longitude": 82.9739, "placeLabel": "Varanasi, India",
    },
    "newyork-1985": {
        "birthDate": "1985-06-15", "birthTime": "23:45", "timezoneName": "America/New_York",
        "latitude": 40.7128, "longitude": -74.006, "placeLabel": "New York, USA",
    },
}


@cache
def chart_artifact(chart_id: str) -> dict:
    return compute_vedic_chart_artifact(CHART_INPUTS[chart_id])
