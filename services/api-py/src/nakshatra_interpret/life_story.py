"""Life-story composer: age-band, dasha, and hybrid chapters from a chart artifact.

Deterministic and evidence-cited. No LLM. Every item carries evidence strings
naming the placements / dasha windows that produced it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from nakshatra_i18n import Lang
from nakshatra_i18n.yogas_hi import YOGA_NAMES_HI

AGE_BANDS: list[dict[str, Any]] = [
    {
        "key": "childhood",
        "from": 0,
        "to": 12,
        "houses": (4, 1),
    },
    {
        "key": "youth",
        "from": 13,
        "to": 24,
        "houses": (3, 5, 9),
    },
    {
        "key": "early-adulthood",
        "from": 25,
        "to": 40,
        "houses": (7, 10, 2),
    },
    {
        "key": "midlife",
        "from": 41,
        "to": 60,
        "houses": (10, 11, 8),
    },
    {
        "key": "later-life",
        "from": 60,
        "to": None,
        "houses": (9, 12, 4),
    },
]


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(dt: datetime) -> str:
    return (
        dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.")
        + f"{dt.microsecond // 1000:03d}Z"
    )


def _item(title: str, text: str, evidence: list[str]) -> dict:
    return {"title": title, "text": text, "evidence": evidence}


def _birth_dt(artifact: dict) -> datetime:
    meta = artifact["calculationMetadata"]
    if meta.get("utcDateTime"):
        return _parse_dt(meta["utcDateTime"])
    inp = meta["input"]
    return datetime.fromisoformat(f"{inp['birthDate']}T12:00:00+00:00")


def _age_years(birth: datetime, at: datetime) -> float:
    return (at - birth).total_seconds() / (365.2425 * 24 * 3600)


def _age_at(birth: datetime, years: float) -> datetime:
    return birth + timedelta(days=years * 365.2425)


def _shadbala_band(artifact: dict, planet: str) -> str | None:
    for row in artifact["strengthMetrics"]["shadbala"]:
        if row["planet"] == planet:
            if row["ratio"] >= 1.15:
                return "strong"
            if row["ratio"] < 0.85:
                return "weak"
            return "moderate"
    return None


def _houses_ruled(artifact: dict, planet: str) -> list[int]:
    return [h["number"] for h in artifact["houses"] if h["lord"] == planet]


def _planet_state(artifact: dict, planet: str) -> dict:
    return next(p for p in artifact["planets"] if p["planet"] == planet)


def _mahadashas(artifact: dict) -> list[dict]:
    return artifact["vimshottari"]["mahadashas"]


def _overlap_mahadashas(
    artifact: dict, window_start: datetime, window_end: datetime
) -> list[dict]:
    out: list[dict] = []
    for maha in _mahadashas(artifact):
        start = _parse_dt(maha["start"])
        end = _parse_dt(maha["end"])
        if start < window_end and end > window_start:
            out.append(maha)
    return out


def _dasha_meta(birth: datetime, maha: dict) -> dict:
    start = _parse_dt(maha["start"])
    end = _parse_dt(maha["end"])
    return {
        "planet": maha["planet"],
        "level": "mahadasha",
        "start": maha["start"],
        "end": maha["end"],
        "ageFrom": round(max(0.0, _age_years(birth, start)), 1),
        "ageTo": round(_age_years(birth, end), 1),
    }

def _lord_promise_text(artifact: dict, planet: str, L: Lang) -> tuple[str, list[str]]:
    sigs, houses, _st, _nt, dignities = L.tables()
    state = _planet_state(artifact, planet)
    sig = sigs[planet]
    band = _shadbala_band(artifact, planet)
    ruled = _houses_ruled(artifact, planet)
    ruled_themes = ", ".join(
        L.t("ls.ruled_item", ord=L.ordinal(n), themes=houses[n]["themes"]) for n in ruled
    )
    tone_key = "strong" if band == "strong" else "weak" if band == "weak" else None
    dignity_tone = (
        "strong"
        if state["dignity"] in ("exalted", "moolatrikona", "own")
        else "weak"
        if state["dignity"] in ("enemy", "debilitated")
        else None
    )
    tone = tone_key or dignity_tone or "strong"
    common = dict(
        title=sig["title"], house_ord=L.ordinal(state["house"]),
        sign=L.sign(state["signName"]), dignity=dignities[state["dignity"]],
        karakas=sig["karakas"], themes=houses[state["house"]]["themes"], effect=sig[tone],
    )
    text = (
        L.t("ls.promise", ruled=ruled_themes, **common)
        if ruled_themes
        else L.t("ls.promise.noruled", **common)
    )
    evidence = [
        L.t("ls.ev.natal", planet=L.planet(planet), h=state["house"],
            sign=L.sign(state["signName"]), dignity=L.dignity(state["dignity"])),
    ]
    if ruled:
        evidence.append(
            L.t("ls.ev.rules", planet=L.planet(planet), houses=", ".join(str(n) for n in ruled))
        )
    if band:
        evidence.append(L.t("ls.ev.band", planet=L.planet(planet), band=L.band(band)))
    return text, evidence


def _stage_theme_items(
    artifact: dict, band: dict, overlapping: list[dict], L: Lang
) -> list[dict]:
    sigs, houses_t, _st, nak_traits, dignities = L.tables()
    items: list[dict] = []
    planets = {p["planet"]: p for p in artifact["planets"]}
    lagna_lord = artifact["houses"][0]["lord"]

    if band["key"] == "childhood":
        moon = planets["moon"]
        ll = planets[lagna_lord]
        items.append(
            _item(
                L.t("ls.child.title"),
                L.t(
                    "ls.child.text", moon_house=L.ordinal(moon["house"]),
                    sign=L.sign(moon["signName"]), nak=L.nak(moon["nakshatra"]),
                    nak_trait=nak_traits.get(moon["nakshatra"], "emotional tone"),
                    ll_title=sigs[lagna_lord]["title"], ll_house=L.ordinal(ll["house"]),
                    h4=houses_t[4]["themes"], h1=houses_t[1]["themes"],
                ),
                [
                    L.t("ls.child.ev.moon", h=moon["house"], sign=L.sign(moon["signName"]),
                        nak=L.nak(moon["nakshatra"]), pada=moon["pada"]),
                    L.t("ls.child.ev.lord", lord=L.planet(lagna_lord), h=ll["house"],
                        sign=L.sign(ll["signName"]), dignity=L.dignity(ll["dignity"])),
                ],
            )
        )

    for house_num in band["houses"]:
        house = artifact["houses"][house_num - 1]
        lord = planets[house["lord"]]
        occupants = house.get("occupants") or []
        occ_phrase = (
            L.t("ls.stage.occ", occ=L.planets(occupants))
            if occupants
            else L.t("ls.stage.noocc")
        )
        items.append(
            _item(
                L.t("ls.stage.title", name=houses_t[house_num]["name"]),
                L.t(
                    "ls.stage.text", themes=houses_t[house_num]["themes"],
                    house_ord=L.ordinal(house_num), lord_title=sigs[house["lord"]]["title"],
                    lh_ord=L.ordinal(lord["house"]), sign=L.sign(lord["signName"]),
                    dignity=dignities[lord["dignity"]], occ_phrase=occ_phrase,
                ),
                [
                    L.t("ls.stage.ev.lord", n=house_num, lord=L.planet(house["lord"]),
                        h=lord["house"], sign=L.sign(lord["signName"]),
                        dignity=L.dignity(lord["dignity"])),
                    *(
                        [L.t("ls.stage.ev.occ", n=house_num, occ=L.planets(occupants))]
                        if occupants
                        else []
                    ),
                ],
            )
        )
        if len(items) >= 3:
            break

    for maha in overlapping[:2]:
        promise, evidence = _lord_promise_text(artifact, maha["planet"], L)
        evidence = [
            L.t("ls.ev.maha", planet=L.planet(maha["planet"]),
                start=maha["start"][:10], end=maha["end"][:10]),
            *evidence,
        ]
        items.append(
            _item(L.t("ls.maha.colour", display=L.display(maha["planet"])), promise, evidence)
        )

    return items[:4]


def _band_window(
    birth: datetime, band: dict
) -> tuple[datetime, datetime, dict]:
    start = _age_at(birth, float(band["from"]))
    if band["to"] is None:
        end = _age_at(birth, 100.0)
        age_range = {"from": band["from"], "to": None}
    else:
        end = _age_at(birth, float(band["to"]) + 1.0)
        age_range = {"from": band["from"], "to": band["to"]}
    if start < birth:
        start = birth
    return start, end, age_range


def _age_band_chapter(
    artifact: dict,
    birth: datetime,
    band: dict,
    now: datetime,
    L: Lang,
    *,
    hybrid: bool,
) -> dict:
    start, end, age_range = _band_window(birth, band)
    overlapping = _overlap_mahadashas(artifact, start, end)
    dashas = [_dasha_meta(birth, m) for m in overlapping]
    items = _stage_theme_items(artifact, band, overlapping, L)

    md_names = [L.display(m["planet"]) for m in overlapping]
    if hybrid and md_names:
        if len(md_names) == 1:
            md_clause = L.t("ls.md.one", a=md_names[0])
        else:
            md_clause = L.t("ls.md.many", head=", ".join(md_names[:-1]), last=md_names[-1])
    else:
        md_clause = ""

    age_label = (
        L.t("ls.age.plus", frm=band["from"])
        if band["to"] is None
        else L.t("ls.age.range", frm=band["from"], to=band["to"])
    )
    band_title = L.t(f"ls.band.{band['key']}.title")
    summary = L.t(
        "ls.summary", md_clause=md_clause, title=band_title, age_label=age_label,
        focus=L.t(f"ls.band.{band['key']}.focus"),
    )

    title = (
        L.t("ls.title.open", title=band_title, frm=band["from"])
        if band["to"] is None
        else L.t("ls.title.range", title=band_title, frm=band["from"], to=band["to"])
    )
    if hybrid and md_names:
        title = L.t("ls.title.hybrid", title=title, names=" / ".join(md_names))

    return {
        "key": f"{'hybrid' if hybrid else 'age'}-{band['key']}",
        "title": title,
        "ageRange": age_range,
        "years": {"start": start.date().isoformat(), "end": end.date().isoformat()},
        "dashas": dashas,
        "summary": summary,
        "items": items,
        "isCurrent": start <= now < end,
    }


def _dasha_chapter(
    artifact: dict, birth: datetime, maha: dict, now: datetime, L: Lang
) -> dict:
    sigs, houses_t, _st, _nt, _dg = L.tables()
    start = _parse_dt(maha["start"])
    end = _parse_dt(maha["end"])
    age_from = max(0.0, _age_years(birth, start))
    age_to = _age_years(birth, end)
    display = L.display(maha["planet"])
    promise, evidence = _lord_promise_text(artifact, maha["planet"], L)
    evidence = [
        L.t("ls.ev.maha", planet=L.planet(maha["planet"]),
            start=maha["start"][:10], end=maha["end"][:10]),
        *evidence,
    ]

    items = [
        _item(L.t("ls.dasha.promise", display=display), promise, evidence),
    ]
    long_ads = []
    for antar in maha.get("children") or []:
        a_start = _parse_dt(antar["start"])
        a_end = _parse_dt(antar["end"])
        years = (a_end - a_start).total_seconds() / (365.2425 * 24 * 3600)
        if years >= 2.0:
            long_ads.append(antar)
    for antar in long_ads[:2]:
        ad_planet = antar["planet"]
        ad_promise, ad_evidence = _lord_promise_text(artifact, ad_planet, L)
        items.append(
            _item(
                L.t("ls.dasha.antar.title", display=L.display(ad_planet)),
                L.t("ls.dasha.antar.text", title=sigs[ad_planet]["title"],
                    start=antar["start"][:10], end=antar["end"][:10], promise=ad_promise),
                [
                    L.t("ls.dasha.antar.ev", planet=L.planet(ad_planet),
                        start=antar["start"][:10], end=antar["end"][:10]),
                    *ad_evidence,
                ],
            )
        )

    ruled = _houses_ruled(artifact, maha["planet"])
    if ruled:
        themes = "; ".join(
            L.t("ls.dasha.ruled.item", name=houses_t[n]["name"], themes=houses_t[n]["themes"])
            for n in ruled
        )
        items.append(
            _item(
                L.t("ls.dasha.ruled.title"),
                L.t("ls.dasha.ruled.text", display=display, themes=themes),
                [
                    L.t("ls.dasha.ruled.ev", planet=L.planet(maha["planet"]),
                        houses=", ".join(str(n) for n in ruled))
                ],
            )
        )

    return {
        "key": f"dasha-{maha['planet']}-{maha['start'][:10]}",
        "title": L.t("ls.dasha.title", display=display, a=f"{age_from:.0f}", b=f"{age_to:.0f}"),
        "ageRange": {"from": int(age_from), "to": int(age_to)},
        "years": {"start": start.date().isoformat(), "end": end.date().isoformat()},
        "dashas": [_dasha_meta(birth, maha)],
        "summary": L.t(
            "ls.dasha.summary", display=display, start=start.date().isoformat(),
            end=end.date().isoformat(), a=f"{age_from:.0f}", b=f"{age_to:.0f}",
            karakas=sigs[maha["planet"]]["karakas"],
        ),
        "items": items[:4],
        "isCurrent": start <= now < end,
    }


def _through_line(artifact: dict, L: Lang) -> dict:
    _sg, _h, sign_traits, nak_traits, _dg = L.tables()
    asc = artifact["ascendant"]
    pan = artifact["panchang"]
    moon_nak = pan["moonNakshatra"]["name"]
    yogas = artifact.get("yogas") or []
    present = [y for y in yogas if y.get("present")]
    yoga_name = None
    if present:
        yoga_name = YOGA_NAMES_HI.get(present[0]["key"], present[0]["name"]) if L.hi else present[0]["name"]
    text = L.t(
        "ls.through.text", sign=L.sign(asc["signName"]),
        sign_trait=sign_traits[asc["signName"]], nak=L.nak(moon_nak),
        nak_trait=nak_traits.get(moon_nak, "lunar colour"),
    )
    evidence = [
        L.t("ls.through.ev.asc", sign=L.sign(asc["signName"]), nak=L.nak(asc["nakshatra"]),
            pada=asc["pada"]),
        L.t("ls.through.ev.moon", nak=L.nak(moon_nak), pada=pan["moonNakshatra"]["pada"]),
    ]
    if yoga_name:
        text += L.t("ls.through.yoga", yoga=yoga_name)
        evidence.append(L.t("ls.through.ev.yoga", yoga=yoga_name))
    return _item(L.t("ls.through.title"), text, evidence)


def build_life_story(artifact: dict, now: datetime | None = None, lang: str = "en") -> dict:
    """Compose hybrid, age-band, and dasha-chapter life story from an artifact."""
    L = Lang(lang)
    now = now or datetime.now(tz=UTC)
    birth = _birth_dt(artifact)
    birth_date = artifact["calculationMetadata"]["input"]["birthDate"]
    current_age = int(_age_years(birth, now))

    age_bands = [
        _age_band_chapter(artifact, birth, band, now, L, hybrid=False)
        for band in AGE_BANDS
    ]
    hybrid = [
        _age_band_chapter(artifact, birth, band, now, L, hybrid=True)
        for band in AGE_BANDS
    ]
    if hybrid:
        hybrid[0]["items"] = [_through_line(artifact, L), *hybrid[0]["items"]]
        hybrid[0]["items"] = hybrid[0]["items"][:4]

    life_end = _age_at(birth, 100.0)
    dasha_chapters = [
        _dasha_chapter(artifact, birth, maha, now, L)
        for maha in _overlap_mahadashas(artifact, birth, life_end)
    ]

    return {
        "generatedAt": _iso(now),
        "birthDate": birth_date,
        "currentAgeYears": current_age,
        "lenses": {
            "hybrid": hybrid,
            "ageBands": age_bands,
            "dashaChapters": dasha_chapters,
        },
    }
