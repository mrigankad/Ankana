# Hindi text awaiting native-speaker review

All Hindi in Ankana is a machine-generated first draft written to the register
"formal, respectful (aap)" with standard Jyotish terms. Nothing here has been
reviewed by a native-speaker Jyotishi yet. Review in this order of risk.

| Area | Where | Notes |
| --- | --- | --- |
| Reading, life story, dasha phala prose | `services/api-py/src/nakshatra_i18n/catalog_hi.py` (`reading.*`, `lagna.*`, `planet.*`, `house.*`, `dasha.*`, `varga.*`, `panchang.*`, `ls.*`) | Sentences are assembled from fragments; check agreement and flow |
| Significations (karakas, strong/weak effects, house themes, sign and nakshatra traits, dignity phrases) | `nakshatra_i18n/significations_hi.py` | Highest reach: appears in every reading |
| Prediction rule texts and source citations | `catalog_hi.py` (`rule.*`, `src.*`, `cond.*`, `pred.*`) | Classical text names (BPHS, Phaladeepika) |
| Remedies (mantras, daan, fasting, gemstone cautions) | `catalog_hi.py` (`rem.*`, `REMEDY_DATA_HI`) | Mantra bija spellings need a pandit's check |
| Yoga names, descriptions, evidence sentences | `nakshatra_i18n/yogas_hi.py` | Evidence is pattern-translated from English detector output |
| Lal Kitab planet-house effects, themes, remedies; rin, masnui, delivery and dormant rules | `packages/lal-kitab/data/hi/*.json` (all rows `needs_review_hi: true`) | 108 rows, about 650 effects; keyed by exact English string |
| Web UI strings | `apps/web-practitioner/lib/i18n/hi.ts` | English text is the key |
| Hinglish assistant text | `services/api-py/src/ankana_ai/prompt.py`, `assistant.py`, `safety.py` | Roman Hindi footer and fallbacks |

Not translated yet: data narratives that the web app builds in TypeScript
(`lib/api/chart-views.ts` summaries), fixture text on Today and Client screens,
and screens outside Today, Clients, Client, New chart, Overview, Dashas and Lal Kitab.
