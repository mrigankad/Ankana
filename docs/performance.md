# Performance and load testing

Scripts: `loadtest/` (Locust). Targets (SLOs) for the practitioner API:

| Flow | Target |
|---|---|
| Generate a chart (new birth record, computed) | p95 < 800 ms |
| Reads (client list, chart summary and tabs) | p95 < 200 ms |
| Errors (any 5xx or failed request, setup excluded) | < 0.5 % |

`loadtest/locustfile.py` checks all three when a run ends and exits non-zero on a breach, so it can
gate a pipeline. Setup requests (seeding clients and charts) are excluded from the figures.

## How the numbers below were taken

One Windows laptop (Ryzen 5 5600H, 12 threads, 31 GB), so the load generator, Postgres, both API
workers and the job worker all compete for the same CPU. That makes the figures pessimistic for the
API and unrepresentative of Azure, but they are repeatable and good for before/after comparisons.

- Postgres 16 from `docker-compose.yml` (Docker Desktop), migrated to head (0008), empty database.
- API: `uvicorn app.main:app --workers 2`, `API_ENV=dev`, `AUTH_DEV_STUB=1` with a fixed stub key
  (`AUTH_DEV_STUB_KEY_PEM`, so both workers accept the same tokens), `ANKANA_EPHEMERIS=swiss`,
  `ANKANA_AI_PROVIDER=mock`, `REPORT_RENDERER=stub`, plans from `loadtest/plans.json` (no quotas).
- Worker: `python -m app.worker` (drains the report jobs; all 148 report jobs finished `done`).
- Load: 30 virtual users, ramp 5 per second, 120 seconds, wait 0.2 to 1.0 s between tasks. Each user
  is a practitioner with their own practice and seeded clients. Mix per user, by weight: read chart
  tabs 8, list clients 5, generate chart 2, ask 2, create report 1, location search 1.

Reproduce: `loadtest/README.md`.

## Results

First run (code as merged before this work):

| | requests | p50 | p95 | p99 | failures |
|---|---|---|---|---|---|
| chart generate (new client) | 196 | 550 ms | 910 ms | 1600 ms | 0 |
| reads (list + chart tabs, 4589 requests) | 4589 | 293 ms | 596 ms | 817 ms | 0 |
| all requests | 6427 | 320 ms | 710 ms | 1100 ms | 0 |

Throughput 54.6 requests per second. Both latency SLOs failed, because the two API workers were CPU
bound: even a trivial read waited behind heavier requests.

After fixing the two hotspots below (same data, same run, same machine):

| | requests | p50 | p95 | p99 | failures |
|---|---|---|---|---|---|
| chart generate (new client) | 399 | 192 ms | **340 ms** | 411 ms | 0 |
| reads (list + chart tabs, 8996 requests) | 8996 | 71 ms | **189 ms** | 280 ms | 0 |
| ask (mock provider) | 400 | 99 ms | 260 ms | | 0 |
| report create (enqueue) | 200 | 120 ms | 310 ms | | 0 |
| all requests | 12264 | 78 ms | 240 ms | 390 ms | **0 (0.00 %)** |

Throughput 102.8 requests per second (1.9x). All three SLOs pass, the read figure narrowly (189 vs
200 ms), so keep an eye on it on real hardware.

Per endpoint, before and after (p50 / p95 in ms):

| endpoint | before | after |
|---|---|---|
| chart read (summary) | 310 / 630 | 77 / 210 |
| chart read predictions | 320 / 610 | 72 / 190 |
| chart read transits | 280 / 570 | 68 / 180 |
| chart read remedies | 280 / 590 | 70 / 180 |
| chart read lal-kitab | 280 / 560 | 72 / 190 |
| clients list | 280 / 600 | 65 / 200 |
| clients list (email lookup) | 280 / 570 | 64 / 220 |
| chart generate | 550 / 910 | 190 / 340 |
| ask (mock) | 430 / 760 | 99 / 260 |
| report create | 480 / 840 | 120 / 310 |

Unloaded (3 users, warm): reads 18 to 33 ms mean, chart generate 87 ms, ask 39 ms, report create 41 ms.

`/v1/locations/search` shows high p95 here because Nominatim is unreachable from the test machine
and each call waits for the offline fallback; it is rate limited (30 a minute per caller, see
`docs/security-review.md` D2) and is not part of the read SLO.

## Hotspots found and fixed

Profile: the API under the same load with `yappi` (CPU clock), plus the Postgres statement log for
statements per request.

1. **Predictions recomputed nine planets per dasha window.** `GET /charts/{id}/predictions` asks, for
   every antardasha window in the horizon, only "is Saturn in Sade Sati at the midpoint", but called
   `compute_transit_snapshot`, which computes all nine bodies and a retrograde probe (two more
   Astronomy Engine evaluations) for each of them. That was about 36 % of endpoint CPU for about 10 %
   of the calls. Fix: `nakshatra_core.transits.sade_sati_active` uses Saturn alone and gives the same
   answer (tested against the full snapshot over twelve years of dates for four golden charts, both
   outcomes seen); `tropical_longitude` and `is_retrograde` are memoised per instant, and
   `GET /charts/{id}/transits` rounds "now" to the minute so concurrent callers share one snapshot.
   Tests: `tests/test_transits.py` (shortcut equals the snapshot, cache hits), existing transit and
   rule goldens unchanged.
2. **Three pool checkouts per authenticated request.** Every request looked the user up in one
   transaction, read memberships in a second, and ran the route in a third. Each checkout costs a
   ping (`pool_pre_ping`), BEGIN and COMMIT round trip, which on a managed Postgres is the dominant
   cost of a small read (about 14 round trips per read, from the statement log). Fix: user lookup and
   `app_memberships` share one transaction and the request reuses the result
   (`app.auth.deps.upsert_user(..., memberships_out)`), so a read takes two checkouts. No staleness
   is introduced: nothing is cached across requests. Tests: `tests/pg/test_perf.py` asserts two
   checkouts and a single `app_memberships` call per request.

I did not isolate the effect of each fix; the combined effect is the table above. Not touched, worth
knowing: FastAPI route matching costs about 7 ms of CPU per request (`_IncludedRouter._match`, nine
candidates each) and the built-in session check adds a transaction per request for built-in tokens.

Checked and fine: the database connection pool (35 new sessions for 905 requests), statements per
request (about 4 real statements for a chart read), no N+1 in the list or read paths.

## Running against a deployed environment

Point `--host` at the staging URL, run with a real practice (`AUTH_DEV_STUB` is refused in
production, so use the built-in sign-in and put a bearer token in the script instead of minting a
stub one) and keep `-u` small; staging is not sized for the local figures. Record results under a new
heading here with the commit and date.
