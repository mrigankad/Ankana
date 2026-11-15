import httpx

from app.locations import search_locations, search_offline


class _FailingClient(httpx.Client):
    def get(self, *args, **kwargs):  # type: ignore[override]
        raise httpx.ConnectError("offline")


class _StubClient(httpx.Client):
    def get(self, *args, **kwargs):  # type: ignore[override]
        return httpx.Response(
            200,
            json=[
                {
                    "place_id": 12345,
                    "display_name": "Raiganj, Uttar Dinajpur, West Bengal, India",
                    "lat": "25.6167",
                    "lon": "88.1233",
                    "importance": 0.62,
                    "address": {"country_code": "in"},
                }
            ],
            request=httpx.Request("GET", "https://nominatim.test"),
        )


def test_offline_fallback_matches_aliases() -> None:
    results = search_offline("kashi, up")
    assert results and results[0]["displayName"].startswith("Varanasi")


def test_search_falls_back_when_provider_fails() -> None:
    body = search_locations("raiganj", client=_FailingClient())
    assert body["provider"] == "offline-fallback"
    assert body["results"][0]["providerPlaceId"] == "geo_raiganj_in"


def test_search_maps_nominatim_results() -> None:
    body = search_locations("raiganj", client=_StubClient())
    assert body["provider"] == "nominatim"
    result = body["results"][0]
    assert result["providerPlaceId"] == "osm_12345"
    assert result["timezoneName"] == "Asia/Kolkata"
    assert result["confidence"] == "high"
    assert result["countryCode"] == "IN"
