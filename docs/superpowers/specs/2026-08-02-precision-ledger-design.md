# Precision Ledger - Visual Design

_Date: 2026-08-02 · Status: approved to build_  
_Direction: Precision ledger (navy / white / black + blue shades)_

## Goal

Make Nakshatra feel like a calm, high-trust practitioner instrument - not a generic SaaS dashboard and not a cosmic marketing site.

## Principles

1. **Chart is the artifact** - on chart routes, the kundali and reading carry visual weight; chrome stays quiet.
2. **One surface language** - white panels, hairline navy borders, soft blue-50 page ground; no mixed gold/glass leftovers.
3. **Typography as hierarchy** - DM Sans for UI; slightly tighter display weight for section titles; data uses tabular figures / quieter mute.
4. **Density with air** - keep practitioner data dense, but drop competing cards, pill clusters, and double chrome.
5. **Motion sparingly** - short fades only; respect `prefers-reduced-motion`.

## Token system

| Role | Hex / token |
|------|-------------|
| Ink / midnight | `#0b1220` |
| Navy primary | `#162a6c` |
| Navy hover | `#213c8f` |
| Navy light | `#3d57a8` |
| Navy dark | `#0d1c52` |
| Page ground | `#f4f6fb` (cool blue-tint, not cream) |
| Panel | `#ffffff` |
| Soft fill | `#eef2fb` (`blue-50`) |
| Border | `rgba(22, 42, 108, 0.10)` |
| Muted text | `#64748b` |

Retire active use of `--gold*` - aliases may remain one release for safety, but selectors use navy tokens.

## Screen order

1. **Tokens + global chrome** - page ground, cards, buttons, badges
2. **Chart workspace** - header, tabs, panels, reading/predictions density
3. **Clients + intake** - same panel language as dashboard
4. **Cleanup** - remove `nk-btn-gold` / `nk-badge-gold` / `bg-gold` dead paths

## Non-goals

- FastAPI cutover, assistant port, new astrology engines
- Dark mode, purple themes, cream+serif “AI default” looks
- Full rewrite of every CSS class in one pass
