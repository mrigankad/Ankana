"""Remedies engine - exact port of rule-engine remedies.ts.

Gemstones sit behind a hard functional-benefic gate; every remedy carries
rationale, evidence, and cautions.
"""

from nakshatra_i18n import REMEDY_DATA_HI, Lang

_REMEDY_DATA: dict[str, dict[str, str]] = {
    "sun": {
        "mantra": "Om Hram Hrim Hraum Sah Suryaya Namah",
        "mantraCount": "7000 repetitions over 40 days",
        "daan": "wheat, jaggery, or copper on a Sunday",
        "fastingDay": "Sunday",
        "gemstone": "Ruby (manik)",
        "deity": "Surya / Aditya",
    },
    "moon": {
        "mantra": "Om Shram Shrim Shraum Sah Chandraya Namah",
        "mantraCount": "11000 repetitions over 40 days",
        "daan": "rice, milk, or white cloth on a Monday",
        "fastingDay": "Monday",
        "gemstone": "Pearl (moti)",
        "deity": "Chandra / Shiva",
    },
    "mars": {
        "mantra": "Om Kram Krim Kraum Sah Bhaumaya Namah",
        "mantraCount": "10000 repetitions over 40 days",
        "daan": "red lentils (masoor) or jaggery on a Tuesday",
        "fastingDay": "Tuesday",
        "gemstone": "Red coral (moonga)",
        "deity": "Hanuman / Kartikeya",
    },
    "mercury": {
        "mantra": "Om Bram Brim Braum Sah Budhaya Namah",
        "mantraCount": "9000 repetitions over 40 days",
        "daan": "green moong or education material on a Wednesday",
        "fastingDay": "Wednesday",
        "gemstone": "Emerald (panna)",
        "deity": "Vishnu",
    },
    "jupiter": {
        "mantra": "Om Gram Grim Graum Sah Gurave Namah",
        "mantraCount": "19000 repetitions over 40 days",
        "daan": "chana dal, turmeric, or books on a Thursday",
        "fastingDay": "Thursday",
        "gemstone": "Yellow sapphire (pukhraj)",
        "deity": "Brihaspati / Dakshinamurthy",
    },
    "venus": {
        "mantra": "Om Dram Drim Draum Sah Shukraya Namah",
        "mantraCount": "16000 repetitions over 40 days",
        "daan": "white rice, curd, or white clothing on a Friday",
        "fastingDay": "Friday",
        "gemstone": "Diamond or white sapphire",
        "deity": "Lakshmi",
    },
    "saturn": {
        "mantra": "Om Pram Prim Praum Sah Shanaye Namah",
        "mantraCount": "23000 repetitions over 40 days",
        "daan": "black sesame, mustard oil, or iron on a Saturday",
        "fastingDay": "Saturday",
        "gemstone": "Blue sapphire (neelam)",
        "deity": "Shani / Hanuman",
    },
    "rahu": {
        "mantra": "Om Bhram Bhrim Bhraum Sah Rahave Namah",
        "mantraCount": "18000 repetitions over 40 days",
        "daan": "blankets or dark-blue items to those in need",
        "fastingDay": "Saturday",
        "gemstone": "Hessonite (gomed)",
        "deity": "Durga",
    },
    "ketu": {
        "mantra": "Om Sram Srim Sraum Sah Ketave Namah",
        "mantraCount": "17000 repetitions over 40 days",
        "daan": "multi-coloured blankets or dog care on a Thursday",
        "fastingDay": "Thursday",
        "gemstone": "Cat's eye (lehsunia)",
        "deity": "Ganesha",
    },
}

_GEMSTONE_CAUTION_KEYS = ("rem.gem.caution1", "rem.gem.caution2", "rem.gem.caution3")

_TRIKONA = (1, 5, 9)
_DUSTHANA = (6, 8, 12)


def is_functional_benefic(planet: str, artifact: dict) -> bool:
    """The planet must rule at least one trikona for this lagna and must not
    rule only dusthanas (simplified, testable gate)."""
    owned = [h["number"] for h in artifact["houses"] if h["lord"] == planet]
    if not owned:
        return False
    owns_trikona = any(h in _TRIKONA for h in owned)
    owns_only_dusthana = all(h in _DUSTHANA for h in owned)
    return owns_trikona and not owns_only_dusthana


def evaluate_remedies(artifact: dict, lang: str = "en") -> list[dict]:
    L = Lang(lang)
    table = REMEDY_DATA_HI if L.hi else _REMEDY_DATA
    remedies: list[dict] = []
    ratio_of = {
        r["planet"]: r["ratio"] for r in artifact["strengthMetrics"]["shadbala"]
    }

    for planet in artifact["planets"]:
        data = table.get(planet["planet"])
        if data is None:
            continue
        pname = L.planet(planet["planet"])

        ratio = ratio_of.get(planet["planet"])
        weak = ratio is not None and ratio < 1
        afflicted = (
            planet["combust"]
            or planet["dignity"] == "debilitated"
            or planet["dignity"] == "enemy"
        )
        is_node = planet["planet"] in ("rahu", "ketu")

        if not weak and not afflicted and not is_node:
            continue
        # Nodes only earn remedies when genuinely afflicting: in dusthana.
        if is_node and planet["house"] not in _DUSTHANA:
            continue

        evidence = [
            L.t("rem.ev.place", planet=pname, sign=L.sign(planet["signName"]),
                house=planet["house"], dignity=L.dignity(planet["dignity"]))
        ]
        if ratio is not None:
            evidence.append(L.t("rem.ev.ratio", ratio=f"{ratio:.2f}"))
        if planet["combust"]:
            evidence.append(L.t("rem.ev.combust", planet=pname))

        if afflicted and weak:
            severity = "strong"
        elif afflicted or weak:
            severity = "moderate"
        else:
            severity = "optional"

        remedies.append(
            {
                "kind": "mantra",
                "planet": planet["planet"],
                "title": L.t("rem.mantra.title", deity=data["deity"], planet=pname),
                "practice": L.t("rem.mantra.practice", mantra=data["mantra"],
                                count=data["mantraCount"]),
                "rationale": L.t("rem.mantra.rationale", planet=pname),
                "evidence": evidence,
                "strengthOfRecommendation": severity,
                "cautions": [],
            }
        )
        remedies.append(
            {
                "kind": "daan",
                "planet": planet["planet"],
                "title": L.t("rem.daan.title", planet=pname),
                "practice": L.t("rem.daan.practice", daan=data["daan"]),
                "rationale": L.t("rem.daan.rationale", planet=pname),
                "evidence": evidence,
                "strengthOfRecommendation": severity,
                "cautions": [],
            }
        )

        if weak or afflicted:
            remedies.append(
                {
                    "kind": "fasting",
                    "planet": planet["planet"],
                    "title": L.t("rem.fast.title", day=data["fastingDay"]),
                    "practice": L.t("rem.fast.practice", day=data["fastingDay"]),
                    "rationale": L.t("rem.fast.rationale", planet=pname),
                    "evidence": evidence,
                    "strengthOfRecommendation": "optional",
                    "cautions": [L.t("rem.fast.caution")],
                }
            )

        # Gemstone: HARD GATE - functional benefic AND weak AND not
        # afflicted-without-cancellation. Otherwise recommend the mantra path.
        gate_open = (
            is_functional_benefic(planet["planet"], artifact)
            and weak
            and not planet["combust"]
            and planet["dignity"] != "debilitated"
        )
        if gate_open:
            remedies.append(
                {
                    "kind": "gemstone",
                    "planet": planet["planet"],
                    "title": L.t("rem.gem.title", gem=data["gemstone"]),
                    "practice": L.t("rem.gem.practice", gem=data["gemstone"], planet=pname),
                    "rationale": L.t("rem.gem.rationale", planet=pname),
                    "evidence": evidence,
                    "strengthOfRecommendation": "optional",
                    "cautions": [L.t(k) for k in _GEMSTONE_CAUTION_KEYS],
                }
            )

    return remedies
