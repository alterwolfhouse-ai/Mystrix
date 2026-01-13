(() => {
  const $ = (sel) => document.querySelector(sel);
  const apiBase = () => {
    try { return window.API_BASE || location.origin; }
    catch (_) { return location.origin; }
  };

  let lastLog = null;
  let audioCtx = null;
  const MAX_FEED_ENTRIES = 10;
  const MAX_NOTIFICATIONS = 6;

  const statusIndicator = document.getElementById('exp-status-indicator');
  const feedPanel = document.getElementById('exp-feed');
  const statusText = document.getElementById('exp-status');
  const notifyPanel = document.getElementById('notify-list');
  const chartRefs = {
    combined: document.getElementById('chart-combined'),
    bull: document.getElementById('chart-bull'),
    bear: document.getElementById('chart-bear'),
  };

  const stateMeta = {
    idle: { label: 'Idle / Ready', className: 'state-idle' },
    running: { label: 'Streaming Divergences', className: 'state-running' },
    success: { label: 'Completed', className: 'state-success' },
    error: { label: 'Error', className: 'state-error' },
  };

  const fmt = (val, digits = 2) => {
    if (val === undefined || val === null || Number.isNaN(val)) return '--';
    return Number(val).toLocaleString(undefined, { maximumFractionDigits: digits });
  };

  const playChime = () => {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const ctx = audioCtx;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.7);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.7);
    } catch (_) {}
  };

  const pushFeed = (message, state = 'info') => {
    if (!feedPanel) return;
    const entry = document.createElement('div');
    entry.className = `feed-entry ${state}`;
    const ts = new Date().toLocaleTimeString();
    entry.innerHTML = `<span class="msg">${message}</span><span class="time">${ts}</span>`;
    feedPanel.prepend(entry);
    const rows = Array.from(feedPanel.querySelectorAll('.feed-entry'));
    if (rows.length > MAX_FEED_ENTRIES) rows.slice(MAX_FEED_ENTRIES).forEach((el) => el.remove());
  };

  const addNotification = (message, tone = 'info') => {
    if (!notifyPanel) return;
    const entry = document.createElement('div');
    entry.className = `notify-entry ${tone}`;
    entry.textContent = message;
    notifyPanel.prepend(entry);
    const rows = Array.from(notifyPanel.querySelectorAll('.notify-entry'));
    if (rows.length > MAX_NOTIFICATIONS) rows.slice(MAX_NOTIFICATIONS).forEach((el) => el.remove());
    if (tone === 'success') playChime();
  };

  const exportFeed = () => {
    const rows = Array.from(feedPanel?.querySelectorAll('.feed-entry') || []);
    if (!rows.length) return;
    const headers = ['Message','Time'];
    const lines = [headers.join(',')];
    rows.reverse().forEach((row) => {
      const msg = row.querySelector('.msg')?.textContent?.trim() || '';
      const time = row.querySelector('.time')?.textContent?.trim() || '';
      const safe = (val) => `"${(val || '').replace(/\"/g,'\"\"')}"`;
      lines.push([safe(msg), safe(time)].join(','));
    });
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `experiment_feed_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const setStatus = (msg, kind = 'info') => {
    if (statusText) {
      statusText.textContent = msg;
      statusText.style.color = kind === 'error' ? '#ff9eae' : 'var(--exp-muted)';
    }
  };

  const setRunState = (state = 'idle', message) => {
    const meta = stateMeta[state] || stateMeta.idle;
    if (statusIndicator) {
      Object.values(stateMeta).forEach((cfg) => statusIndicator.classList.remove(cfg.className));
      statusIndicator.classList.add(meta.className);
      const label = statusIndicator.querySelector('.label');
      if (label) label.textContent = message || meta.label;
    }
    const feedTone = state === 'running' ? 'running' : state === 'success' ? 'success' : state === 'error' ? 'error' : 'info';
    pushFeed(message || meta.label, feedTone);
    addNotification(message || meta.label, feedTone);
    if (state === 'success') playChime();
    setStatus(message || meta.label, state === 'error' ? 'error' : 'info');
  };

  const updateSliderLabel = (slider, target, formatter) => {
    if (!slider || !target) return;
    const apply = () => target.textContent = formatter(slider.value);
    slider.addEventListener('input', apply, { passive: true });
    apply();
  };

  const renderSymbols = (symbols) => {
    const body = document.getElementById('symbol-stats');
    if (!body) return;
    const entries = Object.entries(symbols || {});
    if (!entries.length) {
      body.innerHTML = '<tr><td colspan="4" style="text-align:center;opacity:.6;">No symbol data</td></tr>';
      return;
    }
    body.innerHTML = entries
      .map(([sym, row]) => `<tr><td>${sym}</td><td>${fmt(row.rows, 0)}</td><td>${fmt(row.good, 0)}</td><td>${fmt(row.bad, 0)}</td></tr>`)
      .join('');
  };

  const loadDatasetStats = async () => {
    const dsInput = document.getElementById('exp-dataset');
    const dsPath = (dsInput?.value || '').trim();
    if (!dsPath) {
      setStatus('Dataset path not set. Fetch dataset first.', 'error');
      setRunState('idle', 'Awaiting dataset');
      return;
    }
    setStatus('Fetching dataset stats...');
    try {
      const r = await fetch(`${apiBase()}/experiment/dataset_stats?dataset_path=${encodeURIComponent(dsPath)}`);
      if (!r.ok) throw new Error('Unable to load stats');
      const data = await r.json();
      const totalEl = document.getElementById('stat-total');
      const goodEl = document.getElementById('stat-good');
      const badEl = document.getElementById('stat-bad');
      const updEl = document.getElementById('stat-updated');
      const dsEl = document.getElementById('stat-dataset');
      if (totalEl) totalEl.textContent = fmt(data.total_rows, 0);
      if (goodEl) goodEl.textContent = fmt(data.good_labels, 0);
      if (badEl) badEl.textContent = fmt(data.bad_labels, 0);
      if (updEl) updEl.textContent = data.updated_at || '--';
      if (dsEl) dsEl.textContent = data.dataset_path || '';
      renderSymbols(data.symbols);
      setStatus('Dataset stats refreshed');
      setRunState('idle', 'Dataset ready');
    } catch (err) {
      console.error(err);
      setStatus(err.message || 'Failed to load dataset stats', 'error');
      setRunState('error', err.message || 'Dataset load failed');
    }
  };

  const setSummaryValues = (summary = {}) => {
    const trades = summary.num_trades ?? summary.trades ?? 0;
    const tradeEl = document.getElementById('summary-trades');
    const winEl = document.getElementById('summary-win');
    const eqEl = document.getElementById('summary-equity');
    const retEl = document.getElementById('summary-return');
    const ddEl = document.getElementById('summary-dd');
    const bullEl = document.getElementById('summary-bull');
    const bearEl = document.getElementById('summary-bear');
    if (tradeEl) tradeEl.textContent = fmt(trades, 0);
    if (winEl) winEl.textContent = `${fmt(summary.win_rate_pct ?? 0, 2)}%`;
    if (eqEl) eqEl.textContent = `$${fmt(summary.final_equity ?? 0, 2)}`;
    if (retEl) retEl.textContent = `${fmt(summary.total_return_pct ?? 0, 2)}%`;
    if (ddEl) ddEl.textContent = `${fmt(summary.max_drawdown_pct ?? 0, 2)}%`;
    const counts = summary.divergence_counts || {};
    if (bullEl) bullEl.textContent = fmt(counts.bull ?? 0, 0);
    if (bearEl) bearEl.textContent = fmt(counts.bear ?? 0, 0);
  };

  const renderPreview = (rows) => {
    const body = document.getElementById('preview-body');
    if (!body) return;
    if (!rows || !rows.length) {
      body.innerHTML = '<tr><td colspan="8" style="text-align:center;opacity:.6;">No trades returned from ML gate.</td></tr>';
      return;
    }
    body.innerHTML = rows.map((row) => {
      const conf = Number(row.ml_confidence ?? row.confidence ?? 0);
      return `<tr>
        <td>${row.trade_no || ''}</td>
        <td>${row.symbol || ''}</td>
        <td>${row.entry_time || ''}</td>
        <td>${row.exit_time || ''}</td>
        <td>${fmt(row.entry_price, 4)}</td>
        <td>${fmt(row.exit_price, 4)}</td>
        <td>${fmt(row.ret_pct, 2)}</td>
        <td>${fmt(row.pnl, 2)}</td>
        <td>${row.divergence || ''}</td>
        <td>${fmt(conf * 100, 2)}%</td>
        <td>${row.status || row.ml_action || ''}</td>
      </tr>`;
    }).join('');
  };

  const drawNeonChart = (canvas, points, color) => {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    if (!points || !points.length) {
      ctx.fillStyle = 'rgba(255,255,255,0.35)';
      ctx.font = '12px "IBM Plex Mono"';
      ctx.textAlign = 'center';
      ctx.fillText('No trades', W / 2, H / 2);
      return;
    }
    const vals = points.map((p) => Number(p.equity));
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const pad = 30;
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.strokeRect(pad - 6, pad - 12, W - 2 * (pad - 6), H - 2 * (pad - 12));
    ctx.beginPath();
    points.forEach((pt, idx) => {
      const x = pad + (idx / Math.max(1, points.length - 1)) * (W - 2 * pad);
      const range = max - min || 1;
      const y = H - pad - ((Number(pt.equity) - min) / range) * (H - 2 * pad);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.lineWidth = 3;
    ctx.strokeStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = 12;
    ctx.stroke();
    ctx.shadowBlur = 0;
  };

  const renderCharts = (series = {}) => {
    drawNeonChart(chartRefs.combined, series.combined || [], '#c084fc');
    drawNeonChart(chartRefs.bull, series.bull || [], '#7f5af0');
    drawNeonChart(chartRefs.bear, series.bear || [], '#ff6ad5');
  };

  const parseSymbols = () => {
    const raw = (document.getElementById('exp-symbols')?.value || '').split(',');
    const cleaned = raw.map((s) => s.trim()).filter(Boolean);
    return cleaned.length ? cleaned : ['BTC/USDT'];
  };

  const fetchDataset = async () => {
    const btn = document.getElementById('fetch-dataset');
    if (btn) btn.disabled = true;
    setRunState('running', 'Fetching dataset from exchange...');
    const payload = {
      symbols: parseSymbols(),
      timeframe: document.getElementById('exp-timeframe')?.value || '3m',
      start_date: document.getElementById('exp-start')?.value || '2020-01-01',
      end_date: document.getElementById('exp-end')?.value || null,
      dataset_path: document.getElementById('exp-dataset')?.value || undefined,
      stop_pct: Number(document.getElementById('exp-stop')?.value || 3) / 100,
      target_pct: Number(document.getElementById('exp-target')?.value || 1.5) / 100,
    };
    try {
      const r = await fetch(`${apiBase()}/experiment/fetch_dataset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      if (!r.ok) {
        throw new Error(data && data.detail ? data.detail : 'Fetch failed');
      }
      const dsInput = document.getElementById('exp-dataset');
      if (dsInput) dsInput.value = data.dataset_path || dsInput.value;
      setRunState('success', `Dataset ready (${fmt(data.rows, 0)} rows)`);
      await loadDatasetStats();
    } catch (err) {
      console.error(err);
      setRunState('error', err.message || 'Dataset fetch failed');
    } finally {
      if (btn) btn.disabled = false;
    }
  };

  const runExperiment = async () => {
    const btn = document.getElementById('run-experiment');
    if (btn) btn.disabled = true;
    const datasetPath = (document.getElementById('exp-dataset')?.value || '').trim();
    if (!datasetPath) {
      setRunState('error', 'Dataset path missing. Fetch dataset first.');
      if (btn) btn.disabled = false;
      return;
    }
    setRunState('running', 'Streaming divergences to ML filter...');
    const payload = {
      symbols: parseSymbols(),
      start_date: document.getElementById('exp-start')?.value || '2020-01-01',
      end_date: document.getElementById('exp-end')?.value || null,
      timeframe: document.getElementById('exp-timeframe')?.value || '3m',
      initial_capital: Number(document.getElementById('exp-capital')?.value || 10000),
      threshold: Number(document.getElementById('exp-threshold')?.value || 0.65),
      equity_risk: Number(document.getElementById('exp-risk')?.value || 0.02),
      dataset_path: datasetPath,
      model_path: document.getElementById('exp-model')?.value || 'ml_pipeline/models/ml_filter.pkl',
      stop_pct: Number(document.getElementById('exp-stop')?.value || 3) / 100,
      target_pct: Number(document.getElementById('exp-target')?.value || 1.5) / 100,
      holding_minutes_hint: Number(document.getElementById('exp-hold')?.value || 0),
      log_name: document.getElementById('exp-log-name')?.value || undefined,
    };
    try {
      const r = await fetch(`${apiBase()}/experiment/run_plus`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      if (!r.ok) {
        const detail = data && (data.detail || JSON.stringify(data));
        throw new Error(detail || 'Experiment failed');
      }
      const summary = data.summary || {};
      setSummaryValues(summary);
      renderPreview(data.trades_preview || []);
      renderCharts(data.series || {});
      lastLog = summary.log_name || null;
      const logBtn = document.getElementById('download-log');
      if (logBtn) {
        logBtn.disabled = !lastLog;
        logBtn.dataset.log = lastLog ? `/static/experiment/logs/${lastLog}` : '';
      }
      setRunState('success', 'Experiment completed');
    } catch (err) {
      console.error(err);
      setRunState('error', err.message || 'Experiment error');
    } finally {
      if (btn) btn.disabled = false;
    }
  };

  const downloadLog = () => {
    const logBtn = document.getElementById('download-log');
    if (!logBtn || !logBtn.dataset.log) return;
    window.open(logBtn.dataset.log, '_blank');
  };

  document.addEventListener('DOMContentLoaded', () => {
    updateSliderLabel(document.getElementById('exp-threshold'), document.getElementById('exp-threshold-val'), (v) => Number(v).toFixed(2));
    updateSliderLabel(document.getElementById('exp-risk'), document.getElementById('exp-risk-val'), (v) => `${(Number(v) * 100).toFixed(1)}%`);
    setRunState('idle', 'Awaiting command');
    pushFeed('Ready for dataset fetch', 'info');
    addNotification('Experiment console loaded', 'info');
    loadDatasetStats();
  });

  document.getElementById('fetch-dataset')?.addEventListener('click', fetchDataset);
  document.getElementById('run-experiment')?.addEventListener('click', runExperiment);
  document.getElementById('download-log')?.addEventListener('click', downloadLog);
  document.getElementById('refresh-stats')?.addEventListener('click', loadDatasetStats);
  document.getElementById('exp-export-feed')?.addEventListener('click', exportFeed);
})();

