"""
Macro Dashboard Data — fetches and computes ROC for macro indicators.

Covers FX pairs, bond yields, metals, energy, and global equity indices
via yfinance. Used by the Macro Overview page of the dashboard.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Macro ticker definitions by category
# ---------------------------------------------------------------------------

MACRO_TICKERS: dict[str, dict[str, str]] = {
    "FX": {
        "EURUSD=X": "EUR/USD",
        "GBPUSD=X": "GBP/USD",
        "CHFUSD=X": "CHF/USD",
        "CADUSD=X": "CAD/USD",
        "AUDUSD=X": "AUD/USD",
        "JPYUSD=X": "JPY/USD",
    },
    "Bonds": {
        "^TNX": "US 10Y Yield",
        "^IRX": "US 2Y Yield",
    },
    "Metals": {
        "GC=F": "Gold",
        "SI=F": "Silver",
        "HG=F": "Copper",
    },
    "Energy": {
        "CL=F": "Crude Oil",
        "NG=F": "Natural Gas",
    },
    "Indices": {
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ",
        "^RUT": "Russell 2000",
        "^N225": "Nikkei 225",
        "^STOXX": "STOXX 600",
        "000001.SS": "Shanghai Comp",
        "^HSI": "Hang Seng",
    },
}

# ROC periods for macro analysis (trading days)
_MACRO_ROC_PERIODS = [1, 15, 30, 90]


def _all_macro_tickers() -> list[str]:
    """Return a flat list of all macro ticker symbols."""
    tickers: list[str] = []
    for category_tickers in MACRO_TICKERS.values():
        tickers.extend(category_tickers.keys())
    return tickers


def fetch_macro_data() -> dict[str, pd.DataFrame]:
    """Fetch ~1 year of daily data for all macro tickers via yfinance.

    Returns:
        Dict mapping yfinance ticker symbol to OHLCV DataFrame.
        Tickers that fail to download are omitted from the result.
    """
    tickers = _all_macro_tickers()
    start_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    price_data: dict[str, pd.DataFrame] = {}

    logger.info("Fetching macro data for %d tickers...", len(tickers))

    try:
        df = yf.download(
            tickers=tickers,
            start=start_date,
            end=end_date,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as e:
        logger.error("Macro data download failed: %s", e)
        return price_data

    if df.empty:
        logger.warning("Macro data download returned empty DataFrame")
        return price_data

    # Handle single-ticker vs multi-ticker download
    if not isinstance(df.columns, pd.MultiIndex):
        # Single ticker case (unlikely but handle gracefully)
        if len(tickers) == 1 and "Close" in df.columns:
            ticker_df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(
                subset=["Close"]
            )
            if not ticker_df.empty:
                price_data[tickers[0]] = ticker_df
        return price_data

    # Multi-ticker: extract each ticker's DataFrame
    ticker_level = df.columns.names[1] if df.columns.names[1] else 1

    for ticker in tickers:
        try:
            level_values = df.columns.get_level_values(ticker_level)
            if ticker not in level_values.values:
                logger.debug("Macro ticker %s not found in download", ticker)
                continue

            ticker_df = df.xs(ticker, level=ticker_level, axis=1)
            cols = ["Open", "High", "Low", "Close", "Volume"]
            available = [c for c in cols if c in ticker_df.columns]
            if "Close" not in available:
                continue

            ticker_df = ticker_df[available].dropna(subset=["Close"])
            if not ticker_df.empty:
                price_data[ticker] = ticker_df
        except (KeyError, TypeError) as e:
            logger.debug("Failed to extract macro data for %s: %s", ticker, e)

    logger.info("Fetched macro data for %d / %d tickers", len(price_data), len(tickers))
    return price_data


def compute_macro_roc(price_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Compute multi-period ROC for all macro tickers.

    Args:
        price_data: Dict mapping ticker symbol to OHLCV DataFrame
                    (as returned by fetch_macro_data).

    Returns:
        DataFrame with columns: Category, Ticker, Name, 1D%, 5D%, 30D%, 90D%
        Sorted by category then ticker.
    """
    rows: list[dict] = []

    # Build reverse lookup: ticker -> (category, name)
    ticker_info: dict[str, tuple[str, str]] = {}
    for category, tickers_dict in MACRO_TICKERS.items():
        for ticker, name in tickers_dict.items():
            ticker_info[ticker] = (category, name)

    for ticker, (category, name) in ticker_info.items():
        df = price_data.get(ticker)
        if df is None or df.empty or "Close" not in df.columns:
            # Still include the row with None values for completeness
            row: dict = {
                "Category": category,
                "Ticker": ticker,
                "Name": name,
                "Price": None,
            }
            for period in _MACRO_ROC_PERIODS:
                row[f"{period}D%"] = None
            rows.append(row)
            continue

        close = df["Close"].dropna()
        n = len(close)

        row = {
            "Category": category,
            "Ticker": ticker,
            "Name": name,
            "Price": round(float(close.iloc[-1]), 4),
        }

        for period in _MACRO_ROC_PERIODS:
            if n >= period + 1:
                p_today = close.iloc[-1]
                p_past = close.iloc[-(period + 1)]
                if p_past != 0:
                    roc = float(((p_today / p_past) - 1.0) * 100.0)
                    row[f"{period}D%"] = round(roc, 2)
                else:
                    row[f"{period}D%"] = None
            else:
                row[f"{period}D%"] = None

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)

    # Define category ordering
    category_order = ["FX", "Bonds", "Metals", "Energy", "Indices"]
    result["_cat_sort"] = result["Category"].apply(
        lambda c: category_order.index(c) if c in category_order else len(category_order)
    )
    result = result.sort_values(["_cat_sort", "Ticker"]).drop(columns=["_cat_sort"])
    result = result.reset_index(drop=True)

    return result
