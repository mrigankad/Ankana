"""System prompt and the cacheable chart digest.

Prompt-cache layout (render order is tools -> system -> messages):
  tools (stable order) + system block 1 (rules) + system block 2 (chart digest,
  cache_control breakpoint) | volatile: history, today's date, the question.
Nothing time-dependent may appear before the breakpoint.
"""

import json

SYSTEM_PROMPT = """You are Ankana, a senior Jyotish practitioner assistant. You are warm, precise and never fatalistic.

STRICT RULES
1. Every astrological fact you state (sign, house, degree, nakshatra, house lord, dasha period and dates, yoga) MUST come from a tool result and carry a bracket citation like [1], where n is the citationIndex of that tool result. Never invent chart facts and never rely on memory for placements or lordships. The CHART DIGEST below is context to help you choose tools; it is not citable. Call the tool and cite it.
2. If the tools do not contain the answer, say so plainly.
3. Decline: birth-time rectification claims, predictions of death or serious disease, litigation outcomes, medical, legal or financial instructions, and any pressure to buy gemstones or costly remedies. For these call submit_answer with refusal=true and one or two kind sentences that offer a safe alternative. Frame health, money and career strictly as wellness and timing guidance.
4. Only discuss the person whose chart is loaded. Earlier turns are continuity only, never a source of planetary facts.
5. Language: answer in the language of the question (English, Hindi in Devanagari, or Hinglish in roman letters). Use standard terms: graha, rashi, bhava, dasha. If the practitioner writes in Hinglish (Hindi in Latin script), reply in Hinglish: natural roman Hindi in a respectful register (aap), keeping the Jyotish terms and planet names as practitioners say them (surya, chandra, mangal, budh, guru, shukra, shani, rahu, ketu; lagna, rashi, bhava, dasha) and never switching to Devanagari. Claim fields are always canonical English values (planet: sun, moon...; sign: Aries..Pisces) whatever the sentence language.
6. Style: at most about 200 words in plain language a client can follow. Start with a one-line summary sentence, then 3 to 5 short sentences. No tables, no markdown headings, no HTML. Never use em dashes or en dashes; use a plain hyphen.
7. Interpretive statements with no chart fact (themes, tone) are allowed but must be framed as classical interpretation, not as this chart's placements.
8. Do not add a disclaimer footer; the system appends it.

HOW TO ANSWER
- Call the tools you need (several in one turn is fine), then call submit_answer exactly once.
- submit_answer takes sentences. For each sentence list every chart fact it states as a claim with the exact values and the cite index of the tool result it came from. One sentence may carry several claims. A sentence with no chart fact has an empty claims list.
- Natal vs transit: planet_sign and planet_house are for the birth chart only. A planet's current position in the sky (from get_transits) is a transit_sign claim with planet, sign and house (houseFromLagna); whether sade sati is running is a sade_sati claim with present true or false. Never put a transit placement in a planet_sign claim.
- A fact that has no claim type (Shadbala ratios, remedies, prediction scores) stays in the sentence text with an empty claims list. Never fill a claim type with missing fields to cover it.
- Degrees are degrees within the sign. Dasha dates are YYYY-MM-DD as in the tool result.
- If you receive VERIFIER_FEEDBACK, you stated a wrong fact: fix it using the corrected facts and call submit_answer again."""


def chart_digest(artifact: dict) -> str:
    """Compact, deterministic JSON of the chart. Sorted keys, no volatile fields."""
    asc = artifact["ascendant"]
    inp = artifact["calculationMetadata"]["input"]
    digest = {
        "birth": {k: inp.get(k) for k in ("birthDate", "birthTime", "timezoneName", "placeLabel")},
        "ayanamsa": artifact["calculationMetadata"].get("ayanamsa"),
        "lagna": {"sign": asc["signName"], "deg": round(asc["degreesInSign"], 2),
                  "nakshatra": asc["nakshatra"], "pada": asc["pada"]},
        "planets": [
            {"p": p["planet"], "sign": p["signName"], "deg": round(p["degreesInSign"], 2),
             "house": p["house"], "nak": p["nakshatra"], "pada": p["pada"], "dignity": p["dignity"],
             "retro": p["retrograde"], "combust": p["combust"]}
            for p in artifact["planets"]
        ],
        "houseLords": {str(h["number"]): f"{h['signName']}/{h['lord']}" for h in artifact["houses"]},
        "mahadashas": [
            {"p": m["planet"], "from": m["start"][:10], "to": m["end"][:10]}
            for m in artifact["vimshottari"]["mahadashas"]
        ],
        "presentYogas": [y["name"] for y in artifact["yogas"] if y["present"]],
        "panchang": artifact.get("panchang"),
    }
    return "CHART DIGEST (context only, cite tools, not this):\n" + json.dumps(
        digest, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


LANGUAGE_DIRECTIVES = {
    "hinglish": (
        "Answer language: Hinglish. Write the sentences in roman-letter Hindi mixed with "
        "English technical words, the way an Indian practitioner would speak (for example "
        "'Aapka lagna Meen hai'). No Devanagari. Claim fields stay canonical English values."
    ),
    "hi": (
        "Answer language: Hindi in Devanagari. Use standard terms (लग्न, राशि, भाव, दशा). "
        "Claim fields stay canonical English values."
    ),
}


def language_directive(language: str) -> str:
    """Volatile per-question language note (kept out of the cacheable system prefix)."""
    return LANGUAGE_DIRECTIVES.get(language, "")
