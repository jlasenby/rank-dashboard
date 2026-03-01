# CSE Exchange README Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `CSE:` row to the README Supported Exchanges table so users know CSE tickers work.

**Architecture:** README-only change. The code already handles CSE correctly (`CSE:` → `.CN` yfinance suffix). No logic changes needed.

**Tech Stack:** Markdown

---

### Task 1: Add CSE row to Supported Exchanges table

**Files:**
- Modify: `README.md` (Supported Exchanges table, around line 124–133)

**Step 1: Open the file and locate the table**

The table currently looks like this (lines ~126–133):

```markdown
| TradingView Prefix | Maps To |
|-------------------|---------|
| `TSX:` | Toronto Stock Exchange (`.TO` suffix) |
| `TSE:` | Alias for TSX (legacy) |
| `TSXV:` | TSX Venture Exchange (`.V` suffix) |
| `NEO:` | NEO Exchange (yfinance fallback) |
| `NASDAQ:`, `NYSE:`, `AMEX:` | US exchanges (no suffix) |
| `CBOE:` | CBOE (ETFs like ARKK) |
| `BINANCE:`, `COINBASE:` | Crypto (converted to `yfinance` format) |
```

**Step 2: Insert the CSE row between TSXV and NEO**

```markdown
| TradingView Prefix | Maps To |
|-------------------|---------|
| `TSX:` | Toronto Stock Exchange (`.TO` suffix) |
| `TSE:` | Alias for TSX (legacy) |
| `TSXV:` | TSX Venture Exchange (`.V` suffix) |
| `CSE:` | Canadian Securities Exchange (`.CN` suffix, yfinance) |
| `NEO:` | NEO Exchange (yfinance fallback) |
| `NASDAQ:`, `NYSE:`, `AMEX:` | US exchanges (no suffix) |
| `CBOE:` | CBOE (ETFs like ARKK) |
| `BINANCE:`, `COINBASE:` | Crypto (converted to `yfinance` format) |
```

**Step 3: Verify the change looks correct**

Read the file and confirm the row is present and the table still renders cleanly (pipes aligned, no duplicate rows).

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add CSE exchange to supported exchanges table"
```

**Step 5: Push to GitHub**

```bash
git push
```
