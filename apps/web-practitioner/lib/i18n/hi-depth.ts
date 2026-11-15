/**
 * Hindi for the depth tabs: planet detail, ashtakavarga, dasha drill-down and the proof drawer.
 * Needs native review like hi.ts. Terms follow the engine catalogs (Jyotish, Parashari).
 */
export const HI_DEPTH: Record<string, string> = {
  // generic words
  "none": "कोई नहीं",
  "None": "कोई नहीं",
  "Yes": "हाँ",
  "No": "नहीं",
  "Odd": "विषम",
  "Even": "सम",
  "Level": "स्तर",
  "Lord": "स्वामी",
  "Sign": "राशि",
  "Pada": "चरण",
  "Karaka": "कारक",
  "to": "से",
  "in": "में",
  "years": "वर्ष",
  "Total": "योग",

  // planet table
  "Nakshatra lord": "नक्षत्र स्वामी",
  "Sign lord": "राशि स्वामी",
  "Avastha": "अवस्था",
  "Chara karaka": "चर कारक",
  "Rules houses": "स्वामी भाव",
  "State": "स्थिति",
  "Retrograde": "वक्री",
  "Direct": "मार्गी",
  "Combust": "अस्त",
  "Combustion": "अस्त स्थिति",
  "Clear": "अस्त नहीं",
  "Not tested": "जाँच लागू नहीं",
  "Not assigned": "निर्धारित नहीं",
  "Lagna {sign} {nakshatra} pada {pada}. Select any underlined value to see how it was worked out.":
    "लग्न {sign}, {nakshatra} नक्षत्र, चरण {pada}। रेखांकित किसी भी मान को चुनकर देखें कि वह कैसे निकला।",
  "Chara karakas use the seven planet scheme, so Rahu and Ketu have none. Baladi avastha is not assigned to the nodes.":
    "चर कारक सात ग्रहों की पद्धति से बनते हैं, इसलिए राहु और केतु के कारक नहीं होते। बालादि अवस्था राहु और केतु को नहीं दी जाती।",
  "Bala": "बाल", "Kumara": "कुमार", "Yuva": "युवा", "Vriddha": "वृद्ध", "Mrita": "मृत",
  "Atmakaraka": "आत्मकारक", "Amatyakaraka": "अमात्यकारक", "Bhratrikaraka": "भ्रातृकारक",
  "Matrikaraka": "मातृकारक", "Putrakaraka": "पुत्रकारक", "Gnatikaraka": "ज्ञातिकारक", "Darakaraka": "दारकारक",

  // ashtakavarga
  "Ashtakavarga": "अष्टकवर्ग",
  "Sarvashtakavarga": "सर्वाष्टकवर्ग",
  "Sarva": "सर्व",
  "Ashtakavarga grids": "अष्टकवर्ग तालिकाएँ",
  "bindus": "बिंदु",
  "total bindus": "कुल बिंदु",
  "grand total": "महायोग",
  "Bindus each planet gives to the twelve signs, and their sum. Select any number to see which planets gave it.":
    "हर ग्रह द्वारा बारह राशियों को दिए गए बिंदु और उनका योग। किसी भी संख्या को चुनकर देखें कि किन ग्रहों ने उसे दिया।",
  "Colour legend": "रंग संकेत",
  "Sarva {n} or more: strong sign": "सर्व {n} या अधिक: बलवान राशि",
  "Sarva {n} or fewer: weak sign": "सर्व {n} या कम: दुर्बल राशि",
  "Planet row {n} or more": "ग्रह पंक्ति में {n} या अधिक",
  "Planet row {n} or fewer": "ग्रह पंक्ति में {n} या कम",
  "Strongest signs": "सबसे बलवान राशियाँ",
  "Weakest signs": "सबसे दुर्बल राशियाँ",
  "None at or above {n}": "{n} या उससे अधिक कोई नहीं",
  "None at or below {n}": "{n} या उससे कम कोई नहीं",
  "house {n}": "भाव {n}",
  "gives a bindu from {house}": "{house} से बिंदु देता है",
  "Contributors giving none": "बिंदु न देने वाले योगदानकर्ता",
  "The row total is the sum of its twelve signs. For each planet it is fixed by the classical tables: Sun 48, Moon 49, Mars 39, Mercury 54, Jupiter 56, Venus 52, Saturn 39.":
    "पंक्ति का योग उसकी बारह राशियों का जोड़ है। हर ग्रह के लिए यह शास्त्रीय तालिकाओं से तय है: सूर्य 48, चंद्र 49, मंगल 39, बुध 54, गुरु 56, शुक्र 52, शनि 39।",
  "The Sarvashtakavarga of a sign is the sum of the seven planets' bindus in it. {high} or more is strong, {low} or fewer is weak, and the average is 28.":
    "किसी राशि का सर्वाष्टकवर्ग उसमें सातों ग्रहों के बिंदुओं का योग है। {high} या अधिक बलवान, {low} या कम दुर्बल, और औसत 28 है।",
  "The grand total is the sum of the seven row totals. In the classical scheme it is always 337.":
    "महायोग सात पंक्तियों के योग का जोड़ है। शास्त्रीय पद्धति में यह सदा 337 होता है।",

  // dasha drill-down
  "Maha, antar and pratyantar dasha with exact dates.": "महादशा, अंतर्दशा और प्रत्यंतर्दशा, ठीक तिथियों सहित।",
  "Maha and antar dasha with exact dates. The Yogini system has no deeper level.":
    "महादशा और अंतर्दशा, ठीक तिथियों सहित। योगिनी पद्धति में इससे गहरा स्तर नहीं होता।",
  "Running now": "अभी चल रही",
  "Show running period": "चल रही अवधि दिखाएँ",
  "Collapse all": "सब समेटें",
  "Collapse": "समेटें",
  "Expand": "खोलें",
  "Dasha periods": "दशा अवधियाँ",
  "Mahadasha": "महादशा",
  "Antardasha": "अंतर्दशा",
  "Pratyantardasha": "प्रत्यंतर्दशा",
  "{y} yr": "{y} वर्ष",
  "{y} yr {m} mo": "{y} वर्ष {m} माह",
  "{m} mo": "{m} माह",
  "{d} days": "{d} दिन",
  "Lord's years in the cycle": "चक्र में स्वामी के वर्ष",
  "Cycle length (years)": "चक्र की अवधि (वर्ष)",
  "Parent period": "ऊपरी अवधि",
  "Length": "अवधि",
  "Balance of the first period at birth (years)": "जन्म पर पहली अवधि का शेष (वर्ष)",
  "Birth nakshatra": "जन्म नक्षत्र",
  "Starts": "आरंभ",
  "Ends": "समाप्ति",
  "Year length (days)": "वर्ष की लंबाई (दिन)",
  "Vimshottari runs a 120 year cycle. A maha dasha lasts the lord's years. Inside it, each sub period is the parent's length times the sub lord's years divided by 120, starting with the parent's own lord.":
    "विंशोत्तरी 120 वर्ष का चक्र है। महादशा उसके स्वामी के वर्षों तक चलती है। उसके भीतर हर उप अवधि, ऊपरी अवधि की लंबाई गुणा उप स्वामी के वर्ष भाग 120 होती है, और क्रम ऊपरी अवधि के अपने स्वामी से शुरू होता है।",
  "Yogini dasha runs a 36 year cycle of eight yoginis. Each antardasha is the parent's length times the sub yogini's years divided by 36, starting with the parent's own yogini.":
    "योगिनी दशा आठ योगिनियों का 36 वर्ष का चक्र है। हर अंतर्दशा, ऊपरी अवधि की लंबाई गुणा उप योगिनी के वर्ष भाग 36 होती है, और क्रम ऊपरी अवधि की अपनी योगिनी से शुरू होता है।",
  "Mangala": "मंगला", "Pingala": "पिंगला", "Dhanya": "धान्या", "Bhramari": "भ्रामरी",
  "Bhadrika": "भद्रिका", "Ulka": "उल्का", "Siddha": "सिद्धा", "Sankata": "संकटा",

  // proof drawer
  "How this was worked out": "यह कैसे निकाला गया",
  "Inputs": "आधार मान",
  "Rule": "नियम",
  "Source": "स्रोत",
  "Show how this was worked out": "देखें कि यह कैसे निकाला गया",
  "Sidereal longitude": "निरयण भोगांश",
  "Nakshatra span": "नक्षत्र का विस्तार",
  "Nakshatra number (1 to 27)": "नक्षत्र संख्या (1 से 27)",
  "Fraction of the nakshatra crossed": "नक्षत्र का पार किया हिस्सा",
  "Degrees into the nakshatra": "नक्षत्र में बीते अंश",
  "Pada span": "चरण का विस्तार",
  "Position in the nine-lord cycle": "नौ स्वामियों के चक्र में स्थान",
  "Separation from the Sun": "सूर्य से दूरी",
  "Combustion orb": "अस्त होने की सीमा",
  "Degrees in sign": "राशि में अंश",
  "Sign parity": "राशि की प्रकृति (विषम या सम)",
  "Six degree slice (1 to 5)": "छह अंश का खंड (1 से 5)",
  "Rank by degree among the seven (1 is highest)": "सातों में अंश के अनुसार क्रम (1 सबसे अधिक)",
  "Lagna sign": "लग्न राशि",
  "Houses ruled": "स्वामी भाव",
  "Contributors": "योगदानकर्ता",
  "Classical total": "शास्त्रीय योग",
  "The zodiac is divided into 27 nakshatras of 13 degrees 20 minutes each, counted from 0 degrees Aries. The sidereal longitude decides which one holds the planet.":
    "राशिचक्र 27 नक्षत्रों में बँटा है, हर एक 13 अंश 20 कला का, मेष के 0 अंश से गिना जाता है। निरयण भोगांश तय करता है कि ग्रह किस नक्षत्र में है।",
  "Each nakshatra has four padas of 3 degrees 20 minutes. The pada is how far the planet has travelled into its nakshatra.":
    "हर नक्षत्र के चार चरण होते हैं, हर एक 3 अंश 20 कला का। चरण बताता है कि ग्रह अपने नक्षत्र में कितना आगे बढ़ा है।",
  "Nakshatras take the nine Vimshottari lords in a repeating order: Ketu, Venus, Sun, Moon, Mars, Rahu, Jupiter, Saturn, Mercury.":
    "नक्षत्रों को विंशोत्तरी के नौ स्वामी दोहराते क्रम में मिलते हैं: केतु, शुक्र, सूर्य, चंद्र, मंगल, राहु, गुरु, शनि, बुध।",
  "Each sign has one ruler. Sun rules Leo and Moon rules Cancer; Mars, Mercury, Venus, Jupiter and Saturn rule two signs each.":
    "हर राशि का एक स्वामी है। सूर्य सिंह का और चंद्र कर्क का स्वामी है; मंगल, बुध, शुक्र, गुरु और शनि दो दो राशियों के स्वामी हैं।",
  "A planet is retrograde when its apparent daily motion against the zodiac is backward. The Sun and Moon never are; Rahu and Ketu are always counted retrograde.":
    "जब राशिचक्र में ग्रह की दैनिक गति उलटी दिखती है तब वह वक्री है। सूर्य और चंद्र कभी वक्री नहीं होते; राहु और केतु सदा वक्री माने जाते हैं।",
  "A planet too close to the Sun is combust and loses strength. The limit is a classical orb in degrees, narrower for some planets when retrograde.":
    "सूर्य के बहुत निकट ग्रह अस्त होकर बल खोता है। सीमा शास्त्रीय अंशों में है, कुछ ग्रहों के लिए वक्री होने पर कम।",
  "The Sun, Rahu and Ketu are not tested for combustion.": "सूर्य, राहु और केतु की अस्त स्थिति नहीं जाँची जाती।",
  "Dignity compares the planet's sign with its own, exaltation, debilitation and moolatrikona signs, then with the sign ruler's natural friendship.":
    "बल स्थिति में ग्रह की राशि को उसकी स्वराशि, उच्च, नीच और मूलत्रिकोण राशियों से मिलाया जाता है, फिर राशि स्वामी से उसकी नैसर्गिक मित्रता देखी जाती है।",
  "Baladi avastha splits each sign into five slices of 6 degrees: bala, kumara, yuva, vriddha, mrita. Odd signs run in that order, even signs run in reverse.":
    "बालादि अवस्था हर राशि को 6 अंश के पाँच खंडों में बाँटती है: बाल, कुमार, युवा, वृद्ध, मृत। विषम राशियों में यही क्रम चलता है, सम राशियों में उलटा।",
  "Baladi avastha is not assigned to Rahu and Ketu.": "बालादि अवस्था राहु और केतु को नहीं दी जाती।",
  "Jaimini ranks the seven planets from Sun to Saturn by degrees travelled in their sign. The highest is the atmakaraka, then amatya, bhratri, matri, putra, gnati and the lowest is the darakaraka.":
    "जैमिनि सूर्य से शनि तक सात ग्रहों को उनकी राशि में तय किए अंशों के अनुसार क्रम देते हैं। सबसे अधिक अंश वाला आत्मकारक, फिर अमात्य, भ्रातृ, मातृ, पुत्र, ज्ञाति, और सबसे कम अंश वाला दारकारक होता है।",
  "With whole sign houses, a planet rules the houses whose signs it rules, counted from the lagna sign.":
    "समराशि भाव पद्धति में ग्रह उन भावों का स्वामी होता है जिनकी राशियों का वह स्वामी है, लग्न राशि से गिनकर।",
  "Each of the seven planets gives bindus to the signs that fall in its benefic places counted from the seven planets and the lagna. The grid is the sum of those bindus.":
    "सातों ग्रह, सात ग्रहों और लग्न से गिने अपने शुभ स्थानों में पड़ने वाली राशियों को बिंदु देते हैं। तालिका इन्हीं बिंदुओं का योग है।",

  // sources
  "Brihat Parashara Hora Shastra, Ashtakavarga chapters": "बृहत्पाराशर होराशास्त्र, अष्टकवर्ग के अध्याय",
  "Brihat Parashara Hora Shastra, Vimshottari dasha": "बृहत्पाराशर होराशास्त्र, विंशोत्तरी दशा",
  "Brihat Parashara Hora Shastra, bhava lordship": "बृहत्पाराशर होराशास्त्र, भाव स्वामित्व",
  "Brihat Parashara Hora Shastra, graha avasthas": "बृहत्पाराशर होराशास्त्र, ग्रह अवस्थाएँ",
  "Brihat Parashara Hora Shastra, graha dignities": "बृहत्पाराशर होराशास्त्र, ग्रहों की बल स्थिति",
  "Brihat Parashara Hora Shastra, rashi and nakshatra divisions": "बृहत्पाराशर होराशास्त्र, राशि और नक्षत्र विभाजन",
  "Classical combustion orbs, Brihat Parashara Hora Shastra": "अस्त की शास्त्रीय सीमाएँ, बृहत्पाराशर होराशास्त्र",
  "Ephemeris speed sign; nodes are always retrograde": "पंचांग गणना में गति का चिह्न; राहु और केतु सदा वक्री",
  "Jaimini Upadesha Sutras, chapter 1 (chara karakas)": "जैमिनि उपदेश सूत्र, अध्याय 1 (चर कारक)",
  "Yogini dasha, Brihat Parashara Hora Shastra tradition": "योगिनी दशा, बृहत्पाराशर होराशास्त्र की परंपरा",

  // states
  "This view could not be loaded": "यह दृश्य लोड नहीं हो सका",
  "The chart is fine. Try again in a moment.": "कुंडली ठीक है। थोड़ी देर में फिर कोशिश करें।",
};
