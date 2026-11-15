"""Full Vedic chart artifact composer - port of chart.ts.

Emits the exact camelCase JSON shape of the TS `VedicChartArtifact` so the
existing web app and stored artifacts stay compatible.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from .ashtakavarga import compute_ashtakavarga, compute_sarvashtakavarga
from .aspects import compute_aspects, compute_conjunctions
from .boundaries import boundary_warnings
from .dasha_vimshottari import compute_vimshottari, iso_from_ms
from .dasha_yogini import compute_yogini
from .dignities import dignity_of, is_combust
from .ephemeris import SEVEN_BODIES, normalize_degrees
from .houses import house_of, whole_sign_houses
from .panchang import compute_panchang
from .provenance import calculation_provenance
from .providers import get_provider
from .shadbala import compute_shadbala
from .time import julian_day, to_utc_datetime
from .vargas import compute_varga_charts
from .vimshopaka import compute_vimshopaka
from .yogas import detect_yogas
from .zodiac import nakshatra_of, sign_of

ENGINE_VERSION = "py-1.0.0"


def _local_weekday(utc: datetime, timezone_name: str) -> int:
    local = utc.astimezone(ZoneInfo(timezone_name))
    return (local.weekday() + 1) % 7  # JS getDay(): Sunday = 0


def compute_vedic_chart_artifact(inp: dict) -> dict:
    utc = to_utc_datetime(inp["birthDate"], inp["birthTime"], inp["timezoneName"])
    provider = get_provider()
    ayanamsa_name = inp.get("ayanamsa", "lahiri")
    node_kind = inp.get("nodeType", "mean")
    ayanamsa_value = provider.ayanamsa(utc, ayanamsa_name)

    states = {body: provider.planet(body, utc) for body in SEVEN_BODIES}
    tropical: dict[str, float] = {body: st.longitude for body, st in states.items()}
    tropical["rahu"] = provider.lunar_node(utc, node_kind)
    tropical["ketu"] = normalize_degrees(tropical["rahu"] + 180)

    def to_sidereal(lon: float, _dt: datetime) -> float:
        return normalize_degrees(lon - ayanamsa_value)

    sidereal = {planet: to_sidereal(lon, utc) for planet, lon in tropical.items()}

    asc_sidereal = to_sidereal(
        provider.angles(utc, inp["latitude"], inp["longitude"]).ascendant, utc
    )
    asc_sign = sign_of(asc_sidereal)
    asc_nakshatra = nakshatra_of(asc_sidereal)

    planets = []
    for planet, lon in sidereal.items():
        sign = sign_of(lon)
        nakshatra = nakshatra_of(lon)
        retrograde = (
            True
            if planet in ("rahu", "ketu")
            else (False if planet in ("sun", "moon") else states[planet].speed < 0)
        )
        planets.append(
            {
                "planet": planet,
                "siderealLongitude": lon,
                "signIndex": sign.index,
                "signName": sign.name,
                "degreesInSign": sign.degrees_in_sign,
                "nakshatra": nakshatra.name,
                "pada": nakshatra.pada,
                "house": house_of(lon, asc_sidereal),
                "dignity": dignity_of(planet, lon),
                "retrograde": retrograde,
                "combust": (
                    False
                    if planet == "sun"
                    else is_combust(planet, tropical[planet], tropical["sun"], retrograde)
                ),
            }
        )

    houses = [
        {
            "number": house.number,
            "signIndex": house.sign_index,
            "signName": house.sign_name,
            "lord": house.lord,
            "occupants": [p["planet"] for p in planets if p["house"] == house.number],
        }
        for house in whole_sign_houses(asc_sidereal)
    ]

    planet_signs = {p["planet"]: p["signIndex"] for p in planets}

    # Vara runs sunrise to sunrise: use the weekday of the last sunrise at or
    # before birth (upgrade over the TS engine's calendar-weekday v1
    # approximation; identical for births after sunrise).
    sunrise, sunset = provider.sunrise_sunset(
        utc,
        inp["latitude"],
        inp["longitude"],
        "hindu" if "hindu" in provider.sunrise_rules else "standard",
    )
    panchang = compute_panchang(
        sidereal["sun"], sidereal["moon"], _local_weekday(sunrise, inp["timezoneName"])
    )

    ashtakavarga = compute_ashtakavarga(planet_signs, asc_sign.index)

    return {
        "calculationMetadata": {
            "engineVersion": ENGINE_VERSION,
            "system": "vedic",
            "ayanamsa": {"name": ayanamsa_name, "value": ayanamsa_value},
            "provenance": calculation_provenance(
                provider,
                ayanamsa_name=ayanamsa_name,
                ayanamsa_value=ayanamsa_value,
                node_type=node_kind,
            ),
            "utcDateTime": iso_from_ms(utc.timestamp() * 1000),
            "julianDay": julian_day(utc),
            "input": inp,
        },
        "ascendant": {
            "siderealLongitude": asc_sidereal,
            "signIndex": asc_sign.index,
            "signName": asc_sign.name,
            "degreesInSign": asc_sign.degrees_in_sign,
            "nakshatra": asc_nakshatra.name,
            "pada": asc_nakshatra.pada,
        },
        "planets": planets,
        "houses": houses,
        "panchang": {
            "tithi": {
                "index": panchang.tithi.index,
                "name": panchang.tithi.name,
                "paksha": panchang.tithi.paksha,
            },
            "karana": {"index": panchang.karana.index, "name": panchang.karana.name},
            "yoga": {"index": panchang.yoga.index, "name": panchang.yoga.name},
            "vara": {"index": panchang.vara.index, "name": panchang.vara.name},
            "moonNakshatra": {
                "index": panchang.moon_nakshatra.index,
                "name": panchang.moon_nakshatra.name,
                "pada": panchang.moon_nakshatra.pada,
            },
        },
        "vargas": compute_varga_charts(sidereal, asc_sidereal),
        "vimshottari": compute_vimshottari(sidereal["moon"], utc),
        "yoginiDasha": compute_yogini(sidereal["moon"], utc),
        "yogas": detect_yogas(
            {
                "longitudes": sidereal,
                "signs": planet_signs,
                "ascendantSign": asc_sign.index,
                "dignities": {p["planet"]: p["dignity"] for p in planets},
                "houseLords": [h["lord"] for h in houses],
            }
        ),
        "aspects": compute_aspects(planet_signs),
        "conjunctions": compute_conjunctions(planet_signs),
        "boundaryWarnings": boundary_warnings(sidereal, asc_sidereal),
        "sunrise": iso_from_ms(sunrise.timestamp() * 1000),
        "sunset": iso_from_ms(sunset.timestamp() * 1000),
        "strengthMetrics": {
            "shadbala": compute_shadbala(
                sidereal,
                asc_sidereal,
                normalize_degrees(sidereal["moon"] - sidereal["sun"]),
                {p["planet"]: p["retrograde"] for p in planets},
                next(p for p in planets if p["planet"] == "sun")["house"] >= 7,
            ),
            "ashtakavarga": ashtakavarga,
            "sarvashtakavarga": compute_sarvashtakavarga(ashtakavarga),
            "vimshopaka": compute_vimshopaka(sidereal),
        },
    }
