# Relative Strength Ranking Dashboard

A professional-grade, multi-page Streamlit dashboard for ranking securities by relative strength (momentum). Designed for Canadian long-only equity portfolios, with support for CAD stocks, USD ETFs, crypto, and macro indicators.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Watchlist Files](#watchlist-files)
6. [Running the Dashboard](#running-the-dashboard)
7. [Pages](#pages)
8. [Scoring Engine](#scoring-engine)
9. [Data Sources](#data-sources)
10. [Rank History Persistence](#rank-history-persistence)
11. [Project Structure](#project-structure)
12. [Troubleshooting](#troubleshooting)

---

## What It Does

The dashboard ranks securities by a **volatility-adjusted momentum score**:

```
Score = ROC(90D) / ATR%(90D)
```

Where:
- **ROC** — Rate of Change: percentage gain over the lookback period
- **ATR%** — Average True Range as a percentage of price (volatility normalizer)

A higher score means stronger momentum *relative to volatility* — it rewards securities that trend steadily upward over choppy ones. Rankings are computed across **all watchlists** in the `Watchlists/` directory and persisted to SQLite daily so you can track rank changes over time.

---

## Prerequisites

- **Python 3.11+**
- **Questrade account** with a personal access token (optional — yfinance is used as fallback)
- TradingView watchlist files exported in `.txt` format

---

## Installation

```bash
# 1. Clone or copy the project
cd C:\DOCUMENTS\00_CLAUDE\RANK

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt
```

### Questrade Token (optional)

If you have a Questrade account, create `questrade_token.yaml` in the project root:

```yaml
refresh_token: YOUR_REFRESH_TOKEN_HERE
```

The dashboard will use Questrade for Canadian securities (TSX, TSX-V, NEO) and fall back to yfinance automatically for anything else or if the token is missing/expired.

> **Note:** Without Questrade credentials the dashboard works fully via yfinance, but fetches may be slower.

---

## Configuration

All parameters live in **`config.py`**. Key settings:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ROC_LOOKBACK` | `90` | Lookback days for the primary momentum score |
| `ATR_PERIOD` | `90` | Lookback days for volatility (always matches `ROC_LOOKBACK`) |
| `DISPLAY_ROC_PERIODS` | `[1, 15, 30, 90, 250]` | Multi-timeframe ROC columns shown in tables |
| `INDIVIDUAL_SMA_PERIOD` | `100` | SMA used for the BELOW_SMA flag |
| `BENCHMARK_SYMBOL` | `XIC.TO` | Market regime benchmark (200-day SMA check) |
| `MARKET_SMA_PERIOD` | `200` | Benchmark SMA period |
| `MIN_VOLUME_WARNING` | `50000` | Average daily volume threshold for LOW_VOL flag |
| `ALPHA_GRID_PERCENTILE` | `0.40` | Top fraction shown on the Alpha Grid page |
| `WATCHLIST_DIR` | `Watchlists` | Directory scanned for `.txt` watchlist files |
| `CACHE_DIR` | `cache` | Parquet price cache location |
| `RANK_DB_PATH` | `data/rank_history.db` | SQLite rank history database |
| `BATCH_SIZE` | `50` | Tickers per yfinance batch download |
| `MAX_RETRIES` | `3` | API retry attempts with exponential backoff |

---

## Watchlist Files

Watchlist files live in the `Watchlists/` directory and use **TradingView export format** (`.txt`).

### File Format

```
###EQ_BETA
TSX:XIC,TSX:XEF,TSX:XEM,TSX:ZAG
###EQ_SECTORS
TSX:XEG,TSX:XFN,TSX:XIT,TSX:XHC
###CRB
TSX:XGD,TSX:HBB,COMEX:GC1!
###CRYPTO
BINANCE:BTCUSDT,BINANCE:ETHUSDT
###FI
TSX:ZAG,TSX:XSB
```

**Rules:**
- Lines starting with `###` are **section headers** — everything that follows belongs to that asset class until the next `###` header
- Tickers use TradingView format: `EXCHANGE:SYMBOL`
- Commas and newlines both work as separators
- Files without `###` headers are treated as flat lists (sector comes from yfinance metadata)

### Supported Exchanges

| TradingView Prefix | Maps To |
|-------------------|---------|
| `TSX:` | Toronto Stock Exchange (`.TO` suffix) |
| `TSXV:` | TSX Venture Exchange (`.V` suffix) |
| `NEO:` | NEO Exchange (yfinance fallback) |
| `NASDAQ:`, `NYSE:`, `AMEX:` | US exchanges (no suffix) |
| `CBOE:` | CBOE (ETFs like ARKK) |
| `BINANCE:`, `COINBASE:` | Crypto (converted to `yfinance` format) |

### How Pages Find Their Watchlists

Pages match watchlist files by **keyword in the filename** — not by exact name. This means you can rename files freely as long as the keyword is preserved:

| Page | Keyword rule | Safe rename example |
|------|-------------|-------------------|
| **Core** | filename contains `CORE_MASTER` | `CORE_MASTER_v2.txt` ✅ |
| **Explore** | filename starts with `EXPLORE` | `EXPLORE_CAD_2026.txt` ✅ |
| **USD** | filename starts with `USD_LONGLIST` | `USD_LONGLIST_v2.txt` ✅ |
| **Alpha Grid** | aggregates **all** `.txt` files in `Watchlists/` | any name ✅ |

> **Note:** Any `.txt` file in `Watchlists/` — regardless of name — is loaded into the pipeline and contributes to the Alpha Grid and rank history. Files not matching a page keyword are ranked and persisted but only visible on the Alpha Grid and Overview.

### Adding or Changing a Watchlist

1. Export from TradingView: **Watchlist → ⋮ → Export watchlist**
2. Rename the `.txt` file following the keyword rules above if it should appear on a dedicated page
3. Optionally add `###SECTION_NAME` headers manually
4. Drop the file into the `Watchlists/` directory
5. **Reload:** watchlists are scanned once per browser session at startup — use one of:
   - **Force Refresh** on the Data Status page (⚙️) to reload within the current session
   - Open a **new browser tab** to start a fresh session
   - Restart the dashboard (`Ctrl+C` → `streamlit run app.py`)

---

## Running the Dashboard

```bash
# Option 1: Streamlit directly
streamlit run app.py

# Option 2: Batch launcher (Windows)
launch.bat
```

The dashboard opens at `http://localhost:8501` in your browser.

### First Launch

On first launch the data pipeline runs automatically:

1. **Watchlists scanned** — all `.txt` files in `Watchlists/` are parsed
2. **Price data fetched** — Questrade → yfinance fallback, batched in groups of 50
3. **Benchmark fetched** — XIC.TO for market regime detection
4. **Metadata fetched** — sector, company name, market cap, avg volume
5. **Macro data fetched** — FX, bonds, metals, energy, global indices
6. **Rankings computed** — scored and ranked per watchlist, flagged
7. **Snapshots saved** — today's ranks written to SQLite for all watchlists and Core sections

Subsequent page switches within the same session reuse cached session state — no re-fetching.

### Refresh Data

To force a full data refresh (e.g., during market hours for updated prices):

1. Navigate to **Data Status** page (sidebar → ⚙️)
2. Click **Force Refresh All Data**

---

## Pages

### 📊 Overview

**Top performers snapshot + Macro dashboard**

- Four summary tables showing the **top 20 tickers** from each of: Core, Explore, USD, and Alpha Grid
- Columns: Rank, Ticker, 1D Chg, 15D Chg, 30D Chg, 90D Chg, 250D Chg, Flag
- ROC columns are heat-mapped green (positive) / red (negative)
- Macro dashboard below: grouped by FX / Bonds / Metals / Energy / Indices
  - Shows current Price, 1D%, 15D%, 30D%, 90D% with green/red heat-map cells

---

### 🏆 Alpha Grid

**Top 40% of all tickers across every watchlist in the folder**

- Aggregates ranked tickers from **all** `.txt` files in `Watchlists/` — not just Core, Explore, and USD
- Deduplicates by symbol (keeps the highest-scored occurrence)
- Takes the top 40% (ceiling) by score
- Full ranked table with all ROC columns, VOL, and flags
- Rank change is **not tracked** for this page (tickers move between watchlists)

---

### 🎯 Core

**Master watchlist — asset class sections**

- Displays each `###SECTION` from any `CORE_MASTER_*.txt` file as its own ranked sub-table
- Typical sections: EQ_BETA, EQ_SECTORS, CRB, CRYPTO, FI
- Each section is independently sorted by score with its own 1-based rank numbers
- **Rank history** (Chg, 1W, 4W) compares section-local ranks to section-local history — movement reflects position within the section, not the overall watchlist

---

### 🔍 Explore

**CAD stocks**

- Full ranked table of all tickers from any `EXPLORE_*.txt` file
- Sector distribution bar chart (top 20 ranked tickers by sector)
- Sector data sourced from yfinance metadata
- Rank history columns: Chg (vs yesterday), 1W (vs ~7 days ago), 4W (vs ~28 days ago)

---

### 💵 USD

**USD-denominated ETFs**

- Full ranked table of all tickers from any `USD_LONGLIST_*.txt` file
- Same column set as Explore including rank history

---

### 📈 Rank (Dynamic Analyzer)

**Upload any watchlist and rank it instantly**

- Upload **any** TradingView watchlist file (`.txt` or `.csv`)
- Price data for tickers not in the main pipeline is **fetched automatically** on upload — a progress bar shows fetch status
- Once fetched, data is merged into session state so other pages can use it too
- The same file re-uploaded within the same session skips re-fetching (file-hash dedup)
- **Preset buttons** `15D | 30D | 90D | 250D` above the slider for one-click common periods
- **ROC Lookback slider** (1–365 days, any value) — both ROC and ATR% use the same period
- Table updates instantly as the slider moves
- Rankings are **not persisted** to SQLite for this page

---

### ⚙️ Data Status

**Pipeline health monitor**

- Summary metrics: Total tickers, Fetched OK, Failed, Partial history
- Lists of failed and partial-history tickers
- Data source breakdown (Questrade vs yfinance per ticker)
- Watchlist summary (tickers per file, how many have data)
- Cache status (how many Parquet files, cache directory location)
- **Force Refresh All Data** button — clears all session state and re-runs the full pipeline

---

## Scoring Engine

### Primary Score

```
Score = ROC(lookback) / ATR%(lookback)
```

- **ROC** (`scoring.py`): `(Close_today / Close_N_days_ago) - 1`, expressed as a percentage
- **ATR%** (`scoring.py`): Average True Range over N days, divided by current price × 100
- Score is `None` (ticker excluded from ranking) if there are fewer than `MIN_HISTORY_BARS` (91) trading days of history

### Display ROC Columns

Multi-timeframe ROC values are pre-computed for every ranked ticker at fixed periods regardless of the slider:

| Column | Period |
|--------|--------|
| 1D Chg | 1 trading day |
| 15D Chg | 15 trading days (~3 weeks) |
| 30D Chg | 30 trading days (~6 weeks) |
| 90D Chg | 90 trading days (~quarter) |
| 250D Chg | 250 trading days (~year) |

### Flags

| Flag | Meaning | Visual |
|------|---------|--------|
| `BELOW_SMA` | Price < 100-day SMA | Purple cell background |
| `LOW_VOL` | Avg daily volume < 50,000 | Shown in Flag column |

> **Note:** BELOW_SMA tickers are **included** in rankings (not excluded). The purple highlight is a caution flag indicating elevated downtrend risk; tickers are still ranked normally by score.

### Market Regime

The benchmark (XIC.TO) is checked against its 200-day SMA. If XIC is below its SMA, the market is in a **bearish regime** — shown as a status indicator in the sidebar but does not affect rankings.

---

## Data Sources

### Price Data

| Source | Used For | Notes |
|--------|----------|-------|
| **Questrade** | Canadian securities (TSX, TSX-V) | Requires `questrade_token.yaml`; 10 req/sec with 100ms sleep |
| **yfinance** | Everything else / Questrade fallback | Batched 50 tickers per call; 1s sleep between batches |

**Caching:** OHLCV data is cached as Parquet files in `cache/` (date-stamped). If today's fetch fails, the most recent cache file is used as a stale fallback (up to `MAX_STALE_DAYS = 5` business days).

### Macro Data (yfinance only)

| Category | Tickers |
|----------|---------|
| FX | EUR/USD, GBP/USD, CHF/USD, CAD/USD, AUD/USD, JPY/USD |
| Bonds | US 10Y Yield (^TNX), US 2Y Yield (^IRX) |
| Metals | Gold (GC=F), Silver (SI=F), Copper (HG=F) |
| Energy | Crude Oil (CL=F), Natural Gas (NG=F) |
| Indices | S&P 500, NASDAQ, Russell 2000, Nikkei 225, STOXX 600, Shanghai Comp, Hang Seng |

---

## Rank History Persistence

Rank snapshots are saved to `data/rank_history.db` (SQLite) once per calendar day per session start.

**Schema:**

```sql
CREATE TABLE rank_snapshots (
    snapshot_date  TEXT NOT NULL,   -- ISO date: '2026-02-25'
    page           TEXT NOT NULL,   -- e.g. 'EXPLORE_60221' or 'CORE_MASTER_60221_EQ_BETA'
    ticker         TEXT NOT NULL,   -- yf_symbol: 'RY.TO'
    tv_symbol      TEXT,
    asset_class    TEXT,
    rank           INTEGER,
    score          REAL,
    roc_90         REAL,
    atr_pct        REAL,
    current_price  REAL,
    flags          TEXT,
    PRIMARY KEY (snapshot_date, page, ticker)
);
```

**Page keys saved:**

| Watchlist | Page key(s) saved |
|-----------|------------------|
| `EXPLORE_60221.txt` | `EXPLORE_60221` |
| `USD_LONGLIST_60221.txt` | `USD_LONGLIST_60221` |
| `CORE_MASTER_60221.txt` | `CORE_MASTER_60221` (global) + `CORE_MASTER_60221_EQ_BETA`, `CORE_MASTER_60221_EQ_SECTORS`, etc. (per section) |
| Any other `.txt` file | `<filename stem>` |

**Rank change columns in tables:**

| Column | Meaning | Query |
|--------|---------|-------|
| **Chg** | vs yesterday | Most recent snapshot before today |
| **1W** | vs ~1 week ago | Closest snapshot ≤ 7 calendar days ago |
| **4W** | vs ~4 weeks ago | Closest snapshot ≤ 28 calendar days ago |

Arrow color: 🟢 green = improved rank (lower number), 🔴 red = dropped rank, `—` = unchanged, `NEW` = no history that far back

> **Note on `NEW`:** The 1W column requires 7+ days of snapshots to show data; 4W requires 28+. Both columns show `NEW` until enough history has accumulated. This is expected on a fresh install.

---

## Project Structure

```
RANK/
├── app.py                      # Entry point — data pipeline + page router
├── config.py                   # All parameters (edit here first)
├── requirements.txt
├── launch.bat                  # Windows launcher
│
├── engine/
│   ├── scoring.py              # ROC, ATR%, SMA calculations
│   ├── ranking.py              # Score → Rank → Flag pipeline
│   ├── data_fetch.py           # Questrade + yfinance fetch with retry/cache
│   ├── macro_data.py           # Economic indicator data + ROC
│   ├── questrade_client.py     # Questrade API token refresh & REST calls
│   ├── ticker_mapping.py       # TradingView ↔ yfinance ↔ Questrade symbol mapping
│   └── trend_filters.py        # Market & individual SMA regime detection
│
├── pages/
│   ├── overview.py             # Top-20 summary tables + macro dashboard
│   ├── alpha_grid.py           # Top 40% aggregated across all watchlists
│   ├── core.py                 # Per-section ranked tables (CORE_MASTER_*.txt)
│   ├── explore.py              # CAD stocks + sector chart (EXPLORE_*.txt)
│   ├── usd.py                  # USD ETFs (USD_LONGLIST_*.txt)
│   ├── rank.py                 # Dynamic upload analyzer with auto-fetch
│   └── data_status.py          # Pipeline health monitor + Force Refresh
│
├── ui/
│   ├── tables.py               # render_ranked_table() — shared table renderer
│   ├── styles.py               # Heat-map coloring, flag cell styling
│   └── sidebar.py              # Navigation + data status indicator
│
├── persistence/
│   └── rank_store.py           # SQLite save/load/query rank snapshots
│
├── io_handlers/
│   ├── universe_loader.py      # Scans Watchlists/ directory
│   └── tv_export.py            # TradingView format utilities
│
├── Watchlists/                 # Drop TradingView .txt exports here
│   ├── CORE_MASTER_*.txt       # → Core page
│   ├── EXPLORE_*.txt           # → Explore page
│   ├── USD_LONGLIST_*.txt      # → USD page
│   └── *.txt                   # → Alpha Grid only
│
├── cache/                      # Auto-created; Parquet price cache (gitignored)
├── data/                       # Auto-created; rank_history.db (gitignored)
└── docs/plans/                 # Feature design & implementation plans
```

---

## Troubleshooting

### "Price data is not yet available"
The data pipeline is still running. Wait for the sidebar status indicator to turn green, or check the Data Status page for errors.

### Many tickers showing as failed
1. Check the Data Status page → Failed Tickers list
2. If Questrade tickers are failing, your `questrade_token.yaml` refresh token may be expired — generate a new one from the Questrade app
3. If yfinance tickers are failing, try a Force Refresh (rate limits sometimes cause transient failures)

### BELOW_SMA flag on many tickers
Expected during bearish market conditions. The benchmark (XIC.TO) status indicator in the sidebar shows if the broad market is in a downtrend. BELOW_SMA tickers remain ranked — the purple highlight is a caution flag, not an exclusion.

### 1W / 4W columns showing "NEW" for all tickers
These columns need historical snapshots to compare against. `NEW` means no snapshot exists far enough back:
- **1W** requires 7+ days of daily snapshots (appears ~1 week after first run)
- **4W** requires 28+ days of daily snapshots (appears ~4 weeks after first run)
- The `Chg` (yesterday) column works from day 2 onward

### Rank page — uploaded tickers not appearing / still showing NEW
- Price data for tickers not in the main pipeline is fetched automatically on upload — wait for the progress bar to complete
- If some tickers show "could not be fetched", they may use unsupported exchange prefixes or be delisted
- `NEW` in the 1W/4W columns is expected for uploaded watchlists — the Rank page does not write to SQLite, so no history is ever saved for it

### Watchlist file not appearing on its page
- Confirm the filename contains the correct keyword (`CORE_MASTER`, `EXPLORE`, or `USD_LONGLIST`) — see [How Pages Find Their Watchlists](#how-pages-find-their-watchlists)
- Watchlists are only scanned **once per session** at startup. To pick up a file added mid-session: use **Force Refresh** on Data Status, open a new browser tab, or restart the dashboard

### Cache is stale
Click **Force Refresh All Data** on the Data Status page. This clears all cached session state and triggers a fresh API fetch on the next page load.
