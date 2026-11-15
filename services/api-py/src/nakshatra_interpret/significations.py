"""Classical signification tables used by the reading composer.

Kept as plain data so practitioners can review and extend the vocabulary
without touching composer logic.
"""

PLANET_SIGNIFICATIONS: dict[str, dict] = {
    "sun": {
        "title": "Sun (Surya)",
        "karakas": "soul, vitality, father, authority, government, self-expression",
        "strong": "commanding presence, natural leadership, and recognition from institutions",
        "weak": "struggles with confidence, friction with authority figures, and a need to consciously build self-worth",
    },
    "moon": {
        "title": "Moon (Chandra)",
        "karakas": "mind, emotions, mother, public life, nourishment, adaptability",
        "strong": "emotional steadiness, popularity, and an intuitive read of people",
        "weak": "mood fluctuation and sensitivity that benefits from routine and rest",
    },
    "mercury": {
        "title": "Mercury (Budha)",
        "karakas": "intellect, speech, commerce, analysis, writing, humour",
        "strong": "sharp analytical intelligence, persuasive communication, and commercial instinct",
        "weak": "scattered attention and nervous energy; disciplined study habits help",
    },
    "venus": {
        "title": "Venus (Shukra)",
        "karakas": "love, marriage, arts, luxury, vehicles, diplomacy",
        "strong": "refined taste, harmonious relationships, and ease in attracting comforts",
        "weak": "over-indulgence or delayed gratification in love and luxury",
    },
    "mars": {
        "title": "Mars (Mangala)",
        "karakas": "courage, energy, siblings, land, engineering, competition",
        "strong": "decisive courage, athletic drive, and the ability to fight for what matters",
        "weak": "impatience or scattered aggression; channelled discipline turns it into achievement",
    },
    "jupiter": {
        "title": "Jupiter (Guru)",
        "karakas": "wisdom, fortune, children, teachers, dharma, wealth",
        "strong": "protective grace, sound judgement, and growth wherever it looks",
        "weak": "over-optimism or delayed fortune; mentors and ethics restore its promise",
    },
    "saturn": {
        "title": "Saturn (Shani)",
        "karakas": "discipline, longevity, labour, delays, service, karma",
        "strong": "endurance, structural thinking, and success that compounds with age",
        "weak": "delays and heaviness early in life that mature into hard-won mastery",
    },
    "rahu": {
        "title": "Rahu (North Node)",
        "karakas": "ambition, obsession, foreign lands, technology, unconventional paths",
        "strong": "hunger for growth in new territory and skill with modern tools",
        "weak": "restlessness and shortcuts; grounding practices keep its ambition constructive",
    },
    "ketu": {
        "title": "Ketu (South Node)",
        "karakas": "moksha, detachment, past-life mastery, research, sudden insight",
        "strong": "innate talent that feels inherited and a natural pull toward the spiritual",
        "weak": "disinterest in worldly detail; purpose arrives through inner work",
    },
}

HOUSE_THEMES: dict[int, dict] = {
    1: {"name": "1st house (Lagna)", "themes": "self, body, temperament, life direction"},
    2: {"name": "2nd house", "themes": "wealth, family, speech, food, stored value"},
    3: {"name": "3rd house", "themes": "courage, siblings, communication, short journeys, skills"},
    4: {"name": "4th house", "themes": "mother, home, vehicles, inner peace, property"},
    5: {"name": "5th house", "themes": "children, intelligence, creativity, romance, purva punya"},
    6: {"name": "6th house", "themes": "health, service, competition, debts, daily work"},
    7: {"name": "7th house", "themes": "marriage, partnerships, business alliances, public dealings"},
    8: {"name": "8th house", "themes": "longevity, transformation, inheritance, research, the occult"},
    9: {"name": "9th house", "themes": "fortune, dharma, father, higher learning, long journeys"},
    10: {"name": "10th house", "themes": "career, status, authority, public achievement"},
    11: {"name": "11th house", "themes": "gains, income, networks, aspirations, elder siblings"},
    12: {"name": "12th house", "themes": "expenses, foreign residence, sleep, liberation, retreat"},
}

SIGN_TRAITS: dict[str, str] = {
    "Aries": "direct, pioneering, and quick to act",
    "Taurus": "steady, sensual, and value-oriented",
    "Gemini": "curious, verbal, and versatile",
    "Cancer": "protective, intuitive, and memory-rich",
    "Leo": "dignified, expressive, and authority-seeking",
    "Virgo": "precise, analytical, and service-minded",
    "Libra": "balancing, relational, and aesthetic",
    "Scorpio": "intense, private, and transformational",
    "Sagittarius": "philosophical, expansive, and candid",
    "Capricorn": "pragmatic, ambitious, and structured",
    "Aquarius": "systemic, humanitarian, and unconventional",
    "Pisces": "imaginative, compassionate, and boundary-dissolving",
}

NAKSHATRA_TRAITS: dict[str, str] = {
    "Ashwini": "swift healing energy and pioneering initiative",
    "Bharani": "creative intensity and the bearing of responsibility",
    "Krittika": "purifying sharpness and protective fire",
    "Rohini": "magnetic growth, beauty, and material fertility",
    "Mrigashira": "seeking, gentle curiosity, and restless exploration",
    "Ardra": "storm-born insight and transformative feeling",
    "Punarvasu": "renewal, return of light, and generous wisdom",
    "Pushya": "nourishing care and disciplined devotion",
    "Ashlesha": "penetrating perception and serpentine intelligence",
    "Magha": "ancestral authority and regal bearing",
    "Purva Phalguni": "pleasure, artistry, and social warmth",
    "Uttara Phalguni": "reliable patronage and contractual loyalty",
    "Hasta": "dexterous skill and resourceful humour",
    "Chitra": "architectural brilliance and love of design",
    "Swati": "independent flexibility and diplomatic movement",
    "Vishakha": "goal-locked determination and festival energy",
    "Anuradha": "devoted friendship, discipline, and success away from home",
    "Jyeshtha": "senior authority and protective vigilance",
    "Mula": "root-cutting inquiry and radical truth-seeking",
    "Purva Ashadha": "invigorating declarations and early victories",
    "Uttara Ashadha": "enduring victory and universal principles",
    "Shravana": "listening, learning, and preserving tradition",
    "Dhanishta": "rhythmic wealth and group leadership",
    "Shatabhisha": "healing seclusion and vast systemic vision",
    "Purva Bhadrapada": "fierce idealism and transformative austerity",
    "Uttara Bhadrapada": "deep-sea calm and long-term stability",
    "Revati": "nurturing completion and safe passage for others",
}

DIGNITY_PHRASES: dict[str, str] = {
    "exalted": "exalted - operating at its highest expression",
    "moolatrikona": "in moolatrikona - near its best expression",
    "own": "in its own sign - stable and self-supporting",
    "friend": "in a friendly sign - comfortable and cooperative",
    "neutral": "in a neutral sign - giving mixed but workable results",
    "enemy": "in an enemy sign - its gifts arrive with friction",
    "debilitated": "debilitated - its significations need conscious support",
}
