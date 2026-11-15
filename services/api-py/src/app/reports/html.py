"""Server-side HTML for the PDF report (Jinja2, autoescaped).

Deterministic: the same artifact, options, branding and `generated_at`
produce byte-identical HTML. The page is fully self-contained (fonts and logo
are data: URIs, no scripts) because Chromium renders it with network and
JavaScript disabled.
"""

from __future__ import annotations

import base64
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .branding import Branding
from .i18n import LABELS, PLANETS, SIGNS
from .kundali import south_indian_svg

TEMPLATE_VERSION = "1"
TEMPLATES = {"standard": "report.html.j2"}
ALL_SECTIONS = ("summary", "kundali", "planets", "houses", "yogas", "dasha", "vargas",
                "panchang", "reading", "lal_kitab", "remedies")
DEFAULT_SECTIONS = ("summary", "kundali", "planets", "houses", "yogas", "dasha", "panchang",
                    "remedies")

_HERE = Path(__file__).parent
_env = Environment(loader=FileSystemLoader(_HERE / "templates"),
                   autoescape=select_autoescape(["html", "j2"]), trim_blocks=True,
                   lstrip_blocks=True)


@lru_cache(maxsize=4)
def _font_css(lang: str) -> str:
    def face(family: str, file: str, weights: str, stretch: str = "") -> str:
        data = base64.b64encode((_HERE / "assets" / file).read_bytes()).decode()
        return (f"@font-face{{font-family:'{family}';font-weight:{weights};{stretch}"
                f"src:url(data:font/ttf;base64,{data}) format('truetype');}}")

    css = face("Urbanist", "Urbanist-VF.ttf", "100 900")
    if lang == "hi":
        css += face("Noto Sans Devanagari", "NotoSansDevanagari-VF.ttf", "100 900",
                    "font-stretch:62.5% 100%;")
    return css


def _fmt_date(iso: str) -> str:
    return iso[:10]


def build_context(*, artifact: dict, client_name: str, branding: Branding, language: str,
                  sections: list[str], generated_at: datetime, logo_data_uri: str | None,
                  reading: dict | None, remedies: list[dict] | None,
                  lal_kitab: dict | None) -> dict:
    L = LABELS[language]
    meta = artifact["calculationMetadata"]
    asc = artifact["ascendant"]
    moon = next(p for p in artifact["planets"] if p["planet"] == "moon")
    now = generated_at
    mahadashas = []
    for m in artifact.get("vimshottari", {}).get("mahadashas", []):
        mahadashas.append({
            "planet": PLANETS[language][m["planet"]], "start": _fmt_date(m["start"]),
            "end": _fmt_date(m["end"]),
            "current": m["start"] <= now.strftime("%Y-%m-%dT%H:%M:%S") < m["end"],
        })
    return {
        "lang": language, "L": L, "branding": branding, "logo": logo_data_uri,
        "font_css": _font_css(language), "sections": sections,
        "client_name": client_name, "generated": generated_at.strftime("%Y-%m-%d"),
        "input": meta["input"], "ayanamsa": meta["ayanamsa"], "engine_version":
        meta["engineVersion"], "asc_sign": SIGNS[language][asc["signIndex"]], "asc": asc,
        "moon_sign": SIGNS[language][moon["signIndex"]], "moon": moon,
        "planet_names": PLANETS[language], "sign_names": SIGNS[language],
        "planets": artifact["planets"], "houses": artifact["houses"],
        "yogas": [y for y in artifact.get("yogas", []) if y.get("present")],
        "mahadashas": mahadashas, "panchang": artifact.get("panchang"),
        "kundali_svg": south_indian_svg(artifact, language, branding.primary)
        if "kundali" in sections else "",
        "reading": reading, "remedies": remedies or [], "lal_kitab": lal_kitab,
        "birth_star": artifact.get("vimshottari", {}).get("birthNakshatra"),
    }


def render_html(template: str, context: dict) -> str:
    return _env.get_template(TEMPLATES[template]).render(**context)
