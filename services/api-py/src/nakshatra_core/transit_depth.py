"""Transit depth for the practitioner: the lifetime Sade Sati and dhaiya tracker, gochara
with ashtakavarga bindus and vedha, and the Jupiter plus Saturn double transit.

Everything is Parashari and read from the natal Moon (gochara) or the natal lagna (double
transit). Ashtakavarga is NOT recomputed here: the bindus come straight from the natal
chart payload (`strengthMetrics.ashtakavarga`, built by `ashtakavarga.compute_ashtakavarga`).

Sources, cited in the `proof` lines the API returns:
- Sade Sati: Saturn in the 12th, 1st and 2nd sign from the natal Moon. Dhaiya (small
  panoti): Saturn in the 4th (kantaka shani) or 8th (ashtama shani) from the Moon.
  Parashari gochara from the Moon (Phaladeepika ch. 26; BPHS gochara adhyaya).
- Gochara and vedha: the favourable houses from the Moon and their vedha (obstruction)
  houses, Phaladeepika ch. 26 / BPHS gochara adhyaya. Bindus: BPHS ashtakavarga adhyayas.
- Double transit: Jupiter and Saturn both occupying or casting graha drishti on a house
  (K. N. Rao's use of the two slow planets on top of Parashari drishti, BPHS ch. 26).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .aspects import _SPECIAL_ASPECTS
from .sky import _bisect, _retro, _sign, iso, sidereal
from .zodiac import SIGN_NAMES

GOCHARA_PLANETS = ("sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn")
ALL_BODIES = (*GOCHARA_PLANETS, "rahu", "ketu")

# Favourable houses from the natal Moon, and the vedha house that obstructs each
# (parallel tuples). Phaladeepika ch. 26.
GOCHARA_FAVOURABLE: dict[str, tuple[tuple[int, ...], tuple[int, ...]]] = {
    "sun": ((3, 6, 10, 11), (9, 12, 4, 5)),
    "moon": ((1, 3, 6, 7, 10, 11), (5, 9, 12, 2, 4, 8)),
    "mars": ((3, 6, 11), (12, 9, 5)),
    "mercury": ((2, 4, 6, 8, 10, 11), (5, 3, 9, 1, 8, 12)),
    "jupiter": ((2, 5, 7, 9, 11), (12, 4, 3, 10, 8)),
    "venus": ((1, 2, 3, 4, 5, 8, 9, 11, 12), (8, 7, 1, 10, 9, 5, 11, 6, 3)),
    "saturn": ((3, 6, 11), (12, 9, 5)),
}
# Father and son do not obstruct each other's gochara.
VEDHA_EXEMPT = frozenset({frozenset({"sun", "saturn"}), frozenset({"moon", "mercury"})})

BINDU_STRONG = 4   # a bhinna ashtakavarga count of 4 or more carries the result
BINDU_RESCUE = 5   # five or more softens an unfavourable house
SAV_STRONG = 28    # the sarvashtakavarga average per sign

_PHASE = {12: "rising", 1: "peak", 2: "setting"}
_DHAIYA = {4: "dhaiya_kantaka", 8: "dhaiya_ashtama"}

PROOF_SADE_SATI = (
    "Saturn in the 12th, 1st and 2nd sign from the natal Moon is Sade Sati; in the 4th "
    "(kantaka) or 8th (ashtama) it is dhaiya. Parashari gochara from the Moon "
    "(Phaladeepika ch. 26, BPHS gochara adhyaya). Dates are Saturn's sign ingresses, "
    "sidereal Lahiri, mean node not involved."
)
PROOF_GOCHARA = (
    "Favourable houses from the natal Moon with their vedha points (Phaladeepika ch. 26, "
    "BPHS gochara adhyaya); a favourable house is obstructed when another graha stands in "
    "its vedha house (Sun and Saturn, Moon and Mercury do not obstruct each other). Bindus "
    "are the planet's bhinna ashtakavarga count in the sign it occupies (BPHS ashtakavarga "
    "adhyaya): 4 or more carries the result, 5 or more softens an unfavourable house."
)
PROOF_DOUBLE = (
    "Jupiter and Saturn both occupying or casting graha drishti on a house (Jupiter 5, 7, 9; "
    "Saturn 3, 7, 10 signs counted inclusively) mark a house as active for events: K. N. "
    "Rao's double transit, built on Parashari drishti (BPHS ch. 26)."
)


def _count(from_sign: int, to_sign: int) -> int:
    return ((to_sign - from_sign) % 12) + 1


def _natal(natal: dict) -> tuple[int, int]:
    lagna = int(natal["ascendant"]["signIndex"])
    moon = int(next(p for p in natal["planets"] if p["planet"] == "moon")["signIndex"])
    return lagna, moon


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


# ---------------------------------------------------------------- sign segments
def sign_segments(body: str, start: datetime, end: datetime, step_days: int = 3) -> list[dict]:
    """Contiguous stretches in one sign: [{sign, starts_at, ends_at}] covering [start, end].
    Retrograde re-entries show as separate stretches."""
    out: list[dict] = []
    cursor = start
    sign = _sign(body, cursor)
    seg_start = start
    while cursor < end:
        step = min(cursor + timedelta(days=step_days), end)
        nxt = _sign(body, step)
        if nxt != sign:
            old = sign
            at = _bisect(cursor, step, lambda d, b=body, s=old: _sign(b, d) != s, seconds=300)
            out.append({"sign": sign, "starts_at": seg_start, "ends_at": at})
            seg_start, sign = at, nxt
        cursor = step
    out.append({"sign": sign, "starts_at": seg_start, "ends_at": end})
    return out


# ------------------------------------------------------------ lifetime tracker
def _runs(segments: list[dict], moon: int, houses: set[int], merge_gap_days: int = 400) -> list[list[dict]]:
    """Groups of consecutive segments whose Saturn sign is in `houses` from the Moon, merging
    groups separated by a short retrograde dip into the neighbouring sign."""
    runs: list[list[dict]] = []
    for seg in segments:
        if _count(moon, seg["sign"]) not in houses:
            continue
        if runs and (seg["starts_at"] - runs[-1][-1]["ends_at"]).days < merge_gap_days:
            runs[-1].append(seg)
        else:
            runs.append([seg])
    return runs


def sade_sati_lifetime(natal: dict, as_of: datetime, horizon_years: int = 100) -> dict:
    """Every Sade Sati and dhaiya from before birth to `horizon_years` of age, with phase
    dates, today's status and the next occurrence."""
    as_of = _utc(as_of)
    _, moon = _natal(natal)
    birth = _utc(datetime.fromisoformat(natal["calculationMetadata"]["utcDateTime"].replace("Z", "+00:00")))
    scan_start = birth - timedelta(days=9 * 365)
    scan_end = max(birth + timedelta(days=horizon_years * 365.2425), as_of + timedelta(days=35 * 365)) \
        + timedelta(days=9 * 365)
    segments = sign_segments("saturn", scan_start, scan_end)
    year = 365.2425

    def age(dt: datetime) -> float:
        return round(max(0.0, (dt - birth).total_seconds() / 86400 / year), 1)

    def status_of(start: datetime, end: datetime) -> str:
        return "current" if start <= as_of < end else ("past" if end <= as_of else "upcoming")

    periods: list[dict] = []
    for run in _runs(segments, moon, {12, 1, 2}):
        start, end = run[0]["starts_at"], run[-1]["ends_at"]
        phases: list[dict] = []
        for seg in run:
            phase = _PHASE[_count(moon, seg["sign"])]
            if not phases or phases[-1]["phase"] != phase:
                if phases and any(p["phase"] == phase for p in phases):
                    continue  # retrograde dip back into an earlier sign: fold it in
                phases.append({"phase": phase, "saturn_sign": SIGN_NAMES[seg["sign"]],
                               "starts_at": seg["starts_at"], "ends_at": seg["ends_at"]})
            else:
                phases[-1]["ends_at"] = seg["ends_at"]
        for a, b in zip(phases, phases[1:], strict=False):
            a["ends_at"] = b["starts_at"]
        phases[-1]["ends_at"] = end
        periods.append({"kind": "sade_sati", "starts_at": start, "ends_at": end, "phases": phases})
    for house, kind in ((4, "dhaiya_kantaka"), (8, "dhaiya_ashtama")):
        for run in _runs(segments, moon, {house}):
            start, end = run[0]["starts_at"], run[-1]["ends_at"]
            periods.append({"kind": kind, "starts_at": start, "ends_at": end, "phases": [
                {"phase": "dhaiya", "saturn_sign": SIGN_NAMES[run[0]["sign"]],
                 "starts_at": start, "ends_at": end}]})

    periods = [p for p in periods if p["ends_at"] > birth and p["starts_at"] < scan_end - timedelta(days=9 * 365)]
    periods.sort(key=lambda p: p["starts_at"])
    out_periods: list[dict] = []
    for i, p in enumerate(periods):
        out_periods.append({
            "index": i, "kind": p["kind"], "status": status_of(p["starts_at"], p["ends_at"]),
            "starts_at": iso(p["starts_at"]), "ends_at": iso(p["ends_at"]),
            "age_start": age(p["starts_at"]), "age_end": age(p["ends_at"]),
            "started_before_birth": p["starts_at"] < birth,
            "phases": [{"phase": ph["phase"], "saturn_sign": ph["saturn_sign"],
                        "starts_at": iso(ph["starts_at"]), "ends_at": iso(ph["ends_at"])}
                       for ph in p["phases"]],
        })

    saturn_sign = _sign("saturn", as_of)
    house = _count(moon, saturn_sign)
    current_phase = _PHASE.get(house)
    current_kind = "sade_sati" if house in _PHASE else _DHAIYA.get(house)
    nxt = next((p for p in out_periods if p["status"] == "upcoming"), None)
    nxt_sade = next((p for p in out_periods if p["status"] == "upcoming" and p["kind"] == "sade_sati"), None)
    cur = next((p for p in out_periods if p["status"] == "current"), None)
    return {
        "as_of": iso(as_of), "birth": iso(birth), "moon_sign": SIGN_NAMES[moon],
        "current": {"kind": current_kind,
                    "phase": current_phase or ("dhaiya" if current_kind else None),
                    "saturn_sign": SIGN_NAMES[saturn_sign], "house_from_moon": house,
                    "period_index": cur["index"] if cur else None},
        "next_index": nxt["index"] if nxt else None,
        "next_sade_sati_index": nxt_sade["index"] if nxt_sade else None,
        "periods": out_periods,
        "proof": PROOF_SADE_SATI,
    }


# --------------------------------------------------------------------- gochara
def _vedha_blockers(planet: str, vedha_house: int, moon: int, signs: dict[str, int]) -> list[str]:
    out = []
    for other in GOCHARA_PLANETS:
        if other == planet or frozenset({planet, other}) in VEDHA_EXEMPT:
            continue
        if _count(moon, signs[other]) == vedha_house:
            out.append(other)
    return out


def gochara_snapshot(natal: dict, when: datetime) -> dict:
    """Transiting grahas on `when` against the natal chart, with Moon-based gochara,
    vedha, bhinna ashtakavarga bindus in the occupied sign, SAV, and a verdict."""
    when = _utc(when)
    lagna, moon = _natal(natal)
    metrics = natal["strengthMetrics"]
    bav = {row["planet"]: row["bindusBySign"] for row in metrics["ashtakavarga"]}
    sav = metrics["sarvashtakavarga"]
    longitudes = {b: sidereal(b, when) for b in ALL_BODIES}
    signs = {b: int(longitudes[b] // 30) % 12 for b in ALL_BODIES}

    rows: list[dict] = []
    for planet in ALL_BODIES:
        sign = signs[planet]
        house_moon = _count(moon, sign)
        row = {
            "planet": planet, "sign": SIGN_NAMES[sign], "sign_index": sign,
            "degrees_in_sign": round(longitudes[planet] % 30, 2),
            "retrograde": _retro(planet, when),
            "house_from_moon": house_moon, "house_from_lagna": _count(lagna, sign),
            "bindus": None, "sav": int(sav[sign]), "favourable_houses": [],
            "favourable": None, "vedha_house": None, "vedha_by": [], "verdict": "not_rated",
            "reason_code": "nodes_not_rated",
        }
        if planet in GOCHARA_FAVOURABLE:
            good, vedha = GOCHARA_FAVOURABLE[planet]
            bindus = int(bav[planet][sign])
            favourable = house_moon in good
            vedha_house = vedha[good.index(house_moon)] if favourable else None
            blockers = _vedha_blockers(planet, vedha_house, moon, signs) if vedha_house else []
            if favourable and blockers:
                verdict, code = "mixed", "vedha_blocked"
            elif favourable and bindus >= BINDU_STRONG:
                verdict, code = "favourable", "favourable_strong"
            elif favourable:
                verdict, code = "mixed", "favourable_weak_bindus"
            elif bindus >= BINDU_RESCUE:
                verdict, code = "mixed", "unfavourable_softened"
            else:
                verdict, code = "unfavourable", "unfavourable"
            row.update(bindus=bindus, favourable_houses=list(good), favourable=favourable,
                       vedha_house=vedha_house, vedha_by=blockers, verdict=verdict,
                       reason_code=code)
        row["reason"] = _reason_text(row)
        rows.append(row)

    saturn_house = _count(moon, signs["saturn"])
    status = "sade_sati" if saturn_house in _PHASE else _DHAIYA.get(saturn_house)
    tally = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("favourable", "mixed", "unfavourable")}
    return {
        "date": iso(when), "moon_sign": SIGN_NAMES[moon], "lagna_sign": SIGN_NAMES[lagna],
        "planets": rows,
        "saturn_status": {"kind": status, "phase": _PHASE.get(saturn_house) or ("dhaiya" if status else None),
                          "house_from_moon": saturn_house},
        "tally": tally,
        "proof": PROOF_GOCHARA,
    }


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _reason_text(row: dict) -> str:
    """English fallback of the reason; the web app builds its own localised text from
    `reason_code` and the numbers."""
    name = row["planet"].capitalize()
    h, b = _ord(row["house_from_moon"]), row["bindus"]
    code = row["reason_code"]
    if code == "nodes_not_rated":
        return f"{name} is shown by position only: the classical gochara tables rate the seven grahas."
    if code == "vedha_blocked":
        by = ", ".join(x.capitalize() for x in row["vedha_by"])
        return (f"{name} in the {h} from the Moon is a favourable house but {by} stands in its "
                f"vedha house {row['vedha_house']}, which obstructs it.")
    if code == "favourable_strong":
        return f"{name} in the {h} from the Moon is favourable and holds {b} bindus here."
    if code == "favourable_weak_bindus":
        return f"{name} in the {h} from the Moon is favourable but holds only {b} bindus, so the result is muted."
    if code == "unfavourable_softened":
        return f"{name} in the {h} from the Moon is not a favourable house, softened by {b} bindus."
    return f"{name} in the {h} from the Moon is not a favourable house and holds {b} bindus."


# -------------------------------------------------------------- double transit
def _casts(planet: str) -> tuple[int, ...]:
    return (1, 7, *_SPECIAL_ASPECTS.get(planet, ()))


def double_transit(natal: dict, start: datetime, months: int = 24, reference: str = "lagna") -> dict:
    """Per house, the windows in the next `months` when Jupiter and Saturn both occupy or
    aspect it. `reference` is the sign houses count from: lagna or moon."""
    start = _utc(start)
    months = min(max(months, 1), 36)
    end = start + timedelta(days=round(months * 30.4375))
    lagna, moon = _natal(natal)
    origin = lagna if reference == "lagna" else moon

    jup = sign_segments("jupiter", start, end)
    sat = sign_segments("saturn", start, end)
    cuts = sorted({start, end, *(s["ends_at"] for s in jup), *(s["ends_at"] for s in sat)})

    def sign_at(segs: list[dict], t: datetime) -> int:
        return next(s["sign"] for s in segs if s["starts_at"] <= t < s["ends_at"] or s is segs[-1])

    spans: list[dict] = []
    for a, b in zip(cuts, cuts[1:], strict=False):
        if b <= a:
            continue
        j, s = sign_at(jup, a), sign_at(sat, a)
        houses = [h for h in range(1, 13)
                  if _count(j, (origin + h - 1) % 12) in _casts("jupiter")
                  and _count(s, (origin + h - 1) % 12) in _casts("saturn")]
        spans.append({"starts_at": a, "ends_at": b, "jupiter_sign": j, "saturn_sign": s, "houses": houses})
    merged: list[dict] = []
    for sp in spans:  # join neighbours with the same pair of signs
        if merged and (merged[-1]["jupiter_sign"], merged[-1]["saturn_sign"]) == (sp["jupiter_sign"], sp["saturn_sign"]):
            merged[-1]["ends_at"] = sp["ends_at"]
        else:
            merged.append(dict(sp))

    house_rows = []
    for h in range(1, 13):
        windows: list[dict] = []
        for sp in merged:
            if h not in sp["houses"]:
                continue
            if windows and windows[-1]["ends_at"] == sp["starts_at"]:
                windows[-1]["ends_at"] = sp["ends_at"]
            else:
                windows.append({"starts_at": sp["starts_at"], "ends_at": sp["ends_at"]})
        house_rows.append({
            "house": h, "sign": SIGN_NAMES[(origin + h - 1) % 12],
            "active_now": any(w["starts_at"] <= start < w["ends_at"] for w in windows),
            "days": sum((w["ends_at"] - w["starts_at"]).days for w in windows),
            "windows": [{"starts_at": iso(w["starts_at"]), "ends_at": iso(w["ends_at"])} for w in windows],
        })
    return {
        "start": iso(start), "end": iso(end), "months": months, "reference": reference,
        "reference_sign": SIGN_NAMES[origin],
        "jupiter_now": SIGN_NAMES[sign_at(jup, start)], "saturn_now": SIGN_NAMES[sign_at(sat, start)],
        "spans": [{"starts_at": iso(s["starts_at"]), "ends_at": iso(s["ends_at"]),
                   "jupiter_sign": SIGN_NAMES[s["jupiter_sign"]], "saturn_sign": SIGN_NAMES[s["saturn_sign"]],
                   "houses": s["houses"]} for s in merged],
        "houses": house_rows,
        "proof": PROOF_DOUBLE,
    }


__all__ = ["double_transit", "gochara_snapshot", "sade_sati_lifetime"]
