"""Shared rate limiter for public endpoints.

Counters live in Postgres (`rate_limit_bucket`), so every API replica and worker sees the
same count; the per-process limiter it replaces gave each replica its own allowance.
Sliding-window counter: one statement per hit upserts the current window's count
(`INSERT ... ON CONFLICT DO UPDATE`, atomic, no read-then-write race) and reads the
previous window's, weighting it by how much of it still lies inside the last `window`
seconds (no burst of 2x the limit at a window edge). Keys are hashed with the scope before storage, so no
IP address or token sits in the table.

If the database is unavailable the limiter fails open to an in-process sliding window
(never to "allow everything"), and counts the event in the `ankana.ratelimit.fallback`
metric. With no Postgres engine (legacy SQLite mode) the in-process window is used.
"""

from __future__ import annotations

import hashlib
import logging
import random
import time as _time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.engine import Engine

log = logging.getLogger("ankana.ratelimit")

_HIT = text("""
    WITH cur AS (
        INSERT INTO rate_limit_bucket (key_hash, window_start, hits)
        VALUES (:k, to_timestamp(floor(extract(epoch FROM now()) / CAST(:w AS numeric))
                                 * CAST(:w AS numeric)), 1)
        ON CONFLICT (key_hash, window_start) DO UPDATE SET hits = rate_limit_bucket.hits + 1
        RETURNING hits, window_start
    )
    SELECT cur.hits,
           CAST(:w AS numeric) - (extract(epoch FROM now()) % CAST(:w AS numeric)),
           coalesce((SELECT p.hits FROM rate_limit_bucket p WHERE p.key_hash = :k
                     AND p.window_start = cur.window_start - make_interval(secs => :w)), 0)
    FROM cur
""")
_PRUNE = text("DELETE FROM rate_limit_bucket WHERE window_start < now() - make_interval(secs => :s)")


class MemoryWindow:
    """Sliding window per process: the fallback when Postgres is not available."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit, self.window = limit, window
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = _time.monotonic() if now is None else now
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        if len(self.hits) > 10000:  # bound memory under a key spray
            for k in [k for k, v in self.hits.items() if not v or now - v[-1] > self.window]:
                self.hits.pop(k, None)
        return True


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after: int = 0
    hits: int = 0


class SharedRateLimiter:
    def __init__(self, scope: str, limit: int, window: int = 60) -> None:
        self.scope, self.limit, self.window = scope, limit, window
        self._fallback = MemoryWindow(limit, window)

    def _hash(self, key: str) -> str:
        return hashlib.sha256(f"{self.scope}|{key}".encode()).hexdigest()

    def check(self, engine: Engine | None, key: str) -> Decision:
        if engine is None:
            return self._memory(key)
        try:
            with engine.begin() as conn:
                cur, retry, prev = conn.execute(
                    _HIT, {"k": self._hash(key), "w": self.window}).one()
                if random.random() < 0.005:  # opportunistic cleanup, ~1 in 200 hits
                    conn.execute(_PRUNE, {"s": max(3600, self.window * 10)})
        except Exception as exc:
            log.warning("rate limit store unavailable (%s); using in-process window",
                        exc.__class__.__name__)
            _count_fallback(self.scope)
            return self._memory(key)
        # sliding-window estimate: the previous window counts for the part still in range
        estimate = int(cur) + float(prev) * float(retry) / self.window
        ok = estimate <= self.limit
        _count_decision(self.scope, ok)
        return Decision(ok, 0 if ok else max(1, int(retry)), int(estimate))

    def _memory(self, key: str) -> Decision:
        ok = self._fallback.allow(key)
        _count_decision(self.scope, ok)
        return Decision(ok, 0 if ok else int(self.window))

    def allow(self, engine: Engine | None, key: str) -> bool:
        return self.check(engine, key).allowed

    def reset(self) -> None:
        self._fallback.hits.clear()


def clear(engine: Engine) -> None:
    """Drop every counter (tests, incident response)."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM rate_limit_bucket"))


def prune(engine: Engine, older_than_seconds: int = 86400) -> int:
    with engine.begin() as conn:
        return conn.execute(_PRUNE, {"s": older_than_seconds}).rowcount


def client_ip(request: Request) -> str:
    """Client address. Behind a proxy (AUTH_TRUST_PROXY=1) the last X-Forwarded-For hop,
    the one our own proxy appended, never a value the caller could have chosen."""
    cfg = getattr(getattr(request.app.state, "auth", None), "cfg", None)
    fwd = request.headers.get("x-forwarded-for")
    if cfg is not None and getattr(cfg, "trust_proxy", False) and fwd:
        return fwd.split(",")[-1].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def _count_decision(scope: str, allowed: bool) -> None:
    try:
        from . import metrics

        metrics.rate_limit_decisions.add(1, {"scope": scope, "result": "allowed" if allowed
                                             else "limited"})
    except Exception:  # metrics must never break a request
        pass


def _count_fallback(scope: str) -> None:
    try:
        from . import metrics

        metrics.rate_limit_fallbacks.add(1, {"scope": scope})
    except Exception:
        pass


def limit_dependency(limiter: SharedRateLimiter):
    """FastAPI dependency: 429 problem+json with Retry-After when the caller's IP is over
    the limit for this scope."""
    from fastapi import HTTPException

    def _dep(request: Request) -> None:
        d = limiter.check(getattr(request.app.state, "pg_engine", None), client_ip(request))
        if not d.allowed:
            raise HTTPException(
                status_code=429, detail="Too many requests. Slow down and try again shortly.",
                headers={"Retry-After": str(d.retry_after or limiter.window)})

    return _dep
