"""
Rank History Store — SQLite persistence for daily ranking snapshots.

Stores rank snapshots keyed by (date, page, ticker) so the dashboard can:
  - Show rank changes (arrows) between today and previous day
  - Display rank history charts for individual tickers
  - Track rank evolution across multiple watchlist pages
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import date, timedelta
from typing import Any

import config

logger = logging.getLogger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS rank_snapshots (
    snapshot_date TEXT NOT NULL,
    page TEXT NOT NULL,
    ticker TEXT NOT NULL,
    tv_symbol TEXT,
    asset_class TEXT,
    rank INTEGER,
    score REAL,
    roc_90 REAL,
    atr_pct REAL,
    current_price REAL,
    flags TEXT,
    PRIMARY KEY (snapshot_date, page, ticker)
);
"""

_CREATE_INDEX_PAGE_DATE_SQL = """
CREATE INDEX IF NOT EXISTS idx_rank_page_date
    ON rank_snapshots(page, snapshot_date);
"""

_CREATE_INDEX_TICKER_SQL = """
CREATE INDEX IF NOT EXISTS idx_rank_ticker
    ON rank_snapshots(ticker, page);
"""


def _ensure_db_dir() -> None:
    """Ensure the directory for the database file exists."""
    db_dir = os.path.dirname(config.RANK_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


def _get_connection() -> sqlite3.Connection:
    """Open a connection to the rank history database with WAL mode."""
    _ensure_db_dir()
    conn = sqlite3.connect(config.RANK_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database schema (idempotent).

    Creates the rank_snapshots table and indexes if they do not exist.
    Safe to call on every startup.
    """
    conn = _get_connection()
    try:
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute(_CREATE_INDEX_PAGE_DATE_SQL)
        conn.execute(_CREATE_INDEX_TICKER_SQL)
        conn.commit()
        logger.info("Rank store initialized at %s", config.RANK_DB_PATH)
    finally:
        conn.close()


def save_snapshot(
    snapshot_date: date | str,
    page: str,
    rows: list[dict[str, Any]],
) -> None:
    """Save a ranking snapshot for a given date and page.

    Uses INSERT OR REPLACE so re-running on the same date overwrites
    stale data cleanly.

    Args:
        snapshot_date: The date of the snapshot (date object or ISO string).
        page: The watchlist page name (e.g. "CORE_MASTER_60221").
        rows: List of dicts, each with keys matching the table columns:
              ticker, tv_symbol, asset_class, rank, score, roc_90,
              atr_pct, current_price, flags.
    """
    if isinstance(snapshot_date, date):
        date_str = snapshot_date.isoformat()
    else:
        date_str = str(snapshot_date)

    conn = _get_connection()
    try:
        conn.executemany(
            """
            INSERT OR REPLACE INTO rank_snapshots
                (snapshot_date, page, ticker, tv_symbol, asset_class,
                 rank, score, roc_90, atr_pct, current_price, flags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    date_str,
                    page,
                    row.get("ticker", ""),
                    row.get("tv_symbol"),
                    row.get("asset_class"),
                    row.get("rank"),
                    row.get("score"),
                    row.get("roc_90"),
                    row.get("atr_pct"),
                    row.get("current_price"),
                    row.get("flags"),
                )
                for row in rows
            ],
        )
        conn.commit()
        logger.info(
            "Saved %d rank rows for page '%s' on %s",
            len(rows), page, date_str,
        )
    finally:
        conn.close()


def get_previous_ranks(
    page: str,
    ticker_list: list[str],
    before_date: date | str,
) -> dict[str, int]:
    """Get the most recent rank for each ticker before a given date.

    Useful for computing rank-change arrows (today's rank vs yesterday's).

    Args:
        page: The watchlist page name.
        ticker_list: List of ticker symbols to look up.
        before_date: The reference date (exclusive upper bound).

    Returns:
        Dict mapping ticker -> previous rank. Tickers with no prior
        snapshot are omitted from the result.
    """
    if not ticker_list:
        return {}

    if isinstance(before_date, date):
        date_str = before_date.isoformat()
    else:
        date_str = str(before_date)

    conn = _get_connection()
    try:
        # Build parameterized query for the ticker list
        placeholders = ",".join("?" for _ in ticker_list)
        query = f"""
            SELECT ticker, rank
            FROM rank_snapshots
            WHERE page = ?
              AND snapshot_date = (
                  SELECT MAX(snapshot_date)
                  FROM rank_snapshots
                  WHERE page = ? AND snapshot_date < ?
              )
              AND ticker IN ({placeholders})
        """
        params = [page, page, date_str] + list(ticker_list)
        cursor = conn.execute(query, params)
        return {row["ticker"]: row["rank"] for row in cursor.fetchall()}
    finally:
        conn.close()


def get_ranks_at_lookback(
    page: str,
    ticker_list: list[str],
    current_date: date | str,
    n_days: int,
) -> dict[str, int]:
    """Get each ticker's rank from approximately n_days ago.

    Finds the most recent snapshot on or before (current_date - n_days)
    for each ticker. Returns an empty dict for tickers with no historical
    data that far back.

    Args:
        page: The watchlist page name (e.g. "CORE_MASTER_60221").
        ticker_list: List of yf_symbol ticker strings to look up.
        current_date: Today's date (date object or ISO string).
        n_days: How many calendar days back to look (7 = 1 week, 28 = 4 weeks).

    Returns:
        Dict mapping ticker -> rank at ~n_days ago. Tickers with no
        snapshot that far back are omitted.
    """
    if not ticker_list:
        return {}

    if isinstance(current_date, str):
        current_date = date.fromisoformat(current_date)

    if n_days < 1:
        raise ValueError(f"n_days must be a positive integer, got {n_days!r}")

    target_date_str = (current_date - timedelta(days=n_days)).isoformat()

    conn = _get_connection()
    try:
        placeholders = ",".join("?" for _ in ticker_list)
        # For each ticker, get the most recent snapshot on or before target date
        query = f"""
            SELECT ticker, rank
            FROM rank_snapshots
            WHERE page = ?
              AND ticker IN ({placeholders})
              AND snapshot_date = (
                  SELECT MAX(s2.snapshot_date)
                  FROM rank_snapshots s2
                  WHERE s2.page = ?
                    AND s2.ticker = rank_snapshots.ticker
                    AND s2.snapshot_date <= ?
              )
        """
        params = [page] + list(ticker_list) + [page, target_date_str]
        cursor = conn.execute(query, params)
        return {row["ticker"]: row["rank"] for row in cursor.fetchall()}
    finally:
        conn.close()


def get_rank_history(
    page: str,
    ticker: str,
    n_days: int = 30,
) -> list[dict[str, Any]]:
    """Get the rank history for a specific ticker on a page.

    Returns the most recent n_days of snapshots, ordered by date ascending.

    Args:
        page: The watchlist page name.
        ticker: The ticker symbol.
        n_days: Maximum number of snapshots to return.

    Returns:
        List of dicts with keys: snapshot_date, rank, score, roc_90,
        atr_pct, current_price, flags.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT snapshot_date, rank, score, roc_90, atr_pct,
                   current_price, flags
            FROM rank_snapshots
            WHERE page = ? AND ticker = ?
            ORDER BY snapshot_date DESC
            LIMIT ?
            """,
            (page, ticker, n_days),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        # Return in ascending date order
        rows.reverse()
        return rows
    finally:
        conn.close()
