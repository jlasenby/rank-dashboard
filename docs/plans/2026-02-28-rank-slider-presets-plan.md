# Rank Slider Preset Buttons Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add four preset buttons (15D, 30D, 90D, 250D) above the ROC lookback slider so users can jump to common periods with one click while keeping the full 1–365 free-form range.

**Architecture:** Replace the standalone `st.slider()` call with a session-state-backed pattern: initialise `st.session_state.rank_lookback = 90`, render four `st.button` calls in columns that write to that key, then render the slider with `key="rank_lookback"` so it reads/writes the same state. Read `lookback` from session state after the widget block.

**Tech Stack:** Streamlit 1.52 session state, `st.columns`, `st.button`, `st.slider`

---

### Task 1: Replace slider block with preset buttons + session-state slider

**Files:**
- Modify: `pages/rank.py` (lines 55–65, the "Lookback Period Slider" section)

No other files change.

---

**Step 1: Find the exact block to replace**

The current slider block in `pages/rank.py` (lines 55–65) is:

```python
# ---------------------------------------------------------------------------
# 3. Lookback Period Slider
# ---------------------------------------------------------------------------

lookback = st.slider(
    "ROC Lookback (days)",
    min_value=1,
    max_value=365,
    value=90,
    step=1,
)
```

---

**Step 2: Replace with the new block**

Replace the entire block above with:

```python
# ---------------------------------------------------------------------------
# 3. Lookback Period Slider
# ---------------------------------------------------------------------------

# Initialise session state key on first load
if "rank_lookback" not in st.session_state:
    st.session_state.rank_lookback = 90

# Preset buttons — one-shot setters for common lookback periods
st.caption("Quick select:")
_btn_cols = st.columns(4)
_presets = [(0, "15D", 15), (1, "30D", 30), (2, "90D", 90), (3, "250D", 250)]
for _col_idx, _label, _days in _presets:
    if _btn_cols[_col_idx].button(_label, key=f"preset_{_days}"):
        st.session_state.rank_lookback = _days

# Free-form slider — reads/writes the same session state key
st.slider(
    "ROC Lookback (days)",
    min_value=1,
    max_value=365,
    step=1,
    key="rank_lookback",
)

# Read final value for use in scoring below
lookback: int = st.session_state.rank_lookback
```

**Important:** The existing code below this block uses `lookback` as a plain integer — that variable name is preserved so nothing else needs to change.

---

**Step 3: Syntax check**

Run from the project root:
```bash
python -c "import ast; ast.parse(open('pages/rank.py').read()); print('OK')"
```
Expected output: `OK`

---

**Step 4: Commit**

```bash
git add pages/rank.py
git commit -m "feat: add 15D/30D/90D/250D preset buttons above rank page lookback slider"
```

---

## Notes

- `st.slider` with an explicit `key=` does **not** accept a `value=` argument — the initial value comes from session state initialisation (`st.session_state.rank_lookback = 90`). Do not add `value=90` to the slider call or Streamlit will raise a `StreamlitAPIException`.
- Each preset button has a unique `key` (`preset_15`, `preset_30`, etc.) to avoid Streamlit duplicate-key warnings.
- The `st.caption("Quick select:")` label sits flush above the buttons. It can be removed if the layout feels cluttered after visual inspection — but keep it for the first pass.
- No automated test infrastructure exists; the syntax check in Step 3 substitutes.
