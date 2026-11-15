"""Name tables for the interpretation layer (English keys -> Hindi, Devanagari).

English is the identity for every lookup, so English output stays exactly as
the engine produces it. Hindi uses standard Jyotish terms.
"""

PLANETS_HI = {
    "sun": "सूर्य", "moon": "चंद्र", "mars": "मंगल", "mercury": "बुध",
    "jupiter": "गुरु", "venus": "शुक्र", "saturn": "शनि", "rahu": "राहु",
    "ketu": "केतु",
}
PLANET_DISPLAY_EN = {
    "sun": "Sun", "moon": "Moon", "mars": "Mars", "mercury": "Mercury",
    "jupiter": "Jupiter", "venus": "Venus", "saturn": "Saturn", "rahu": "Rahu",
    "ketu": "Ketu",
}

SIGNS_HI = {
    "Aries": "मेष", "Taurus": "वृषभ", "Gemini": "मिथुन", "Cancer": "कर्क",
    "Leo": "सिंह", "Virgo": "कन्या", "Libra": "तुला", "Scorpio": "वृश्चिक",
    "Sagittarius": "धनु", "Capricorn": "मकर", "Aquarius": "कुंभ", "Pisces": "मीन",
}

NAKSHATRAS_HI = {
    "Ashwini": "अश्विनी", "Bharani": "भरणी", "Krittika": "कृत्तिका",
    "Rohini": "रोहिणी", "Mrigashira": "मृगशिरा", "Ardra": "आर्द्रा",
    "Punarvasu": "पुनर्वसु", "Pushya": "पुष्य", "Ashlesha": "आश्लेषा",
    "Magha": "मघा", "Purva Phalguni": "पूर्व फाल्गुनी",
    "Uttara Phalguni": "उत्तर फाल्गुनी", "Hasta": "हस्त", "Chitra": "चित्रा",
    "Swati": "स्वाति", "Vishakha": "विशाखा", "Anuradha": "अनुराधा",
    "Jyeshtha": "ज्येष्ठा", "Mula": "मूल", "Purva Ashadha": "पूर्वाषाढ़ा",
    "Uttara Ashadha": "उत्तराषाढ़ा", "Shravana": "श्रवण", "Dhanishta": "धनिष्ठा",
    "Shatabhisha": "शतभिषा", "Purva Bhadrapada": "पूर्व भाद्रपद",
    "Uttara Bhadrapada": "उत्तर भाद्रपद", "Revati": "रेवती",
}

TITHIS_HI = {
    "Pratipada": "प्रतिपदा", "Dwitiya": "द्वितीया", "Tritiya": "तृतीया",
    "Chaturthi": "चतुर्थी", "Panchami": "पंचमी", "Shashthi": "षष्ठी",
    "Saptami": "सप्तमी", "Ashtami": "अष्टमी", "Navami": "नवमी",
    "Dashami": "दशमी", "Ekadashi": "एकादशी", "Dwadashi": "द्वादशी",
    "Trayodashi": "त्रयोदशी", "Chaturdashi": "चतुर्दशी", "Purnima": "पूर्णिमा",
    "Amavasya": "अमावस्या",
}
PAKSHA_HI = {"shukla": "शुक्ल", "krishna": "कृष्ण"}

PANCHANG_YOGAS_HI = {
    "Vishkumbha": "विष्कुंभ", "Priti": "प्रीति", "Ayushman": "आयुष्मान",
    "Saubhagya": "सौभाग्य", "Shobhana": "शोभन", "Atiganda": "अतिगंड",
    "Sukarma": "सुकर्मा", "Dhriti": "धृति", "Shula": "शूल", "Ganda": "गंड",
    "Vriddhi": "वृद्धि", "Dhruva": "ध्रुव", "Vyaghata": "व्याघात",
    "Harshana": "हर्षण", "Vajra": "वज्र", "Siddhi": "सिद्धि",
    "Vyatipata": "व्यतीपात", "Variyana": "वरीयान", "Parigha": "परिघ",
    "Shiva": "शिव", "Siddha": "सिद्ध", "Sadhya": "साध्य", "Shubha": "शुभ",
    "Shukla": "शुक्ल", "Brahma": "ब्रह्म", "Indra": "इंद्र",
    "Vaidhriti": "वैधृति",
}
KARANAS_HI = {
    "Bava": "बव", "Balava": "बालव", "Kaulava": "कौलव", "Taitila": "तैतिल",
    "Garaja": "गर", "Vanija": "वणिज", "Vishti": "विष्टि", "Shakuni": "शकुनि",
    "Chatushpada": "चतुष्पद", "Naga": "नाग", "Kimstughna": "किंस्तुघ्न",
}
VARAS_HI = {
    "Ravivara": "रविवार", "Somavara": "सोमवार", "Mangalavara": "मंगलवार",
    "Budhavara": "बुधवार", "Guruvara": "गुरुवार", "Shukravara": "शुक्रवार",
    "Shanivara": "शनिवार",
}

DIGNITIES_HI = {
    "exalted": "उच्च", "moolatrikona": "मूलत्रिकोण", "own": "स्वराशि",
    "friend": "मित्र राशि", "neutral": "सम राशि", "enemy": "शत्रु राशि",
    "debilitated": "नीच",
}
BANDS_HI = {
    "strong": "प्रबल", "weak": "दुर्बल", "moderate": "मध्यम",
    "well-supported": "भली-भाँति समर्थित",
    "under-supported": "अपर्याप्त रूप से समर्थित",
    "adequately supported": "पर्याप्त रूप से समर्थित",
}
ORDINALS_EN = {
    1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th",
    7: "7th", 8: "8th", 9: "9th", 10: "10th", 11: "11th", 12: "12th",
}
ORDINALS_HI = {
    1: "प्रथम", 2: "द्वितीय", 3: "तृतीय", 4: "चतुर्थ", 5: "पंचम", 6: "षष्ठ",
    7: "सप्तम", 8: "अष्टम", 9: "नवम", 10: "दशम", 11: "एकादश", 12: "द्वादश",
}
LEVELS_HI = {"mahadasha": "महादशा", "antardasha": "अंतर्दशा"}
DOMAINS_HI = {
    "career": "करियर", "wealth": "धन", "marriage": "विवाह", "health": "स्वास्थ्य",
    "education": "शिक्षा", "travel": "यात्रा", "spiritual": "अध्यात्म",
}
DOMAIN_LABELS_HI = {
    "career": "करियर और व्यवसाय",
    "wealth": "धन और आय",
    "marriage": "विवाह और साझेदारी",
    "health": "स्वास्थ्य और जीवन शक्ति",
    "education": "शिक्षा और अध्ययन",
    "travel": "यात्रा और स्थानांतरण",
    "spiritual": "आध्यात्मिक उन्नति",
}
YOGA_PLANET_KEYS = {
    "ruchaka": "mars", "bhadra": "mercury", "hamsa": "jupiter",
    "malavya": "venus", "sasa": "saturn",
}
