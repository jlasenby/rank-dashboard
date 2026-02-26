"""
Heat-map styling and flag badge renderers for the Ranking Dashboard.

Provides pandas Styler-based colour gradients and HTML badge formatters
used by all ranking table pages.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

# ---------------------------------------------------------------------------
# Category colour constants (one per macro category)
# ---------------------------------------------------------------------------

CATEGORY_COLORS: dict[str, str] = {
    "FX": "#1565c0",       # Blue
    "Bonds": "#6a1b9a",    # Purple
    "Metals": "#f9a825",   # Gold / Amber
    "Energy": "#e65100",   # Deep orange
    "Indices": "#2e7d32",  # Green
}

# ---------------------------------------------------------------------------
# Custom colour maps
# ---------------------------------------------------------------------------

_GREEN_CMAP = LinearSegmentedColormap.from_list(
    "roc_green", ["#c8ffc8", "#00c853"]
)
_RED_CMAP = LinearSegmentedColormap.from_list(
    "roc_red", ["#ffc8c8", "#ff1744"]
)
_VOL_CMAP = LinearSegmentedColormap.from_list(
    "vol_orange", ["#fff8e1", "#e65100"]
)


# ---------------------------------------------------------------------------
# ROC heat-map (green for positive, red for negative)
# ---------------------------------------------------------------------------

def style_roc_heatmap(
    styler: pd.io.formats.style.Styler,
    columns: list[str],
) -> pd.io.formats.style.Styler:
    """Apply green/red background gradient to ROC columns.

    Positive values receive a green gradient (darker = more positive).
    Negative values receive a red gradient (darker = more negative).
    Zero or None values are left neutral (no colour).

    Args:
        styler: An existing pandas Styler object.
        columns: Column names to apply the ROC heat-map to.

    Returns:
        The Styler with heat-map applied.
    """
    df = styler.data

    for col in columns:
        if col not in df.columns:
            continue

        series = pd.to_numeric(df[col], errors="coerce")

        pos_mask = series > 0
        neg_mask = series < 0

        if pos_mask.any():
            pos_vals = series[pos_mask]
            vmin = 0.0
            vmax = pos_vals.max() if pos_vals.max() > 0 else 1.0
            styler = styler.background_gradient(
                cmap=_GREEN_CMAP,
                subset=pd.IndexSlice[pos_mask, col],
                vmin=vmin,
                vmax=vmax,
            )

        if neg_mask.any():
            neg_vals = series[neg_mask].abs()
            vmin = 0.0
            vmax = neg_vals.max() if neg_vals.max() > 0 else 1.0
            # For negative values we apply the red map on absolute values
            # We use a custom apply approach to map negative magnitude to red
            styler = styler.background_gradient(
                cmap=_RED_CMAP,
                subset=pd.IndexSlice[neg_mask, col],
                vmin=-vmax,
                vmax=0.0,
                gmap=series[neg_mask].abs(),
            )

    return styler


def _roc_colour_func(val: float | None) -> str:
    """Return a background-color CSS string for a single ROC value.

    This is used as a fallback per-cell styler when the gradient approach
    is not suitable (e.g. mixed positive/negative in small DataFrames).
    """
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""

    if val > 0:
        # Normalise to 0..1 range assuming max ~50% ROC
        intensity = min(abs(val) / 50.0, 1.0)
        r, g, b, _ = _GREEN_CMAP(intensity)
        return f"background-color: rgba({int(r*255)},{int(g*255)},{int(b*255)},0.85)"

    if val < 0:
        intensity = min(abs(val) / 50.0, 1.0)
        r, g, b, _ = _RED_CMAP(intensity)
        return f"background-color: rgba({int(r*255)},{int(g*255)},{int(b*255)},0.85)"

    return ""


def style_roc_heatmap_applymap(
    styler: pd.io.formats.style.Styler,
    columns: list[str],
) -> pd.io.formats.style.Styler:
    """Apply per-cell ROC colouring using applymap (simpler, always works).

    This is the preferred method — it handles mixed positive/negative values
    in every column without needing separate subset masks.

    Args:
        styler: An existing pandas Styler object.
        columns: Column names to apply the ROC heat-map to.

    Returns:
        The Styler with per-cell ROC colours.
    """
    valid_cols = [c for c in columns if c in styler.data.columns]
    if valid_cols:
        styler = styler.map(_roc_colour_func, subset=valid_cols)
    return styler


# ---------------------------------------------------------------------------
# Volatility heat-map (orange gradient — higher = darker)
# ---------------------------------------------------------------------------

def style_vol_heatmap(
    styler: pd.io.formats.style.Styler,
    columns: list[str],
) -> pd.io.formats.style.Styler:
    """Apply orange-gold gradient to volatility columns.

    Higher volatility values get a darker orange background.

    Args:
        styler: An existing pandas Styler object.
        columns: Column names to apply the volatility gradient to.

    Returns:
        The Styler with orange gradient applied.
    """
    for col in columns:
        if col not in styler.data.columns:
            continue

        series = pd.to_numeric(styler.data[col], errors="coerce")
        if series.notna().any():
            styler = styler.background_gradient(
                cmap=_VOL_CMAP,
                subset=[col],
                vmin=0.0,
                vmax=series.max() if series.max() > 0 else 1.0,
            )

    return styler


# ---------------------------------------------------------------------------
# Flag badges — HTML spans for flag indicators
# ---------------------------------------------------------------------------

_FLAG_STYLES: dict[str, tuple[str, str, str]] = {
    # flag_name -> (background_colour, text_colour, display_label)
    "BELOW_SMA": ("#ef5350", "#ffffff", "\u2193 SMA"),    # Red, downward arrow
    "NO_SCORE":  ("#9e9e9e", "#ffffff", "? Data"),         # Grey
    "LOW_VOL":   ("#ff9800", "#000000", "\u26a0 Vol"),     # Amber/orange, warning
}


def format_flag_badges(flags_str: str | None) -> str:
    """Convert a comma-separated flags string to styled HTML badge spans.

    Args:
        flags_str: Comma-separated flag names, e.g. "BELOW_SMA,LOW_VOL".
                   None or empty string returns empty string.

    Returns:
        HTML string with styled ``<span>`` elements for each flag.
    """
    if not flags_str or not flags_str.strip():
        return ""

    badges: list[str] = []
    for flag in flags_str.split(","):
        flag = flag.strip()
        if flag in _FLAG_STYLES:
            bg, fg, label = _FLAG_STYLES[flag]
            badges.append(
                f'<span style="background-color:{bg}; color:{fg}; '
                f'padding:2px 6px; border-radius:4px; font-size:0.75em; '
                f'margin-right:4px; white-space:nowrap;">{label}</span>'
            )

    return " ".join(badges)


def style_flag_highlight(
    styler: "pd.io.formats.style.Styler",
    col: str,
) -> "pd.io.formats.style.Styler":
    """Apply purple background to Flag cells that contain BELOW_SMA.

    Uses a semi-transparent purple so the cell is clearly flagged
    without being jarring. Other flags (LOW_VOL, NO_SCORE) receive
    no special background — they are identified by the flag text alone.

    Args:
        styler: An existing pandas Styler object.
        col: The display name of the flags column (e.g. "Flag").

    Returns:
        The Styler with purple background applied to BELOW_SMA cells.
    """
    def _below_sma_style(val: object) -> str:
        if isinstance(val, str) and "BELOW_SMA" in val:
            return "background-color: rgba(123,31,162,0.35); color: #e1bee7"
        return ""

    if col in styler.data.columns:
        styler = styler.map(_below_sma_style, subset=[col])
    return styler
