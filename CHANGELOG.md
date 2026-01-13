# Changelog

All notable changes to this project will be documented in this file.

Format loosely follows Keep a Changelog; versions are semantic.

## [Unreleased]
- Minor UI polish and docs.

## [3.1.0] - 2025-10-26
- Consistent Pine parameter flow across Backtest, Live Signals, and Chart.
- Candlestick chart with labeled signals (Long, Exit, SL), crosshair, zoom/pan; auto-fetch on load.
- Live Signals table simplified to symbol, price, rsi, signal.
- Persist Backtester inputs via localStorage.
- Compounding sizing (percent-of-equity) and Max Drawdown (%) in metrics.
- Server endpoints accept Pine params for /signals and /pine/signal; added POST /restart.
- Accurate latest price using CCXT ticker override.
- Silenced pandas FutureWarnings in divergence helpers.
- Themed dropdown lists to match dark palette.

## [3.0.0] - 2025-10-26
- Switched backend to Pine v6–compatible long-only engine.
- Added SQLite OHLCV cache (data_cache.db) with helpers.
- Introduced Signal Chart panel and initial Live Signals API compatibility layer.

[Unreleased]: ./
[3.1.0]: ./
[3.0.0]: ./
