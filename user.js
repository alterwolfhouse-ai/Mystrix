// MystriX User Console (core + premium locks)
const API = (typeof location !== 'undefined' && location.origin.startsWith('http')) ? location.origin : 'http://127.0.0.1:8000';
const $ = (s)=>document.querySelector(s);
const $$ = (s)=>Array.from(document.querySelectorAll(s));

async function me(){
  try{
    const r = await fetch(API + '/me', {credentials:'include'});
    if(!r.ok) return null;
    return (await r.json()).user;
  }catch(_){
    return null;
  }
}

function setPlan(user){
  const planEl = $('#u-plan');
  const noteEl = $('#u-plan-note');
  if(!user){
    planEl.textContent = 'Guest';
    noteEl.textContent = 'Sign in to unlock premium modules.';
    return;
  }
  const plan = user.plan_name || (user.has_mystrix_plus ? 'MystriX+' : 'Free Core');
  planEl.textContent = plan;
  noteEl.textContent = user.plan_note || (user.has_mystrix_plus ? 'Premium modules unlocked.' : 'Core access only.');
}

function setAuthButtons(user){
  const login = $('#u-login');
  const logout = $('#u-logout');
  if(user){
    login.style.display = 'none';
    logout.style.display = 'inline-block';
  } else {
    login.style.display = 'inline-block';
    logout.style.display = 'none';
  }
}

function toggleLocks(user){
  const flags = {
    mystrix_plus: !!user?.has_mystrix_plus,
    backtest: !!user?.has_backtest,
    autotrader: !!user?.has_autotrader,
  };
  $$('[data-lock]').forEach(card => {
    const key = card.getAttribute('data-lock');
    const allowed = !!flags[key];
    const overlay = card.querySelector('.lock-overlay');
    if(overlay){
      overlay.classList.toggle('active', !allowed);
    }
  });
}

function bindPremiumActions(user){
  const canPlus = !!user?.has_mystrix_plus;
  const canBacktest = !!user?.has_backtest;
  const canAuto = !!user?.has_autotrader;
  const pricingModal = $('#pricing-modal');
  const showPricing = () => pricingModal?.classList.add('active');
  const hidePricing = () => pricingModal?.classList.remove('active');

  $('#btn-go-live')?.addEventListener('click', () => {
    if(!canPlus) return showPricing();
    location.href = 'live_mystrix+.html';
  });
  $('#btn-go-cpa')?.addEventListener('click', () => {
    if(!canBacktest) return showPricing();
    location.href = 'concurrent_lab.html';
  });
  $('#btn-go-auto')?.addEventListener('click', () => {
    if(!canAuto) return showPricing();
    location.href = 'live_mystrix+.html';
  });
  $$('.btn-upgrade').forEach(btn => btn.addEventListener('click', showPricing));
  $('#pricing-close')?.addEventListener('click', hidePricing);
  $('#pricing-pay')?.addEventListener('click', () => {
    alert('Thanks. Our team will contact you to activate MystriX+.');
    hidePricing();
  });
}

// Server status indicator
async function checkStatus(){
  const el = $('#srv-status');
  const dot = el?.querySelector('.status-dot');
  try{
    const r = await fetch(API + '/healthz', {method:'GET'});
    const ok = r.ok;
    if(dot){
      dot.classList.toggle('dot-on', ok);
      dot.classList.toggle('dot-off', !ok);
    }
    if(el){
      el.innerHTML = `Server: <span class="status-dot ${ok?'dot-on':'dot-off'}"></span> ${ok?'Online':'Offline'}`;
    }
  }catch(_){
    if(dot){
      dot.classList.add('dot-off');
      dot.classList.remove('dot-on');
    }
    if(el){
      el.innerHTML = 'Server: <span class="status-dot dot-off"></span> Offline';
    }
  }
}

// Populate symbols and favorites
async function loadSymbols(){
  try{
    const r = await fetch(API + '/symbols');
    const j = await r.json();
    const dl = document.getElementById('u-symbols');
    if(dl){
      dl.innerHTML = (j.symbols || []).map(s => `<option value="${s}"></option>`).join('');
    }
    const inp = document.getElementById('u-symbol');
    if(inp && !inp.value) inp.value = 'BTC/USDT';
  }catch(_){ /* no-op */ }
}

async function loadFavorites(){
  try{
    const r = await fetch(API + '/favorites', {credentials:'include'});
    if(!r.ok) return;
    const favs = (await r.json()).favorites || [];
    const box = $('#u-favs');
    box.innerHTML = favs.map(s=>`<button class="cta" data-sym="${s}">${s}</button>`).join('');
    box.querySelectorAll('button').forEach(b => b.addEventListener('click', ()=>{
      $('#u-symbol').value = b.dataset.sym;
      fetchSignal();
    }));
  }catch(_){}
}

// Suggestions
$('#u-suggest')?.addEventListener('click', async ()=>{
  const t = $('#u-missing').value.trim();
  if(!t) return;
  try{
    const r = await fetch(API + '/suggest_coin', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      credentials:'include',
      body: JSON.stringify({text:t}),
    });
    if(r.ok){ $('#u-missing').value=''; }
  }catch(_){ }
});

// Favorites toggle
$('#u-fav')?.addEventListener('click', async ()=>{
  const sym = $('#u-symbol').value;
  try{
    await fetch(API + '/favorites', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      credentials:'include',
      body: JSON.stringify({symbol:sym}),
    });
    loadFavorites();
  }catch(_){}
});

// Chart
const canvas = $('#u-canvas');
const ctx = canvas?.getContext('2d');
let state = {candles:[],markers:[],viewStart:0,viewEnd:0};

function drawChart(candles, markers){
  if(!ctx || !candles || candles.length === 0) return;
  const W=canvas.width, H=canvas.height;
  ctx.clearRect(0,0,W,H);
  const padL=50,padR=10,padT=10,padB=20;
  const nTotal=candles.length;
  const start=Math.max(0,Math.min(state.viewStart,nTotal-2));
  const end=Math.max(start+1,Math.min(state.viewEnd||(nTotal-1),nTotal-1));
  const n=end-start+1;
  const view=candles.slice(start,end+1);
  const hi=Math.max(...view.map(c=>Number(c.h)));
  const lo=Math.min(...view.map(c=>Number(c.l)));
  const range=Math.max(1e-9,(hi-lo));
  const px=i=> padL+(W-padL-padR)*((i-start)/(n-1));
  const py=p=> padT+(H-padT-padB)*(1-(Number(p)-lo)/range);
  const barW=Math.max(1,Math.floor((W-padL-padR)/n*0.7));

  ctx.strokeStyle='rgba(255,255,255,0.08)';
  ctx.lineWidth=1;
  for(let i=0;i<5;i++){
    const yy=padT+(H-padT-padB)*i/4;
    ctx.beginPath(); ctx.moveTo(padL,yy); ctx.lineTo(W-padR,yy); ctx.stroke();
  }
  ctx.fillStyle='rgba(255,255,255,0.5)';
  ctx.font='10px monospace';
  ctx.fillText(hi.toFixed(2),4,py(hi));
  ctx.fillText(lo.toFixed(2),4,py(lo));

  for(let i=start;i<=end;i++){
    const c=candles[i];
    const x=Math.round(px(i));
    const yH=Math.round(py(c.h));
    const yL=Math.round(py(c.l));
    const yO=Math.round(py(c.o));
    const yC=Math.round(py(c.c));
    const up=Number(c.c)>=Number(c.o);
    ctx.strokeStyle='rgba(220,210,255,0.6)';
    ctx.beginPath(); ctx.moveTo(x,yH); ctx.lineTo(x,yL); ctx.stroke();
    const h=Math.max(1,Math.abs(yC-yO));
    const top=Math.min(yC,yO);
    ctx.fillStyle=up?'rgba(168,147,255,0.85)':'rgba(239,68,68,0.7)';
    ctx.fillRect(x-Math.floor(barW/2), top, barW, h);
  }
  markers = Array.isArray(markers)?markers:[];
  const timeToIndex=new Map(candles.map((c,i)=>[c.t,i]));
  markers.forEach(m=>{
    const i=timeToIndex.get(m.t);
    if(i===undefined) return;
    if(i<start||i>end) return;
    const x=Math.round(px(i));
    const y=Math.round(py(m.price ?? candles[i].c));
    if(m.type==='enter'){
      ctx.fillStyle='#22c55e';
      ctx.beginPath(); ctx.moveTo(x,y-7); ctx.lineTo(x-6,y+7); ctx.lineTo(x+6,y+7); ctx.closePath(); ctx.fill();
      ctx.fillStyle='rgba(255,255,255,0.85)';
      ctx.font='10px monospace';
      ctx.fillText('Long', x+8, y+3);
    } else if(m.type==='exit_normal'){
      ctx.fillStyle='#f43f5e';
      ctx.beginPath(); ctx.moveTo(x,y+7); ctx.lineTo(x-6,y-7); ctx.lineTo(x+6,y-7); ctx.closePath(); ctx.fill();
      ctx.fillStyle='rgba(255,255,255,0.85)';
      ctx.font='10px monospace';
      ctx.fillText('Exit', x+8, y-2);
    } else if(m.type==='exit_sl'){
      ctx.strokeStyle='#f43f5e';
      ctx.lineWidth=2;
      ctx.beginPath();
      ctx.moveTo(x-6,y-6); ctx.lineTo(x+6,y+6);
      ctx.moveTo(x+6,y-6); ctx.lineTo(x-6,y+6);
      ctx.stroke();
      ctx.fillStyle='rgba(255,255,255,0.85)';
      ctx.font='10px monospace';
      ctx.fillText('SL', x+8, y-2);
    }
  });
}

function renderSigLog(trades){
  const box = $('#u-log');
  const rows = (trades || []).slice(-5).map(t=>{
    const price = t.price !== undefined ? Number(t.price).toFixed(2) : '';
    return `<tr><td>${t.t||''}</td><td>${t.type||''}</td><td>${price}</td></tr>`;
  }).join('');
  const head = '<tr><th>time</th><th>type</th><th>price</th></tr>';
  box.innerHTML = `<table class="trades"><thead>${head}</thead><tbody>${rows}</tbody></table>`;
}

async function fetchSignal(){
  const sym = $('#u-symbol').value;
  const tf = '3m';
  const bars = 400;
  const status = $('#u-status');
  status.textContent = 'Loading...';
  try{
    const url = `${API}/pine/signal?symbol=${encodeURIComponent(sym)}&timeframe=${encodeURIComponent(tf)}&bars=${bars}`;
    const res = await fetch(url, {credentials:'include'});
    if(!res.ok) throw new Error(await res.text());
    const data = await res.json();
    state.candles = Array.isArray(data.chart?.candles) ? data.chart.candles : [];
    state.markers = Array.isArray(data.chart?.markers) ? data.chart.markers : [];
    state.viewEnd = state.candles.length ? state.candles.length-1 : 0;
    const initial = Math.min(state.candles.length-1, Math.max(50, Math.floor(state.candles.length*0.5)));
    state.viewStart = Math.max(0, state.viewEnd-initial);
    drawChart(state.candles, state.markers);
    status.textContent = `Last action: ${data.action || 'HOLD'}`;
    renderSigLog(data.trades || []);
  }catch(e){
    status.textContent = String(e);
  }
}

$('#u-fetch')?.addEventListener('click', fetchSignal);
let autoTimer = null;
$('#u-auto')?.addEventListener('click', ()=>{
  const b = $('#u-auto');
  if(autoTimer){
    clearInterval(autoTimer);
    autoTimer = null;
    b.textContent = 'Start Auto';
  } else {
    fetchSignal();
    autoTimer = setInterval(fetchSignal, 30000);
    b.textContent = 'Stop Auto';
  }
});

// Alarm
let alarmTimer = null;
let lastAction = 'HOLD';
$('#u-alarm')?.addEventListener('click', ()=>{
  const b = $('#u-alarm');
  if(alarmTimer){
    clearInterval(alarmTimer);
    alarmTimer = null;
    b.textContent = 'Alarm Off';
  } else {
    alarmTimer = setInterval(checkAlarm, 12000);
    b.textContent = 'Alarm On';
  }
});

async function checkAlarm(){
  try{
    const sym=$('#u-symbol').value;
    const url=`${API}/signals?symbols=${encodeURIComponent(sym)}&timeframe=3m&bars=400`;
    const r=await fetch(url);
    if(!r.ok) return;
    const j=await r.json();
    const sig=j.signals&&j.signals[0]&&j.signals[0].signal?j.signals[0].signal.action:'HOLD';
    if(sig!=='HOLD' && sig!==lastAction){ beep(); }
    lastAction=sig;
  }catch(_){}
}

function beep(){
  try{
    const ac=new (window.AudioContext||window.webkitAudioContext)();
    const o=ac.createOscillator();
    const g=ac.createGain();
    o.connect(g);
    g.connect(ac.destination);
    o.frequency.value=880;
    g.gain.value=0.1;
    o.start();
    setTimeout(()=>{ o.stop(); ac.close(); }, 400);
  }catch(_){}
}

$('#u-logout')?.addEventListener('click', async ()=>{
  try{ await fetch(API + '/auth/logout', {method:'POST', credentials:'include'}); }catch(_){}
  init();
});

async function init(){
  const user = await me();
  setPlan(user);
  setAuthButtons(user);
  toggleLocks(user);
  bindPremiumActions(user);
  await loadSymbols();
  await loadFavorites();
  fetchSignal();
  checkStatus();
  setInterval(checkStatus, 4000);
}

init();
