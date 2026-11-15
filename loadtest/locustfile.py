"""Locust load test for the Ankana API (services/api-py).

Each virtual user is one practitioner with their own practice: sign in through the dev stub
issuer, then mix the flows a practice actually runs, weighted by how often they happen:

  list clients          GET  /v1/clients (and the blind-index email lookup)
  generate chart        new client + consent + birth record (setup, not timed) then the timed
                        POST /v1/clients/{id}/charts that computes a chart
  read chart tabs       GET  chart, predictions, remedies, transits, lal-kitab
  ask                   POST /v1/charts/{id}/ask (MockProvider, so no AI cost)
  create report         POST /v1/reports (202, enqueue; the worker renders)
  location search       GET  /v1/locations/search (public; the shared limiter answers 429
                        past 30 a minute per IP, which is expected and not an error here)

Environment (see loadtest/README.md):
  LT_STUB_KEY_FILE  PEM private key the API runs its dev stub with (AUTH_DEV_STUB_KEY_PEM)
  LT_SLO            "1" (default) to evaluate the SLOs when the run ends and set the exit code

SLOs (override with LT_SLO_CHART_P95_MS / LT_SLO_READ_P95_MS / LT_SLO_ERROR_PCT):
  chart generate p95 < 800 ms, read p95 < 200 ms, error rate < 0.5 %
Requests named "setup ..." (seeding data) are excluded from the SLO figures.
"""

from __future__ import annotations

import os
import random
import time
import uuid
from collections import defaultdict

import jwt
from locust import HttpUser, between, events, task

KEY = open(os.environ["LT_STUB_KEY_FILE"], encoding="utf-8").read() if os.getenv(
    "LT_STUB_KEY_FILE") else None
CHART_P95_MS = float(os.getenv("LT_SLO_CHART_P95_MS", "800"))
READ_P95_MS = float(os.getenv("LT_SLO_READ_P95_MS", "200"))
ERROR_PCT = float(os.getenv("LT_SLO_ERROR_PCT", "0.5"))

PLACES = [  # (label, lat, lon, tz): spread so charts differ
    ("Varanasi", 25.3176, 82.9739, "Asia/Kolkata"), ("Delhi", 28.6139, 77.209, "Asia/Kolkata"),
    ("Raiganj", 25.6167, 88.1233, "Asia/Kolkata"), ("Mumbai", 19.076, 72.8777, "Asia/Kolkata"),
    ("Chennai", 13.0827, 80.2707, "Asia/Kolkata"), ("Pune", 18.5204, 73.8567, "Asia/Kolkata"),
]
QUESTIONS = ["Where is my Moon?", "What is my ascendant?", "Which dasha is running now?",
             "Where is Saturn placed?"]

# response times in ms per SLO bucket, filled from the request event
samples: dict[str, list[float]] = defaultdict(list)
totals = {"requests": 0, "failures": 0}


def bucket(name: str) -> str | None:
    if name.startswith("setup"):
        return None
    if name.startswith("chart generate"):
        return "chart_generate"
    if name.startswith("chart read"):
        return "read"
    if name.startswith("clients list"):
        return "read"
    return "other"


@events.request.add_listener
def _collect(request_type, name, response_time, response_length, exception, **kw):
    b = bucket(name)
    if b is None:
        return
    totals["requests"] += 1
    if exception is not None:
        totals["failures"] += 1
    samples[b].append(response_time)


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


@events.quitting.add_listener
def _slo(environment, **kw):
    if os.getenv("LT_SLO", "1") != "1":
        return
    err = 100.0 * totals["failures"] / max(1, totals["requests"])
    rows = [
        ("chart generate p95 (ms)", pct(samples["chart_generate"], 0.95), CHART_P95_MS,
         pct(samples["chart_generate"], 0.95) < CHART_P95_MS),
        ("read p95 (ms)", pct(samples["read"], 0.95), READ_P95_MS,
         pct(samples["read"], 0.95) < READ_P95_MS),
        ("error rate (%)", err, ERROR_PCT, err < ERROR_PCT),
    ]
    print("\n=== SLO check (setup requests excluded) ===")
    for label, got, target, ok in rows:
        print(f"{label:28} {got:9.2f}  target < {target:<7} {'PASS' if ok else 'FAIL'}")
    print(f"chart generate n={len(samples['chart_generate'])} p50={pct(samples['chart_generate'], .5):.0f} "
          f"p99={pct(samples['chart_generate'], .99):.0f} | read n={len(samples['read'])} "
          f"p50={pct(samples['read'], .5):.0f} p99={pct(samples['read'], .99):.0f} | "
          f"other n={len(samples['other'])} p95={pct(samples['other'], .95):.0f}")
    if not all(r[3] for r in rows):
        environment.process_exit_code = 1


class Practitioner(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self) -> None:
        if KEY is None:
            raise RuntimeError("set LT_STUB_KEY_FILE to the PEM the API uses for its dev stub")
        subject = f"lt-{uuid.uuid4().hex[:12]}"
        now = int(time.time())
        token = jwt.encode(
            {"iss": "ankana-dev-stub", "aud": "ankana-api", "sub": subject,
             "email": f"{subject}@example.test", "iat": now, "exp": now + 7200},
            KEY, algorithm="RS256", headers={"kid": "dev-stub-fixed"})
        self.headers = {"Authorization": f"Bearer {token}"}
        r = self.client.post("/v1/practices", json={"name": f"Load {subject}"},
                             headers=self.headers, name="setup sign-in + practice")
        r.raise_for_status()
        self.headers["X-Practice-Id"] = r.json()["practice_id"]
        self.charts: list[tuple[str, str]] = []  # (client_id, chart_id)
        self.emails: list[str] = []
        for _ in range(3):
            self._seed_client(chart=True)

    # ------------------------------------------------------------------ helpers
    def _seed_client(self, chart: bool) -> tuple[str, str | None]:
        n = uuid.uuid4().hex[:8]
        email = f"c{n}@example.test"
        c = self.client.post("/v1/clients", headers=self.headers, name="setup client", json={
            "display_name": f"Client {n}", "contact_email": email, "contact_phone": "9" + "".join(random.choices("0123456789", k=9))})
        c.raise_for_status()
        cid = c.json()["client"]["id"]
        self.emails.append(email)
        for purpose in ("chart_compute", "ai_assistant"):
            self.client.post(f"/v1/clients/{cid}/consents", headers=self.headers,
                             name="setup consent", json={
                                 "purpose": purpose, "notice_version": "v1",
                                 "notice_text": "We process your chart.", "channel": "in_person"})
        place = random.choice(PLACES)
        self.client.post(f"/v1/clients/{cid}/birth-records", headers=self.headers,
                         name="setup birth record", json={
                             "birth_date": f"{random.randint(1950, 2005)}-"
                                           f"{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                             "birth_time": f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00",
                             "time_source": "certificate", "place_label": place[0],
                             "latitude": place[1], "longitude": place[2], "timezone_name": place[3]}
                         ).raise_for_status()
        if not chart:
            return cid, None
        ch = self.client.post(f"/v1/clients/{cid}/charts", headers=self.headers,
                              name="setup chart", json={})
        ch.raise_for_status()
        chart_id = ch.json()["chart"]["id"]
        self.charts.append((cid, chart_id))
        return cid, chart_id

    # -------------------------------------------------------------------- flows
    @task(5)
    def list_clients(self) -> None:
        self.client.get("/v1/clients?limit=20", headers=self.headers, name="clients list")
        if self.emails and random.random() < 0.3:
            self.client.get("/v1/clients", params={"email": random.choice(self.emails)},
                            headers=self.headers, name="clients list (email lookup)")

    @task(2)
    def generate_chart(self) -> None:
        cid, _ = self._seed_client(chart=False)
        r = self.client.post(f"/v1/clients/{cid}/charts", headers=self.headers, json={},
                             name="chart generate (new client)")
        if r.status_code == 201:
            self.charts.append((cid, r.json()["chart"]["id"]))

    @task(8)
    def read_chart_tabs(self) -> None:
        _, chart_id = random.choice(self.charts)
        for tab in ("", "/predictions", "/remedies", "/transits", "/lal-kitab"):
            self.client.get(f"/v1/charts/{chart_id}{tab}", headers=self.headers,
                            name=f"chart read{tab or ' (summary)'}")

    @task(2)
    def ask(self) -> None:
        _, chart_id = random.choice(self.charts)
        self.client.post(f"/v1/charts/{chart_id}/ask", headers=self.headers,
                         json={"question": random.choice(QUESTIONS)}, name="ask (mock provider)")

    @task(1)
    def create_report(self) -> None:
        _, chart_id = random.choice(self.charts)
        self.client.post("/v1/reports", headers=self.headers, json={"chart_id": chart_id},
                         name="report create")

    @task(1)
    def location_search(self) -> None:
        with self.client.get("/v1/locations/search", params={"q": "Varanasi"},
                             name="locations search (public)", catch_response=True) as r:
            if r.status_code in (200, 429):  # 429 = the shared limiter doing its job
                r.success()
