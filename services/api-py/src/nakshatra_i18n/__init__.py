"""Interpretation i18n: message catalogs (en, hi) and name tables.

`Lang(code)` is the single entry point. For English every name lookup is the
identity, so English output is exactly what the engine always produced.
"""

from . import names
from . import significations_hi as _sig_hi
from .catalog_en import EN
from .catalog_hi import HI, REMEDY_DATA_HI

LANGUAGES = ("en", "hi")
CATALOGS = {"en": EN, "hi": HI}


def normalize_lang(value: str | None) -> str:
    """Map a ?lang= value or Accept-Language fragment to a supported code (default en)."""
    if not value:
        return "en"
    code = value.strip().lower().replace("_", "-").split(",")[0].split(";")[0].split("-")[0]
    return code if code in LANGUAGES else "en"


def render(lang: str, key: str, **params) -> str:
    return CATALOGS[lang][key].format(**params)


class Lang:
    def __init__(self, code: str = "en") -> None:
        self.code = normalize_lang(code)
        self.hi = self.code == "hi"

    # messages
    def t(self, key: str, **params) -> str:
        return render(self.code, key, **params)

    # names (identity in English)
    def planet(self, key: str) -> str:
        return names.PLANETS_HI.get(key, key) if self.hi else key

    def display(self, key: str) -> str:
        return names.PLANETS_HI[key] if self.hi else names.PLANET_DISPLAY_EN[key]

    def sign(self, name: str) -> str:
        return names.SIGNS_HI.get(name, name) if self.hi else name

    def nak(self, name: str) -> str:
        return names.NAKSHATRAS_HI.get(name, name) if self.hi else name

    def dignity(self, key: str) -> str:
        return names.DIGNITIES_HI.get(key, key) if self.hi else key

    def band(self, key: str) -> str:
        return names.BANDS_HI.get(key, key) if self.hi else key

    def ordinal(self, n: int) -> str:
        return (names.ORDINALS_HI if self.hi else names.ORDINALS_EN)[n]

    def level(self, key: str) -> str:
        return names.LEVELS_HI[key] if self.hi else key

    def domain(self, key: str) -> str:
        return names.DOMAINS_HI.get(key, key) if self.hi else key

    def vara(self, n: str) -> str:
        return names.VARAS_HI.get(n, n) if self.hi else n

    def tithi(self, n: str) -> str:
        return names.TITHIS_HI.get(n, n) if self.hi else n

    def paksha(self, n: str) -> str:
        return names.PAKSHA_HI.get(n, n) if self.hi else n

    def pyoga(self, n: str) -> str:
        return names.PANCHANG_YOGAS_HI.get(n, n) if self.hi else n

    def karana(self, n: str) -> str:
        return names.KARANAS_HI.get(n, n) if self.hi else n

    def planets(self, keys) -> str:
        return ", ".join(self.planet(k) for k in keys)

    # significations tables
    def tables(self):
        """(PLANET_SIGNIFICATIONS, HOUSE_THEMES, SIGN_TRAITS, NAKSHATRA_TRAITS, DIGNITY_PHRASES)"""
        if self.hi:
            s = _sig_hi
        else:
            from nakshatra_interpret import significations as s
        return (s.PLANET_SIGNIFICATIONS, s.HOUSE_THEMES, s.SIGN_TRAITS,
                s.NAKSHATRA_TRAITS, s.DIGNITY_PHRASES)


__all__ = ["LANGUAGES", "Lang", "normalize_lang", "render", "REMEDY_DATA_HI", "names"]
