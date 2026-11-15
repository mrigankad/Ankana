"""Practice branding: validation and safe logo embedding.

The PDF is rendered by Chromium with all network access blocked, so a logo has
to be embedded as a data: URI. Fetching a user-supplied URL is an SSRF risk,
so only https is allowed, hosts resolving to private/loopback/link-local
addresses are refused, and size and content type are capped.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from ankana_ai.netguard import NetGuardError, guarded_client

COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_LOGO_BYTES = 1_000_000
ALLOWED_LOGO_TYPES = ("image/png", "image/jpeg", "image/svg+xml", "image/webp")
DEFAULT_PRIMARY = "#221e1d"
DEFAULT_ACCENT = "#d32704"


class BrandingError(ValueError):
    pass


@dataclass(frozen=True)
class Branding:
    name: str
    logo_url: str | None = None
    primary: str = DEFAULT_PRIMARY
    accent: str = DEFAULT_ACCENT
    footer: str | None = None

    def snapshot(self) -> dict:
        return {"name": self.name, "logo_url": self.logo_url, "primary": self.primary,
                "accent": self.accent, "footer": self.footer}

    @classmethod
    def from_snapshot(cls, d: dict) -> Branding:
        return cls(d["name"], d.get("logo_url"), d.get("primary") or DEFAULT_PRIMARY,
                   d.get("accent") or DEFAULT_ACCENT, d.get("footer"))


def validate_color(value: str | None) -> str | None:
    if value is None:
        return None
    if not COLOR_RE.match(value):
        raise BrandingError("colours must look like #RRGGBB")
    return value


def validate_logo_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("data:"):
        m = re.match(r"^data:(image/[a-z+]+);base64,", url)
        if not m or m.group(1) not in ALLOWED_LOGO_TYPES or len(url) > MAX_LOGO_BYTES * 4 // 3 + 64:
            raise BrandingError("logo data URI must be a base64 png/jpeg/svg/webp under 1 MB")
        return url
    if urlparse(url).scheme != "https":
        raise BrandingError("logo_url must be https or a data: URI")
    return url


def logo_data_uri(logo_url: str | None, transport: httpx.BaseTransport | None = None) -> str | None:
    """Return a data: URI for the logo, or None when absent. Raises
    BrandingError when the logo is unusable (the renderer then omits it)."""
    if not logo_url:
        return None
    if logo_url.startswith("data:"):
        return validate_logo_url(logo_url)
    validate_logo_url(logo_url)
    host = (urlparse(logo_url).hostname or "").lower()
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        raise BrandingError("logo host resolves to a non-public address")
    # The guarded client resolves the host once, refuses non-public answers and connects to
    # that IP (no rebinding window). No redirects: one could point at an internal address.
    try:
        with guarded_client(timeout=10, inner=transport) as client:
            with client.stream("GET", logo_url) as r:
                if r.status_code != 200:
                    raise BrandingError(f"logo fetch failed ({r.status_code})")
                ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
                if ctype not in ALLOWED_LOGO_TYPES:
                    raise BrandingError("logo must be png, jpeg, svg or webp")
                data = b""
                for chunk in r.iter_bytes():
                    data += chunk
                    if len(data) > MAX_LOGO_BYTES:
                        raise BrandingError("logo larger than 1 MB")
    except NetGuardError as exc:
        raise BrandingError(str(exc)) from exc
    except httpx.HTTPError as exc:
        raise BrandingError(f"logo fetch failed: {type(exc).__name__}") from exc
    return f"data:{ctype};base64,{base64.b64encode(data).decode()}"
