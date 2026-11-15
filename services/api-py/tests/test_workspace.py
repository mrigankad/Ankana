from fastapi.testclient import TestClient

from app.db import make_engine
from app.main import create_app


def make_client() -> TestClient:
    return TestClient(create_app(engine=make_engine("sqlite://")))


BIRTH = {
    "birthDate": "2003-08-29",
    "birthTime": "12:22",
    "timezoneName": "Asia/Kolkata",
    "placeLabel": "Raiganj, West Bengal",
    "latitude": 25.6167,
    "longitude": 88.1233,
}


def _setup_job(client: TestClient) -> tuple[str, str, str]:
    created = client.post("/api/v1/clients", json={"fullName": "Test Person"})
    client_id = created.json()["client"]["id"]
    record = client.post(
        f"/api/v1/clients/{client_id}/birth-records", json=BIRTH
    ).json()["birthRecord"]
    job = client.post(
        "/api/v1/charts/generate",
        json={"clientId": client_id, "birthRecordId": record["id"]},
    ).json()["job"]
    return client_id, record["id"], job["id"]


def test_client_crud_and_chart_job_flow() -> None:
    client = make_client()
    client_id, record_id, job_id = _setup_job(client)

    assert client.get("/api/v1/clients").json()["clients"][0]["id"] == client_id
    detail = client.get(f"/api/v1/clients/{client_id}").json()
    assert detail["birthRecords"][0]["id"] == record_id

    job = client.get(f"/api/v1/charts/jobs/{job_id}").json()["job"]
    assert job["status"] == "completed"

    artifact_body = client.get(f"/api/v1/charts/jobs/{job_id}/artifact").json()
    assert artifact_body["artifact"]["ascendant"]["signName"] == "Scorpio"
    assert len(artifact_body["reading"]["sections"]) == 7

    predictions = client.get(
        f"/api/v1/charts/jobs/{job_id}/predictions"
    ).json()["predictions"]
    assert predictions and all("confidenceBand" in p for p in predictions)

    remedies = client.get(f"/api/v1/charts/jobs/{job_id}/remedies").json()["remedies"]
    assert remedies

    transits = client.get(
        f"/api/v1/charts/jobs/{job_id}/transits?date=2026-07-19T00:00:00Z"
    ).json()["transits"]
    assert len(transits["planets"]) == 9

    events = client.get("/api/v1/audit-events").json()["events"]
    actions = {e["action"] for e in events}
    assert {"client.created", "birthRecord.created", "chart.generated"} <= actions

    summary = client.get("/api/v1/dashboard/summary").json()
    assert summary["clients"] == 1 and summary["chartRequests"] == 1


def test_missing_resources_return_404() -> None:
    client = make_client()
    assert client.get("/api/v1/clients/cli_missing").status_code == 404
    assert client.get("/api/v1/charts/jobs/job_missing").status_code == 404
    assert client.get("/api/v1/charts/jobs/job_missing/artifact").status_code == 404
