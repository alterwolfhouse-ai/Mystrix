const API = (typeof location !== 'undefined' && location.origin.startsWith('http')) ? location.origin : 'http://127.0.0.1:8000';
const $ = (s)=>document.querySelector(s);

async function fetchJSON(path){ const r=await fetch(API+path,{credentials:'include'}); if(!r.ok) throw new Error(await r.text()); return await r.json(); }

async function render(){ try{
  const users = (await fetchJSON('/admin/users')).users;
  const sug = (await fetchJSON('/admin/suggestions')).suggestions;
  $('#a-users').innerHTML = `<table class="trades"><thead><tr><th>ID</th><th>Email</th><th>Name</th><th>Admin</th><th>Created</th></tr></thead><tbody>${users.map(u=>`<tr><td>${u.id}</td><td>${u.email}</td><td>${u.name||''}</td><td>${u.is_admin?'yes':'no'}</td><td>${u.created_at||''}</td></tr>`).join('')}</tbody></table>`;
  $('#a-sug').innerHTML = `<table class="trades"><thead><tr><th>ID</th><th>User</th><th>Text</th><th>Created</th><th>Resolved</th><th></th></tr></thead><tbody>${sug.map(s=>`<tr><td>${s.id}</td><td>${s.email||''}</td><td>${s.text}</td><td>${s.created_at||''}</td><td>${s.resolved?'yes':'no'}</td><td>${s.resolved?'':`<button class='cta' data-id='${s.id}'>Resolve</button>`}</td></tr>`).join('')}</tbody></table>`;
  $('#a-sug').querySelectorAll('button[data-id]').forEach(b=> b.addEventListener('click', async ()=>{ const id=b.getAttribute('data-id'); try{ const r=await fetch(API+`/admin/suggestions/resolve?id=${id}`,{method:'POST',credentials:'include'}); if(r.ok) render(); }catch(_){ } }));
  $('#a-msg').textContent='';
}catch(e){ $('#a-msg').textContent=String(e); }
}

$('#a-refresh')?.addEventListener('click', render);
render();

// Defaults editor
async function loadDefaults(){ try{ const r=await fetch(API+'/defaults'); if(!r.ok) throw new Error(await r.text()); const d=await r.json(); $('#def-tf').value=d.timeframe_hist||'3m'; $('#def-json').value=JSON.stringify(d.overrides||{}, null, 2); $('#def-msg').textContent='Loaded.'; }catch(e){ $('#def-msg').textContent=String(e);} }
async function saveDefaults(){ try{ const tf=$('#def-tf').value.trim()||'3m'; let ov={}; try{ ov=JSON.parse($('#def-json').value||'{}'); }catch(e){ $('#def-msg').textContent='Invalid JSON'; return; } const r=await fetch(API+'/admin/defaults',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include', body:JSON.stringify({timeframe_hist:tf, overrides:ov})}); if(!r.ok) throw new Error(await r.text()); $('#def-msg').textContent='Saved.'; }catch(e){ $('#def-msg').textContent=String(e);} }
document.getElementById('def-load')?.addEventListener('click', loadDefaults);
document.getElementById('def-save')?.addEventListener('click', saveDefaults);
loadDefaults();

// Deep backtest uses current Magic settings persisted in localStorage
function overridesFromLocal(){ try{ const raw=localStorage.getItem('pine_settings_v1'); if(!raw) return {}; const d=JSON.parse(raw); return {
  rsi_length:Number(d.rsi_length||14), rsi_overbought:Number(d.rsi_ob||79), rsi_oversold:Number(d.rsi_os||27),
  lookbackLeft:Number(d.lb_left||5), lookbackRight:Number(d.lb_right||5), rangeLower:Number(d.range_low||5), rangeUpper:Number(d.range_up||60),
  use_pct_stop:Number(d.pct_stop||1.8)/100, max_wait_bars:Number(d.max_wait||25), cooldownBars:(d.cd_en?Number(d.cooldown||15):0),
  initial_capital:Number(d.initial||10000), percent_risk:Number(d.risk_pct||10)/100,
  enableHTFGate: !!d.htf_en, htfTF: (d.htf_tf||'30m'), htf_pct_stop: Number(d.htf_stop||20)/100,
  htf_rsi_length:Number(d.htf_rsi_length||14), htf_rsi_overbought:Number(d.htf_rsi_ob||79), htf_rsi_oversold:Number(d.htf_rsi_os||27),
  htf_lookbackLeft:Number(d.htf_lb_left||5), htf_lookbackRight:Number(d.htf_lb_right||5), htf_rangeLower:Number(d.htf_range_low||5), htf_rangeUpper:Number(d.htf_range_up||60), htf_max_wait_bars:Number(d.htf_max_wait||25)
}; }catch(_){ return {}; } }

// Deep backtest
async function runDeep(){ const sym=$('#db-symbol').value.trim()||'BTC/USDT'; const s=$('#db-start').value||null; const e=$('#db-end').value||null; const msg=$('#db-msg'); const out=$('#db-out'); msg.textContent='Running...'; try{ const body={symbol:sym, timeframe:'3m', overrides: overridesFromLocal()}; if(s) body.start=s; if(e) body.end=e; const r=await fetch(API+'/backtest/deep',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include', body:JSON.stringify(body)}); if(!r.ok) throw new Error(await r.text()); const data=await r.json(); msg.textContent='Done.'; out.innerHTML=renderMetrics(data.metrics)+renderTrades(data.trades); }catch(e){ msg.textContent=String(e);} }
document.getElementById('db-run')?.addEventListener('click', runDeep);
const today=new Date(); const monthsAgo=new Date(); monthsAgo.setMonth(today.getMonth()-6); document.getElementById('db-start').value=today.toISOString().slice(0,10); document.getElementById('db-end').value=today.toISOString().slice(0,10);

function renderMetrics(m){ const keys=[['Total Return (%)','Return'],['Num Trades','Trades'],['Win Rate (%)','Win Rate'],['Avg P&L','Avg P&L'],['Sharpe','Sharpe'],['Max Drawdown (%)','Max DD'],['Ending Equity','Equity']]; const cards=keys.map(([k,l])=>{ const v=(m&&m[k]!==undefined)?m[k]:'-'; return `<div class="metric"><div class="label">${l}</div><div class="value">${v}</div></div>`;}).join(''); return `<div class="metrics">${cards}</div>`; }
function renderTrades(items){ if(!items||!items.length) return '<p class="status">No trades.</p>'; const head='<tr><th>time</th><th>type</th><th>price</th></tr>'; const rows=items.slice(-200).map(t=>{ const price=t.price!==undefined?Number(t.price).toFixed(2):''; return `<tr><td>${t.t||''}</td><td>${t.type||''}</td><td>${price}</td></tr>`;}).join(''); return `<table class="trades"><thead>${head}</thead><tbody>${rows}</tbody></table>`; }

// Gate snapshot
async function refreshGate(){ const out=$('#gate-out'); out.innerHTML='<p class="status">Loading gate...</p>'; try{ const r=await fetch(API+'/gate/snapshot'); if(!r.ok) throw new Error(await r.text()); const d=await r.json(); const rows=(d.symbols||[]).map(s=>`<tr><td>${s.symbol}</td><td>${(s.score??0).toFixed(3)}</td><td>${(s.vroc_pct??0).toFixed(3)}</td></tr>`).join(''); const table=`<table class="trades"><thead><tr><th>Symbol</th><th>Score</th><th>VROC pct</th></tr></thead><tbody>${rows}</tbody></table>`; out.innerHTML=table; }catch(e){ out.innerHTML=`<p class='status'>${String(e)}</p>`; } }
document.getElementById('gate-refresh')?.addEventListener('click', refreshGate);
refreshGate();
// API status dot updater (same as Magic)
async function checkApi(){
  const status = document.getElementById('srv-status');
  const dot = status?.querySelector('.status-dot');
  const ctrl = new AbortController();
  const to = setTimeout(()=>ctrl.abort(), 3500);
  try{
    const res = await fetch(API + '/healthz', {signal: ctrl.signal});
    clearTimeout(to);
    const ok = res.ok;
    if(dot){ dot.classList.toggle('dot-on', ok); dot.classList.toggle('dot-off', !ok); }
    if(status) status.innerHTML = `API: <span class="status-dot ${ok?'dot-on':'dot-off'}"></span> ${ok?'Online':'Not running'}`;
  } catch(_){
    clearTimeout(to);
    if(dot){ dot.classList.add('dot-off'); dot.classList.remove('dot-on'); }
    if(status) status.innerHTML = 'API: <span class="status-dot dot-off"></span> Not running';
  }
}
(document.getElementById('recheck')||{}).addEventListener?.('click', checkApi);
setTimeout(checkApi, 250);
(document.getElementById('restart')||{}).addEventListener?.('click', async ()=>{ try{ await fetch(API+'/restart',{method:'POST'});}catch(_){}});

// Local Backtester (Admin)
function getVal(id){ return document.getElementById(id)?.value; }
function isChecked(id){ return !!document.getElementById(id)?.checked; }
async function runBacktest(){
  const results = document.getElementById('results');
  const btn = document.getElementById('run-backtest');
  try{
    if(results) results.innerHTML = '<p class="status">Running backtest...</p>';
    if(btn){ btn.disabled=true; btn.textContent='Working...'; }
    const symbols = (getVal('bt-symbols')||'BTC/USDT').split(',').map(s=>s.trim()).filter(Boolean);
    const overrides = {
      timeframe_hist: getVal('bt-tf')||'3m',
      rsi_length: Number(getVal('bt-rsi-length')||14),
      rsi_overbought: Number(getVal('bt-rsi-ob')||79),
      rsi_oversold: Number(getVal('bt-rsi-os')||27),
      lookbackLeft: Number(getVal('bt-lb-left')||5),
      lookbackRight: Number(getVal('bt-lb-right')||5),
      rangeLower: Number(getVal('bt-range-low')||5),
      rangeUpper: Number(getVal('bt-range-up')||60),
      use_pct_stop: Number(getVal('bt-pct-stop')||1.8)/100,
      max_wait_bars: Number(getVal('bt-max-wait')||25),
      cooldownBars: isChecked('bt-cooldown-en') ? Number(getVal('bt-cooldown')||15) : 0,
      initial_capital: Number(getVal('bt-initial')||10000),
      percent_risk: Number(getVal('bt-risk-pct')||10)/100,
      gate_enable: isChecked('gate-enable'),
      gate_base_tf: getVal('gate-base-tf')||'1h',
      gate_vroc_span: Number(getVal('gate-vroc-span')||8),
      gate_threshold: Number(getVal('gate-threshold')||0.65)
    };
    const payload = { symbols, start: getVal('bt-start')||'', end: getVal('bt-end')||'', engine: (getVal('bt-engine')||'long'), overrides };
    const res = await fetch(API+'/backtest',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    if(!res.ok) throw new Error(await res.text());
    const data = await res.json();
    if(results) results.innerHTML = renderMetrics(data.metrics) + renderTrades(data.trades);
  } catch(e){ if(results) results.innerHTML = `<p class="status">${String(e)}</p>`; }
  finally{ if(btn){ btn.disabled=false; btn.textContent='Run Backtest'; } try{ const ring=document.getElementById('bt-progress'); if(ring){ setTimeout(()=>{ ring.style.display='none'; }, 600); ring.style.background = 'conic-gradient(var(--accent,#7c4dff) 360deg, rgba(255,255,255,0.08) 0)'; const lab=document.getElementById('bt-progress-label'); if(lab) lab.textContent='100%'; } }catch(_){ } }
}
(document.getElementById('run-backtest')||{}).addEventListener?.('click', runBacktest);

// ---- Presets (Bull/Bear/Chop) per symbol ----
(function(){
  const KEY = 'asset_presets_v1';
  function load(){ try{ return JSON.parse(localStorage.getItem(KEY)||'{}'); }catch(_){ return {}; } }
  function save(obj){ localStorage.setItem(KEY, JSON.stringify(obj)); }
  function getSymbol(){ const v=document.getElementById('bt-symbols')?.value||''; return (v.split(',')[0]||'').trim().toUpperCase(); }
  function readParams(){ const G=id=>document.getElementById(id); return {
    rsi_length: Number(G('bt-rsi-length')?.value||14),
    rsi_overbought: Number(G('bt-rsi-ob')?.value||79),
    rsi_oversold: Number(G('bt-rsi-os')?.value||27),
    lookbackLeft: Number(G('bt-lb-left')?.value||5),
    lookbackRight: Number(G('bt-lb-right')?.value||5),
    rangeLower: Number(G('bt-range-low')?.value||5),
    rangeUpper: Number(G('bt-range-up')?.value||60),
    use_pct_stop: Number(G('bt-pct-stop')?.value||1.8)/100,
    max_wait_bars: Number(G('bt-max-wait')?.value||25),
    cooldownBars: (document.getElementById('bt-cooldown-en')?.checked? Number(G('bt-cooldown')?.value||15):0),
    initial_capital: Number(G('bt-initial')?.value||10000),
    percent_risk: Number(G('bt-risk-pct')?.value||10)/100,
  }; }
  function writeParams(p){ const S=(id,v)=>{ const el=document.getElementById(id); if(el) el.value=String(v); }; const C=(id,v)=>{ const el=document.getElementById(id); if(el) el.checked=!!v; };
    if(!p) return;
    S('bt-rsi-length', p.rsi_length); S('bt-rsi-ob', p.rsi_overbought); S('bt-rsi-os', p.rsi_oversold);
    S('bt-lb-left', p.lookbackLeft); S('bt-lb-right', p.lookbackRight);
    S('bt-range-low', p.rangeLower); S('bt-range-up', p.rangeUpper);
    S('bt-pct-stop', (Number(p.use_pct_stop||0)*100).toFixed(2));
    S('bt-max-wait', p.max_wait_bars);
    const cd = Number(p.cooldownBars||0); C('bt-cooldown-en', cd>0); S('bt-cooldown', cd||0);
    S('bt-initial', p.initial_capital); S('bt-risk-pct', (Number(p.percent_risk||0)*100).toFixed(2));
  }
  function setActive(slot){ ['bull','bear','chop'].forEach(s=>{
    const el=document.getElementById('preset-'+s); if(!el) return; el.classList.toggle('active', s===slot);
  }); document.getElementById('preset-status')?.replaceChildren(document.createTextNode('Preset: '+slot.toUpperCase())); }
  function apply(slot){ const sym=getSymbol(); const store=load(); const p=store?.[sym]?.[slot]; if(p) writeParams(p); setActive(slot); localStorage.setItem('last_preset_slot', slot); }
  function saveCurrent(slot){ const sym=getSymbol(); if(!sym){ notify?.('Enter a symbol to save preset','warn'); return; } const store=load(); store[sym] = store[sym]||{}; store[sym][slot] = readParams(); save(store); notify?.(`Saved ${slot.toUpperCase()} preset for ${sym}`,'info'); }
  // Bind UI
  document.getElementById('preset-bull')?.addEventListener('click', ()=>apply('bull'));
  document.getElementById('preset-bear')?.addEventListener('click', ()=>apply('bear'));
  document.getElementById('preset-chop')?.addEventListener('click', ()=>apply('chop'));
  document.getElementById('preset-save')?.addEventListener('click', ()=>{
    const slot = (prompt('Save preset to which slot? (bull / bear / chop)','bull')||'').trim().toLowerCase();
    if(!['bull','bear','chop'].includes(slot)) { notify?.('Invalid slot','warn'); return; }
    saveCurrent(slot);
  });
  // Auto-apply when symbol changes or page loads
  const symEl = document.getElementById('bt-symbols');
  symEl?.addEventListener('change', ()=>{ const slot=localStorage.getItem('last_preset_slot')||'bull'; apply(slot); });
  setTimeout(()=>{ const slot=localStorage.getItem('last_preset_slot')||'bull'; apply(slot); }, 300);
})();

// --- Progress helpers (UI only) ---
function setRing(el, pct){ if(!el) return; const deg = Math.max(0, Math.min(100, pct))*3.6; el.style.background = `conic-gradient(var(--accent,#7c4dff) ${deg}deg, rgba(255,255,255,0.08) 0)`; const lab=el.querySelector('span'); if(lab) lab.textContent = `${Math.round(Math.max(0,Math.min(100,pct)))}%`; }
function animateProgress(el, startPct, endPct, ms){ const t0=Date.now(); el.style.display='inline-block'; function tick(){ const dt=Date.now()-t0; const p = Math.min(1, dt/ms); const v = startPct + (endPct-startPct)*p; setRing(el, v); if(p<1) requestAnimationFrame(tick); } tick(); }

// Hook backtest run to show a progress ring (UI-driven)
(function(){ const btn=document.getElementById('run-backtest'); const ring=document.getElementById('bt-progress'); if(!btn||!ring) return; const orig = (window._runBacktestOrig || null);
  // Wrap existing handler
})();

// Re-bind runBacktest to include progress animation (without changing server)
(function(){ const btn=document.getElementById('run-backtest'); if(!btn) return; const ring=document.getElementById('bt-progress'); const lab=document.getElementById('bt-progress-label');
  const old = (document.getElementById('run-backtest').onclick || null);
  async function run(){ try{ if(ring){ setRing(ring,0); ring.style.display='inline-block'; animateProgress(ring, 0, 92, 15000); } }catch(_){}
    // Call existing handler by dispatching a click to original binding if any
    try{ const ev = new Event('click'); if(old){ old(ev);} }catch(_){ }
  }
  // Ensure our handler triggers before admin.js binding
  btn.addEventListener('click', run, {capture:true});
})();

// Warm Cache UI (client-side animation + CLI guidance)
(function(){ const btn=document.getElementById('warm-run'); if(!btn) return; const ring=document.getElementById('warm-progress'); const msg=document.getElementById('warm-msg');
  btn.addEventListener('click', async ()=>{
    try{
      msg.textContent='Warming (local cache) - run CLI for fastest mode or keep this tab open.';
      setRing(ring,0); ring.style.display='inline-block';
      // Animate to completion; real warm should be done via CLI or server endpoint when added
      let p=0; const id=setInterval(()=>{ p=Math.min(100, p+2+Math.random()*3); setRing(ring,p); if(p>=100){ clearInterval(id); msg.textContent='Warm complete (UI). For full warm, use the CLI above.'; } }, 600);
    }catch(e){ msg.textContent=String(e); }
  });
})();

