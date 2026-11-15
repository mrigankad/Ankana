"""RLS proofs against real Postgres. Connections use the app role, which is
neither superuser nor table owner, so a passing test means the policy held."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.tenancy.models import (
    TENANT_TABLES,
    AuditEvent,
    BirthRecord,
    ChartArtifact,
    Client,
    Member,
    Practice,
    RemedyPlan,
    RemedyStatus,
    Role,
    TimeSource,
    UserAccount,
)
from app.tenancy.session import bind_practice, tenant_session

pytestmark = pytest.mark.pg


def _make_practice(engine, name: str) -> uuid.UUID:
    pid = uuid.uuid4()
    with tenant_session(engine, pid) as s:
        s.add(Practice(id=pid, name=name))
        user = UserAccount(issuer="t", subject=uuid.uuid4().hex)
        s.add(user)  # user_account is global, no RLS
        s.flush()
        s.add(Member(practice_id=pid, user_id=user.id, role=Role.owner))
    return pid


def _seed_client(engine, pid: uuid.UUID, name: str) -> uuid.UUID:
    with tenant_session(engine, pid) as s:
        c = Client(practice_id=pid, display_name=name)
        s.add(c)
        s.flush()
        b = BirthRecord(practice_id=pid, client_id=c.id, birth_date=date(2000, 1, 1),
                        time_source=TimeSource.memory, place_label="Pune",
                        latitude=18.5, longitude=73.8, timezone_name="Asia/Kolkata")
        s.add(b)
        s.flush()
        s.add(ChartArtifact(practice_id=pid, birth_record_id=b.id, settings_hash="h",
                            engine_version="1", payload={"x": 1}))
        s.add(AuditEvent(practice_id=pid, action="t", entity_type="client", entity_id=str(c.id)))
        return c.id


def test_every_tenant_table_has_forced_rls(owner_engine) -> None:
    with owner_engine.connect() as c:
        rows = c.execute(text(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = ANY(:t) AND relkind = 'r'"), {"t": [*TENANT_TABLES, "practice"]}
        ).all()
        policies = {r[0] for r in c.execute(text("SELECT tablename FROM pg_policies"))}
    assert {r[0] for r in rows} == {*TENANT_TABLES, "practice"}
    for name, enabled, forced in rows:
        assert enabled and forced, name
        assert name in policies, name


def test_app_role_is_not_privileged(app_engine) -> None:
    with app_engine.connect() as c:
        sup, byp = c.execute(text(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
    assert not sup and not byp


def test_cross_practice_reads_return_nothing(app_engine) -> None:
    a, b = _make_practice(app_engine, "A"), _make_practice(app_engine, "B")
    ca = _seed_client(app_engine, a, "Alice")
    cb = _seed_client(app_engine, b, "Bob")
    for model in (Client, BirthRecord, ChartArtifact, AuditEvent, Member):
        with tenant_session(app_engine, a) as s:
            rows = s.scalars(select(model)).all()
            assert rows and all(r.practice_id == a for r in rows), model
    with tenant_session(app_engine, a) as s:
        assert s.get(Client, cb) is None
        assert s.get(Client, ca) is not None
        assert [p.id for p in s.scalars(select(Practice))] == [a]


def test_no_practice_bound_sees_nothing(app_engine) -> None:
    pid = _make_practice(app_engine, "C")
    _seed_client(app_engine, pid, "Carol")
    with Session(app_engine) as s, s.begin():
        for model in (Client, BirthRecord, ChartArtifact, AuditEvent, Member, Practice):
            assert s.scalars(select(model)).all() == [], model


def test_setting_does_not_leak_across_pooled_transactions(app_engine) -> None:
    pid = _make_practice(app_engine, "D")
    _seed_client(app_engine, pid, "Dan")
    with tenant_session(app_engine, pid) as s:
        assert s.scalars(select(Client)).all()
    with Session(app_engine) as s, s.begin():
        assert s.scalar(text("SELECT current_setting('app.practice_id', true)")) in (None, "")
        assert s.scalars(select(Client)).all() == []


def test_cannot_write_into_another_practice(app_engine) -> None:
    a, b = _make_practice(app_engine, "E"), _make_practice(app_engine, "F")
    with pytest.raises(DBAPIError):
        with tenant_session(app_engine, a) as s:
            s.add(Client(practice_id=b, display_name="Smuggled"))
            s.flush()
    cid = _seed_client(app_engine, b, "Frank")
    with tenant_session(app_engine, a) as s:  # update/delete touch zero rows
        assert s.execute(text("UPDATE client SET display_name='x' WHERE id=:i"),
                         {"i": cid}).rowcount == 0
        assert s.execute(text("DELETE FROM client WHERE id=:i"), {"i": cid}).rowcount == 0
    with tenant_session(app_engine, b) as s:
        assert s.get(Client, cid).display_name == "Frank"


def test_composite_fk_blocks_cross_practice_reference(owner_engine, app_engine) -> None:
    a, b = _make_practice(app_engine, "G"), _make_practice(app_engine, "H")
    cb = _seed_client(app_engine, b, "Hal")
    # Even a superuser-written row cannot point practice A at practice B's client.
    with pytest.raises(IntegrityError):
        with Session(owner_engine) as s, s.begin():
            bind_practice(s, a)  # encrypted columns need a practice scope even for the owner
            s.add(BirthRecord(practice_id=a, client_id=cb, birth_date=date(2000, 1, 1),
                              time_source=TimeSource.unknown, place_label="x", latitude=0,
                              longitude=0, timezone_name="UTC"))


def test_audit_event_is_append_only(app_engine) -> None:
    pid = _make_practice(app_engine, "I")
    _seed_client(app_engine, pid, "Ivy")
    with pytest.raises(ProgrammingError):  # no UPDATE or DELETE grant at all
        with tenant_session(app_engine, pid) as s:
            s.execute(text("UPDATE audit_event SET action='tampered'"))
    with pytest.raises(ProgrammingError):
        with tenant_session(app_engine, pid) as s:
            s.execute(text("DELETE FROM audit_event"))


def test_one_active_remedy_plan_per_client(app_engine) -> None:
    pid = _make_practice(app_engine, "J")
    cid = _seed_client(app_engine, pid, "Jo")
    with tenant_session(app_engine, pid) as s:
        s.add(RemedyPlan(practice_id=pid, client_id=cid, title="one", status=RemedyStatus.active))
        s.add(RemedyPlan(practice_id=pid, client_id=cid, title="draft",
                         status=RemedyStatus.draft))
    with pytest.raises(IntegrityError):
        with tenant_session(app_engine, pid) as s:
            s.add(RemedyPlan(practice_id=pid, client_id=cid, title="two",
                             status=RemedyStatus.active))
    with tenant_session(app_engine, pid) as s:
        plan = s.scalar(select(RemedyPlan).where(RemedyPlan.title == "one"))
        assert plan.cycle_days == 43
        plan.status = RemedyStatus.completed
    with tenant_session(app_engine, pid) as s:  # now another may activate
        s.add(RemedyPlan(practice_id=pid, client_id=cid, title="three",
                         status=RemedyStatus.active))


def test_chart_artifact_unique_per_birth_settings_engine(app_engine) -> None:
    pid = _make_practice(app_engine, "K")
    cid = _seed_client(app_engine, pid, "Kim")
    with pytest.raises(IntegrityError):
        with tenant_session(app_engine, pid) as s:
            b = s.scalar(select(BirthRecord).where(BirthRecord.client_id == cid))
            s.add(ChartArtifact(practice_id=pid, birth_record_id=b.id, settings_hash="h",
                                engine_version="1", payload={}))
