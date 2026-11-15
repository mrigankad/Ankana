"""Model routing policy: Haiku for simple lookups, Sonnet for synthesis,
Opus only when the caller opts in to a deep reading."""

import re
from dataclasses import dataclass

from .config import HAIKU, OPUS, SONNET

# Cues that the question needs synthesis across several chart factors.
_SYNTHESIS = re.compile(
    r"\b(why|how (?:will|would|does|do)|career|job|marriage|relationship|love|money|wealth|"
    r"finance|health|education|children|travel|abroad|timing|when will|predict|future|"
    r"compare|explain|summar|overall|life|story|chapter|report|remed|upay|advice|"
    r"should i|strength|transit|sade sati|prediction|window|reading|"
    r"kyun|kaise|kab|shaadi|naukri|bhavishya|kya hoga)\b"
    r"|कैसे|क्यों|कब|भविष्य|करियर|शादी|विवाह|नौकरी|उपाय|सारांश|जीवन",
    re.IGNORECASE,
)
# Cues that the question is a single-fact lookup.
_LOOKUP = re.compile(
    r"\b(which|what(?:'s| is)|where|kaun|kya|kahan|lagna|ascendant|rising|moon sign|"
    r"nakshatra|mahadasha|antardasha|current dasha|house (?:is|of)|lord of|placed|"
    r"degree|yoga present|which yoga)\b"
    r"|कौन|कहाँ|कहां|लग्न|नक्षत्र|महादशा|अंतर्दशा",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ModelChoice:
    tier: str  # "simple" | "synthesis" | "deep"
    model: str
    effort: str  # output_config.effort


def route(question: str, *, deep: bool = False) -> ModelChoice:
    """Pick a model. Long or multi-clause questions go to synthesis by default."""
    if deep:
        return ModelChoice("deep", OPUS, "high")
    text = question.strip()
    words = len(text.split())
    if _SYNTHESIS.search(text) or words > 28:
        return ModelChoice("synthesis", SONNET, "medium")
    if _LOOKUP.search(text):
        return ModelChoice("simple", HAIKU, "low")
    # Unknown shape: be safe on quality.
    return ModelChoice("synthesis", SONNET, "medium")
