"""Location search: Nominatim geocoding with offline static fallback.

Port of apps/api/src/modules/locations. Nominatim usage policy requires a
descriptive User-Agent and at most one request per second, which interactive
practitioner searches stay well under.
"""

import httpx
from fastapi import APIRouter, Depends, Query
from tzfpy import get_tz

from .ratelimit import SharedRateLimiter, limit_dependency

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

_LOCATION_FIXTURES = [
    {
        "providerPlaceId": "geo_varanasi_in",
        "displayName": "Varanasi, Uttar Pradesh, India",
        "latitude": 25.3176,
        "longitude": 82.9739,
        "timezoneName": "Asia/Kolkata",
        "confidence": "high",
        "countryCode": "IN",
    },
    {
        "providerPlaceId": "geo_delhi_in",
        "displayName": "Delhi, India",
        "latitude": 28.6139,
        "longitude": 77.209,
        "timezoneName": "Asia/Kolkata",
        "confidence": "high",
        "countryCode": "IN",
    },
    {
        "providerPlaceId": "geo_raiganj_in",
        "displayName": "Raiganj, Uttar Dinajpur, West Bengal, India",
        "latitude": 25.6167,
        "longitude": 88.1233,
        "timezoneName": "Asia/Kolkata",
        "confidence": "high",
        "countryCode": "IN",
    },
]

_QUERY_ALIASES = {"banaras": "varanasi", "benares": "varanasi", "kashi": "varanasi",
                  "up": "uttar pradesh"}


def _normalize_query(query: str) -> str:
    tokens = []
    for part in query.strip().lower().split(","):
        for token in part.strip().split():
            tokens.append(_QUERY_ALIASES.get(token, token))
    return " ".join(tokens)


def search_offline(query: str, preferred_country_code: str | None = None) -> list[dict]:
    normalized = _normalize_query(query)
    results = []
    for location in _LOCATION_FIXTURES:
        if preferred_country_code and location["countryCode"] != preferred_country_code:
            continue
        haystack = (
            f"{location['displayName'].lower()} "
            f"{(location['countryCode'] or '').lower()}"
        )
        if all(token in haystack for token in normalized.split()):
            results.append(location)
    return results


def _confidence(importance: float) -> str:
    if importance > 0.5:
        return "high"
    if importance > 0.3:
        return "medium"
    return "low"


def search_nominatim(
    query: str,
    preferred_country_code: str | None = None,
    client: httpx.Client | None = None,
) -> list[dict]:
    params = {"q": query, "format": "jsonv2", "addressdetails": "1", "limit": "6"}
    if preferred_country_code:
        params["countrycodes"] = preferred_country_code.lower()
    http = client or httpx.Client(timeout=5)
    try:
        response = http.get(
            NOMINATIM_URL,
            params=params,
            headers={
                "User-Agent": "Nakshatra-Astrology-Platform/0.1 (practitioner geocoding)",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        places = response.json()
    finally:
        if client is None:
            http.close()

    results = []
    for place in places:
        latitude = float(place["lat"])
        longitude = float(place["lon"])
        country = (place.get("address") or {}).get("country_code")
        results.append(
            {
                "providerPlaceId": f"osm_{place['place_id']}",
                "displayName": place["display_name"],
                "latitude": latitude,
                "longitude": longitude,
                # tzfpy takes (lon, lat)
                "timezoneName": get_tz(longitude, latitude),
                "confidence": _confidence(place.get("importance") or 0),
                "countryCode": country.upper() if country else None,
            }
        )
    return results


def search_locations(
    query: str,
    preferred_country_code: str | None = None,
    client: httpx.Client | None = None,
) -> dict:
    try:
        results = search_nominatim(query, preferred_country_code, client)
        return {"results": results, "provider": "nominatim"}
    except (httpx.HTTPError, KeyError, ValueError):
        return {
            "results": search_offline(query, preferred_country_code),
            "provider": "offline-fallback",
        }


# Public and unauthenticated, and it proxies to Nominatim (usage policy: one request a
# second for the whole deployment), so it is limited per caller in the shared store.
SEARCH_LIMIT = SharedRateLimiter("locations_search", 30, 60)
PUBLIC_READ_LIMIT = SharedRateLimiter("public_read", 120, 60)


def build_locations_router(client: httpx.Client | None = None) -> APIRouter:
    """Mounted at /v1 and, for older web builds, /api/v1 (see app.main)."""
    router = APIRouter(dependencies=[Depends(limit_dependency(SEARCH_LIMIT))])

    @router.get("/locations/search", operation_id="searchLocations", tags=["locations"],
                summary="Place search for birth places (rate limited per caller)")
    def locations_search(q: str = Query(min_length=1, max_length=200),
                         countryCode: str | None = Query(default=None, max_length=2)) -> dict:
        return search_locations(q, countryCode, client)

    return router
