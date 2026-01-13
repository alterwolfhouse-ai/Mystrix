// Basic utilities
const API = (typeof location !== 'undefined' && location.origin.startsWith('http')) ? location.origin : 'http://127.0.0.1:8000';
const $ = (s)=>document.querySelector(s);
const $$ = (s)=>Array.from(document.querySelectorAll(s));

// Auth modal controls
const modal = $('#auth-modal');
$('#btn-login')?.addEventListener('click', ()=> modal.style.display='flex');
$('#btn-auth-close')?.addEventListener('click', ()=> modal.style.display='none');
$('#btn-do-signup')?.addEventListener('click', async ()=>{
  const email=$('#auth-email').value.trim(); const pass=$('#auth-pass').value; const name=$('#auth-name').value.trim();
  try{ const r=await fetch(API+'/auth/signup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password:pass,name})}); if(!r.ok) throw new Error(await r.text()); $('#auth-msg').textContent='Signup ok. Now login.'; }catch(e){ $('#auth-msg').textContent=String(e); }
});
$('#btn-do-login')?.addEventListener('click', async ()=>{
  const email=$('#auth-email').value.trim(); const pass=$('#auth-pass').value;
  try{ const r=await fetch(API+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password:pass}), credentials:'include'}); if(!r.ok) throw new Error(await r.text()); $('#auth-msg').textContent='Logged in'; modal.style.display='none'; init(); }catch(e){ $('#auth-msg').textContent=String(e); }
});
$('#btn-logout')?.addEventListener('click', async ()=>{ try{ await fetch(API+'/auth/logout',{method:'POST', credentials:'include'});}catch(_){} init(); });

async function me(){ try{ const r=await fetch(API+'/me',{credentials:'include'}); if(!r.ok) return null; return (await r.json()).user; }catch(_){ return null; } }

// Populate symbols and favorites
async function loadSymbols(){
  try{
    const r=await fetch(API+'/symbols');
    const j=await r.json();
    const dl=document.getElementById('u-symbols');
    if(dl){ dl.innerHTML=(j.symbols||[]).map(s=>`<option value="${s}"></option>`).join(''); }
    const inp=document.getElementById('u-symbol');
    if(inp && !inp.value) inp.value='BTC/USDT';
  }catch(_){ /* no-op */ }
}
async function loadFavorites(){ try{ const r=await fetch(API+'/favorites',{credentials:'include'}); if(!r.ok) return; const favs=(await r.json()).favorites||[]; const box=$('#u-favs'); box.innerHTML=favs.map(s=>`<button class="cta" data-sym="${s}">${s}</button>`).join(''); box.querySelectorAll('button').forEach(b=> b.addEventListener('click', ()=>{ $('#u-symbol').value=b.dataset.sym; fetchSignal(); })); }catch(_){} }

// Suggestions
$('#u-suggest')?.addEventListener('click', async ()=>{ const t=$('#u-missing').value.trim(); if(!t) return; try{ const r=await fetch(API+'/suggest_coin',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({text:t})}); if(r.ok){ $('#u-missing').value=''; } }catch(_){ } });

// Favorites toggle
$('#u-fav')?.addEventListener('click', async ()=>{ const sym=$('#u-symbol').value; try{ await fetch(API+'/favorites',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({symbol:sym})}); loadFavorites(); }catch(_){ } });

// Build Pine params from saved Magic settings
function pineQueryFromSaved(){ try{ const raw=localStorage.getItem('pine_settings_v1'); if(!raw) return ''; const d=JSON.parse(raw); const q=new URLSearchParams(); const setIf=(k,v)=>{ if(v!==undefined&&v!==null&&String(v)!=='') q.set(k,String(v)); }; setIf('rsi_length',d.rsi_length); setIf('rsi_overbought',d.rsi_ob); setIf('rsi_oversold',d.rsi_os); setIf('lookbackLeft',d.lb_left); setIf('lookbackRight',d.lb_right); setIf('rangeLower',d.range_low); setIf('rangeUpper',d.range_up); if(d.pct_stop!==undefined) setIf('use_pct_stop', Number(d.pct_stop)/100); setIf('max_wait_bars', d.max_wait); setIf('cooldownBars', d.cd_en?d.cooldown:0); if(d.initial) setIf('initial_capital', d.initial); if(d.risk_pct!==undefined) setIf('percent_risk', Number(d.risk_pct)/100); if(d.htf_en!==undefined) setIf('enableHTFGate', d.htf_en?'true':'false'); if(d.htf_tf) setIf('htfTF', d.htf_tf); if(d.htf_stop!==undefined) setIf('htf_pct_stop', Number(d.htf_stop)/100); setIf('htf_rsi_length', d.htf_rsi_length); setIf('htf_rsi_overbought', d.htf_rsi_ob); setIf('htf_rsi_oversold', d.htf_rsi_os); setIf('htf_lookbackLeft', d.htf_lb_left); setIf('htf_lookbackRight', d.htf_lb_right); setIf('htf_rangeLower', d.htf_range_low); setIf('htf_rangeUpper', d.htf_range_up); setIf('htf_max_wait_bars', d.htf_max_wait); return q.toString(); }catch(_){ return ''; } }

// Chart
const canvas=$('#u-canvas'); const ctx=canvas?.getContext('2d'); let state={candles:[],markers:[],viewStart:0,viewEnd:0,cross:null};
function drawChart(candles, markers){ if(!ctx||!candles||candles.length===0) return; const W=canvas.width,H=canvas.height; ctx.clearRect(0,0,W,H); const padL=50,padR=10,padT=10,padB=20; const nTotal=candles.length; const start=Math.max(0,Math.min(state.viewStart,nTotal-2)); const end=Math.max(start+1,Math.min(state.viewEnd||(nTotal-1),nTotal-1)); const n=end-start+1; const view=candles.slice(start,end+1); const hi=Math.max(...view.map(c=>Number(c.h))); const lo=Math.min(...view.map(c=>Number(c.l))); const range=Math.max(1e-9,(hi-lo)); const px=i=> padL+(W-padL-padR)*((i-start)/(n-1)); const py=p=> padT+(H-padT-padB)*(1-(Number(p)-lo)/range); const barW=Math.max(1,Math.floor((W-padL-padR)/n*0.7)); ctx.strokeStyle='rgba(255,255,255,0.08)'; ctx.lineWidth=1; for(let i=0;i<5;i++){ const yy=padT+(H-padT-padB)*i/4; ctx.beginPath(); ctx.moveTo(padL,yy); ctx.lineTo(W-padR,yy); ctx.stroke(); } ctx.fillStyle='rgba(255,255,255,0.5)'; ctx.font='10px monospace'; ctx.fillText(hi.toFixed(2),4,py(hi)); ctx.fillText(lo.toFixed(2),4,py(lo)); for(let i=start;i<=end;i++){ const c=candles[i]; const x=Math.round(px(i)); const yH=Math.round(py(c.h)); const yL=Math.round(py(c.l)); const yO=Math.round(py(c.o)); const yC=Math.round(py(c.c)); const up=Number(c.c)>=Number(c.o); ctx.strokeStyle='rgba(220,210,255,0.6)'; ctx.beginPath(); ctx.moveTo(x,yH); ctx.lineTo(x,yL); ctx.stroke(); const h=Math.max(1,Math.abs(yC-yO)); const top=Math.min(yC,yO); ctx.fillStyle=up?'rgba(168,147,255,0.85)':'rgba(239,68,68,0.7)'; ctx.fillRect(x-Math.floor(barW/2), top, barW, h); } markers=Array.isArray(markers)?markers:[]; const timeToIndex=new Map(candles.map((c,i)=>[c.t,i])); markers.forEach(m=>{ const i=timeToIndex.get(m.t); if(i===undefined) return; if(i<start||i>end) return; const x=Math.round(px(i)); const y=Math.round(py(m.price ?? candles[i].c)); if(m.type==='enter'){ ctx.fillStyle='#22c55e'; ctx.beginPath(); ctx.moveTo(x,y-7); ctx.lineTo(x-6,y+7); ctx.lineTo(x+6,y+7); ctx.closePath(); ctx.fill(); ctx.fillStyle='rgba(255,255,255,0.85)'; ctx.font='10px monospace'; ctx.fillText('Long', x+8, y+3); } else if(m.type==='exit_normal'){ ctx.fillStyle='#f43f5e'; ctx.beginPath(); ctx.moveTo(x,y+7); ctx.lineTo(x-6,y-7); ctx.lineTo(x+6,y-7); ctx.closePath(); ctx.fill(); ctx.fillStyle='rgba(255,255,255,0.85)'; ctx.font='10px monospace'; ctx.fillText('Exit', x+8, y-2); } else if(m.type==='exit_sl'){ ctx.strokeStyle='#f43f5e'; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(x-6,y-6); ctx.lineTo(x+6,y+6); ctx.moveTo(x+6,y-6); ctx.lineTo(x-6,y+6); ctx.stroke(); ctx.fillStyle='rgba(255,255,255,0.85)'; ctx.font='10px monospace'; ctx.fillText('SL', x+8, y-2); } }); }

async function fetchSignal(){
  const sym=$('#u-symbol').value; const tf='3m'; const bars=400; const status=$('#u-status');
  status.textContent='Loading...';
  try{
    const extras=pineQueryFromSaved();
    const url=`${API}/pine/signal?symbol=${encodeURIComponent(sym)}&timeframe=${encodeURIComponent(tf)}&bars=${bars}${extras?('&'+extras):''}`;
    const res=await fetch(url,{credentials:'include'});
    if(!res.ok) throw new Error(await res.text());
    const data=await res.json();
    state.candles=Array.isArray(data.chart?.candles)?data.chart.candles:[];
    state.markers=Array.isArray(data.chart?.markers)?data.chart.markers:[];
    state.viewEnd=state.candles.length?state.candles.length-1:0;
    const initial=Math.min(state.candles.length-1, Math.max(50,Math.floor(state.candles.length*0.5)));
    state.viewStart=Math.max(0, state.viewEnd-initial);
    drawChart(state.candles,state.markers);
    status.textContent=`Last action: ${data.action||'HOLD'}`;
    renderSigLog(data.trades||[]);
  }catch(e){ status.textContent=String(e); }
}
function renderSigLog(trades){ const box=$('#u-log'); const rows=(trades||[]).slice(-5).map(t=>{ const price=t.price!==undefined?Number(t.price).toFixed(2):''; return `<tr><td>${t.t||''}</td><td>${t.type||''}</td><td>${price}</td></tr>`; }).join(''); const head='<tr><th>time</th><th>type</th><th>price</th></tr>'; box.innerHTML = `<table class="trades"><thead>${head}</thead><tbody>${rows}</tbody></table>`; }

$('#u-fetch')?.addEventListener('click', fetchSignal);
let autoTimer=null; $('#u-auto')?.addEventListener('click', ()=>{ const b=$('#u-auto'); if(autoTimer){ clearInterval(autoTimer); autoTimer=null; b.textContent='Start Auto'; } else { fetchSignal(); autoTimer=setInterval(fetchSignal, 30000); b.textContent='Stop Auto'; } });

async function init(){
  const user = await me();
  if(user){ $('#btn-login').style.display='none'; $('#btn-logout').style.display='inline-block'; if(user.is_admin) $('#nav-admin').style.display='inline-block'; }
  else { $('#btn-login').style.display='inline-block'; $('#btn-logout').style.display='none'; $('#nav-admin').style.display='none'; }
  await loadSymbols(); await loadFavorites(); fetchSignal();
  // Prefill backtest dates: last 90 days
  const end=new Date(); const start=new Date(); start.setDate(end.getDate()-90);
  const iso=(d)=>d.toISOString().slice(0,10);
  const sEl=$('#bt-start'); const eEl=$('#bt-end'); if(sEl&&!sEl.value) sEl.value=iso(start); if(eEl&&!eEl.value) eEl.value=iso(end);
  $('#bt-run')?.addEventListener('click', runBacktest);
  // server status
  checkStatus(); setInterval(checkStatus, 4000);
}
init();

// Server status indicator
async function checkStatus(){ const el=$('#srv-status'); const dot=el?.querySelector('.status-dot'); try{ const r=await fetch(API+'/healthz',{method:'GET'}); const ok=r.ok; if(dot){ dot.classList.toggle('dot-on',ok); dot.classList.toggle('dot-off',!ok); el.innerHTML=`Server: <span class="status-dot ${ok?'dot-on':'dot-off'}"></span> ${ok?'Online':'Offline'}`; } }catch(_){ if(dot){ dot.classList.add('dot-off'); dot.classList.remove('dot-on'); el.innerHTML='Server: <span class="status-dot dot-off"></span> Offline'; } } }

// User backtest: range only; admin defaults provide engine params
async function getDefaults(){ try{ const r=await fetch(API+'/defaults'); if(!r.ok) return {timeframe_hist:'3m',overrides:{}}; return await r.json(); }catch(_){ return {timeframe_hist:'3m',overrides:{}}; } }
async function runBacktest(){ const sym=$('#u-symbol').value; const s=$('#bt-start').value; const e=$('#bt-end').value; const out=$('#bt-out'); const msg=$('#bt-msg'); msg.textContent='Running backtest...'; try{ const defs=await getDefaults(); const body={ symbols:[sym], start:s, end:e, overrides:Object.assign({timeframe_hist:defs.timeframe_hist||'3m'}, defs.overrides||{}) }; const r=await fetch(API+'/backtest',{method:'POST',headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); if(!r.ok) throw new Error(await r.text()); const data=await r.json(); msg.textContent='Done.'; out.innerHTML=renderMetrics(data.metrics)+renderTrades(data.trades); }catch(e){ msg.textContent=String(e); } }
function renderMetrics(m){ const keys=[['Total Return (%)','Return'],['Num Trades','Trades'],['Win Rate (%)','Win Rate'],['Avg P&L','Avg P&L'],['Sharpe','Sharpe'],['Max Drawdown (%)','Max DD'],['Ending Equity','Equity']]; const cards=keys.map(([k,l])=>{ const v=(m&&m[k]!==undefined)?m[k]:'-'; return `<div class="metric"><div class="label">${l}</div><div class="value">${v}</div></div>`;}).join(''); return `<div class="metrics">${cards}</div>`; }
function renderTrades(items){ if(!items||!items.length) return '<p class="status">No trades.</p>'; const head='<tr><th>time</th><th>type</th><th>price</th></tr>'; const rows=items.slice(-200).map(t=>{ const price=t.price!==undefined?Number(t.price).toFixed(2):''; return `<tr><td>${t.t||''}</td><td>${t.type||''}</td><td>${price}</td></tr>`;}).join(''); return `<table class="trades"><thead>${head}</thead><tbody>${rows}</tbody></table>`; }

// Alarm: per selected symbol; admin configs via defaults
let alarmTimer=null, lastAction='HOLD';
$('#u-alarm')?.addEventListener('click', ()=>{ const b=$('#u-alarm'); if(alarmTimer){ clearInterval(alarmTimer); alarmTimer=null; b.textContent='Alarm Off'; } else { alarmTimer=setInterval(checkAlarm, 12000); b.textContent='Alarm On'; } });
async function checkAlarm(){ try{ const sym=$('#u-symbol').value; const url=`${API}/signals?symbols=${encodeURIComponent(sym)}&timeframe=3m&bars=400`; const r=await fetch(url); if(!r.ok) return; const j=await r.json(); const sig=j.signals&&j.signals[0]&&j.signals[0].signal?j.signals[0].signal.action:'HOLD'; if(sig!=='HOLD' && sig!==lastAction){ beep(); } lastAction=sig; }catch(_){} }
function beep(){ try{ const ac=new (window.AudioContext||window.webkitAudioContext)(); const o=ac.createOscillator(); const g=ac.createGain(); o.connect(g); g.connect(ac.destination); o.frequency.value=880; g.gain.value=0.1; o.start(); setTimeout(()=>{ o.stop(); ac.close(); }, 400); }catch(_){} }

