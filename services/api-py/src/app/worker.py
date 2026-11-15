"""Background worker: `python -m app.worker`.

Env: API_DATABASE_URL (RLS-bound app role), STORAGE_* (see app.storage),
WORKER_CONCURRENCY (default 2, caps concurrent Chromium instances),
WORKER_POLL_SECONDS (default 1.0), WORKER_VISIBILITY_SECONDS (default 900).
Flags: --once drains the queue and exits (tests, cron-style runs).
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.engine import Engine

from app import metrics
from app.jobs import Job, claim_next, complete, fail, reap_stale

log = logging.getLogger("app.worker")

Handler = Callable[[Job], dict | None]
FailureHook = Callable[[Job, str, bool], None]


@dataclass
class Registry:
    handlers: dict[str, Handler]
    on_failure: dict[str, FailureHook]
    # (interval seconds, fn) run from the supervisor loop, e.g. the reminder cron tick.
    periodic: list[tuple[float, Callable[[], object]]] = field(default_factory=list)


def ai_reading_job(job: Job, engine: Engine | None = None) -> dict:
    """Stub generation, real provider resolution: the AI reading pipeline lands with the
    ankana_ai worker port, but it already resolves its model through the practice's routing
    (role "report") with the same fallback chain as /ask."""
    log.info("ai_reading stub job=%s", job.id)
    result: dict = {"status": "stub"}
    if engine is not None and job.practice_id is not None:
        from app.ai_connections import chain_for_role
        from app.tenancy.session import tenant_session

        with tenant_session(engine, job.practice_id) as db:
            chain = chain_for_role(db, "report")
        result["providers"] = [e.kind for e in chain.entries] if chain else []
    return result


def default_registry(engine: Engine, storage) -> Registry:
    from app.notify.scheduler import (
        TICK_JOB,
        ensure_tick_job,
        send_failed,
        send_job,
        tick_job,
    )
    from app.notify.service import SEND_JOB
    from app.privacy.jobs import request_failed, run_request
    from app.privacy.service import JOB_KIND as PRIVACY_JOB
    from app.reports.service import RENDER_REPORT, render_report_failed, render_report_job

    return Registry(
        handlers={
            PRIVACY_JOB: lambda job: run_request(job, engine, storage),
            RENDER_REPORT: lambda job: render_report_job(job, engine, storage),
            "ai_reading": lambda job: ai_reading_job(job, engine),
            TICK_JOB: lambda job: tick_job(job, engine),
            SEND_JOB: lambda job: send_job(job, engine),
        },
        on_failure={
            RENDER_REPORT: lambda job, err, final: render_report_failed(job, engine, err, final),
            SEND_JOB: lambda job, err, final: send_failed(job, engine, err, final),
            PRIVACY_JOB: lambda job, err, final: request_failed(job, engine, err, final),
        },
        periodic=[(float(os.getenv("NOTIFY_TICK_SECONDS", "300")),
                   lambda: ensure_tick_job(engine))],
    )


def process_one(engine: Engine, registry: Registry, worker_id: str) -> bool:
    """Claim and run a single job. Returns False when the queue is empty."""
    job = claim_next(engine, worker_id, kinds=list(registry.handlers))
    if job is None:
        return False
    started = time.perf_counter()
    try:
        result = registry.handlers[job.kind](job)
    except Exception as exc:
        metrics.job_duration.record(time.perf_counter() - started,
                                    {"kind": job.kind, "outcome": "error"})
        # Never log payloads: they are ids only, but exceptions may carry data.
        err = f"{type(exc).__name__}: {exc}"
        log.warning("job %s (%s) attempt %s failed: %s", job.id, job.kind, job.attempts,
                    type(exc).__name__)
        final = fail(engine, job, err)
        hook = registry.on_failure.get(job.kind)
        if hook:
            hook(job, err, final)
    else:
        metrics.job_duration.record(time.perf_counter() - started,
                                    {"kind": job.kind, "outcome": "done"})
        complete(engine, job, result)
    return True


def run_worker(engine: Engine, registry: Registry, *, concurrency: int = 2,
               poll_seconds: float = 1.0, visibility_seconds: float = 900,
               stop: threading.Event | None = None, once: bool = False) -> None:
    stop = stop or threading.Event()
    host = socket.gethostname()

    def reap() -> None:
        for job in reap_stale(engine, visibility_seconds):
            hook = registry.on_failure.get(job.kind)
            if hook:
                hook(job, "worker lost", True)

    def loop(n: int) -> None:
        worker_id = f"{host}:{os.getpid()}:{n}:{uuid.uuid4().hex[:6]}"
        while not stop.is_set():
            try:
                if not process_one(engine, registry, worker_id):
                    if once:
                        return
                    stop.wait(poll_seconds)
            except Exception:
                log.exception("worker loop error")
                stop.wait(poll_seconds)

    reap()
    threads = [threading.Thread(target=loop, args=(i,), name=f"worker-{i}", daemon=True)
               for i in range(concurrency)]
    for t in threads:
        t.start()
    last_reap = 0.0
    import time

    last_run = [-1e9] * len(registry.periodic)

    while any(t.is_alive() for t in threads):
        for t in threads:
            t.join(timeout=0.5)
        if not once and time.monotonic() - last_reap > 60:
            reap()
            last_reap = time.monotonic()
        if not once:
            for idx, (interval, fn) in enumerate(registry.periodic):
                if time.monotonic() - last_run[idx] >= interval:
                    last_run[idx] = time.monotonic()
                    try:
                        fn()
                    except Exception:
                        log.exception("periodic task failed")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.worker")
    parser.add_argument("--once", action="store_true", help="drain the queue then exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")

    from app.settings import Settings
    from app.storage import storage_from_env
    from app.tenancy.session import make_pg_engine

    settings = Settings.from_env()
    if not settings.database_url:
        raise SystemExit("API_DATABASE_URL is required")
    from app.messaging import assert_production_ready

    assert_production_ready()  # refuses console sms/whatsapp when API_ENV=production
    engine = make_pg_engine(settings.database_url)
    from app.observability import setup_worker_observability

    setup_worker_observability(engine)
    registry = default_registry(engine, storage_from_env())

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    log.info("worker started kinds=%s", sorted(registry.handlers))
    run_worker(
        engine, registry, concurrency=int(os.getenv("WORKER_CONCURRENCY", "2")),
        poll_seconds=float(os.getenv("WORKER_POLL_SECONDS", "1.0")),
        visibility_seconds=float(os.getenv("WORKER_VISIBILITY_SECONDS", "900")),
        stop=stop, once=args.once)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
