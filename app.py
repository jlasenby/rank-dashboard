"""
Relative Strength Ranking Dashboard — Main Entry Point.

Multi-page Streamlit application that:
  1. Loads all watchlist files from the Watchlists directory
  2. Fetches price data (Questrade primary, yfinance fallback)
  3. Fetches benchmark data (XIC.TO) and metadata
  4. Fetches macro data for the overview page
  5. Builds rankings per watchlist page
  6. Persists rank snapshots to SQLite
  7. Routes to the selected page via st.navigation()
"""

from __future__ import annotations

import logging
from datetime import datetime, date

import pandas as pd
import streamlit as st

import config
from engine.data_fetch import FetchResult, TickerMetadata, fetch_metadata, fetch_price_data
from engine.macro_data import fetch_macro_data, compute_macro_roc
from engine.ranking import RankingResult, build_ranking
from engine.scoring import compute_display_rocs
from engine.ticker_mapping import TickerMapping
from io_handlers.universe_loader import load_all_watchlists
from persistence.rank_store import init_db, save_snapshot
from ui.sidebar import render_sidebar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config (must be the first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="RS Ranking Dashboard",
    page_icon="\U0001f4ca",  # chart emoji
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

pages = [
    st.Page("pages/overview.py", title="Overview", icon="\U0001f4ca"),
    st.Page("pages/alpha_grid.py", title="Alpha Grid", icon="\U0001f3c6"),
    st.Page("pages/core.py", title="Core", icon="\U0001f3af"),
    st.Page("pages/explore.py", title="Explore", icon="\U0001f50d"),
    st.Page("pages/usd.py", title="USD", icon="\U0001f4b5"),
    st.Page("pages/rank.py", title="Rank", icon="\U0001f4c8"),
]

utility_pages = [
    st.Page("pages/data_status.py", title="Data Status", icon="\u2699\ufe0f"),
]

nav = st.navigation(
    {
        "Dashboard": pages,
        "Utilities": utility_pages,
    }
)

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------

_SESSION_DEFAULTS: dict[str, object] = {
    "watchlists": None,          # per-file watchlist data
    "all_mappings": None,        # merged deduplicated ticker list
    "fetch_result": None,        # FetchResult from data_fetch
    "metadata": None,            # dict of TickerMetadata
    "benchmark_df": None,        # XIC.TO DataFrame
    "rankings": None,            # dict of page_name -> RankingResult
    "macro_data": None,          # macro DataFrame
    "data_status": None,         # status dict for sidebar indicator
}

for key, default in _SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# Data loading pipeline (runs once per session, cached in session_state)
# ---------------------------------------------------------------------------

def _run_data_pipeline() -> None:
    """Execute the full data loading and ranking pipeline.

    Each step is guarded by a session-state check so re-runs of the
    Streamlit script skip already-completed work.
    """
    # Step 0: Initialise rank-history database
    try:
        init_db()
    except Exception as e:
        logger.error("Failed to initialise rank store: %s", e)

    # Step 1: Load watchlists
    if st.session_state.watchlists is None:
        with st.spinner("Loading watchlists..."):
            try:
                per_file, all_mappings = load_all_watchlists()
                st.session_state.watchlists = per_file
                st.session_state.all_mappings = all_mappings
            except FileNotFoundError as e:
                st.error(f"Watchlist error: {e}")
                return

    all_mappings: list[TickerMapping] = st.session_state.all_mappings
    if not all_mappings:
        st.warning("No tickers loaded. Check the Watchlists directory.")
        return

    # Step 2: Fetch price data
    if st.session_state.fetch_result is None:
        progress_bar = st.progress(0, text="Fetching price data...")

        def _price_progress(current: int, total: int) -> None:
            if total > 0:
                progress_bar.progress(
                    current / total,
                    text=f"Fetching price data... ({current}/{total})",
                )

        fetch_result = fetch_price_data(
            all_mappings, progress_callback=_price_progress,
        )
        st.session_state.fetch_result = fetch_result
        progress_bar.empty()

    fetch_result: FetchResult = st.session_state.fetch_result

    # Step 3: Fetch benchmark data (XIC.TO)
    if st.session_state.benchmark_df is None:
        with st.spinner("Fetching benchmark data (XIC.TO)..."):
            benchmark_mapping = TickerMapping(
                tv_symbol=config.BENCHMARK_TV_SYMBOL,
                yf_symbol=config.BENCHMARK_SYMBOL,
                exchange="TSX",
                bare_ticker="XIC",
            )
            bench_result = fetch_price_data([benchmark_mapping])
            st.session_state.benchmark_df = bench_result.price_data.get(
                config.BENCHMARK_SYMBOL, pd.DataFrame()
            )

    # Step 4: Fetch metadata
    if st.session_state.metadata is None:
        progress_bar = st.progress(0, text="Fetching metadata...")

        def _meta_progress(current: int, total: int) -> None:
            if total > 0:
                progress_bar.progress(
                    current / total,
                    text=f"Fetching metadata... ({current}/{total})",
                )

        metadata = fetch_metadata(
            all_mappings, progress_callback=_meta_progress,
        )
        st.session_state.metadata = metadata
        progress_bar.empty()

    # Step 5: Fetch macro data
    if st.session_state.macro_data is None:
        with st.spinner("Fetching macro data..."):
            try:
                raw_macro = fetch_macro_data()
                macro_df = compute_macro_roc(raw_macro)
                st.session_state.macro_data = macro_df
            except Exception as e:
                logger.error("Macro data fetch failed: %s", e)
                st.session_state.macro_data = pd.DataFrame()

    # Step 6: Build rankings per watchlist page
    if st.session_state.rankings is None:
        with st.spinner("Building rankings..."):
            rankings: dict[str, RankingResult] = {}
            watchlists = st.session_state.watchlists
            metadata: dict[str, TickerMetadata] = st.session_state.metadata
            benchmark_df = st.session_state.benchmark_df

            for page_name, (page_mappings, asset_classes) in watchlists.items():
                # Filter price data to only this page's tickers
                page_yf_symbols = {m.yf_symbol for m in page_mappings}
                page_price_data = {
                    sym: df
                    for sym, df in fetch_result.price_data.items()
                    if sym in page_yf_symbols
                }

                page_failed = [
                    t for t in fetch_result.failed_tickers
                    if t in page_yf_symbols
                ]

                ranking_result = build_ranking(
                    price_data=page_price_data,
                    benchmark_df=benchmark_df,
                    metadata=metadata,
                    mappings=page_mappings,
                    failed_tickers=page_failed,
                )

                # Augment ranked_df with display ROC columns
                if not ranking_result.ranked_df.empty:
                    roc_rows: list[dict[str, float | None]] = []
                    for _, row in ranking_result.ranked_df.iterrows():
                        yf_sym = row["yf_symbol"]
                        price_df = fetch_result.price_data.get(yf_sym)
                        if price_df is not None:
                            roc_rows.append(compute_display_rocs(price_df))
                        else:
                            roc_rows.append(
                                {f"{p}D": None for p in config.DISPLAY_ROC_PERIODS}
                            )
                    roc_df = pd.DataFrame(roc_rows, index=ranking_result.ranked_df.index)
                    ranking_result.ranked_df = pd.concat(
                        [ranking_result.ranked_df, roc_df], axis=1,
                    )

                rankings[page_name] = ranking_result

            st.session_state.rankings = rankings

        # Step 7: Save rank snapshots to SQLite
        for page_name, ranking in st.session_state.rankings.items():
            if ranking.ranked_df.empty:
                continue
            snapshot_rows = []
            for _, row in ranking.ranked_df.iterrows():
                snapshot_rows.append({
                    "ticker": row.get("yf_symbol", ""),
                    "tv_symbol": row.get("tv_symbol"),
                    "asset_class": row.get("asset_class"),
                    "rank": row.get("rank"),
                    "score": row.get("score"),
                    "roc_90": row.get("roc"),
                    "atr_pct": row.get("atr_pct"),
                    "current_price": row.get("current_price"),
                    "flags": row.get("flags"),
                })
            try:
                save_snapshot(date.today(), page_name, snapshot_rows)
            except Exception as e:
                logger.error(
                    "Failed to save rank snapshot for '%s': %s", page_name, e,
                )

        # Step 7b: Save per-section snapshots for Core pages so rank history
        # comparisons use section-local ranks (not the global full-page rank).
        for page_name, ranking in st.session_state.rankings.items():
            if "CORE_MASTER" not in page_name or ranking.ranked_df.empty:
                continue
            for section_name in ranking.ranked_df["asset_class"].dropna().unique():
                sec_df = (
                    ranking.ranked_df[
                        ranking.ranked_df["asset_class"] == section_name
                    ]
                    .copy()
                    .sort_values("score", ascending=False)
                    .reset_index(drop=True)
                )
                sec_df["rank"] = range(1, len(sec_df) + 1)
                section_snapshot_rows = [
                    {
                        "ticker": row.get("yf_symbol", ""),
                        "tv_symbol": row.get("tv_symbol"),
                        "asset_class": row.get("asset_class"),
                        "rank": row.get("rank"),
                        "score": row.get("score"),
                        "roc_90": row.get("roc"),
                        "atr_pct": row.get("atr_pct"),
                        "current_price": row.get("current_price"),
                        "flags": row.get("flags"),
                    }
                    for _, row in sec_df.iterrows()
                ]
                try:
                    save_snapshot(
                        date.today(),
                        f"{page_name}_{section_name}",
                        section_snapshot_rows,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to save section snapshot for '%s_%s': %s",
                        page_name, section_name, e,
                    )

    # Step 8: Build data-status dict for sidebar
    if st.session_state.data_status is None:
        total = len(all_mappings)
        failed = len(fetch_result.failed_tickers)
        partial = len(fetch_result.partial_tickers)
        fetched_ok = len(fetch_result.price_data) - partial

        st.session_state.data_status = {
            "total_tickers": total,
            "fetched_ok": max(fetched_ok, 0),
            "failed_count": failed,
            "partial_count": partial,
            "last_refresh": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


# ---------------------------------------------------------------------------
# Run pipeline and render
# ---------------------------------------------------------------------------

_run_data_pipeline()

# Sidebar: data status (page navigation is handled by st.navigation)
render_sidebar(st.session_state.data_status)

# Run the selected page
nav.run()
