"""
Data Status Page — Data Health Detail.

Shows detailed information about the data pipeline health including
summary metrics, failed/partial tickers, watchlist summaries, and cache status.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import config


# ---------------------------------------------------------------------------
# 1. Summary metrics
# ---------------------------------------------------------------------------

data_status: dict | None = st.session_state.get("data_status")

if data_status is None:
    st.info("Data pipeline has not completed yet. Please wait for data to load.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Tickers", data_status.get("total_tickers", 0))
with col2:
    st.metric("Successfully Fetched", data_status.get("fetched_ok", 0))
with col3:
    st.metric("Failed", data_status.get("failed_count", 0))
with col4:
    st.metric("Partial History", data_status.get("partial_count", 0))

# ---------------------------------------------------------------------------
# 2. Last Refresh
# ---------------------------------------------------------------------------

st.markdown(
    f"**Last Refresh:** {data_status.get('last_refresh', 'N/A')}"
)

st.divider()

# ---------------------------------------------------------------------------
# 3. Failed Tickers
# ---------------------------------------------------------------------------

fetch_result = st.session_state.get("fetch_result")

st.subheader("Failed Tickers")

if fetch_result is not None and fetch_result.failed_tickers:
    failed_df = pd.DataFrame(
        {"Ticker": fetch_result.failed_tickers}
    )
    st.dataframe(failed_df, use_container_width=True, hide_index=True)
else:
    st.success("No failed tickers.")

# ---------------------------------------------------------------------------
# 4. Partial History Tickers
# ---------------------------------------------------------------------------

st.subheader("Partial History Tickers")

if fetch_result is not None and fetch_result.partial_tickers:
    partial_df = pd.DataFrame(
        {"Ticker": fetch_result.partial_tickers}
    )
    st.dataframe(partial_df, use_container_width=True, hide_index=True)
else:
    st.success("No tickers with partial history.")

st.divider()

# ---------------------------------------------------------------------------
# 5. Data Sources
# ---------------------------------------------------------------------------

st.subheader("Data Sources")

if fetch_result and hasattr(fetch_result, 'data_sources') and fetch_result.data_sources:
    source_counts = {}
    for src in fetch_result.data_sources.values():
        source_counts[src] = source_counts.get(src, 0) + 1

    # Summary metrics
    src_cols = st.columns(len(source_counts))
    for i, (src, count) in enumerate(sorted(source_counts.items())):
        label = src.replace("_", " ").title()
        src_cols[i].metric(label, count)

    # Detailed table
    with st.expander("Detailed Source per Ticker"):
        source_df = pd.DataFrame([
            {"Ticker": ticker, "Source": source}
            for ticker, source in sorted(fetch_result.data_sources.items())
        ])
        st.dataframe(source_df, use_container_width=True, hide_index=True)
else:
    st.info("Source tracking data not available.")

st.divider()

# ---------------------------------------------------------------------------
# 6. Watchlist Summary
# ---------------------------------------------------------------------------

st.subheader("Watchlist Summary")

watchlists = st.session_state.get("watchlists")

if watchlists:
    price_data = fetch_result.price_data if fetch_result is not None else {}

    summary_rows: list[dict] = []
    for page_name, (page_mappings, asset_classes) in watchlists.items():
        yf_symbols = {m.yf_symbol for m in page_mappings}
        with_data = sum(1 for sym in yf_symbols if sym in price_data)
        sections = set(asset_classes.values()) if asset_classes else set()

        summary_rows.append({
            "File": page_name,
            "Total Tickers": len(page_mappings),
            "With Data": with_data,
            "Sections": len(sections) if sections else 0,
        })

    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
else:
    st.info("No watchlists loaded.")

st.divider()

# ---------------------------------------------------------------------------
# 7. Cache Status
# ---------------------------------------------------------------------------

st.subheader("Cache Status")

cache_dir = Path(config.CACHE_DIR)
st.markdown(f"**Cache directory:** `{cache_dir.resolve()}`")

if cache_dir.is_dir():
    parquet_files = list(cache_dir.glob("*.parquet"))
    st.markdown(f"**Cached files:** {len(parquet_files)}")
else:
    st.markdown("**Cached files:** 0 (cache directory does not exist)")

st.markdown("")  # spacing

if st.button("Force Refresh All Data"):
    for key in [
        "fetch_result",
        "metadata",
        "benchmark_df",
        "rankings",
        "macro_data",
        "data_status",
    ]:
        st.session_state[key] = None
    st.rerun()
