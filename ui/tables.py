"""
Reusable ranked table renderer for the Ranking Dashboard.

Provides ``render_ranked_table()`` — the core component used by every page
to display ranking DataFrames with heat-map styling, flag badges, and
optional rank-change indicators.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from persistence.rank_store import get_previous_ranks, get_ranks_at_lookback
from ui.styles import format_flag_badges, style_roc_heatmap_applymap, style_vol_heatmap


# ---------------------------------------------------------------------------
# Column display-name mapping
# ---------------------------------------------------------------------------

_DISPLAY_NAMES: dict[str, str] = {
    "rank": "Rank",
    "tv_symbol": "Ticker",
    "sector": "Sector",
    "1D": "1D Chg",
    "15D": "15D Chg",
    "30D": "30D Chg",
    "90D": "90D Chg",
    "250D": "250D Chg",
    "atr_pct": "VOL",
    "flags": "Flag",
    "rank_chg": "Chg",
    "rank_1w": "1W",
    "rank_4w": "4W",
}

# Columns hidden from the display (used internally only)
_HIDDEN_COLS = {"yf_symbol", "company", "asset_class", "roc", "atr", "score",
                "current_price", "sma_100", "market_cap", "avg_volume",
                "div_yield"}

# ROC display columns (used for heat-map colouring)
_ROC_COLS = ["1D", "15D", "30D", "90D", "250D"]

# Numeric columns to round to 1 decimal place
_ROUND_COLS = _ROC_COLS + ["atr_pct"]


# ---------------------------------------------------------------------------
# Rank-change helper
# ---------------------------------------------------------------------------

def _compute_rank_change_col(
    df: pd.DataFrame,
    page_name: str,
) -> pd.Series:
    """Compute a rank-change display column as plain text.

    Compares current ranks against the most recent previous snapshot
    stored in the SQLite rank store.

    Returns a Series of plain-text strings (styled later via Styler):
      - "▲{delta}" for improved rank (lower number is better)
      - "▼{delta}" for worsened rank (higher number is worse)
      - "—" for unchanged
      - "NEW" when no prior data exists
    """
    tickers = df["yf_symbol"].tolist()
    prev_ranks = get_previous_ranks(page_name, tickers, before_date=date.today())

    changes: list[str] = []
    for _, row in df.iterrows():
        yf_sym = row["yf_symbol"]
        current_rank = row["rank"]
        prev_rank = prev_ranks.get(yf_sym)

        if prev_rank is None:
            changes.append("NEW")
        elif current_rank < prev_rank:
            delta = prev_rank - current_rank
            changes.append(f"\u25b2{delta}")
        elif current_rank > prev_rank:
            delta = current_rank - prev_rank
            changes.append(f"\u25bc{delta}")
        else:
            changes.append("\u2014")

    return pd.Series(changes, index=df.index, name="rank_chg")


def _compute_historical_rank_col(
    df: pd.DataFrame,
    page_name: str,
    n_days: int,
) -> pd.Series:
    """Compute a historical rank column showing rank from n_days ago.

    Format:
      - "▲{prev_rank}" (green) — was prev_rank, now improved (lower rank number)
      - "▼{prev_rank}" (red)   — was prev_rank, now worsened (higher rank number)
      - "—"            (grey)  — rank unchanged
      - "NEW"          (grey)  — no snapshot exists that far back

    The number shown is the previous rank, not the delta.

    Args:
        df: Ranked DataFrame (must have yf_symbol and rank columns).
        page_name: Watchlist page name for SQLite lookup.
        n_days: Calendar days back to look up (7 = 1 week, 28 = 4 weeks).

    Returns:
        Series of plain-text strings, one per row in df.
    """
    tickers = df["yf_symbol"].tolist()
    hist_ranks = get_ranks_at_lookback(
        page_name, tickers, current_date=date.today(), n_days=n_days
    )

    values: list[str] = []
    for _, row in df.iterrows():
        yf_sym = row["yf_symbol"]
        current_rank = row["rank"]
        prev_rank = hist_ranks.get(yf_sym)

        if prev_rank is None:
            values.append("NEW")
        elif current_rank < prev_rank:
            values.append(f"\u25b2{prev_rank}")
        elif current_rank > prev_rank:
            values.append(f"\u25bc{prev_rank}")
        else:
            values.append("\u2014")

    return pd.Series(values, index=df.index)


def _rank_chg_color(val: str) -> str:
    """Return CSS color for a rank-change cell value.

    Used with ``Styler.map()`` to colour the plain-text rank-change
    indicators produced by ``_compute_rank_change_col()``.
    """
    if isinstance(val, str) and val.startswith("\u25b2"):
        return "color: #00c853"
    if isinstance(val, str) and val.startswith("\u25bc"):
        return "color: #ff1744"
    return "color: #9e9e9e"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_ranked_table(
    df: pd.DataFrame,
    page_name: str,
    show_rank_change: bool = True,
    show_asset_class: bool = False,
    show_sector: bool = False,
) -> None:
    """Render a styled ranking table via ``st.dataframe()``.

    Takes a ranked DataFrame (from ``build_ranking()`` output) and applies
    heat-map styling, flag badges, and optional rank-change indicators
    before displaying it in the Streamlit app.

    Args:
        df: Ranked DataFrame with columns: rank, tv_symbol, asset_class,
            company, sector, current_price, roc, atr_pct, score, flags,
            plus display ROC columns (1D, 15D, 30D, 90D, 250D).
        page_name: Watchlist page name (used to look up previous ranks).
        show_rank_change: If True, add a "Chg" column showing rank change.
        show_asset_class: If True, show the asset_class column.
        show_sector: If True, show the Sector column.
    """
    if df.empty:
        st.info("No ranked tickers to display.")
        return

    display_df = df.copy()

    # --- Add rank-change columns ---
    if show_rank_change:
        display_df["rank_chg"] = _compute_rank_change_col(display_df, page_name)
        display_df["rank_1w"] = _compute_historical_rank_col(display_df, page_name, n_days=7)
        display_df["rank_4w"] = _compute_historical_rank_col(display_df, page_name, n_days=28)

    # --- Round numeric columns ---
    for col in _ROUND_COLS:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(
                display_df[col], errors="coerce"
            ).round(1)

    # --- Build visible column list ---
    visible_cols: list[str] = ["rank"]

    if show_rank_change and "rank_chg" in display_df.columns:
        visible_cols.append("rank_chg")
    if show_rank_change and "rank_1w" in display_df.columns:
        visible_cols.append("rank_1w")
    if show_rank_change and "rank_4w" in display_df.columns:
        visible_cols.append("rank_4w")

    visible_cols.append("tv_symbol")

    if show_asset_class and "asset_class" in display_df.columns:
        visible_cols.append("asset_class")

    if show_sector and "sector" in display_df.columns:
        visible_cols.append("sector")

    # ROC columns
    for col in _ROC_COLS:
        if col in display_df.columns:
            visible_cols.append(col)

    # Volatility
    if "atr_pct" in display_df.columns:
        visible_cols.append("atr_pct")

    # Flags
    if "flags" in display_df.columns:
        visible_cols.append("flags")

    # Filter to visible columns only
    visible_cols = [c for c in visible_cols if c in display_df.columns]
    display_df = display_df[visible_cols]

    # --- Rename columns for display ---
    rename_map = {k: v for k, v in _DISPLAY_NAMES.items() if k in display_df.columns}
    if show_asset_class and "asset_class" in display_df.columns:
        rename_map["asset_class"] = "Class"
    display_df = display_df.rename(columns=rename_map)

    # --- Apply styling ---
    roc_display_cols = [_DISPLAY_NAMES.get(c, c) for c in _ROC_COLS if c in visible_cols]
    vol_display_col = _DISPLAY_NAMES.get("atr_pct", "VOL")

    styler = display_df.style

    # ROC heat-map (per-cell green/red colouring)
    styler = style_roc_heatmap_applymap(styler, roc_display_cols)

    # Rank-change text colouring (▲ green / ▼ red / grey)
    for _chg_key in ("rank_chg", "rank_1w", "rank_4w"):
        _chg_display = _DISPLAY_NAMES.get(_chg_key, _chg_key)
        if _chg_display in display_df.columns:
            styler = styler.map(_rank_chg_color, subset=[_chg_display])

    # Volatility heat-map (orange gradient)
    if vol_display_col in display_df.columns:
        styler = style_vol_heatmap(styler, [vol_display_col])

    # Suppress the default pandas index in the display
    styler = styler.hide(axis="index")

    # Format numeric columns
    format_dict = {}
    for col in roc_display_cols:
        if col in display_df.columns:
            format_dict[col] = "{:.1f}%"
    if vol_display_col in display_df.columns:
        format_dict[vol_display_col] = "{:.1f}%"
    if format_dict:
        styler = styler.format(format_dict, na_rep="--")

    # --- Render ---
    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
        height=min(len(display_df) * 35 + 38, 1200),
        column_config={
            _DISPLAY_NAMES.get("rank_chg", "Chg"): st.column_config.Column(width="small"),
            _DISPLAY_NAMES.get("rank_1w", "1W"): st.column_config.Column(width="small"),
            _DISPLAY_NAMES.get("rank_4w", "4W"): st.column_config.Column(width="small"),
            _DISPLAY_NAMES.get("flags", "Flag"): st.column_config.Column(width="medium"),
        },
    )
