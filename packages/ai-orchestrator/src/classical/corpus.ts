/**
 * Curated classical / pedagogical snippets for retrieval.
 * Original Nakshatra notes inspired by traditional Jyotish themes - not
 * verbatim copyrighted source text. Used only to color interpretation;
 * placements always come from chart tools.
 */

export interface ClassicalPassage {
  id: string;
  source: string;
  title: string;
  tags: string[];
  text: string;
}

export const CLASSICAL_CORPUS: ClassicalPassage[] = [
  {
    id: "nk-house-01",
    source: "Nakshatra classical notes · houses",
    title: "1st house (Lagna / Tanu)",
    tags: ["house", "lagna", "1st", "self", "body", "temperament"],
    text: "The 1st house signifies the native's body, vitality, temperament, and overall life direction. Planets here color personality expression and how the person meets the world. The lagna lord's dignity and placement strongly condition health resilience and initiative.",
  },
  {
    id: "nk-house-02",
    source: "Nakshatra classical notes · houses",
    title: "2nd house (Dhana)",
    tags: ["house", "2nd", "wealth", "speech", "family", "food"],
    text: "The 2nd house speaks to accumulated resources, speech, family values, and early nourishment. Benefics here or a strong 2nd lord support savings tone and articulate speech; affliction can show strained family finances or harsh words.",
  },
  {
    id: "nk-house-03",
    source: "Nakshatra classical notes · houses",
    title: "3rd house (Sahaja)",
    tags: ["house", "3rd", "siblings", "courage", "effort", "skills"],
    text: "The 3rd house covers siblings, short journeys, courage, writing, and self-effort. A strong 3rd lord favors initiative and skill-building; Mars or Mercury influence often heightens drive and communication craft.",
  },
  {
    id: "nk-house-04",
    source: "Nakshatra classical notes · houses",
    title: "4th house (Sukha)",
    tags: ["house", "4th", "home", "mother", "peace", "property", "education"],
    text: "The 4th house relates to home, mother, emotional peace, vehicles, and foundational education. Comfort and belonging themes rise when the 4th lord is well placed; Moon and Venus are natural friends to this house's sukha quality.",
  },
  {
    id: "nk-house-05",
    source: "Nakshatra classical notes · houses",
    title: "5th house (Putra)",
    tags: ["house", "5th", "creativity", "children", "intellect", "romance", "speculation"],
    text: "The 5th house signifies creativity, romance, children, mantra, and intelligence applied with joy. Jupiter's gaze or occupancy classically supports learning and counsel; speculative risk themes appear when malefics dominate without support.",
  },
  {
    id: "nk-house-06",
    source: "Nakshatra classical notes · houses",
    title: "6th house (Ripu / Ari)",
    tags: ["house", "6th", "service", "debt", "health", "enemies", "routine"],
    text: "The 6th house covers service, daily discipline, debt, competition, and manageable adversity. Strength here can mean skill in problem-solving; chronic stress themes need wellness framing only, never medical diagnosis.",
  },
  {
    id: "nk-house-07",
    source: "Nakshatra classical notes · houses",
    title: "7th house (Kalatra)",
    tags: ["house", "7th", "partnership", "marriage", "contracts", "other"],
    text: "The 7th house describes partnerships, marriage, and open contracts with others. Venus and Jupiter support harmonious relating when dignified; the 7th lord's condition shows how the native meets the 'other' in life.",
  },
  {
    id: "nk-house-08",
    source: "Nakshatra classical notes · houses",
    title: "8th house (Ayur / Randhra)",
    tags: ["house", "8th", "transformation", "shared resources", "occult", "longevity"],
    text: "The 8th house relates to transformation, shared resources, research, and hidden processes. Classical texts treat longevity factors carefully; practitioners should avoid fatalistic timing claims and keep focus on change, inheritance themes, and depth work.",
  },
  {
    id: "nk-house-09",
    source: "Nakshatra classical notes · houses",
    title: "9th house (Dharma)",
    tags: ["house", "9th", "dharma", "teacher", "fortune", "travel", "faith"],
    text: "The 9th house signifies dharma, teachers, higher learning, long travel, and grace. A strong 9th lord or Jupiter influence supports mentorship and ethical orientation; this is a primary house of fortune (bhagya).",
  },
  {
    id: "nk-house-10",
    source: "Nakshatra classical notes · houses",
    title: "10th house (Karma)",
    tags: ["house", "10th", "career", "status", "karma", "public", "vocation"],
    text: "The 10th house is the peak of visible karma: vocation, status, and public contribution. The 10th lord, planets in the 10th, and dashas of career karakas (Sun, Saturn, Mercury variously) shape professional chapters.",
  },
  {
    id: "nk-house-11",
    source: "Nakshatra classical notes · houses",
    title: "11th house (Labha)",
    tags: ["house", "11th", "gains", "friends", "networks", "aspirations"],
    text: "The 11th house covers gains, networks, elder siblings, and fulfilled aspirations. Benefics or a strong 11th lord support income streams and alliances; friendship circles often mirror this house's condition.",
  },
  {
    id: "nk-house-12",
    source: "Nakshatra classical notes · houses",
    title: "12th house (Vyaya)",
    tags: ["house", "12th", "expenditure", "retreat", "foreign", "moksha", "sleep"],
    text: "The 12th house speaks to expenditure, retreat, foreign residence, sleep, and release. Classical moksha themes live here alongside practical outflows; balance charity and rest without romanticizing loss.",
  },
  {
    id: "nk-planet-sun",
    source: "Nakshatra classical notes · graha karakas",
    title: "Sun (Surya)",
    tags: ["planet", "sun", "surya", "soul", "authority", "father", "vitality"],
    text: "The Sun signifies soul purpose, vitality, authority, father figures, and recognition. Dignity in Leo or Aries and strength in the 1st/9th/10th support confidence; combustion of other planets near the Sun can mute their expression.",
  },
  {
    id: "nk-planet-moon",
    source: "Nakshatra classical notes · graha karakas",
    title: "Moon (Chandra)",
    tags: ["planet", "moon", "chandra", "mind", "mother", "emotions", "public"],
    text: "The Moon signifies mind, mother, emotional weather, and public receptivity. Waxing/waning context and nakshatra matter; a well-placed Moon supports adaptability, while affliction asks for steadier routines rather than fatal labels.",
  },
  {
    id: "nk-planet-mars",
    source: "Nakshatra classical notes · graha karakas",
    title: "Mars (Mangala)",
    tags: ["planet", "mars", "mangala", "energy", "courage", "siblings", "conflict"],
    text: "Mars signifies energy, courage, technical skill, siblings, and conflict readiness. Constructive Mars builds discipline and protection; poorly directed Mars shows impatience. Manglik discussions should stay non-alarmist and chart-specific.",
  },
  {
    id: "nk-planet-mercury",
    source: "Nakshatra classical notes · graha karakas",
    title: "Mercury (Budha)",
    tags: ["planet", "mercury", "budha", "speech", "commerce", "analysis", "learning"],
    text: "Mercury signifies speech, analysis, commerce, and adaptable learning. Association with friends (benefics) sharpens wit; with malefics it can scatter focus. Budhaditya themes arise when Mercury joins the Sun with dignity.",
  },
  {
    id: "nk-planet-jupiter",
    source: "Nakshatra classical notes · graha karakas",
    title: "Jupiter (Guru)",
    tags: ["planet", "jupiter", "guru", "wisdom", "expansion", "children", "dharma"],
    text: "Jupiter signifies wisdom, expansion, counsel, children, and dharma. As a natural benefic, its aspects uplift houses it touches. Weak Jupiter invites humility in teaching roles rather than despair.",
  },
  {
    id: "nk-planet-venus",
    source: "Nakshatra classical notes · graha karakas",
    title: "Venus (Shukra)",
    tags: ["planet", "venus", "shukra", "relationships", "arts", "comfort", "vehicles"],
    text: "Venus signifies relationships, aesthetics, comforts, and refined skill. Strong Venus supports harmony and taste; overemphasis without Saturn's balance can show indulgence. Relationship timing still requires dasha evidence from the chart.",
  },
  {
    id: "nk-planet-saturn",
    source: "Nakshatra classical notes · graha karakas",
    title: "Saturn (Shani)",
    tags: ["planet", "saturn", "shani", "discipline", "delay", "karma", "longevity", "sade sati"],
    text: "Saturn signifies discipline, time, duty, delay, and structural karma. Mature Saturn builds endurance; harsh Saturn without support asks for patience and realistic pacing. Sade sati is a transit chapter, not a sentence - pair with natal strength.",
  },
  {
    id: "nk-planet-rahu",
    source: "Nakshatra classical notes · graha karakas",
    title: "Rahu",
    tags: ["planet", "rahu", "north node", "ambition", "foreign", "innovation", "obsession"],
    text: "Rahu amplifies desire, foreign or unconventional paths, and breakthrough hunger. It is not a physical graha; interpret via sign, house, and dispositor. Avoid moral panic language; channel into skillful ambition with ethical anchors.",
  },
  {
    id: "nk-planet-ketu",
    source: "Nakshatra classical notes · graha karakas",
    title: "Ketu",
    tags: ["planet", "ketu", "south node", "detachment", "insight", "past", "moksha"],
    text: "Ketu signifies detachment, specialized insight, and release of worn patterns. House and dispositor show where the native already carries instinctive skill and where letting go supports growth. Pair with Rahu for axis balance.",
  },
  {
    id: "nk-yoga-gajakesari",
    source: "Nakshatra classical notes · yogas",
    title: "Gajakesari yoga (theme)",
    tags: ["yoga", "gajakesari", "jupiter", "moon", "reputation"],
    text: "Gajakesari arises when Jupiter occupies a kendra from the Moon. Classical reading emphasizes reputation, counsel, and steadiness of mind when both grahas are otherwise sound. Always verify presence from chart yogas tool before applying this language.",
  },
  {
    id: "nk-yoga-budhaditya",
    source: "Nakshatra classical notes · yogas",
    title: "Budhaditya yoga (theme)",
    tags: ["yoga", "budhaditya", "sun", "mercury", "intelligence"],
    text: "Budhaditya links Sun and Mercury in the same sign, traditionally coloring intelligence, articulation, and administrative skill when neither is severely damaged. Combust Mercury needs careful wording - skill may still be present with more effort.",
  },
  {
    id: "nk-yoga-pancha-mahapurusha",
    source: "Nakshatra classical notes · yogas",
    title: "Pancha Mahapurusha themes",
    tags: ["yoga", "ruchaka", "bhadra", "hamsa", "malavya", "sasa", "mahapurusha"],
    text: "Pancha Mahapurusha yogas occur when Mars, Mercury, Jupiter, Venus, or Saturn is in own/exaltation sign in a kendra. Each names a excellence pattern (valor, intellect, wisdom, refinement, endurance). Confirm with the yogas tool; do not invent which one is present.",
  },
  {
    id: "nk-yoga-kemadruma",
    source: "Nakshatra classical notes · yogas",
    title: "Kemadruma caution",
    tags: ["yoga", "dosha", "kemadruma", "moon", "isolation"],
    text: "Kemadruma describes a Moon without neighboring planetary support, classically linked to fluctuating fortunes and loneliness themes. Cancellations exist; never state Kemadruma without the yogas tool confirming present=true, and keep tone supportive.",
  },
  {
    id: "nk-dasha-principles",
    source: "Nakshatra classical notes · dasha",
    title: "Vimshottari dasha principles",
    tags: ["dasha", "vimshottari", "mahadasha", "antardasha", "timing"],
    text: "Vimshottari periods activate the karakas, houses, and yogas of the dasha lord. Mahadasha sets the long climate; antardasha colors chapters inside it. Results mature according to the lord's dignity, house ownership, and current transits - cite chart tools for the actual lords in play.",
  },
  {
    id: "nk-dasha-saturn",
    source: "Nakshatra classical notes · dasha",
    title: "Saturn mahadasha tone",
    tags: ["dasha", "saturn", "mahadasha", "discipline", "structure"],
    text: "Saturn mahadasha often emphasizes structure, accountability, and slower compounding gains. When Saturn is strong, it can be a mastery chapter; when stressed, it asks for boundary work and realistic timelines rather than fear narratives.",
  },
  {
    id: "nk-dasha-jupiter",
    source: "Nakshatra classical notes · dasha",
    title: "Jupiter mahadasha tone",
    tags: ["dasha", "jupiter", "mahadasha", "growth", "teaching"],
    text: "Jupiter mahadasha classically expands learning, guidance roles, and ethical opportunities. Overextension is the shadow; pair growth language with the chart's actual Jupiter strength and house lordships from tools.",
  },
  {
    id: "nk-dasha-rahu",
    source: "Nakshatra classical notes · dasha",
    title: "Rahu mahadasha tone",
    tags: ["dasha", "rahu", "mahadasha", "ambition", "change"],
    text: "Rahu mahadasha can accelerate unconventional paths, foreign links, or intense ambition. Ground interpretation in Rahu's sign, house, and dispositor from the birth chart - never treat Rahu periods as inherently destructive.",
  },
  {
    id: "nk-remedy-mantra",
    source: "Nakshatra classical notes · remedies",
    title: "Mantra upay (principle)",
    tags: ["remedy", "mantra", "upay", "japa"],
    text: "Mantra practice is a traditional upay for focusing devotion and steadying the mind around a graha's themes. Recommend only when the remedies tool lists it; keep counts and deities as given, and frame as optional spiritual discipline - not guaranteed outcomes.",
  },
  {
    id: "nk-remedy-daan",
    source: "Nakshatra classical notes · remedies",
    title: "Daan / charity (principle)",
    tags: ["remedy", "daan", "charity", "upay"],
    text: "Charity (daan) linked to a planet's significations is a classical softener of friction. Use only remedies the engine suggests; emphasize sincerity and proportion, never transactional 'pay to fix destiny' language.",
  },
  {
    id: "nk-remedy-gemstone",
    source: "Nakshatra classical notes · remedies",
    title: "Gemstone caution",
    tags: ["remedy", "gemstone", "ratna", "caution"],
    text: "Gemstones are the most caution-heavy upay class. Classical practice requires trial, medical/practical suitability, and clear affliction logic. Never invent a stone; only discuss stones returned by the remedies tool, including all listed cautions.",
  },
  {
    id: "nk-transit-sade-sati",
    source: "Nakshatra classical notes · transits",
    title: "Sade sati framing",
    tags: ["transit", "sade sati", "saturn", "moon"],
    text: "Sade sati is Saturn's transit across the 12th, 1st, and 2nd from the Moon - a multi-year maturity arc. Read phase and natal Moon/Saturn strength together. Avoid doom language; emphasize pacing, duty, and support systems.",
  },
  {
    id: "nk-aspects-general",
    source: "Nakshatra classical notes · aspects",
    title: "Graha aspects (drishti) overview",
    tags: ["aspect", "drishti", "conjunction", "influence"],
    text: "Planets influence houses and grahas by occupancy and classical aspect. Jupiter's special aspects, Mars, and Saturn color how support or pressure arrives. Always derive who aspects whom from computed chart data, then use this note only for interpretive tone.",
  },
  {
    id: "nk-nakshatra-principle",
    source: "Nakshatra classical notes · nakshatra",
    title: "Nakshatra and pada",
    tags: ["nakshatra", "pada", "lunar mansion", "disposition"],
    text: "Nakshatra and pada refine planetary expression beyond rashi. Moon's nakshatra especially colors mind and dasha seed. Use artifact nakshatra fields for facts; this note only reminds that pada can nuance dignity and life-style expression.",
  },
  {
    id: "nk-varga-principle",
    source: "Nakshatra classical notes · vargas",
    title: "Vargas (divisional charts)",
    tags: ["varga", "navamsa", "d9", "d10", "divisional"],
    text: "Vargas refine domains: Navamsa (D9) for relational/dharma depth, Dasamsa (D10) for vocation texture. Interpret vargas as amplifiers of D1 themes, never as a separate birth story. Cite varga data from reading or chart tools when discussing them.",
  },
  {
    id: "nk-ethics-advice",
    source: "Nakshatra classical notes · practice ethics",
    title: "Advisory ethics",
    tags: ["ethics", "advisory", "refusal", "client care"],
    text: "Jyotish counsel is advisory. Refuse death timing, disease diagnosis, litigation outcomes, and financial instructions. Prefer agency language: timing climates, strengths to cultivate, and evidence from the client's own chart tools.",
  },
];

export function classicalPassageById(
  id: string,
): ClassicalPassage | undefined {
  return CLASSICAL_CORPUS.find((p) => p.id === id);
}
