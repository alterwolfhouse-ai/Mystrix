(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  const api = () => {
    try { return window.API_BASE || location.origin; }
    catch (_) { return location.origin; }
  };

  const ASSETS = [
    "BTC/USDT","ETH/USDT","BNB/USDT","SOL/USDT","XRP/USDT","ADA/USDT","DOGE/USDT","MATIC/USDT","DOT/USDT","AVAX/USDT",
    "LTC/USDT","LINK/USDT","NEAR/USDT","ATOM/USDT","APT/USDT","ARB/USDT","OP/USDT","SUI/USDT","PEPE/USDT","SHIB/USDT",
    "XLM/USDT","FIL/USDT","INJ/USDT","ETC/USDT","ALGO/USDT","AAVE/USDT","SAND/USDT","MANA/USDT","EGLD/USDT","FTM/USDT"
  ];

  const datasetInput = $("#dataset-path");
  const cacheInput = $("#cache-path");
  let chime = null;
  try {
    chime = new Audio("data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAwF0AAIC7AAACABAAZGF0YQAAAAA=");
  } catch (_) {}
  const modelInput = $("#model-path");
  const timeframeSelect = $("#timeframe");
  const startInput = $("#start-date");
  const endInput = $("#end-date");
  const thresholdInput = $("#threshold");
  const thresholdLabel = $("#threshold-val");
  const equityInput = $("#equity-pct");
  const equityLabel = $("#equity-pct-val");
  const initialInput = $("#initial-equity");
  const feeInput = $("#fee-bps");
  const maxPosInput = $("#max-positions");
  const runBtn = $("#run-btn");
  const runStatus = $("#run-status");
  const fetchBtn = $("#fetch-btn");
  const fetchStatus = $("#fetch-status");
  const assetGrid = $("#asset-grid");
  const chartCaption = $("#chart-caption");
  const statNote = $("#stat-note");
  const symbolTable = $("#symbol-table tbody");
  const tradeTable = $("#trade-table tbody");
  const stats = {
    return: $("#stat-return"),
    cagr: $("#stat-cagr"),
    dd: $("#stat-dd"),
    win: $("#stat-win"),
    trades: $("#stat-trades"),
    conc: $("#stat-conc"),
  };

  let chart;

  function updateCount() {
    const picks = selectedAssets();
    const counter = $("#asset-count");
    if (counter) counter.textContent = `${picks.length} / 30 selected`;
  }

  function addAsset(sym) {
    if (!assetGrid) return;
    const clean = (sym || "").trim().toUpperCase();
    if (!clean.includes("/")) return;
    // Limit max 30 (unless rechecking an existing item)
    if (selectedAssets().length >= 30 && !assetGrid.querySelector(`input[value="${clean}"]`)) {
      alert("Max 30 assets allowed.");
      return;
    }
    const exists = assetGrid.querySelector(`input[value="${clean}"]`);
    if (exists) {
      exists.checked = true;
      updateCount();
      return;
    }
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" value="${clean}" checked /> <span>${clean}</span>`;
    assetGrid.appendChild(label);
    updateCount();
  }

  function populateAssets() {
    assetGrid.innerHTML = "";
    ASSETS.forEach(sym => addAsset(sym));
    updateCount();
    buildSuggestions();
  }

  function buildSuggestions(prefix="") {
    const dl = $("#asset-suggestions");
    if (!dl) return;
    const look = Array.from(new Set([...ASSETS, ...selectedAssets()])).sort();
    const regex = prefix ? new RegExp("^" + prefix.trim().toUpperCase().replace(/[.*+?^${}()|[\\]\\\\]/g, "\\$&")) : null;
    dl.innerHTML = "";
    look.filter((s) => !regex || regex.test(s)).slice(0, 25).forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s;
      dl.appendChild(opt);
    });
  }

  function initFormDefaults() {
    const today = new Date();
    const past = new Date();
    past.setMonth(past.getMonth() - 3);
    startInput.value = past.toISOString().split("T")[0];
    endInput.value = today.toISOString().split("T")[0];
    thresholdInput.addEventListener("input", () => thresholdLabel.textContent = Number(thresholdInput.value).toFixed(2));
    equityInput.addEventListener("input", () => equityLabel.textContent = `${Math.round(Number(equityInput.value) * 100)}%`);
    thresholdLabel.textContent = thresholdInput.value;
    equityLabel.textContent = `${Math.round(Number(equityInput.value) * 100)}%`;
  }

  function selectedAssets() {
    if (!assetGrid) return [];
    return Array.from(assetGrid.querySelectorAll("input[type='checkbox']:checked")).map((el) => el.value);
  }

  function payload() {
    const picks = selectedAssets();
    const cachePathVal = (cacheInput?.value.trim() || "cache_data");
    return {
      dataset_path: datasetInput.value.trim(),
      cache_path: cachePathVal || null,
      model_path: modelInput.value.trim() || null,
      start_date: startInput.value || null,
      end_date: endInput.value || null,
      threshold: Number(thresholdInput.value),
      equity_pct: Number(equityInput.value),
      initial_equity: Number(initialInput.value || 10000),
      fee_bps: Number(feeInput.value || 5),
      max_positions: Number(maxPosInput.value || 20),
      symbols: picks,
      max_assets: picks.length ? Math.min(30, picks.length) : 30,
    };
  }

  function setRunning(state, message) {
    runBtn.disabled = state;
    runStatus.textContent = message;
    runStatus.classList.remove("idle","run","err");
    runStatus.classList.add(state ? "run" : "idle");
    if (!state && message === "Idle") {
      runStatus.classList.remove("run");
      runStatus.classList.add("idle");
    }
  }

  function renderStats(summary) {
    stats.return.textContent = summary?.total_return_pct !== undefined ? `${summary.total_return_pct.toFixed(2)}%` : "--";
    stats.cagr.textContent = summary?.cagr_pct !== undefined ? `${summary.cagr_pct.toFixed(2)}%` : "--";
    stats.dd.textContent = summary?.max_drawdown_pct !== undefined ? `${summary.max_drawdown_pct.toFixed(2)}%` : "--";
    stats.win.textContent = summary?.win_rate_pct !== undefined ? `${summary.win_rate_pct.toFixed(2)}%` : "--";
    stats.trades.textContent = summary?.trades ?? "--";
    stats.conc.textContent = summary?.max_concurrent ?? "--";
    statNote.textContent = `Signals ${summary?.signals ?? 0} - Filtered ${summary?.filtered ?? 0} - Skipped (capacity) ${summary?.skipped_capacity ?? 0}`;
  }

  function renderChart(curve) {
    if (!chart) {
      const ctx = document.getElementById("equity-chart");
      chart = new Chart(ctx, {
        type: "line",
        data: { labels: [], datasets: [{ label: "Equity", data: [], borderColor: "#7f5af0", tension: 0.2, fill: false }] },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: "#ccc" } },
            y: { ticks: { color: "#ccc" } },
          },
        },
      });
    }
    if (!Array.isArray(curve) || curve.length === 0) {
      chart.data.labels = [];
      chart.data.datasets[0].data = [];
      chart.update();
      chartCaption.textContent = "No equity data.";
      return;
    }
    chart.data.labels = curve.map((pt) => new Date(pt.t).toLocaleString());
    chart.data.datasets[0].data = curve.map((pt) => pt.equity);
    chart.update();
    chartCaption.textContent = `${curve.length} equity points`;
  }

  function renderSymbols(rows) {
    symbolTable.innerHTML = "";
    if (!rows?.length) {
      symbolTable.innerHTML = `<tr><td colspan="5" class="empty">No symbol stats yet.</td></tr>`;
      return;
    }
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${row.symbol}</td>
        <td>${row.trades}</td>
        <td>${row.win_rate.toFixed(1)}%</td>
        <td>${row.pnl.toFixed(2)}</td>
        <td>${row.avg_minutes.toFixed(1)}</td>
      `;
      symbolTable.appendChild(tr);
    });
  }

  function renderTrades(rows) {
    tradeTable.innerHTML = "";
    if (!rows?.length) {
      tradeTable.innerHTML = `<tr><td colspan="16" class="empty">No trades processed.</td></tr>`;
      return;
    }
    rows.forEach((row, idx) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${idx + 1}</td>
        <td>${row.symbol}</td>
        <td>${new Date(row.entry_time).toLocaleString()}</td>
        <td>${new Date(row.exit_time).toLocaleString()}</td>
        <td>${(row.entry_price ?? 0).toFixed(4)}</td>
        <td>${(row.exit_price ?? 0).toFixed(4)}</td>
        <td>${(row.size ?? 0).toFixed(2)}</td>
        <td>${(row.ret_pct ?? 0).toFixed(2)}</td>
        <td>${(row.net_pnl ?? 0).toFixed(2)}</td>
        <td>${row.side || (row.direction >= 0 ? 'bull' : 'bear')}</td>
        <td>${(row.prob ?? 0).toFixed(2)}</td>
        <td>${(row.equity_before ?? 0).toFixed(2)}</td>
        <td>${(row.equity_after ?? 0).toFixed(2)}</td>
        <td>${(row.hold_minutes ?? 0).toFixed(1)}</td>
        <td>${(row.fee_paid ?? 0).toFixed(2)}</td>
        <td>${row.status || 'taken'}</td>
      `;
      tradeTable.appendChild(tr);
    });
  }

  function logFeed(msg, type="info") {
    const rail = $("#fetch-log");
    if (!rail) return;
    const div = document.createElement("div");
    div.className = "feed-line " + (type === "error" ? "err" : type === "ok" ? "ok" : "muted");
    const ts = new Date().toLocaleTimeString();
    div.textContent = `[${ts}] ${msg}`;
    rail.appendChild(div);
    rail.scrollTop = rail.scrollHeight;
    try { chime && chime.play(); } catch(_) {}
  }

  function exportTradesCsv() {
    const rows = Array.from(tradeTable?.querySelectorAll("tr") || []).filter(r => r.cells?.length > 1);
    if (!rows.length) {
      logFeed("No trades to export yet.", "muted");
      return;
    }
    const headers = ["#", "Symbol", "Entry", "Exit", "Entry Px", "Exit Px", "Trade Size", "Ret %", "PNL ($)", "Side", "Prob", "Equity Before", "Equity After", "Hold Minutes", "Fee", "Status"];
    const lines = [headers.join(",")];
    rows.forEach((r) => {
      const cells = Array.from(r.cells).map((td) => `"${td.textContent.trim().replace(/"/g,'""')}"`);
      lines.push(cells.join(","));
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `concurrent_trades_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    logFeed(`Exported ${rows.length} trades to CSV.`, "ok");
  }

  const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

  async function fetchDataset() {
    if (!fetchStatus) return;
    const symbols = selectedAssets();
    if (!symbols.length) {
      alert("Select at least one asset to fetch data.");
      return;
    }
    const start = startInput.value || "2021-01-01";
    const outputPath = datasetInput.value.trim() || `ml_pipeline/data/div_custom_${Date.now()}.csv`;
    let failed = [];
    fetchBtn.disabled = true;
    fetchStatus.textContent = "Fetching...";
    fetchStatus.classList.remove("idle","err");
    fetchStatus.classList.add("run");
    logFeed(`Scanning cache and preparing ${symbols.length} symbols @ ${timeframeSelect?.value || "3m"} from ${start} to ${endInput.value || "latest"}`, "info");

    for (let i = 0; i < symbols.length; i++) {
      const sym = symbols[i];
      let ok = false;
      logFeed(`${sym}: scanning cache and syncing window...`, "muted");
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          logFeed(`${sym}: fetch attempt ${attempt}/3`, "info");
          const res = await fetch(`${api()}/datasets/build_step`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              symbol: sym,
              timeframe: timeframeSelect?.value || "3m",
              start_date: start,
              end_date: endInput.value || null,
              output_path: outputPath,
              cache_path: cacheInput?.value.trim() || null,
              truncate: i === 0 && attempt === 1, // fresh file on first symbol
            }),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Failed to fetch symbol");
          datasetInput.value = data.path || outputPath;
          (data.messages || []).forEach((m) => logFeed(m, "muted"));
          logFeed(`${sym}: data ready, rows=${data.rows}`, "ok");
          ok = true;
          break;
        } catch (err) {
          const msg = (err?.message || "").toLowerCase();
          const rate = msg.includes("429") || msg.includes("rate") || msg.includes("too many");
          if (rate && attempt < 3) {
            const waitSec = 12 * attempt;
            logFeed(`${sym}: rate limit, waiting ${waitSec}s before retry...`, "err");
            for (let t = waitSec; t >= 1; t--) {
              logFeed(`${sym}: cooldown ${t}s`, "muted");
              // lightweight countdown without blocking UI
              // avoid spamming too much
              await sleep(1000);
            }
            continue;
          } else {
            logFeed(`${sym}: failed attempt ${attempt}/3 (${err?.message || err})`, "error");
          }
        }
      }
      if (!ok) failed.push(sym);
      // small pause between symbols to avoid burst
      if (i < symbols.length - 1) await sleep(400);
    }

    if (failed.length === symbols.length) {
      fetchStatus.textContent = "Error";
      fetchStatus.classList.remove("run");
      fetchStatus.classList.add("err");
      logFeed("All symbols failed; no data written.", "error");
    } else if (failed.length) {
      fetchStatus.textContent = `Partial (failed: ${failed.length})`;
      fetchStatus.classList.remove("err");
      fetchStatus.classList.add("run");
      logFeed(`Completed with failures: ${failed.join(", ")}`, "error");
    } else {
      fetchStatus.textContent = "Fetched";
      fetchStatus.classList.remove("err");
      fetchStatus.classList.add("run");
      logFeed("Fetch complete for all symbols.", "ok");
      try { chime && chime.play(); } catch(_) {}
    }
    fetchBtn.disabled = false;
  }


  async function runBacktest() {
    try {
      if (!datasetInput.value.trim()) {
        alert("Please fetch data or provide a dataset path before running the backtest.");
        return;
      }
      setRunning(true, "Running...");
      const body = payload();
      const res = await fetch(`${api()}/backtest/concurrent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Concurrent backtest failed");
      renderStats(data.summary || {});
      renderChart(data.equity_curve || []);
      renderSymbols(data.symbols || []);
      renderTrades(data.trades || []);
      runStatus.textContent = "Complete";
      runStatus.classList.remove("idle");
      runStatus.classList.add("run");
    } catch (err) {
      console.error(err);
      runStatus.textContent = err.message || "Error";
      runStatus.classList.remove("idle","run");
      runStatus.classList.add("err");
      statNote.textContent = err.message || "Failed to run backtest.";
    } finally {
      setTimeout(() => setRunning(false, "Idle"), 1500);
    }
  }

  populateAssets();
  initFormDefaults();
  // Bind custom asset adder
  const addBtn = $("#asset-add");
  const assetInput = $("#asset-input");
  addBtn?.addEventListener("click", () => {
    addAsset(assetInput.value);
    assetInput.value = "";
  });
  const selectAllBtn = $("#asset-select-all");
  selectAllBtn?.addEventListener("click", () => {
    assetGrid.querySelectorAll("input[type='checkbox']").forEach((el, idx) => {
      if (idx < 30) el.checked = true;
    });
    updateCount();
  });
  const clearBtn = $("#asset-clear");
  clearBtn?.addEventListener("click", () => {
    assetGrid.querySelectorAll("input[type='checkbox']").forEach((el) => { el.checked = false; });
    updateCount();
  });
  assetInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addAsset(assetInput.value);
      assetInput.value = "";
    }
  });
  assetInput?.addEventListener("input", () => buildSuggestions(assetInput.value));
  assetGrid?.addEventListener("change", updateCount);
  if (cacheInput && !cacheInput.value) cacheInput.value = "cache_data";
  runBtn?.addEventListener("click", runBacktest);
  fetchBtn?.addEventListener("click", fetchDataset);
  $("#export-concurrent-csv")?.addEventListener("click", exportTradesCsv);
})();
