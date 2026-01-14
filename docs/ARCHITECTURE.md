# War Zone — Project Architecture & Operating Guide

This document explains how the project is structured, how the server side and browser side work together, and how to run, extend, and troubleshoot the system.

## Snapshot Notice — Restored to "semifinalhedge"
- The working tree has been reverted to the snapshot saved at `.backup/semifinalhedge`.
- Scope of restore:
  - Core UI and scripts: `magic.html`, `script.js`, `asset_picker.js`.
  - Server entry: `server.py` (routes and redirects as in the snapshot).
  - Engines: reverted key modules (e.g., `engine/pine_short.py`) to the snapshot state.
- Items not part of the snapshot remain on disk (e.g., the experimental `mobile/` Expo client). They are out of the main flow and can be removed later without impact.
- Start the server from the repo root exactly: `python server.py` (see Run Book below). Open `http://127.0.0.1:8000/static/magic.html`.


## Overview
- Purpose: Provide a simple website experience to backtest and monitor multi‑asset trading signals locally, without cloud hosting.
- Components:
  - Server end: a lightweight Python API built with FastAPI (local only).
  - Browser end: the Magic Lab page and scripts that call the API and render results.
  - Trading engine: modular Python package under `engine/` for data, indicators, filters, execution, and risk.

## Server End (FastAPI)
- Entry point: `server.py:1`
- Framework: FastAPI + Uvicorn, CORS enabled for local development.
- Core behavior:
  - Normalizes dates and symbols for convenience (`ETHUSD` → `ETH/USDT`, `21-10-2025` → `2025-10-21`). See `server.py:40`.
  - Uses the modular engine to run backtests or compute live signals.
  - Disables DXY gating and ML during backtests to minimize friction and failures; this is configurable.

### Endpoints
- `GET /healthz` — quick status probe.
- `GET /symbols` — lists common `*/USDT` pairs (via `ccxt` if available).
- `POST /backtest` — runs backtests.
  - Request body:
    - `symbols: string[]` (e.g., `["BTC/USDT","ETH/USDT"]`)
    - `start: string` — accepts `DD-MM-YYYY` or `YYYY-MM-DD`
    - `end: string` — accepts `DD-MM-YYYY` or `YYYY-MM-DD`
    - `overrides: object` — optional engine overrides (e.g., `{ "timeframe_hist": "3m" }`)
  - Response: `{ metrics, trades }` with last up to 500 trades.
- `GET /signals` (and `/signals/`) — computes a snapshot per symbol.
  - Query: `symbols=BTC/USDT,ETH/USDT&timeframe=3m&lookback=2000`
  - Response: `{ signals: Signal[], logs: Record<symbol, Event[]> }`
    - `signals[i]` fields: `symbol`, `price`, `rsi`, `bias`, `bias_conf`, `mid`, `mid_conf`, `squeeze`, `event`, `signal`.
    - `signal`: `action: BUY|SELL|HOLD`, `confidence: 0..1`, `level: 1|2|3` (1=low, 3=high).
    - `logs[symbol]`: last 5 events `enter_long|exit_normal|exit_sl` with time, entry/exit, qty.

### Data handling on the server
- Historical fetch: `engine/data.py:29` supports full‑range CCXT paging via `fetch_ccxt_hist_range()` and quick recent pulls via `fetch_ccxt_recent()`.
- Resampling: `resample_ohlcv()` uses modern pandas frequencies (`3min`, `5min`, `1h`, `4h`) to avoid deprecation warnings.
- Indexing: avoids inplace operations to keep pandas forwards‑compatible.

### Backtest execution
- Orchestrator: `engine/bot.py:16` (`RemixBot`).
- Flow per symbol:
  1. Load history for requested range/timeframe.
  2. Prefilter with BB squeeze on `1h`.
  3. Compute HTF bias, mid‑TF choppiness, and LTF risk/stop.
  4. 3m executor processes bars, looking for pivot‑confirmed RSI divergence entries and managed exits.
  5. Fees are applied on both sides (bps).
- Metrics computation: uses numpy nan‑safe statistics to avoid pandas truthiness issues (`engine/bot.py:119`).
- ML advisory: removed. Engine relies on Pine-style stops and an HTF (30m) gate with a 20% HTF stop.

## Browser End (Magic Lab)
- Page: `magic.html:1`
- Style: `styles.css`, keeping neon theme and existing CTA/components.
- Script: `script.js` integrates with the API.

### Local Backtester UI
- Inputs: symbols, start date, end date, timeframe (default `3m`).
- Actions:
  - Recheck API: pings `/healthz` and updates status dot.
  - Run Backtest: POSTs to `/backtest`, renders metrics grid and recent trades table.
- Error handling: shows concise error string under the panel; server normalizes dates and symbols.

### Live Signals UI
- Inputs: symbols, timeframe, auto‑refresh (themed input).
- Actions:
  - Scan Now: GET `/signals` and render table.
  - Start/Stop Auto: toggles periodic scans.
- Output:
  - Table with `symbol/price/RSI/bias/mid/squeeze/signal` where `signal` is `BUY/SELL/HOLD (L1..L3)`.
  - Logs viewer: dropdown of scanned symbols, showing last 5 events per selection.

## Configuration
- Base config: `config.yaml` sets symbols, dates, risk/stops, fees, filters, and defaults.
- API applies safe defaults for local runs:
  - `disable_ml = true` (unless you provide a trained schema‑aligned model).
  - `use_dxy_filter = false` (no macro gating for local/dev).
- Optional environment guards:
  - `MAX_BACKTEST_DAYS` caps backtest date ranges.
  - `API_TOKEN` requires `X-API-Key` (or a valid session cookie) for API access.
  - `CORS_ORIGINS`/`CORS_ORIGIN_REGEX` control allowed origins.

## Run Book
- Install & start server (local only):
  - Windows PowerShell:
    - `python -m venv .venv; .\\.venv\\Scripts\\Activate.ps1; pip install -U pip; pip install -r requirements.txt; python server.py`
  - macOS/Linux:
    - `python -m venv .venv && source .venv/bin/activate && pip install -U pip && pip install -r requirements.txt && python server.py`
- Open `magic.html` in a browser:
  - Green status dot = API reachable.
  - Use Backtester or Live Signals as needed.

### Bybit v5 + RAW + Gate (new)
- Ingest RAW OHLCV (append-only) from Bybit testnet:
  - `POST /ingest` with `{ \"symbols\":[\"BTCUSDT\"], \"timeframe\":\"1h\" }` (requires header `X-API-Key` if `API_TOKEN` is set).
- Gate:
  - `GET /gate/compute` computes a fresh 8h Volume ROC snapshot and persists it.
  - `GET /gate/snapshot` returns the latest persisted ranked list.
- Engines:
  - `/backtest` accepts `engine: \"long\"|\"short\"` and 8h gate overrides: `gate_enable`, `gate_threshold`, `gate_base_tf`, `gate_vroc_span`.
  - `/pine/signal` and `/signals` accept `engine` and prefer RAW data if present.

### Remote/Mobile Use
- The server now exposes static files under `/static` so the UI can be loaded from the same origin as the API:
  - `http://<HOST>:8000/static/magic.html`
- To listen on your LAN for mobile/Android testing, bind to all interfaces:
  - Windows PowerShell: `$env:HOST = "0.0.0.0"; $env:PORT = "8000"; python server.py`
  - macOS/Linux: `HOST=0.0.0.0 PORT=8000 python server.py`
- For internet access, prefer a secure tunnel (Cloudflare Tunnel, Tailscale, ngrok) and update the Android app's Server URL accordingly.

## Cloud Deploy (No Port Forwarding)

When your ISP does not provide a public IP or port forwarding, run the site/API fully in the cloud. The repo includes a production-ready Docker + Caddy setup under `deploy/cloud/`.

### Option A — VPS (Docker Compose)
- Pick a small VPS (1 vCPU / 2GB RAM is fine) close to India for latency.
  - Examples: DigitalOcean (Bengaluru), AWS Lightsail (Mumbai), Hetzner (Ashburn/Singapore).
- On the VPS (Ubuntu 22.04+):
  - `sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin git`
  - `git clone <your-repo> warzone && cd warzone/deploy/cloud`
  - Set your public hostname (normal DNS) to point to the VPS IP (A record). You may use DuckDNS if you don’t own a DNS domain.
  - `export SITE_HOST=your.domain.example`
  - Update `deploy/cloud/Caddyfile` email if desired (for Let’s Encrypt).
  - `sudo docker compose up -d`

What this runs:
- `app`: your FastAPI (`server.py`) bound to `0.0.0.0:8000`.
- `caddy`: terminates TLS for `https://$SITE_HOST` and reverse-proxies to `app`.

Access:
- Open `https://$SITE_HOST/static/magic.html`
- Health: `https://$SITE_HOST/healthz`

Android App:
- Use `https://$SITE_HOST` as the Server URL on first run.

Optional security:
- If you set `API_TOKEN` in `compose.yml`, the server can require `X-API-Key: <token>` on requests (enable server-side check first).

### Option B — PaaS (no server admin)
- Render.com or Railway.app can run `server.py` directly, but you’ll need to:
  - Set the start command to `python server.py` and expose port 8000.
  - Add a CDN or static reverse proxy for custom domains/HTTPS.
  - Persist `data_cache.db` to a disk or let the server re-fetch candles via CCXT.

## Error Handling & Troubleshooting
- API returns precise error text in the frontend when a request fails.
- Common issues:
  - Date formats: both `DD-MM-YYYY` and `YYYY-MM-DD` are accepted; server normalizes internally.
  - Symbols: `ETHUSD/BTCUSD` etc. are normalized to `ETH/USDT`, `BTC/USDT`.
  - ML model mismatch: backtests run with ML disabled by default. Re‑enable only with a schema‑aligned model.
  - No trades: filters can be strict for short ranges on `3m`. Use a longer period or relax prefilters via overrides.
- Logs: Live Signals include last 5 events per symbol; for server logs run `python server.py` in a terminal to view console output.

## Extending
- Add endpoints (e.g., `/ws` for live push) in `server.py`.
- Cache candles to disk to speed repeat queries (e.g., Parquet per symbol/tf).
- Harden security (when moving off localhost): add auth, restrict CORS, or run behind a tunnel with SSO.

 

## Security Considerations (local now, cloud later)
- Current setup is local-only by default.
- If you later expose the API externally, require authentication, restrict origins, and prefer a zero-trust tunnel (e.g., Cloudflare Tunnel) instead of opening router ports.

## Android Version
- A lightweight Android WebView app is provided under `android version/`.
- It loads the Magic UI from your PC server at `http://<HOST>:8000/static/magic.html` and communicates with the same-origin API.
- First run prompts for the Server URL; you can use `http://10.0.2.2:8000` on the emulator or your PC's LAN/tunnel address on devices.

---

Questions or changes you want made next (e.g., caching, presets, or WebSocket streams)?


## Update - Pine Long Engine v3

- Server now uses a Pine v6-compatible long-only engine for both backtesting and on-demand signals.
- New local OHLCV cache: `engine/storage.py` writes to `data_cache.db` (SQLite) and auto-populates via CCXT.
- Endpoints:
  - `POST /backtest` — Backtests with Pine params in `overrides` (e.g., `rsi_length`, `rsi_overbought`, `rsi_oversold`, `lookbackLeft`, `lookbackRight`, `rangeLower`, `rangeUpper`, `use_pct_stop`, `max_wait_bars`, `cooldownBars`, plus `timeframe_hist`).
  - `GET /pine/signal?symbol=BTC/USDT&timeframe=3m&bars=500` — Returns `{ action, metrics, trades, chart: { candles, markers } }` for quick charting.
- UI changes:
  - Backtester panel gains parameter inputs matching the Pine script.
  - New "Signal Chart (Pine Long)" panel renders a simple in-page chart with entry/exit/SL markers, polling `/pine/signal`.

## Update — v3.1 Quality/UX Improvements

- Consistent Param Flow
  - RSI/pivots/range/stop/wait/cooldown plus Initial Capital and Risk-per-trade now drive Backtest, Live Signals, and Signal Chart. The website sends these as overrides to each endpoint.

- Candlestick Chart + Signals
  - Candles (OHLC), wicks and bodies with theme colors.
  - Signal markers with labels: Long, Exit, SL; crosshair, zoom, and pan.
  - Auto-fetch once on page load to populate the chart immediately.

- Live Signals Table
  - Trimmed to the fields the new engine actually produces: `symbol`, `price`, `rsi`, and `signal.action`.

- Persistence
  - Backtester inputs are saved to `localStorage` and restored on refresh (symbols, dates, timeframe, all Pine params, initial capital, risk%).

- Metrics / Risk
  - Backtests compounding by percent-of-equity sizing.
  - Added `Max Drawdown (%)` metric based on closed-trade equity curve.

- Server Endpoints
  - `/pine/signal` and `/signals` accept Pine params + `initial_capital`, `percent_risk`, and HTF gate controls: `enableHTFGate`, `htfTF`, `htf_pct_stop`.
  - `/restart` (POST) returns `{ ok: true, restarting: true }` and exits the process after a short delay so you can relaunch the server quickly in local dev.

- Accuracy and Stability
  - Recent CCXT candles + ticker override for last price ensure accurate values.
  - Silenced pandas FutureWarnings in divergence helpers.
  - Dropdown styling for a dark list panel.

## Project Notes (Modules, Pages, User Journey)

This project ships two personas and a shared engine. The Admin experience exposes all tuning and diagnostics (the original “Magic Lab”), while the User experience is guard‑railed to time‑range selection and symbol choice. A single FastAPI backend serves all pages and the API from the same origin for simplicity and cookie‑based auth.

- Pages and tree
  - `index.html` (Mystrix marketing): hero, story, value pillars, footer CTAs, bottom dock.
  - `login.html` (standalone sign-in): username/password, optional quick-fill buttons on localhost, server status.
  - `user.html` (user panel): symbol dropdown, “missing coin” suggest, favorites row, chart canvas, alarm toggle (per symbol), date‑range backtest (timeframe/params locked by admin defaults), server status dot.
  - `admin.html` (admin dashboard): full Magic Lab panels (Local Backtester, Live Signals, Signal Chart), plus Users, Suggestions, Engine Defaults editor and Deep Backtest.
  - `magic.html` (legacy/admin panel): original UI; kept for familiarity and reuse.

- Client scripts
  - `script.js`: wiring for Magic Lab (backtest, live signals, chart), dynamic bottom‑nav highlighting, copy helpers.
  - `user.js`: auth modal, favorites CRUD, suggestions, server status, range‑only backtest using `/defaults`, simple alarm (audio cue) per selected symbol, chart renderer.
  - `admin.js`: Users/Suggestions lists with resolve, Engine Defaults load/save (`/defaults`, `/admin/defaults`), Deep Backtest runner (`/backtest/deep`).
  - `login.js`: server health check and cookie login with redirects.

- Server/API (FastAPI; `server.py`)
  - Static at `/static` serves all pages/assets from the same origin.
  - Core engine endpoints: `/healthz`, `/symbols`, `/backtest`, `/signals`, `/pine/signal`, `/backtest/deep`.
  - Auth + storage (SQLite in `data_cache.db`): tables `users`, `sessions`, `favorites`, `suggestions`, `settings`.
    - `/auth/signup`, `/auth/login`, `/auth/logout`, `/me` with HttpOnly session cookie.
    - `/favorites` (GET/POST/DELETE), `/suggest_coin`.
    - Admin: `/admin/users`, `/admin/suggestions`, `/admin/suggestions/resolve`, `/admin/defaults`.
  - Defaults: `/defaults` returns locked parameters for user backtests; admins set them.

- Engine modules
  - `engine/pine_long.py` implements the long-only signal engine (Pine-style entries/stops) and HTF gate used by `/backtest` and `/pine/signal`.
  - `engine/storage.py` and `engine/data.py` handle OHLCV cache, CCXT fetch, and resampling.
  - `engine/indicators.py` exposes utilities (e.g., Wilder RSI).
  - `engine/executor.py` (and peers) organize execution logic used across modes.

- User journey
  1) Land on `index.html` → tap “Launch Mystrix” → `user.html`.
  2) Log in (or use demo) → select a symbol; add to favorites; submit missing coin if needed.
  3) View chart, toggle alarm for the current symbol, run a date‑range backtest (defaults enforce consistency).

- Admin journey
  1) Sign in as admin → `admin.html`.
  2) Use Magic Lab panels (full parameter control), review users/suggestions.
  3) Edit Engine Defaults to govern user backtests; run Deep Backtests for analysis.

- Hosting options
  - Local LAN: `HOST=0.0.0.0 PORT=8000 python server.py`; pages under `/static`.
  - Cloud: `deploy/cloud/compose.yml` with Caddy for TLS; or Cloudflare/other tunnels for no‑port‑forwarding.

Security notes: the first created account is admin; no default accounts are created. Cookies require serving pages from `/static` (avoid opening files directly). CORS is controlled by `CORS_ORIGINS`/`CORS_ORIGIN_REGEX`, and `API_TOKEN` can require `X-API-Key` (or a valid session cookie) for API access.

---

## Extended Project Notes (Deep Dive, 2000+ words)

This section documents the project in depth so a new contributor can join and become productive in a single sitting. It covers the page tree and UI behavior, client scripts and patterns, backend layout and endpoints, database schema and lifecycle, the trading engine modules and data handling, guardrails for users, and a practical guide to hosting, testing, and troubleshooting. The aim is to explain not just what exists, but why it is structured this way and how to extend it safely.

### 1. System Architecture at a Glance

The system is a single‑origin web app backed by a FastAPI server. The same FastAPI process serves both the API and static assets (HTML/CSS/JS) under `/static`. This has several advantages:

- Simpler deployments: one process, one port.
- Cookie‑based authentication works out of the box because the frontend and backend share the origin.
- Fewer moving parts while developing locally (no extra dev server).

From a product perspective we support two personas:

- Admin: full control of the engine, parameters, diagnostics, and moderation (original “Magic Lab” experience). Admins can change engine defaults that are enforced on the user side and run Deep Backtests.
- User: a guided panel with guardrails. Users can select a symbol, toggle a symbol alarm, run date‑range backtests (timeframe and other parameters locked by admin defaults), manage favorites, and suggest missing coins.

The client is “thin but capable”: all parameter entry, charts, and tables are rendered in the browser using canvas and DOM; the API returns compact JSON payloads. The trading engine logic and data acquisition live on the server.

### 2. Page Tree and Navigation

All pages are simple HTML files committed to the repository and served from the server’s working directory. The “bottom dock” component (nav bar + floor light bar) is repeated across pages for consistent navigation and branding.

- `index.html` – The marketing/landing page for “Mystrix by Wolf House.” It introduces the product, includes the “Story of Mystrix,” and presents value pillars and CTAs. The “Launch Mystrix” CTA links to `user.html`.
- `login.html` - A standalone login page. It offers optional quick-fill buttons for localhost development and checks server status.
- `user.html` – The user panel. The top has a symbol selector and a “Missing coin?” submit box. The middle shows a chart canvas with fetch/auto and an alarm toggle, and a favorites strip for quick symbol access. A guarded “Backtest” block allows picking only Start and End dates; server defaults are applied behind the scenes.
- `admin.html` – The admin dashboard. The top half reinstates the full Magic Lab panels (Backtester with RSI and other parameters, Live Signals, and Signal Chart). Below, the admin‑only blocks list users, coin suggestions, the Engine Defaults editor, and a Deep Backtest runner.
- `magic.html` – The original Magic Lab page. It remains as a reference and for anyone who prefers the classic view.

Bottom Dock behavior:

- The bottom nav and the “floor light bar” remain fixed and centered, with a consistent theme. On user pages, the Admin link is hidden unless the authenticated user is an admin. This is enforced in `user.js` after `/me` resolves.
- The nav highlight follows the visible section using an IntersectionObserver in `script.js`. This helps users keep track of where they are as they scroll long views.

### 3. Styling, Components, and Responsiveness

We use a small custom CSS (no external frameworks) to remain lightweight and consistent with the brand. Key elements:

- The neon/purple theme is built using layered radial gradients and a linear base gradient. A grain overlay adds subtle texture.
- Forms are composed of labeled blocks using `.form-grid`, responsive to available width.
- Inputs are themed for consistency: `input[type=text|date|password|number].themed-number` share palette and focus rings.
- The `glass` component is a translucent panel with blur, borders, and shadows. All main panels sit inside `glass` containers for coherence.
- The “bottom dock” (nav + floor bar) ensures nav items never overlap the footer text by attaching the neon floor under the dock. Admin visibility is dynamic.
- The user chart sits in `.chart-wrap`, a darker panel to ensure candles and grid do not blend into the surrounding glow.

### 4. Client Code Structure

We split behavior into four scripts:

- `script.js` – The site’s general wiring including:
  - Dynamic year injection for `#year` and `.year` spans.
  - Bottom nav highlighting tied to scroll position via IntersectionObserver.
  - Magic Lab functionality: Backtest (posting `/backtest`), Live Signals (`/signals`), and Signal Chart (`/pine/signal`). It includes copy‑to‑clipboard helpers for startup commands.

- `user.js` – Implements the user panel.
  - Auth modal actions: signup and login (cookie‑based, uses `credentials:'include'`).
  - Favorites: add/remove and quick‑launch buttons using `/favorites` endpoints.
  - Suggestions: post “missing coin” via `/suggest_coin`.
  - Server status indicator: polls `/healthz` every 4 seconds to set Online/Offline.
  - Charting: requests `/pine/signal` for the current symbol, renders candles and markers on canvas, and shows a short trade log.
  - Alarm: a simple polling watch on the selected symbol via `/signals`, playing an audio beep on action changes (BUY/SELL/EXIT). The alarm purposefully keeps UX simple; parameter control lives with admins.
  - Range‑only Backtest: posts to `/backtest` using server defaults fetched from `/defaults`. This enforces admin guardrails.

- `admin.js` – Admin‑only helpers.
  - Users and Suggestions: lists and resolve actions via `/admin/users`, `/admin/suggestions`, and `/admin/suggestions/resolve`.
  - Engine Defaults: loads current defaults from `/defaults` and saves updates via `/admin/defaults` (admin‑only). Defaults include a locked timeframe and a JSON overrides blob used by user backtests.
  - Deep Backtest: posts to `/backtest/deep` for long‑range analysis.
  - For the upper half of `admin.html` (Magic Lab panels), the logic is reused from `script.js` by including it before `admin.js`.

- `login.js` – Focused on login flows.
  - Health check for `/healthz`, optional quick-fill buttons on localhost, and redirect to `user.html` after a successful login.

The approach keeps each page relatively self‑contained while avoiding duplication by reusing `script.js` for the Magic Lab UI.When in doubt, search for element IDs (e.g., `#run-backtest`, `#sc-fetch`) to see where they are wired.

### 5. Server Details

`server.py` is the single entry point. Its responsibilities:

- Serve the API and all static assets from a single origin at `/static`. This avoids CORS headaches for cookie flows, particularly for login and any stateful requests.
- Add CORS for configured origins via `CORS_ORIGINS`/`CORS_ORIGIN_REGEX` (defaults include localhost). We avoid wildcard CORS when cookies are involved.
- Initialize a small SQLite store inside `data_cache.db` for:
  - `users(id, email, name, pass_salt, pass_hash, is_admin, created_at)` - authentication and roles. The first created user becomes admin.
  - `sessions(sid, user_id, created_at, expires_at)` – HttpOnly cookie sessions keyed by `sid`.
  - `favorites(id, user_id, symbol)` – user’s quick‑access list.
  - `suggestions(id, user_id, text, created_at, resolved)` – coin requests from the user panel.
  - `settings(key, value)` – JSON store for engine defaults (`engine_defaults`).

Authentication is deliberately simple but secure enough for local/cloud dev:

- PBKDF2‑HMAC‑SHA256 password hashing with per‑user salt and constant‑time comparison.
- Sessions are random URL‑safe tokens with a seven‑day TTL in a cookie set to `HttpOnly` and `SameSite=Lax`.
- There are helpers to fetch the current user from the cookie (`get_user_from_request`), guard endpoints that require a user (`require_user`), and restrict admin endpoints (`require_admin`).

Endpoints overview (beyond engine):

- Auth: `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`, `GET /me`.
- Favorites: `GET /favorites`, `POST /favorites`, `DELETE /favorites?symbol=`.
- Suggestions: `POST /suggest_coin`.
- Admin: `GET /admin/users`, `GET /admin/suggestions`, `POST /admin/suggestions/resolve`.
- Defaults: `GET /defaults`, `POST /admin/defaults`.

Engine endpoints (already documented above):

- `GET /symbols` (from CCXT or fallback list), `GET /healthz`.
- `POST /backtest` – Backtest a list of symbols over a given range/timeframe with Pine Long overrides.
- `GET /signals` – Snapshot per symbol for the Live Signals table.
- `GET /pine/signal` – Chart data (candles/markers) and last action for a symbol/timeframe.
- `POST /backtest/deep` – A convenience endpoint that defaults to ~3 years of data if explicit dates are omitted.

### 6. Engine and Data Handling

The engine provides a pragmatic set of capabilities based on experience with intraday crypto signals.

- Data: `engine/data.py` and `engine/storage.py`
  - Fetch OHLCV from CCXT with paging for history (`fetch_ccxt_hist_range`) and lighter recent pulls (`fetch_ccxt_recent`).
  - Cache results in SQLite (`data_cache.db`) to speed subsequent requests.
  - Resampling and indexing are done with pandas in a forward‑compatible way (no chained indexing or deprecated frequency strings).

- Indicators: `engine/indicators.py`
  - Core utilities like Wilder RSI (`rsi_wilder`), used by engine and by `/signals` for quick metrics.

- Engine: `engine/pine_long.py`
  - A long‑only Pine v6‑style strategy implemented in Python. It encodes a set of parameters (RSI length and bounds, pivot widths, range filters, percent stop, wait/cooldown bars, etc.).
  - The engine provides two core methods: `backtest(symbol, df)` returning `{metrics, trades}`, and `signal_snapshot(symbol, df)` returning live state, a chart schema (candles/markers), and a summarized action.

Backtester flow (as used by `/backtest`):

1) Data acquisition for `(symbol, timeframe, start, end)` using cache + CCXT fallbacks.
2) Pre‑filters, HTF awareness, range checks.
3) Execution logic across bars, generating trades with type (enter/exit/exit_sl), timestamps, prices, and optional quantities.
4) Metrics such as total return, win rate, Sharpe, and max drawdown are derived from the trades and equity curve.

The chart endpoint `/pine/signal` augments candles with markers and pulls the latest price when possible (CCXT ticker) to render a more accurate right‑edge.

### 7. Guardrails and Permissions

User backtesting is intentionally kept simple: only date range can be selected. All engine parameters, timeframe, and overrides are defined centrally by admin defaults (`/defaults`). This separation prevents accidental drift in user runs and helps admins compare backtests apples‑to‑apples.

Users cannot modify server settings or engine parameters from the user panel. Alarms are per selected symbol with a single toggle. Favorites and suggestions are personal and harmless. Everything that can affect shared behavior (defaults, moderation, or analyses that may change team decisions) requires admin authentication.

### 8. Deployment, Hosting, and Android

Local: bind to all interfaces to reach from LAN (`HOST=0.0.0.0 PORT=8000 python server.py`) and open pages under `/static`. A small Windows Firewall rule may be required on first run. Cookies won’t work when opening pages as file:// — always use the server origin.

Tunnels: in cases without port forwarding or public IP, a tunnel (Cloudflare/Tailscale/ngrok) exposes the server securely. Because the frontend is served by the same FastAPI instance, authentication and CORS keep working unchanged over HTTPS.

Cloud: `deploy/cloud/compose.yml` runs the server behind Caddy with auto‑TLS. Point a DNS name to the box, set `SITE_HOST`, and `docker compose up -d` to go live.

Android: the app in `android version/` wraps the website in a WebView. It loads `/static/magic.html` or the public URL, with a config activity for setting the server base URL. Cleartext traffic is allowed for dev; switch to HTTPS for production.

### 9. Developer Workflow and Local Testing

1) Create and activate a virtual environment; install requirements.
2) Launch `server.py`. On first run there are no users; the first signup becomes admin. Defaults fall back to timeframe `3m` with empty overrides when not set.
3) Visit `static/login.html` and sign in. Use the admin to review users and suggestions and optionally change defaults.
4) Visit `static/user.html` and explore the user journey. Favorites are persisted per account.
5) For Magic Lab testing, go to `static/admin.html` which contains the full Backtester, Live Signals, and Chart along with admin controls.

If you see ?TypeError: Failed to fetch? in the browser, verify you are not loading the page as a file, confirm the server is online (visit `/healthz`), and ensure the browser origin is allowed by CORS (configure `CORS_ORIGINS`/`CORS_ORIGIN_REGEX`).

### 10. Extending Safely

A few guidelines make modifications predictable:

- Favor adding endpoints under a clear path (e.g., `/admin/...`, `/analytics/...`) and keep request/response JSON minimal yet explicit.
- When adding front‑end panels, reuse existing utility functions and CSS classes (`glass`, `.form-grid`, `.cta`) to maintain a consistent theme.
- For new persistent settings, store under the `settings` table as a JSON value keyed by a small, clear name (e.g., `engine_defaults_v2`).
- Prefer server‑side policy enforcement for guardrails; don’t rely solely on hidden fields or disabling controls in the UI.
- Keep large data fetches cache‑aware and resilient; the engine already degrades to local cache when CCXT fails.

### 11. Troubleshooting and Frequently Asked Questions

**Q: Login fails with “Failed to fetch.”**
— You are probably opening the HTML directly (file://) or the server is offline. Serve pages from `/static` and confirm `/healthz` returns `{ok:true}`.

**Q: Cookies don’t persist.**
— Cookies are set with `HttpOnly` and `SameSite=Lax` and require a real origin. Use `http://127.0.0.1:8000/static/...` locally.

**Q: Live price on chart looks stale.**
— If CCXT ticker fetch fails, we keep the candle close. This is normal when rate‑limited or offline; refresh later.

**Q: Can users change engine parameters?**
— No. Users can only provide date ranges. Admins set defaults in `admin.html`.

**Q: How do I add a new engine?**
— Create a new module under `engine/`, expose an interface mirroring `pine_long.py` (e.g., `backtest()`, `signal_snapshot()`), then add new endpoints `/engine2/backtest`, `/engine2/signal` and a thin UI panel.

**Q: How do I make the alarm send desktop notifications?**
— Add the Notifications API flow in `user.js` (permission request + `new Notification(...)`) and back it with a Service Worker if you want background persistence.

**Q: The admin link is visible to non‑admins.**
— The UI hides it client‑side after `/me`. For a belt‑and‑suspenders approach, you can also render server‑side or add a small `/whoami` inline script.

---

With these notes, a new developer should be able to clone, run, and extend Mystrix comfortably. The most important mental model is “single origin, two personas, one engine”: the single‑origin FastAPI host keeps authentication painless; the user/admin split preserves guardrails and expressivity; and the engine modules keep business logic encapsulated with clear, testable boundaries.



### Speed Mode (no code changes)
To make backtests feel instant on your machine (RTX 3060 12GB, 32GB RAM), use the helper script under `tools/`:

- One‑time: tune SQLite for fast local I/O
  - `python tools/perf.py tune-db --db data_cache.db`

- Warm caches once so repeat runs are local only
  - RAW (Bybit MAINNET → append‑only):
    - `python tools/perf.py warm-raw --symbols BTCUSDT,ETHUSDT,XAUTUSDT --tf 3m --start 2024-01-01 --end 2025-11-06`
  - Legacy cache (ccxt/Binance) for long historical ranges:
    - `python tools/perf.py warm-ccxt --symbols BTC/USDT,ETH/USDT --tf 3m --start 2022-01-01 --end 2025-11-06`

- Run API with multiple workers (parallel requests)
  - `python tools/perf.py run-api --host 127.0.0.1 --port 8000 --workers 6`

Optional environment (set once, restart terminal):
- `setx OMP_NUM_THREADS 12`
- `setx MKL_NUM_THREADS 12`
- `setx OPENBLAS_NUM_THREADS 12`
- `setx NUMEXPR_MAX_THREADS 12`

Tips:
- Keep server + DB on SSD/NVMe and leave API running to retain OS file cache.
- Use longer ranges from local cache to avoid network stalls on first fetch.
