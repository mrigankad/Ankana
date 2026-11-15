---
title: Lal Kitab notes
order: 5
summary: How the Lal Kitab module reads a chart, what it leaves out, and what is still under review.
---

The module follows the 1952 Goswami edition. Rules are paraphrased, not quoted. Each row in `packages/lal-kitab/data` carries its volume and page citation, with a `needs_review` flag where the page has not been checked against the scan.

## What it does

- The lagna is house 1 by default. An Aries-as-house-1 option exists.
- Planet-in-house entries are complete: 108 of them, nine planets in twelve houses, each with a citation.
- It handles dormant planets and houses, aspects, rin (debts), masnui planets, varshphal and the 35-year cycle.
- Remedies are ranked and offered one at a time, as the book prescribes.

## What it leaves out

Remedies that harm people or animals, and remedies built around liquor, piercing or medicine doses, are deliberately excluded. Each affected row records the reason in its `note` field.

## Status

Expert review is in progress. Most entries carry `needs_review`, and the citations for Moon, Mars, Mercury and Jupiter reuse placeholder page numbers that may be a few pages off. Venus to Ketu citations were taken from the running page headers. Treat the page numbers as pointers to check, not as final.

The Python port loads the same data files, so the rule tables have one source of truth. See `packages/lal-kitab/README.md` for current data status.
