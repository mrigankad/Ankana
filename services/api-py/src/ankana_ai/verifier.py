"""Deterministic claim verifier.

The model returns sentences, each with structured claims in canonical English
values (language independent). Every claim is compared against the chart
artifact (and the Lal Kitab provider for lk_* claims). Nothing here calls a
model.

Policy applied by the assistant: one rewrite on mismatch, then the failing
sentence is replaced by the verified chart fact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from .tools import SIGNS, Citation, LalKitabProvider

DEGREE_TOLERANCE = 0.5
DATE_TOLERANCE_DAYS = 1

# Tools whose results can legitimately support each claim type (soft check).
SUPPORTING_TOOLS: dict[str, set[str]] = {
    "lagna": {"get_birth_chart", "get_reading_summary", "get_life_story"},
    "planet_sign": {"get_birth_chart", "get_reading_summary", "get_life_story", "get_transits"},
    "planet_house": {"get_birth_chart", "get_reading_summary", "get_life_story"},
    "planet_degree": {"get_birth_chart"},
    "planet_nakshatra": {"get_birth_chart", "get_reading_summary"},
    "house_lord": {"get_birth_chart", "get_reading_summary"},
    "dasha_period": {"get_dashas", "get_life_story", "get_predictions", "get_reading_summary"},
    "yoga": {"get_yogas", "get_reading_summary", "get_life_story"},
    "lk_planet_house": {"lk_chart"},
    "transit_sign": {"get_transits"},
    "sade_sati": {"get_transits"},
}

# Words that mark a sentence as being about the sky now, not the natal chart.
_TRANSIT_WORDS = re.compile(
    r"\btransit\w*|\bgochar\b|\bsade ?sati\b|\bsadhe ?sati\b|गोचर|साढ़े ?साती|साढे ?साती",
    re.IGNORECASE)

_PLANET_ALIASES = {
    "surya": "sun", "ravi": "sun", "chandra": "moon", "soma": "moon", "mangal": "mars",
    "kuja": "mars", "budh": "mercury", "guru": "jupiter", "brihaspati": "jupiter",
    "shukra": "venus", "shani": "saturn", "asc": "lagna", "ascendant": "lagna",
}


def norm_planet(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    return _PLANET_ALIASES.get(v, v) or None


def norm_sign(value: object) -> str | None:
    if isinstance(value, int) and 0 <= value < 12:
        return SIGNS[value]
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    for s in SIGNS:
        if s.lower() == v:
            return s
    return value.strip() or None


def _date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")[:10])
    except ValueError:
        return None


def _strip(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


@dataclass
class Mismatch:
    claim: dict
    reason: str
    correct_fact: str
    soft: bool = False  # soft = warning only, does not force a rewrite

    def as_dict(self) -> dict:
        return {"claim": self.claim, "reason": self.reason,
                "correctFact": self.correct_fact, "soft": self.soft}


@dataclass
class ClaimReport:
    checked: int = 0
    failed: int = 0
    mismatches: dict[int, list[Mismatch]] = field(default_factory=dict)  # by sentence index

    def hard_failures(self) -> dict[int, list[Mismatch]]:
        out = {}
        for idx, ms in self.mismatches.items():
            hard = [m for m in ms if not m.soft]
            if hard:
                out[idx] = hard
        return out


class Verifier:
    def __init__(self, artifact: dict, lalkitab: LalKitabProvider | None = None,
                 now: datetime | None = None):
        self.a = artifact
        self.lk = lalkitab
        self.now = now
        self._transit: dict | None = None
        self.planets = {p["planet"]: p for p in artifact["planets"]}
        self.houses = {h["number"]: h for h in artifact["houses"]}
        self._lk_cache: dict | None = None

    # ------------------------------------------------------------- facts

    def _body(self, planet: str) -> dict | None:
        if planet == "lagna":
            return self.a["ascendant"]
        return self.planets.get(planet)

    def fact_for_planet(self, planet: str) -> str:
        if planet == "lagna":
            asc = self.a["ascendant"]
            return (f"Lagna is {asc['signName']} {asc['degreesInSign']:.2f} deg, "
                    f"{asc['nakshatra']} pada {asc['pada']}")
        p = self.planets.get(planet)
        if not p:
            return f"{planet} is not a chart planet"
        return (f"{planet.capitalize()} is in {p['signName']} {p['degreesInSign']:.2f} deg, "
                f"house {p['house']}, {p['nakshatra']} pada {p['pada']}")

    def _dasha_candidates(self, planet: str | None, level: str, parent: str | None) -> list[dict]:
        out: list[dict] = []
        for md in self.a["vimshottari"]["mahadashas"]:
            if level == "mahadasha":
                if planet is None or md["planet"] == planet:
                    out.append(md)
            else:
                if parent and md["planet"] != parent:
                    continue
                for ad in md.get("children", []):
                    if planet is None or ad["planet"] == planet:
                        out.append({**ad, "_parent": md["planet"]})
        return out

    def transit_snapshot(self) -> dict | None:
        """Today's sky against the natal chart (same call the get_transits tool makes)."""
        if self._transit is None and self.now is not None:
            from nakshatra_core.transits import compute_transit_snapshot

            self._transit = compute_transit_snapshot(self.a, self.now)
        return self._transit

    def fact_for_transit(self, planet: str) -> str:
        snap = self.transit_snapshot()
        tp = next((p for p in (snap or {}).get("planets", []) if p["planet"] == planet), None)
        if tp is None:
            return f"{planet} is not a transit body"
        return (f"Transit {planet.capitalize()} is in {tp['signName']} "
                f"({snap['date'][:10]}), house {tp['houseFromLagna']} from the natal lagna")

    def check_transit(self, claim: dict) -> Mismatch | None:
        """transit_sign: current sign (and house from the natal lagna) of a graha; sade_sati:
        whether it is active. Without a reference date nothing can be checked, so it passes."""
        snap = self.transit_snapshot()
        if snap is None:
            return None
        if claim.get("type") == "sade_sati":
            ss = snap["sadeSati"]
            fact = ("Sade sati is " + (f"active ({ss['phase']} phase)" if ss["active"]
                                       else "not active") + " now")
            if "present" in claim and bool(claim["present"]) != bool(ss["active"]):
                return Mismatch(claim, fact, fact)
            return None
        planet = norm_planet(claim.get("planet"))
        tp = next((p for p in snap["planets"] if p["planet"] == planet), None)
        if tp is None:
            return Mismatch(claim, f"unknown transit planet {claim.get('planet')!r}",
                            "Transit bodies: the nine grahas")
        fact = self.fact_for_transit(planet)
        sign = norm_sign(claim.get("sign"))
        if sign is not None and sign != tp["signName"]:
            return Mismatch(claim, f"transit {planet} sign is {tp['signName']}, not {sign}", fact)
        house = claim.get("house")
        if house is not None and int(house) != tp["houseFromLagna"]:
            return Mismatch(claim, f"transit {planet} is in house {tp['houseFromLagna']} from "
                            f"the lagna, not {house}", fact)
        if sign is None and house is None:
            return Mismatch(claim, "transit_sign claim states nothing checkable", fact)
        return None

    # ------------------------------------------------------------- checks

    def check_claim(self, claim: dict) -> Mismatch | None:
        t = claim.get("type")
        planet = norm_planet(claim.get("planet"))
        if t in ("transit_sign", "sade_sati"):
            return self.check_transit(claim)

        if t in {"lagna", "planet_sign", "planet_house", "planet_degree", "planet_nakshatra"}:
            if t == "lagna":
                planet = "lagna"
            body = self._body(planet or "")
            if body is None:
                return Mismatch(claim, f"unknown planet {claim.get('planet')!r}",
                                "Valid bodies: lagna and the nine grahas")
            fact = self.fact_for_planet(planet)
            sign = norm_sign(claim.get("sign"))
            if sign is not None and sign != body["signName"]:
                return Mismatch(claim, f"{planet} sign is {body['signName']}, not {sign}", fact)
            if t == "lagna" and sign is None and claim.get("degree") is None \
                    and claim.get("nakshatra") is None:
                return Mismatch(claim, "lagna claim states nothing checkable", fact)
            house = claim.get("house")
            if house is not None and planet != "lagna" and int(house) != body["house"]:
                return Mismatch(claim, f"{planet} is in house {body['house']}, not {house}", fact)
            degree = claim.get("degree")
            if degree is not None:
                if abs(float(degree) - body["degreesInSign"]) > DEGREE_TOLERANCE:
                    return Mismatch(
                        claim, f"{planet} degree is {body['degreesInSign']:.2f}, not {degree}", fact)
            nak = claim.get("nakshatra")
            if nak is not None and _strip(str(nak)) != _strip(body["nakshatra"]):
                return Mismatch(claim, f"{planet} nakshatra is {body['nakshatra']}, not {nak}", fact)
            pada = claim.get("pada")
            if pada is not None and int(pada) != body["pada"]:
                return Mismatch(claim, f"{planet} pada is {body['pada']}, not {pada}", fact)
            if t == "planet_sign" and sign is None:
                return Mismatch(claim, "planet_sign claim missing sign", fact)
            if t == "planet_house" and house is None:
                return Mismatch(claim, "planet_house claim missing house", fact)
            if t == "planet_degree" and degree is None:
                return Mismatch(claim, "planet_degree claim missing degree", fact)
            if t == "planet_nakshatra" and nak is None:
                return Mismatch(claim, "planet_nakshatra claim missing nakshatra", fact)
            return None

        if t == "house_lord":
            house = claim.get("house")
            lord = norm_planet(claim.get("lord") or claim.get("planet"))
            h = self.houses.get(int(house)) if house is not None else None
            if h is None:
                return Mismatch(claim, "house_lord claim needs a house 1-12", "Houses are numbered 1-12")
            fact = f"House {h['number']} is {h['signName']}, lord {h['lord']}"
            if lord != h["lord"]:
                return Mismatch(claim, f"house {h['number']} lord is {h['lord']}, not {lord}", fact)
            sign = norm_sign(claim.get("sign"))
            if sign is not None and sign != h["signName"]:
                return Mismatch(claim, f"house {h['number']} sign is {h['signName']}, not {sign}", fact)
            return None

        if t == "dasha_period":
            level = claim.get("level") or "mahadasha"
            parent = norm_planet(claim.get("parent"))
            candidates = self._dasha_candidates(planet, level, parent)
            start, end = _date(claim.get("start")), _date(claim.get("end"))
            listing = "; ".join(
                f"{c['planet']} {level} {c['start'][:10]} to {c['end'][:10]}"
                + (f" (in {c['_parent']})" if "_parent" in c else "")
                for c in candidates[:6]
            ) or f"no {level} for {planet}"
            if not candidates:
                return Mismatch(claim, f"no {level} for {planet}", listing)
            for c in candidates:
                cs, ce = _date(c["start"]), _date(c["end"])
                ok_s = start is None or abs((start - cs).days) <= DATE_TOLERANCE_DAYS
                ok_e = end is None or abs((end - ce).days) <= DATE_TOLERANCE_DAYS
                if ok_s and ok_e:
                    return None
            if start is None and end is None:
                return None
            return Mismatch(claim, f"{planet} {level} dates do not match the chart", listing)

        if t == "yoga":
            name = str(claim.get("yoga") or "")
            key = _strip(name)
            found = next(
                (y for y in self.a["yogas"]
                 if key and (_strip(y["key"]) == key or _strip(y["name"]) == key
                             or key in _strip(y["name"]))),
                None,
            )
            present_claimed = claim.get("present", True)
            present_all = ", ".join(y["name"] for y in self.a["yogas"] if y["present"]) or "none"
            if found is None:
                return Mismatch(claim, f"unknown yoga {name!r}", f"Present yogas: {present_all}")
            if bool(found["present"]) != bool(present_claimed):
                state = "present" if found["present"] else "not present"
                return Mismatch(claim, f"{found['name']} is {state}", f"Present yogas: {present_all}")
            return None

        if t == "lk_planet_house":
            if self.lk is None:
                return None
            if self._lk_cache is None:
                self._lk_cache = self.lk.chart(self.a, "lagna_h1").get("planetHouse", {})
            actual = self._lk_cache.get(planet or "")
            fact = f"Lal Kitab: {planet} in house {actual}"
            if actual is None or int(claim.get("house", -1)) != actual:
                return Mismatch(claim, f"Lal Kitab house of {planet} is {actual}", fact)
            return None

        return Mismatch(claim, f"unsupported claim type {t!r}", "Use a documented claim type")

    # ------------------------------------------------------------- answer

    def verify(self, sentences: list[dict], citations: list[Citation]) -> ClaimReport:
        report = ClaimReport()
        by_index = {c.index: c for c in citations}
        for si, sentence in enumerate(sentences):
            found: list[Mismatch] = []
            sky = False
            for claim in sentence.get("claims") or []:
                report.checked += 1
                cite0 = claim.get("cite")
                cit0 = by_index.get(cite0) if isinstance(cite0, int) else None
                if (cit0 is not None and cit0.tool == "get_transits"
                        and claim.get("type") in ("planet_sign", "planet_house")):
                    # The model cited the transit result: it means the sky now, not the natal chart.
                    claim = {**claim, "type": "transit_sign"}
                    sky = True
                try:
                    mm = self.check_claim(claim)
                except (TypeError, ValueError) as exc:
                    mm = Mismatch(claim, f"malformed claim: {exc}", "Provide well-formed claims")
                cite = claim.get("cite")
                if mm is None:
                    citation = by_index.get(cite) if isinstance(cite, int) else None
                    if citation is None:
                        mm = Mismatch(claim, f"citation [{cite}] does not exist",
                                      "Cite the [n] of a tool result you actually called")
                    elif citation.tool not in SUPPORTING_TOOLS.get(claim.get("type", ""), set()):
                        found.append(Mismatch(
                            claim, f"[{cite}] ({citation.tool}) does not carry this fact",
                            "Cite the tool result that contains it", soft=True))
                if mm is not None:
                    report.failed += 1
                    found.append(mm)
            for mm in scan_unstructured(sentence.get("text", ""), self,
                                        transit=sky or any(c.get("type") in ("transit_sign", "sade_sati")
                                                    for c in sentence.get("claims") or [])):
                report.checked += 1
                report.failed += 1
                found.append(mm)
            if found:
                report.mismatches[si] = found
        return report


# ------------------------------------------- undeclared-claim safety net
# A claim cannot hide in prose: "<planet> in <sign>" patterns are checked even
# when the model did not declare them. Works for English, Hinglish and Hindi.

_PLANET_WORDS = {
    "sun": "sun", "surya": "sun", "सूर्य": "sun",
    "moon": "moon", "chandra": "moon", "चंद्र": "moon", "चन्द्र": "moon",
    "mars": "mars", "mangal": "mars", "मंगल": "mars",
    "mercury": "mercury", "budh": "mercury", "बुध": "mercury",
    "jupiter": "jupiter", "guru": "jupiter", "गुरु": "jupiter", "बृहस्पति": "jupiter",
    "venus": "venus", "shukra": "venus", "शुक्र": "venus",
    "saturn": "saturn", "shani": "saturn", "शनि": "saturn",
    "rahu": "rahu", "राहु": "rahu", "ketu": "ketu", "केतु": "ketu",
}
_SIGN_WORDS = {
    "aries": "Aries", "mesh": "Aries", "मेष": "Aries",
    "taurus": "Taurus", "vrishabh": "Taurus", "vrishabha": "Taurus", "वृषभ": "Taurus",
    "gemini": "Gemini", "mithun": "Gemini", "मिथुन": "Gemini",
    "cancer": "Cancer", "kark": "Cancer", "karka": "Cancer", "कर्क": "Cancer",
    "leo": "Leo", "simha": "Leo", "singh": "Leo", "सिंह": "Leo",
    "virgo": "Virgo", "kanya": "Virgo", "कन्या": "Virgo",
    "libra": "Libra", "tula": "Libra", "तुला": "Libra",
    "scorpio": "Scorpio", "vrischik": "Scorpio", "vrishchik": "Scorpio", "वृश्चिक": "Scorpio",
    "sagittarius": "Sagittarius", "dhanu": "Sagittarius", "धनु": "Sagittarius",
    "capricorn": "Capricorn", "makar": "Capricorn", "मकर": "Capricorn",
    "aquarius": "Aquarius", "kumbh": "Aquarius", "कुंभ": "Aquarius", "कुम्भ": "Aquarius",
    "pisces": "Pisces", "meen": "Pisces", "मीन": "Pisces",
}


def _alt(words: dict) -> str:
    return "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))


# English / Hinglish: "<planet> is in/placed in/sits in <sign>", "<planet> <sign> mein"
_PAT_EN = re.compile(
    rf"(?<![\w])({_alt(_PLANET_WORDS)})\b\s+(?:(?:is|are|sits|sit|placed|posited|stands|currently|now)\s+)*"
    rf"(?:in|inside)\s+(?:the\s+sign\s+of\s+)?({_alt(_SIGN_WORDS)})\b",
    re.IGNORECASE,
)
# Hinglish / Hindi: "<planet> <sign> mein|में|राशि में"
_PAT_HI = re.compile(
    rf"({_alt(_PLANET_WORDS)})\s+(?:ki\s+rashi\s+)?({_alt(_SIGN_WORDS)})\s+(?:rashi\s+|राशि\s+)?(?:mein|me\b|में)",
    re.IGNORECASE,
)


def scan_unstructured(text: str, verifier: Verifier, *, transit: bool = False) -> list[Mismatch]:
    """Undeclared "<planet> in <sign>" statements. A sentence about transits (declared, or
    spotted by its wording) is compared with the sky now instead of the natal chart."""
    out: list[Mismatch] = []
    for pat in (_PAT_EN, _PAT_HI):
        for m in pat.finditer(text):
            planet = _PLANET_WORDS.get(m.group(1).lower()) or _PLANET_WORDS.get(m.group(1))
            sign = _SIGN_WORDS.get(m.group(2).lower()) or _SIGN_WORDS.get(m.group(2))
            sky = transit or bool(_TRANSIT_WORDS.search(text[max(0, m.start() - 48):m.end()]))
            if sky:
                snap = verifier.transit_snapshot()
                if snap is None:
                    continue  # no reference date: cannot judge a sky statement
                tp = next((p for p in snap["planets"] if p["planet"] == planet), None)
                if tp and sign and tp["signName"] != sign:
                    claim = {"type": "transit_sign", "planet": planet, "sign": sign,
                             "undeclared": True}
                    out.append(Mismatch(claim, f"transit {planet} is in {tp['signName']}, "
                                        f"not {sign}", verifier.fact_for_transit(planet)))
                continue
            body = verifier.planets.get(planet or "")
            if body and sign and body["signName"] != sign:
                claim = {"type": "planet_sign", "planet": planet, "sign": sign, "undeclared": True}
                out.append(Mismatch(claim, f"{planet} is in {body['signName']}, not {sign}",
                                    verifier.fact_for_planet(planet)))
    return out


def format_feedback(failures: dict[int, list[Mismatch]], sentences: list[dict]) -> str:
    """Text fed back to the model for the single rewrite attempt."""
    lines = ["VERIFIER_FEEDBACK: these statements disagree with the chart data. "
             "Rewrite the answer with correct facts and call submit_answer again. "
             "Do not repeat the wrong facts."]
    for si, ms in sorted(failures.items()):
        lines.append(f'Sentence {si + 1}: "{sentences[si].get("text", "")[:160]}"')
        for m in ms:
            lines.append(f"  - {m.reason}. Correct: {m.correct_fact}")
    return "\n".join(lines)
