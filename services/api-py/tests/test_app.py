from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())

RAIGANJ = {
    "birthDate": "2003-08-29",
    "birthTime": "12:22",
    "timezoneName": "Asia/Kolkata",
    "latitude": 25.6167,
    "longitude": 88.1233,
    "placeLabel": "Raiganj, Uttar Dinajpur, West Bengal, India",
}


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_compute_chart_returns_full_artifact() -> None:
    response = client.post("/api/v1/charts/compute", json=RAIGANJ)
    assert response.status_code == 200
    artifact = response.json()
    assert artifact["ascendant"]["signName"] == "Scorpio"
    assert artifact["ascendant"]["nakshatra"] == "Anuradha"
    assert len(artifact["planets"]) == 9
    assert len(artifact["yogas"]) == 28
    assert artifact["calculationMetadata"]["engineVersion"] == "py-1.0.0"


def test_reading_endpoint_returns_sectioned_report() -> None:
    response = client.post("/api/v1/charts/reading", json=RAIGANJ)
    assert response.status_code == 200
    body = response.json()
    assert body["artifact"]["ascendant"]["signName"] == "Scorpio"
    keys = [s["key"] for s in body["reading"]["sections"]]
    assert keys == [
        "lagna", "planets", "houses", "yogas", "dasha", "vargas", "panchang",
    ]


def test_predictions_endpoint_enriched() -> None:
    response = client.post("/api/v1/charts/predictions", json=RAIGANJ)
    assert response.status_code == 200
    predictions = response.json()["predictions"]
    assert predictions, "expected at least one prediction"
    for prediction in predictions:
        assert prediction["confidenceBand"] in ("low", "medium", "high")
        assert prediction["narrative"]
        assert prediction["evidence"]


def test_remedies_endpoint() -> None:
    response = client.post("/api/v1/charts/remedies", json=RAIGANJ)
    assert response.status_code == 200
    remedies = response.json()["remedies"]
    assert remedies
    kinds = {r["kind"] for r in remedies}
    assert kinds <= {"mantra", "daan", "fasting", "lifestyle", "gemstone", "rudraksha"}
    for remedy in remedies:
        if remedy["kind"] == "gemstone":
            assert remedy["cautions"], "gemstones must carry cautions"


def test_compute_chart_validates_input() -> None:
    response = client.post(
        "/api/v1/charts/compute", json={**RAIGANJ, "birthTime": "noon"}
    )
    assert response.status_code == 422
