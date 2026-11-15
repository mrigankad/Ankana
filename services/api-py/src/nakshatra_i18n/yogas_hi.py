"""Hindi names, descriptions and evidence translation for the 28 yoga/dosha detectors.

The detectors in nakshatra_core emit English evidence sentences. For Hindi we
match those sentence shapes and re-render them with Hindi names; a sentence
that matches no pattern is returned unchanged (a test asserts none are missed
for the reference charts).
"""

import re

from . import names

YOGA_NAMES_HI = {
    "gajakesari": "गजकेसरी योग",
    "budhaditya": "बुधादित्य योग",
    "raj-yoga": "राज योग (केंद्र-त्रिकोण)",
    "vipreet-raj": "विपरीत राज योग",
    "neecha-bhanga": "नीचभंग राज योग",
    "adhi": "अधि योग",
    "amala": "अमल योग",
    "saraswati": "सरस्वती योग",
    "lakshmi": "लक्ष्मी योग",
    "chandra-mangal": "चंद्र-मंगल योग",
    "dhana-yoga": "धन योग",
    "ruchaka": "रुचक योग (मंगल महापुरुष)",
    "bhadra": "भद्र योग (बुध महापुरुष)",
    "hamsa": "हंस योग (गुरु महापुरुष)",
    "malavya": "मालव्य योग (शुक्र महापुरुष)",
    "sasa": "शश योग (शनि महापुरुष)",
    "sunapha": "सुनफा योग",
    "anapha": "अनफा योग",
    "durudhara": "दुरुधरा योग",
    "voshi": "वोशी योग",
    "veshi": "वेशी योग",
    "ubhayachari": "उभयचारी योग",
    "manglik": "मांगलिक दोष (कुज दोष)",
    "guru-chandal": "गुरु चांडाल योग",
    "pitra-dosha": "पितृ दोष",
    "grahan": "ग्रहण योग",
    "kemadruma": "केमद्रुम योग",
    "kaal-sarp": "काल सर्प योग",
}

_MAHA_DESC = "{planet} अपनी स्वराशि या उच्च राशि में लग्न से केंद्र भाव में स्थित हो।"

YOGA_DESC_HI = {
    "gajakesari": "चंद्र से गुरु केंद्र (1, 4, 7 या 10वें) भाव में हो; यह ज्ञान, प्रतिष्ठा और स्थायी समृद्धि से जुड़ा माना जाता है।",
    "budhaditya": "सूर्य और बुध एक ही राशि में युति करें; यह बुद्धि, संवाद-कौशल और प्रशासनिक क्षमता से जुड़ा माना जाता है।",
    "chandra-mangal": "चंद्र और मंगल की युति या परस्पर सप्तम दृष्टि; यह अर्जन की प्रवृत्ति और भौतिक उद्यम से जुड़ा माना जाता है।",
    "kemadruma": "चंद्र के साथ या उससे दूसरे अथवा बारहवें भाव में कोई ग्रह (सूर्य, राहु, केतु को छोड़कर) न हो; शास्त्रों में इसे एकाकीपन और उतार-चढ़ाव भरे भाग्य से जोड़ा गया है।",
    "kaal-sarp": "सातों शास्त्रीय ग्रह राहु-केतु अक्ष के एक ओर सिमटे हों; परंपरा में इसे केंद्रित कर्मिक तीव्रता के रूप में पढ़ा जाता है।",
    "sunapha": "चंद्र से दूसरे भाव में कोई ग्रह हो; यह स्वयं अर्जित धन, अच्छी बुद्धि और अपने प्रयासों से समृद्धि का सूचक है।",
    "anapha": "चंद्र से बारहवें भाव में कोई ग्रह हो; यह अच्छे स्वास्थ्य, सद्गुण और सुखमय जीवन का सूचक है।",
    "durudhara": "चंद्र के दोनों ओर (दूसरे और बारहवें भाव में) ग्रह हों; यह धन, उदारता और सुख-सुविधाओं भरे जीवन का सूचक है।",
    "voshi": "सूर्य से दूसरे भाव में कोई ग्रह हो; यह वाक्पटुता, विद्या और दानशील स्वभाव का सूचक है।",
    "veshi": "सूर्य से बारहवें भाव में कोई ग्रह हो; यह अधिकार, सामर्थ्य और स्थिर स्वभाव का सूचक है।",
    "ubhayachari": "सूर्य के दोनों ओर (दूसरे और बारहवें भाव में) ग्रह हों; यह शक्तिशाली, राजसी व्यक्तित्व और प्रभावशाली उपस्थिति का सूचक है।",
    "adhi": "चंद्र से छठे, सातवें और आठवें भाव में नैसर्गिक शुभ ग्रह हों; यह उच्च पद, अधिकार और शत्रुओं पर विजय का सूचक है।",
    "amala": "लग्न या चंद्र से दशम भाव में कोई नैसर्गिक शुभ ग्रह हो; यह बेदाग प्रतिष्ठा, परोपकार और स्थायी यश का सूचक है।",
    "manglik": "मंगल लग्न से 1, 2, 4, 7, 8 या 12वें भाव में हो; वैवाहिक अनुकूलता के लिए परंपरागत रूप से इसका विचार होता है। परिहार की स्थितियाँ इसके प्रभाव को कम कर सकती हैं।",
    "guru-chandal": "गुरु और राहु एक ही राशि में हों; यह अपारंपरिक ज्ञान, गुरुजनों के सुझावों में व्यवधान या अपरंपरागत आध्यात्मिक झुकाव का संकेत दे सकता है।",
    "pitra-dosha": "सूर्य के साथ राहु या केतु की युति; यह पूर्वजों के कर्म-ऋण का सूचक है, जो जीवन में बाधाओं या विलंबित फलों के रूप में प्रकट हो सकता है।",
    "raj-yoga": "किसी केंद्र के स्वामी और किसी त्रिकोण के स्वामी की युति, या एक ही ग्रह दोनों का स्वामी हो; यह सबसे शुभ संयोगों में से एक है, जो सत्ता, सफलता और मान्यता का सूचक है।",
    "dhana-yoga": "द्वितीय भाव के स्वामी की एकादश भाव के स्वामी से युति या परस्पर दृष्टि; यह धन-संचय और सुदृढ़ आर्थिक लाभ का सूचक है।",
    "vipreet-raj": "किसी दुःस्थान (6, 8 या 12वें) भाव का स्वामी किसी अन्य दुःस्थान में स्थित हो; यह विपत्ति को लाभ में बदल देता है, बाधाएँ अप्रत्याशित लाभ का स्रोत बनती हैं।",
    "neecha-bhanga": "नीच ग्रह की दुर्बलता विशेष स्थितियों (जैसे बलवान स्वामी) से भंग हो जाए; यह कठिन स्थिति को महान बल के स्रोत में बदल देता है।",
    "saraswati": "गुरु, शुक्र और बुध तीनों केंद्र, त्रिकोण या द्वितीय भाव में हों और गुरु सम्मानित स्थिति में हो; यह विद्या, वाक्पटुता तथा कला और विज्ञान में निपुणता देता है।",
    "lakshmi": "नवम भाव का स्वामी अपनी स्वराशि, उच्च या मूलत्रिकोण राशि में केंद्र में स्थित हो; यह अपार धन, भाग्य और दैवी कृपा का सूचक है।",
    "grahan": "किसी प्रकाशक ग्रह (सूर्य या चंद्र) की राहु या केतु से युति; यह उस ग्रह के कारकत्वों, अर्थात पहचान (सूर्य) या मन और भावनाओं (चंद्र), के आसपास कर्मिक तीव्रता का सूचक है।",
}

_P = r"(?P<p>sun|moon|mars|mercury|jupiter|venus|saturn|rahu|ketu)"
_S = r"(?P<s>Aries|Taurus|Gemini|Cancer|Leo|Virgo|Libra|Scorpio|Sagittarius|Capricorn|Aquarius|Pisces)"
_PL = r"(?P<pl>[a-z]+(?:\+[a-z]+)?(?:, [a-z]+)*)"
_D = r"(?P<d>exalted|moolatrikona|own|friend|neutral|enemy|debilitated)"
_LUM = r"(?P<lum>Moon|Sun)"

# (regex over the English sentence, Hindi template). Group names: p planet,
# s sign, pl planet list, d dignity, lum Moon/Sun, others are literals.
_PATTERNS: list[tuple[str, str]] = [
    (rf"^{_P} in {_S} \(house (?P<n>\d+)\)$", "{p} {s} राशि में (भाव {n})"),
    (r"^Jupiter is (?P<n>\d+) signs from the Moon \(kendra positions: 1, 4, 7, 10\)\.$",
     "गुरु चंद्र से {n} राशि दूर है (केंद्र स्थितियाँ: 1, 4, 7, 10)।"),
    (r"^Mars is (?P<n>\d+) signs from the Moon\.$", "मंगल चंद्र से {n} राशि दूर है।"),
    (rf"^{_P} dignity: {_D}\.$", "{p} की बल स्थिति: {d}।"),
    (rf"^{_P} occupies house (?P<n>\d+) from the lagna\.$", "{p} लग्न से भाव {n} में स्थित है।"),
    (r"^No supporting planet in the 2nd or 12th from the Moon or with the Moon\.$",
     "चंद्र के साथ या उससे दूसरे अथवा बारहवें भाव में कोई सहायक ग्रह नहीं है।"),
    (rf"^Supporting planets around the Moon: {_PL}\.$", "चंद्र के आसपास सहायक ग्रह: {pl}।"),
    (r"^Rahu at (?P<a>[\d.]+) deg, Ketu at (?P<b>[\d.]+) deg\.$", "राहु {a} अंश पर, केतु {b} अंश पर।"),
    (r"^All seven classical planets fall on one side of the nodal axis\.$",
     "सातों शास्त्रीय ग्रह राहु-केतु अक्ष के एक ओर हैं।"),
    (r"^Planets occupy both sides of the nodal axis\.$", "ग्रह राहु-केतु अक्ष के दोनों ओर स्थित हैं।"),
    (rf"^{_PL} in the (?P<h>2nd|12th) from {_LUM} \({_S}\)\.$",
     "{pl} {lum} से {h} भाव ({s}) में।"),
    (rf"^No qualifying planet in the (?P<h>2nd|12th) from {_LUM}\.$",
     "{lum} से {h} भाव में कोई योग्य ग्रह नहीं है।"),
    (rf"^In (?P<h>2nd|12th) from {_LUM}: {_PL}\.$", "{lum} से {h} भाव में: {pl}।"),
    (rf"^No planet in (?P<h>2nd|12th) from {_LUM}\.$", "{lum} से {h} भाव में कोई ग्रह नहीं।"),
    (rf"^{_P} in house (?P<n>\d+) from Moon\.$", "{p} चंद्र से भाव {n} में।"),
    (r"^(?P<n>\d+) benefic\(s\) in the 6th/7th/8th houses from Moon\.$",
     "चंद्र से छठे/सातवें/आठवें भाव में {n} शुभ ग्रह।"),
    (r"^Insufficient benefics in 6th/7th/8th from Moon\.$",
     "चंद्र से छठे/सातवें/आठवें भाव में पर्याप्त शुभ ग्रह नहीं हैं।"),
    (rf"^{_P} in the 10th from lagna\.$", "{p} लग्न से दशम भाव में।"),
    (rf"^{_P} in the 10th from Moon\.$", "{p} चंद्र से दशम भाव में।"),
    (r"^No natural benefic in the 10th house\.$", "दशम भाव में कोई नैसर्गिक शुभ ग्रह नहीं है।"),
    (r"^Jupiter aspects or conjoins Mars\.$", "गुरु मंगल को देखता है या उसके साथ स्थित है।"),
    (rf"^Mars is {_D}, reducing the dosha effect\.$", "मंगल {d} में है, जिससे दोष का प्रभाव घटता है।"),
    (r"^Mars occupies house (?P<n>\d+) from lagna\.$", "मंगल लग्न से भाव {n} में स्थित है।"),
    (rf"^Sun conjoined with (?P<node>Rahu|Ketu) in {_S}\.$", "सूर्य {s} राशि में {node} के साथ युति में है।"),
    (r"^Sun is not conjunct either node\.$", "सूर्य किसी भी छाया ग्रह के साथ युति में नहीं है।"),
    (r"^Lord of (?P<k>\d+)th \(kendra\) and lord of (?P<t>\d+)th \(trikona\): (?P<pl>[a-z+]+)\.$",
     "{k} भाव (केंद्र) और {t} भाव (त्रिकोण) के स्वामी: {pl}।"),
    (r"^No kendra-trikona lord conjunction found\.$", "केंद्र-त्रिकोण स्वामियों की युति नहीं मिली।"),
    (rf"^Lord of (?P<h>2nd|11th|9th): {_P} \((?P<place>.+)\)\.$", "{h} भाव का स्वामी: {p} ({place})।"),
    (r"^Lords of 2nd and 11th are conjunct\.$", "द्वितीय और एकादश भाव के स्वामी युति में हैं।"),
    (r"^Lords of 2nd and 11th are in mutual 7th aspect\.$",
     "द्वितीय और एकादश भाव के स्वामी परस्पर सप्तम दृष्टि में हैं।"),
    (r"^No conjunction or mutual aspect between lords of 2nd and 11th\.$",
     "द्वितीय और एकादश भाव के स्वामियों में न युति है, न परस्पर दृष्टि।"),
    (rf"^(?P<v>Harsha|Sarala|Vimala) Yoga: lord of (?P<h>\d+)th \({_P}\) placed in house (?P<n>\d+)\.$",
     "{v} योग: {h} भाव का स्वामी ({p}) भाव {n} में स्थित है।"),
    (r"^No dusthana lord is placed in another dusthana\.$", "कोई दुःस्थान स्वामी अन्य दुःस्थान में स्थित नहीं है।"),
    (rf"^{_P} is debilitated; its dispositor (?P<q>[a-z]+) is in kendra \(house (?P<n>\d+)\)\.$",
     "{p} नीच है; उसका राशि-स्वामी {q} केंद्र (भाव {n}) में है।"),
    (rf"^{_P} is debilitated; its dispositor (?P<q>[a-z]+) is {_D}\.$",
     "{p} नीच है; उसका राशि-स्वामी {q} {d} में है।"),
    (r"^Debilitated planet\(s\): (?P<pl>[a-z, ]+) but no cancellation conditions met\.$",
     "नीच ग्रह: {pl}, किंतु नीचभंग की कोई शर्त पूरी नहीं हुई।"),
    (r"^No debilitated planet found\.$", "कोई नीच ग्रह नहीं मिला।"),
    (rf"^{_P} in house (?P<n>\d+) \({_D}\)\.$", "{p} भाव {n} में ({d})।"),
    (r"^Jupiter is dignified\.$", "गुरु सम्मानित स्थिति में है।"),
    (r"^Jupiter is weak \(debilitated or in enemy sign\)\.$", "गुरु दुर्बल है (नीच या शत्रु राशि में)।"),
    (r"^Dignity: (?P<d>[a-z]+)\. House: (?P<n>\d+)\.$", "बल स्थिति: {d}। भाव: {n}।"),
    (r"^Lord of 9th is strong in a kendra\.$", "नवम भाव का स्वामी केंद्र में बलवान है।"),
    (r"^Lord of 9th is strong but not in a kendra\.$", "नवम भाव का स्वामी बलवान है, किंतु केंद्र में नहीं।"),
    (r"^Lord of 9th is in a kendra but not strong\.$", "नवम भाव का स्वामी केंद्र में है, किंतु बलवान नहीं।"),
    (r"^Lord of 9th is neither in a kendra nor strong\.$", "नवम भाव का स्वामी न केंद्र में है, न बलवान।"),
    (r"^(?P<l>Sun|Moon) conjunct (?P<node>Rahu|Ketu) \((?P<kind>solar|lunar) eclipse pattern\)\.$",
     "{l} की {node} से युति ({kind} ग्रहण का योग)।"),
    (r"^Neither luminary is conjunct a node\.$", "कोई भी प्रकाशक ग्रह (सूर्य/चंद्र) राहु-केतु के साथ नहीं है।"),
]
_COMPILED = [(re.compile(rx), tpl) for rx, tpl in _PATTERNS]
_ORD = {"2nd": "द्वितीय", "12th": "द्वादश", "11th": "एकादश", "9th": "नवम"}
_NODE = {"Rahu": "राहु", "Ketu": "केतु"}
_LUM_HI = {"Moon": "चंद्र", "Sun": "सूर्य"}
_ECL = {"solar": "सूर्य", "lunar": "चंद्र"}


def _planet_list(text: str) -> str:
    return re.sub(r"[a-z]+", lambda m: names.PLANETS_HI.get(m.group(0), m.group(0)), text)


def translate_evidence(line: str) -> str:
    for rx, tpl in _COMPILED:
        m = rx.match(line)
        if not m:
            continue
        g = m.groupdict()
        out = {}
        for k, v in g.items():
            if k in ("p", "q", "l") and v in names.PLANETS_HI:
                out[k] = names.PLANETS_HI[v]
            elif k in ("p", "q") or k == "pl":
                out[k] = _planet_list(v)
            elif k == "s":
                out[k] = names.SIGNS_HI[v]
            elif k == "d":
                out[k] = names.DIGNITIES_HI.get(v, v)
            elif k == "lum" or k == "l":
                out[k] = _LUM_HI[v]
            elif k in ("h", "k", "t"):
                out[k] = _ORD.get(v) or names.ORDINALS_HI.get(int(v.rstrip("thndrs")), v)
            elif k == "v":
                out[k] = {"Harsha": "हर्ष", "Sarala": "सरल", "Vimala": "विमल"}[v]
            elif k == "node":
                out[k] = _NODE[v]
            elif k == "kind":
                out[k] = _ECL[v]
            elif k == "place":
                out[k] = translate_evidence(v)
            else:
                out[k] = v
        return tpl.format(**out)
    return line


def localize_yoga(yoga: dict) -> tuple[str, str, list[str]]:
    key = yoga["key"]
    name = YOGA_NAMES_HI.get(key, yoga["name"])
    if key in names.YOGA_PLANET_KEYS:
        desc = _MAHA_DESC.format(planet=names.PLANETS_HI[names.YOGA_PLANET_KEYS[key]])
    else:
        desc = YOGA_DESC_HI.get(key, yoga["description"])
    return name, desc, [translate_evidence(e) for e in yoga["evidence"]]
