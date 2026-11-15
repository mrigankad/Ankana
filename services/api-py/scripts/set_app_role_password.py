"""Set the LOGIN password of the RLS-bound app role after migrations.

Runs in the migration job as the owner role. The migration creates ankana_app
as NOLOGIN; this gives it the password the apps connect with (from Key Vault).
Env: API_MIGRATION_URL (owner), APP_ROLE_PASSWORD.
"""

import os
import sys

from sqlalchemy import create_engine, text

APP_ROLE = "ankana_app"


def main() -> int:
    url = os.environ.get("API_MIGRATION_URL")
    password = os.environ.get("APP_ROLE_PASSWORD")
    if not url or not password:
        print("API_MIGRATION_URL and APP_ROLE_PASSWORD are required", file=sys.stderr)
        return 2
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        # Identifiers cannot be bound; the role name is a constant, the password is quoted.
        quoted = password.replace("'", "''")
        conn.execute(text(f"ALTER ROLE {APP_ROLE} LOGIN PASSWORD '{quoted}'"))
    print(f"{APP_ROLE}: login password set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
