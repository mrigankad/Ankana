# Engine accuracy: astronomy-engine vs Swiss Ephemeris

Workstream 2a. Provisional truth is Swiss Ephemeris 2.10.03 (pyswisseph, `.se1` files)
with the planned JHora defaults: Lahiri, mean node, Hindu sunrise, whole-sign houses,
Vimshottari from the Moon. Cases are marked `swisseph-provisional`; replace them with
JHora exports (same files in `services/api-py/tests/reference/cases/`) when available.
Numbers below are signed (astronomy provider minus reference) and reproducible with:

```
cd services/api-py
python scripts/report_deviations.py --markdown ../../docs/engine-accuracy-tables.md
```

## Result

Against the proposed tolerances (planets 5", Moon 10", asc 10", ayanamsa 1", dasha dates
exact) the current astronomy provider passes **0 of 12** cases. Swiss passes 12 of 12
(by construction, until JHora exports replace the truth).

Where the error comes from:

1. **Ayanamsa: constant -14.5" anchor error** (formula anchored at 23.85306 deg at J2000
   versus Swiss Lahiri), plus it ignores nutation. The planet longitudes are apparent
   (true equinox, nutation included), so the missing nutation term (+-17", 18.6 year
   cycle) makes sidereal positions wobble: -30" to +3" total in these cases. This one term
   explains the Moon, every other planet, the ascendant, and the dasha drift.
2. **Planets themselves are fine**: tropical Moon within 0.4" typical (5.6" worst, 2040).
3. **Mean node** differs by a constant 14.6" sidereal (same anchor error; node itself
   lacks nutation, which cancels in the sidereal value).
4. **Ascendant**: tracks the ayanamsa error (mean obliquity vs true adds up to ~2").
5. **Sunrise**: astronomy-engine is correct for the standard rule (2 s typical, 5 s worst
   against Swiss standard) but the Hindu rule (disc centre, no refraction) is 3.4 to 10 min
   later. Using the standard rule for a Hindu-convention panchang shifts vara-sensitive
   births and muhurta windows.
6. **Vimshottari**: first mahadasha start drifts up to 3.7 days because the Moon's
   sidereal error shifts the nakshatra balance (1" of Moon ~ 0.05 day).

Provider `astronomy` vs Swiss Ephemeris reference (arcsec unless noted, signed provider minus reference).

| Case | Moon tropical | Ayanamsa | Moon sidereal | Asc | Mean node | Worst other planet | Sunrise std-vs-std (s) | Sunrise vs Hindu (s) | Dasha start drift first / worst (days) |
|---|---|---|---|---|---|---|---|---|---|
| ananya-sharma | 0.89 | -25.82 | 26.71 | 26.56 | 14.62 | 31.60 | -1.8 | -221.0 | -1.42 / -1.42 |
| bengaluru-2040 | 5.60 | 0.34 | 5.26 | -2.01 | 14.69 | 2.92 | -1.6 | -207.1 | -0.24 / -0.24 |
| chennai-2010-dawn | -1.02 | -30.11 | 29.08 | 29.06 | 14.65 | 30.78 | -1.8 | -212.8 | -1.33 / -1.33 |
| delhi-1984 | 0.38 | 1.07 | -0.69 | -4.39 | 14.60 | 4.03 | -1.9 | -236.8 | 0.05 / 0.05 |
| london-dst-1962 | 0.94 | -1.94 | 2.88 | 0.67 | 14.53 | 3.78 | -3.4 | -412.8 | -0.37 / -0.37 |
| losangeles-1999 | 0.45 | -0.58 | 1.03 | 0.30 | 14.63 | 4.59 | -2.2 | -273.9 | -0.14 / -0.14 |
| moon-nakshatra-boundary | -0.05 | 2.82 | -2.87 | -2.06 | 14.63 | 7.87 | -2.0 | -237.7 | 0.22 / 0.22 |
| mumbai-1947 | 0.47 | -1.45 | 1.92 | -1.26 | 14.51 | 2.52 | -1.8 | -218.4 | -0.28 / -0.28 |
| nairobi-1971 | 0.07 | -25.54 | 25.61 | 24.06 | 14.56 | 28.09 | -1.7 | -201.6 | -1.17 / -1.17 |
| newyork-2003 | 1.69 | -0.36 | 2.05 | 0.51 | 14.64 | 9.56 | -2.3 | -295.7 | -0.11 / -0.11 |
| sydney-1988 | 0.94 | -21.13 | 22.06 | 13.36 | 14.60 | 26.13 | -2.3 | -275.9 | -2.69 / -2.69 |
| tromso-1975 | 1.19 | -29.14 | 30.33 | 27.88 | 14.57 | 33.11 | -4.7 | -597.5 | -3.69 / -3.69 |

| Field | Mean abs | Max abs |
|---|---|---|
| Moon tropical (arcsec) | 1.14 | 5.60 |
| Ayanamsa (arcsec) | 11.69 | 30.11 |
| Moon sidereal (arcsec) | 12.54 | 30.33 |
| Ascendant (arcsec) | 11.01 | 29.06 |
| Mean node (arcsec) | 14.60 | 14.69 |
| Worst other planet (arcsec) | 15.41 | 33.11 |
| Sunrise standard rule (s) | 2.30 | 4.73 |
| Sunrise vs Hindu rule (s) | 282.59 | 597.49 |
| Vimshottari first start (days) | 0.98 | 3.69 |
| Vimshottari worst start (days) | 0.98 | 3.69 |

Reading the table: "Sunrise std-vs-std" isolates engine error; "Sunrise vs Hindu" is the
convention gap the astronomy provider cannot close. The nutation-driven spread is visible
in the Ayanamsa column: 1995, 2010, 1971, 1975, 1988 cases are -21" to -30", others
within +-3".

## Provider settings used

- Ayanamsa: Swiss default (nutation included, consistent with apparent planets). Setting
  `ANKANA_AYANAMSA_MEAN=1` gives the classical mean value; only for comparison.
- Swiss data files `sepl/semo/seas_18.se1` (1800-2399). Without them the provider falls
  back to Moshier (not used for references).
- Raman, KP and True Chitra are available on the Swiss provider only.

## Open decisions

1. Confirm JHora's ayanamsa convention (nutation included vs mean) and node default from a
   real export; the provisional cases assume nutation-included Lahiri, mean node.
2. Swiss Ephemeris licence (see `services/api-py/LICENSING.md`); default stays astronomy
   until decided.
3. If astronomy stays the default: a cheap partial fix is the ayanamsa anchor (-14.5")
   plus a nutation term, which would bring most fields near tolerance, but asc/node/Hindu
   sunrise would still need new code.
