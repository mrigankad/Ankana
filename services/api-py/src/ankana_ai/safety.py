"""Deterministic pre-model gate for the refusal policy.

Runs before any model call (so it costs nothing and cannot be talked around):
death/lifespan, serious-disease diagnosis, litigation outcomes, gemstone or
remedy-selling pressure, birth-time rectification claims and financial tips.
English, Hindi (Devanagari) and Hinglish (roman) triggers.
"""

import re
from dataclasses import dataclass

_I = re.IGNORECASE


def _rx(*patterns: str) -> re.Pattern:
    return re.compile("|".join(patterns), _I)


CATEGORIES: dict[str, re.Pattern] = {
    "death": _rx(
        r"\bwhen (?:will|would|am i going to|do) (?:i|he|she|my \w+) (?:die|pass away|expire)\b",
        r"\b(?:date|age|year|time) of (?:my |his |her |their )?(?:death|dying)\b",
        r"\b(?:will|when) (?:i|he|she|my \w+) (?:die|be dead)\b",
        r"\blife ?span\b|\bhow long (?:will i|do i) live\b",
        r"\bmaut\b|\bmrityu\b|\bmarunga\b|\bmarungi\b|\bkab mar\w*\b",
        r"\bam i going to die\b",
        r"मृत्यु|मौत|कब मर|कितनी उम्र तक जी",
    ),
    "serious_disease": _rx(
        # "Cancer" is also a zodiac sign: only treat disease words as medical in a health context.
        r"\b(?:get|getting|have|having|develop|developing|suffer\w*|risk of|chances? of|diagnos\w*)\W+"
        r"(?:\w+\W+){0,3}(?:cancer|tumou?r|heart attack|stroke|diabetes|hiv|aids)\b",
        r"\b(?:cancer|tumou?r|heart attack|stroke)\W+(?:\w+\W+){0,3}"
        r"(?:disease|treatment|diagnos\w*|hoga|ho jayega)\b",
        r"\b(?:diagnose|diagnosis|prognosis)\b",
        r"\bserious (?:disease|illness)\b|\bterminal illness\b|\bbimari\b.*\b(?:gambhir|serious)\b",
        r"कैंसर|ट्यूमर|दिल का दौरा|हार्ट अटैक|गंभीर बीमारी|लाइलाज",
    ),
    "litigation": _rx(
        r"\b(?:win|lose|won|lost) (?:my |the |this |our )?(?:court )?(?:case|lawsuit|litigation|trial|appeal)\b",
        r"\b(?:court|legal) (?:case|verdict|outcome|battle)\b",
        r"\bwill i (?:be )?(?:acquitted|convicted|jailed|sentenced)\b|\bverdict\b",
        r"\bmuqadma\b|\bmukadma\b|\bmukadama\b|\bcourt (?:me|mein|case)\b|\bcase (?:jeet|haar)\w*\b",
        r"मुकदमा|मुक़दमा|कोर्ट केस|केस जीत|अदालत",
    ),
    "gemstone_pressure": _rx(
        r"\b(?:gem ?stones?|ratna|rudraksha|yantra)\b.*\b"
        r"(?:sell|selling|push|pressure|convince|persuade|force|scare|frighten|upsell|commission|"
        r"last chance|must buy|buy now|urgent|lakh)\b",
        r"\b(?:sell|selling|push|pressure|convince|persuade|force|scare|frighten|upsell)\b.*\b"
        r"(?:gem ?stones?|ratna|rudraksha|yantra|puja|pooja|remed\w+|upay)\b",
        r"\bratna\b.*\b(?:bech|bechna|bechne|dabav|daraa|dara)\w*\b"
        r"|\b(?:bech|bechna|bechne)\w*\b.*\b(?:ratna|nag|moti|pukhraj|neelam)\b",
        r"रत्न.*(?:बेच|दबाव|डरा)|(?:बेच|दबाव|डरा).*रत्न",
    ),
    "rectification": _rx(
        r"\brectif\w+\b",
        r"\b(?:correct|fix|find|guess) (?:my |the |his |her )?(?:exact )?birth ?time\b",
        r"जन्म ?समय (?:सुधार|ठीक)|समय शोधन",
    ),
    "financial": _rx(
        r"\b(?:which|what) (?:stocks?|shares?|crypto|coins?|funds?|mutual funds?)\b",
        r"\b(?:buy|sell|invest in|short) (?:this |these |the )?(?:stocks?|shares?|crypto|bitcoin|nifty|sensex)\b",
        r"\blottery\b|\bsatta\b|\bintraday\b|\bwill (?:nifty|sensex|bitcoin|gold) (?:go|rise|fall)\b",
        r"\bshare market (?:me|mein) (?:kya|kaunsa)\b|शेयर बाजार|कौन सा शेयर|लॉटरी|सट्टा",
    ),
}

REFUSAL_TEXT = {
    "en": {
        "death": "I do not predict death, lifespan or dates of death. Jyotish can describe themes and timing of life chapters, but not this, and a chart should never be used to frighten anyone. I can look at health and vitality as wellness themes if that helps.",
        "serious_disease": "I cannot diagnose or predict serious illness from a chart. For any health worry please consult a qualified doctor. I can describe the chart's wellness themes in general terms if you would like that.",
        "litigation": "I cannot predict the outcome of a court case or any legal matter. Please rely on a qualified lawyer. I can describe general timing themes in the chart for stress and resolution, without any verdict.",
        "gemstone_pressure": "I will not help pressure anyone into buying gemstones, rituals or expensive remedies, or frighten a client into spending. I can describe low-cost, optional, traditional remedies with their cautions, presented without any urgency or guarantees.",
        "rectification": "I cannot claim to rectify or correct a birth time. The chart is computed from the birth data as entered; if the time is uncertain, treat time-sensitive factors such as the lagna and divisional charts with caution.",
        "financial": "I cannot give stock, trading or lottery picks or any financial instruction. I can describe general themes of income and timing in the chart as guidance only.",
    },
    "hi": {
        "death": "मैं मृत्यु, आयु-सीमा या मृत्यु की तिथि की भविष्यवाणी नहीं करता। ज्योतिष जीवन के विषय और समय बता सकता है, पर यह नहीं, और कुंडली से किसी को डराना नहीं चाहिए। चाहें तो मैं स्वास्थ्य को कल्याण के विषय के रूप में देख सकता हूँ।",
        "serious_disease": "मैं कुंडली से गंभीर बीमारी का निदान या भविष्यवाणी नहीं कर सकता। स्वास्थ्य की चिंता हो तो कृपया योग्य डॉक्टर से मिलें। चाहें तो मैं सामान्य कल्याण के विषय बता सकता हूँ।",
        "litigation": "मैं अदालती मामले या किसी कानूनी विवाद के नतीजे की भविष्यवाणी नहीं कर सकता। कृपया योग्य वकील पर भरोसा करें।",
        "gemstone_pressure": "मैं किसी पर रत्न, पूजा या महंगे उपाय खरीदने का दबाव डालने या डराने में मदद नहीं करूँगा। मैं वैकल्पिक, कम खर्च वाले पारंपरिक उपाय सावधानियों के साथ बता सकता हूँ, बिना किसी जल्दबाज़ी या गारंटी के।",
        "rectification": "मैं जन्म समय का शोधन या सुधार करने का दावा नहीं कर सकता। कुंडली दर्ज किए गए जन्म विवरण से बनती है; समय अनिश्चित हो तो लग्न और वर्ग कुंडलियों पर सावधानी रखें।",
        "financial": "मैं शेयर, ट्रेडिंग या लॉटरी की सलाह या कोई वित्तीय निर्देश नहीं दे सकता। आय और समय के सामान्य विषय केवल मार्गदर्शन के रूप में बता सकता हूँ।",
    },
    "hinglish": {
        "death": "Main maut, umr ki seema ya maut ki tithi ki bhavishyavani nahi karta. Jyotish jeevan ke vishay aur samay bata sakta hai, par yeh nahi, aur kundli se kisi ko darana nahi chahiye. Chahein toh main sehat ko wellness ke vishay ke roop mein dekh sakta hoon.",
        "serious_disease": "Main kundli se gambhir bimari ka diagnosis ya bhavishyavani nahi kar sakta. Sehat ki chinta ho toh kripya yogya doctor se milein. Chahein toh main general wellness ke vishay bata sakta hoon.",
        "litigation": "Main court case ya kisi kanooni vivad ke nateeje ki bhavishyavani nahi kar sakta. Kripya yogya vakil par bharosa karein. Tanav aur samadhan ke samay ke general vishay bina kisi faisle ke bata sakta hoon.",
        "gemstone_pressure": "Main kisi par ratna, puja ya mehange upay kharidne ka dabav daalne ya darane mein madad nahi karunga. Main optional, kam kharch wale paramparik upay savdhaniyon ke saath bata sakta hoon, bina jaldbaazi ya guarantee ke.",
        "rectification": "Main janm samay ka rectification karne ka daava nahi kar sakta. Kundli darj kiye gaye janm vivaran se banti hai; samay anishchit ho toh lagna aur varga kundliyon par savdhani rakhein.",
        "financial": "Main stock, trading ya lottery ki salah ya koi financial nirdesh nahi de sakta. Aay aur samay ke general vishay sirf margdarshan ke roop mein bata sakta hoon.",
    },
}

FOOTER = {
    "en": "Advisory guidance only - not medical, legal, or financial advice.",
    "hi": "केवल सलाहात्मक मार्गदर्शन - यह चिकित्सा, कानूनी या वित्तीय सलाह नहीं है।",
    "hinglish": "Sirf salah ke roop mein margdarshan - yeh medical, legal ya financial salah nahi hai.",
}

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_HINGLISH = re.compile(
    r"\b(mera|meri|mere|kya|kab|kaun|kahan|kaise|hai|hoga|hogi|mein|me|ka|ki|ke|"
    r"batao|bataiye|dikhao|kundli|shaadi|naukri|paisa|nahi|bhi|aur|kyun)\b",
    _I,
)


def detect_language(text: str) -> str:
    """Return 'hi' for Devanagari, 'hinglish' for roman Hindi, else 'en'."""
    if _DEVANAGARI.search(text):
        return "hi"
    if len(_HINGLISH.findall(text)) >= 2:
        return "hinglish"
    return "en"


def footer_for(language: str) -> str:
    return FOOTER.get(language, FOOTER["en"])


@dataclass(frozen=True)
class GateResult:
    refused: bool
    category: str | None = None
    message: str | None = None
    language: str = "en"


def check(question: str) -> GateResult:
    """Return a refusal result when the question hits a hard-refuse category."""
    language = detect_language(question)
    for category, pattern in CATEGORIES.items():
        if pattern.search(question):
            key = language if language in ("hi", "hinglish") else "en"
            return GateResult(
                True, category, f"{REFUSAL_TEXT[key][category]} {FOOTER[key]}", language
            )
    return GateResult(False, language=language)
