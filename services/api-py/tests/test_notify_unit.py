"""Reminder maths, signed links, template sandbox, channels. No database needed."""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.notify import channels, due, links
from app.notify.public import RateLimiter
from app.notify.templates import (
    DEFAULTS,
    SAMPLE_CONTEXT,
    TemplateError,
    render_message,
    render_text,
    validate_template,
)

NY = "America/New_York"


def utc(*a):
    return datetime(*a, tzinfo=UTC)


# ---------------------------------------------------------------- time zones
def test_local_today_differs_by_zone():
    now = utc(2026, 11, 4, 20, 0)
    assert due.local_today(now, "Asia/Kolkata") == date(2026, 11, 5)  # 01:30 next day
    assert due.local_today(now, NY) == date(2026, 11, 4)
    assert due.local_today(now, "Pacific/Auckland") == date(2026, 11, 5)
    assert due.local_today(now, "Not/AZone") == date(2026, 11, 5)  # falls back to India


def test_send_time_follows_dst():
    # 08:00 New York is 13:00Z in winter (EST) and 12:00Z after spring-forward (EDT).
    assert due.at_local(date(2026, 3, 7), 8, NY) == utc(2026, 3, 7, 13)
    assert due.at_local(date(2026, 3, 8), 8, NY) == utc(2026, 3, 8, 12)
    # Nov 1 2026 fall-back: 08:00 is EST again.
    assert due.at_local(date(2026, 11, 1), 8, NY) == utc(2026, 11, 1, 13)
    # India has no DST.
    assert due.at_local(date(2026, 3, 8), 8, "Asia/Kolkata") == utc(2026, 3, 8, 2, 30)


def test_nonexistent_wall_time_in_spring_gap_resolves_forward():
    # 02:30 on 2026-03-08 does not exist in New York; it must land at 03:30 EDT = 07:30Z.
    assert due.at_local(date(2026, 3, 8), 2, NY, 30) == utc(2026, 3, 8, 7, 30)


def test_local_day_is_23_hours_on_spring_forward():
    start = due.at_local(date(2026, 3, 8), 0, NY)
    nxt = due.at_local(date(2026, 3, 9), 0, NY)
    assert nxt - start == timedelta(hours=23)
    assert due.local_today(nxt - timedelta(seconds=1), NY) == date(2026, 3, 8)


# --------------------------------------------------------------- quiet hours
def test_quiet_hours_wrap_midnight():
    s, e = time(21), time(7)
    assert due.in_quiet_hours(time(22), s, e)
    assert due.in_quiet_hours(time(3), s, e)
    assert not due.in_quiet_hours(time(7), s, e)
    assert not due.in_quiet_hours(time(12), s, e)
    assert not due.in_quiet_hours(time(5), time(8), time(8))  # empty window


def test_schedule_time_defers_or_skips_stale():
    ist = "Asia/Kolkata"
    day = date(2026, 11, 4)
    qs, qe = time(21), time(7)
    # Tick at 00:05 IST: wait for 08:00 IST.
    now = utc(2026, 11, 3, 18, 35)
    run_at, skip = due.schedule_time(now, day, ist, 8, qs, qe)
    assert (run_at, skip) == (utc(2026, 11, 4, 2, 30), None)
    # Tick at 11:00 IST: send immediately.
    now = utc(2026, 11, 4, 5, 30)
    assert due.schedule_time(now, day, ist, 8, qs, qe) == (now, None)
    # Tick at 22:00 IST: quiet hours push to tomorrow 07:00, which is stale for `day`.
    now = utc(2026, 11, 4, 16, 30)
    run_at, skip = due.schedule_time(now, day, ist, 8, qs, qe)
    assert skip == "quiet_hours" and run_at == utc(2026, 11, 5, 1, 30)
    # Reminder hour inside quiet hours: moved to the end of the window, same day.
    run_at, skip = due.schedule_time(utc(2026, 11, 3, 18, 35), day, ist, 6, qs, qe)
    assert (run_at, skip) == (utc(2026, 11, 4, 1, 30), None)


# -------------------------------------------------------------- signed links
def test_link_roundtrip_expiry_and_tamper():
    t0 = utc(2026, 11, 4, 3)
    tok = links.sign("checkin", {"p": "a", "c": "b"}, timedelta(hours=1), t0)
    assert links.verify(tok, "checkin", t0 + timedelta(minutes=59))["p"] == "a"
    with pytest.raises(links.LinkError) as e:
        links.verify(tok, "checkin", t0 + timedelta(hours=1, seconds=1))
    assert e.value.code == "expired"
    body, sig = tok.split(".")
    for bad in (f"{body}.{sig[:-2]}AA", f"x{body}.{sig}", body + ".", "garbage", ".sig"):
        with pytest.raises(links.LinkError):
            links.verify(bad, "checkin", t0)
    with pytest.raises(links.LinkError) as e:  # a checkin token is not a stop token
        links.verify(tok, "stop", t0)
    assert e.value.code == "bad_signature"


def test_link_payload_tamper_detected():
    import base64
    import json

    t0 = utc(2026, 11, 4, 3)
    tok = links.sign("checkin", {"c": "client-1"}, timedelta(hours=1), t0)
    body, sig = tok.split(".")
    data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    data["c"] = "client-2"
    forged = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    with pytest.raises(links.LinkError) as e:
        links.verify(f"{forged}.{sig}", "checkin", t0)
    assert e.value.code == "bad_signature"


def test_secret_required_in_production(monkeypatch):
    monkeypatch.delenv("NOTIFY_LINK_SECRET", raising=False)
    monkeypatch.setenv("API_ENV", "production")
    with pytest.raises(RuntimeError):
        links.sign("stop", {}, timedelta(hours=1))


def test_rate_limiter_window():
    rl = RateLimiter(2, 10)
    assert rl.allow("k", 0) and rl.allow("k", 1)
    assert not rl.allow("k", 2)
    assert rl.allow("other", 2)
    assert rl.allow("k", 12)


# ------------------------------------------------------------ template sandbox
@pytest.mark.parametrize("src", [
    "{{ 'a' * 99999999 }}", "{{ name.__class__ }}", "{{ name.upper() }}",
    "{{ range(3) }}", "{{ ''.__class__.__mro__ }}", "{% macro m() %}x{% endmacro %}",
    "{% import 'x' as y %}", "{% include 'x' %}", "{{ cycler }}", "{{ config }}",
    "{% for a in items %}{% for b in items %}{% for c in items %}x{% endfor %}"
    "{% endfor %}{% endfor %}", "{{ _private }}", "{{ 2 ** 99 }}", "{% set a = 1 %}",
    "{{ nothing_defined }}", "{{ name | center(100000000) }}", "{{ name | tojson }}",
    "{% if %}", "x" * 3001,
])
def test_sandbox_rejects(src):
    with pytest.raises(TemplateError):
        render_text(src, SAMPLE_CONTEXT)


def test_sandbox_allows_the_intended_subset():
    out = render_text("Hi {{ name | title }}: {% for i in items %}[{{ i }}]{% endfor %}"
                      "{% if day > 3 %} late{% endif %} {{ items | length }}", SAMPLE_CONTEXT)
    assert out.startswith("Hi Asha: [Light a mustard oil lamp]") and out.endswith("2")


def test_subject_must_be_one_line_and_body_non_empty():
    with pytest.raises(TemplateError):
        validate_template("a\nb", "ok")
    with pytest.raises(TemplateError):
        validate_template("a", "   ")


def test_defaults_valid_both_languages_with_advisory_and_stop():
    for (kind, lang), (subj, body) in DEFAULTS.items():
        validate_template(subj, body)
        r = render_message(kind, "email", lang, SAMPLE_CONTEXT, "https://x.test/stop/T")
        assert "https://x.test/stop/T" in r.body and "STOP" in r.body
        assert ("not medical" in r.body) if lang == "en" else ("सलाह नहीं" in r.body)
        assert r.subject and "\n" not in r.subject
    assert {lang for _, lang in DEFAULTS} == {"en", "hi"}


def test_footer_cannot_be_removed_by_an_override():
    r = render_message("remedy_due", "email", "en", SAMPLE_CONTEXT, "https://x.test/s",
                       {("remedy_due", "*", "en"): ("S", "Just this")})
    assert r.source == "practice" and r.body.startswith("Just this")
    assert "https://x.test/s" in r.body and "not medical" in r.body


def test_channel_specific_override_wins_and_sms_has_no_subject():
    ov = {("remedy_due", "*", "en"): ("Gen", "general"), ("remedy_due", "sms", "en"): ("S", "short")}
    assert render_message("remedy_due", "sms", "en", SAMPLE_CONTEXT, "u", ov).body.startswith("short")
    assert render_message("remedy_due", "sms", "en", SAMPLE_CONTEXT, "u", ov).subject is None
    assert render_message("remedy_due", "email", "en", SAMPLE_CONTEXT, "u", ov).subject == "Gen"


# ------------------------------------------------------------------ channels
def test_console_channel_never_leaves_process_and_masks(caplog):
    ch = channels.ConsoleChannel("email")
    with caplog.at_level("INFO", logger="app.notify.channels"):
        res = ch.send(channels.Message("someone@example.test", "secret body", "S"))
    assert res.provider == "console" and ch.sent[0].body == "secret body"
    assert "someone@example.test" not in caplog.text and "secret body" not in caplog.text


def test_backend_selection(monkeypatch):
    monkeypatch.delenv("NOTIFY_EMAIL_BACKEND", raising=False)
    assert channels.get_channel("email").name == "console"
    monkeypatch.setenv("NOTIFY_WHATSAPP_BACKEND", "gupshup")
    with pytest.raises(RuntimeError):
        channels.get_channel("whatsapp")
    monkeypatch.setenv("NOTIFY_EMAIL_BACKEND", "smtp")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    with pytest.raises(RuntimeError):
        channels.get_channel("email")


def test_smtp_message_has_unsubscribe_header():
    ch = channels.SmtpEmailChannel("localhost")
    m = ch.build(channels.Message("a@b.test", "hi", "Sub", unsubscribe_url="https://x/stop"))
    assert m["List-Unsubscribe"] == "<https://x/stop>" and m["Subject"] == "Sub"
