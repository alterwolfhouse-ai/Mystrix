// Mystrix Lab UI script (clean)
(function(){
  // Year footer
  try{ const yr=new Date().getFullYear(); document.querySelectorAll('#year,.year').forEach(el=>el.textContent=yr); }catch(_){ }

  // Utils
  const $=s=>document.querySelector(s);
  const $$=s=>Array.from(document.querySelectorAll(s));
  // Optional API override via URL: ?api=http://127.0.0.1:8000
  try{ const q=new URLSearchParams(location.search); const api=q.get('api'); if(api){ window.API_BASE=api; } }catch(_){ }
  // Default API host for custom domain
  try{
    const host = location.hostname || '';
    if (!window.API_BASE && /(^|\.)mystrixwolf\.in$/i.test(host)) {
      window.API_BASE = 'https://api.mystrixwolf.in';
    }
    if (!window.API_BASE && /(^|\.)github\.io$/i.test(host)) {
      window.API_BASE = 'https://api.mystrixwolf.in';
    }
  }catch(_){ }
  // If opened via file://, default API base to local server
  try{ if(location.protocol==='file:' && !window.API_BASE){ window.API_BASE='http://127.0.0.1:8000'; } }catch(_){ }

  // Progress ring helpers
  function setRing(el, pct){ if(!el) return; const deg=Math.max(0,Math.min(100,pct))*3.6; el.style.background=`conic-gradient(var(--accent,#7c4dff) ${deg}deg, rgba(255,255,255,0.08) 0)`; const lab=el.querySelector('span'); if(lab) lab.textContent=`${Math.round(pct)}%`; }
  function animateProgress(el, from, to, ms){ const t0=performance.now(); function step(t){ const k=Math.min(1,(t-t0)/ms); setRing(el, from+(to-from)*k); if(k<1) requestAnimationFrame(step); } requestAnimationFrame(step); }
  window.setRing = window.setRing || setRing;
  window.animateProgress = window.animateProgress || animateProgress;

  // Notification rail
  (function(){ if(document.getElementById('notif-rail')) return; const rail=document.createElement('aside'); rail.id='notif-rail'; rail.style.cssText='position:fixed;right:14px;bottom:14px;max-height:50vh;width:min(92vw,380px);overflow:auto;background:rgba(0,0,0,0.6);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px;z-index:9999;'; document.body.appendChild(rail); window.notify=function(msg,level){ const ts=new Date().toLocaleTimeString(); const div=document.createElement('div'); const color=level==='error'?'#f87171':(level==='warn'?'#fde047':'#d1d5db'); div.style.cssText='font:12px monospace;margin:6px 2px;color:'+color; div.textContent='['+ts+'] '+msg; rail.appendChild(div); rail.scrollTo({top:rail.scrollHeight,behavior:'smooth'}); }; })();

  // Copy buttons
  function bindCopy(){ $$('.codebox .copy').forEach(btn=>{ btn.style.cursor='pointer'; btn.addEventListener('click', async ()=>{ try{ const ring=$('#bt-progress'); if(ring){ setRing(ring,0); ring.style.display='inline-block'; animateProgress(ring, 0, 92, 15000); } }catch(_){} const id=btn.getAttribute('data-target'); const el=document.getElementById(id); const text=el?el.textContent:''; try{ await navigator.clipboard.writeText(text); btn.textContent='Copied!'; }catch(e){ try{ const ta=document.createElement('textarea'); ta.value=text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); btn.textContent='Copied!'; }catch(_){ btn.textContent='Copy'; } finally{ const ta2=document.querySelector('body>textarea'); if(ta2) document.body.removeChild(ta2); } } setTimeout(()=>btn.textContent='Copy',1200); }, {passive:true}); }); }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', bindCopy, {once:true}); else bindCopy();

  // Remove accidental literal "\n" sequences injected in markup
  function sanitizeEscapes(){
    try{
      document.querySelectorAll('#magic-run label, #magic-run .form-grid label').forEach(el=>{
        el.innerHTML = el.innerHTML.replace(/\\n\s*/g, '');
      });
    }catch(_){ }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', sanitizeEscapes, {once:true}); else sanitizeEscapes();

  // Short bot params are common to all products; always visible (toggle affects engine, not UI)

  // Long bot panel visibility follows the toggle
  function wireLongToggle(){
    try{
      const panel = document.getElementById('long-rsi');
      const tgl = document.getElementById('en-long');
      if(!panel || !tgl) return;
      const apply = ()=>{ panel.style.display = tgl.checked ? 'block' : 'none'; };
      tgl.addEventListener('change', apply, {passive:true});
      apply();
    }catch(_){ }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', wireLongToggle, {once:true}); else wireLongToggle();

  // Product switcher + gating
  function initProducts(){ const btnM=$('#prod-mystrix'), btnP=$('#prod-mystrixplus'), btnU=$('#prod-ultimate'); if(!btnM&&!btnP&&!btnU) return; const runP=$('#magic-run'), liveP=$('#magic-live'), chartP=$('#magic-chart'), ultP=$('#ultimate-panel'), empty=$('#product-empty'); const secHTF=(function(){ let el=document.getElementById('bt-htf-en'); while(el && !(el.tagName==='SECTION' && el.classList.contains('glass'))) el=el.parentElement; return el||null; })(); const secGateCS=(function(){ let el=document.getElementById('gate-enable'); while(el && !(el.tagName==='SECTION' && el.classList.contains('glass'))) el=el.parentElement; return el||null; })(); function hideAll(){ if(runP) runP.style.display='none'; if(liveP) liveP.style.display='none'; if(chartP) chartP.style.display='none'; if(ultP) ultP.style.display='none'; if(empty) empty.style.display='block'; } function setProd(p){ localStorage.setItem('product',p); hideAll(); if(p==='mystrix'){ if(empty) empty.style.display='none'; if(secHTF) secHTF.style.display='none'; if(secGateCS) secGateCS.style.display='none'; if(runP) runP.style.display='block'; if(liveP) liveP.style.display='block'; if(chartP) chartP.style.display='block'; notify&&notify('Product: Mystrix','info'); } else if(p==='mystrixplus'){ if(empty) empty.style.display='none'; if(secHTF) secHTF.style.display='block'; if(secGateCS) secGateCS.style.display='none'; if(runP) runP.style.display='block'; if(liveP) liveP.style.display='block'; if(chartP) chartP.style.display='block'; notify&&notify('Product: Mystrix+','info'); } else if(p==='ultimate'){ if(empty) empty.style.display='none'; if(ultP) ultP.style.display='block'; notify&&notify('Product: Mystrix Ultimate','info'); } }
    // Expose for inline fallback
    window.__setProd = setProd;
    // Direct listeners
    btnM&&btnM.addEventListener('click',()=>setProd('mystrix'), {passive:true});
    btnP&&btnP.addEventListener('click',()=>setProd('mystrixplus'), {passive:true});
    btnU&&btnU.addEventListener('click',()=>setProd('ultimate'), {passive:true});
    // Delegated fallback (works even if above didn't bind)
    document.addEventListener('click', (e)=>{
      const t = e.target && (e.target.closest ? e.target.closest('[data-prod]') : null);
      if(t && t.dataset && t.dataset.prod){ setProd(t.dataset.prod); }
    }, {passive:true});
    hideAll();
  }
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', initProducts, {once:true}); } else { initProducts(); }

  // Top switch bar auto-hide on scroll down, show on scroll up
  (function(){ let lastY=window.scrollY||0; function onScroll(){ const sb=document.getElementById('switch-bar'); if(!sb) return; const y=window.scrollY||0; if(y>lastY+5){ sb.classList.add('hide-up'); } else if(y<lastY-5){ sb.classList.remove('hide-up'); } lastY=y; }
    window.addEventListener('scroll', onScroll, {passive:true}); })();

  // API health checker with fallback
  (function(){ const status=document.querySelector('#srv-status'); if(!status) return; function set(ok){ status.innerHTML = 'API: <span class="status-dot '+(ok?'dot-on':'dot-off')+'"></span> ' + (ok?'Online':'Not running'); }
    async function tryBase(base){ try{ const ctrl=new AbortController(); const to=setTimeout(()=>ctrl.abort(),3000); const r=await fetch(base+'/healthz',{signal:ctrl.signal}); clearTimeout(to); return r.ok; }catch(_){ return false; } }
    async function init(){ const candidates = [window.API_BASE, location.origin, 'http://127.0.0.1:8000', 'http://localhost:8000'].filter(Boolean); let ok=false, base=''; for (const c of candidates){ ok = await tryBase(c); if(ok){ base=c; break; } } if(!ok){ base=candidates[candidates.length-1]; } window.API_BASE = base; set(ok); }
    init(); setTimeout(init, 2000); const btn=document.getElementById('recheck'); if(btn) btn.addEventListener('click', init);
  })();
})();

// --- Backtest + Symbols wiring with Equity chart ---
(function(){
  const $=s=>document.querySelector(s);
  if (document.body && document.body.id === 'admin-page') return;
  function ensureContainers(){
    const host = document.getElementById('magic-run'); if(!host) return;
    if(!document.getElementById('bt-msg')){ const m=document.createElement('div'); m.id='bt-msg'; m.className='status'; host.appendChild(m); }
    if(!document.getElementById('bt-out')){ const o=document.createElement('div'); o.id='bt-out'; o.className='glass'; o.style.marginTop='10px'; o.style.padding='12px'; host.appendChild(o); }
    if(!document.getElementById('bt-equity')){ const w=document.createElement('div'); w.style.marginTop='10px'; w.className='glass'; const h=document.createElement('h3'); h.textContent='Equity Curve'; h.style.margin='6px 8px'; const c=document.createElement('canvas'); c.id='bt-equity'; c.width=980; c.height=260; c.style.maxWidth='100%'; w.appendChild(h); w.appendChild(c); host.appendChild(w); }
  }
  async function loadSymbols(){ try{ const base=(window.API_BASE||location.origin); const r=await fetch(base+'/symbols'); if(!r.ok) return; const data=await r.json(); const dl=document.getElementById('symbols-list'); if(!dl) return; dl.innerHTML=''; (data.symbols||[]).forEach(s=>{ const o=document.createElement('option'); o.value=s; dl.appendChild(o); }); }catch(_){} }
  function normSymbol(s){ s=(s||'').toUpperCase().trim(); if(!s) return 'BTC/USDT'; if(!s.includes('/')){ if(s.endsWith('USDT')) return s.slice(0,-4)+'/USDT'; if(s.endsWith('USD')) return s.slice(0,-3)+'/USDT'; } return s; }
  function collectOverrides(){ const get=(id,def)=>{ const el=document.getElementById(id); return el?el.value:def; }; const on=(id)=>{ const el=document.getElementById(id); return !!(el&&el.checked); };
    const pctStop = parseFloat(get('bt-pct-stop',1.8)) / 100.0;
    const rpct = parseFloat(get('bt-risk-pct',10)) / 100.0;
    const cd = on('bt-cooldown-en') ? parseInt(get('bt-cooldown',15)) : 0;
    return {
      timeframe_hist: get('bt-tf','3m'), rsi_length: parseInt(get('bt-rsi-length',14)), rsi_overbought: parseInt(get('bt-rsi-ob',79)), rsi_oversold: parseInt(get('bt-rsi-os',27)),
      lookbackLeft: parseInt(get('bt-lb-left',5)), lookbackRight: parseInt(get('bt-lb-right',5)), rangeLower: parseInt(get('bt-range-low',5)), rangeUpper: parseInt(get('bt-range-up',60)),
      use_pct_stop: pctStop, max_wait_bars: parseInt(get('bt-max-wait',25)), cooldownBars: cd, initial_capital: parseFloat(get('bt-initial',10000)), percent_risk: rpct,
      enableHTFGate: on('bt-htf-en'), htfTF: get('bt-htf-tf','30m'), htf_pct_stop: parseFloat(get('bt-htf-stop',20))/100.0,
      htf_rsi_length: parseInt(get('htf-rsi-length',14)), htf_rsi_overbought: parseInt(get('htf-rsi-ob',79)), htf_rsi_oversold: parseInt(get('htf-rsi-os',27)), htf_lookbackLeft: parseInt(get('htf-lb-left',5)), htf_lookbackRight: parseInt(get('htf-lb-right',5)), htf_rangeLower: parseInt(get('htf-range-low',5)), htf_rangeUpper: parseInt(get('htf-range-up',60)), htf_max_wait_bars: parseInt(get('htf-max-wait',25))
    };
  }
  function renderMetrics(m){
    if(!m) return '<p class="status">No metrics.</p>';
    const synth = String(m['Synthetic Data Used'] ?? '').toLowerCase() === 'true';
    const warn = synth ? '<p class="status">Warning: synthetic data used (network fetch failed).</p>' : '';
    const rows=Object.entries(m).map(([k,v])=>`<tr><td>${k}</td><td>${v}</td></tr>`).join('');
    return warn + `<table class="trades"><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
  function renderTrades(tr){ if(!tr||!tr.length) return '<p class="status">No trades.</p>'; const head=Object.keys(tr[0]); const th=head.map(h=>`<th>${h}</th>`).join(''); const body=tr.map(row=>`<tr>${head.map(h=>`<td>${(row[h]!==undefined&&row[h]!==null)?row[h]:'-'}</td>`).join('')}</tr>`).join(''); return `<table class="trades"><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table>`; }
  function drawEquity(trades, initial){ const c=document.getElementById('bt-equity'); const ctx=(c && c.getContext)? c.getContext('2d') : null; if(!ctx) return; ctx.clearRect(0,0,c.width,c.height); const exits = (trades||[]).filter(t=>String(t.type||'').startsWith('exit')); if(exits.length===0){ ctx.fillStyle='#aaa'; ctx.fillText('No closed trades', 10, 20); return; } let equity=Number(initial||10000); const points=[]; exits.forEach(t=>{ const pnl=Number(t.pnl||0); equity += pnl; const ts=new Date(t.t||Date.now()).getTime(); points.push([ts, equity]); }); points.sort((a,b)=>a[0]-b[0]); const pad=30; const W=c.width, H=c.height; const xs=points.map(p=>p[0]), ys=points.map(p=>p[1]); const xMin=Math.min(...xs), xMax=Math.max(...xs); const yMin=Math.min(...ys), yMax=Math.max(...ys); const xScale=(x)=> pad + (W-2*pad) * ((x - xMin)/Math.max(1,(xMax-xMin))); const yScale=(y)=> H - pad - (H-2*pad) * ((y - yMin)/Math.max(1,(yMax-yMin)));
    ctx.strokeStyle='rgba(124,77,255,0.9)'; ctx.lineWidth=2; ctx.beginPath(); points.forEach((p,i)=>{ const x=xScale(p[0]); const y=yScale(p[1]); if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y); }); ctx.stroke(); ctx.fillStyle='rgba(124,77,255,0.15)'; ctx.lineTo(xScale(xMax), yScale(yMin)); ctx.lineTo(xScale(xMin), yScale(yMin)); ctx.closePath(); ctx.fill(); ctx.fillStyle='#999'; ctx.font='12px monospace'; ctx.fillText(`Start: ${Math.round(points[0][1])}`, 10, 14); ctx.fillText(`End: ${Math.round(points[points.length-1][1])}`, 10, 28);
  }
  function drawPrice(candles, markers){ const c=document.getElementById('bt-price'); const ctx=(c && c.getContext)? c.getContext('2d') : null; if(!ctx||!candles||!candles.length) return; ctx.clearRect(0,0,c.width,c.height); const W=c.width,H=c.height,pad=40; const xs=candles.map((k,i)=>i), hi=Math.max(...candles.map(k=>Number(k.h))), lo=Math.min(...candles.map(k=>Number(k.l))); const xMin=0,xMax=candles.length-1; const xScale=i=> pad + (W-2*pad) * ((i-xMin)/Math.max(1,(xMax-xMin))); const yScale=y=> H - pad - (H-2*pad)*((y-lo)/Math.max(1,(hi-lo))); ctx.strokeStyle='rgba(150,150,150,0.3)'; ctx.strokeRect(pad, pad, W-2*pad, H-2*pad); candles.forEach((k,i)=>{ const x=xScale(i); const o=Number(k.o),h=Number(k.h),l=Number(k.l),cl=Number(k.c); ctx.strokeStyle= cl>=o? '#59f39b':'#f66'; ctx.beginPath(); ctx.moveTo(x, yScale(l)); ctx.lineTo(x, yScale(h)); ctx.stroke(); ctx.lineWidth=3; ctx.beginPath(); ctx.moveTo(x-2, yScale(o)); ctx.lineTo(x+2, yScale(cl)); ctx.stroke(); ctx.lineWidth=1; }); (markers||[]).forEach(m=>{ const i=candles.findIndex(k=>k.t===m.t); if(i<0) return; const x=xScale(i); const y=yScale(Number(m.price)); ctx.fillStyle = (m.side==='short')? '#f59e0b' : '#22c55e'; if(String(m.type).startsWith('exit')) ctx.fillStyle = (m.side==='short')? '#fb923c' : '#ef4444'; ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI*2); ctx.fill(); }); }
  async function runBacktest(){ ensureContainers(); const msg=document.getElementById('bt-msg'); const out=document.getElementById('bt-out'); const eqInit = collectOverrides().initial_capital||10000; const chartSec=document.getElementById('bt-chart-section'); if(chartSec) chartSec.style.display='none'; msg.textContent='Running...'; out.innerHTML=''; const base=(window.API_BASE||location.origin); var elSy=document.getElementById('bt-symbols'); const symsStr=(elSy && elSy.value)||'BTC/USDT'; const first=normSymbol(symsStr.split(',')[0]); var elS=document.getElementById('bt-start'); var elE=document.getElementById('bt-end'); let start=(elS && elS.value)||''; let end=(elE && elE.value)||''; if(!end){ const d=new Date(); end=d.toISOString().slice(0,10); } if(!start){ const d=new Date(end+'T00:00:00Z'); d.setMonth(d.getMonth()-3); start=d.toISOString().slice(0,10); }
    const ov = collectOverrides(); const body={ symbols:[first], start, end, overrides: ov, engine:'long' };
    let r; try { r = await fetch(base+'/backtest',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)}); } catch(e){ msg.textContent= String(e&&e.message||e); return; }
    if(!r.ok){ msg.textContent = await r.text(); return; }
    const data=await r.json(); msg.textContent='Done.'; out.innerHTML= renderMetrics(data.metrics) + renderTrades(data.trades); if(chartSec) chartSec.style.display='block'; drawEquity(data.trades, ov.initial_capital); drawPrice(data.candles, data.markers); }
  async function runHedge(){ ensureContainers(); const msg=document.getElementById('bt-msg'); const out=document.getElementById('bt-out'); const chartSec=document.getElementById('bt-chart-section'); if(chartSec) chartSec.style.display='none'; msg.textContent='Running hedge...'; out.innerHTML=''; const base=(window.API_BASE||location.origin); var elSy=document.getElementById('bt-symbols'); const symsStr=(elSy && elSy.value)||'BTC/USDT'; const first=normSymbol(symsStr.split(',')[0]); var elS=document.getElementById('bt-start'); var elE=document.getElementById('bt-end'); let start=(elS && elS.value)||''; let end=(elE && elE.value)||''; if(!end){ const d=new Date(); end=d.toISOString().slice(0,10); } if(!start){ const d=new Date(end+'T00:00:00Z'); d.setMonth(d.getMonth()-6); start=d.toISOString().slice(0,10); } const ov = collectOverrides(); const body={ symbols:[first], start, end, overrides: ov, engine:'both' }; let r; try { r=await fetch(base+'/backtest',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)}); } catch(e){ msg.textContent= String(e&&e.message||e); return; } if(!r.ok){ msg.textContent = await r.text(); return; } const data=await r.json(); msg.textContent='Done.'; out.innerHTML= renderMetrics(data.metrics) + renderTrades(data.trades); if(chartSec) chartSec.style.display='block'; drawPrice(data.candles, data.markers); // Equity: combined + long + short
    const comb = data.equity_series||[]; const c=document.getElementById('bt-equity'); const ctx=(c && c.getContext)? c.getContext('2d') : null; if(ctx){ ctx.clearRect(0,0,c.width,c.height); const series=[{s:comb,color:'rgba(124,77,255,0.9)',fill:'rgba(124,77,255,0.15)',label:'Combined'},{s:(data.equity_series_long||[]),color:'#22c55e',fill:'rgba(34,197,94,0.15)',label:'Long'},{s:(data.equity_series_short||[]),color:'#f59e0b',fill:'rgba(245,158,11,0.15)',label:'Short'}]; const pad=30,W=c.width,H=c.height; function drawLine(pts,color,fill){ if(!pts.length) return; const xs=pts.map(p=>new Date(p.t).getTime()), ys=pts.map(p=>p.equity); const xMin=Math.min(...xs), xMax=Math.max(...xs), yMin=Math.min(...ys), yMax=Math.max(...ys); const xScale=x=> pad+(W-2*pad)*((x-xMin)/Math.max(1,(xMax-xMin))); const yScale=y=> H-pad-(H-2*pad)*((y-yMin)/Math.max(1,(yMax-yMin))); ctx.strokeStyle=color; ctx.lineWidth=2; ctx.beginPath(); pts.forEach((p,i)=>{ const x=xScale(new Date(p.t).getTime()); const y=yScale(p.equity); if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y); }); ctx.stroke(); ctx.fillStyle=fill; ctx.lineTo(xScale(xMax), yScale(yMin)); ctx.lineTo(xScale(xMin), yScale(yMin)); ctx.closePath(); ctx.fill(); }
    series.forEach(s=> drawLine(s.s, s.color, s.fill)); }
  function bind(){ const run=document.getElementById('run-backtest'); if(run){ run.addEventListener('click', runBacktest, {passive:true}); } const hedge=document.getElementById('run-hedge'); if(hedge){ hedge.addEventListener('click', runHedge, {passive:true}); }
    const resBtn=document.getElementById('btn-resolve'); if(resBtn){ resBtn.addEventListener('click', ()=>{ const out=document.getElementById('resolve-out'); var el=document.getElementById('bt-symbols'); const sy=((el&&el.value)||'').split(',')[0].trim(); const norm=normSymbol(sy); if(out) out.textContent = sy? (sy+" -> "+norm):'Enter a symbol'; }, {passive:true}); }
  }
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', bind, {once:true}); document.addEventListener('DOMContentLoaded', loadSymbols, {once:true}); } else { bind(); loadSymbols(); }
})();
