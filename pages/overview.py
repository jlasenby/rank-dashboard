"""
Overview Page — Top Ranked Assets & Macro Dashboard.

Section A (top half): 2x2 grid of summary tables showing the top-ranked
tickers from each watchlist plus the Alpha Grid top 10.

Section B (bottom half): Macro Dashboard with category-grouped tables for
FX, Bonds, Metals, Energy, and Indices.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
import streamlit as st

import config
from ui.styles import style_roc_heatmap_applymap, CATEGORY_COLORS


# ---------------------------------------------------------------------------
# Helper: Build a small summary table from a ranked DataFrame
# ---------------------------------------------------------------------------

def _summary_table(
    ranked_df: pd.DataFrame,
    top_n: int,
    show_sector: bool = False,
) -> pd.DataFrame:
    """Extract the top-N rows and format for display.

    Returns a DataFrame with columns: Rank, Ticker, 30D Chg, 90D Chg,
    250D Chg (and optionally Sector).
    """
    if ranked_df.empty:
        return pd.DataFrame()

    df = ranked_df.head(top_n).copy()

    cols: dict[str, str] = {"rank": "Rank", "tv_symbol": "Ticker"}
    if show_sector and "sector" in df.columns:
        cols["sector"] = "Sector"
    cols["30D"] = "30D Chg"
    cols["90D"] = "90D Chg"
    cols["250D"] = "250D Chg"

    available = [c for c in cols if c in df.columns]
    out = df[available].rename(columns=cols)

    # Round numeric columns
    for col in ["30D Chg", "90D Chg", "250D Chg"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(1)

    return out.reset_index(drop=True)


def _render_summary_styled(title: str, df: pd.DataFrame) -> None:
    """Display a styled summary card with heat-map colouring."""
    st.subheader(title)
    if df.empty:
        st.info("No data available.")
        return

    roc_cols = [c for c in ["30D Chg", "90D Chg", "250D Chg"] if c in df.columns]
    styler = df.style.hide(axis="index")
    styler = style_roc_heatmap_applymap(styler, roc_cols)

    fmt = {c: "{:.1f}%" for c in roc_cols if c in df.columns}
    if fmt:
        styler = styler.format(fmt, na_rep="--")

    st.dataframe(styler, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Helper: Build the Alpha Grid top-N for the overview card
# ---------------------------------------------------------------------------

def _build_alpha_grid_top(rankings: dict, top_n: int = 10) -> pd.DataFrame:
    """Aggregate top 40% from all watchlists, return first top_n rows.

    Logic mirrors the full Alpha Grid page but returns a smaller slice
    for the overview summary card.
    """
    all_rows: list[pd.DataFrame] = []
    for page_name, result in rankings.items():
        if result.ranked_df.empty:
            continue
        all_rows.append(result.ranked_df.copy())

    if not all_rows:
        return pd.DataFrame()

    combined = pd.concat(all_rows, ignore_index=True)

    # Deduplicate by yf_symbol — keep the occurrence with the best score
    combined = combined.sort_values("score", ascending=False)
    combined = combined.drop_duplicates(subset="yf_symbol", keep="first")

    total_unique = len(combined)
    cutoff = math.ceil(total_unique * config.ALPHA_GRID_PERCENTILE)
    alpha = combined.head(cutoff).copy()

    # Re-rank
    alpha = alpha.reset_index(drop=True)
    alpha["rank"] = range(1, len(alpha) + 1)

    return alpha.head(top_n)


# ---------------------------------------------------------------------------
# Helper: Render a macro category table
# ---------------------------------------------------------------------------

def _render_macro_table(category: str, cat_df: pd.DataFrame) -> None:
    """Display a single macro category table with heat-map styling."""
    color = CATEGORY_COLORS.get(category, "#555555")
    st.markdown(
        f'<h4 style="color:{color}; margin-bottom:0.3em;">{category}</h4>',
        unsafe_allow_html=True,
    )

    if cat_df.empty:
        st.info("No data.")
        return

    # Show Name + ROC columns, hide Ticker and Category
    display_cols = ["Name"]
    roc_cols = []
    for c in ["1D%", "5D%", "30D%", "90D%"]:
        if c in cat_df.columns:
            display_cols.append(c)
            roc_cols.append(c)

    display_df = cat_df[display_cols].reset_index(drop=True)

    styler = display_df.style.hide(axis="index")
    styler = style_roc_heatmap_applymap(styler, roc_cols)

    fmt = {c: "{:.2f}%" for c in roc_cols if c in display_df.columns}
    if fmt:
        styler = styler.format(fmt, na_rep="--")

    st.dataframe(styler, use_container_width=True, hide_index=True)


# ===================================================================
# Page render
# ===================================================================

st.header("Overview")

rankings: dict | None = st.session_state.get("rankings")
macro_df: pd.DataFrame | None = st.session_state.get("macro_data")
data_status: dict[str, Any] | None = st.session_state.get("data_status")

if rankings is None:
    st.warning("Rankings have not been computed yet. Please wait for the data pipeline to complete.")
    st.stop()

# -----------------------------------------------------------------------
# Section A: Top Ranked Assets (2x2 grid)
# -----------------------------------------------------------------------

st.markdown("---")
st.subheader("Top Ranked Assets")

row1_col1, row1_col2 = st.columns(2)

# 1. Core Top 5
with row1_col1:
    core_key = None
    for key in rankings:
        if key.startswith("CORE_MASTER"):
            core_key = key
            break
    if core_key and not rankings[core_key].ranked_df.empty:
        df_core = _summary_table(rankings[core_key].ranked_df, top_n=5)
        _render_summary_styled("Core Top 5", df_core)
    else:
        st.subheader("Core Top 5")
        st.info("No Core ranking data available.")

# 2. USD Top 5
with row1_col2:
    usd_key = None
    for key in rankings:
        if key.startswith("USD_LONGLIST"):
            usd_key = key
            break
    if usd_key and not rankings[usd_key].ranked_df.empty:
        df_usd = _summary_table(rankings[usd_key].ranked_df, top_n=5)
        _render_summary_styled("USD Top 5", df_usd)
    else:
        st.subheader("USD Top 5")
        st.info("No USD ranking data available.")

row2_col1, row2_col2 = st.columns(2)

# 3. Explore Top 20
with row2_col1:
    explore_key = None
    for key in rankings:
        if key.startswith("EXPLORE"):
            explore_key = key
            break
    if explore_key and not rankings[explore_key].ranked_df.empty:
        df_explore = _summary_table(
            rankings[explore_key].ranked_df, top_n=20, show_sector=True,
        )
        _render_summary_styled("Explore Top 20", df_explore)
    else:
        st.subheader("Explore Top 20")
        st.info("No Explore ranking data available.")

# 4. Alpha Grid Top 10
with row2_col2:
    df_alpha = _build_alpha_grid_top(rankings, top_n=10)
    if not df_alpha.empty:
        df_alpha_summary = _summary_table(df_alpha, top_n=10)
        _render_summary_styled("Alpha Grid Top 10", df_alpha_summary)
    else:
        st.subheader("Alpha Grid Top 10")
        st.info("No Alpha Grid data available.")


# -----------------------------------------------------------------------
# Data Status section
# -----------------------------------------------------------------------

st.markdown("---")

if data_status is not None:
    failed = data_status.get("failed_count", 0)
    partial = data_status.get("partial_count", 0)
    total = data_status.get("total_tickers", 0)
    fetched = data_status.get("fetched_ok", 0)

    if failed > 0 or partial > 0:
        st.warning(
            f"Data Status: {fetched} OK / {partial} partial / {failed} failed "
            f"out of {total} tickers. "
            f"Check the Data Status page for details."
        )
    else:
        st.success(f"Data Status: All {fetched}/{total} tickers fetched successfully.")
else:
    st.info("Data status not yet available.")


# -----------------------------------------------------------------------
# Section B: Macro Dashboard
# -----------------------------------------------------------------------

st.markdown("---")
st.subheader("Macro Dashboard")

if macro_df is None or (isinstance(macro_df, pd.DataFrame) and macro_df.empty):
    st.info("Macro data not available.")
    st.stop()

# Row 1: FX, Bonds, Metals
macro_row1_cols = st.columns(3)
categories_row1 = ["FX", "Bonds", "Metals"]

for col, cat in zip(macro_row1_cols, categories_row1):
    with col:
        cat_df = macro_df[macro_df["Category"] == cat]
        _render_macro_table(cat, cat_df)

# Row 2: Energy, Indices
macro_row2_cols = st.columns(2)
categories_row2 = ["Energy", "Indices"]

for col, cat in zip(macro_row2_cols, categories_row2):
    with col:
        cat_df = macro_df[macro_df["Category"] == cat]
        _render_macro_table(cat, cat_df)
