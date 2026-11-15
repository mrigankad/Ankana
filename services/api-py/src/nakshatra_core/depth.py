"""Chart depth views: derived facts the stored artifact implies but does not spell out.

Pure functions over a stored `VedicChartArtifact` payload (no ephemeris call), each fact
paired with a `proof` (inputs, rule id, classical source) so a UI can show how it was
derived. Rule ids are stable keys; the web app owns the human wording.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .ashtakavarga import _BENEFIC_PLACES, _CONTRIBUTORS, ASHTAKAVARGA_PLANETS
from .dasha_vimshottari import VIMSHOTTARI_TOTAL_YEARS, VIMSHOTTARI_YEARS
from .dasha_yogini import YOGINI_CYCLE_YEARS, YOGINIS
from .dignities import _COMBUSTION_ORBS
from .ephemeris import normalize_degrees
from .zodiac import (
    NAKSHATRA_LORD_CYCLE,
    SIGN_LORDS,
    SIGN_NAMES,
    is_odd_sign,
    nakshatra_of,
)

SARVA_HIGH = 28  # a sign at or above the 28-bindu average is strong
SARVA_LOW = 25   # at or below 25 is weak
BHINNA_HIGH = 5
BHINNA_LOW = 2

CHARA_KARAKAS = (
    ("atmakaraka", "AK"), ("amatyakaraka", "AmK"), ("bhratrikaraka", "BK"),
    ("matrikaraka", "MK"), ("putrakaraka", "PK"), ("gnatikaraka", "GK"),
    ("darakaraka", "DK"),
)
_KARAKA_PLANETS = ("sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn")
BALADI = ("bala", "kumara", "yuva", "vriddha", "mrita")

_MS_YEAR = 365.2425 * 86_400_000


def _inp(key: str, value: object) -> dict:
    return {"key": key, "value": value}


def _proof(rule_id: str, source: str, *inputs: dict) -> dict:
    return {"rule_id": rule_id, "source": source, "inputs": list(inputs)}


def baladi_avastha(sign_index: int, degrees_in_sign: float) -> str:
    """Five-fold age state: 6 degree slices, in order for odd signs and reversed for even."""
    slot = min(int(degrees_in_sign // 6), 4)
    return BALADI[slot] if is_odd_sign(sign_index) else BALADI[4 - slot]


def chara_karakas(planets: list[dict]) -> dict[str, str]:
    """Jaimini seven-karaka scheme: Sun to Saturn ranked by degrees within sign, highest first."""
    ranked = sorted((p for p in planets if p["planet"] in _KARAKA_PLANETS),
                    key=lambda p: -p["degreesInSign"])
    return {p["planet"]: CHARA_KARAKAS[i][0] for i, p in enumerate(ranked)}


def planet_depth(artifact: dict) -> dict:
    planets = artifact["planets"]
    houses = artifact["houses"]
    asc_sign = artifact["ascendant"]["signIndex"]
    sun = next(p for p in planets if p["planet"] == "sun")
    karakas = chara_karakas(planets)
    rank = {name: i for i, (name, _ab) in enumerate(CHARA_KARAKAS)}
    rows = []
    for p in planets:
        name = p["planet"]
        lon = p["siderealLongitude"]
        nak = nakshatra_of(lon)
        is_node = name in ("rahu", "ketu")
        lord_of = [h["number"] for h in houses if h["lord"] == name]

        if name in _COMBUSTION_ORBS:
            sep = min(normalize_degrees(lon - sun["siderealLongitude"]),
                      normalize_degrees(sun["siderealLongitude"] - lon))
            orb = _COMBUSTION_ORBS[name][1 if p["retrograde"] else 0]
            combust = {"applicable": True, "is_combust": sep <= orb,
                       "separation": round(sep, 4), "orb": orb}
            cb_proof = _proof(
                "combust", "Classical combustion orbs, Brihat Parashara Hora Shastra",
                _inp("separation_from_sun", round(sep, 4)), _inp("orb", orb),
                _inp("retrograde", p["retrograde"]))
        else:
            combust = {"applicable": False, "is_combust": False, "separation": None, "orb": None}
            cb_proof = _proof("combust_na", "Brihat Parashara Hora Shastra, rashi and nakshatra divisions", _inp("planet", name))

        avastha = None if is_node else baladi_avastha(p["signIndex"], p["degreesInSign"])
        slot = None if avastha is None else min(int(p["degreesInSign"] // 6), 4) + 1
        karaka = karakas.get(name)
        sign_lord = SIGN_LORDS[p["signIndex"]]
        rows.append({
            "planet": name,
            "sign": p["signName"], "sign_index": p["signIndex"],
            "degrees_in_sign": round(p["degreesInSign"], 4),
            "longitude": round(lon, 4),
            "house": p["house"],
            "nakshatra": nak.name, "nakshatra_index": nak.index + 1, "pada": nak.pada,
            "nakshatra_lord": nak.lord, "sign_lord": sign_lord,
            "retrograde": p["retrograde"],
            "combust": combust,
            "dignity": p["dignity"],
            "avastha": avastha,
            "karaka": karaka,
            "karaka_abbr": None if karaka is None else CHARA_KARAKAS[rank[karaka]][1],
            "lord_of_houses": lord_of,
            "proof": {
                "nakshatra": _proof(
                    "nakshatra", "Brihat Parashara Hora Shastra, rashi and nakshatra divisions",
                    _inp("sidereal_longitude", round(lon, 4)), _inp("span_degrees", "13.3333"),
                    _inp("nakshatra_number", nak.index + 1),
                    _inp("fraction_traversed", round(nak.fraction_traversed, 4))),
                "pada": _proof(
                    "pada", "Brihat Parashara Hora Shastra, rashi and nakshatra divisions",
                    _inp("degrees_in_nakshatra", round(nak.fraction_traversed * 360 / 27, 4)),
                    _inp("pada_span_degrees", "3.3333"), _inp("pada", nak.pada)),
                "nakshatra_lord": _proof(
                    "nakshatra_lord", "Brihat Parashara Hora Shastra, Vimshottari dasha",
                    _inp("nakshatra_number", nak.index + 1),
                    _inp("cycle_position", nak.index % 9 + 1), _inp("lord", nak.lord)),
                "sign_lord": _proof(
                    "sign_lord", "Brihat Parashara Hora Shastra, rashi and nakshatra divisions",
                    _inp("sign", p["signName"]), _inp("lord", sign_lord)),
                "retrograde": _proof(
                    "retrograde", "Ephemeris speed sign; nodes are always retrograde",
                    _inp("planet", name), _inp("retrograde", p["retrograde"])),
                "combust": cb_proof,
                "dignity": _proof(
                    "dignity", "Brihat Parashara Hora Shastra, graha dignities",
                    _inp("sign", p["signName"]),
                    _inp("degrees_in_sign", round(p["degreesInSign"], 4)),
                    _inp("dignity", p["dignity"])),
                "avastha": _proof(
                    "avastha_na" if is_node else "avastha_baladi", "Brihat Parashara Hora Shastra, graha avasthas",
                    _inp("sign", p["signName"]),
                    _inp("sign_parity", "odd" if is_odd_sign(p["signIndex"]) else "even"),
                    _inp("degrees_in_sign", round(p["degreesInSign"], 4)),
                    _inp("slice", slot if slot is not None else "none")),
                "karaka": _proof(
                    "chara_karaka", "Jaimini Upadesha Sutras, chapter 1 (chara karakas)",
                    _inp("degrees_in_sign", round(p["degreesInSign"], 4)),
                    _inp("rank_among_seven", None if karaka is None else rank[karaka] + 1),
                    _inp("karaka", karaka)),
                "house_lordship": _proof(
                    "house_lordship", "Brihat Parashara Hora Shastra, bhava lordship",
                    _inp("lagna_sign", SIGN_NAMES[asc_sign]),
                    _inp("houses", ", ".join(map(str, lord_of)) or "none")),
            },
        })
    return {
        "lagna": {"sign": SIGN_NAMES[asc_sign], "sign_index": asc_sign,
                  "nakshatra": artifact["ascendant"]["nakshatra"],
                  "pada": artifact["ascendant"]["pada"]},
        "planets": rows,
    }


def ashtakavarga_depth(artifact: dict) -> dict:
    sm = artifact["strengthMetrics"]
    asc = artifact["ascendant"]["signIndex"]
    pos = {p["planet"]: p["signIndex"] for p in artifact["planets"]}
    bhinna = []
    for row in sm["ashtakavarga"]:
        target = row["planet"]
        contributors: list[list[str]] = []
        for sign in range(12):
            names = []
            for c in _CONTRIBUTORS:
                src = asc if c == "lagna" else pos[c]
                if ((sign - src) % 12) + 1 in _BENEFIC_PLACES[target][c]:
                    names.append(c)
            contributors.append(names)
        bhinna.append({
            "planet": target, "bindus_by_sign": row["bindusBySign"],
            "total": row["totalBindus"], "contributors": contributors,
            "sign_of_planet": pos[target],
        })
    sarva = sm["sarvashtakavarga"]
    return {
        "lagna_sign_index": asc,
        "sign_names": list(SIGN_NAMES),
        "bhinna": bhinna,
        "sarva": sarva,
        "sarva_total": sum(sarva),
        "thresholds": {"sarva_high": SARVA_HIGH, "sarva_low": SARVA_LOW,
                       "bhinna_high": BHINNA_HIGH, "bhinna_low": BHINNA_LOW},
        "planets_order": list(ASHTAKAVARGA_PLANETS),
        "proof": _proof(
            "ashtakavarga", "Brihat Parashara Hora Shastra, Ashtakavarga chapters",
            _inp("contributors", "Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Lagna"),
            _inp("lagna_sign", SIGN_NAMES[asc]), _inp("expected_total", 337)),
    }


def _ms(iso: str) -> float:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000


def _node(p: dict, asof_ms: float) -> dict:
    start = _ms(p["start"])
    end = _ms(p["end"])
    node = {
        "level": p["level"], "planet": p["planet"], "name": p.get("name"),
        "start": p["start"], "end": p["end"],
        "years": round((end - start) / _MS_YEAR, 4),
        "state": "current" if start <= asof_ms < end else ("past" if end <= asof_ms else "future"),
    }
    kids = p.get("children")
    if kids:
        node["children"] = [_node(c, asof_ms) for c in kids]
    return node


def dashas_depth(artifact: dict, system: str, asof: datetime | None = None) -> dict:
    if system not in ("vimshottari", "yogini"):
        raise ValueError("system must be vimshottari or yogini")
    when = asof or datetime.now(tz=UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    asof_ms = when.timestamp() * 1000
    if system == "vimshottari":
        src = artifact["vimshottari"]
        rule = {"id": "vimshottari", "source": "Brihat Parashara Hora Shastra, Vimshottari dasha",
                "total_years": VIMSHOTTARI_TOTAL_YEARS, "years": VIMSHOTTARI_YEARS,
                "year_length_days": 365.2425, "levels": 3}
        birth = {"nakshatra": src["birthNakshatra"], "lord": src["birthLord"]}
        lord_cycle = list(NAKSHATRA_LORD_CYCLE)
    else:
        src = artifact["yoginiDasha"]
        rule = {"id": "yogini", "source": "Yogini dasha, Brihat Parashara Hora Shastra tradition",
                "total_years": YOGINI_CYCLE_YEARS,
                "years": {y["name"]: y["years"] for y in YOGINIS},
                "year_length_days": 365.2425, "levels": 2}
        birth = {"nakshatra": src["birthNakshatra"], "lord": src["birthYogini"]}
        lord_cycle = [y["name"] for y in YOGINIS]
    mahas = [_node(m, asof_ms) for m in src["mahadashas"]]

    current: list[dict] = []
    level = mahas
    while level:
        cur = next((n for n in level if n["state"] == "current"), None)
        if cur is None:
            break
        current.append({k: cur[k] for k in ("level", "planet", "name", "start", "end")})
        level = cur.get("children") or []

    return {
        "system": system, "asof": when.isoformat().replace("+00:00", "Z"),
        "birth": birth, "balance_years": round(src["balanceYears"], 4),
        "rule": rule, "lord_cycle": lord_cycle,
        "current": current, "mahadashas": mahas,
    }
