# Rank Auto-Fetch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When a user uploads a watchlist on the Rank page, automatically fetch price data for any tickers not already in session state, then render the ranked table without any manual intervention.

**Architecture:** Add a file-hash dedup guard immediately after the upload parse step in `pages/rank.py`. Missing tickers are passed to the existing `fetch_price_data()` + `fetch_metadata()` functions (with a `st.progress` bar). Results are merged into the main session state dicts. The hash is stored in `st.session_state.rank_fetched_hashes` so subsequent slider moves or re-renders skip the fetch entirely. No other files change.

**Tech Stack:** Streamlit session state, Python `hashlib` (stdlib), `engine.data_fetch.fetch_price_data`, `engine.data_fetch.fetch_metadata`

---

### Task 1: Add auto-fetch to `pages/rank.py`

**Files:**
- Modify: `pages/rank.py`

This is the only file that changes. The existing `data_fetch.py`, `app.py`, and all other files are untouched.

---

**Step 1: Add `hashlib` and data-fetch imports**

At the top of `pages/rank.py`, the current import from `engine.data_fetch` is:

```python
from engine.data_fetch import TickerMetadata
```

Change it to:

```python
import hashlib

from engine.data_fetch import fetch_metadata, fetch_price_data, TickerMetadata
```

`hashlib` is Python stdlib — no install needed.

---

**Step 2: Compute file hash immediately after the success message**

Current code after the parse block (around line 46):

```python
st.success(f"Parsed **{len(mappings)}** tickers from **{uploaded_file.name}**")
```

Add the hash computation right after that line:

```python
st.success(f"Parsed **{len(mappings)}** tickers from **{uploaded_file.name}**")

# Stable identifier for this file — used to skip re-fetch on slider moves
_file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()
if "rank_fetched_hashes" not in st.session_state:
    st.session_state.rank_fetched_hashes = set()
```

`uploaded_file.getvalue()` returns the raw bytes already read during the `content = uploaded_file.getvalue().decode(…)` call above — no extra I/O.

---

**Step 3: Replace the missing-ticker warning block with the auto-fetch block**

Find and **delete** the entire existing block that shows the info message and stopping condition (currently lines 78–96):

```python
# Separate tickers into those with data and those without
tickers_with_data: list[TickerMapping] = []
tickers_missing: list[str] = []

for m in mappings:
    if m.yf_symbol in price_data:
        tickers_with_data.append(m)
    else:
        tickers_missing.append(m.tv_symbol)

if tickers_missing:
    st.info(
        f"**{len(tickers_missing)}** ticker(s) not in current price data "
        f"(need to be fetched separately): {', '.join(tickers_missing[:20])}"
        + ("..." if len(tickers_missing) > 20 else "")
    )

if not tickers_with_data:
    st.warning("None of the uploaded tickers have price data available.")
    st.stop()
```

Replace it with:

```python
# Identify tickers whose price data is not yet in session state
missing_mappings = [m for m in mappings if m.yf_symbol not in price_data]

# Auto-fetch missing tickers (once per file per session)
if missing_mappings and _file_hash not in st.session_state.rank_fetched_hashes:
    _n = len(missing_mappings)
    _progress_bar = st.progress(0, text=f"Fetching price data for {_n} tickers…")

    def _rank_progress(current: int, total: int) -> None:
        pct = current / total if total else 1.0
        _progress_bar.progress(pct, text=f"Fetching price data… {current}/{total}")

    with st.spinner(f"Fetching price data for {_n} tickers…"):
        _new_prices = fetch_price_data(missing_mappings, progress_callback=_rank_progress)
        _new_meta = fetch_metadata(missing_mappings)

    # Merge into main session state so other pages and future re-runs benefit
    fetch_result.price_data.update(_new_prices.price_data)
    metadata_store.update(_new_meta)
    st.session_state.metadata = metadata_store

    # Mark this file as processed so slider moves don't re-trigger fetch
    st.session_state.rank_fetched_hashes.add(_file_hash)

    _progress_bar.empty()

    # Non-blocking note for any symbols that genuinely failed
    if _new_prices.failed_tickers:
        st.caption(
            f"{len(_new_prices.failed_tickers)} ticker(s) could not be fetched: "
            + ", ".join(_new_prices.failed_tickers[:20])
            + ("…" if len(_new_prices.failed_tickers) > 20 else "")
        )

# Build final list of scorable tickers (all mappings now checked against updated price_data)
tickers_with_data = [m for m in mappings if m.yf_symbol in fetch_result.price_data]

if not tickers_with_data:
    st.warning(
        "None of the uploaded tickers have price data available. "
        "They may use unsupported exchange prefixes or be delisted."
    )
    st.stop()
```

---

**Step 4: Verify the complete file reads correctly**

The final flow in `rank.py` should now read:

1. `st.file_uploader` → stop if no file
2. Parse → stop if no tickers
3. `st.success(…)` parse confirmation
4. Compute `_file_hash`, init `rank_fetched_hashes`
5. `st.slider` for lookback
6. Load `fetch_result` and `metadata_store` from session state
7. Guard: stop if `fetch_result is None`
8. Identify `missing_mappings`
9. If missing and unseen hash → fetch with progress → merge → mark hash
10. Build `tickers_with_data` from updated `price_data`
11. Guard: stop if `tickers_with_data` is empty
12. Score loop → `ranked_df` → `render_ranked_table`
13. `st.caption` summary

Confirm the slider block (step 5 above) remains **before** the session state lookups — this is the existing order in the file and must be preserved.

---

**Step 5: Manual smoke test**

1. Run `streamlit run app.py`
2. Navigate to the **Rank** page
3. Upload a TradingView file containing tickers **not** in the main watchlists (e.g. US stocks)
4. Verify: progress bar appears, fills, disappears, table renders with all tickers ranked
5. Move the lookback slider — verify: no spinner, table updates instantly
6. Re-upload the same file — verify: no spinner, table renders immediately
7. Upload a different file — verify: fresh fetch runs for the new file's missing tickers

---

**Step 6: Commit**

```bash
git add pages/rank.py
git commit -m "feat: auto-fetch price data for uploaded watchlist tickers on rank page"
```

---

## Notes

- **No test infrastructure exists** in this project (pure Streamlit dashboard). Manual smoke test in Step 5 substitutes for automated tests.
- `fetch_price_data()` already checks the Parquet disk cache before hitting any API — a file containing mostly cached tickers will fetch almost instantly.
- The `_rank_progress` closure references `_progress_bar` via Python closure capture — this is intentional and works correctly with Streamlit's execution model.
- The `_` prefix on local variables (`_file_hash`, `_n`, `_new_prices`, etc.) avoids polluting the module-level namespace in the Streamlit re-run model.
