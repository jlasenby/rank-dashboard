"""
Alpha Grid Page — Top 40% Relative Strength across all watchlists.

Aggregates ranked tickers from every watchlist page, deduplicates by
yf_symbol (keeping the highest-scored occurrence), takes the top 40%,
and displays the result in a full ranked table.
"""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

import config
from ui.tables import render_ranked_table


# ---------------------------------------------------------------------------
# Alpha Grid aggregation logic
# ---------------------------------------------------------------------------

def _build_alpha_grid(rankings: dict) -> tuple[pd.DataFrame, int]:
    """Aggregate top 40% performers from all watchlist rankings.

    Steps:
        1. Collect all ranked DataFrames from every watchlist page.
        2. Concatenate into a single DataFrame.
        3. Sort by score descending so the best occurrence is first.
        4. Deduplicate by yf_symbol (keep highest-scored entry).
        5. Take the top 40% (ceil of total unique count * ALPHA_GRID_PERCENTILE).
        6. Assign fresh ranks 1, 2, 3, ...

    Returns:
        Tuple of (alpha_grid DataFrame, total unique ticker count).
        Returns (empty DataFrame, 0) if no data is available.
    """
    all_rows: list[pd.DataFrame] = []

    for page_name, result in rankings.items():
        if result.ranked_df.empty:
            continue
        all_rows.append(result.ranked_df.copy())

    if not all_rows:
        return pd.DataFrame(), 0

    combined = pd.concat(all_rows, ignore_index=True)

    # Sort by score descending so drop_duplicates keeps the best occurrence
    combined = combined.sort_values("score", ascending=False)
    combined = combined.drop_duplicates(subset="yf_symbol", keep="first")

    total_unique = len(combined)
    cutoff = math.ceil(total_unique * config.ALPHA_GRID_PERCENTILE)
    alpha = combined.head(cutoff).copy()

    # Assign fresh sequential ranks
    alpha = alpha.reset_index(drop=True)
    alpha["rank"] = range(1, len(alpha) + 1)

    return alpha, total_unique


# ===================================================================
# Page render
# ===================================================================

rankings: dict | None = st.session_state.get("rankings")

if rankings is None:
    st.warning("Rankings have not been computed yet. Please wait for the data pipeline to complete.")
    st.stop()

alpha_df, total_unique = _build_alpha_grid(rankings)

if alpha_df.empty:
    st.info("No ranked tickers available to build the Alpha Grid.")
    st.stop()

# Count indicator
st.markdown(
    f"Showing **{len(alpha_df)}** of **{total_unique}** total ranked securities"
)

# Render the full ranked table
# Alpha Grid does NOT use persistence / rank-change tracking
render_ranked_table(
    df=alpha_df,
    page_name="alpha_grid",
    show_rank_change=False,
    show_asset_class=True,
)
