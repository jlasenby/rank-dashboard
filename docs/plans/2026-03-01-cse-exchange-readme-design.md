# Design: Document CSE Exchange Support in README

**Date:** 2026-03-01
**Approach:** A — README fix only

## Problem

The README "Supported Exchanges" table omits `CSE:` entirely, giving the impression that Canadian Securities Exchange tickers are unsupported. In reality, the code already handles them correctly:

- `ticker_mapping.py` maps `CSE:` → `.CN` yfinance suffix (e.g. `CSE:GTII` → `GTII.CN`)
- `questrade_client.py` maps CSE to Questrade's `CNSX` filter, with yfinance as fallback
- yfinance successfully fetches `.CN` tickers (confirmed: `GTII.CN` returns live data)

## Change

Add one row to the Supported Exchanges table in `README.md`, between TSXV and NEO:

| TradingView Prefix | Maps To |
|--------------------|---------|
| `CSE:` | Canadian Securities Exchange (`.CN` suffix, yfinance) |

The note "(yfinance)" matches the NEO row convention, accurately reflecting that CSE routes through yfinance rather than Questrade.

## Files Changed

- `README.md` — one row inserted in the Supported Exchanges table

## Files Not Changed

- `engine/ticker_mapping.py` — already correct
- `engine/questrade_client.py` — already correct
- `engine/data_fetch.py` — already correct
