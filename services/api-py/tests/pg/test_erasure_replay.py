"""Backup/restore with erasure replay.

A restore is simulated the way point-in-time restore behaves: a copy of the database taken
at time T (CREATE DATABASE ... TEMPLATE) is what comes back after the live database has moved
on. Erasures that happened after T must be re-applied from the durable log (object storage),
including a client that was under legal hold in the backup."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from app.privacy import cli, erasure_log, service
from app.privacy.erasure_log import Event
from app.storage import LocalStorage
from app.tenancy.models import BirthRecord, Client, TimeSource
from app.tenancy.rls import APP_ROLE
from app.tenancy.session import make_pg_engine, tenant_session

pytestmark = pytest.mark.pg

APP_PASSWORD = "app_test_pw"


def _copy_db(admin_url, source, name):
    admin = create_engine(admin_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                       "WHERE datname = :d AND pid <> pg_backend_pid()"), {"d": source})
        c.execute(text(f'CREATE DATABASE "{name}" TEMPLATE "{source}"'))
    admin.dispose()


def _app_engine(owner_url):
    url = owner_url.set(username=APP_ROLE, password=APP_PASSWORD)
    return make_pg_engine(url.render_as_string(hide_password=False))


def _add_client(engine, pid, name, email):
    from datetime import date, time

    with tenant_session(engine, pid) as db:
        c = Client(practice_id=pid, display_name=name, contact_email=email)
        db.add(c)
        db.flush()
        db.add(BirthRecord(practice_id=pid, client_id=c.id, birth_date=date(1990, 1, 1),
                           birth_time=time(6, 0), time_source=TimeSource.certificate,
                           place_label="Varanasi", latitude=25.3, longitude=82.97,
                           timezone_name="Asia/Kolkata"))
        return str(c.id)


def _client_state(engine, pid, cid):
    with tenant_session(engine, pid) as db:
        c = db.get(Client, cid)
        births = db.scalar(text("SELECT count(*) FROM birth_record WHERE client_id = :c"),
                           {"c": cid})
        return c.display_name, c.contact_email, c.erased_at, c.legal_hold, births


@pytest.fixture()
def world(admin_url, db_urls, make_scratch_db, tmp_path, monkeypatch):
    owner_url, cfg = make_scratch_db("head")
    live_name = owner_url.database
    owner = create_engine(owner_url)
    p1, p2 = str(uuid.uuid4()), str(uuid.uuid4())
    with owner.begin() as c:
        c.execute(text("INSERT INTO practice (id, name) VALUES (:a,'Keep'), (:b,'Close')"),
                  {"a": p1, "b": p2})
    live = _app_engine(owner_url)
    storage = LocalStorage(tmp_path / "store", "k" * 32, "http://t")
    ids = {"x": _add_client(live, p1, "Asha X", "x@example.com"),
           "y": _add_client(live, p1, "Ravi Y", "y@example.com"),
           "z": _add_client(live, p2, "Meera Z", "z@example.com")}
    with tenant_session(live, p1) as db:  # X is under legal hold at backup time
        service.set_legal_hold(db, p1, db.get(Client, ids["x"]), True, "court order")
    backup_time = datetime.now(UTC)
    live.dispose()
    owner.dispose()
    _copy_db(admin_url, live_name, f"{live_name}_r1")
    _copy_db(admin_url, live_name, f"{live_name}_r2")
    live = _app_engine(owner_url)
    # ---- life goes on after the backup: hold released, X erased, practice 2 closed
    with tenant_session(live, p1) as db:
        service.set_legal_hold(db, p1, db.get(Client, ids["x"]), False, None)
        service.erase_client(db, p1, ids["x"], storage)
    with tenant_session(live, p2) as db:
        service.delete_practice(db, p2, storage)
    yield {"p1": p1, "p2": p2, "ids": ids, "storage": storage, "live": live,
           "owner_url": owner_url, "since": backup_time - timedelta(seconds=1),
           "r1": owner_url.set(database=f"{live_name}_r1"),
           "r2": owner_url.set(database=f"{live_name}_r2")}
    live.dispose()


def test_log_is_ids_only_and_in_storage_and_database(world):
    keys = world["storage"].list_keys(erasure_log.PREFIX)
    assert len(keys) == 3  # client X, client Z (practice deletion), practice 2
    blob = world["storage"].get(keys[0]).decode()
    assert "Asha" not in blob and "example.com" not in blob and "court" not in blob
    events = erasure_log.read_storage(world["storage"], world["since"])
    assert [e.kind for e in events].count("practice") == 1
    assert {e.event_id for e in events} == {
        e.event_id for e in erasure_log.read_db(world["live"], world["since"])}
    assert all(e.via in ("request", "practice_deletion") for e in events)


def test_restore_then_replay_leaves_erased_clients_erased(world):
    p1, p2, ids = world["p1"], world["p2"], world["ids"]
    restored = _app_engine(world["r1"])
    # the restored copy resurrected everything, including the held client and practice 2
    name, email, erased, hold, births = _client_state(restored, p1, ids["x"])
    assert (name, email, erased, hold, births) == ("Asha X", "x@example.com", None, True, 1)
    assert _client_state(restored, p2, ids["z"])[1] == "z@example.com"

    events = erasure_log.read_storage(world["storage"], world["since"])
    res = erasure_log.replay(restored, world["storage"], events)
    # practice 2's deletion also erased its client, so that client's own event finds it done
    assert (res["applied"], res["already_erased"]) == (2, 1)
    assert res["errors"] == 0 and res["unknown"] == 0, res

    name, email, erased, hold, births = _client_state(restored, p1, ids["x"])
    assert name == "Erased client" and email is None and erased is not None
    assert hold is False and births == 0  # hold overridden, data gone
    y = _client_state(restored, p1, ids["y"])
    assert y[:2] == ("Ravi Y", "y@example.com") and y[2] is None and y[4] == 1  # untouched
    z = _client_state(restored, p2, ids["z"])
    assert z[0] == "Erased client" and z[1] is None and z[4] == 0
    with tenant_session(restored, p2) as db:
        assert db.scalar(text("SELECT deleted_at IS NOT NULL FROM practice WHERE id = :p"),
                         {"p": p2})
        assert db.scalar(text("SELECT count(*) FROM practice_key")) == 0  # keys shredded again
    # replay is idempotent, and the restored database now carries the events too
    again = erasure_log.replay(restored, world["storage"], events)
    assert again["applied"] == 0 and again["already_erased"] == 3
    assert {e.event_id for e in erasure_log.read_db(restored, world["since"])} == {
        e.event_id for e in events}
    restored.dispose()


def test_unknown_clients_and_dry_run(world):
    restored = _app_engine(world["r1"])
    ghost = Event(str(uuid.uuid4()), "client", world["p1"], str(uuid.uuid4()), "request",
                  datetime.now(UTC))
    events = erasure_log.read_storage(world["storage"], world["since"]) + [ghost]
    dry = erasure_log.replay(restored, world["storage"], events, dry_run=True)
    assert dry["applied"] == 3 and dry["unknown"] == 1 and dry["dry_run"]
    assert _client_state(restored, world["p1"], world["ids"]["x"])[2] is None  # nothing changed
    real = erasure_log.replay(restored, world["storage"], events)
    assert real["applied"] == 2 and real["already_erased"] == 1 and real["unknown"] == 1
    restored.dispose()


def test_events_before_the_restore_point_are_ignored(world):
    future = datetime.now(UTC) + timedelta(hours=1)
    assert erasure_log.read_storage(world["storage"], future) == []


def test_cli_export_and_replay_from_file(world, monkeypatch, tmp_path, capsys):
    out = tmp_path / "events.jsonl"
    # the app role, as in production: the CLI must work under RLS (a superuser would see every
    # practice at once, which is not how a managed Postgres admin behaves with FORCE RLS)
    def app_url(u):
        return u.set(username=APP_ROLE, password=APP_PASSWORD).render_as_string(
            hide_password=False)

    monkeypatch.delenv("API_MIGRATION_URL", raising=False)
    monkeypatch.setenv("API_DATABASE_URL", app_url(world["owner_url"]))
    assert cli.main(["export-erasure-log", "--since", world["since"].isoformat(),
                     "--out", str(out)]) == 0
    assert len(out.read_text().splitlines()) == 3
    monkeypatch.setenv("API_DATABASE_URL", app_url(world["r2"]))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("STORAGE_SIGNING_KEY", "k" * 32)
    capsys.readouterr()
    rc = cli.main(["replay-erasures", "--since", world["since"].isoformat(),
                   "--source", str(out)])
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0 and summary["applied"] == 2 and summary["errors"] == 0
    # the same command straight from the storage log is a no-op now
    rc = cli.main(["replay-erasures", "--since", world["since"].isoformat()])
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0 and summary["applied"] == 0 and summary["already_erased"] == 3
    restored = _app_engine(world["r2"])
    assert _client_state(restored, world["p1"], world["ids"]["x"])[0] == "Erased client"
    restored.dispose()


def test_erasure_does_not_start_when_the_log_cannot_be_written(world):
    class Broken(LocalStorage):
        def put(self, *a, **k):
            raise OSError("storage down")

    broken = Broken(world["storage"].root, "k" * 32)
    with pytest.raises(OSError), tenant_session(world["live"], world["p1"]) as db:
        service.erase_client(db, world["p1"], world["ids"]["y"], broken)
    assert _client_state(world["live"], world["p1"], world["ids"]["y"])[1] == "y@example.com"
