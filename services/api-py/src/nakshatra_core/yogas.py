"""Yoga and dosha detection - exact port of yogas.ts.

Every detector returns a result with a `present` flag plus evidence, so the
UI and rule engine can show both fired and explicitly-absent yogas.
"""

from .aspects import sign_count
from .dignities import dignity_of
from .zodiac import SIGN_LORDS, SIGN_NAMES

_KENDRA = (1, 4, 7, 10)
_STRONG = ("exalted", "moolatrikona", "own")
_SEVEN = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")
_SUPPORTERS = ("mercury", "venus", "mars", "jupiter", "saturn")
_BENEFICS = ("mercury", "venus", "jupiter")


def _placement(planet: str, inp: dict) -> str:
    return (
        f"{planet} in {SIGN_NAMES[inp['signs'][planet]]} "
        f"(house {sign_count(inp['ascendantSign'], inp['signs'][planet])})"
    )


def _house_of(inp: dict, planet: str) -> int:
    return sign_count(inp["ascendantSign"], inp["signs"][planet])


def _from_moon(inp: dict, planet: str) -> int:
    return sign_count(inp["signs"]["moon"], inp["signs"][planet])


def _lord_of(inp: dict, house: int) -> str:
    return inp["houseLords"][house - 1]


def _result(key, name, present, description, evidence, category) -> dict:
    return {
        "key": key,
        "name": name,
        "present": present,
        "description": description,
        "evidence": evidence,
        "category": category,
    }


def _gajakesari(inp: dict) -> dict:
    count = sign_count(inp["signs"]["moon"], inp["signs"]["jupiter"])
    return _result(
        "gajakesari",
        "Gajakesari Yoga",
        count in _KENDRA,
        "Jupiter in a kendra (1st, 4th, 7th, or 10th) from the Moon, associated "
        "with wisdom, reputation, and lasting prosperity.",
        [
            _placement("moon", inp),
            _placement("jupiter", inp),
            f"Jupiter is {count} signs from the Moon (kendra positions: 1, 4, 7, 10).",
        ],
        "raj",
    )


def _budhaditya(inp: dict) -> dict:
    return _result(
        "budhaditya",
        "Budhaditya Yoga",
        inp["signs"]["sun"] == inp["signs"]["mercury"],
        "Sun and Mercury conjunct in one sign, associated with intelligence, "
        "communication skill, and administrative ability.",
        [_placement("sun", inp), _placement("mercury", inp)],
        "raj",
    )


def _chandra_mangal(inp: dict) -> dict:
    count = sign_count(inp["signs"]["moon"], inp["signs"]["mars"])
    return _result(
        "chandra-mangal",
        "Chandra-Mangal Yoga",
        count in (1, 7),
        "Moon and Mars in conjunction or mutual opposition, associated with "
        "earning drive and material enterprise.",
        [
            _placement("moon", inp),
            _placement("mars", inp),
            f"Mars is {count} signs from the Moon.",
        ],
        "dhan",
    )


_MAHAPURUSHA = (
    ("ruchaka", "Ruchaka Yoga (Mars Mahapurusha)", "mars"),
    ("bhadra", "Bhadra Yoga (Mercury Mahapurusha)", "mercury"),
    ("hamsa", "Hamsa Yoga (Jupiter Mahapurusha)", "jupiter"),
    ("malavya", "Malavya Yoga (Venus Mahapurusha)", "venus"),
    ("sasa", "Sasa Yoga (Saturn Mahapurusha)", "saturn"),
)


def _mahapurusha(inp: dict) -> list[dict]:
    results = []
    for key, name, planet in _MAHAPURUSHA:
        house_count = sign_count(inp["ascendantSign"], inp["signs"][planet])
        dignity = dignity_of(planet, inp["longitudes"][planet])
        results.append(
            _result(
                key,
                name,
                house_count in _KENDRA and dignity in _STRONG,
                f"{planet} in its own or exaltation sign placed in a kendra "
                f"from the lagna.",
                [
                    _placement(planet, inp),
                    f"{planet} dignity: {dignity}.",
                    f"{planet} occupies house {house_count} from the lagna.",
                ],
                "pancha-mahapurusha",
            )
        )
    return results


def _kemadruma(inp: dict) -> dict:
    moon_sign = inp["signs"]["moon"]
    flanks = ((moon_sign + 1) % 12, (moon_sign + 11) % 12)
    support = [
        p
        for p in _SUPPORTERS
        if inp["signs"][p] in flanks or inp["signs"][p] == moon_sign
    ]
    present = len(support) == 0
    return _result(
        "kemadruma",
        "Kemadruma Yoga",
        present,
        "No planet (excluding Sun, Rahu, Ketu) conjoins the Moon or occupies "
        "the 2nd or 12th from it; classically linked to isolation and "
        "fluctuating fortunes.",
        (
            [
                _placement("moon", inp),
                "No supporting planet in the 2nd or 12th from the Moon or with "
                "the Moon.",
            ]
            if present
            else [
                _placement("moon", inp),
                f"Supporting planets around the Moon: {', '.join(support)}.",
            ]
        ),
        "dosha",
    )


def _kaal_sarp(inp: dict) -> dict:
    rahu = inp["longitudes"]["rahu"]
    ketu = inp["longitudes"]["ketu"]

    def side_of(lon: float) -> int:
        from_rahu = (lon - rahu + 360) % 360
        axis_span = (ketu - rahu + 360) % 360
        return 0 if from_rahu < axis_span else 1

    sides = {side_of(inp["longitudes"][p]) for p in _SEVEN}
    present = len(sides) == 1
    return _result(
        "kaal-sarp",
        "Kaal Sarp Yoga",
        present,
        "All seven classical planets hemmed on one side of the Rahu-Ketu axis; "
        "traditionally read as concentrated karmic intensity.",
        [
            f"Rahu at {rahu:.2f} deg, Ketu at {ketu:.2f} deg.",
            (
                "All seven classical planets fall on one side of the nodal axis."
                if present
                else "Planets occupy both sides of the nodal axis."
            ),
        ],
        "dosha",
    )


def _flank_yoga(inp, key, name, anchor, offset, description, category) -> dict:
    target = (inp["signs"][anchor] + offset) % 12
    found = [p for p in _SUPPORTERS if inp["signs"][p] == target]
    house_word = "2nd" if offset == 1 else "12th"
    anchor_title = anchor.capitalize()
    return _result(
        key,
        name,
        len(found) > 0,
        description,
        [
            _placement(anchor, inp),
            (
                f"{', '.join(found)} in the {house_word} from {anchor_title} "
                f"({SIGN_NAMES[target]})."
                if found
                else f"No qualifying planet in the {house_word} from {anchor_title}."
            ),
        ],
        category,
    )


def _sunapha(inp: dict) -> dict:
    return _flank_yoga(
        inp, "sunapha", "Sunapha Yoga", "moon", 1,
        "A planet in the 2nd house from the Moon; indicates self-made wealth, "
        "good intellect, and prosperity through one's own efforts.",
        "lunar",
    )


def _anapha(inp: dict) -> dict:
    return _flank_yoga(
        inp, "anapha", "Anapha Yoga", "moon", 11,
        "A planet in the 12th house from the Moon; indicates good health, "
        "virtue, and comfortable living.",
        "lunar",
    )


def _durudhara(inp: dict) -> dict:
    second = (inp["signs"]["moon"] + 1) % 12
    twelfth = (inp["signs"]["moon"] + 11) % 12
    in_2nd = [p for p in _SUPPORTERS if inp["signs"][p] == second]
    in_12th = [p for p in _SUPPORTERS if inp["signs"][p] == twelfth]
    return _result(
        "durudhara",
        "Durudhara Yoga",
        bool(in_2nd) and bool(in_12th),
        "Planets flanking the Moon on both sides (2nd and 12th from it); "
        "indicates wealth, generosity, and a life of comforts.",
        [
            _placement("moon", inp),
            f"In 2nd from Moon: {', '.join(in_2nd)}." if in_2nd
            else "No planet in 2nd from Moon.",
            f"In 12th from Moon: {', '.join(in_12th)}." if in_12th
            else "No planet in 12th from Moon.",
        ],
        "lunar",
    )


def _voshi(inp: dict) -> dict:
    return _flank_yoga(
        inp, "voshi", "Voshi Yoga", "sun", 1,
        "A planet in the 2nd house from the Sun; indicates eloquence, "
        "learning, and charitable disposition.",
        "solar",
    )


def _veshi(inp: dict) -> dict:
    return _flank_yoga(
        inp, "veshi", "Veshi Yoga", "sun", 11,
        "A planet in the 12th house from the Sun; indicates authority, power, "
        "and steady temperament.",
        "solar",
    )


def _ubhayachari(inp: dict) -> dict:
    second = (inp["signs"]["sun"] + 1) % 12
    twelfth = (inp["signs"]["sun"] + 11) % 12
    in_2nd = [p for p in _SUPPORTERS if inp["signs"][p] == second]
    in_12th = [p for p in _SUPPORTERS if inp["signs"][p] == twelfth]
    return _result(
        "ubhayachari",
        "Ubhayachari Yoga",
        bool(in_2nd) and bool(in_12th),
        "Planets flanking the Sun on both sides (2nd and 12th); indicates a "
        "powerful, kingly personality with commanding presence.",
        [
            _placement("sun", inp),
            f"In 2nd from Sun: {', '.join(in_2nd)}." if in_2nd
            else "No planet in 2nd from Sun.",
            f"In 12th from Sun: {', '.join(in_12th)}." if in_12th
            else "No planet in 12th from Sun.",
        ],
        "solar",
    )


def _adhi(inp: dict) -> dict:
    found = [p for p in _BENEFICS if _from_moon(inp, p) in (6, 7, 8)]
    present = len(found) >= 2
    evidence = [_placement("moon", inp)]
    evidence += [f"{p} in house {_from_moon(inp, p)} from Moon." for p in found]
    evidence.append(
        f"{len(found)} benefic(s) in the 6th/7th/8th houses from Moon."
        if present
        else "Insufficient benefics in 6th/7th/8th from Moon."
    )
    return _result(
        "adhi",
        "Adhi Yoga",
        present,
        "Natural benefics occupy the 6th, 7th, and 8th from the Moon; indicates "
        "high status, authority, and victory over adversaries.",
        evidence,
        "raj",
    )


def _amala(inp: dict) -> dict:
    from_lagna = [p for p in _BENEFICS if _house_of(inp, p) == 10]
    from_moon = [p for p in _BENEFICS if _from_moon(inp, p) == 10]
    all_found = list(dict.fromkeys(from_lagna + from_moon))
    present = len(all_found) > 0
    evidence = [f"{p} in the 10th from lagna." for p in from_lagna]
    evidence += [f"{p} in the 10th from Moon." for p in from_moon]
    if not present:
        evidence.append("No natural benefic in the 10th house.")
    return _result(
        "amala",
        "Amala Yoga",
        present,
        "A natural benefic in the 10th house from lagna or Moon; indicates an "
        "unblemished reputation, philanthropy, and lasting fame.",
        evidence,
        "raj",
    )


def _manglik(inp: dict) -> dict:
    mars_house = _house_of(inp, "mars")
    present = mars_house in (1, 2, 4, 7, 8, 12)
    cancellations = []
    if present:
        jup_mars = sign_count(inp["signs"]["jupiter"], inp["signs"]["mars"])
        if jup_mars in (1, 5, 7, 9):
            cancellations.append("Jupiter aspects or conjoins Mars.")
        if inp["dignities"]["mars"] in _STRONG:
            cancellations.append(
                f"Mars is {inp['dignities']['mars']}, reducing the dosha effect."
            )
    return _result(
        "manglik",
        "Manglik Dosha (Kuja Dosha)",
        present,
        "Mars in houses 1, 2, 4, 7, 8, or 12 from the lagna; traditionally "
        "assessed for marital compatibility. Cancellation conditions may "
        "mitigate the effect.",
        [
            _placement("mars", inp),
            f"Mars occupies house {mars_house} from lagna.",
            *cancellations,
        ],
        "dosha",
    )


def _guru_chandal(inp: dict) -> dict:
    return _result(
        "guru-chandal",
        "Guru Chandal Yoga",
        inp["signs"]["jupiter"] == inp["signs"]["rahu"],
        "Jupiter conjoined with Rahu in the same sign; may indicate "
        "unconventional wisdom, disrupted advice from teachers, or unorthodox "
        "spiritual leanings.",
        [_placement("jupiter", inp), _placement("rahu", inp)],
        "dosha",
    )


def _pitra_dosha(inp: dict) -> dict:
    sun_rahu = inp["signs"]["sun"] == inp["signs"]["rahu"]
    sun_ketu = inp["signs"]["sun"] == inp["signs"]["ketu"]
    present = sun_rahu or sun_ketu
    evidence = [_placement("sun", inp)]
    if sun_rahu:
        evidence.append(_placement("rahu", inp))
    if sun_ketu:
        evidence.append(_placement("ketu", inp))
    evidence.append(
        f"Sun conjoined with {'Rahu' if sun_rahu else 'Ketu'} in "
        f"{SIGN_NAMES[inp['signs']['sun']]}."
        if present
        else "Sun is not conjunct either node."
    )
    return _result(
        "pitra-dosha",
        "Pitra Dosha",
        present,
        "Sun conjunct Rahu or Ketu; indicates ancestral karmic debts that may "
        "manifest as obstacles or delayed results in life.",
        evidence,
        "dosha",
    )


def _raj_yogas(inp: dict) -> dict:
    pairs = []
    for kh in (1, 4, 7, 10):
        for th in (1, 5, 9):
            if kh == th:
                continue
            k_lord = _lord_of(inp, kh)
            t_lord = _lord_of(inp, th)
            if k_lord == t_lord:
                pairs.append((kh, th, k_lord))
            elif inp["signs"][k_lord] == inp["signs"][t_lord]:
                pairs.append((kh, th, f"{k_lord}+{t_lord}"))
    return _result(
        "raj-yoga",
        "Raj Yoga (Kendra-Trikona)",
        len(pairs) > 0,
        "Lord of a kendra and lord of a trikona conjoined or the same planet "
        "rules both; one of the most auspicious combinations indicating power, "
        "success, and recognition.",
        (
            [
                f"Lord of {kh}th (kendra) and lord of {th}th (trikona): {planet}."
                for kh, th, planet in pairs
            ]
            if pairs
            else ["No kendra-trikona lord conjunction found."]
        ),
        "raj",
    )


def _dhana_yoga(inp: dict) -> dict:
    lord2 = _lord_of(inp, 2)
    lord11 = _lord_of(inp, 11)
    conjunct = inp["signs"][lord2] == inp["signs"][lord11]
    aspect = sign_count(inp["signs"][lord2], inp["signs"][lord11]) == 7
    present = lord2 != lord11 and (conjunct or aspect)
    if conjunct:
        relation = "Lords of 2nd and 11th are conjunct."
    elif aspect:
        relation = "Lords of 2nd and 11th are in mutual 7th aspect."
    else:
        relation = "No conjunction or mutual aspect between lords of 2nd and 11th."
    return _result(
        "dhana-yoga",
        "Dhana Yoga",
        present,
        "Lord of the 2nd house conjoined with or in mutual aspect with the lord "
        "of the 11th; indicates wealth accumulation and strong financial gains.",
        [
            f"Lord of 2nd: {lord2} ({_placement(lord2, inp)}).",
            f"Lord of 11th: {lord11} ({_placement(lord11, inp)}).",
            relation,
        ],
        "dhan",
    )


def _vipreet_raj(inp: dict) -> dict:
    spec = ((6, (8, 12), "Harsha"), (8, (6, 12), "Sarala"), (12, (6, 8), "Vimala"))
    matches = []
    for house, others, vname in spec:
        lord = _lord_of(inp, house)
        lord_house = _house_of(inp, lord)
        if lord_house in others:
            matches.append(
                f"{vname} Yoga: lord of {house}th ({lord}) placed in house "
                f"{lord_house}."
            )
    return _result(
        "vipreet-raj",
        "Vipreet Raj Yoga",
        len(matches) > 0,
        "Lord of a dusthana (6th, 8th, or 12th) placed in another dusthana; "
        "turns adversity into advantage - obstacles become sources of "
        "unexpected gain.",
        matches if matches else ["No dusthana lord is placed in another dusthana."],
        "raj",
    )


def _neecha_bhanga(inp: dict) -> dict:
    debilitated = [p for p in _SEVEN if inp["dignities"][p] == "debilitated"]
    cancelled = []
    for planet in debilitated:
        dispositor = SIGN_LORDS[inp["signs"][planet]]
        disp_house = _house_of(inp, dispositor)
        if disp_house in _KENDRA:
            cancelled.append(
                f"{planet} is debilitated; its dispositor {dispositor} is in "
                f"kendra (house {disp_house})."
            )
        if inp["dignities"][dispositor] in _STRONG:
            cancelled.append(
                f"{planet} is debilitated; its dispositor {dispositor} is "
                f"{inp['dignities'][dispositor]}."
            )
    if cancelled:
        evidence = cancelled
    elif debilitated:
        evidence = [
            f"Debilitated planet(s): {', '.join(debilitated)} but no "
            f"cancellation conditions met."
        ]
    else:
        evidence = ["No debilitated planet found."]
    return _result(
        "neecha-bhanga",
        "Neecha Bhanga Raj Yoga",
        len(cancelled) > 0,
        "A debilitated planet whose weakness is cancelled by specific "
        "conditions (strong dispositor, etc.); transforms a difficult "
        "placement into a source of great strength.",
        evidence,
        "raj",
    )


def _saraswati(inp: dict) -> dict:
    qualifying = (1, 2, 4, 5, 7, 9, 10)
    targets = ("jupiter", "venus", "mercury")
    in_qualifying = [p for p in targets if _house_of(inp, p) in qualifying]
    jupiter_strong = inp["dignities"]["jupiter"] not in ("debilitated", "enemy")
    return _result(
        "saraswati",
        "Saraswati Yoga",
        len(in_qualifying) == 3 and jupiter_strong,
        "Jupiter, Venus, and Mercury all in kendras, trikonas, or the 2nd house "
        "with Jupiter dignified; confers learning, eloquence, mastery of arts "
        "and sciences.",
        [
            *(
                f"{p} in house {_house_of(inp, p)} ({inp['dignities'][p]})."
                for p in targets
            ),
            "Jupiter is dignified."
            if jupiter_strong
            else "Jupiter is weak (debilitated or in enemy sign).",
        ],
        "raj",
    )


def _lakshmi(inp: dict) -> dict:
    lord9 = _lord_of(inp, 9)
    lord9_house = _house_of(inp, lord9)
    is_strong = inp["dignities"][lord9] in _STRONG
    in_kendra = lord9_house in _KENDRA
    present = in_kendra and is_strong
    if present:
        status = "Lord of 9th is strong in a kendra."
    elif is_strong:
        status = "Lord of 9th is strong but not in a kendra."
    elif in_kendra:
        status = "Lord of 9th is in a kendra but not strong."
    else:
        status = "Lord of 9th is neither in a kendra nor strong."
    return _result(
        "lakshmi",
        "Lakshmi Yoga",
        present,
        "Lord of the 9th house placed in a kendra in its own, exalted, or "
        "moolatrikona sign; indicates immense wealth, fortune, and divine grace.",
        [
            f"Lord of 9th: {lord9} ({_placement(lord9, inp)}).",
            f"Dignity: {inp['dignities'][lord9]}. House: {lord9_house}.",
            status,
        ],
        "dhan",
    )


def _grahan(inp: dict) -> dict:
    signs = inp["signs"]
    eclipses = []
    if signs["sun"] == signs["rahu"]:
        eclipses.append("Sun conjunct Rahu (solar eclipse pattern).")
    if signs["sun"] == signs["ketu"]:
        eclipses.append("Sun conjunct Ketu (solar eclipse pattern).")
    if signs["moon"] == signs["rahu"]:
        eclipses.append("Moon conjunct Rahu (lunar eclipse pattern).")
    if signs["moon"] == signs["ketu"]:
        eclipses.append("Moon conjunct Ketu (lunar eclipse pattern).")
    return _result(
        "grahan",
        "Grahan Yoga",
        len(eclipses) > 0,
        "A luminary (Sun or Moon) conjoined with a node (Rahu or Ketu); "
        "indicates karmic intensity around the luminary's significations - "
        "identity (Sun) or mind/emotions (Moon).",
        eclipses if eclipses else ["Neither luminary is conjunct a node."],
        "dosha",
    )


def detect_yogas(inp: dict) -> list[dict]:
    return [
        _gajakesari(inp),
        _budhaditya(inp),
        _raj_yogas(inp),
        _vipreet_raj(inp),
        _neecha_bhanga(inp),
        _adhi(inp),
        _amala(inp),
        _saraswati(inp),
        _lakshmi(inp),
        _chandra_mangal(inp),
        _dhana_yoga(inp),
        *_mahapurusha(inp),
        _sunapha(inp),
        _anapha(inp),
        _durudhara(inp),
        _voshi(inp),
        _veshi(inp),
        _ubhayachari(inp),
        _manglik(inp),
        _guru_chandal(inp),
        _pitra_dosha(inp),
        _grahan(inp),
        _kemadruma(inp),
        _kaal_sarp(inp),
    ]
