# Design: Rank Page Slider Preset Buttons

**Date:** 2026-02-28
**Status:** Approved

---

## Problem

The Rank page slider allows any lookback from 1–365 days, but the most useful values (15, 30, 90, 250) require precise dragging to hit. Users want quick access to these common periods while keeping the full free-form range.

---

## Solution: Preset Buttons Above Slider (Approach A)

Four pill buttons (`15D`, `30D`, `90D`, `250D`) sit above the slider. Clicking one jumps the slider to that value. The slider remains fully draggable for any value 1–365.

**File changed:** `pages/rank.py` only.

---

## UI Layout

```
ROC Lookback (days)
[ 15D ]  [ 30D ]  [ 90D ]  [ 250D ]
━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━
1                    90          365
```

---

## Implementation

### Session State

| Key | Type | Initial value |
|-----|------|---------------|
| `rank_lookback` | `int` | `90` |

Initialised once on first load: `if "rank_lookback" not in st.session_state: st.session_state.rank_lookback = 90`

### Preset Buttons

Four `st.button` calls inside `st.columns(4)`. Each button:
- Sets `st.session_state.rank_lookback` to its value
- Streamlit's natural re-run picks up the new value immediately

### Slider

Uses `key="rank_lookback"` — reads from and writes to the same session state key. Range stays 1–365, step 1.

### Lookback Value

`lookback = st.session_state.rank_lookback` — read after the widget block for use in scoring.

---

## Behaviour

| Action | Result |
|--------|--------|
| Click `90D` | Slider jumps to 90, table rescores |
| Drag slider to 45 | Value is 45, no button highlighted |
| Re-upload same file | Slider stays at current value |
| Page first load | Slider at 90 (existing default) |

---

## Out of Scope

- No active/highlighted state on buttons (one-shot setters only)
- No changes to scoring, fetch, or rendering logic
- No CSS tick marks on the slider track
