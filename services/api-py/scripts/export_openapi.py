"""Write the OpenAPI document to services/api-py/openapi.json.

    python scripts/export_openapi.py [--check]

--check exits 1 if the committed file is stale (for CI). Needs no database:
the app is built with a stub verifier and a lazy Postgres engine.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from app.auth import StubIssuer  # noqa: E402
from app.db import make_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.tenancy.session import make_pg_engine  # noqa: E402


def build() -> str:
    pg = make_pg_engine("postgresql+psycopg://x:x@localhost/none")  # never connects
    app = create_app(engine=make_engine("sqlite://"), pg_engine=pg, verifier=StubIssuer())
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    out = ROOT / "openapi.json"
    text = build()
    if "--check" in sys.argv:
        sys.exit(0 if out.exists() and out.read_text(encoding="utf8") == text else 1)
    out.write_text(text, encoding="utf8")
    print(f"wrote {out}")
