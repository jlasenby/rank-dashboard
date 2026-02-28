"""
Rank Page — Dynamic Momentum Ranking Dashboard.

Allows users to drag-and-drop a TradingView watchlist file and rank tickers
instantly with a configurable lookback slider. No persistence — rank changes
are NOT tracked for this page.
"""

from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

import config
from engine.data_fetch import fetch_metadata, fetch_price_data, TickerMetadata
from engine.scoring import ScoringResult, compute_scores, compute_display_rocs
from engine.ticker_mapping import parse_watchlist_with_sections, TickerMapping
from ui.tables import render_ranked_table


uploaded_file = st.file_uploader(
    "Drop a TradingView watchlist file",
    type=["txt", "csv"],
    accept_multiple_files=False,
)

if uploaded_file is None:
    st.info(
        "Upload a TradingView watchlist file (.txt or .csv) above to get started. "
        "The file should contain ticker symbols in TradingView format "
        "(e.g. TSX:RY, NASDAQ:AAPL) separated by commas or newlines."
    )
    st.stop()

# ---------------------------------------------------------------------------
# 2. Parse uploaded file
# ---------------------------------------------------------------------------

content = uploaded_file.getvalue().decode("utf-8", errors="replace")
mappings, asset_classes = parse_watchlist_with_sections(content)

if not mappings:
    st.warning("No valid ticker symbols found in the uploaded file.")
    st.stop()

st.success(f"Parsed **{len(mappings)}** tickers from **{uploaded_file.name}**")

# Stable identifier for this file — used to skip re-fetch on slider moves
_file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()
if "rank_fetched_hashes" not in st.session_state:
    st.session_state.rank_fetched_hashes = set()

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

# ---------------------------------------------------------------------------
# 4. Build ranked table
# ---------------------------------------------------------------------------

# Check that session state has price data
fetch_result = st.session_state.get("fetch_result")
metadata_store: dict[str, TickerMetadata] = st.session_state.get("metadata") or {}

if fetch_result is None or fetch_result.price_data is None:
    st.warning(
        "Price data is not yet available. Please wait for the data pipeline "
        "to finish loading on the main page."
    )
    st.stop()

price_data: dict[str, pd.DataFrame] = fetch_result.price_data

# Identify tickers whose price data is not yet in session state
missing_mappings = [m for m in mappings if m.yf_symbol not in price_data]

# Auto-fetch missing tickers (once per file per session)
if missing_mappings and _file_hash not in st.session_state.rank_fetched_hashes:
    missing_count = len(missing_mappings)
    _progress_bar = st.progress(0, text=f"Fetching price data for {missing_count} tickers…")

    def _rank_progress(current: int, total: int) -> None:
        pct = current / total if total else 1.0
        _progress_bar.progress(pct, text=f"Fetching price data… {current}/{total}")

    try:
        with st.spinner(f"Fetching price data for {missing_count} tickers…"):
            _new_prices = fetch_price_data(missing_mappings, progress_callback=_rank_progress)
            _new_meta = fetch_metadata(missing_mappings)
    finally:
        _progress_bar.empty()

    # Merge into main session state so other pages and future re-runs benefit
    # Note: .update() mutates in-place, so the local `price_data` reference
    # (assigned from fetch_result.price_data above) reflects this change too.
    fetch_result.price_data.update(_new_prices.price_data)
    metadata_store.update(_new_meta)
    st.session_state.metadata = metadata_store

    # Mark this file as processed so slider moves don't re-trigger fetch
    st.session_state.rank_fetched_hashes.add(_file_hash)

    # Non-blocking note for any symbols that genuinely failed
    if _new_prices.failed_tickers:
        _failed_list = ", ".join(_new_prices.failed_tickers[:20])
        _ellipsis = "…" if len(_new_prices.failed_tickers) > 20 else ""
        st.caption(
            f"{len(_new_prices.failed_tickers)} ticker(s) could not be fetched: {_failed_list}{_ellipsis}"
        )

# Build final list of scorable tickers (all mappings now checked against updated price_data)
tickers_with_data = [m for m in mappings if m.yf_symbol in fetch_result.price_data]

if not tickers_with_data:
    st.warning(
        "None of the uploaded tickers have price data available. "
        "They may use unsupported exchange prefixes or be delisted."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Score each ticker with the user-selected lookback
# ---------------------------------------------------------------------------

ranked_rows: list[dict] = []

for m in tickers_with_data:
    price_df = price_data[m.yf_symbol]
    scores: ScoringResult = compute_scores(
        price_df,
        roc_lookback=lookback,
        atr_period=lookback,
    )

    # Skip tickers with no computable score
    if scores.score is None:
        continue

    # Compute display ROCs (multi-timeframe)
    display_rocs = compute_display_rocs(price_df)

    # Metadata
    meta = metadata_store.get(m.yf_symbol, TickerMetadata())

    # Flags
    flags: list[str] = []
    if scores.above_sma_100 is False:
        flags.append("BELOW_SMA")
    if (
        meta.average_volume is not None
        and meta.average_volume < config.MIN_VOLUME_WARNING
    ):
        flags.append("LOW_VOL")

    row = {
        "yf_symbol": m.yf_symbol,
        "tv_symbol": m.tv_symbol,
        "asset_class": m.asset_class or asset_classes.get(m.yf_symbol),
        "company": meta.short_name,
        "sector": meta.sector,
        "roc": scores.roc,
        "atr": scores.atr,
        "atr_pct": scores.atr_pct,
        "score": scores.score,
        "current_price": scores.current_price,
        "sma_100": scores.sma_100,
        "market_cap": meta.market_cap,
        "avg_volume": meta.average_volume,
        "div_yield": meta.dividend_yield,
        "flags": ",".join(flags) if flags else "",
    }

    # Add display ROC columns
    for label, value in display_rocs.items():
        row[label] = value

    ranked_rows.append(row)

if not ranked_rows:
    st.warning(
        "No tickers could be scored with the current lookback period. "
        "This usually means insufficient price history for the selected "
        f"{lookback}-day lookback."
    )
    st.stop()

# Build DataFrame, sort by score descending, assign ranks
ranked_df = pd.DataFrame(ranked_rows)
ranked_df = ranked_df.sort_values("score", ascending=False).reset_index(drop=True)
ranked_df.insert(0, "rank", range(1, len(ranked_df) + 1))

# ---------------------------------------------------------------------------
# Render the table (no rank-change tracking for this page)
# ---------------------------------------------------------------------------

render_ranked_table(
    ranked_df,
    page_name="rank_upload",
    show_rank_change=False,
    show_sector=True,
)

st.caption(
    f"Showing {len(ranked_df)} of {len(tickers_with_data)} tickers "
    f"with data (lookback: {lookback}D). "
    f"Ranking is not persisted for uploaded files."
)
