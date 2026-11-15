"""Application metrics (OpenTelemetry). Instruments are created from the global meter
provider, so with no SDK or exporter configured every call is a cheap no-op.

Names (the OTLP -> Prometheus form replaces dots with underscores and adds unit suffixes):

  ankana.http.request.duration       histogram ms   method, route (template), status_class
  ankana.jobs.queue_depth            gauge          kind          queued jobs ready to run
  ankana.jobs.oldest_queued_age      gauge s        kind          age of the oldest ready job
  ankana.jobs.failed_recent          gauge          kind          terminally failed in last 24 h
  ankana.jobs.duration               histogram s    kind, outcome (done | error)
  ankana.report.render.duration      histogram s    outcome
  ankana.ai.tokens                   counter        provider, model, type (input | output | cache_*)
  ankana.ai.cost_usd                 counter USD    provider, model
  ankana.ai.requests                 counter        provider, model
  ankana.notifications.failures      counter        channel, final
  ankana.auth.events                 counter        action (signin.failed, signin.blocked, ...)
  ankana.ratelimit.decisions         counter        scope, result (allowed | limited)
  ankana.ratelimit.fallbacks         counter        scope

No client, practice or user identifier is ever a metric attribute (cardinality and DPDP).
Call `init(provider)` to bind the instruments to a specific MeterProvider (tests, or the
exporter setup in app.observability).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterable

from opentelemetry import metrics as _api
from opentelemetry.metrics import CallbackOptions, Observation
from sqlalchemy import text

log = logging.getLogger("ankana.metrics")

HTTP_BUCKETS_MS = [5, 10, 25, 50, 100, 200, 400, 800, 1500, 3000, 6000, 12000]
SECONDS_BUCKETS = [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120]

_engine = None
_lock = threading.Lock()
_cache: dict[str, object] = {"at": -1e9, "rows": []}
_QUEUE_SQL = text("""
    SELECT kind,
           count(*) FILTER (WHERE status = 'queued' AND run_at <= now()) AS depth,
           coalesce(extract(epoch FROM now() - min(run_at) FILTER (
               WHERE status = 'queued' AND run_at <= now())), 0) AS oldest,
           count(*) FILTER (WHERE status = 'failed'
                            AND finished_at > now() - interval '24 hours') AS failed
    FROM job GROUP BY kind
""")


def _queue_rows() -> list:
    """One query per collection, shared by the three gauges (cached for 5 s)."""
    if _engine is None:
        return []
    with _lock:
        if time.monotonic() - float(_cache["at"]) < 5:  # type: ignore[arg-type]
            return list(_cache["rows"])  # type: ignore[arg-type]
        try:
            with _engine.connect() as conn:
                rows = [tuple(r) for r in conn.execute(_QUEUE_SQL)]
        except Exception as exc:
            log.warning("queue metrics query failed: %s", exc.__class__.__name__)
            rows = []
        _cache.update(at=time.monotonic(), rows=rows)
        return list(rows)


def _obs(index: int) -> Iterable[Observation]:
    return [Observation(float(r[index]), {"kind": r[0]}) for r in _queue_rows()]


def _cb_depth(_o: CallbackOptions) -> Iterable[Observation]:
    return _obs(1)


def _cb_oldest(_o: CallbackOptions) -> Iterable[Observation]:
    return _obs(2)


def _cb_failed(_o: CallbackOptions) -> Iterable[Observation]:
    return _obs(3)


def init(provider=None) -> None:
    """(Re)create the instruments, from `provider` or the global meter provider."""
    meter = (provider or _api).get_meter("ankana")
    g = globals()
    g["http_request_duration"] = meter.create_histogram(
        "ankana.http.request.duration", unit="ms", description="HTTP request latency")
    g["job_queue_depth"] = meter.create_observable_gauge(
        "ankana.jobs.queue_depth", callbacks=[_cb_depth], description="Queued jobs ready to run")
    g["job_oldest_age"] = meter.create_observable_gauge(
        "ankana.jobs.oldest_queued_age", unit="s", callbacks=[_cb_oldest],
        description="Age of the oldest queued job that is ready to run")
    g["job_failed_recent"] = meter.create_observable_gauge(
        "ankana.jobs.failed_recent", callbacks=[_cb_failed],
        description="Jobs that failed terminally in the last 24 hours")
    g["job_duration"] = meter.create_histogram(
        "ankana.jobs.duration", unit="s", description="Job handler run time")
    g["report_render_duration"] = meter.create_histogram(
        "ankana.report.render.duration", unit="s", description="Report PDF render time")
    g["ai_tokens"] = meter.create_counter("ankana.ai.tokens", description="LLM tokens")
    g["ai_cost_usd"] = meter.create_counter("ankana.ai.cost_usd", unit="USD",
                                            description="LLM cost estimate")
    g["ai_requests"] = meter.create_counter("ankana.ai.requests", description="LLM calls")
    g["notification_failures"] = meter.create_counter(
        "ankana.notifications.failures", description="Notification send failures")
    g["auth_events"] = meter.create_counter(
        "ankana.auth.events", description="Security-relevant auth events")
    g["rate_limit_decisions"] = meter.create_counter(
        "ankana.ratelimit.decisions", description="Rate limiter decisions")
    g["rate_limit_fallbacks"] = meter.create_counter(
        "ankana.ratelimit.fallbacks", description="Rate limiter fell back to in-process")


def bind_engine(engine) -> None:
    """Let the queue gauges read the job table (API and worker call this once)."""
    global _engine
    _engine = engine
    _cache["at"] = -1e9


def record_ai_usage(provider: str, model: str, usage: dict, cost: float) -> None:
    attrs = {"provider": provider, "model": model}
    ai_requests.add(1, attrs)  # noqa: F821
    for key, kind in (("input_tokens", "input"), ("output_tokens", "output"),
                      ("cache_read_input_tokens", "cache_read"),
                      ("cache_creation_input_tokens", "cache_write")):
        n = int(usage.get(key) or 0)
        if n:
            ai_tokens.add(n, {**attrs, "type": kind})  # noqa: F821
    if cost:
        ai_cost_usd.add(cost, attrs)  # noqa: F821


def status_class(status: int) -> str:
    return f"{status // 100}xx"


class HttpMetricsMiddleware:
    """Pure ASGI (no BaseHTTPMiddleware body buffering). Records latency by route
    template, so ids in paths never become label values."""

    SKIP = ("/health", "/ready")

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["path"] in self.SKIP:
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        status = {"code": 500}

        async def _send(message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            route = scope.get("route")
            path = getattr(route, "path", None) or "unmatched"
            http_request_duration.record(  # noqa: F821
                (time.perf_counter() - start) * 1000.0,
                {"method": scope["method"], "route": path,
                 "status_class": status_class(status["code"])})


def install_ai_hook() -> None:
    from ankana_ai import telemetry

    telemetry.usage_hook = record_ai_usage


init()
