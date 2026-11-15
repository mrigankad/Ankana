# Load test

Locust script for the practitioner API. Flows, weights and SLOs are described at the top of
`locustfile.py`; results and the tuning they led to are in `docs/performance.md`.

```
pip install locust "pyjwt[crypto]"        # a separate venv is fine

# 1. Postgres + migrations
docker compose up -d postgres
cd services/api-py
export API_MIGRATION_URL=postgresql+psycopg://ankana:ankana_dev@localhost:5432/ankana
alembic upgrade head

# 2. A fixed dev-stub key, so several API workers accept the same tokens
python - <<'PY'
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
open("stub.pem", "wb").write(k.private_bytes(serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
PY

# 3. API (2 workers) and the job worker
export API_DATABASE_URL=postgresql+psycopg://ankana_app:ankana_app_dev@localhost:5432/ankana
export API_ENV=dev AUTH_DEV_STUB=1 AUTH_DEV_STUB_KEY_PEM="$(cat stub.pem)"
export ANKANA_EPHEMERIS=swiss ANKANA_AI_PROVIDER=mock REPORT_RENDERER=stub
export ANKANA_PLANS_FILE=../../loadtest/plans.json     # no plan quotas
uvicorn app.main:app --port 8765 --workers 2 &
python -m app.worker &

# 4. Load
cd ../../loadtest
LT_STUB_KEY_FILE=../services/api-py/stub.pem \
  locust -f locustfile.py --headless -u 30 -r 5 -t 120s --host http://127.0.0.1:8765 \
  --only-summary --csv out/run
```

The run ends with an SLO table and a non-zero exit code on any breach:

```
=== SLO check (setup requests excluded) ===
chart generate p95 (ms)         339.83  target < 800.0   PASS
read p95 (ms)                   189.37  target < 200.0   PASS
error rate (%)                    0.00  target < 0.5     PASS
```

Tuning: `LT_SLO_CHART_P95_MS`, `LT_SLO_READ_P95_MS`, `LT_SLO_ERROR_PCT`, `LT_SLO=0` to skip the check.

`/v1/locations/search` is public and limited to 30 requests a minute per caller by the shared
limiter, so most location requests in a run answer 429; the script treats that as success.
The dev stub is refused when `API_ENV=production`; this is a local and CI tool. Add `ANKANA_METRICS`
exporter settings (docs/operations.md) to watch the same run in Grafana or the Azure workbook.
