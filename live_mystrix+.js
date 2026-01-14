(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  try {
    const host = location.hostname || "";
    if (!window.API_BASE && /(^|\.)wolfmystrix\.in$/i.test(host)) {
      window.API_BASE = "https://api.wolfmystrix.in";
    }
  } catch (_) {}
  const apiBase = () => {
    try { return window.API_BASE || location.origin; }
    catch (_) { return location.origin; }
  };

  const DEFAULT_ASSETS = [
    "BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","XRP/USDT","LTC/USDT","ADA/USDT","DOGE/USDT","MATIC/USDT","DOT/USDT",
    "AVAX/USDT","SHIB/USDT","APT/USDT","ARB/USDT","OP/USDT","SUI/USDT","PEPE/USDT","NEAR/USDT","ATOM/USDT","LINK/USDT"
  ];
  const MAX_ASSETS = 20;
  const LEVELS = [
    { level: 1, balance: 20, target: 6, ending: 26, risk: 4.5 },
    { level: 2, balance: 26, target: 8, ending: 34, risk: 6 },
    { level: 3, balance: 34, target: 10, ending: 44, risk: 8 },
    { level: 4, balance: 44, target: 14, ending: 58, risk: 10 },
    { level: 5, balance: 58, target: 18, ending: 76, risk: 14 },
    { level: 6, balance: 76, target: 22, ending: 98, risk: 18 },
    { level: 7, balance: 98, target: 28, ending: 126, risk: 22 },
    { level: 8, balance: 126, target: 38, ending: 164, risk: 28 },
    { level: 9, balance: 164, target: 48, ending: 212, risk: 38 },
    { level: 10, balance: 212, target: 64, ending: 276, risk: 48 },
    { level: 11, balance: 276, target: 82, ending: 358, risk: 64 },
    { level: 12, balance: 358, target: 108, ending: 466, risk: 82 },
    { level: 13, balance: 466, target: 140, ending: 606, risk: 108 },
    { level: 14, balance: 606, target: 182, ending: 788, risk: 140 },
    { level: 15, balance: 788, target: 236, ending: 1024, risk: 182 },
    { level: 16, balance: 1024, target: 308, ending: 1332, risk: 236 },
    { level: 17, balance: 1332, target: 400, ending: 1732, risk: 308 },
    { level: 18, balance: 1732, target: 520, ending: 2252, risk: 400 },
    { level: 19, balance: 2252, target: 674, ending: 2926, risk: 520 },
    { level: 20, balance: 2926, target: 878, ending: 3804, risk: 674 },
    { level: 21, balance: 3804, target: 1140, ending: 4944, risk: 878 },
    { level: 22, balance: 4944, target: 1482, ending: 6426, risk: 1140 },
    { level: 23, balance: 6426, target: 1928, ending: 8354, risk: 1482 },
    { level: 24, balance: 8354, target: 2506, ending: 10860, risk: 1928 },
    { level: 25, balance: 10860, target: 3256, ending: 14116, risk: 2506 },
    { level: 26, balance: 14116, target: 4234, ending: 18350, risk: 3256 },
    { level: 27, balance: 18350, target: 5504, ending: 23854, risk: 4234 },
    { level: 28, balance: 23854, target: 7156, ending: 31010, risk: 5504 },
    { level: 29, balance: 31010, target: 9302, ending: 40312, risk: 7156 },
    { level: 30, balance: 40312, target: 12092, ending: 52404, risk: 9302 },
  ];

  let hunterActive = false;
  let hunterTimer = null;
  let liveRunning = false;
  let tradeNo = 0;
  let toastTimer = null;

  let autoTradeActive = false;
  let autoConfig = null;
  let autoBalance = 0;
  let paperMode = true;
  const LIVE_STATUSES = new Set(["taken","closed","demo_closed","completed"]);
  const ENTRY_STATUSES = new Set(["taken"]);
  const AUTO_TRADE_MAX_AGE_MIN = 30;
  let lastHeartbeatTs = null;
  let assetOrder = [...DEFAULT_ASSETS];
  let enabledAssets = new Set(assetOrder.slice(0, 4));
  let allAssets = [...DEFAULT_ASSETS];
  let assetsLocked = false;
  const openTrades = new Map();
  let manualTradeSeq = 1;
  let baseBalance = null;
  let pnlSeries = [];
  let lastPnlValue = null;
  let lastSuggestions = [];
  const priceCache = new Map();
  let pricePollTimer = null;
  let priceRefreshTimer = null;
  let lastPriceFetch = 0;
  let priceFeedDisabledUntil = 0;
  let priceFeedWarned = false;
  const sltpOverrides = new Map();
  const FAVORITES_KEY = "mystrixFavorites";
  const AUTO_UNIVERSE_KEY = "mystrixAutoUniverse";
  let autoUniverseEnabled = true;
  let autoUniverseBlockedWarned = false;
  let tradingStopDisabledUntil = 0;
  let tradingStopWarned = false;
  let scanInFlight = false;
  let scanAbortController = null;
  const SCAN_TIMEOUT_MS = 20000;
  let favorites = new Set();

  const assetList = $("#asset-list");
  const assetSearch = $("#asset-search");
  const assetAddBtn = $("#asset-add");
  const assetOptions = $("#asset-options");
  const selectAllBtn = $("#select-all");
  const clearAllBtn = $("#clear-all");
  const suggestedList = $("#suggested-list");
  const suggestedStatus = $("#suggested-status");
  const suggestedRefresh = $("#refresh-suggested");
  const autoUniverseToggle = $("#auto-universe-toggle");
  const favoritesList = $("#favorites-list");
  const favoritesEmpty = $("#favorites-empty");
  const openTradesBody = $("#open-trades-body");
  const manualTradeForm = $("#manual-trade-form");
  const manualSymbol = $("#manual-symbol");
  const manualSide = $("#manual-side");
  const manualSize = $("#manual-size");
  const manualLeverage = $("#manual-leverage");
  const manualEntry = $("#manual-entry");
  const manualStop = $("#manual-sl");
  const manualTarget = $("#manual-tp");
  const liveOrderForm = $("#live-order-form");
  const liveOrderSymbol = $("#live-order-symbol");
  const liveOrderSide = $("#live-order-side");
  const liveOrderNotional = $("#live-order-notional");
  const levelBadge = $("#level-badge");
  const riskBadge = $("#risk-badge");
  const levelCurrent = $("#level-current");
  const levelBalance = $("#level-balance");
  const levelTarget = $("#level-target");
  const levelRisk = $("#level-risk");
  const levelEnding = $("#level-ending");
  const pnlChart = $("#pnl-chart");
  const pnlTotal = $("#pnl-total");
  const liveLog = $("#live-log");
  const rejectLog = $("#reject-log");
  const autoLog = $("#auto-log");
  const toastStack = $("#toast-stack");
  const balanceAmount = $("#balance-amount");
  const balanceStatus = $("#balance-status");
  const balanceBreakdown = $("#balance-breakdown");
  const paperToggle = $("#paper-toggle");
  const refreshBalanceBtn = $("#refresh-balance");
  const statusPill = $("#live-status");
  const startBtn = $("#start-live");
  const hunterToggle = $("#hunter-toggle");
  const statusFeed = $("#status-feed");
  const statusCards = {
    live: document.querySelector("[data-status='live']"),
    hunter: document.querySelector("[data-status='hunter']"),
    auto: document.querySelector("[data-status='auto']"),
  };
  const heartbeatIndicator = $("#heartbeat-indicator");
  const heartbeatLabel = $("#heartbeat-label");
  const pulseFeed = $("#pulse-feed");
  const pulseMeta = $("#heartbeat-meta");
  const demoBtn = $("#demo-trade-btn");

  const thresholdSlider = $("#live-threshold");
  const thresholdValue = $("#live-threshold-val");
  if (thresholdSlider && thresholdValue) {
    const update = () => thresholdValue.textContent = Number(thresholdSlider.value).toFixed(2);
    thresholdSlider.addEventListener("input", update);
    update();
  }

  function normalizeSymbol(raw) {
    const cleaned = String(raw || "").trim().toUpperCase();
    if (!cleaned) return "";
    if (cleaned.includes("/")) return cleaned;
    if (cleaned.endsWith("USDT")) {
      return `${cleaned.slice(0, -4)}/USDT`;
    }
    return `${cleaned}/USDT`;
  }

  function updatePriceCache(prices) {
    if (!prices || typeof prices !== "object") return;
    Object.entries(prices).forEach(([sym, px]) => {
      const norm = normalizeSymbol(sym);
      const val = Number(px);
      if (!norm || !Number.isFinite(val) || val <= 0) return;
      priceCache.set(norm, val);
    });
  }

  function getCachedPrice(sym) {
    const norm = normalizeSymbol(sym);
    if (!norm) return null;
    const val = priceCache.get(norm);
    return Number.isFinite(val) ? val : null;
  }

  function queuePriceRefresh() {
    if (priceRefreshTimer) return;
    priceRefreshTimer = setTimeout(() => {
      priceRefreshTimer = null;
      fetchMarketPrices().catch(()=>{});
    }, 500);
  }

  async function fetchMarketPrices() {
    const symbols = Array.from(openTrades.values()).map((t) => t.symbol).filter(Boolean);
    const unique = Array.from(new Set(symbols.map((s) => normalizeSymbol(s)).filter(Boolean)));
    if (!unique.length) return;
    const now = Date.now();
    if (now - lastPriceFetch < 4000) return;
    if (priceFeedDisabledUntil && now < priceFeedDisabledUntil) return;
    lastPriceFetch = now;
    try {
      const res = await fetch(`${apiBase()}/market/prices`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols: unique }),
      });
      let data = {};
      try {
        data = await res.json();
      } catch (_) {
        data = {};
      }
      if (!res.ok) {
        if (res.status === 404) {
          priceFeedDisabledUntil = Date.now() + 60000;
          if (!priceFeedWarned) {
            addAutoLog("Price feed unavailable (restart server to enable /market/prices).");
            priceFeedWarned = true;
          }
          return;
        }
        throw new Error(data.detail || `Price fetch failed (${res.status})`);
      }
      priceFeedWarned = false;
      priceFeedDisabledUntil = 0;
      updatePriceCache(data.prices || {});
      renderOpenTrades();
    } catch (err) {
      if (!priceFeedWarned) {
        addAutoLog(`Price feed error: ${err.message || err}`);
      }
    }
  }

  function ensurePricePolling() {
    if (pricePollTimer) return;
    pricePollTimer = setInterval(() => {
      if (!openTrades.size) return;
      fetchMarketPrices().catch(()=>{});
    }, 15000);
  }

  function renderAssetOptions() {
    if (!assetOptions) return;
    assetOptions.innerHTML = "";
    allAssets.forEach((sym) => {
      const opt = document.createElement("option");
      opt.value = sym;
      assetOptions.appendChild(opt);
    });
  }

  function loadFavorites() {
    try {
      const raw = localStorage.getItem(FAVORITES_KEY);
      const parsed = JSON.parse(raw || "[]");
      if (Array.isArray(parsed)) favorites = new Set(parsed);
    } catch (_) {
      favorites = new Set();
    }
  }

  function saveFavorites() {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(Array.from(favorites)));
  }

  function renderFavorites() {
    if (!favoritesList || !favoritesEmpty) return;
    const list = Array.from(favorites);
    if (!list.length) {
      favoritesEmpty.style.display = "block";
      favoritesList.innerHTML = "";
      return;
    }
    favoritesEmpty.style.display = "none";
    favoritesList.innerHTML = "";
    list.sort().forEach((sym) => {
      const chip = document.createElement("div");
      chip.className = "favorite-chip";
      chip.innerHTML = `
        <span>${sym}</span>
        <button type="button" data-fav-remove="${sym}">x</button>
      `;
      favoritesList.appendChild(chip);
    });
  }

  function toggleFavorite(sym) {
    if (!sym) return;
    if (favorites.has(sym)) favorites.delete(sym);
    else favorites.add(sym);
    saveFavorites();
    renderFavorites();
    renderAssets();
  }

  function renderAssets() {
    assetList.innerHTML = "";
    if (!enabledAssets.size && assetOrder.length) {
      enabledAssets.add(assetOrder[0]);
    }
    assetOrder.forEach((sym) => {
      const wrap = document.createElement("label");
      wrap.className = "asset-option";
      const checked = enabledAssets.has(sym);
      const fav = favorites.has(sym);
      wrap.innerHTML = `
        <input type="checkbox" data-symbol="${sym}" ${checked ? "checked" : ""}/>
        <span>${sym}</span>
        <button type="button" class="favorite-toggle ${fav ? "active" : ""}" data-favorite="${sym}">${fav ? "★" : "☆"}</button>
        <button type="button" class="asset-remove" data-remove="${sym}">x</button>
      `;
      const checkbox = wrap.querySelector("input");
      const removeBtn = wrap.querySelector(".asset-remove");
      const favBtn = wrap.querySelector(".favorite-toggle");
      if (checkbox) {
        checkbox.disabled = assetsLocked;
        checkbox.addEventListener("change", (e) => {
          if (e.target.checked) enabledAssets.add(sym);
          else enabledAssets.delete(sym);
        });
      }
      if (removeBtn) {
        removeBtn.disabled = assetsLocked;
        removeBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          removeAsset(sym);
        });
      }
      if (favBtn) {
        favBtn.disabled = assetsLocked;
        favBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          toggleFavorite(sym);
        });
      }
      assetList.appendChild(wrap);
    });
  }

  function addAsset(raw) {
    const sym = normalizeSymbol(raw);
    if (!sym) return;
    if (assetOrder.includes(sym)) {
      pushStatus(`Asset already added: ${sym}`, "warn");
      return;
    }
    if (assetOrder.length >= MAX_ASSETS) {
      pushStatus(`Asset limit reached (${MAX_ASSETS}).`, "warn");
      return;
    }
    assetOrder.push(sym);
    enabledAssets.add(sym);
    renderAssets();
    if (lastSuggestions.length) renderSuggestions(lastSuggestions);
    if (assetSearch) assetSearch.value = "";
    pushStatus(`Asset added: ${sym}`, "run");
  }

  function removeAsset(sym) {
    assetOrder = assetOrder.filter((s) => s !== sym);
    enabledAssets.delete(sym);
    if (favorites.has(sym)) {
      favorites.delete(sym);
      saveFavorites();
      renderFavorites();
    }
    renderAssets();
    if (lastSuggestions.length) renderSuggestions(lastSuggestions);
    pushStatus(`Asset removed: ${sym}`, "warn");
  }

  async function loadSymbols() {
    try {
      const res = await fetch(`${apiBase()}/symbols`);
      if (!res.ok) throw new Error("symbols");
      const data = await res.json();
      if (Array.isArray(data.symbols) && data.symbols.length) {
        allAssets = data.symbols;
        renderAssetOptions();
      }
    } catch (_) {}
  }

  function renderSuggestions(items) {
    if (!suggestedList) return;
    suggestedList.innerHTML = "";
    if (!items.length) {
      if (suggestedStatus) suggestedStatus.textContent = "No suggestions available.";
      return;
    }
    items.forEach((item) => {
      const sym = normalizeSymbol(item.symbol);
      const wrap = document.createElement("div");
      wrap.className = "suggested-item";
      const added = assetOrder.includes(sym);
      wrap.innerHTML = `
        <strong>${sym}</strong>
        <small>Range ${item.range_pct}% | Move ${item.change_pct}%</small>
        <button type="button" data-suggest-add="${sym}" ${added || assetsLocked ? "disabled" : ""}>
          ${added ? "Added" : "Add"}
        </button>
      `;
      suggestedList.appendChild(wrap);
    });
  }

  function loadAutoUniverse() {
    const raw = localStorage.getItem(AUTO_UNIVERSE_KEY);
    if (raw === null) autoUniverseEnabled = true;
    else autoUniverseEnabled = raw === "true";
    if (autoUniverseToggle) autoUniverseToggle.checked = autoUniverseEnabled;
  }

  function setAutoUniverse(enabled) {
    autoUniverseEnabled = enabled;
    localStorage.setItem(AUTO_UNIVERSE_KEY, String(enabled));
    if (autoUniverseEnabled && lastSuggestions.length) {
      applyUniverseSuggestions(lastSuggestions);
    }
  }

  function applyUniverseSuggestions(items) {
    if (assetsLocked) {
      if (!autoUniverseBlockedWarned) {
        pushStatus("Auto sync paused while live feed is running.", "warn");
        autoUniverseBlockedWarned = true;
      }
      return;
    }
    autoUniverseBlockedWarned = false;
    const picks = items.map((item) => normalizeSymbol(item.symbol)).filter(Boolean);
    if (!picks.length) return;
    const unique = [];
    picks.forEach((sym) => {
      if (!unique.includes(sym)) unique.push(sym);
    });
    const limited = unique.slice(0, MAX_ASSETS);
    const same = limited.length === assetOrder.length && limited.every((sym, idx) => assetOrder[idx] === sym);
    assetOrder = limited;
    enabledAssets = new Set(limited);
    renderAssets();
    renderSuggestions(lastSuggestions);
    if (!same) pushStatus("Assets synced to universe suggestions.", "run");
  }

  async function loadSuggestions() {
    if (suggestedStatus) suggestedStatus.textContent = "Scanning universe...";
    try {
      const res = await fetch(`${apiBase()}/universe/suggestions?limit=${MAX_ASSETS}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Suggestion fetch failed");
      lastSuggestions = data.suggestions || [];
      renderSuggestions(lastSuggestions);
      if (autoUniverseEnabled) applyUniverseSuggestions(lastSuggestions);
      if (suggestedStatus && data.meta?.as_of) {
        const stamp = toIST(data.meta.as_of);
        suggestedStatus.textContent = `Updated ${stamp || "now"} (IST)`;
      }
    } catch (err) {
      if (suggestedStatus) suggestedStatus.textContent = "Unable to load suggestions.";
      addAutoLog(`Universe scan error: ${err.message || err}`);
    }
  }

  function levelForBalance(balance) {
    if (!Number.isFinite(balance) || !LEVELS.length) return null;
    let current = LEVELS[0];
    for (const lvl of LEVELS) {
      if (balance >= lvl.balance) current = lvl;
    }
    return current;
  }

  function updateLevelStats(balance) {
    const lvl = levelForBalance(balance);
    if (!lvl) return;
    if (levelBadge) levelBadge.textContent = `Level ${lvl.level}`;
    if (riskBadge) riskBadge.textContent = `Risk $${lvl.risk.toFixed(2)}`;
    if (levelCurrent) levelCurrent.textContent = `Level ${lvl.level}`;
    if (levelBalance) levelBalance.textContent = `$${lvl.balance.toFixed(2)}`;
    if (levelTarget) levelTarget.textContent = `$${lvl.target.toFixed(2)}`;
    if (levelRisk) levelRisk.textContent = `$${lvl.risk.toFixed(2)}`;
    if (levelEnding) levelEnding.textContent = `$${lvl.ending.toFixed(2)}`;
    if (manualSize && (!manualSize.value || Number(manualSize.value) <= 0)) {
      manualSize.value = lvl.risk.toFixed(2);
    }
  }

  function pnlSeriesKey() {
    return paperMode ? "mystrixPnlSeriesPaper" : "mystrixPnlSeriesLive";
  }

  function baseBalanceKey() {
    return paperMode ? "mystrixBaseBalancePaper" : "mystrixBaseBalanceLive";
  }

  function loadPnlState() {
    const baseRaw = localStorage.getItem(baseBalanceKey());
    const seriesRaw = localStorage.getItem(pnlSeriesKey());
    baseBalance = baseRaw ? Number(baseRaw) : null;
    pnlSeries = [];
    try {
      const parsed = JSON.parse(seriesRaw || "[]");
      if (Array.isArray(parsed)) pnlSeries = parsed;
    } catch (_) {
      pnlSeries = [];
    }
    lastPnlValue = pnlSeries.length ? pnlSeries[pnlSeries.length - 1].pnl : null;
    if (pnlTotal && lastPnlValue !== null) {
      pnlTotal.textContent = `$${Number(lastPnlValue).toFixed(2)}`;
    }
    resizePnlCanvas();
  }

  function savePnlState() {
    localStorage.setItem(pnlSeriesKey(), JSON.stringify(pnlSeries));
    if (baseBalance !== null && Number.isFinite(baseBalance)) {
      localStorage.setItem(baseBalanceKey(), String(baseBalance));
    }
  }

  function updatePnlSeries(balance) {
    if (!Number.isFinite(balance)) return;
    if (baseBalance === null) {
      baseBalance = balance;
      savePnlState();
    }
    const pnl = balance - baseBalance;
    if (lastPnlValue === null || Math.abs(pnl - lastPnlValue) >= 0.01) {
      pnlSeries.push({ ts: Date.now(), pnl: Number(pnl.toFixed(2)) });
      if (pnlSeries.length > 160) pnlSeries = pnlSeries.slice(-160);
      lastPnlValue = pnl;
      savePnlState();
    }
    if (pnlTotal) pnlTotal.textContent = `$${pnl.toFixed(2)}`;
    drawPnlChart();
  }

  function drawPnlChart() {
    if (!pnlChart) return;
    const ctx = pnlChart.getContext("2d");
    if (!ctx) return;
    const w = pnlChart.width;
    const h = pnlChart.height;
    ctx.clearRect(0, 0, w, h);
    const series = pnlSeries.length ? pnlSeries : [{ ts: Date.now(), pnl: 0 }];
    const vals = series.map((p) => p.pnl);
    let min = Math.min(...vals);
    let max = Math.max(...vals);
    if (min === max) {
      min -= 1;
      max += 1;
    }
    const pad = 20;
    const xStep = series.length > 1 ? (w - pad * 2) / (series.length - 1) : 0;
    const color = (series[series.length - 1]?.pnl || 0) >= 0 ? "#8dffd2" : "#ff9f95";

    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad, h - pad);
    ctx.lineTo(w - pad, h - pad);
    ctx.stroke();

    if (min < 0 && max > 0) {
      const zeroY = pad + (1 - (0 - min) / (max - min)) * (h - pad * 2);
      ctx.strokeStyle = "rgba(255,255,255,0.15)";
      ctx.beginPath();
      ctx.moveTo(pad, zeroY);
      ctx.lineTo(w - pad, zeroY);
      ctx.stroke();
    }

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    series.forEach((point, idx) => {
      const x = pad + xStep * idx;
      const y = pad + (1 - (point.pnl - min) / (max - min)) * (h - pad * 2);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  function resizePnlCanvas() {
    if (!pnlChart) return;
    const width = pnlChart.clientWidth || 520;
    const height = pnlChart.clientHeight || 220;
    if (pnlChart.width !== width || pnlChart.height !== height) {
      pnlChart.width = width;
      pnlChart.height = height;
    }
    drawPnlChart();
  }

  function renderOpenTrades() {
    if (!openTradesBody) return;
    const trades = Array.from(openTrades.values());
    if (!trades.length) {
      openTradesBody.innerHTML = `<tr><td colspan="14" style="text-align:center;opacity:.6;">No open trades.</td></tr>`;
      return;
    }
    trades.sort((a, b) => (a.opened_at_ts || 0) - (b.opened_at_ts || 0));
    openTradesBody.innerHTML = "";
    trades.forEach((t) => {
      const row = document.createElement("tr");
      const opened = t.opened_at ? toIST(t.opened_at) : "--";
      const leverage = Number(t.leverage || 0);
      let margin = Number(t.margin || 0);
      const levLabel = Number.isFinite(leverage) && leverage > 0 ? `${leverage.toFixed(2)}x` : "--";
      const slVal = Number(t.stop_loss || 0);
      const tpVal = Number(t.take_profit || 0);
      const slLabel = Number.isFinite(slVal) && slVal > 0 ? fmt(slVal) : "--";
      const tpLabel = Number.isFinite(tpVal) && tpVal > 0 ? fmt(tpVal) : "--";
      const slBtn = `<button class="trade-action trade-mini" data-set-sl="${t.key}">${slLabel === "--" ? "Add" : "Edit"}</button>`;
      const tpBtn = `<button class="trade-action trade-mini" data-set-tp="${t.key}">${tpLabel === "--" ? "Add" : "Edit"}</button>`;
      const slCell = `<span class="sl-tp-cell"><span>${slLabel}</span>${slBtn}</span>`;
      const tpCell = `<span class="sl-tp-cell"><span>${tpLabel}</span>${tpBtn}</span>`;
      const entry = Number(t.entry_price || 0);
      const size = Number(t.size || 0);
      const lastCached = getCachedPrice(t.symbol);
      const lastRaw = Number(t.last_price || 0);
      const lastPx = Number.isFinite(lastCached) ? lastCached : (Number.isFinite(lastRaw) && lastRaw > 0 ? lastRaw : null);
      if (!(Number.isFinite(margin) && margin > 0) && Number.isFinite(leverage) && leverage > 0 && size > 0 && lastPx) {
        margin = (size * lastPx) / leverage;
      }
      const marginLabel = Number.isFinite(margin) && margin > 0 ? fmt(margin, 2) : "--";
      let floatPnl = Number.isFinite(t.unrealized_pnl) ? Number(t.unrealized_pnl) : null;
      if (floatPnl === null && entry > 0 && lastPx && size > 0) {
        const side = String(t.side || "").toLowerCase();
        const isShort = side === "short" || side === "sell";
        const ret = isShort ? (entry - lastPx) / entry : (lastPx - entry) / entry;
        floatPnl = ret * size;
      }
      const lastLabel = lastPx ? fmt(lastPx, 4) : "--";
      const pnlLabel = floatPnl === null ? "--" : fmt(floatPnl, 2);
      const pnlClass = floatPnl === null ? "" : (floatPnl > 0 ? "float-pos" : (floatPnl < 0 ? "float-neg" : ""));
      let action = `<span>--</span>`;
      if (t.source === "manual") {
        action = `<div class="trade-actions"><button class="trade-action" data-close="${t.key}">Close Px</button><button class="trade-action" data-close-mkt="${t.key}">Close MKT</button></div>`;
      } else if (t.source === "paper" || t.source === "bybit") {
        action = `<div class="trade-actions"><button class="trade-action" data-close-mkt="${t.key}">Close MKT</button></div>`;
      }
      row.innerHTML = `
        <td>${t.id}</td>
        <td>${t.source}</td>
        <td>${t.symbol}</td>
        <td>${t.side}</td>
        <td>${fmt(t.entry_price)}</td>
        <td>${slCell}</td>
        <td>${tpCell}</td>
        <td>${fmt(t.size, 2)}</td>
        <td>${levLabel}</td>
        <td>${marginLabel}</td>
        <td>${lastLabel}</td>
        <td class="${pnlClass}">${pnlLabel}</td>
        <td>${opened}</td>
        <td>${action}</td>
      `;
      openTradesBody.appendChild(row);
    });
  }

  function upsertOpenTrade(trade, render = true) {
    openTrades.set(trade.key, trade);
    if (render) renderOpenTrades();
    queuePriceRefresh();
  }

  function removeOpenTrade(key) {
    openTrades.delete(key);
    sltpOverrides.delete(key);
    renderOpenTrades();
    queuePriceRefresh();
  }

  function syncPaperTrades(data) {
    if (!data) return;
    if (data.prices) updatePriceCache(data.prices);
    const active = Array.isArray(data.active) ? data.active : [];
    const activeKeys = new Set();
    active.forEach((t) => {
      const key = `paper:${t.id}`;
      activeKeys.add(key);
      const lastPrice = getCachedPrice(t.symbol);
      const override = sltpOverrides.get(key);
      upsertOpenTrade({
        key,
        id: t.id,
        symbol: t.symbol,
        side: t.side === "buy" ? "long" : t.side,
        entry_price: Number(t.entry_price || 0),
        size: Number(t.size || 0),
        last_price: lastPrice || undefined,
        stop_loss: override?.stop_loss || null,
        take_profit: override?.take_profit || null,
        source: "paper",
        opened_at: t.opened_at,
        opened_at_ts: t.opened_at ? Date.parse(t.opened_at) : Date.now(),
      }, false);
    });
    Array.from(openTrades.keys()).forEach((key) => {
      if (key.startsWith("paper:") && !activeKeys.has(key)) removeOpenTrade(key);
    });
    renderOpenTrades();
  }

  function trackSignalTrade(evt) {
    if (!evt || !evt.status) return;
    const key = evt.trade_no ? `signal:${evt.trade_no}` : `signal:${Date.now()}`;
    if (evt.status === "taken") {
      upsertOpenTrade({
        key,
        id: evt.trade_no || "--",
        symbol: evt.symbol,
        side: evt.divergence === "bull" ? "long" : "short",
        entry_price: Number(evt.entry_price || 0),
        size: Number(evt.trade_size || 0),
        source: "signal",
        opened_at: evt.entry_time,
        opened_at_ts: evt.entry_time ? Date.parse(evt.entry_time) : Date.now(),
      });
      return;
    }
    if (LIVE_STATUSES.has(evt.status)) {
      removeOpenTrade(key);
    }
  }

  renderAssetOptions();
  loadFavorites();
  renderAssets();
  renderFavorites();
  loadSymbols();
  loadPnlState();
  loadAutoUniverse();
  loadSuggestions();
  ensurePricePolling();

  assetAddBtn?.addEventListener("click", () => addAsset(assetSearch?.value));
  assetSearch?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addAsset(assetSearch.value);
    }
  });

  autoUniverseToggle?.addEventListener("change", (e) => {
    setAutoUniverse(Boolean(e.target.checked));
  });

  suggestedRefresh?.addEventListener("click", () => loadSuggestions());
  suggestedList?.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-suggest-add]");
    if (!btn) return;
    const sym = btn.getAttribute("data-suggest-add");
    if (!sym) return;
    addAsset(sym);
  });

  favoritesList?.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-fav-remove]");
    if (!btn) return;
    const sym = btn.getAttribute("data-fav-remove");
    if (!sym) return;
    toggleFavorite(sym);
  });

  selectAllBtn?.addEventListener("click", () => {
    enabledAssets = new Set(assetOrder);
    renderAssets();
  });
  clearAllBtn?.addEventListener("click", () => {
    enabledAssets.clear();
    renderAssets();
  });

  setInterval(() => {
    if (autoUniverseEnabled) loadSuggestions();
  }, 300000);

  manualTradeForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    const symbol = normalizeSymbol(manualSymbol?.value);
    const side = (manualSide?.value || "long").toLowerCase();
    const size = Number(manualSize?.value || 0);
    const leverage = Number(manualLeverage?.value || 1);
    const entry = Number(manualEntry?.value || 0);
    const stopRaw = Number(manualStop?.value || 0);
    const targetRaw = Number(manualTarget?.value || 0);
    if (!symbol || !Number.isFinite(size) || size <= 0 || !Number.isFinite(entry) || entry <= 0) {
      pushStatus("Manual trade needs symbol, size, and entry price.", "warn");
      return;
    }
    if (!Number.isFinite(leverage) || leverage <= 0) {
      pushStatus("Manual trade needs a valid leverage.", "warn");
      return;
    }
    const stopLoss = Number.isFinite(stopRaw) && stopRaw > 0 ? stopRaw : null;
    const takeProfit = Number.isFinite(targetRaw) && targetRaw > 0 ? targetRaw : null;
    const margin = size / leverage;
    const id = `M${manualTradeSeq++}`;
    upsertOpenTrade({
      key: `manual:${id}`,
      id,
      symbol,
      side,
      entry_price: entry,
      size,
      leverage,
      margin,
      stop_loss: stopLoss,
      take_profit: takeProfit,
      source: "manual",
      opened_at: new Date().toISOString(),
      opened_at_ts: Date.now(),
    });
    if (manualSymbol) manualSymbol.value = "";
    if (manualEntry) manualEntry.value = "";
    if (manualStop) manualStop.value = "";
    if (manualTarget) manualTarget.value = "";
    pushStatus(`Manual trade logged: ${symbol} ${side}`, "run");
  });

  function closeManualTrade(trade, exit, tag) {
    const entry = Number(trade.entry_price || 0);
    const size = Number(trade.size || 0);
    const ret = trade.side === "short" ? (entry - exit) / entry : (exit - entry) / entry;
    const pnl = ret * size;
    removeOpenTrade(trade.key);
    const note = tag ? ` ${tag}` : "";
    addAutoLog(`Manual close ${trade.symbol} ${trade.side} pnl=${pnl.toFixed(2)}${note}`);
    pushStatus(`Manual trade closed: ${trade.symbol} pnl ${pnl.toFixed(2)}`, pnl >= 0 ? "run" : "warn");
  }

  openTradesBody?.addEventListener("click", async (e) => {
    const setBtn = e.target.closest("button[data-set-sl], button[data-set-tp]");
    if (setBtn) {
      const key = setBtn.getAttribute("data-set-sl") || setBtn.getAttribute("data-set-tp");
      const isStop = Boolean(setBtn.getAttribute("data-set-sl"));
      const trade = key ? openTrades.get(key) : null;
      if (!trade) return;
      const label = isStop ? "Stop loss" : "Take profit";
      const current = isStop ? trade.stop_loss : trade.take_profit;
      const promptVal = prompt(`${label} price for ${trade.symbol} (${trade.side})`, current ? String(current) : "");
      if (promptVal === null) return;
      const next = Number(promptVal);
      if (!Number.isFinite(next)) {
        pushStatus(`Invalid ${label} price.`, "warn");
        return;
      }
      const nextValue = next <= 0 ? null : next;
      if (trade.source === "bybit") {
        if (paperMode) {
          pushStatus("Disable paper mode before updating live SL/TP.", "warn");
          return;
        }
        const cfg = autoConfig || ensureAutotraderConfig();
        if (!cfg) {
          pushStatus("Configure AutoTrader before updating SL/TP.", "warn");
          return;
        }
        const payload = {
          base_url: cfg.base || cfg.base_url,
          api_key: cfg.api || cfg.api_key,
          api_secret: cfg.secret || cfg.api_secret,
          exchange: cfg.exchange || "bybit",
          account_type: cfg.account_type,
          margin_mode: cfg.margin_mode,
          environment: cfg.environment,
          symbol: trade.symbol,
          side: trade.side,
          stop_loss: isStop ? (nextValue === null ? 0 : nextValue) : undefined,
          take_profit: !isStop ? (nextValue === null ? 0 : nextValue) : undefined,
          confirm: true,
        };
        const now = Date.now();
        if (tradingStopDisabledUntil && now < tradingStopDisabledUntil) {
          pushStatus("Trading stop unavailable (restart server).", "warn");
          return;
        }
        try {
          const res = await fetch(`${apiBase()}/autotrader/trading_stop`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          let data = {};
          try {
            data = await res.json();
          } catch (_) {
            data = {};
          }
          if (!res.ok) {
            if (res.status === 404) {
              tradingStopDisabledUntil = Date.now() + 60000;
              if (!tradingStopWarned) {
                addAutoLog("Trading stop endpoint missing (restart server to enable SL/TP).");
                tradingStopWarned = true;
              }
              pushStatus("Trading stop unavailable (restart server).", "warn");
              return;
            }
            throw new Error(data.detail || "Trading stop failed");
          }
          tradingStopWarned = false;
          tradingStopDisabledUntil = 0;
          if (isStop) trade.stop_loss = nextValue;
          else trade.take_profit = nextValue;
          sltpOverrides.set(trade.key, {
            stop_loss: trade.stop_loss || null,
            take_profit: trade.take_profit || null,
          });
          openTrades.set(trade.key, trade);
          renderOpenTrades();
          const logVal = nextValue === null ? "cleared" : nextValue;
          addAutoLog(`${label} set on Bybit for ${trade.symbol} ${trade.side} @ ${logVal}`);
          pushStatus(`${label} updated on Bybit.`, "run");
        } catch (err) {
          addAutoLog(`${label} error: ${err.message || err}`);
          pushStatus(`${label} error: ${err.message || err}`, "err");
        }
        return;
      }
      if (isStop) trade.stop_loss = nextValue;
      else trade.take_profit = nextValue;
      if (trade.source !== "manual") {
        sltpOverrides.set(trade.key, {
          stop_loss: trade.stop_loss || null,
          take_profit: trade.take_profit || null,
        });
      }
      openTrades.set(trade.key, trade);
      renderOpenTrades();
      const logVal = nextValue === null ? "cleared" : nextValue;
      addAutoLog(`${label} set for ${trade.symbol} ${trade.side} @ ${logVal}`);
      if (trade.source !== "manual") {
        pushStatus(`${label} updated (paper only).`, "warn");
      } else {
        pushStatus(`${label} updated.`, "run");
      }
      return;
    }
    const mktBtn = e.target.closest("button[data-close-mkt]");
    if (mktBtn) {
      const key = mktBtn.getAttribute("data-close-mkt");
      const trade = openTrades.get(key);
      if (!trade) return;
      if (trade.source === "manual") {
        let exit = getCachedPrice(trade.symbol);
        if (!exit) {
          await fetchMarketPrices().catch(()=>{});
          exit = getCachedPrice(trade.symbol);
        }
        if (!exit || exit <= 0) {
          pushStatus("No live price available for market close.", "warn");
          return;
        }
        closeManualTrade(trade, exit, "(market)");
        return;
      }
      if (trade.source === "paper") {
        if (!confirm(`Close PAPER ${trade.symbol} at market?`)) return;
        try {
          const res = await fetch(`${apiBase()}/paper/close`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ trade_id: Number(trade.id) }),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Paper close failed");
          removeOpenTrade(trade.key);
          const pnl = Number(data.trade?.pnl || 0);
          addAutoLog(`Paper close ${trade.symbol} pnl=${pnl.toFixed(2)}`);
          pushStatus(`Paper trade closed: ${trade.symbol} pnl ${pnl.toFixed(2)}`, pnl >= 0 ? "run" : "warn");
          fetchBalance(autoConfig || ensureAutotraderConfig(), false).catch(()=>{});
        } catch (err) {
          addAutoLog(`Paper close error: ${err.message || err}`);
          pushStatus(`Paper close error: ${err.message || err}`, "err");
        }
        return;
      }
      if (trade.source === "bybit") {
        if (paperMode) {
          pushStatus("Disable paper mode before closing live positions.", "warn");
          return;
        }
        const cfg = autoConfig || ensureAutotraderConfig();
        if (!cfg) {
          pushStatus("Configure AutoTrader before closing live positions.", "warn");
          return;
        }
        const qty = Number(trade.size || 0);
        if (!Number.isFinite(qty) || qty <= 0) {
          pushStatus("No valid size for market close.", "warn");
          return;
        }
        const closeSide = trade.side === "short" ? "buy" : "sell";
        if (!confirm(`Close LIVE ${trade.symbol} ${trade.side} with market order?`)) return;
        const payload = {
          base_url: cfg.base || cfg.base_url,
          api_key: cfg.api || cfg.api_key,
          api_secret: cfg.secret || cfg.api_secret,
          exchange: cfg.exchange || "bybit",
          account_type: cfg.account_type,
          margin_mode: cfg.margin_mode,
          environment: cfg.environment,
          symbol: trade.symbol,
          side: closeSide,
          qty,
          reduce_only: true,
          confirm: true,
        };
        try {
          const res = await fetch(`${apiBase()}/autotrader/order`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Live close failed");
          addAutoLog(`Live close sent: ${trade.symbol} ${closeSide} qty=${qty}`);
          pushStatus(`Live close sent: ${trade.symbol}`, "run");
          fetchPositions(cfg).catch(()=>{});
        } catch (err) {
          addAutoLog(`Live close error: ${err.message || err}`);
          pushStatus(`Live close error: ${err.message || err}`, "err");
        }
        return;
      }
      return;
    }
    const btn = e.target.closest("button[data-close]");
    if (!btn) return;
    const key = btn.getAttribute("data-close");
    const trade = openTrades.get(key);
    if (!trade) return;
    const exitRaw = prompt(`Exit price for ${trade.symbol} (${trade.side})`, "");
    if (!exitRaw) return;
    const exit = Number(exitRaw);
    if (!Number.isFinite(exit) || exit <= 0) {
      pushStatus("Invalid exit price.", "warn");
      return;
    }
    closeManualTrade(trade, exit, "");
  });

  liveOrderForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (paperMode) {
      pushStatus("Disable paper mode before placing live orders.", "warn");
      return;
    }
    const cfg = autoConfig || ensureAutotraderConfig();
    if (!cfg) {
      pushStatus("Configure AutoTrader before placing live orders.", "warn");
      return;
    }
    const symbol = normalizeSymbol(liveOrderSymbol?.value);
    const side = (liveOrderSide?.value || "buy").toLowerCase();
    const notional = Number(liveOrderNotional?.value || 0);
    if (!symbol || !Number.isFinite(notional) || notional <= 0) {
      pushStatus("Live order needs symbol and notional.", "warn");
      return;
    }
    if (!confirm(`Place LIVE ${side.toUpperCase()} ${symbol} for ${notional.toFixed(2)} USDT?`)) {
      return;
    }
    const payload = {
      base_url: cfg.base || cfg.base_url,
      api_key: cfg.api || cfg.api_key,
      api_secret: cfg.secret || cfg.api_secret,
      exchange: cfg.exchange || "bybit",
      account_type: cfg.account_type,
      margin_mode: cfg.margin_mode,
      environment: cfg.environment,
      symbol,
      side,
      notional_usdt: notional,
      confirm: true,
    };
    try {
      const res = await fetch(`${apiBase()}/autotrader/order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Order failed");
      addAutoLog(`Live order placed: ${symbol} ${side} ${data.qty || ""}`);
      pushStatus(`Live order sent: ${symbol} ${side}`, "run");
      fetchBalance(cfg, true).catch(()=>{});
    } catch (err) {
      addAutoLog(`Live order error: ${err.message}`);
      pushStatus(`Live order error: ${err.message}`, "err");
    }
  });

  if (hunterToggle) {
    hunterToggle.addEventListener("change", (e) => {
      if (e.target.checked) {
        if (!liveRunning) {
          toggleLive(true);
        } else {
          startHunter();
          pushStatus("Divergence hunter restarted manually.", "run");
        }
      } else {
        if (liveRunning) {
          toggleLive(false);
        } else {
          stopHunter();
          pushStatus("Hunter parked.", "idle");
        }
      }
    });
  }

  const presetSelectors = ["#live-dataset","#live-model","#live-threshold","#live-count"];
  function setPresetDisabled(disabled) {
    assetsLocked = disabled;
    presetSelectors.forEach(sel => {
      const el = $(sel);
      if (el) el.disabled = disabled;
    });
    if (assetSearch) assetSearch.disabled = disabled;
    if (assetAddBtn) assetAddBtn.disabled = disabled;
    if (selectAllBtn) selectAllBtn.disabled = disabled;
    if (clearAllBtn) clearAllBtn.disabled = disabled;
    $$("input[data-symbol]").forEach(cb => cb.disabled = disabled);
    $$(".asset-remove").forEach(btn => btn.disabled = disabled);
    $$(".favorite-toggle").forEach(btn => btn.disabled = disabled);
    if (lastSuggestions.length) renderSuggestions(lastSuggestions);
  }

  function selectedAssets() {
    const picks = Array.from(enabledAssets);
    if (picks.length) return picks;
    if (assetOrder.length) return [assetOrder[0]];
    return ["BTC/USDT"];
  }

  function updateStatusCard(key, state, message) {
    const card = statusCards[key];
    if (!card) return;
    card.classList.remove("idle","running","error");
    card.classList.add(state);
    const label = card.querySelector(".status-state");
    if (label) label.textContent = message;
  }

  function pushStatus(message, tone = "run") {
    if (!statusFeed) return;
    const note = document.createElement("p");
    note.className = `status-note ${tone}`;
    note.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    statusFeed.prepend(note);
    while (statusFeed.children.length > 6) statusFeed.removeChild(statusFeed.lastChild);
    playChime();
  }

  function recordPulse(payload) {
    const heartbeat = payload?.heartbeat;
    if (!heartbeat) return;
    const pulseTime = new Date(heartbeat);
    lastHeartbeatTs = pulseTime.getTime();
    if (heartbeatIndicator) {
      heartbeatIndicator.classList.add("beating");
      heartbeatIndicator.classList.remove("idle");
      setTimeout(() => heartbeatIndicator.classList.remove("beating"), 900);
    }
    if (heartbeatLabel) heartbeatLabel.textContent = "Active";
    const count = payload?.scan_count ?? 0;
    const assets = payload?.symbols?.length ?? selectedAssets().length;
    const pulseLabel = pulseTime.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" });
    if (pulseMeta) {
      pulseMeta.dataset.ts = `${lastHeartbeatTs}`;
      pulseMeta.dataset.summary = `${count} signals - ${assets} assets`;
      pulseMeta.textContent = `Pulse @ ${pulseLabel} (IST) - ${count} signals - ${assets} assets`;
    }
    if (pulseFeed) {
      if (pulseFeed.querySelector("[data-empty]")) pulseFeed.innerHTML = "";
      const item = document.createElement("li");
      item.innerHTML = `<strong>${pulseLabel}</strong><span>${count} signals - ${assets} assets</span>`;
      pulseFeed.prepend(item);
      while (pulseFeed.children.length > 12) pulseFeed.removeChild(pulseFeed.lastChild);
      playChime();
    }
  }

  setInterval(() => {
    if (!pulseMeta) return;
    const tsVal = Number(pulseMeta.dataset.ts || 0);
    if (!tsVal) {
      pulseMeta.textContent = "Awaiting scanner pulse...";
      if (heartbeatIndicator) heartbeatIndicator.classList.add("idle");
      return;
    }
    const diff = Math.max(0, Date.now() - tsVal);
    const secs = Math.round(diff / 1000);
    const summary = pulseMeta.dataset.summary || "";
    pulseMeta.textContent = `Pulse ${secs}s ago - ${summary}`;
    if (heartbeatIndicator) heartbeatIndicator.classList.toggle("idle", secs > 30);
  }, 2000);

  function setLiveStatus(state, message) {
    if (!statusPill) return;
    statusPill.classList.remove("idle","running","error");
    statusPill.classList.add(state);
    const label = statusPill.querySelector(".label");
    if (label) label.textContent = message || state.toUpperCase();
    updateStatusCard("live", state, message || state.toUpperCase());
  }

  function toggleLive(run) {
    if (run) {
      if (liveRunning) return;
      liveRunning = true;
      setPresetDisabled(true);
      setLiveStatus("running","Hunting divergences");
      if (startBtn) { startBtn.textContent = "Stop Live Feed"; startBtn.classList.add("running"); }
      if (hunterToggle) hunterToggle.checked = true;
      pushStatus(`Live feed engaged on ${selectedAssets().length} asset(s).`, "run");
      startHunter();
    } else {
      if (!liveRunning) return;
      liveRunning = false;
      setPresetDisabled(false);
      if (startBtn) { startBtn.textContent = "Start Live Feed"; startBtn.classList.remove("running"); }
      setLiveStatus("idle","Idle");
      if (hunterToggle) hunterToggle.checked = false;
      updateStatusCard("hunter","idle","Idle");
      pushStatus("Live feed halted.", "idle");
      if (heartbeatLabel) heartbeatLabel.textContent = "Idle";
      heartbeatIndicator?.classList.add("idle");
      if (pulseMeta) {
        delete pulseMeta.dataset.ts;
        pulseMeta.textContent = "Scanner paused.";
      }
      stopHunter();
    }
  }

  startBtn?.addEventListener("click", async () => {
    if (!liveRunning) {
      toggleLive(true);
      if (autoTradeActive && autoConfig) await fetchBalance(autoConfig, true).catch(()=>{});
    } else {
      toggleLive(false);
    }
  });

  function startHunter() {
    if (hunterActive) return;
    hunterActive = true;
    updateStatusCard("hunter","running","Scanning divergences");
    pushStatus("Divergence hunter armed.", "run");
    fetchScan();
    hunterTimer = setInterval(fetchScan, 5000);
  }

  function stopHunter() {
    if (!hunterActive) return;
    hunterActive = false;
    if (hunterTimer) clearInterval(hunterTimer);
    if (scanAbortController) {
      scanAbortController.abort();
      scanAbortController = null;
    }
    if (!liveRunning) updateStatusCard("hunter","idle","Idle");
  }

  async function fetchScan() {
    if (scanInFlight) return;
    scanInFlight = true;
    const payload = {
      symbols: selectedAssets(),
      dataset_path: $("#live-dataset")?.value || undefined,
      model_path: $("#live-model")?.value || undefined,
      threshold: Number($("#live-threshold")?.value || 0.65),
      max_events: Number($("#live-count")?.value || 3),
    };
    scanAbortController = new AbortController();
    const timeout = setTimeout(() => scanAbortController?.abort(), SCAN_TIMEOUT_MS);
    try {
      const res = await fetch(`${apiBase()}/live/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: scanAbortController.signal,
      });
      const data = await res.json();
      recordPulse(data);
      (data.events || []).forEach(handleEvent);
      if (!data.events?.length) setLiveStatus("running","Watching...");
    } catch (err) {
      if (err && err.name === "AbortError") {
        pushStatus("Feed timeout. Slowing scan cadence.", "warn");
      } else {
        console.error(err);
        setLiveStatus("error","Feed error");
        if (pulseMeta) pulseMeta.textContent = "Pulse paused (feed error)";
        if (heartbeatLabel) heartbeatLabel.textContent = "Paused";
        heartbeatIndicator?.classList.add("idle");
        updateStatusCard("hunter","error","Feed error");
        pushStatus(`Feed error: ${err.message || err}`, "err");
      }
    } finally {
      clearTimeout(timeout);
      scanAbortController = null;
      scanInFlight = false;
    }
  }

  function eventAgeMinutes(evt) {
    const ages = [];
    if (evt && evt.divergence_age_minutes !== undefined && evt.divergence_age_minutes !== null) {
      ages.push(Number(evt.divergence_age_minutes));
    }
    if (evt && evt.price_age_minutes !== undefined && evt.price_age_minutes !== null) {
      ages.push(Number(evt.price_age_minutes));
    }
    if (evt && evt.entry_time) {
      const d = new Date(evt.entry_time);
      if (!Number.isNaN(d.getTime())) {
        ages.push((Date.now() - d.getTime()) / 60000);
      }
    }
    const finite = ages.filter((n) => Number.isFinite(n));
    if (!finite.length) return null;
    return Math.max(...finite);
  }

  function shouldAutoTrade(evt) {
    if (!autoTradeActive) return false;
    if (!evt || evt.status !== "taken") return false;
    const age = eventAgeMinutes(evt);
    if (age === null) return true;
    return age <= AUTO_TRADE_MAX_AGE_MIN;
  }

  function handleEvent(evt) {
    tradeNo += 1;
    const id = evt.trade_no || tradeNo;
    const row = document.createElement("tr");
    const liveRow = LIVE_STATUSES.has(evt.status);
    row.className = liveRow ? "live-row" : "reject-row";
    const entryTs = toIST(evt.entry_time);
    const exitTs = toIST(evt.exit_time);
    const priceTs = toIST(evt.price_timestamp);
    row.innerHTML = `
      <td>${id}</td>
      <td>${evt.symbol || ""}</td>
      <td>${evt.divergence || ""}</td>
      <td>${entryTs}</td>
      <td>${exitTs}</td>
      <td>${fmt(evt.entry_price)}</td>
      <td>${fmt(evt.exit_price)}</td>
      <td>${fmt(evt.trade_size)}</td>
      <td>${fmt(evt.ret_pct,2)}</td>
      <td>${fmt(evt.pnl,2)}</td>
      <td>${fmt(evt.ml_confidence * 100,2)}%</td>
      <td>${evt.status}${priceTs ? ` (px @ ${priceTs})` : ""}</td>
    `;
    if (liveRow) {
      if (liveLog.children.length === 1 && liveLog.children[0].children.length === 1) liveLog.innerHTML = "";
      liveLog.prepend(row);
      if (ENTRY_STATUSES.has(evt.status)) {
        showToast(evt);
        scheduleChimes();
        pushStatus(`TAKE ${evt.symbol} (${evt.divergence}) @ ${fmt(evt.entry_price)} | PnL ${fmt(evt.pnl,2)}`, "run");
        if (autoTradeActive) {
          if (shouldAutoTrade(evt)) {
            routeToAutotrader(evt);
          } else {
            const age = eventAgeMinutes(evt);
            const label = Number.isFinite(age) ? `${age.toFixed(1)}m` : "unknown";
            pushStatus(`AutoTrader skipped stale signal (${label}).`, "warn");
          }
        }
      } else {
        pushStatus(`UPDATE ${evt.symbol} - ${evt.status}`, "run");
      }
    } else {
      logRejection(id, evt);
      pushStatus(`SKIP ${evt.symbol} (${evt.divergence}) - ${evt.reason || evt.ml_action}`, "warn");
    }
    trackSignalTrade(evt);
  }

  function logRejection(id, evt) {
    if (rejectLog.children.length === 1 && rejectLog.children[0].children.length === 1) rejectLog.innerHTML = "";
    const row = document.createElement("tr");
    row.className = "reject-row";
    const entryTs = toIST(evt.entry_time);
    const exitTs = toIST(evt.exit_time);
    const priceTs = toIST(evt.price_timestamp);
    row.innerHTML = `
      <td>${id}</td>
      <td>${evt.symbol || ""}</td>
      <td>${evt.divergence || ""}</td>
      <td>${entryTs}</td>
      <td>${exitTs}</td>
      <td>${fmt(evt.ml_confidence * 100,2)}%</td>
      <td>${evt.ml_action === "skip" ? "ML filter skipped" : (evt.reason || "Rejected")}${priceTs ? ` (px @ ${priceTs})` : ""}</td>
    `;
    rejectLog.prepend(row);
  }

  function fmt(value, digits = 4) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) return "--";
    return Number(value).toFixed(digits);
  }

  function toIST(ts) {
    if (!ts) return "";
    try {
      const d = new Date(ts);
      return d.toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour12: true,
      });
    } catch (_) {
      return ts || "";
    }
  }

  function exportCsv() {
    const rows = Array.from(liveLog?.querySelectorAll("tr") || []).filter((r) => r.cells && r.cells.length > 1);
    if (!rows.length) {
      pushStatus("No signal rows to export yet.", "warn");
      return;
    }
    const headers = ["#", "Symbol", "Divergence", "Entry Time", "Exit Time", "Entry Px", "Exit Px", "Trade Size", "Ret %", "PNL ($)", "Confidence", "Status"];
    const lines = [headers.join(",")];
    rows.forEach((r) => {
      const cells = Array.from(r.cells).map((td) => `"${td.textContent.trim().replace(/"/g, '""')}"`);
      lines.push(cells.join(","));
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mystrix_live_report_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    pushStatus(`Exported ${rows.length} rows to CSV.`, "run");
  }

  function renderBalanceBreakdown(rows) {
    if (!balanceBreakdown) return;
    if (!Array.isArray(rows) || !rows.length) {
      balanceBreakdown.innerHTML = "<li>No balances yet.</li>";
      return;
    }
    balanceBreakdown.innerHTML = "";
    rows.slice(0, 5).forEach((row) => {
      const item = document.createElement("li");
      item.innerHTML = `<span>${row.asset} - ${fmt(row.amount, 4)}</span><span>$${fmt(row.usdt_value, 2)}</span>`;
      balanceBreakdown.appendChild(item);
    });
    if (rows.length > 5) {
      const extra = document.createElement("li");
      extra.innerHTML = `<span>+${rows.length - 5} more</span><span></span>`;
      balanceBreakdown.appendChild(extra);
    }
  }

  function showToast(evt) {
    if (!toastStack) return;
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.innerHTML = `
      <strong>${evt.symbol || ""}</strong> - ${evt.divergence || ""}<br/>
      PnL: ${fmt(evt.pnl, 2)} | Conf: ${fmt(evt.ml_confidence * 100, 2)}%
    `;
    toastStack.appendChild(toast);
    setTimeout(() => toast.remove(), 15000);
  }

  function scheduleChimes() {
    const start = Date.now();
    const play = () => {
      playChime();
      if (Date.now() - start < 10000) toastTimer = setTimeout(play, 2000);
    };
    play();
  }

  let audioCtx;
  function playChime() {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const ctx = audioCtx;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.8);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.8);
    } catch (_) {}
  }

  function ensureAutotraderConfig() {
    const raw = localStorage.getItem("autotraderConfig");
    if (!raw) return null;
    try { return JSON.parse(raw); }
    catch (err) { console.error(err); return null; }
  }

  $("#autotrader-toggle")?.addEventListener("change", async (e) => {
    if (e.target.checked) {
      const config = ensureAutotraderConfig();
      if (!config) {
        e.target.checked = false;
        window.open("autotrader_setup.html", "_blank");
        showToast({ symbol: "AutoTrader", pnl: "--", divergence: "Config", ml_confidence: 0 });
        return;
      }
      autoConfig = config;
      autoTradeActive = true;
      addAutoLog("AutoTrader armed with config.");
      updateStatusCard("auto","running","Armed");
      pushStatus("AutoTrader armed.", "run");
      await fetchBalance(config, true).catch(()=>{});
    } else {
      autoTradeActive = false;
      addAutoLog("AutoTrader paused.");
      updateStatusCard("auto","idle","Idle");
      pushStatus("AutoTrader paused.", "idle");
    }
  });

  $("#open-autotrader-settings")?.addEventListener("click", () => window.open("autotrader_setup.html", "_blank"));

  function routeToAutotrader(evt) {
    const cfg = autoConfig || ensureAutotraderConfig();
    if (!cfg) return;
    const balance = autoBalance || Number(cfg.sim_balance || 0);
    const level = levelForBalance(balance);
    const leverageRaw = Number(cfg.leverage || 1);
    const leverage = Number.isFinite(leverageRaw) && leverageRaw > 0 ? leverageRaw : 1;
    const basePct = normalizePct(cfg.max_equity_pct || 0.02);
    const baseSize = balance * basePct * leverage;
    const size = level ? level.risk * leverage : baseSize;
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${evt.trade_no || "--"}</td>
      <td>${evt.symbol || ""}</td>
      <td>${evt.divergence === "bull" ? "LONG" : "SHORT"}</td>
      <td>${fmt(size, 2)}</td>
      <td>sent</td>
      <td>SL ${cfg.stop_pct || 3}% / TP ${cfg.target_pct || 1.5}%</td>
    `;
    if (autoLog.children.length === 1 && autoLog.children[0].children.length === 1) autoLog.innerHTML = "";
    autoLog.prepend(row);
  }

  function addAutoLog(message) {
    const row = document.createElement("tr");
    row.innerHTML = `<td colspan="6">${message}</td>`;
    autoLog.prepend(row);
  }

  function renderPaperTrades(list, active) {
    if (!Array.isArray(list)) return;
    if (list.length === 0) {
      addAutoLog(`${active ? "Active" : "History"} trades: 0`);
      return;
    }
    const top = list.slice(0, 3).map((t) => {
      const pnl = (t.pnl || 0).toFixed(2);
      const ret = (t.ret_pct || 0).toFixed(2);
      return `${t.symbol} ${t.side||""} pnl=${pnl} ret%=${ret} status=${t.status}`;
    }).join(" | ");
    addAutoLog(`${active ? "Active" : "History"} trades (${list.length}): ${top}`);
  }

  function normalizePct(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return 0;
    return num > 1 ? num / 100 : num;
  }

  function syncBybitPositions(list) {
    const positions = Array.isArray(list) ? list : [];
    const activeKeys = new Set();
    positions.forEach((p, idx) => {
      const sym = normalizeSymbol(p.symbol);
      if (!sym) return;
      const side = (p.side || "long").toLowerCase();
      const key = `bybit:${sym}:${side}`;
      const unrealized = Number(p.unrealized_pnl);
      const leverage = Number(p.leverage || 0);
      const lastPrice = Number(p.last_price || 0);
      let margin = Number(p.margin || 0);
      if (!(Number.isFinite(margin) && margin > 0) && Number.isFinite(leverage) && leverage > 0 && Number(p.size || 0) > 0 && lastPrice > 0) {
        margin = (Number(p.size) * lastPrice) / leverage;
      }
      const override = sltpOverrides.get(key);
      const stopLoss = Number(p.stop_loss || 0) || null;
      const takeProfit = Number(p.take_profit || 0) || null;
      activeKeys.add(key);
      upsertOpenTrade({
        key,
        id: sym,
        symbol: sym,
        side,
        entry_price: Number(p.entry_price || 0),
        size: Number(p.size || 0),
        unrealized_pnl: Number.isFinite(unrealized) ? unrealized : null,
        last_price: lastPrice || 0,
        leverage: Number.isFinite(leverage) && leverage > 0 ? leverage : null,
        margin: Number.isFinite(margin) && margin > 0 ? margin : null,
        stop_loss: override?.stop_loss ?? stopLoss,
        take_profit: override?.take_profit ?? takeProfit,
        source: "bybit",
        opened_at: p.opened_at,
        opened_at_ts: p.opened_at ? Date.parse(p.opened_at) : Date.now() + idx,
      }, false);
    });
    Array.from(openTrades.keys()).forEach((key) => {
      if (key.startsWith("bybit:") && !activeKeys.has(key)) removeOpenTrade(key);
    });
    renderOpenTrades();
  }

  async function fetchPositions(config) {
    if (!config) return;
    try {
      const baseUrlRaw = config.base || config.base_url;
      const envRaw = (config.environment || "").toLowerCase();
      const payload = {
        base_url: baseUrlRaw && baseUrlRaw !== "paper" ? baseUrlRaw : "https://api.bybit.com",
        api_key: config.api || config.api_key,
        api_secret: config.secret || config.api_secret,
        exchange: config.exchange || "bybit",
        account_type: config.account_type,
        margin_mode: config.margin_mode,
        environment: envRaw && envRaw !== "paper" ? envRaw : "live",
      };
      const res = await fetch(`${apiBase()}/autotrader/positions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Positions fetch failed");
      syncBybitPositions(data.positions || []);
    } catch (err) {
      addAutoLog(`Positions error: ${err.message}`);
    }
  }

  function setPaperMode(enabled, notify = false) {
    const cfg = autoConfig || ensureAutotraderConfig();
    if (!enabled && !cfg) {
      if (paperToggle) paperToggle.checked = true;
      paperMode = true;
      addAutoLog("AutoTrader config missing; staying in paper mode.");
      pushStatus("Configure AutoTrader before switching to live.", "warn");
      initPaper();
      return;
    }
    paperMode = enabled;
    loadPnlState();
    if (notify) {
      pushStatus(enabled ? "Paper mode enabled." : "Live mode enabled.", enabled ? "warn" : "run");
      addAutoLog(enabled ? "Paper mode enabled." : "Live mode enabled.");
    }
    if (enabled) {
      Array.from(openTrades.keys()).forEach((key) => {
        if (key.startsWith("bybit:")) openTrades.delete(key);
      });
      renderOpenTrades();
      initPaper();
    } else {
      Array.from(openTrades.keys()).forEach((key) => {
        if (key.startsWith("paper:")) removeOpenTrade(key);
      });
    }
    if (!enabled && cfg) {
      fetchBalance(cfg, true).catch(()=>{});
    }
  }

  async function fetchBalance(config, notify) {
    try {
      if (balanceStatus) balanceStatus.textContent = "syncing";
      let data = null;
      if (paperMode) {
        // advance paper prices and maybe auto-close
        await fetch(`${apiBase()}/paper/tick`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
        const res = await fetch(`${apiBase()}/paper/balance`);
        data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Balance fetch failed");
        autoBalance = Number(data.balance || 0);
        renderBalanceBreakdown([{ asset: "USDT", amount: autoBalance, usdt_value: autoBalance }]);
        if (data.active) renderPaperTrades(data.active, true);
        if (data.history) renderPaperTrades(data.history, false);
        if (data.prices) updatePriceCache(data.prices);
        syncPaperTrades(data);
        if (notify) addAutoLog(`Balance (paper): ${autoBalance.toFixed(2)} USDT`);
      } else {
        if (!config) throw new Error("AutoTrader config missing");
        if (!config.api || !config.secret) throw new Error("AutoTrader API keys missing");
        const baseUrlRaw = config.base || config.base_url;
        const envRaw = (config.environment || "").toLowerCase();
        const payload = {
          base_url: baseUrlRaw && baseUrlRaw !== "paper" ? baseUrlRaw : "https://api.bybit.com",
          api_key: config.api || config.api_key,
          api_secret: config.secret || config.api_secret,
          exchange: config.exchange || "bybit",
          account_type: config.account_type,
          margin_mode: config.margin_mode,
          environment: envRaw && envRaw !== "paper" ? envRaw : "live",
        };
        const res = await fetch(`${apiBase()}/autotrader/balance`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Balance fetch failed");
        autoBalance = Number(data.balance || 0);
        renderBalanceBreakdown(data.breakdown || []);
        fetchPositions(config).catch(()=>{});
        if (notify) {
          addAutoLog(`Balance (live): ${autoBalance.toFixed(2)} USDT`);
          if (data.account_type_used) {
            addAutoLog(`Bybit account: ${data.account_type_used} (${data.environment || "live"})`);
          }
        }
      }
      if (balanceAmount) balanceAmount.textContent = `$${autoBalance.toFixed(2)}`;
      updateLevelStats(autoBalance);
      updatePnlSeries(autoBalance);
      if (balanceStatus) balanceStatus.textContent = liveRunning ? "running" : "synced";
      updateStatusCard("auto", autoTradeActive ? "running" : "idle", autoTradeActive ? "Synced" : "Idle");
      if (notify) pushStatus(`Balance synced (${autoBalance.toFixed(2)} USDT).`, "run");
    } catch (err) {
      if (balanceStatus) balanceStatus.textContent = "error";
      addAutoLog(`Balance error: ${err.message}`);
      updateStatusCard("auto","error","Balance error");
      pushStatus(`AutoTrader balance error: ${err.message}`, "err");
      throw err;
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && autoTradeActive && autoConfig) fetchBalance(autoConfig, false).catch(()=>{});
  });

  $("#refresh-live")?.addEventListener("click", () => window.location.reload());
  $("#export-csv")?.addEventListener("click", exportCsv);
  refreshBalanceBtn?.addEventListener("click", () => {
    const cfg = autoConfig || ensureAutotraderConfig();
    if (!paperMode && !cfg) {
      addAutoLog("AutoTrader config needed to sync live balance.");
      pushStatus("Configure AutoTrader to sync balances.", "warn");
      return;
    }
    fetchBalance(cfg, true).catch(()=>{});
  });

  const initialCfg = ensureAutotraderConfig();
  if (initialCfg) {
    autoConfig = initialCfg;
    fetchBalance(initialCfg, false).catch(()=>{});
  }

  async function initPaper() {
    try {
      await fetch(`${apiBase()}/paper/init`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ balance: 10000 }),
      });
      addAutoLog("Paper wallet initialized to $10,000.");
      const cfg = autoConfig || ensureAutotraderConfig();
      fetchBalance(cfg, true).catch(()=>{});
    } catch (err) {
      addAutoLog(`Paper init failed: ${err.message}`);
    }
  }

  if (paperToggle) {
    paperMode = paperToggle.checked;
    if (paperMode) initPaper();
    paperToggle.addEventListener("change", () => setPaperMode(paperToggle.checked, true));
  }

  demoBtn?.addEventListener("click", async () => {
    if (demoBtn.disabled) return;
    const original = demoBtn.textContent;
    demoBtn.disabled = true;
    demoBtn.textContent = "Firing demo...";
    try {
      if (!paperMode) {
        const cfg = autoConfig || ensureAutotraderConfig();
        if (!cfg) throw new Error("AutoTrader config required for live demo");
        if (!confirm("Place LIVE demo order on Bybit (BNB/USDT 500 USDT, auto-close 45s)?")) {
          throw new Error("Live demo cancelled");
        }
        const payload = {
          base_url: cfg.base || cfg.base_url,
          api_key: cfg.api || cfg.api_key,
          api_secret: cfg.secret || cfg.api_secret,
          exchange: cfg.exchange || "bybit",
          account_type: cfg.account_type,
          margin_mode: cfg.margin_mode,
          environment: cfg.environment,
          symbol: "BNB/USDT",
          side: "buy",
          notional_usdt: 500,
          hold_seconds: 45,
          confirm: true,
        };
        const res = await fetch(`${apiBase()}/autotrader/demo_trade`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Live demo trade failed");
        addAutoLog("Live demo trade sent to Bybit (BNB/USDT 500 USDT).");
        pushStatus("Live demo trade sent to Bybit (auto-close 45s).", "run");
        fetchBalance(cfg, true).catch(()=>{});
      } else {
        const url = `${apiBase()}/live/demo_trade`;
        const controller = new AbortController();
        const t = setTimeout(() => controller.abort(), 8000);
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
          signal: controller.signal,
        });
        clearTimeout(t);
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Demo trade failed");
        pushStatus("Demo trade fired on BNB/USDT (500 USDT, 45s hold).", "run");
        if (data.event) handleEvent(data.event);
      }
    } catch (err) {
      console.error(err);
      if (err.message !== "Live demo cancelled") {
        pushStatus(`Demo trade failed: ${err.message}`, "err");
      }
    } finally {
      demoBtn.disabled = false;
      demoBtn.textContent = original;
    }
  });

  // Screensaver logic (Three.js placeholder)
  let saverActive = false;
  let saverTimer = null;
  let saverRenderer = null;
  let saverScene = null;
  let saverCamera = null;
  let saverCardGroup = null;
  let saverGlow = null;
  let saverDust = null;
  let saverLogoMat = null;
  let saverGridMat = null;
  let saverLogoTexture = null;
  let saverFrame = null;
  const saverOverlay = document.getElementById("screensaver");
  const saverWrap = document.getElementById("saver-canvas-wrap");
  const IDLE_TIMEOUT = 180000;

  function resetIdleTimer() {
    if (saverTimer) clearTimeout(saverTimer);
    stopScreensaver();
    saverTimer = setTimeout(startScreensaver, IDLE_TIMEOUT);
  }

  function startScreensaver() {
    if (saverActive || !saverOverlay || !saverWrap || !window.THREE) return;
    saverActive = true;
    saverOverlay.classList.add("active");
    if (!saverRenderer) initScreensaver();
    saverRenderer.setSize(saverWrap.clientWidth, saverWrap.clientHeight);
    saverCamera.aspect = saverWrap.clientWidth / saverWrap.clientHeight;
    saverCamera.updateProjectionMatrix();
    animateScreensaver();
  }

  function stopScreensaver() {
    if (!saverActive) return;
    saverActive = false;
    if (saverOverlay) saverOverlay.classList.remove("active");
    if (saverFrame) cancelAnimationFrame(saverFrame);
  }

  function createGridTexture() {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 512;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "rgba(6, 10, 16, 0.95)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "rgba(120, 220, 255, 0.12)";
    ctx.lineWidth = 1;
    for (let x = 0; x <= canvas.width; x += 32) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y <= canvas.height; y += 32) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    return texture;
  }

  function loadLogoTexture() {
    const loader = new THREE.TextureLoader();
    loader.load(
      "mystrix_logo.png",
      (tex) => {
        saverLogoTexture = tex;
        if ("colorSpace" in tex) {
          tex.colorSpace = THREE.SRGBColorSpace;
        } else if ("encoding" in tex) {
          tex.encoding = THREE.sRGBEncoding;
        }
        if (saverLogoMat) {
          saverLogoMat.map = tex;
          saverLogoMat.emissiveMap = tex;
          saverLogoMat.needsUpdate = true;
        }
      },
      undefined,
      () => {}
    );
  }

  function createGlowSprite() {
    const canvas = document.createElement("canvas");
    const size = 256;
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    const grad = ctx.createRadialGradient(size / 2, size / 2, 10, size / 2, size / 2, size / 2);
    grad.addColorStop(0, "rgba(170, 255, 255, 0.9)");
    grad.addColorStop(0.45, "rgba(120, 150, 255, 0.35)");
    grad.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);
    const texture = new THREE.CanvasTexture(canvas);
    const material = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(3.2, 4.6, 1);
    sprite.position.set(0, 0, -0.12);
    return sprite;
  }

  function createDust() {
    const count = 140;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      const idx = i * 3;
      positions[idx] = (Math.random() - 0.5) * 6;
      positions[idx + 1] = (Math.random() - 0.5) * 6;
      positions[idx + 2] = (Math.random() - 0.5) * 6;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const material = new THREE.PointsMaterial({
      color: 0x7de3ff,
      size: 0.025,
      transparent: true,
      opacity: 0.5,
      depthWrite: false,
    });
    return new THREE.Points(geometry, material);
  }

  function initScreensaver() {
    saverRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    saverRenderer.setPixelRatio(window.devicePixelRatio || 1);
    saverRenderer.setSize(saverWrap.clientWidth, saverWrap.clientHeight);
    saverWrap.innerHTML = "";
    saverWrap.appendChild(saverRenderer.domElement);

    saverScene = new THREE.Scene();
    saverScene.background = null;
    saverCamera = new THREE.PerspectiveCamera(45, saverWrap.clientWidth / saverWrap.clientHeight, 0.1, 100);
    saverCamera.position.set(0, 0, 3.8);

    const ambient = new THREE.AmbientLight(0x4c3a7a, 0.6);
    const light1 = new THREE.PointLight(0x8be4ff, 1.2, 10);
    light1.position.set(2.4, 1.8, 3.2);
    const light2 = new THREE.PointLight(0xff7bfd, 0.9, 10);
    light2.position.set(-2.2, -1.6, 2.4);
    const light3 = new THREE.PointLight(0x64ffda, 0.6, 10);
    light3.position.set(0, 2.6, -2.2);
    saverScene.add(ambient, light1, light2, light3);

    const cardGeometry = new THREE.BoxGeometry(1.5, 2.3, 0.08);
    const sideMat = new THREE.MeshStandardMaterial({ color: 0x120918, metalness: 0.55, roughness: 0.4 });
    const frontMat = new THREE.MeshStandardMaterial({
      color: 0x070b16,
      emissive: 0x0b1624,
      emissiveIntensity: 0.35,
      metalness: 0.5,
      roughness: 0.25,
    });
    const backMat = new THREE.MeshStandardMaterial({
      color: 0x05060f,
      emissive: 0x050a12,
      emissiveIntensity: 0.25,
      metalness: 0.45,
      roughness: 0.3,
    });
    const materials = [sideMat, sideMat, sideMat, sideMat, frontMat, backMat];
    const card = new THREE.Mesh(cardGeometry, materials);

    saverCardGroup = new THREE.Group();
    saverCardGroup.add(card);

    const edges = new THREE.EdgesGeometry(cardGeometry);
    const edgeMat = new THREE.LineBasicMaterial({ color: 0x9efcff, transparent: true, opacity: 0.6 });
    const outline = new THREE.LineSegments(edges, edgeMat);
    saverCardGroup.add(outline);

    const gridTexture = createGridTexture();
    saverGridMat = new THREE.MeshStandardMaterial({
      map: gridTexture,
      transparent: true,
      opacity: 0.5,
      emissive: 0x2ec4ff,
      emissiveIntensity: 0.4,
      depthWrite: false,
    });
    const gridPlane = new THREE.Mesh(new THREE.PlaneGeometry(1.38, 2.08), saverGridMat);
    gridPlane.position.z = 0.042;
    saverCardGroup.add(gridPlane);

    saverLogoMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.95,
      emissive: 0x8fe9ff,
      emissiveIntensity: 0.85,
      depthWrite: false,
    });
    const logoPlane = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 1.5), saverLogoMat);
    logoPlane.position.z = 0.055;
    saverCardGroup.add(logoPlane);
    loadLogoTexture();

    saverGlow = createGlowSprite();
    if (saverGlow) saverCardGroup.add(saverGlow);

    saverScene.add(saverCardGroup);

    saverDust = createDust();
    saverScene.add(saverDust);
  }

  function animateScreensaver() {
    if (!saverActive) return;
    const now = performance.now();
    const t = now * 0.001;
    if (saverCardGroup) {
      saverCardGroup.rotation.y += 0.006;
      saverCardGroup.rotation.x = Math.sin(t * 0.6) * 0.12;
      saverCardGroup.rotation.z = Math.sin(t * 0.4) * 0.04;
      saverCardGroup.position.y = Math.sin(t * 0.8) * 0.08;
    }
    if (saverGlow) {
      const pulse = 0.95 + Math.sin(t * 1.4) * 0.06;
      saverGlow.scale.set(3.2 * pulse, 4.6 * pulse, 1);
    }
    if (saverDust) {
      saverDust.rotation.y += 0.001;
      saverDust.rotation.x += 0.0006;
    }
    saverRenderer.render(saverScene, saverCamera);
    saverFrame = requestAnimationFrame(animateScreensaver);
  }

  ["mousemove","keydown","click","scroll","touchstart","touchmove"].forEach((evt) => {
    window.addEventListener(evt, resetIdleTimer, { passive: true });
  });
  resetIdleTimer();

  window.addEventListener("resize", () => {
    resizePnlCanvas();
    if (!saverRenderer || !saverWrap || !saverCamera) return;
    saverRenderer.setSize(saverWrap.clientWidth, saverWrap.clientHeight);
    saverCamera.aspect = saverWrap.clientWidth / saverWrap.clientHeight;
    saverCamera.updateProjectionMatrix();
  });

})();
