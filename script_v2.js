// Clean Lab wiring and product gating
(function(){
  const $ = (s)=>document.querySelector(s);
  const $$ = (s)=>Array.from(document.querySelectorAll(s));

  // Year footer
  try{ const y=new Date().getFullYear(); $$('.year,#year').forEach(el=>el.textContent=y); }catch(_){ }

  const hud = document.getElementById('bt-hud');
  const hudText = hud ? hud.querySelector('.hud-text') : null;
  const btStatus = document.getElementById('bt-status');
  const serverIndicator = document.getElementById('server-indicator');
  const serverDot = serverIndicator ? serverIndicator.querySelector('.dot') : null;
  const serverLabel = serverIndicator ? serverIndicator.querySelector('.label') : null;
  const goLiveBtn = document.getElementById('go-live');
  if (goLiveBtn) {
    goLiveBtn.addEventListener('click', () => {
      window.location.href = 'live_mystrix+.html';
    });
  }

  function setBtState(msg, spinning){
    if (btStatus) btStatus.textContent = msg || '';
    if (!hud) return;
    if (spinning){
      hud.classList.add('active');
      if (hudText) hudText.textContent = msg || 'Running Backtest';
    } else {
      hud.classList.remove('active');
    }
  }

  function setServerIndicator(ok){
    if (!serverIndicator) return;
    serverIndicator.classList.toggle('online', ok);
    serverIndicator.classList.toggle('offline', !ok);
    if (serverDot){
      serverDot.classList.toggle('online', ok);
      serverDot.classList.toggle('offline', !ok);
    }
    if (serverLabel){
      serverLabel.textContent = ok ? 'Server Live' : 'Server Offline';
    }
  }

  // API base
  function apiBase(){ try{ return window.API_BASE || location.origin || 'http://127.0.0.1:8000'; }catch(_){ return 'http://127.0.0.1:8000'; } }

  // Health
  async function health(){
    const base=apiBase();
    try{
      const r=await fetch(base+'/healthz');
      const ok=r.ok;
      const dot=$('#srv-status .status-dot');
      const lab=$('#srv-status');
      if(dot) dot.className='status-dot '+(ok?'dot-on':'dot-off');
      if(lab) lab.innerHTML='API: <span class="status-dot '+(ok?'dot-on':'dot-off')+'"></span> ' + (ok?'Online':'Not running');
      setServerIndicator(ok);
      return ok;
    }catch(_){
      setServerIndicator(false);
      return false;
    }
  }

  // Product gating - Short always available, HTF for Mystrix+, Universe for Ultimate
  function gateProduct(p){ try{
    const htf=$('#htf-gate'); const ult=$('#ultimate-panel');
    if(htf) htf.style.display = (p==='mystrixplus') ? 'block' : 'none';
    if(ult) ult.style.display = (p==='ultimate') ? 'block' : 'none';
    localStorage.setItem('product', p);
  }catch(_){ }
  function bindProduct(){
    $$('#product-switch [data-prod]').forEach(b=>{
      b.addEventListener('click', ()=> gateProduct(b.getAttribute('data-prod')));
    });
    const last = localStorage.getItem('product') || 'mystrix';
    gateProduct(last);
  }

  // Long/Short visibility via toggles
  function bindToggles(){
    const L=$('#long-rsi'), S=$('#short-rsi'); const tl=$('#en-long'), ts=$('#en-short');
    const apply=()=>{ if(L&&tl) L.style.display = tl.checked? 'block':'none'; if(S&&ts) S.style.display = ts.checked? 'block':'none'; };
    tl&&tl.addEventListener('change', apply, {passive:true}); ts&&ts.addEventListener('change', apply, {passive:true}); apply();
  }

  // Helpers
  function get(id, def){ const el=document.getElementById(id); return el?el.value:def; }
  function on(id){ const el=document.getElementById(id); return !!(el&&el.checked); }

  // Load symbols into datalist
  async function loadSymbols(){ try{ const r=await fetch(apiBase()+'/symbols'); if(!r.ok) return; const data=await r.json(); const dl=$('#symbols-list'); if(!dl) return; dl.innerHTML=''; (data.symbols||[]).forEach(s=>{ const o=document.createElement('option'); o.value=s; dl.appendChild(o); }); }catch(_){ } }

  // Backtest
  async function runBacktest(){
    const base=apiBase(); const out=$('#bt-out'); if(out) out.innerHTML='';
    setBtState('Running backtest...', true);
    const syms=(get('bt-symbols','BTC/USDT').split(',').map(s=>s.trim()).filter(Boolean));
    const symbol = syms[0] || 'BTC/USDT';
    const tf=get('bt-tf','3m'); const start=get('bt-start',''); const end=get('bt-end','');
    const enLong=on('en-long'); const enShort=on('en-short');
    const engine = (enLong&&enShort)? 'both' : (enShort? 'short' : 'long');
    function ovLong(){ const pctStop=parseFloat(get('bt-pct-stop',1.8))/100; const rpct=parseFloat(get('bt-risk-pct',10))/100; const cd = on('bt-cooldown-en')? parseInt(get('bt-cooldown',15)) : 0; return {
      timeframe_hist: tf, rsi_length: parseInt(get('bt-rsi-length',14)), rsi_overbought: parseInt(get('bt-rsi-ob',79)), rsi_oversold: parseInt(get('bt-rsi-os',27)),
      lookbackLeft: parseInt(get('bt-lb-left',5)), lookbackRight: parseInt(get('bt-lb-right',5)), rangeLower: parseInt(get('bt-range-low',5)), rangeUpper: parseInt(get('bt-range-up',60)),
      use_pct_stop: pctStop, max_wait_bars: parseInt(get('bt-max-wait',25)), cooldownBars: cd, initial_capital: parseFloat(get('bt-initial',10000)), percent_risk: rpct
    }; }
    function ovShort(){ const pctStop=parseFloat(get('sb-pct-stop',1.8))/100; const rpct=parseFloat(get('sb-risk-pct',10))/100; const cd = on('sb-cooldown-en')? parseInt(get('sb-cooldown',15)) : 0; return {
      timeframe_hist: tf, rsi_length: parseInt(get('sb-rsi-length',14)), rsi_overbought: parseInt(get('sb-rsi-ob',79)), rsi_oversold: parseInt(get('sb-rsi-os',27)),
      lookbackLeft: parseInt(get('sb-lb-left',5)), lookbackRight: parseInt(get('sb-lb-right',5)), rangeLower: parseInt(get('sb-range-low',5)), rangeUpper: parseInt(get('sb-range-up',60)),
      use_pct_stop: pctStop, max_wait_bars: parseInt(get('sb-max-wait',25)), cooldownBars: cd, initial_capital: parseFloat(get('sb-initial',10000)), percent_risk: rpct
    }; }
    const overrides = (engine==='short')? ovShort() : ovLong();
    try{
      const r = await fetch(base+'/backtest', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ symbols:[symbol], start, end, overrides, engine }) });
      const j = await r.json();
      if(!r.ok){ out.innerHTML = `<p class="status">${(j&&j.detail)||'Backtest error'}</p>`; setBtState('Backtest failed', false); return; }
      renderBacktest(j, engine, out);
      setBtState('Backtest completed', false);
    }catch(e){
      if(out) out.innerHTML=`<p class="status">${e&&e.message||e}</p>`;
      setBtState(`Backtest failed: ${e&&e.message?e.message:e}`, false);
    }
  }

  function renderBacktest(data, engine, out){
    function table(obj){ const rows=Object.entries(obj||{}).map(([k,v])=>`<tr><td>${k}</td><td>${v}</td></tr>`).join(''); return `<table class="trades"><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>${rows}</tbody></table>`; }
    function drawPrice(id, candles, markers){ const c=document.getElementById(id); if(!c) return; const ctx=c.getContext('2d'); const W=c.width,H=c.height,p=36; const vals=candles||[]; if(!vals.length){ ctx.clearRect(0,0,W,H); return; } const hi=Math.max(...vals.map(k=>Number(k.h||k.high||0))); const lo=Math.min(...vals.map(k=>Number(k.l||k.low||0))); const xMin=0,xMax=vals.length-1; const x=(i)=> p + (W-2*p)*((i-xMin)/Math.max(1,(xMax-xMin))); const y=(v)=> H-p - (H-2*p) * ((v-lo)/Math.max(1,hi-lo)); ctx.clearRect(0,0,W,H); ctx.strokeStyle='rgba(150,150,150,0.3)'; ctx.strokeRect(p,p,W-2*p,H-2*p); vals.forEach((k,i)=>{ const X=x(i); const o=Number(k.o||k.open),h=Number(k.h||k.high),l=Number(k.l||k.low),cl=Number(k.c||k.close); ctx.strokeStyle= cl>=o? '#59f39b':'#f66'; ctx.beginPath(); ctx.moveTo(X, y(l)); ctx.lineTo(X, y(h)); ctx.stroke(); ctx.lineWidth=3; ctx.beginPath(); ctx.moveTo(X-2, y(o)); ctx.lineTo(X+2, y(cl)); ctx.stroke(); ctx.lineWidth=1; }); (markers||[]).forEach(m=>{ const i=vals.findIndex(k=>k.t===m.t); if(i<0) return; const X=x(i); const Y=y(Number(m.price)); ctx.fillStyle = (m.side==='short')? '#f59e0b' : '#22c55e'; if(String(m.type||'').startsWith('exit')) ctx.fillStyle = (m.side==='short')? '#fb923c' : '#ef4444'; ctx.beginPath(); ctx.arc(X,Y,3,0,Math.PI*2); ctx.fill(); }); }
    const chartId = 'bt-price-'+Math.random().toString(16).slice(2);
    const chart = `<div class="chart-wrap" style="margin-top:8px;"><canvas id="${chartId}" width="980" height="320" style="max-width:100%"></canvas></div>`;
    out.innerHTML = table(data.metrics||{}) + chart + (data.trades&&data.trades.length? `<div class="results"><table class="trades"><thead><tr><th>t</th><th>type</th><th>price</th><th>pnl</th><th>side</th></tr></thead><tbody>${(data.trades||[]).map(t=>`<tr><td>${t.t||''}</td><td>${t.type||''}</td><td>${t.price||''}</td><td>${t.pnl||''}</td><td>${t.side||engine}</td></tr>`).join('')}</tbody></table></div>` : '<p class="status">No trades.</p>');
    setTimeout(()=> drawPrice(chartId, data.candles||[], data.markers||[]), 0);
  }

  // Live Signals
  async function scanSignals(){ const base=apiBase(); const symbols=get('ls-symbols','BTC/USDT,ETH/USDT'); const tf=get('ls-tf','3m'); const bars=500; const url=new URL(base+'/signals'); url.searchParams.set('symbols', symbols); url.searchParams.set('timeframe', tf); url.searchParams.set('bars', bars); const out=$('#signals'); try{ const r=await fetch(url.toString()); const j=await r.json(); if(!r.ok){ out.innerHTML='<p class="status">Error</p>'; return; } const tbl = `<table class="signals"><thead><tr><th>Symbol</th><th>Price</th><th>RSI</th><th>Action</th></tr></thead><tbody>${(j.signals||[]).map(s=>`<tr><td>${s.symbol}</td><td>${Number(s.price).toFixed(4)}</td><td>${Number(s.rsi).toFixed(2)}</td><td>${(s.signal||{}).action||'HOLD'}</td></tr>`).join('')}</tbody></table>`; out.innerHTML=tbl; const sel=$('#ls-symbol-list'); if(sel){ sel.innerHTML=(j.signals||[]).map(s=>`<option value="${s.symbol}">${s.symbol}</option>`).join(''); } $('#ls-logs').innerHTML=''; }catch(_){ out.innerHTML='<p class="status">Scan error</p>'; } }

  // Chart (Pine Long)
  async function fetchSignal(){ const base=apiBase(); const symbol=get('sc-symbol','BTC/USDT'); const timeframe=get('sc-tf','3m'); const bars=parseInt(get('sc-bars',400)); const url=new URL(base+'/pine/signal'); url.searchParams.set('symbol', symbol); url.searchParams.set('timeframe', timeframe); url.searchParams.set('bars', String(bars)); try{ const r=await fetch(url.toString()); const j=await r.json(); const c=$('#sig-canvas'); const ctx=c.getContext('2d'); ctx.clearRect(0,0,c.width,c.height); const candles=(j.chart&&j.chart.candles)||j.candles||[]; const markers=(j.chart&&j.chart.markers)||j.markers||[]; // draw simplified
      const W=c.width,H=c.height,p=36; if(!candles.length){ return; } const hi=Math.max(...candles.map(k=>Number(k.h||k.high||0))); const lo=Math.min(...candles.map(k=>Number(k.l||k.low||0))); const xMin=0,xMax=candles.length-1; const x=i=> p+(W-2*p)*((i-xMin)/Math.max(1,(xMax-xMin))); const y=v=> H-p-(H-2*p)*((v-lo)/Math.max(1,hi-lo)); ctx.strokeStyle='rgba(150,150,150,0.3)'; ctx.strokeRect(p,p,W-2*p,H-2*p); candles.forEach((k,i)=>{ const X=x(i); const o=Number(k.o||k.open),h=Number(k.h||k.high),l=Number(k.l||k.low),cl=Number(k.c||k.close); ctx.strokeStyle= cl>=o? '#59f39b':'#f66'; ctx.beginPath(); ctx.moveTo(X, y(l)); ctx.lineTo(X, y(h)); ctx.stroke(); ctx.lineWidth=3; ctx.beginPath(); ctx.moveTo(X-2, y(o)); ctx.lineTo(X+2, y(cl)); ctx.stroke(); ctx.lineWidth=1; }); (markers||[]).forEach(m=>{ const i=candles.findIndex(k=>k.t===m.t); if(i<0) return; const X=x(i), Y=y(Number(m.price)); ctx.fillStyle=(m.side==='short')?'#f59e0b':'#22c55e'; if(String(m.type||'').startsWith('exit')) ctx.fillStyle=(m.side==='short')?'#fb923c':'#ef4444'; ctx.beginPath(); ctx.arc(X,Y,3,0,Math.PI*2); ctx.fill(); }); }catch(_){ }
  }

  function bindActions(){
    $('#recheck')&&$('#recheck').addEventListener('click', health);
    $('#run-backtest')&&$('#run-backtest').addEventListener('click', runBacktest);
    $('#ls-scan')&&$('#ls-scan').addEventListener('click', scanSignals);
    $('#sc-fetch')&&$('#sc-fetch').addEventListener('click', fetchSignal);
  }

  function initDates(){ const s=$('#bt-start'), e=$('#bt-end'); const today=new Date(); const past=new Date(); past.setMonth(today.getMonth()-1); if(s&&!s.value) s.value=past.toISOString().slice(0,10); if(e&&!e.value) e.value=today.toISOString().slice(0,10); }

  function init(){ bindProduct(); bindToggles(); initDates(); bindActions(); loadSymbols(); health(); }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init, {once:true}); else init();
})();

