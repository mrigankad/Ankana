"""OpenTelemetry metrics: HTTP latency by route template, AI tokens and cost per provider,
job/queue gauges, notification failures, auth events, rate limiter decisions."""

import pytest

pytest.importorskip("opentelemetry.sdk")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from opentelemetry.sdk.metrics import MeterProvider  # noqa: E402
from opentelemetry.sdk.metrics.export import InMemoryMetricReader  # noqa: E402

from ankana_ai import MockProvider, ask, telemetry  # noqa: E402
from ankana_ai.eval.charts import EVAL_NOW, chart_artifact  # noqa: E402
from app import metrics  # noqa: E402
from app.ratelimit import SharedRateLimiter  # noqa: E402


@pytest.fixture()
def reader():
    r = InMemoryMetricReader()
    metrics.init(MeterProvider(metric_readers=[r]))
    yield r
    metrics.init()  # back to the global (no-op) provider
    telemetry.usage_hook = None


def points(reader, name):
    out = []
    data = reader.get_metrics_data()
    for rm in (data.resource_metrics if data else []):
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name == name:
                    out.extend(m.data.data_points)
    return out


def test_http_latency_uses_route_templates_and_status_class(reader):
    app = FastAPI()
    app.add_middleware(metrics.HttpMetricsMiddleware)

    @app.get("/items/{item_id}")
    def item(item_id: str):
        return {"id": item_id}

    @app.get("/boom")
    def boom():
        raise RuntimeError("x")

    @app.get("/health")
    def health():
        return {}

    c = TestClient(app, raise_server_exceptions=False)
    c.get("/items/1"), c.get("/items/2"), c.get("/boom"), c.get("/nope"), c.get("/health")
    by = {(p.attributes["route"], p.attributes["status_class"]): p.count
          for p in points(reader, "ankana.http.request.duration")}
    assert by == {("/items/{item_id}", "2xx"): 2, ("/boom", "5xx"): 1, ("unmatched", "4xx"): 1}
    # no id ever becomes a label value
    assert all("1" not in str(p.attributes.get("route")) for p in
               points(reader, "ankana.http.request.duration"))


def test_ai_tokens_and_cost_are_metered_per_provider(reader):
    metrics.install_ai_hook()
    chart = chart_artifact("ananya-1995")
    res = ask(MockProvider("faithful"), chart, "Where is my Moon?", now=EVAL_NOW)
    assert res.usage["input_tokens"] > 0
    tokens = {(p.attributes["provider"], p.attributes["type"]): p.value
              for p in points(reader, "ankana.ai.tokens")}
    assert tokens[("mock", "input")] == res.usage["input_tokens"]
    assert tokens[("mock", "output")] == res.usage["output_tokens"]
    reqs = sum(p.value for p in points(reader, "ankana.ai.requests"))
    assert reqs == res.rounds
    # cost counter only moves for priced models; the mock model is free
    assert sum(p.value for p in points(reader, "ankana.ai.cost_usd")) == pytest.approx(res.cost_usd)


def test_ai_cost_counter_adds_up(reader):
    metrics.record_ai_usage("anthropic", "claude-sonnet-4-5", {"input_tokens": 100,
                                                               "output_tokens": 50}, 0.002)
    metrics.record_ai_usage("anthropic", "claude-sonnet-4-5", {"input_tokens": 10}, 0.001)
    cost = points(reader, "ankana.ai.cost_usd")
    assert len(cost) == 1 and cost[0].value == pytest.approx(0.003)


def test_telemetry_hook_failures_never_break_an_answer():
    def bad(*a):
        raise RuntimeError("exporter down")

    telemetry.usage_hook = bad
    try:
        telemetry.record_usage(MockProvider(), "m", {"input_tokens": 1}, 0.0)  # no raise
    finally:
        telemetry.usage_hook = None


def test_rate_limit_decisions_are_counted(reader):
    lim = SharedRateLimiter("t_metrics", 1, 60)
    lim.allow(None, "k"), lim.allow(None, "k")
    by = {p.attributes["result"]: p.value for p in points(reader, "ankana.ratelimit.decisions")}
    assert by == {"allowed": 1, "limited": 1}


def test_auth_and_notification_counters_have_low_cardinality_labels(reader):
    metrics.auth_events.add(1, {"action": "signin.failed"})
    metrics.notification_failures.add(1, {"channel": "email", "final": "true"})
    assert points(reader, "ankana.auth.events")[0].attributes == {"action": "signin.failed"}
    assert set(points(reader, "ankana.notifications.failures")[0].attributes) == {
        "channel", "final"}


def test_metric_instruments_never_carry_identifiers():
    # attribute names used anywhere in app code for metrics: a guard against someone adding
    # practice_id / client_id / email as a label later
    import pathlib
    import re

    src = pathlib.Path(__file__).parent.parent / "src"
    pattern = re.compile(r"metrics\.\w+\.(?:add|record)\([^)]*\{([^}]*)\}", re.S)
    for path in src.rglob("*.py"):
        for attrs in pattern.findall(path.read_text(encoding="utf-8")):
            assert not re.search(r"practice|client|user|email|ip\b|name", attrs), (path, attrs)


# ------------------------------------------------ dashboards and alerts stay in step
def _instrument_names() -> set[str]:
    r = InMemoryMetricReader()
    metrics.init(MeterProvider(metric_readers=[r]))
    try:
        import pathlib
        import re

        doc = pathlib.Path(metrics.__file__).read_text(encoding="utf-8")
        return set(re.findall(r"^\s{2}(ankana\.[a-z_.0-9]+)\s", doc, re.M))
    finally:
        metrics.init()


def test_workbook_grafana_and_alerts_only_use_metrics_that_exist():
    import json
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[3] / "infra" / "monitoring"
    names = _instrument_names()
    assert len(names) >= 12
    wb = (root / "workbook.json").read_text(encoding="utf-8")
    json.loads(wb)
    bicep = (root / "alerts.bicep").read_text(encoding="utf-8")
    for used in set(re.findall(r"ankana\.[a-z_.0-9]+", wb + bicep)):
        assert used in names, used
    dash = json.loads((root / "grafana-dashboard.json").read_text(encoding="utf-8"))
    prom = {n.replace(".", "_") for n in names}
    exprs = " ".join(t["expr"] for p in dash["panels"] for t in p["targets"])
    for used in set(re.findall(r"ankana_[a-zA-Z_0-9]+", exprs)):
        base = re.sub(r"_(milliseconds|seconds|USD|total|bucket|count|sum)", "", used)
        assert any(base == p or p.startswith(base) for p in prom), used
    # the SLO panels carry the targets from the brief
    titles = {p["title"] for p in dash["panels"]}
    assert "Chart generate p95 (SLO < 800 ms)" in titles and "Reads p95 (SLO < 200 ms)" in titles
