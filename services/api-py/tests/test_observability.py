import logging

from app.observability import JsonFormatter, PracticeFilter, scrub_attributes, set_practice


def test_scrub_removes_pii_and_query_strings():
    clean = scrub_attributes(
        {
            "http.url": "http://x/api/v1/locations/search?q=Raiganj",
            "http.route": "/api/v1/locations/search",
            "birthDate": "2003-08-29",
            "client.full_name": "A B",
            "http.request.body": "{...}",
            "practice_id": "p1",
        }
    )
    assert clean["http.url"] == "http://x/api/v1/locations/search"
    assert "birthDate" not in clean and "client.full_name" not in clean
    assert "http.request.body" not in clean
    assert clean["practice_id"] == "p1"


def test_logs_carry_practice_id():
    pid = "11111111-1111-1111-1111-111111111111"
    set_practice(pid)
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello", None, None)
    PracticeFilter().filter(record)
    assert pid in JsonFormatter().format(record)


def test_scrub_redacts_invite_tokens_in_url_paths():
    from app.observability import scrub_attributes

    out = scrub_attributes({
        "http.url": "http://x/v1/auth/invites/SeCrEtToKeN123/accept?a=1",
        "http.target": "/v1/auth/invites/SeCrEtToKeN123"})
    assert "SeCrEtToKeN123" not in str(out) and "<redacted>" in out["http.url"]
    assert out["http.url"].endswith("/invites/<redacted>/accept")
