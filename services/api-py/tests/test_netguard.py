"""SSRF guard: DNS rebinding, odd IP encodings, redirects (docs/security-review.md)."""

import socket

import httpx
import pytest

from ankana_ai import netguard
from ankana_ai.netguard import NetGuardError, guarded_client, is_public_ip
from app.reports.branding import BrandingError, logo_data_uri


def fake_dns(monkeypatch, answers):
    """answers: list of IP lists returned by successive getaddrinfo calls."""
    calls = []

    def getaddrinfo(host, port, *a, **k):
        calls.append(host)
        ips = answers[min(len(calls) - 1, len(answers) - 1)]
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "",
                 (ip, port)) for ip in ips]

    monkeypatch.setattr(netguard.socket, "getaddrinfo", getaddrinfo)
    return calls


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "100.64.0.1", "0.0.0.0",
    "::1", "fe80::1", "fd00::1", "::ffff:127.0.0.1", "::ffff:10.0.0.1", "224.0.0.1",
])
def test_non_public_ips_are_refused(ip):
    assert not is_public_ip(ip)


def test_public_ips_pass():
    assert is_public_ip("93.184.216.34") and is_public_ip("2606:2800:220:1::1")


def test_connects_to_the_validated_ip_and_keeps_host_and_sni(monkeypatch):
    fake_dns(monkeypatch, [["93.184.216.34"]])
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["host"] = str(request.url), request.headers["host"]
        seen["sni"] = request.extensions.get("sni_hostname")
        return httpx.Response(200, content=b"ok")

    with guarded_client(inner=httpx.MockTransport(handler)) as c:
        assert c.get("https://logo.example.test/a.png").content == b"ok"
    assert seen["url"].startswith("https://93.184.216.34/")
    assert seen["host"] == "logo.example.test" and seen["sni"] == "logo.example.test"


def test_dns_rebinding_second_answer_is_never_used(monkeypatch):
    """First lookup public, later lookups private: the request must go to the public IP
    from the single lookup the guard made (no second resolution to race)."""
    calls = fake_dns(monkeypatch, [["93.184.216.34"], ["127.0.0.1"]])
    hit = []
    with guarded_client(inner=httpx.MockTransport(
            lambda r: hit.append(r.url.host) or httpx.Response(200))) as c:
        c.get("https://rebind.example.test/")
    assert hit == ["93.184.216.34"] and len(calls) == 1


def test_private_answer_blocks_the_request(monkeypatch):
    fake_dns(monkeypatch, [["10.1.2.3"]])
    with guarded_client(inner=httpx.MockTransport(lambda r: httpx.Response(200))) as c:
        with pytest.raises(NetGuardError):
            c.get("https://evil.example.test/")


def test_mixed_answers_are_refused(monkeypatch):
    fake_dns(monkeypatch, [["93.184.216.34", "169.254.169.254"]])
    with guarded_client(inner=httpx.MockTransport(lambda r: httpx.Response(200))) as c:
        with pytest.raises(NetGuardError):
            c.get("https://mixed.example.test/")


def test_decimal_ip_host_is_resolved_and_refused(monkeypatch):
    # 2130706433 == 127.0.0.1; the OS resolver accepts it, ipaddress.ip_address() does not.
    fake_dns(monkeypatch, [["127.0.0.1"]])
    with guarded_client(inner=httpx.MockTransport(lambda r: httpx.Response(200))) as c:
        with pytest.raises(NetGuardError):
            c.get("https://2130706433/")


def test_logo_fetch_does_not_follow_redirects(monkeypatch):
    fake_dns(monkeypatch, [["93.184.216.34"]])
    t = httpx.MockTransport(lambda r: httpx.Response(302, headers={"location": "http://169.254.169.254/"}))
    with pytest.raises(BrandingError):
        logo_data_uri("https://logo.example.test/a.png", transport=t)


def test_logo_fetch_happy_path_and_rebinding(monkeypatch):
    fake_dns(monkeypatch, [["93.184.216.34"], ["127.0.0.1"]])
    t = httpx.MockTransport(lambda r: httpx.Response(
        200, headers={"content-type": "image/png"}, content=b"\x89PNG"))
    assert logo_data_uri("https://logo.example.test/a.png", transport=t).startswith(
        "data:image/png;base64,")


def test_logo_private_resolution_is_a_branding_error(monkeypatch):
    fake_dns(monkeypatch, [["10.0.0.1"]])
    with pytest.raises(BrandingError):
        logo_data_uri("https://logo.example.test/a.png",
                      transport=httpx.MockTransport(lambda r: httpx.Response(200)))


# ------------------------------------------------------------ AI connection base URLs
def test_base_url_rejects_numeric_host_encodings_and_cgnat(monkeypatch):
    from ankana_ai import connections as cx

    monkeypatch.delenv("ANKANA_ALLOW_LOCAL_PROVIDERS", raising=False)
    for bad in ("https://2130706433/v1", "https://0x7f.1/v1", "https://100.64.0.1/v1",
                "https://[::ffff:127.0.0.1]/v1", "https://[::1]/v1", "https://10.0.0.1/v1"):
        with pytest.raises(ValueError):
            cx.validate_base_url(bad, "openai_compatible")
    assert cx.validate_base_url("https://api.groq.com/openai/v1", "openai_compatible")


def test_hosted_providers_use_the_guarded_transport(monkeypatch):
    from ankana_ai import connections as cx

    monkeypatch.delenv("ANKANA_ALLOW_LOCAL_PROVIDERS", raising=False)
    p = cx.build_provider("openai_compatible", base_url="https://api.groq.com/openai/v1",
                          api_key="k")
    assert isinstance(p.http._transport, netguard.GuardedTransport)
    fake_dns(monkeypatch, [["127.0.0.1"]])  # a name that resolves to loopback at call time
    from ankana_ai.providers import ProviderRequest

    with pytest.raises(Exception) as exc:
        p.complete(ProviderRequest(model="m", system="s", chart_context="", messages=[
            {"role": "user", "content": "hi"}], tools=[], max_tokens=5))
    assert "non-public" in str(exc.value) or "Could not reach" in str(exc.value)


def test_self_hosted_may_use_local_urls(monkeypatch):
    from ankana_ai import connections as cx

    monkeypatch.setenv("ANKANA_ALLOW_LOCAL_PROVIDERS", "1")
    assert cx.validate_base_url("http://localhost:1234/v1", "openai_compatible")
    p = cx.build_provider("openai_compatible", base_url="http://localhost:1234/v1")
    assert not isinstance(p.http._transport, netguard.GuardedTransport)
