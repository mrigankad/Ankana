"""Optional OpenTelemetry tracing, structured logs and Sentry.

Everything here is opt-in and degrades to a no-op when the packages or env vars
are missing, so local dev and CI need none of it. Install with
`pip install -e ".[observability]"`.

Privacy rules (birth data and names are personal data under DPDP):
- Request and response bodies are never recorded.
- URL query strings are stripped from spans (location search puts place names in
  `?q=`), and a deny-list removes any attribute that looks like personal data.
- Logs carry `practice_id` (a UUID), never client names or birth details.
- Sentry runs with send_default_pii=False, no request bodies, and a before_send
  scrubber.

Environment:
  OTEL_EXPORTER_OTLP_ENDPOINT   enable OTLP trace export (collector, Grafana, etc).
                                Unset = tracing disabled.
  APPLICATIONINSIGHTS_CONNECTION_STRING
                                alternative: export to Application Insights
                                (needs azure-monitor-opentelemetry-exporter).
  OTEL_SERVICE_NAME             default "ankana-api".
  ANKANA_METRICS                set to 0 to keep traces but skip metrics export.
                                ANKANA_METRICS_INTERVAL_SECONDS (default 30).
  SENTRY_DSN                    enable Sentry. SENTRY_TRACES_SAMPLE_RATE (default 0.0).
  API_ENV, RELEASE_SHA          reported as environment / release.
  LOG_LEVEL                     default INFO.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import re
from typing import Any
from urllib.parse import urlsplit

practice_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "practice_id", default=None
)

# Attribute-name fragments that must never leave the process.
_DENY_SUBSTRINGS = (
    "birth", "name", "email", "phone", "place", "latitude", "longitude", "lat", "lon",
    "body", "query", "authorization", "cookie", "token",
)
_ALLOW_EXACT = {"http.method", "http.route", "http.status_code", "practice_id", "service.name"}
_URL_KEYS = {"http.url", "url.full", "http.target", "url.path"}

# /v1/auth/invites/<token>[/accept]: the path segment is a bearer secret for the invite.
_INVITE_TOKEN = re.compile(r"(/invites/)[^/?#\s]+")

log = logging.getLogger("ankana.observability")


def set_practice(practice_id: object) -> None:
    """Record the tenant for logs and the current span. Called from bind_practice."""
    pid = str(practice_id)
    practice_id_var.set(pid)
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("practice_id", pid)
    except ImportError:
        pass


def _current_practice() -> str | None:
    pid = practice_id_var.get()
    if pid:
        return pid
    try:
        from opentelemetry import trace

        attrs = getattr(trace.get_current_span(), "attributes", None) or {}
        return attrs.get("practice_id")
    except ImportError:
        return None


class PracticeFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.practice_id = _current_practice() or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "practice_id": getattr(record, "practice_id", "-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def scrub_attributes(attrs: dict[str, Any]) -> dict[str, Any]:
    """Drop PII-looking attributes and strip query strings from URLs."""
    clean: dict[str, Any] = {}
    for key, value in attrs.items():
        lowered = key.lower()
        if key in _ALLOW_EXACT:
            clean[key] = value
        elif lowered in _URL_KEYS and isinstance(value, str):
            clean[key] = _INVITE_TOKEN.sub(
                r"\1<redacted>", urlsplit(value)._replace(query="", fragment="").geturl())
        elif any(s in lowered for s in _DENY_SUBSTRINGS):
            continue
        else:
            clean[key] = value
    return clean


def _scrubbing_exporter(inner: Any) -> Any:
    from opentelemetry.sdk.trace.export import SpanExporter

    class ScrubbingExporter(SpanExporter):
        def export(self, spans):
            for span in spans:
                span._attributes = scrub_attributes(dict(span.attributes or {}))
            return inner.export(spans)

        def shutdown(self) -> None:
            inner.shutdown()

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return inner.force_flush(timeout_millis)

    return ScrubbingExporter()


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    if getattr(root, "_ankana_configured", False):
        return
    handler = logging.StreamHandler()
    handler.addFilter(PracticeFilter())
    if os.getenv("API_ENV", "dev") == "dev":
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(practice_id)s] %(name)s: %(message)s")
        )
    else:
        handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root._ankana_configured = True  # type: ignore[attr-defined]


def _setup_tracing(app: Any) -> bool:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    appi = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not (endpoint or appi):
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter()
        else:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

            exporter = AzureMonitorTraceExporter.from_connection_string(appi)
    except ImportError as exc:
        log.warning("tracing requested but packages missing: %s", exc)
        return False

    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", "ankana-api"),
            "deployment.environment": os.getenv("API_ENV", "dev"),
            "service.version": os.getenv("RELEASE_SHA", "dev"),
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(_scrubbing_exporter(exporter)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls="health,ready")
    return True


def _sentry_before_send(event: dict, hint: dict) -> dict | None:
    request = event.get("request") or {}
    for key in ("data", "cookies", "query_string", "headers"):
        request.pop(key, None)
    event["request"] = request
    event.pop("user", None)
    pid = _current_practice()
    if pid:
        event.setdefault("tags", {})["practice_id"] = pid
    return event


def _setup_sentry() -> bool:
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        log.warning("SENTRY_DSN set but sentry-sdk is not installed")
        return False
    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("API_ENV", "dev"),
        release=os.getenv("RELEASE_SHA"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        before_send=_sentry_before_send,
    )
    return True


def _setup_metrics() -> bool:
    """OTLP/HTTP (collector, Grafana Alloy) or Azure Monitor, whichever is configured.
    Instruments live in app.metrics and are no-ops without this."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    appi = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not (endpoint or appi) or os.getenv("ANKANA_METRICS", "1") == "0":
        return False
    try:
        from opentelemetry import metrics as otel_metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
        from opentelemetry.sdk.resources import Resource

        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

            exporter = OTLPMetricExporter()
        else:
            from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter

            exporter = AzureMonitorMetricExporter.from_connection_string(appi)
    except ImportError as exc:
        log.warning("metrics requested but packages missing: %s", exc)
        return False
    from . import metrics as app_metrics

    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "ankana-api"),
        "deployment.environment": os.getenv("API_ENV", "dev"),
        "service.version": os.getenv("RELEASE_SHA", "dev"),
    })
    interval = int(os.getenv("ANKANA_METRICS_INTERVAL_SECONDS", "30")) * 1000
    views = [
        View(instrument_name="ankana.http.request.duration",
             aggregation=ExplicitBucketHistogramAggregation(app_metrics.HTTP_BUCKETS_MS)),
        View(instrument_name="ankana.jobs.duration",
             aggregation=ExplicitBucketHistogramAggregation(app_metrics.SECONDS_BUCKETS)),
        View(instrument_name="ankana.report.render.duration",
             aggregation=ExplicitBucketHistogramAggregation(app_metrics.SECONDS_BUCKETS)),
    ]
    provider = MeterProvider(
        resource=resource, views=views,
        metric_readers=[PeriodicExportingMetricReader(exporter, export_interval_millis=interval)])
    otel_metrics.set_meter_provider(provider)
    app_metrics.init(provider)
    return True


def setup_worker_observability(engine: Any) -> dict[str, bool]:
    """Worker process: logging, metrics and the queue gauges (no FastAPI app)."""
    os.environ.setdefault("OTEL_SERVICE_NAME", "ankana-worker")
    from . import metrics as app_metrics

    app_metrics.bind_engine(engine)
    app_metrics.install_ai_hook()
    status = {"metrics": _setup_metrics(), "sentry": _setup_sentry()}
    log.info("worker observability: %s", status)
    return status


def setup_observability(app: Any) -> dict[str, bool]:
    configure_logging()
    from . import metrics as app_metrics

    app_metrics.install_ai_hook()
    app.add_middleware(app_metrics.HttpMetricsMiddleware)
    status = {"tracing": _setup_tracing(app), "metrics": _setup_metrics(),
              "sentry": _setup_sentry()}
    log.info("observability: %s", status)
    return status
