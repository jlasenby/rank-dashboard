# Design: Auto-Fetch on Rank Page Upload

**Date:** 2026-02-28
**Status:** Approved

---

## Problem

When a user uploads a watchlist on the Rank page that contains tickers outside the main pipeline watchlists (e.g. US growth stocks), the page shows a warning and renders nothing:

```
114 ticker(s) not in current price data (need to be fetched separately): MSFT, PLTR, …
None of the uploaded tickers have price data available.
```

The user has to do nothing — price data should be fetched automatically.

---

## Approach: File-Hash Dedup Guard (Approach B)

Detect missing tickers on file upload, fetch them via the existing `fetch_price_data()` + `fetch_metadata()` pipeline, and merge results into the main session state. A file-hash guard prevents re-fetching on slider moves or other re-runs.

**Files changed:** `pages/rank.py` only.

---

## Flow

```
Upload file
    │
    ▼
Parse tickers (unchanged)
    │
    ▼
Compute MD5 hash of file bytes
    │
    ▼
missing = tickers not in session_state.fetch_result.price_data
    │
    ├─ No missing ──────────────────────────────────────────▶ Score & Render
    │
    ▼ Yes missing
Hash in session_state.rank_fetched_hashes?
    │
    ├─ Yes (same file, already fetched this session) ──────▶ Score & Render
    │
    ▼ No (new file)
st.spinner("Fetching price data for N tickers…")
    │
    ├─ fetch_price_data(missing_mappings, progress_callback=…)
    ├─ fetch_metadata(missing_mappings)
    │
    ▼
Merge → session_state.fetch_result.price_data
Merge → session_state.metadata
Add hash → session_state.rank_fetched_hashes
    │
    ▼
Score & Render (all tickers now have data)
```

---

## Session State

| Key | Type | Purpose |
|-----|------|---------|
| `rank_fetched_hashes` | `set[str]` | MD5 hashes of files already processed this session |

`fetch_result.price_data` and `metadata` are mutated in-place — no new top-level session keys needed.

---

## UI During Fetch

- `st.spinner("Fetching price data for {N} tickers…")` wraps both fetch calls
- `st.progress()` bar driven by `progress_callback` passed to `fetch_price_data()`
- Page re-renders automatically after fetch completes
- If some tickers still fail: `st.caption("X tickers could not be fetched: …")` below table — no blocking warning

---

## Edge Cases

| Case | Behaviour |
|------|-----------|
| Same file uploaded again | Hash match → skip fetch, render immediately |
| Slider moved after fetch | Hash match → skip fetch, render immediately |
| Partial fetch failure | Failed tickers listed in caption; rest renders normally |
| `fetch_result is None` (pipeline not loaded) | Existing guard unchanged |
| Mix of known + unknown tickers | Only unknown tickers fetched |

---

## Out of Scope

- No changes to `data_fetch.py`, `app.py`, or any other file
- No new disk persistence — uploaded file data lives in session state (same as main watchlist data)
- No retry UI — `fetch_price_data()` already retries internally (3 attempts with backoff)
