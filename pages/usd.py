"""
USD Page -- ~212 USD ETFs in a single ranked table.

Simplest ranking page: one full-width table with rank change tracking.
Excluded tickers are shown in a collapsed expander at the bottom.
"""

from __future__ import annotations

import streamlit as st

from ui.tables import render_ranked_table


# ===================================================================
# Page render
# ===================================================================

rankings: dict | None = st.session_state.get("rankings")

if rankings is None:
    st.warning("Rankings have not been computed yet. Please wait for the data pipeline to complete.")
    st.stop()

# Find the USD ranking
usd_ranking = None
usd_page_name = None
for page_name, ranking in rankings.items():
    if "USD" in page_name:
        usd_ranking = ranking
        usd_page_name = page_name
        break

if usd_ranking is None:
    st.info("No USD ranking data available.")
    st.stop()

ranked_df = usd_ranking.ranked_df

if ranked_df.empty:
    st.info("No ranked tickers to display.")
    st.stop()

# Count indicator
st.caption(f"Showing {len(ranked_df)} ranked securities")

# Full ranked table
render_ranked_table(
    df=ranked_df,
    page_name=usd_page_name,
    show_rank_change=True,
    show_asset_class=False,
    show_sector=False,
)

# ---------------------------------------------------------------------------
# Excluded tickers
# ---------------------------------------------------------------------------

if not usd_ranking.excluded_df.empty:
    with st.expander(f"Excluded Tickers ({len(usd_ranking.excluded_df)})"):
        display_cols = ["tv_symbol", "asset_class", "reason", "flags"]
        available_cols = [c for c in display_cols if c in usd_ranking.excluded_df.columns]
        st.dataframe(usd_ranking.excluded_df[available_cols])
