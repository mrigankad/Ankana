# Lal Kitab rules: verification against the source book

Source: Goswami/Vashisth, Lal Kitab (1952 edition, 778 scan pages). Every page below was read from a rendered page image, not only from OCR text. Page refs are `printed / pdf` (the pdf-minus-printed offset differs per section of the scan, see below). Book prose is never copied; the data files hold paraphrases and cites.

Status words: **verified** (matches the page image), **corrected** (our data or cite was wrong and was changed), **ambiguous** (the book itself is unclear or contradicts itself; flag kept), **needs expert** (a reading decision that a Lal Kitab practitioner should settle).

## Page offsets (printed = pdf - offset)

Vol I front section 19 (pp. 42-334 of the scan); Vol II planet sections: Jupiter 16, Sun 16, Moon 14, Venus 13, Mars 11, Mercury 10, Saturn 8, Rahu 6, Ketu 4; annual-chart matrix and practical examples 3. All 108 planet-in-house rows were re-derived from the section heading pages. Wrong before: Moon (was 16, is 14), Mars (16 -> 11), Mercury (16 -> 10). Sun, Jupiter, Venus, Saturn, Rahu and Ketu were already right. A few chapter-opening pages carry no printed number; those printed numbers are inferred from the neighbouring pages.

## Rule table

| # | Rule | Status | Book page (printed / pdf) | Notes |
|---|---|---|---|---|
| 1 | Chart origin: ascendant sign is house 1, houses counted anticlockwise, signs erased | verified, cite corrected | 91 / 110; worked example 760 / 763 | Our comment said "Ch.12, p.69". It is Ch.4 "12 Fixed Houses", p.91. The `aries_h1` option is not in the book and stays an opt-in. |
| 2 | Pakka ghar (Sun 1, Jupiter 2/5/9/11, Mars 3/8, Moon 4, Ketu 6, Venus 7 and Mercury 7, Saturn 8/10, Rahu 12) | verified | 69 / 88 | Mercury 7 vs 3/6: the page lists Mercury with Venus in H7. The 3 and 6 are Mercury's debt houses (134) and its effect houses (124), not pakka ghar; flag removed. Jupiter in H12 (with Rahu) and Mercury in H6 (with Ketu) are "joint" houses (69b, 115) that we do not count as own: needs expert. |
| 3 | Aspect arrows 1>7, 4>10 (100%), 3>9/11, 5>9 (50%), 2>6, 8>2 (25%) | verified | 118 / 137 | Table matches the image. |
| 4 | 6>12 at 25% | verified (was flagged) | 119 / 138, 121 / 140, 126 / 145 | Absent from the table but present in the prose list of arrow ends, in the "6th aspects 12th, not the reverse" paragraph and in the 1-7, 4-10, 5-9, 3-9, 6-12 list. Flag removed, no longer "derived". |
| 5 | Derived 7>1 and 10>4 | ambiguous | 119 / 138, 121 / 140 | "Every house has full aspect on its 7th" conflicts with the percentages on the same page and with "prior houses aspect later ones". Flag set to true. No effect on dormancy (houses 1 and 4 are not tested by the unaspected rule). |
| 6 | 8>2 strength | ambiguous | 118 / 137 vs 121 / 140 | Table says 25%, prose says 100%. Table kept. |
| 7 | Mercury, Rahu, Ketu special aspects | ambiguous, not implemented | 119 / 138, 121 / 140 | Only qualitative: Mercury in H12 may aspect H6, Mercury in 3/9/12 "makes all planets meaningless"; Rahu-Ketu mutual aspect and H2/H9 are called "a different story" with no table. Recorded in the data note. |
| 8 | Dormant: own pakka ghar is awake | verified | 116 / 135 | |
| 9 | Dormant: 1-6 empty makes 7-12 dormant and vice versa | verified (flag removed) | 115 / 134, 116 / 135 | |
| 10 | Dormant: planet in 1-6 with empty opposite house | verified (flag removed) | 116 / 135 | Stated flatly. |
| 11 | Dormant: H10 empty makes H2 dormant; H2 empty makes H10 and H9 dormant | verified, one conflict | 117 / 136 | The book's own example (761 / 764) calls Rahu in H10 awake with H2 empty (Rahu is aspected 100% from H4); engine says dormant. See expert Q1. `h2_empty_h10` keeps its flag. |
| 12 | Dormant: unaspected planet | ambiguous | 116 / 135 | Literal reading would make planets in houses 1, 3, 4, 5, 8 dormant (no arrow ends there). We apply it to houses 7-12 only. Expert Q2. |
| 13 | Dormant houses: empty and unaspected | verified | 116 / 135 | |
| 14 | Awakening map (1 Mars, 2 Moon, 3 Mercury, 4 Moon, 5 Sun, 6 Rahu, 7 Venus, 8 Moon, 9 Jupiter, 10 Saturn, 11 Jupiter, 12 Ketu) | verified | 116 / 135 (also bold list 115 / 134) | |
| 15 | Self-awakening ages 16, 22, 24, 25, 28, 34, 36, 42, 48 and triggers | verified | 117 / 136 | Mercury's malefic-year cell is smudged (reads 35th; pattern says 36th): that one cell flagged. |
| 16 | Moon age 12 vs 24 | explained, not a data error | 74 / 93, 117 / 136, 761 / 764 | 24 is the Moon's full (unconjoined) age and is what the awakening table uses. p.74 gives 12 when the Moon is with Jupiter, Venus, Mercury or Rahu and 8 with Saturn; the book's worked example uses 12. The p.74 table is now in `dormant.json` (`effective_age`) but the engine still reports the table age. Expert Q3. |
| 17 | Rin (debts) table: 9 planets, placement houses, enemy columns, causes, symptoms | verified | 134-135 / 153-154 | All nine rows match the image. Sun's enemy cell ("Venus or Sun Rahu-Ketu") and Ketu's (trailing comma after Moon) are ambiguous and keep their flags. |
| 18 | Rin remedies | verified | 138-145 / 157-164 | Remedy sits under each planet's symptom block. Mars remedy was flagged "inferred": it is certain (p.140 under the Mars block), flag removed. |
| 19 | First-degree debt to father (planet in H9 + Mercury in listed house) | verified table, ambiguous reading | 136 / 155 | p.137 adds that a debilitated house 2/5/9/12 must be involved; we do not test that, so findings stay flagged. |
| 20 | Second-degree debt to father | transcribed, not implemented | 136 / 155 | Clean on the image except Jupiter's row (scrambled). Table now in `rin.json` (`second_degree_father`). Reading of "outside H.No." unclear: Expert Q4. |
| 21 | Malefics in 2/5/9/12 indicate father's debt | ambiguous | 132 / 151, 137 / 156 | Kept as a soft indicator. |
| 22 | Debt scope: natal chart only | verified | 137 / 156 | |
| 23 | Masnui (artificial planets), 13 combinations | verified | 68 / 87 (also 287 / 306) | All pairs match the table. All are "same house". Jupiter's row carries "in hollow condition" which the book never defines: flag set. p.478 / 489 lists "Sun + Saturn (anywhere)" as a condition for real Mars being negative, which is a separate rule from the artificial planet. Two slips in the book noted (Mars + Mercury = Mars negative on 159; Sun + Mercury = artificial Moon on 402). |
| 24 | Masnui remedy principle (remove the malefic component) | verified text; image not read for p.159 | 158 / 177 (image), 159 / 178 (OCR only) | p.159 cite left `verified_from_image: false`. |
| 25 | 35-year cycle: order and parts | verified (flags removed) | 77-78 / 96-97 | Order is stated in words on p.77 and in the table; all nine rows match. Assumption: the engine always starts the cycle with Jupiter at birth, but p.77 says it can start from another planet: Expert Q5. |
| 26 | Varshphal matrix, 100 rows | verified | 756-758 / 759-761 | Rows 1, 2, 33, 40, 44, 80, 99, 100 compared with the images; all 100 rows are permutations and column 1 repeats every 12 years as the book says. Row 1 is not the identity, so the natal chart is not a matrix row. |
| 27 | Varshphal age convention | ambiguous | 761-767, 221-222, 239 | We use completed years + 1 (the 14.09.1997 example for a native born 05.09.1962, "running 36", uses row 36). The 1902-born example (annual chart "at age 37" in 1939) reads like completed years. Expert Q6. |
| 28 | Annual chart houses as months of the Vikram year | verified | 215 / 234 | |
| 29 | Remedy delivery by house | verified | 171 / 190 | H11 has no remedy, as coded. |
| 30 | One remedy at a time, 40 or 43 days | verified | 133 / 152; 75 / 94 | "days / weeks" on 133; 40 = 28 nakshatras + 12 signs, at most 43 (p.75). |
| 31 | Friendship tables | verified transcription, ambiguous use | 761 / 764 | Chart-specific worked-example tables; flag stays. |
| 32 | Planet-in-house rows (108) | cites verified; text sampled | per planet | Only page cites and headings audited for all rows. Moon H1 was read in full against the page: one omission fixed (Saturn or Sun in H2 as well as H6). The rest of the paraphrased effects were not re-read. |

## Real-chart checks

Done in a scratchpad file, not in the repo. Result: for both a real internal test chart and the sample client chart the engine matches a literal reading of the book (test chart: 5 of 9 dormant, 3 artificial planets in H10; sample client: Ketu, Rahu, Venus dormant, first-degree father debt). The disagreement risk is in the reading questions below, not in the arithmetic. No code change was needed for either chart.

## Questions for a Lal Kitab expert

1. Does an incoming aspect rescue a planet from the "H2 empty makes H10 (and H9) dormant" rule? The book's own worked example (Rahu in H10, aspected from H4, H2 empty, called awake) suggests it might; the literal rule says dormant. This decides whether three planets in H10 with an aspect from H4 count as dormant.
2. For "an unaspected planet is dormant": which aspects count (arrow table only, or also yog-drishti 5th/9th help, joint wall, 3rd-house Mercury route)? Should the rule apply to houses 1-6 as well?
3. Should the Moon (and Sun, Mercury, Venus, Saturn) self-awakening age follow the p.74 conjunction table (Moon 12 with Mercury, etc.) rather than the single awakening-table age?
4. How should "Sun outside H.No. 1 or 11" in the second-degree debt table be read, and what is the intended Jupiter row?
5. Does the 35-year circulation always start with Jupiter at birth, or does the starting planet depend on the chart (p.77)?
6. In the annual chart, is "age N" completed years N or the Nth year of life (completed + 1)? Is there a natal-chart row (age 0)?
7. Does "every house aspects its 7th fully" (p.119) add 7>1 and 10>4 (and 9>3 etc.), and is 8>2 25% or 100%?
8. What does "hollow condition" mean for artificial Jupiter (Sun + Venus)? Does Jupiter being present in the same house cancel it?
9. Are Jupiter in H12 (with Rahu) and Mercury in H6 (with Ketu) "in their own house" for the awake rule?
10. Is "Mars + Mercury = Mars negative" (p.159) or "Sun + Mercury = artificial Moon" (p.402) a printing slip?
