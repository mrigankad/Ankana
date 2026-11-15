"""Python port of packages/lal-kitab (TS). Parity is enforced by tests/test_lal_kitab_parity.py.

Function mapping (TS -> Python): lkChart -> lk_chart, lkChartFromHouses ->
lk_chart_from_houses, planetsIn -> planets_in, lkAspects -> lk_aspects,
aspectedHouses -> aspected_houses, sleepingPlanets/Houses -> sleeping_planets/_houses,
detectRin -> detect_rin, detectMasnui -> detect_masnui, varshphal -> varshphal,
cycle35Position -> cycle35_position, yearOfLife -> year_of_life,
remedies -> remedies, matchPlanetHouseEntries -> match_planet_house_entries,
lalKitabReport -> lal_kitab_report, dataCoverage -> data_coverage.
Output keys are snake_case (see models.py); dump with model_dump(by_alias=True).
"""

from .adapter import assistant_adapter
from .chart import lk_chart, lk_chart_from_houses, planets_in
from .data import PLANET_ORDER, data_coverage
from .models import LalKitabReport, LkChart
from .remedies import clause_holds, match_planet_house_entries, remedies
from .report import lal_kitab_report
from .rules import (
    aspected_houses,
    detect_masnui,
    detect_rin,
    lk_aspects,
    sleeping_houses,
    sleeping_planets,
)
from .varshphal import VARSHPHAL_MAX_AGE, cycle35_position, varshphal, year_of_life

__all__ = [
    "PLANET_ORDER", "VARSHPHAL_MAX_AGE", "assistant_adapter", "LalKitabReport", "LkChart", "aspected_houses",
    "clause_holds", "cycle35_position", "data_coverage", "detect_masnui", "detect_rin",
    "lal_kitab_report", "lk_aspects", "lk_chart", "lk_chart_from_houses",
    "match_planet_house_entries", "planets_in", "remedies", "sleeping_houses",
    "sleeping_planets", "varshphal", "year_of_life",
]
