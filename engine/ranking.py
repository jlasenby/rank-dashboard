"""
Ranking Pipeline — Score -> Filter -> Rank -> Flag.

Orchestrates the full ranking process:
  1. Compute ROC/ATR%/SMA scores for all tickers
  2. Check market regime (XIC vs 200-day SMA)
  3. Apply individual 100-day SMA filter
  4. Sort passing tickers by volatility-adjusted score
  5. Assign ranks
  6. Generate per-ticker flags (BELOW_SMA, NO_SCORE, LOW_VOL)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

import config
from engine.data_fetch import TickerMetadata
from engine.scoring import ScoringResult, compute_scores_batch
from engine.ticker_mapping import TickerMapping
from engine.trend_filters import MarketRegime, apply_individual_filter, check_market_regime


@dataclass
class RankingResult:
    """Complete ranking output for one point in time."""

    date: date = field(default_factory=date.today)
    market_regime: MarketRegime = field(default_factory=MarketRegime)
    ranked_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    excluded_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    all_scores: dict[str, ScoringResult] = field(default_factory=dict)
    failed_tickers: list[str] = field(default_factory=list)


def _compute_flags(
    scores: ScoringResult,
    metadata: TickerMetadata,
) -> list[str]:
    """Generate flag strings for a single ticker.

    Flags:
      - "BELOW_SMA": price is below the 100-day SMA
      - "NO_SCORE":  score could not be computed (insufficient data)
      - "LOW_VOL":   average daily volume < 50,000
    """
    flags: list[str] = []

    if scores.above_sma_100 is False:
        flags.append("BELOW_SMA")

    if scores.score is None:
        flags.append("NO_SCORE")

    if (
        metadata.average_volume is not None
        and metadata.average_volume < config.MIN_VOLUME_WARNING
    ):
        flags.append("LOW_VOL")

    return flags


def build_ranking(
    price_data: dict[str, pd.DataFrame],
    benchmark_df: pd.DataFrame,
    metadata: dict[str, TickerMetadata],
    mappings: list[TickerMapping],
    failed_tickers: list[str] | None = None,
) -> RankingResult:
    """Full ranking pipeline: score -> filter -> rank -> flag.

    Args:
        price_data: Dict of yf_symbol -> OHLCV DataFrame.
        benchmark_df: OHLCV DataFrame for XIC.TO.
        metadata: Dict of yf_symbol -> TickerMetadata.
        mappings: List of all TickerMapping objects.
        failed_tickers: List of yf_symbols that failed data fetch.

    Returns:
        RankingResult with ranked and excluded DataFrames, each
        containing a "flags" column (comma-separated flag strings).
    """
    result = RankingResult(
        date=date.today(),
        failed_tickers=list(failed_tickers or []),
    )

    # Build lookup maps
    yf_to_tv: dict[str, str] = {m.yf_symbol: m.tv_symbol for m in mappings}
    yf_to_asset_class: dict[str, str | None] = {
        m.yf_symbol: m.asset_class for m in mappings
    }

    # Step 1: Check market regime
    result.market_regime = check_market_regime(benchmark_df)

    # Step 2: Compute scores for all tickers
    result.all_scores = compute_scores_batch(price_data)

    # Step 3: Build ranked DataFrame from ALL scorable tickers
    # BELOW_SMA tickers are included; they carry the flag and receive
    # purple highlighting in the table instead of being excluded.
    ranked_rows = []
    for symbol, scores in result.all_scores.items():
        if scores.score is None:
            continue
        meta = metadata.get(symbol, TickerMetadata())
        flags = _compute_flags(scores, meta)
        ranked_rows.append({
            "yf_symbol": symbol,
            "tv_symbol": yf_to_tv.get(symbol, symbol),
            "asset_class": yf_to_asset_class.get(symbol),
            "company": meta.short_name,
            "sector": meta.sector,
            "roc": scores.roc,
            "atr": scores.atr,
            "atr_pct": scores.atr_pct,
            "score": scores.score,
            "current_price": scores.current_price,
            "sma_100": scores.sma_100,
            "market_cap": meta.market_cap,
            "avg_volume": meta.average_volume,
            "div_yield": meta.dividend_yield,
            "flags": ",".join(flags) if flags else "",
        })

    if ranked_rows:
        ranked_df = pd.DataFrame(ranked_rows)
        ranked_df = ranked_df.sort_values("score", ascending=False).reset_index(drop=True)
        ranked_df.insert(0, "rank", range(1, len(ranked_df) + 1))
        result.ranked_df = ranked_df

    # Step 4: Build excluded DataFrame (only tickers with no computable score)
    excluded_rows = []
    for symbol, scores in result.all_scores.items():
        if scores.score is not None:
            continue  # Already in ranked_df
        meta = metadata.get(symbol, TickerMetadata())
        flags = _compute_flags(scores, meta)
        excluded_rows.append({
            "yf_symbol": symbol,
            "tv_symbol": yf_to_tv.get(symbol, symbol),
            "asset_class": yf_to_asset_class.get(symbol),
            "company": meta.short_name,
            "sector": meta.sector,
            "roc": scores.roc,
            "atr": scores.atr,
            "atr_pct": scores.atr_pct,
            "score": scores.score,
            "current_price": scores.current_price,
            "sma_100": scores.sma_100,
            "reason": _exclusion_reason(scores),
            "flags": ",".join(flags) if flags else "",
        })

    if excluded_rows:
        result.excluded_df = pd.DataFrame(excluded_rows)

    return result


def _exclusion_reason(scores: ScoringResult) -> str:
    """Describe why a ticker was excluded."""
    reasons = []
    if scores.above_sma_100 is False:
        reasons.append("Below 100-day SMA")
    elif scores.above_sma_100 is None:
        if not scores.has_sma_100:
            reasons.append("Insufficient history for SMA")
    if not scores.has_roc:
        reasons.append("Insufficient history for ROC")
    if not scores.has_atr:
        reasons.append("Insufficient history for ATR")
    return "; ".join(reasons) if reasons else "Unknown"
