"""
Core Page -- CORE_MASTER watchlist organized by asset class sections.

Displays five vertically stacked tables (EQ_BETA, EQ_SECTORS, CRB, CRYPTO, FI),
each filtered from the CORE_MASTER ranked DataFrame by asset_class column.
Excluded tickers are shown in a collapsed expander at the bottom.
"""

from __future__ import annotations

import streamlit as st

from ui.tables import render_ranked_table


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SECTION_ORDER: list[str] = ["EQ_BETA", "EQ_SECTORS", "CRB", "CRYPTO", "FI"]


# ===================================================================
# Page render
# ===================================================================

rankings: dict | None = st.session_state.get("rankings")

if rankings is None:
    st.warning("Rankings have not been computed yet. Please wait for the data pipeline to complete.")
    st.stop()

# Find the CORE_MASTER ranking
core_ranking = None
core_page_name = None
for page_name, ranking in rankings.items():
    if "CORE_MASTER" in page_name:
        core_ranking = ranking
        core_page_name = page_name
        break

if core_ranking is None:
    st.info("No CORE_MASTER ranking data available.")
    st.stop()

# ---------------------------------------------------------------------------
# Render one section table per asset class
# ---------------------------------------------------------------------------

for section in _SECTION_ORDER:
    st.subheader(section)

    section_df = core_ranking.ranked_df[
        core_ranking.ranked_df["asset_class"] == section
    ].copy()

    if section_df.empty:
        st.info("No ranked tickers in this section")
        continue

    # Re-rank within section (independent per-section ranking)
    section_df = section_df.sort_values("score", ascending=False).reset_index(drop=True)
    section_df["rank"] = range(1, len(section_df) + 1)

    render_ranked_table(
        df=section_df,
        page_name=f"{core_page_name}_{section}",
        show_rank_change=True,
        show_asset_class=False,
        show_sector=False,
    )

# ---------------------------------------------------------------------------
# Excluded tickers
# ---------------------------------------------------------------------------

if not core_ranking.excluded_df.empty:
    with st.expander(f"Excluded Tickers ({len(core_ranking.excluded_df)})"):
        display_cols = ["tv_symbol", "asset_class", "reason", "flags"]
        available_cols = [c for c in display_cols if c in core_ranking.excluded_df.columns]
        st.dataframe(core_ranking.excluded_df[available_cols])
