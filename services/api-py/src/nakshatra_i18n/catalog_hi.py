"""Hindi (Devanagari) message catalog. Same keys and placeholders as catalog_en.

Register: formal, respectful (आप). Standard Jyotish terms. Machine-generated
first draft by the engineering team: every string here is flagged for review by
a native-speaker Jyotishi (see docs/i18n/hindi-review.md).
"""

HI: dict[str, str] = {
    # ---- reading: section titles
    "reading.sec.lagna": "लग्न और स्वभाव",
    "reading.sec.planets": "ग्रह-दर-ग्रह फल",
    "reading.sec.houses": "भाव-दर-भाव फल",
    "reading.sec.yogas": "सक्रिय योग और दोष",
    "reading.sec.dasha": "वर्तमान दशा फल",
    "reading.sec.vargas": "वर्ग कुंडली विशेष",
    "reading.sec.panchang": "जन्म पंचांग",

    # ---- reading: lagna
    "lagna.title": "{sign} लग्न: स्वभाव और जीवन की दिशा",
    "lagna.text": (
        "लग्न {sign} राशि ({sign_trait}) में उदित है, {nak} नक्षत्र के चरण {pada} में, "
        "जो व्यक्तित्व को {nak_trait} का रंग देता है। लग्नेश {lord} {lord_house} भाव में "
        "{lord_sign} राशि में स्थित है, {dignity}; इसलिए जीवन की दिशा प्रमुख रूप से "
        "{themes} के माध्यम से प्रवाहित होती है।"
    ),
    "lagna.ev.asc": "लग्न {sign}, {deg} अंश, {nak} नक्षत्र चरण {pada}।",
    "lagna.ev.lord": "लग्नेश {lord} भाव {house} में ({sign}, {dignity})।",

    # ---- reading: planets
    "planet.title": "{house_ord} भाव में {title}",
    "planet.head": (
        "{title}, {karakas} का कारक ग्रह, {sign} राशि ({nak} नक्षत्र, चरण {pada}) में "
        "{house_ord} भाव में स्थित है, {dignity}।"
    ),
    "planet.retro": (
        "वक्री गति इसके कार्य को अंतर्मुखी बना देती है: पुनरावलोकन, संशोधन और दूसरे "
        "प्रयासों से फल गहरे होते हैं।"
    ),
    "planet.combust": (
        "सूर्य से अस्त होने के कारण इसके कारकत्व पहचान और दृश्यता के प्रश्नों में घुल "
        "जाते हैं; इसकी देन अपने प्रदर्शन के बजाय किसी बड़ी भूमिका की सेवा में सबसे "
        "अधिक चमकती है।"
    ),
    "planet.band": "षड्बल इसे {band} आँकता है, अतः {themes} के विषयों में {effect} की अपेक्षा रखें।",
    "planet.channel": "इस स्थिति के माध्यम से यह {effect} को {themes} की ओर प्रवाहित करता है।",
    "planet.ev.place": "{planet} {sign} राशि में {deg} अंश, भाव {house}, बल स्थिति {dignity}।",
    "planet.ev.retro": "{planet} वक्री।",
    "planet.ev.combust": "{planet} अस्त।",
    "planet.ev.shadbala": "षड्बल अनुपात {ratio} (आवश्यक {rupas} रूप)।",

    # ---- reading: houses
    "house.l1": (
        "{name} ({themes}) {sign} राशि में पड़ता है और {bindus} सर्वाष्टकवर्ग बिंदुओं के "
        "साथ {band} है।"
    ),
    "house.occ": "{occ} की उपस्थिति से इसके विषय सक्रिय और व्यक्तिगत रूप से महत्वपूर्ण बने रहते हैं।",
    "house.empty": "कोई ग्रह स्थित न होने से इसके फल मुख्यतः इसके स्वामी {lord} के माध्यम से प्रवाहित होते हैं।",
    "house.link": (
        "स्वामी {lord} {house_ord} भाव ({sign}, {dignity}) में स्थित है, जो {a} को {b} से "
        "जोड़ता है।"
    ),
    "house.ev.sav": "भाव {n} = {sign}, सर्वाष्टकवर्ग बिंदु {bindus}।",
    "house.ev.lord": "स्वामी {lord} भाव {h} में ({dignity})।",
    "house.ev.occ": "स्थित ग्रह: {occ}।",

    # ---- reading: dasha
    "dasha.text": (
        "वर्तमान महादशा {title} की है, जो जन्म कुंडली में {house_ord} भाव में {sign} "
        "राशि ({dignity}) में स्थित है। यह काल {karakas} को सामने लाता है, जिसकी "
        "अभिव्यक्ति {themes} के माध्यम से होती है।"
    ),
    "dasha.antar": (
        " इसके भीतर {planet} की अंतर्दशा ({end} तक) घटनाओं को {house_ord} भाव के "
        "माध्यम से छानती है ({themes}), जिससे {karakas} दैनिक जीवन के केंद्र में आ जाते हैं।"
    ),
    "dasha.ev.maha": "{planet} महादशा {start} से {end} तक।",
    "dasha.ev.natal": "जन्म कुंडली में {planet} भाव {h} में ({sign}, {dignity})।",
    "dasha.ev.antar": "{planet} अंतर्दशा {start} से {end} तक; जन्म कुंडली में {planet} भाव {h} में।",
    "dasha.title.md": "वर्तमान काल: {md} महादशा",
    "dasha.title.mdad": "वर्तमान काल: {md} महादशा / {ad} अंतर्दशा",

    # ---- reading: vargas
    "varga.d9.title": "नवांश (D9): विवाह और आंतरिक बल",
    "varga.d9.text": (
        "नवांश में लग्न {asc} राशि में पड़ता है। विवाह का कारक शुक्र {venus_d9} में और "
        "चंद्र {moon_d9} में जाता है; इनकी राशि कुंडली की स्थितियों ({venus_rashi}, "
        "{moon_rashi}) से तुलना करने पर दिखता है कि जन्म कुंडली की सतह के नीचे संबंध "
        "कैसे परिपक्व होते हैं।"
    ),
    "varga.d9.ev1": "नवांश लग्न {asc}।",
    "varga.d9.ev2": "नवांश में शुक्र {venus}; नवांश में चंद्र {moon}।",
    "varga.d10.title": "दशमांश (D10): करियर की अभिव्यक्ति",
    "varga.d10.text": (
        "दशमांश में लग्न {asc} राशि में पड़ता है। सूर्य (अधिकार) {sun} में और शनि "
        "(निरंतर परिश्रम) {saturn} में स्थित है, जो राशि कुंडली के दशम भाव से आगे "
        "व्यावसायिक जीवन की बनावट को दर्शाता है।"
    ),
    "varga.d10.ev1": "दशमांश लग्न {asc}।",
    "varga.d10.ev2": "दशमांश में सूर्य {sun}; दशमांश में शनि {saturn}।",

    # ---- reading: panchang
    "panchang.title": "जन्म पंचांग",
    "panchang.text": (
        "जन्म {vara} को {paksha} पक्ष की {tithi} तिथि में, {nak} नक्षत्र (चरण {pada}) के "
        "अंतर्गत, {yoga} योग और {karana} करण के साथ हुआ। जन्म नक्षत्र मन को "
        "{nak_trait} प्रदान करता है।"
    ),
    "panchang.ev": (
        "तिथि {tithi} ({paksha}), करण {karana}, योग {yoga}, वार {vara}, "
        "चंद्र नक्षत्र {nak} चरण {pada}।"
    ),

    # ---- life story: age bands
    "ls.band.childhood.title": "बाल्यावस्था",
    "ls.band.childhood.focus": "घर, देखभाल, स्वभाव और आरंभिक भावनात्मक नींव",
    "ls.band.youth.title": "किशोरावस्था और युवावस्था",
    "ls.band.youth.focus": "शिक्षा, मित्रमंडली, साहस और व्यक्तित्व का निर्माण",
    "ls.band.early-adulthood.title": "प्रारंभिक वयस्कता",
    "ls.band.early-adulthood.focus": "साझेदारी, करियर की दिशा और संसाधनों का निर्माण",
    "ls.band.midlife.title": "मध्य आयु",
    "ls.band.midlife.focus": "अधिकार, लाभ और गहन रूपांतरण",
    "ls.band.later-life.title": "उत्तर आयु",
    "ls.band.later-life.focus": "धर्म, मुक्ति और जड़ों की ओर वापसी",

    # ---- life story: items
    "ls.child.title": "स्वभाव और घर की नींव",
    "ls.child.text": (
        "बचपन का रंग {moon_house} भाव में स्थित चंद्र ({sign}, {nak}) से आता है, जिसका "
        "स्वरूप {nak_trait} है, और लग्नेश {ll_title} से, जो {ll_house} भाव में है; ये "
        "आरंभिक {h4} और {h1} को आकार देते हैं।"
    ),
    "ls.child.ev.moon": "चंद्र भाव {h} में ({sign}, {nak} नक्षत्र चरण {pada})।",
    "ls.child.ev.lord": "लग्नेश {lord} भाव {h} में ({sign}, {dignity})।",
    "ls.stage.title": "{name}: विषय",
    "ls.stage.text": (
        "इस चरण में {themes} का महत्व रहता है। {house_ord} भाव के स्वामी {lord_title} हैं, "
        "जो {lh_ord} भाव में {sign} राशि ({dignity}) में स्थित हैं।{occ_phrase}"
    ),
    "ls.stage.occ": " इसमें {occ} स्थित हैं।",
    "ls.stage.noocc": " इसमें कोई जन्मकालीन ग्रह स्थित नहीं है; विषय को स्वामी वहन करता है।",
    "ls.stage.ev.lord": "भाव {n} का स्वामी {lord} भाव {h} में ({sign}, {dignity})।",
    "ls.stage.ev.occ": "भाव {n} में स्थित ग्रह: {occ}।",
    "ls.maha.colour": "{display} महादशा का रंग",
    "ls.promise": (
        "{title} जन्म कुंडली में {house_ord} भाव में {sign} राशि ({dignity}) में स्थित है "
        "और {karakas} को {themes} के माध्यम से प्रवाहित करता है। महादशा स्वामी के रूप में "
        "यह अपने स्वामित्व के भावों को सक्रिय करता है: {ruled}। फलस्वरूप {effect} की "
        "अपेक्षा रखें।"
    ),
    "ls.promise.noruled": (
        "{title} जन्म कुंडली में {house_ord} भाव में {sign} राशि ({dignity}) में स्थित है "
        "और {karakas} को {themes} के माध्यम से प्रवाहित करता है। महादशा स्वामी के रूप में "
        "यह अपने स्वामित्व के भावों को सक्रिय करता है। फलस्वरूप {effect} की अपेक्षा रखें।"
    ),
    "ls.ruled_item": "{ord} ({themes})",
    "ls.ev.natal": "जन्म कुंडली में {planet} भाव {h} में ({sign}, {dignity})।",
    "ls.ev.rules": "{planet} लग्न से भाव {houses} का स्वामी है।",
    "ls.ev.band": "{planet} का षड्बल स्तर: {band}।",
    "ls.ev.maha": "{planet} महादशा {start} से {end} तक।",
    "ls.md.one": "{a} के वर्षों में, ",
    "ls.md.many": "{head} और {last} के वर्षों में, ",
    "ls.age.plus": "आयु {frm}+",
    "ls.age.range": "आयु {frm}-{to} वर्ष",
    "ls.summary": (
        "{md_clause}{title} ({age_label}) में {focus} प्रमुख रहते हैं। कुंडली इस अध्याय को "
        "नीचे बताए गए भावों और स्वामियों के माध्यम से दिशा देती है; ये समय की संभावित "
        "खिड़कियाँ हैं, निश्चित जीवन-घटनाएँ नहीं।"
    ),
    "ls.title.open": "{title} ({frm}+)",
    "ls.title.range": "{title} ({frm}–{to})",
    "ls.title.hybrid": "{title} · {names}",
    "ls.dasha.title": "{display} के वर्ष, आयु {a}–{b}",
    "ls.dasha.promise": "{display} महादशा का फल",
    "ls.dasha.antar.title": "{display} अंतर्दशा का रंग",
    "ls.dasha.antar.text": (
        "इस महादशा के भीतर {title} की लंबी अंतर्दशा ({start} से {end} तक) दैनिक जीवन को "
        "अपनी जन्मकालीन प्रतिज्ञा के माध्यम से छानती है। {promise}"
    ),
    "ls.dasha.antar.ev": "{planet} अंतर्दशा {start} से {end} तक।",
    "ls.dasha.ruled.title": "स्वामित्व से सक्रिय होने वाले भाव",
    "ls.dasha.ruled.item": "{name}: {themes}",
    "ls.dasha.ruled.text": (
        "{display} लग्न से {themes} का स्वामी है। इन वर्षों में जीवन के ये क्षेत्र "
        "कुंडली में सबसे आगे रहते हैं।"
    ),
    "ls.dasha.ruled.ev": "{planet} भाव {houses} का स्वामी है।",
    "ls.dasha.summary": (
        "{display} महादशा {start} से {end} तक चलती है (लगभग आयु {a}–{b})। यह {karakas} "
        "को सामने लाती है, जिसकी अभिव्यक्ति नीचे बताई गई जन्मकालीन स्थिति और भावों के "
        "माध्यम से होती है।"
    ),
    "ls.through.title": "स्वभाव की मूल धारा",
    "ls.through.text": (
        "हर अध्याय में {sign} लग्न ({sign_trait}) और {nak} में स्थित चंद्र ({nak_trait}) "
        "स्वभाव की मूल धारा तय करते हैं।"
    ),
    "ls.through.yoga": " सक्रिय योगों में {yoga} एक स्थायी पहचान बना रहता है।",
    "ls.through.ev.asc": "लग्न {sign}, {nak} नक्षत्र चरण {pada}।",
    "ls.through.ev.moon": "चंद्र नक्षत्र {nak} चरण {pada}।",
    "ls.through.ev.yoga": "सक्रिय योग: {yoga}।",

    # ---- prediction rules
    "rule.lord-strong-dasha": (
        "{level} स्वामी {lord} {label} से जुड़े भावों का स्वामी है और अपेक्षित से अधिक "
        "षड्बल रखता है, जिससे {label} के क्षेत्र में लाभ सक्रिय होते हैं।"
    ),
    "rule.lord-weak-dasha": (
        "{level} स्वामी {lord} {label} से जुड़े भावों का स्वामी है, किंतु षड्बल में "
        "दुर्बल है; इस अवधि में {label} के विषयों में सजग प्रयास की आवश्यकता है।"
    ),
    "rule.lord-in-domain-house": (
        "{level} स्वामी {lord} {label} से जुड़े भाव में सुस्थित है, जिससे {label} में "
        "प्रत्यक्ष फल मिलते हैं।"
    ),
    "rule.lord-dusthana-weak": (
        "{level} स्वामी {lord} {label} का अधिपति है, किंतु क्षतिपूर्ति करने वाले बल के "
        "बिना दुःस्थान (त्रिक भाव) से कार्य करता है, जिससे पहले बाधाएँ आती हैं।"
    ),
    "rule.career-exalted-lord-kendra": (
        "उच्च राशि का {level} स्वामी {lord} केंद्र या त्रिकोण में हो तो यह दृश्यमान "
        "उन्नति और मान्यता का काल होता है।"
    ),
    "rule.wealth-gajakesari-jupiter": (
        "गुरु की {level} में गजकेसरी योग सक्रिय होता है: प्रतिष्ठा से प्राप्त लाभ और "
        "धन की रक्षा।"
    ),
    "rule.marriage-venus-dasha-strong": (
        "बलवान शुक्र की {level} साझेदारी, सगाई और मौजूदा संबंधों में सामंजस्य के "
        "अनुकूल होती है।"
    ),
    "rule.health-sade-sati-window": (
        "इस अवधि में साढ़ेसाती चल रही है; ऊर्जा, नींद और दिनचर्या का ध्यान रखें; "
        "स्थिर अनुशासन दबाव को सहनशक्ति में बदल देता है।"
    ),
    "rule.health-combust-lord": (
        "{level} स्वामी {lord} जन्म कुंडली में अस्त है, जिससे इसके रक्षात्मक फल क्षीण "
        "हो जाते हैं; स्वयं को अधिक न खींचें।"
    ),
    "rule.spiritual-ketu-dasha": (
        "केतु की {level} ध्यान को भीतर की ओर मोड़ती है: चिंतन-साधना और वैराग्य सहज "
        "रूप से गहरे होते हैं।"
    ),
    "rule.travel-rahu-dasha": (
        "राहु की {level} अपारंपरिक बदलावों के अनुकूल है: विदेश, नए परिवेश और सीमाएँ "
        "लाँघने वाले अवसर।"
    ),

    # ---- prediction rule sources
    "src.dasha-phala-full": (
        "बृहत्पाराशर होराशास्त्र, दशाफल अध्याय (दशा के फल स्वामित्व और बल का अनुसरण करते हैं)"
    ),
    "src.dasha-phala": "बृहत्पाराशर होराशास्त्र, दशाफल अध्याय",
    "src.phaladeepika-placement": "फलदीपिका (दशा स्वामियों की स्थिति)",
    "src.bphs-dusthana": "बृहत्पाराशर होराशास्त्र (दशा स्वामियों की दुःस्थान स्थिति)",
    "src.phaladeepika": "फलदीपिका",
    "src.bphs-yoga-phala": (
        "बृहत्पाराशर होराशास्त्र, योगफल (योग अपने कारकों की दशा में फलित होते हैं)"
    ),
    "src.venus-karaka": "विवाह के कारक के रूप में शुक्र (बृहत्पाराशर होराशास्त्र, कारकाध्याय)",
    "src.sade-sati": "शनि गोचर परंपरा (साढ़ेसाती)",
    "src.combustion": "अस्त ग्रह सिद्धांत",
    "src.ketu-moksha": "मोक्षकारक के रूप में केतु",
    "src.rahu-videsha": "विदेशकारक के रूप में राहु",

    # ---- prediction evidence and framing
    "cond.owns": "{lord} भाव {hits} का स्वामी है",
    "cond.occupies": "{lord} भाव {house} में स्थित है",
    "cond.dignity": "{lord} {dignity} में है",
    "cond.ratio_ge": "{lord} का षड्बल अनुपात {ratio} ≥ {th}",
    "cond.ratio_lt": "{lord} का षड्बल अनुपात {ratio} < {th}",
    "cond.lord_is": "{level} स्वामी {lord} है",
    "cond.combust": "{lord} जन्म कुंडली में अस्त है",
    "cond.yoga": "जन्मकालीन योग उपस्थित: {keys}",
    "cond.sade_sati": "अवधि के मध्य बिंदु पर साढ़ेसाती सक्रिय है",
    "pred.headline": "{domain} - {md} महादशा / {ad} अंतर्दशा ({label})",
    "pred.window": "{start} से {end} तक",
    "pred.tension": (
        "इस अवधि में अनुकूल और चुनौतीपूर्ण, दोनों संकेत हैं; किसी एक को चुनने के बजाय "
        "दोनों को साथ पढ़ें: "
    ),
    "pred.driver": "{lord} का षड्बल अनुपात {ratio}",
    "pred.and": " और ",

    # ---- remedies
    "rem.mantra.title": "{planet} के लिए {deity} मंत्र",
    "rem.mantra.practice": "{mantra}, {count}।",
    "rem.mantra.rationale": (
        "मंत्र जप सबसे सुरक्षित प्रथम उपाय है: यह {planet} को बढ़ाए बिना उसे शांत करता है।"
    ),
    "rem.daan.title": "{planet} के लिए दान",
    "rem.daan.practice": "{daan} का दान करें।",
    "rem.daan.rationale": (
        "दान पीड़ित {planet} को बलवान करने के बजाय उसके कर्म-ऋण को चुकाता है।"
    ),
    "rem.fast.title": "{day} का व्रत-नियम",
    "rem.fast.practice": "{day} को हल्का उपवास या सरल सात्त्विक आहार।",
    "rem.fast.rationale": "{planet} का वार उसके उपाय को केंद्रित करता है।",
    "rem.fast.caution": (
        "गर्भावस्था में, मधुमेह होने पर या चिकित्सक द्वारा मना किए जाने पर उपवास बिल्कुल न करें।"
    ),
    "rem.gem.title": "{gem} (केवल परीक्षण के बाद)",
    "rem.gem.practice": (
        "{gem} {planet} को सहारा दे सकता है, क्योंकि यह कार्येश शुभ ग्रह है जिसमें बल की कमी है।"
    ),
    "rem.gem.rationale": (
        "इस लग्न के लिए {planet} त्रिकोण का स्वामी है और दुर्बल होते हुए भी पीड़ित नहीं है; "
        "यही वह एकमात्र स्थिति है जिसमें शास्त्रीय रूप से बल बढ़ाने वाला रत्न मान्य है।"
    ),
    "rem.gem.caution1": (
        "रत्न ग्रह को बिना भेद किए बढ़ाते हैं; केवल परीक्षण अवधि के बाद और तभी धारण करें "
        "जब ग्रह इस लग्न के लिए कार्येश शुभ हो।"
    ),
    "rem.gem.caution2": "पहले से धारण किए गए शत्रु ग्रहों के रत्नों के साथ न पहनें।",
    "rem.gem.caution3": (
        "यह केवल परामर्श है; खरीद से पहले योग्य ज्योतिषी से सलाह लें; रत्न का आकार नहीं, "
        "उसकी गुणवत्ता और जड़ाई अधिक महत्वपूर्ण है।"
    ),
    "rem.ev.place": "{planet} {sign} राशि में (भाव {house}), बल स्थिति {dignity}",
    "rem.ev.ratio": "षड्बल अनुपात {ratio} (आवश्यक 1.00)",
    "rem.ev.combust": "{planet} अस्त है",
}

# Remedy data: Hindi counterparts of nakshatra_rules.remedies._REMEDY_DATA.
REMEDY_DATA_HI: dict[str, dict[str, str]] = {
    "sun": {
        "mantra": "ॐ ह्रां ह्रीं ह्रौं सः सूर्याय नमः",
        "mantraCount": "40 दिनों में 7000 जप",
        "daan": "रविवार को गेहूँ, गुड़ या तांबा",
        "fastingDay": "रविवार",
        "gemstone": "माणिक्य (रूबी)",
        "deity": "सूर्य / आदित्य",
    },
    "moon": {
        "mantra": "ॐ श्रां श्रीं श्रौं सः चंद्राय नमः",
        "mantraCount": "40 दिनों में 11000 जप",
        "daan": "सोमवार को चावल, दूध या सफेद वस्त्र",
        "fastingDay": "सोमवार",
        "gemstone": "मोती",
        "deity": "चंद्र / शिव",
    },
    "mars": {
        "mantra": "ॐ क्रां क्रीं क्रौं सः भौमाय नमः",
        "mantraCount": "40 दिनों में 10000 जप",
        "daan": "मंगलवार को लाल मसूर या गुड़",
        "fastingDay": "मंगलवार",
        "gemstone": "लाल मूँगा",
        "deity": "हनुमान / कार्तिकेय",
    },
    "mercury": {
        "mantra": "ॐ ब्रां ब्रीं ब्रौं सः बुधाय नमः",
        "mantraCount": "40 दिनों में 9000 जप",
        "daan": "बुधवार को हरी मूँग या शिक्षा-सामग्री",
        "fastingDay": "बुधवार",
        "gemstone": "पन्ना",
        "deity": "विष्णु",
    },
    "jupiter": {
        "mantra": "ॐ ग्रां ग्रीं ग्रौं सः गुरवे नमः",
        "mantraCount": "40 दिनों में 19000 जप",
        "daan": "गुरुवार को चने की दाल, हल्दी या पुस्तकें",
        "fastingDay": "गुरुवार",
        "gemstone": "पुखराज",
        "deity": "बृहस्पति / दक्षिणामूर्ति",
    },
    "venus": {
        "mantra": "ॐ द्रां द्रीं द्रौं सः शुक्राय नमः",
        "mantraCount": "40 दिनों में 16000 जप",
        "daan": "शुक्रवार को सफेद चावल, दही या सफेद वस्त्र",
        "fastingDay": "शुक्रवार",
        "gemstone": "हीरा या सफेद पुखराज",
        "deity": "लक्ष्मी",
    },
    "saturn": {
        "mantra": "ॐ प्रां प्रीं प्रौं सः शनये नमः",
        "mantraCount": "40 दिनों में 23000 जप",
        "daan": "शनिवार को काले तिल, सरसों का तेल या लोहा",
        "fastingDay": "शनिवार",
        "gemstone": "नीलम",
        "deity": "शनि / हनुमान",
    },
    "rahu": {
        "mantra": "ॐ भ्रां भ्रीं भ्रौं सः राहवे नमः",
        "mantraCount": "40 दिनों में 18000 जप",
        "daan": "ज़रूरतमंदों को कंबल या गहरे नीले रंग की वस्तुएँ",
        "fastingDay": "शनिवार",
        "gemstone": "गोमेद",
        "deity": "दुर्गा",
    },
    "ketu": {
        "mantra": "ॐ स्रां स्रीं स्रौं सः केतवे नमः",
        "mantraCount": "40 दिनों में 17000 जप",
        "daan": "गुरुवार को बहुरंगी कंबल या कुत्तों की देखभाल",
        "fastingDay": "गुरुवार",
        "gemstone": "लहसुनिया",
        "deity": "गणेश",
    },
}
