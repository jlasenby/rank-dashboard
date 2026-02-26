"""
Explore Page -- ~240 CAD stocks with sector distribution chart.

Section A: Horizontal bar chart of top 20 sectors by ticker count.
Section B: Full ranked table with sector column visible.
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

# Find the EXPLORE ranking
explore_ranking = None
explore_page_name = None
for page_name, ranking in rankings.items():
    if "EXPLORE" in page_name:
        explore_ranking = ranking
        explore_page_name = page_name
        break

if explore_ranking is None:
    st.info("No Explore ranking data available.")
    st.stop()

ranked_df = explore_ranking.ranked_df

if ranked_df.empty:
    st.info("No ranked tickers to display.")
    st.stop()

# ---------------------------------------------------------------------------
# Section A: Sector Distribution Chart
# ---------------------------------------------------------------------------

st.subheader("Sector Distribution \u2014 Top 20 Ranked")

if "sector" in ranked_df.columns:
    # Count sectors among top 20 ranked tickers only
    top20 = ranked_df.head(20)
    sector_counts = top20["sector"].value_counts()

    if not sector_counts.empty:
        try:
            import plotly.express as px

            fig = px.bar(
                x=sector_counts.index,
                y=sector_counts.values,
                labels={"x": "Sector", "y": "Count"},
            )
            fig.update_layout(
                template="plotly_dark",
                height=400,
                margin=dict(l=10, r=10, t=10, b=80),
                showlegend=False,
                xaxis=dict(tickangle=-35),
            )
            fig.update_traces(marker_color="#1f77b4")
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.bar_chart(sector_counts)
    else:
        st.info("No sector data available for charting.")
else:
    st.info("Sector column not available in ranked data.")

# ---------------------------------------------------------------------------
# Section B: Full Ranked Table
# ---------------------------------------------------------------------------

st.markdown("---")
st.caption(f"Showing {len(ranked_df)} ranked securities")

render_ranked_table(
    df=ranked_df,
    page_name=explore_page_name,
    show_rank_change=True,
    show_asset_class=False,
    show_sector=True,
)
