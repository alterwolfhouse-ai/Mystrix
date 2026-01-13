# Project Error Log and Resolutions

This log tracks issues encountered during development/debugging and their resolutions so the next person can quickly diagnose similar problems.

Note: ML advisory sizing has been removed; the engine now relies on Pine-style stops and an HTF gate.

## 1) Live prices incorrect in chart and table
- Symptoms: Signal chart showed wrong last prices; Live Signals table showed the same price for multiple symbols; bias/mid/squeeze columns persisted from old engine.
- Cause: Endpoints used the legacy engine and cached data; last close wasn’t aligned to current ticker; UI expected fields no longer produced.
- Fixes:
  - Switched `/signals` to the Pine engine and trimmed fields to `{ symbol, price, rsi, signal: { action } }`.
  - `/pine/signal` and `/signals` fetch recent CCXT OHLCV; when possible the latest candle’s close is overridden with the live ticker.
  - Updated UI to remove bias/mid/squeeze columns.

Files: `server.py`, `script.js`

## 2) No chart or markers showing
- Symptoms: Chart area stayed empty; no signals rendered.
- Causes:
  - Incomplete/mangled JS during earlier edits; auto-fetch on load missing.
  - Excessive marker truncation.
- Fixes:
  - Rewrote `script.js` cleanly; added auto `fetchSignal()` shortly after load; extended markers to last 200 entries.
  - Added robust canvas candlestick renderer + labeled markers (Long/Exit/SL), crosshair, zoom/pan.

Files: `script.js`, `engine/pine_long.py`

## 3) “Working…” statuses not appearing
- Symptoms: Clicking buttons didn’t show transient states like “Running backtest…” or “Scanning…”.
- Cause: Event handlers and text toggles were lost in a broken JS merge.
- Fixes: Restored status text and button disabled states for Backtest, Live Signals, and Chart fetch.

Files: `script.js`

## 4) RSI thresholds incorrectly interpreted
- Symptom: User could set Overbought below Oversold by mistake.
- Fix: Guard in engine swaps OB/OS when inverted, keeping Pine logic valid (OB>OS).

Files: `engine/pine_long.py`

## 5) Persistence across refresh not working
- Symptom: After refresh, configured inputs reverted to defaults.
- Fix: Save Backtester inputs to `localStorage` and reload them on page load.

Files: `script.js`

## 6) Dropdown select list hard to read (white background)
- Fix: Styled `select` and `option` for a dark theme.

Files: `styles.css`

## 7) pandas FutureWarnings
- Symptoms: Console spam from `fillna` on boolean series in divergence helpers.
- Fix: Use nullable boolean before `fillna(False)` and cast back to `bool`.

Files: `engine/divergence.py`

## 8) Performance: repeated data fetches slow
- Improvement: Added SQLite OHLCV cache (`data_cache.db`) with helper functions to reuse cached data and populate missing ranges.

Files: `engine/storage.py`

## 9) Unified parameter flow and compounding
- Feature: Backtests, Live Signals, and Chart now share a single set of Pine params, initial capital, and percent risk.
- Implementation: UI constructs query overrides; server passes them into Pine engine.
- Added `Max Drawdown (%)` and compounding via percent-of-equity sizing.

Files: `script.js`, `server.py`, `engine/pine_long.py`

## 10) Quick local restart
- Feature: `POST /restart` to exit the process gracefully so it can be relaunched.

Files: `server.py`
