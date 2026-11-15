"""Labels for report chrome. Interpretive prose now comes from the nakshatra_i18n
catalogs (en, hi), so Hindi reports are fully Hindi except the Lal Kitab pages,
which use the *_hi fields where present."""

LABELS = {
    "en": {
        "title": "Birth Chart Report", "prepared_for": "Prepared for", "born": "Born",
        "place": "Place", "ayanamsa": "Ayanamsa", "generated": "Generated",
        "summary": "Chart summary", "kundali": "Kundali (South Indian)",
        "planets": "Planetary positions", "houses": "Houses", "yogas": "Yogas and doshas",
        "dasha": "Vimshottari dasha", "vargas": "Divisional highlights",
        "panchang": "Birth panchang", "reading": "Reading", "lal_kitab": "Lal Kitab",
        "remedies": "Remedies", "lagna": "Lagna", "moon_sign": "Moon sign",
        "birth_star": "Birth nakshatra", "planet": "Planet", "sign": "Sign",
        "degree": "Degree", "nakshatra": "Nakshatra", "pada": "Pada", "house": "House",
        "dignity": "Dignity", "lord": "Lord", "occupants": "Occupants",
        "mahadasha": "Mahadasha", "start": "Start", "end": "End", "years": "Years",
        "evidence": "Evidence", "present": "Present", "one_at_a_time": "One remedy at a time",
        "sleeping_planets": "Sleeping planets", "rin": "Rin (debts)", "masnui": "Masnui planets",
        "upay": "Upay (remedies)", "page": "Page", "none": "None",
        "disclaimer": "This report is a traditional astrological reading for guidance and "
                      "reflection. It is not medical, legal or financial advice.",
    },
    "hi": {
        "title": "जन्म कुंडली रिपोर्ट", "prepared_for": "इनके लिए तैयार", "born": "जन्म",
        "place": "स्थान", "ayanamsa": "अयनांश", "generated": "तैयार किया गया",
        "summary": "कुंडली सारांश", "kundali": "कुंडली (दक्षिण भारतीय)",
        "planets": "ग्रह स्थिति", "houses": "भाव", "yogas": "योग और दोष",
        "dasha": "विंशोत्तरी दशा", "vargas": "वर्ग विशेष",
        "panchang": "जन्म पंचांग", "reading": "फलादेश", "lal_kitab": "लाल किताब",
        "remedies": "उपाय", "lagna": "लग्न", "moon_sign": "चंद्र राशि",
        "birth_star": "जन्म नक्षत्र", "planet": "ग्रह", "sign": "राशि",
        "degree": "अंश", "nakshatra": "नक्षत्र", "pada": "चरण", "house": "भाव",
        "dignity": "बल स्थिति", "lord": "स्वामी", "occupants": "स्थित ग्रह",
        "mahadasha": "महादशा", "start": "आरंभ", "end": "समाप्ति", "years": "वर्ष",
        "evidence": "आधार", "present": "उपस्थित", "one_at_a_time": "एक समय में एक उपाय",
        "sleeping_planets": "सोए हुए ग्रह", "rin": "ऋण", "masnui": "मसनुई ग्रह",
        "upay": "उपाय", "page": "पृष्ठ", "none": "कोई नहीं",
        "disclaimer": "यह रिपोर्ट मार्गदर्शन और चिंतन के लिए पारंपरिक ज्योतिषीय विश्लेषण है। "
                      "यह चिकित्सीय, कानूनी या वित्तीय सलाह नहीं है।",
    },
}

PLANETS = {
    "en": {"sun": "Sun", "moon": "Moon", "mars": "Mars", "mercury": "Mercury",
           "jupiter": "Jupiter", "venus": "Venus", "saturn": "Saturn", "rahu": "Rahu",
           "ketu": "Ketu"},
    "hi": {"sun": "सूर्य", "moon": "चंद्र", "mars": "मंगल", "mercury": "बुध",
           "jupiter": "गुरु", "venus": "शुक्र", "saturn": "शनि", "rahu": "राहु",
           "ketu": "केतु"},
}
PLANET_ABBR = {
    "en": {"sun": "Su", "moon": "Mo", "mars": "Ma", "mercury": "Me", "jupiter": "Ju",
           "venus": "Ve", "saturn": "Sa", "rahu": "Ra", "ketu": "Ke", "asc": "As"},
    "hi": {"sun": "सू", "moon": "चं", "mars": "मं", "mercury": "बु", "jupiter": "गु",
           "venus": "शु", "saturn": "श", "rahu": "रा", "ketu": "के", "asc": "ल"},
}
SIGNS = {
    "en": ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
           "Sagittarius", "Capricorn", "Aquarius", "Pisces"],
    "hi": ["मेष", "वृषभ", "मिथुन", "कर्क", "सिंह", "कन्या", "तुला", "वृश्चिक",
           "धनु", "मकर", "कुंभ", "मीन"],
}

LANGUAGES = ("en", "hi")
