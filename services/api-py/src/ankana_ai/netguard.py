"""Outbound HTTP that cannot be aimed at internal addresses (SSRF guard).

Checking a hostname at configuration time is not enough: the name can resolve to
a public address then and to 127.0.0.1 or 169.254.169.254 when the request is
made (DNS rebinding), or be written as a decimal/octal IP that the URL parser
does not recognise. GuardedTransport resolves the host itself for every request,
refuses anything that is not a globally routable unicast address, then connects
to that exact IP (the request keeps its Host header and TLS SNI, so certificate
checks still run against the original name). There is no second lookup to race.
Redirects stay off (httpx default); callers must not enable them.
"""

from __future__ import annotations

import ipaddress
import socket

import httpx


class NetGuardError(httpx.TransportError):
    """The destination is not a public address."""


def is_public_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def resolve_public(host: str, port: int) -> str:
    """The IP to connect to for `host`, or NetGuardError when any answer is non-public."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise NetGuardError(f"cannot resolve {host}") from exc
    addrs = [i[4][0] for i in infos]
    if not addrs:
        raise NetGuardError(f"cannot resolve {host}")
    if not all(is_public_ip(a) for a in addrs):
        raise NetGuardError("destination resolves to a non-public address")
    return addrs[0]


class GuardedTransport(httpx.BaseTransport):
    def __init__(self, inner: httpx.BaseTransport | None = None) -> None:
        self._inner = inner or httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        ip = resolve_public(host, port)
        request.extensions = {**request.extensions, "sni_hostname": host}
        request.url = request.url.copy_with(host=ip)
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


def guarded_client(timeout: float = 10.0, inner: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(transport=GuardedTransport(inner), timeout=timeout, follow_redirects=False)
