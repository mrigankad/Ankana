"""Reference-chart runner: compute a chart with a provider and compare to expected values."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from nakshatra_core.dasha_vimshottari import compute_vimshottari
from nakshatra_core.providers import get_provider
from nakshatra_core.providers.base import Ephemeris
from nakshatra_core.time import to_utc_datetime

HERE = Path(__file__).parent
CASES_DIR = HERE / "cases"
BODIES = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")
ARCSEC = 3600.0

# Proposed in Ankana Research/02-engine.md. Units: arcseconds, seconds, days.
TOLERANCES = {
    "planet": 5.0,
    "moon": 10.0,
    "ascendant": 10.0,
    "ayanamsa": 1.0,
    "mean_node": 1.0,
    "true_node": 10.0,
    "sunrise_s": 5.0,
    "dasha_days": 0.0,  # exact calendar date
}


def load_cases() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES_DIR.glob("*.json"))]


def birth_utc(case: dict) -> datetime:
    i = case["input"]
    return to_utc_datetime(i["birthDate"], i["birthTime"], i["timezoneName"])


def _gap(a: float, b: float) -> float:
    """Signed shortest angular difference a - b in degrees."""
    return (a - b + 180) % 360 - 180


def compute(case: dict, provider: Ephemeris, sunrise_rule: str | None = None) -> dict:
    """Same shape as case['expected'], computed by `provider` under the case settings."""
    s, i = case["settings"], case["input"]
    utc = birth_utc(case)
    aya = provider.ayanamsa(utc, s["ayanamsa"])
    planets = {b: (provider.planet(b, utc).longitude - aya) % 360 for b in BODIES}
    planets["rahu"] = (provider.lunar_node(utc, s["node"]) - aya) % 360
    planets["ketu"] = (planets["rahu"] + 180) % 360
    angles = provider.angles(utc, i["latitude"], i["longitude"])
    rule = sunrise_rule or (s["sunriseRule"] if s["sunriseRule"] in provider.sunrise_rules
                            else "standard")
    rise, sett = provider.sunrise_sunset(utc, i["latitude"], i["longitude"], rule)
    return {
        "ayanamsa": aya,
        "planets": planets,
        "ascendant": (angles.ascendant - aya) % 360,
        "midheaven": (angles.midheaven - aya) % 360,
        "sunrise": rise.isoformat(),
        "sunset": sett.isoformat(),
        "vimshottariStarts": vimshottari_starts(planets["moon"], utc),
    }


def vimshottari_starts(moon_sidereal: float, utc: datetime) -> list[dict]:
    out = compute_vimshottari(moon_sidereal, utc)
    return [{"planet": m["planet"], "start": m["start"][:10]} for m in out["mahadashas"]]


def dasha_start_instants(moon_sidereal: float, utc: datetime) -> list[datetime]:
    out = compute_vimshottari(moon_sidereal, utc)
    return [datetime.fromisoformat(m["start"].replace("Z", "+00:00")) for m in out["mahadashas"]]


@dataclass
class Deviation:
    field: str
    value: float
    tolerance: float
    unit: str

    @property
    def ok(self) -> bool:
        return abs(self.value) <= self.tolerance


def compare(case: dict, actual: dict) -> list[Deviation]:
    exp, s = case["expected"], case["settings"]
    devs = [Deviation("ayanamsa", _gap(actual["ayanamsa"], exp["ayanamsa"]) * ARCSEC,
                      TOLERANCES["ayanamsa"], "arcsec")]
    for b, lon in exp["planets"].items():
        if b == "ketu":
            continue
        if b == "rahu":
            tol = TOLERANCES["mean_node"] if s["node"] == "mean" else TOLERANCES["true_node"]
        else:
            tol = TOLERANCES["moon"] if b == "moon" else TOLERANCES["planet"]
        devs.append(Deviation(b, _gap(actual["planets"][b], lon) * ARCSEC, tol, "arcsec"))
    devs.append(Deviation("ascendant", _gap(actual["ascendant"], exp["ascendant"]) * ARCSEC,
                          TOLERANCES["ascendant"], "arcsec"))
    for key in ("sunrise", "sunset"):
        secs = (datetime.fromisoformat(actual[key]) - datetime.fromisoformat(exp[key])
                ).total_seconds()
        devs.append(Deviation(key, secs, TOLERANCES["sunrise_s"], "s"))
    for e, a in zip(exp["vimshottariStarts"], actual["vimshottariStarts"], strict=True):
        days = (datetime.fromisoformat(a["start"]).replace(tzinfo=UTC)
                - datetime.fromisoformat(e["start"]).replace(tzinfo=UTC)).days
        devs.append(Deviation(f"dasha_{e['planet']}", float(days), TOLERANCES["dasha_days"],
                              "days"))
    return devs


def run(provider_name: str) -> dict[str, list[Deviation]]:
    provider = get_provider(provider_name)
    return {c["id"]: compare(c, compute(c, provider)) for c in load_cases()}
