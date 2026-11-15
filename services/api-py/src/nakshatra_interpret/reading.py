"""Reading composer: VedicChartArtifact -> sectioned, evidence-cited reading.

Every paragraph carries `evidence` strings naming the placements that
produced it, preserving the platform's grounding contract. Prose comes from
the nakshatra_i18n message catalogs (en, hi); English output is unchanged.
"""

from datetime import UTC, datetime

from nakshatra_i18n import Lang
from nakshatra_i18n.yogas_hi import localize_yoga

from .life_story import build_life_story


def _item(title: str, text: str, evidence: list[str]) -> dict:
    return {"title": title, "text": text, "evidence": evidence}


def _shadbala_band(artifact: dict, planet: str) -> str | None:
    for row in artifact["strengthMetrics"]["shadbala"]:
        if row["planet"] == planet:
            if row["ratio"] >= 1.15:
                return "strong"
            if row["ratio"] < 0.85:
                return "weak"
            return "moderate"
    return None  # rahu/ketu carry no shadbala


def _sav_band(bindus: int) -> str:
    if bindus >= 30:
        return "well-supported"
    if bindus <= 24:
        return "under-supported"
    return "adequately supported"


def _lagna_section(artifact: dict, L: Lang) -> dict:
    sigs, houses, sign_traits, nak_traits, dignities = L.tables()
    asc = artifact["ascendant"]
    lagna_lord = artifact["houses"][0]["lord"]
    lord_state = next(p for p in artifact["planets"] if p["planet"] == lagna_lord)
    text = L.t(
        "lagna.text",
        sign=L.sign(asc["signName"]), sign_trait=sign_traits[asc["signName"]],
        nak=L.nak(asc["nakshatra"]), pada=asc["pada"], nak_trait=nak_traits[asc["nakshatra"]],
        lord=L.planet(lagna_lord), lord_house=L.ordinal(lord_state["house"]),
        lord_sign=L.sign(lord_state["signName"]),
        dignity=dignities[lord_state["dignity"]],
        themes=houses[lord_state["house"]]["themes"],
    )
    return _item(
        L.t("lagna.title", sign=L.sign(asc["signName"])),
        text,
        [
            L.t("lagna.ev.asc", sign=L.sign(asc["signName"]),
                deg=f"{asc['degreesInSign']:.2f}", nak=L.nak(asc["nakshatra"]),
                pada=asc["pada"]),
            L.t("lagna.ev.lord", lord=L.planet(lagna_lord), house=lord_state["house"],
                sign=L.sign(lord_state["signName"]), dignity=L.dignity(lord_state["dignity"])),
        ],
    )


def _planet_sections(artifact: dict, L: Lang) -> list[dict]:
    sigs, houses, _st, _nt, dignities = L.tables()
    sections = []
    for p in artifact["planets"]:
        sig = sigs[p["planet"]]
        band = _shadbala_band(artifact, p["planet"])
        tone_key = "strong" if band == "strong" else "weak" if band == "weak" else None
        dignity_tone = (
            "strong" if p["dignity"] in ("exalted", "moolatrikona", "own") else
            "weak" if p["dignity"] in ("enemy", "debilitated") else None
        )
        tone = tone_key or dignity_tone or "strong"
        themes = houses[p["house"]]["themes"]

        clauses = [
            L.t("planet.head", title=sig["title"], karakas=sig["karakas"],
                house_ord=L.ordinal(p["house"]), sign=L.sign(p["signName"]),
                nak=L.nak(p["nakshatra"]), pada=p["pada"], dignity=dignities[p["dignity"]])
        ]
        if p["retrograde"] and p["planet"] not in ("rahu", "ketu"):
            clauses.append(L.t("planet.retro"))
        if p["combust"]:
            clauses.append(L.t("planet.combust"))
        if band:
            clauses.append(L.t("planet.band", band=L.band(band), effect=sig[tone], themes=themes))
        else:
            clauses.append(L.t("planet.channel", effect=sig[tone], themes=themes))

        evidence = [
            L.t("planet.ev.place", planet=L.planet(p["planet"]), sign=L.sign(p["signName"]),
                deg=f"{p['degreesInSign']:.2f}", house=p["house"],
                dignity=L.dignity(p["dignity"])),
        ]
        if p["retrograde"]:
            evidence.append(L.t("planet.ev.retro", planet=L.planet(p["planet"])))
        if p["combust"]:
            evidence.append(L.t("planet.ev.combust", planet=L.planet(p["planet"])))
        if band:
            row = next(
                r
                for r in artifact["strengthMetrics"]["shadbala"]
                if r["planet"] == p["planet"]
            )
            evidence.append(
                L.t("planet.ev.shadbala", ratio=f"{row['ratio']:.2f}", rupas=row["requiredRupas"])
            )

        sections.append(
            _item(
                L.t("planet.title", title=sig["title"], house_ord=L.ordinal(p["house"])),
                " ".join(clauses),
                evidence,
            )
        )
    return sections


def _house_sections(artifact: dict, L: Lang) -> list[dict]:
    _sg, houses, _st, _nt, _dg = L.tables()
    sav = artifact["strengthMetrics"]["sarvashtakavarga"]
    planets = {p["planet"]: p for p in artifact["planets"]}
    sections = []
    for house in artifact["houses"]:
        number = house["number"]
        theme = houses[number]
        lord = house["lord"]
        lord_state = planets[lord]
        bindus = sav[house["signIndex"]]
        occupants = house["occupants"]

        clauses = [
            L.t("house.l1", name=theme["name"], themes=theme["themes"],
                sign=L.sign(house["signName"]), band=L.band(_sav_band(bindus)), bindus=bindus)
        ]
        if occupants:
            clauses.append(L.t("house.occ", occ=L.planets(occupants)))
        else:
            clauses.append(L.t("house.empty", lord=L.planet(lord)))
        clauses.append(
            L.t("house.link", lord=L.planet(lord), house_ord=L.ordinal(lord_state["house"]),
                sign=L.sign(lord_state["signName"]), dignity=L.dignity(lord_state["dignity"]),
                a=theme["themes"].split(",")[0],
                b=houses[lord_state["house"]]["themes"].split(",")[0])
        )

        evidence = [
            L.t("house.ev.sav", n=number, sign=L.sign(house["signName"]), bindus=bindus),
            L.t("house.ev.lord", lord=L.planet(lord), h=lord_state["house"],
                dignity=L.dignity(lord_state["dignity"])),
        ]
        if occupants:
            evidence.append(L.t("house.ev.occ", occ=L.planets(occupants)))

        sections.append(_item(theme["name"], " ".join(clauses), evidence))
    return sections


def _yoga_sections(artifact: dict, L: Lang) -> list[dict]:
    sections = []
    for yoga in artifact["yogas"]:
        if not yoga["present"]:
            continue
        if L.hi:
            name, desc, evidence = localize_yoga(yoga)
            sections.append(_item(name, desc, evidence))
        else:
            sections.append(
                _item(yoga["name"], yoga["description"], list(yoga["evidence"]))
            )
    return sections


def _active_periods(dasha: dict, now: datetime) -> tuple[dict | None, dict | None]:
    def parse(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    for maha in dasha["mahadashas"]:
        if parse(maha["start"]) <= now < parse(maha["end"]):
            for antar in maha.get("children", []):
                if parse(antar["start"]) <= now < parse(antar["end"]):
                    return maha, antar
            return maha, None
    return None, None


def _dasha_section(artifact: dict, now: datetime, L: Lang) -> list[dict]:
    sigs, houses, _st, _nt, dignities = L.tables()
    maha, antar = _active_periods(artifact["vimshottari"], now)
    if maha is None:
        return []
    planets = {p["planet"]: p for p in artifact["planets"]}
    md = planets[maha["planet"]]
    md_sig = sigs[maha["planet"]]
    text = L.t(
        "dasha.text", title=md_sig["title"], house_ord=L.ordinal(md["house"]),
        sign=L.sign(md["signName"]), dignity=dignities[md["dignity"]],
        karakas=md_sig["karakas"], themes=houses[md["house"]]["themes"],
    )
    evidence = [
        L.t("dasha.ev.maha", planet=L.planet(maha["planet"]),
            start=maha["start"][:10], end=maha["end"][:10]),
        L.t("dasha.ev.natal", planet=L.planet(maha["planet"]), h=md["house"],
            sign=L.sign(md["signName"]), dignity=L.dignity(md["dignity"])),
    ]
    if antar is not None:
        ad = planets[antar["planet"]]
        ad_sig = sigs[antar["planet"]]
        text += L.t(
            "dasha.antar", planet=L.planet(antar["planet"]), end=antar["end"][:10],
            house_ord=L.ordinal(ad["house"]), themes=houses[ad["house"]]["themes"],
            karakas=ad_sig["karakas"],
        )
        evidence.append(
            L.t("dasha.ev.antar", planet=L.planet(antar["planet"]),
                start=antar["start"][:10], end=antar["end"][:10], h=ad["house"])
        )
    md_name = L.planet(maha["planet"])
    title = (
        L.t("dasha.title.mdad", md=md_name, ad=L.planet(antar["planet"]))
        if antar else L.t("dasha.title.md", md=md_name)
    )
    return [_item(title, text, evidence)]


def _varga_section(artifact: dict, L: Lang) -> list[dict]:
    from nakshatra_core.zodiac import SIGN_NAMES

    sections = []
    d9 = artifact["vargas"]["d9"]
    d10 = artifact["vargas"]["d10"]
    planets = {p["planet"]: p for p in artifact["planets"]}
    sn = lambda i: L.sign(SIGN_NAMES[i])  # noqa: E731

    venus_d9 = d9["planets"]["venus"]
    moon_d9 = d9["planets"]["moon"]
    sections.append(
        _item(
            L.t("varga.d9.title"),
            L.t("varga.d9.text", asc=sn(d9["ascendantSign"]), venus_d9=sn(venus_d9),
                moon_d9=sn(moon_d9), venus_rashi=L.sign(planets["venus"]["signName"]),
                moon_rashi=L.sign(planets["moon"]["signName"])),
            [
                L.t("varga.d9.ev1", asc=sn(d9["ascendantSign"])),
                L.t("varga.d9.ev2", venus=sn(venus_d9), moon=sn(moon_d9)),
            ],
        )
    )

    sun_d10 = d10["planets"]["sun"]
    saturn_d10 = d10["planets"]["saturn"]
    sections.append(
        _item(
            L.t("varga.d10.title"),
            L.t("varga.d10.text", asc=sn(d10["ascendantSign"]), sun=sn(sun_d10),
                saturn=sn(saturn_d10)),
            [
                L.t("varga.d10.ev1", asc=sn(d10["ascendantSign"])),
                L.t("varga.d10.ev2", sun=sn(sun_d10), saturn=sn(saturn_d10)),
            ],
        )
    )
    return sections


def _panchang_section(artifact: dict, L: Lang) -> dict:
    _sg, _h, _st, nak_traits, _dg = L.tables()
    pan = artifact["panchang"]
    args = dict(
        vara=L.vara(pan["vara"]["name"]), paksha=L.paksha(pan["tithi"]["paksha"]),
        tithi=L.tithi(pan["tithi"]["name"]), nak=L.nak(pan["moonNakshatra"]["name"]),
        pada=pan["moonNakshatra"]["pada"], yoga=L.pyoga(pan["yoga"]["name"]),
        karana=L.karana(pan["karana"]["name"]),
    )
    text = L.t("panchang.text", nak_trait=nak_traits[pan["moonNakshatra"]["name"]], **args)
    return _item(L.t("panchang.title"), text, [L.t("panchang.ev", **args)])


def build_reading(artifact: dict, now: datetime | None = None, lang: str = "en") -> dict:
    """Compose the full deterministic reading for a chart artifact."""
    L = Lang(lang)
    now = now or datetime.now(tz=UTC)
    return {
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
        "engineVersion": artifact["calculationMetadata"]["engineVersion"],
        "sections": [
            {"key": "lagna", "title": L.t("reading.sec.lagna"),
             "items": [_lagna_section(artifact, L)]},
            {"key": "planets", "title": L.t("reading.sec.planets"),
             "items": _planet_sections(artifact, L)},
            {"key": "houses", "title": L.t("reading.sec.houses"),
             "items": _house_sections(artifact, L)},
            {"key": "yogas", "title": L.t("reading.sec.yogas"),
             "items": _yoga_sections(artifact, L)},
            {"key": "dasha", "title": L.t("reading.sec.dasha"),
             "items": _dasha_section(artifact, now, L)},
            {"key": "vargas", "title": L.t("reading.sec.vargas"),
             "items": _varga_section(artifact, L)},
            {"key": "panchang", "title": L.t("reading.sec.panchang"),
             "items": [_panchang_section(artifact, L)]},
        ],
        "lifeStory": build_life_story(artifact, now, lang),
    }
