"""Queue semantics on real Postgres: claim, retry/backoff, exhaustion,
concurrent claiming without duplicates, stale-job recovery, worker loop."""

import threading
import uuid

import pytest
from sqlalchemy import text

from app import worker
from app.jobs import claim_next, complete, enqueue, fail, queue, reap_stale


@pytest.fixture(autouse=True)
def clean_jobs(owner_engine):
    with owner_engine.begin() as c:
        c.execute(text("DELETE FROM job"))
    yield


def _enqueue(engine, kind="t", payload=None, **kw):
    with engine.begin() as c:
        return enqueue(c, kind, payload or {}, **kw)


def _row(engine, job_id):
    with engine.begin() as c:
        return c.execute(text("SELECT status, attempts, last_error FROM job WHERE id=:i"),
                         {"i": job_id}).one()


def test_claim_is_exclusive_and_ordered(app_engine):
    a = _enqueue(app_engine)
    b = _enqueue(app_engine)
    j1 = claim_next(app_engine, "w1")
    j2 = claim_next(app_engine, "w2")
    assert (j1.id, j2.id) == (a, b)
    assert j1.attempts == 1
    assert claim_next(app_engine, "w3") is None
    complete(app_engine, j1, {"ok": True})
    assert _row(app_engine, a).status == "done"


def test_kind_filter_and_delay(app_engine):
    _enqueue(app_engine, "other")
    _enqueue(app_engine, "later", delay_seconds=60)
    assert claim_next(app_engine, "w", kinds=["later"]) is None  # not yet due
    assert claim_next(app_engine, "w", kinds=["nope"]) is None
    assert claim_next(app_engine, "w", kinds=["other"]).kind == "other"


def test_retry_with_backoff_then_terminal_failure(app_engine, monkeypatch):
    monkeypatch.setattr(queue, "BACKOFF_BASE_SECONDS", 0.0)
    jid = _enqueue(app_engine, max_attempts=3)
    outcomes = []
    for _ in range(3):
        job = claim_next(app_engine, "w")
        assert job is not None
        outcomes.append(fail(app_engine, job, "boom"))
    assert outcomes == [False, False, True]
    row = _row(app_engine, jid)
    assert (row.status, row.attempts, row.last_error) == ("failed", 3, "boom")
    assert claim_next(app_engine, "w") is None


def test_backoff_delays_next_attempt(app_engine):
    _enqueue(app_engine, max_attempts=3)
    job = claim_next(app_engine, "w")
    fail(app_engine, job, "boom")  # backoff 5s
    assert claim_next(app_engine, "w") is None


def test_concurrent_workers_never_double_claim(app_engine):
    ids = {_enqueue(app_engine, payload={"n": i}) for i in range(40)}
    claimed: list[uuid.UUID] = []
    lock = threading.Lock()

    def drain(name):
        while (job := claim_next(app_engine, name)) is not None:
            with lock:
                claimed.append(job.id)
            complete(app_engine, job)

    threads = [threading.Thread(target=drain, args=(f"w{i}",)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(claimed) == 40
    assert set(claimed) == ids  # each exactly once


def test_reap_stale_requeues_then_fails(app_engine, owner_engine):
    jid = _enqueue(app_engine, max_attempts=2)
    claim_next(app_engine, "dead-worker")
    assert reap_stale(app_engine, 3600) == []  # lock is fresh
    with owner_engine.begin() as c:
        c.execute(text("UPDATE job SET locked_at = now() - interval '2 hours'"))
    assert reap_stale(app_engine, 3600) == []
    assert _row(app_engine, jid).status == "queued"
    claim_next(app_engine, "dead-worker-2")  # attempt 2 of 2
    with owner_engine.begin() as c:
        c.execute(text("UPDATE job SET locked_at = now() - interval '2 hours'"))
    dead = reap_stale(app_engine, 3600)
    assert [j.id for j in dead] == [jid]
    assert _row(app_engine, jid).status == "failed"


def test_enqueue_is_transactional(app_engine):
    with pytest.raises(RuntimeError):
        with app_engine.begin() as c:
            enqueue(c, "t")
            raise RuntimeError("rollback")
    assert claim_next(app_engine, "w") is None


def test_worker_loop_runs_handlers_retries_and_calls_failure_hook(app_engine, monkeypatch):
    monkeypatch.setattr(queue, "BACKOFF_BASE_SECONDS", 0.0)
    seen, hooks, attempts = [], [], {"flaky": 0}

    def ok(job):
        seen.append(job.payload["n"])
        return {"n": job.payload["n"]}

    def flaky(job):
        attempts["flaky"] += 1
        if attempts["flaky"] < 3:
            raise ValueError("transient")

    def always(job):
        raise ValueError("permanent")

    reg = worker.Registry(
        {"ok": ok, "flaky": flaky, "always": always},
        {"always": lambda job, err, final: hooks.append((err, final))})
    for n in range(5):
        _enqueue(app_engine, "ok", {"n": n})
    flaky_id = _enqueue(app_engine, "flaky")
    always_id = _enqueue(app_engine, "always", max_attempts=2)
    worker.run_worker(app_engine, reg, concurrency=3, once=True, poll_seconds=0.05)
    assert sorted(seen) == [0, 1, 2, 3, 4]
    assert _row(app_engine, flaky_id).status == "done"
    assert _row(app_engine, always_id).status == "failed"
    assert hooks == [("ValueError: permanent", False), ("ValueError: permanent", True)]


def test_ai_reading_stub_job(app_engine):
    jid = _enqueue(app_engine, "ai_reading", {"x": 1})
    reg = worker.Registry({"ai_reading": worker.ai_reading_job}, {})
    worker.run_worker(app_engine, reg, concurrency=1, once=True, poll_seconds=0.05)
    assert _row(app_engine, jid).status == "done"


def test_a_reaped_worker_cannot_finish_or_fail_the_run_that_replaced_it(app_engine, owner_engine):
    jid = _enqueue(app_engine, max_attempts=3)
    old = claim_next(app_engine, "w-old")
    with owner_engine.begin() as c:
        c.execute(text("UPDATE job SET locked_at = now() - interval '1 hour' WHERE id=:i"),
                  {"i": jid})
    reap_stale(app_engine, 900)
    new = claim_next(app_engine, "w-new")
    assert new.id == jid and new.attempts == 2
    complete(app_engine, old, {"stale": True})  # late, from the lost worker
    fail(app_engine, old, "stale failure")
    row = _row(app_engine, jid)
    assert row.status == "running" and row.attempts == 2
    complete(app_engine, new, {"ok": True})
    assert _row(app_engine, jid).status == "done"
    fail(app_engine, new, "after done")  # cannot resurrect a finished job
    assert _row(app_engine, jid).status == "done"
