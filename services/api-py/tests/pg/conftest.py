"""Real-Postgres fixtures.

Two ways to get a database:
- API_TEST_ADMIN_URL=postgresql+psycopg://<superuser>:<pw>@host:port/postgres
  (e.g. the docker-compose service); a throwaway database is created in it.
- Otherwise testcontainers starts postgres:16-alpine (needs a running Docker).
If neither works the pg tests are skipped with a reason; nothing falls back to
SQLite because SQLite cannot prove RLS.
"""

import os
import uuid

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from alembic import command
from app.auth import StubIssuer
from app.main import create_app
from app.tenancy.rls import APP_ROLE
from app.tenancy.session import make_pg_engine

APP_PASSWORD = "app_test_pw"


@pytest.fixture(scope="session")
def admin_url():
    explicit = os.getenv("API_TEST_ADMIN_URL")
    if explicit:
        yield make_url(explicit)
        return
    try:
        from testcontainers.postgres import PostgresContainer

        container = PostgresContainer("postgres:16-alpine", driver="psycopg")
        container.start()
    except Exception as exc:  # docker missing or not running
        pytest.skip(f"no Postgres available (start Docker or set API_TEST_ADMIN_URL): {exc}")
    try:
        yield make_url(container.get_connection_url())
    finally:
        container.stop()


@pytest.fixture(scope="session")
def db_urls(admin_url: URL):
    """Create a fresh database, migrate it as owner, return (owner, app) URLs."""
    name = f"ankana_test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(admin_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        exists = c.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE})
        if not exists:
            c.execute(text(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}'"))
        else:
            c.execute(text(f"ALTER ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}'"))
        c.execute(text(f'CREATE DATABASE "{name}"'))
    owner_url = admin_url.set(database=name)
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
    cfg.set_main_option("script_location",
                        os.path.join(os.path.dirname(__file__), "..", "..", "alembic"))
    os.environ["API_MIGRATION_URL"] = owner_url.render_as_string(hide_password=False)
    command.upgrade(cfg, "head")
    app_url = owner_url.set(username=APP_ROLE, password=APP_PASSWORD)
    yield owner_url, app_url, cfg
    admin.dispose()


@pytest.fixture()
def make_scratch_db(admin_url: URL):
    """A throwaway migrated database at a given revision (for migration tests that must
    not disturb the shared session database). Returns (owner_url, alembic Config)."""
    made: list[str] = []
    saved = os.environ.get("API_MIGRATION_URL")
    admin = create_engine(admin_url.set(database="postgres"), isolation_level="AUTOCOMMIT")

    def _make(revision: str):
        name = f"ankana_scratch_{uuid.uuid4().hex[:8]}"
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{name}"'))
        made.append(name)
        url = admin_url.set(database=name)
        cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
        cfg.set_main_option("script_location",
                            os.path.join(os.path.dirname(__file__), "..", "..", "alembic"))
        os.environ["API_MIGRATION_URL"] = url.render_as_string(hide_password=False)
        command.upgrade(cfg, revision)
        return url, cfg

    yield _make
    if saved is not None:
        os.environ["API_MIGRATION_URL"] = saved
    with admin.connect() as c:
        for name in made:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="session")
def owner_engine(db_urls):
    engine = create_engine(db_urls[0])
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def app_engine(db_urls):
    """Engine connected as the RLS-bound app role (not superuser, not owner)."""
    engine = make_pg_engine(db_urls[1].render_as_string(hide_password=False))
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def stub() -> StubIssuer:
    return StubIssuer()


@pytest.fixture()
def api(app_engine, stub) -> TestClient:
    from app.db import make_engine

    app = create_app(engine=make_engine("sqlite://"), pg_engine=app_engine, verifier=stub)
    return TestClient(app)


@pytest.fixture()
def auth(stub):
    def _auth(subject, practice_id=None):
        token = stub.issue(subject, email=subject + "@example.test")
        headers = {"Authorization": "Bearer " + token}
        if practice_id:
            headers["X-Practice-Id"] = practice_id
        return headers

    return _auth


@pytest.fixture()
def make_practice(api, auth):
    """Create a practice with a fresh owner user; returns (practice_id, subject)."""

    def _make(name: str = "Test Practice") -> tuple[str, str]:
        subject = f"user-{uuid.uuid4().hex[:10]}"
        r = api.post("/v1/practices", json={"name": name}, headers=auth(subject))
        assert r.status_code == 201, r.text
        return r.json()["practice_id"], subject

    return _make
