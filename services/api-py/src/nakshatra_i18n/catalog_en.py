"""English message catalog. These templates reproduce the engine's original
English output byte for byte (tests/golden/interpret_en.json guards that).
Placeholders use str.format syntax; every key must exist in catalog_hi with the
same placeholder set."""

EN: dict[str, str] = {
    # ---- reading: section titles
    "reading.sec.lagna": "Lagna & temperament",
    "reading.sec.planets": "Planet by planet",
    "reading.sec.houses": "House by house",
    "reading.sec.yogas": "Active yogas & doshas",
    "reading.sec.dasha": "Current dasha phala",
    "reading.sec.vargas": "Divisional highlights",
    "reading.sec.panchang": "Birth panchang",

    # ---- reading: lagna
    "lagna.title": "{sign} Lagna - temperament and life direction",
    "lagna.text": (
        "The lagna rises in {sign} ({sign_trait}), within {nak} nakshatra pada {pada}, "
        "which colours the personality with {nak_trait}. The lagna lord {lord} sits in "
        "the {lord_house} house in {lord_sign}, {dignity}; life direction therefore "
        "flows strongly through {themes}."
    ),
    "lagna.ev.asc": "Ascendant {sign} {deg} deg, {nak} pada {pada}.",
    "lagna.ev.lord": "Lagna lord {lord} in house {house} ({sign}, {dignity}).",

    # ---- reading: planets
    "planet.title": "{title} in the {house_ord} house",
    "planet.head": (
        "{title} - karaka of {karakas} - occupies the {house_ord} house in {sign} "
        "({nak} pada {pada}), {dignity}."
    ),
    "planet.retro": (
        "Retrograde motion internalises its agenda: results deepen with revision, "
        "review, and second attempts."
    ),
    "planet.combust": (
        "Combustion by the Sun folds its significations into questions of identity and "
        "visibility; its gifts shine brightest in service of a larger role rather than "
        "for their own display."
    ),
    "planet.band": "Shadbala rates it {band}, so expect {effect} in matters of {themes}.",
    "planet.channel": "Through this placement it channels {effect} into {themes}.",
    "planet.ev.place": "{planet} in {sign} {deg} deg, house {house}, dignity {dignity}.",
    "planet.ev.retro": "{planet} retrograde.",
    "planet.ev.combust": "{planet} combust.",
    "planet.ev.shadbala": "Shadbala ratio {ratio} (required {rupas} rupas).",

    # ---- reading: houses
    "house.l1": (
        "The {name} ({themes}) falls in {sign} and is {band} with {bindus} "
        "Sarvashtakavarga bindus."
    ),
    "house.occ": "Occupied by {occ}, its affairs stay active and personally significant.",
    "house.empty": "With no occupants, its results flow chiefly through its lord {lord}.",
    "house.link": (
        "The lord {lord} is placed in the {house_ord} house ({sign}, {dignity}), "
        "linking {a} with {b}."
    ),
    "house.ev.sav": "House {n} = {sign}, SAV bindus {bindus}.",
    "house.ev.lord": "Lord {lord} in house {h} ({dignity}).",
    "house.ev.occ": "Occupants: {occ}.",

    # ---- reading: dasha
    "dasha.text": (
        "The running mahadasha belongs to {title}, placed natally in the {house_ord} "
        "house in {sign} ({dignity}). This period foregrounds {karakas}, expressed "
        "through {themes}."
    ),
    "dasha.antar": (
        " Within it, the {planet} antardasha (until {end}) filters events through the "
        "{house_ord} house - {themes} - bringing {karakas} to the front of daily life."
    ),
    "dasha.ev.maha": "{planet} mahadasha {start} to {end}.",
    "dasha.ev.natal": "Natal {planet} in house {h} ({sign}, {dignity}).",
    "dasha.ev.antar": "{planet} antardasha {start} to {end}; natal {planet} in house {h}.",
    "dasha.title.md": "Current period: {md} mahadasha",
    "dasha.title.mdad": "Current period: {md} mahadasha / {ad} antardasha",

    # ---- reading: vargas
    "varga.d9.title": "Navamsa (D9) - marriage and inner strength",
    "varga.d9.text": (
        "In the navamsa the lagna falls in {asc}. Venus, karaka of marriage, moves to "
        "{venus_d9} and the Moon to {moon_d9}; comparing these with their rashi "
        "positions ({venus_rashi}, {moon_rashi}) shows how relationships mature "
        "beneath the surface of the birth chart."
    ),
    "varga.d9.ev1": "D9 ascendant {asc}.",
    "varga.d9.ev2": "D9 Venus {venus}; D9 Moon {moon}.",
    "varga.d10.title": "Dashamsa (D10) - career expression",
    "varga.d10.text": (
        "In the dashamsa the lagna falls in {asc}. The Sun (authority) occupies {sun} "
        "and Saturn (sustained labour) {saturn}, describing the texture of "
        "professional life beyond the 10th house of the rashi chart."
    ),
    "varga.d10.ev1": "D10 ascendant {asc}.",
    "varga.d10.ev2": "D10 Sun {sun}; D10 Saturn {saturn}.",

    # ---- reading: panchang
    "panchang.title": "Birth panchang",
    "panchang.text": (
        "Born on {vara} during {paksha} paksha {tithi} tithi, under {nak} nakshatra "
        "(pada {pada}) with {yoga} yoga and {karana} karana. The birth nakshatra "
        "lends the mind {nak_trait}."
    ),
    "panchang.ev": (
        "Tithi {tithi} ({paksha}), karana {karana}, yoga {yoga}, vara {vara}, "
        "Moon nakshatra {nak} pada {pada}."
    ),

    # ---- life story: age bands (title/focus)
    "ls.band.childhood.title": "Childhood",
    "ls.band.childhood.focus": "home, care, temperament, and early emotional foundations",
    "ls.band.youth.title": "Youth",
    "ls.band.youth.focus": "learning, peers, courage, and identity formation",
    "ls.band.early-adulthood.title": "Early adulthood",
    "ls.band.early-adulthood.focus": "partnership, career direction, and building resources",
    "ls.band.midlife.title": "Midlife",
    "ls.band.midlife.focus": "authority, gains, and deeper transformation",
    "ls.band.later-life.title": "Later life",
    "ls.band.later-life.focus": "dharma, release, and returning to roots",

    # ---- life story: items
    "ls.child.title": "Temperament and home foundations",
    "ls.child.text": (
        "Childhood colour comes from the Moon in the {moon_house} house ({sign}, {nak}) "
        "- {nak_trait} - and from lagna lord {ll_title} in the {ll_house} house, "
        "shaping early {h4} and {h1}."
    ),
    "ls.child.ev.moon": "Moon in house {h} ({sign}, {nak} pada {pada}).",
    "ls.child.ev.lord": "Lagna lord {lord} in house {h} ({sign}, {dignity}).",
    "ls.stage.title": "{name} themes",
    "ls.stage.text": (
        "This stage weighs {themes}. The {house_ord} house is ruled by {lord_title}, "
        "placed in the {lh_ord} house in {sign} ({dignity}).{occ_phrase}"
    ),
    "ls.stage.occ": " Occupied by {occ}.",
    "ls.stage.noocc": " No natal planets occupy it; the lord carries the theme.",
    "ls.stage.ev.lord": "House {n} lord {lord} in house {h} ({sign}, {dignity}).",
    "ls.stage.ev.occ": "House {n} occupants: {occ}.",
    "ls.maha.colour": "{display} mahadasha colour",
    "ls.promise": (
        "{title} sits natally in the {house_ord} house in {sign} ({dignity}), channeling "
        "{karakas} through {themes}. As mahadasha lord it activates the houses it "
        "rules: {ruled} - expect {effect}."
    ),
    "ls.promise.noruled": (
        "{title} sits natally in the {house_ord} house in {sign} ({dignity}), channeling "
        "{karakas} through {themes}. As mahadasha lord it activates the houses it "
        "rules - expect {effect}."
    ),
    "ls.ruled_item": "{ord} ({themes})",
    "ls.ev.natal": "Natal {planet} in house {h} ({sign}, {dignity}).",
    "ls.ev.rules": "{planet} rules house(s) {houses} from lagna.",
    "ls.ev.band": "Shadbala band for {planet}: {band}.",
    "ls.ev.maha": "{planet} mahadasha {start} to {end}.",
    "ls.md.one": "Under {a}'s years, ",
    "ls.md.many": "Across {head} and {last} years, ",
    "ls.age.plus": "ages {frm}+",
    "ls.age.range": "ages {frm}-{to}",
    "ls.summary": (
        "{md_clause}{title} ({age_label}) highlights {focus}. The chart steers this "
        "chapter through the houses and lords named below - timing windows, not fixed "
        "biographical events."
    ),
    "ls.title.open": "{title} ({frm}+)",
    "ls.title.range": "{title} ({frm}–{to})",
    "ls.title.hybrid": "{title} · {names}",
    "ls.dasha.title": "{display} years, age {a}–{b}",
    "ls.dasha.promise": "{display} mahadasha promise",
    "ls.dasha.antar.title": "{display} antardasha colour",
    "ls.dasha.antar.text": (
        "Within this mahadasha, a longer {title} antardasha ({start} to {end}) filters "
        "daily life through its natal promise. {promise}"
    ),
    "ls.dasha.antar.ev": "{planet} antardasha {start} to {end}.",
    "ls.dasha.ruled.title": "Houses activated by rulership",
    "ls.dasha.ruled.item": "{name}: {themes}",
    "ls.dasha.ruled.text": (
        "{display} rules {themes} from the lagna. During these years those life areas "
        "stay on the front desk of the chart."
    ),
    "ls.dasha.ruled.ev": "{planet} rules house(s) {houses}.",
    "ls.dasha.summary": (
        "The {display} mahadasha runs from {start} to {end} (about age {a}–{b}). It "
        "foregrounds {karakas}, expressed through the natal placement and houses below."
    ),
    "ls.through.title": "Temperament through-line",
    "ls.through.text": (
        "Across every chapter, the {sign} lagna ({sign_trait}) and Moon in {nak} "
        "({nak_trait}) set the temperament through-line."
    ),
    "ls.through.yoga": " Among active yogas, {yoga} remains a standing signature.",
    "ls.through.ev.asc": "Ascendant {sign}, {nak} pada {pada}.",
    "ls.through.ev.moon": "Moon nakshatra {nak} pada {pada}.",
    "ls.through.ev.yoga": "Active yoga: {yoga}.",

    # ---- prediction rules (texts keep {level}/{lord} for the evaluator)
    "rule.lord-strong-dasha": (
        "The {level} lord {lord} rules the {label} houses and carries above-required "
        "Shadbala, activating gains in {label}."
    ),
    "rule.lord-weak-dasha": (
        "The {level} lord {lord} rules the {label} houses but is weak in Shadbala; "
        "{label} matters need deliberate effort in this window."
    ),
    "rule.lord-in-domain-house": (
        "The {level} lord {lord} sits well-placed in a {label} house, giving direct "
        "results in {label}."
    ),
    "rule.lord-dusthana-weak": (
        "The {level} lord {lord} governs {label} but operates from a dusthana without "
        "compensating strength, bringing obstacles first."
    ),
    "rule.career-exalted-lord-kendra": (
        "An exalted {level} lord {lord} in a kendra or trikona marks a period of "
        "visible rise and recognition."
    ),
    "rule.wealth-gajakesari-jupiter": (
        "Gajakesari yoga activates during Jupiter's {level}: reputation-led gains and "
        "protection of wealth."
    ),
    "rule.marriage-venus-dasha-strong": (
        "A strong Venus {level} favors partnership, engagement, and harmony in "
        "existing bonds."
    ),
    "rule.health-sade-sati-window": (
        "Sade sati runs through this window; guard energy, sleep, and routines - "
        "steady discipline converts pressure into endurance."
    ),
    "rule.health-combust-lord": (
        "The {level} lord {lord} is combust in the natal chart, thinning its "
        "protective results; avoid overextension."
    ),
    "rule.spiritual-ketu-dasha": (
        "Ketu's {level} turns attention inward: contemplative practice and detachment "
        "deepen naturally."
    ),
    "rule.travel-rahu-dasha": (
        "Rahu's {level} favors unconventional moves - foreign lands, new "
        "environments, and boundary-crossing opportunities."
    ),

    # ---- prediction rule sources
    "src.dasha-phala-full": (
        "BPHS dasha-phala adhyaya (period results follow lordship and strength)"
    ),
    "src.dasha-phala": "BPHS dasha-phala adhyaya",
    "src.phaladeepika-placement": "Phaladeepika (placement of period lords)",
    "src.bphs-dusthana": "BPHS (dusthana placements of period lords)",
    "src.phaladeepika": "Phaladeepika",
    "src.bphs-yoga-phala": (
        "BPHS yoga-phala (yogas fructify in their karakas' periods)"
    ),
    "src.venus-karaka": "Venus as karaka of marriage (BPHS karakadhyaya)",
    "src.sade-sati": "Saturn transit tradition (sade sati)",
    "src.combustion": "Combustion doctrine (asta graha)",
    "src.ketu-moksha": "Ketu as moksha-karaka",
    "src.rahu-videsha": "Rahu as videsha-karaka",

    # ---- prediction evidence and framing
    "cond.owns": "{lord} rules house {hits}",
    "cond.occupies": "{lord} occupies house {house}",
    "cond.dignity": "{lord} is {dignity}",
    "cond.ratio_ge": "{lord} Shadbala ratio {ratio} ≥ {th}",
    "cond.ratio_lt": "{lord} Shadbala ratio {ratio} < {th}",
    "cond.lord_is": "{level} lord is {lord}",
    "cond.combust": "{lord} is combust in the natal chart",
    "cond.yoga": "natal yoga present: {keys}",
    "cond.sade_sati": "sade sati is active at the window midpoint",
    "pred.headline": "{domain} - {md} mahadasha / {ad} antardasha ({label})",
    "pred.window": "{start} to {end}",
    "pred.tension": (
        "This window carries both supportive and challenging indications - read them "
        "together rather than choosing one: "
    ),
    "pred.driver": "{lord} Shadbala ratio {ratio}",
    "pred.and": " and ",

    # ---- remedies
    "rem.mantra.title": "{deity} mantra for {planet}",
    "rem.mantra.practice": "{mantra} - {count}.",
    "rem.mantra.rationale": (
        "Mantra japa is the safest first remedy: it pacifies {planet} without "
        "amplifying it."
    ),
    "rem.daan.title": "Charity (daan) for {planet}",
    "rem.daan.practice": "Donate {daan}.",
    "rem.daan.rationale": (
        "Daan discharges the karmic debt of an afflicted {planet} rather than "
        "strengthening it."
    ),
    "rem.fast.title": "{day} observance",
    "rem.fast.practice": "Light fasting or a simplified sattvic diet on {day}s.",
    "rem.fast.rationale": "The weekday of {planet} concentrates its remediation.",
    "rem.fast.caution": (
        "Skip fasting entirely if pregnant, diabetic, or medically advised against it."
    ),
    "rem.gem.title": "{gem} (only after trial)",
    "rem.gem.practice": (
        "{gem} may support {planet} as a functional benefic that lacks strength."
    ),
    "rem.gem.rationale": (
        "{planet} rules a trikona for this lagna and is weak but unafflicted, the one "
        "case where a strengthening stone is classically sanctioned."
    ),
    "rem.gem.caution1": (
        "Gemstones amplify a planet indiscriminately; wear only after a trial period "
        "and only if the planet is a functional benefic for this lagna."
    ),
    "rem.gem.caution2": "Do not combine with gemstones of inimical planets already being worn.",
    "rem.gem.caution3": (
        "Advisory only - consult a qualified astrologer before purchase; quality and "
        "setting matter more than size."
    ),
    "rem.ev.place": "{planet} in {sign} (house {house}), dignity {dignity}",
    "rem.ev.ratio": "Shadbala ratio {ratio} (required 1.00)",
    "rem.ev.combust": "{planet} is combust",
}
