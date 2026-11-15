"""Queue gauges and worker job metrics against real Postgres."""

import pytest
from sqlalchemy import text

pytest.importorskip("opentelemetry.sdk")

from opentelemetry.sdk.metrics import MeterProvider  # noqa: E402
from opentelemetry.sdk.metrics.export import InMemoryMetricReader  # noqa: E402

from app import metrics, worker  # noqa: E402

pytestmark = pytest.mark.pg


@pytest.fixture()
def reader(app_engine, owner_engine):
    with owner_engine.begin() as c:
        c.execute(text("DELETE FROM job"))
    r = InMemoryMetricReader()
    metrics.init(MeterProvider(metric_readers=[r]))
    metrics.bind_engine(app_engine)
    yield r
    metrics.bind_engine(None)
    metrics.init()
    with owner_engine.begin() as c:
        c.execute(text("DELETE FROM job"))


def gauge(reader, name):
    out = {}
    data = reader.get_metrics_data()
    for rm in (data.resource_metrics if data else []):
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name == name:
                    for p in m.data.data_points:
                        out[p.attributes["kind"]] = p.value
    return out


def test_queue_depth_age_and_failed_gauges(reader, owner_engine):
    with owner_engine.begin() as c:
        c.execute(text(
            "INSERT INTO job (kind, payload, status, run_at, max_attempts) VALUES "
            "('render_report', '{}', 'queued', now() - interval '90 seconds', 3), "
            "('render_report', '{}', 'queued', now() - interval '10 seconds', 3), "
            "('render_report', '{}', 'queued', now() + interval '1 hour', 3), "  # not ready yet
            "('send_notification', '{}', 'queued', now(), 3)"))
        c.execute(text(
            "INSERT INTO job (kind, payload, status, finished_at, max_attempts) VALUES "
            "('render_report', '{}', 'failed', now() - interval '1 hour', 3), "
            "('render_report', '{}', 'failed', now() - interval '3 days', 3)"))
    assert gauge(reader, "ankana.jobs.queue_depth") == {"render_report": 2, "send_notification": 1}
    ages = gauge(reader, "ankana.jobs.oldest_queued_age")
    assert 89 <= ages["render_report"] <= 150 and ages["send_notification"] < 30
    assert gauge(reader, "ankana.jobs.failed_recent")["render_report"] == 1  # only the last 24 h


def test_worker_records_job_duration_and_outcome(reader, app_engine, owner_engine):
    with owner_engine.begin() as c:
        c.execute(text("INSERT INTO job (kind, payload, max_attempts) VALUES "
                       "('ok_kind', '{}', 1), ('bad_kind', '{}', 1)"))

    def bad(job):
        raise RuntimeError("boom")

    reg = worker.Registry(handlers={"ok_kind": lambda j: {}, "bad_kind": bad}, on_failure={})
    while worker.process_one(app_engine, reg, "t"):
        pass
    seen = {}
    data = reader.get_metrics_data()
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name == "ankana.jobs.duration":
                    for p in m.data.data_points:
                        seen[(p.attributes["kind"], p.attributes["outcome"])] = p.count
    assert seen == {("ok_kind", "done"): 1, ("bad_kind", "error"): 1}
