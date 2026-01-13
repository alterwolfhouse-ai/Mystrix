(function(){
  function $(s){ return document.querySelector(s); }
  function $all(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); }

  try{ var y=new Date().getFullYear(); $all('.year,#year').forEach(function(el){ el.textContent=y; }); }catch(_){ }

  function apiBase(){ try{ return window.API_BASE || location.origin || 'http://127.0.0.1:8000'; }catch(_){ return 'http://127.0.0.1:8000'; } }

  var goLiveBtn = document.getElementById('go-live');
  if(goLiveBtn){
    goLiveBtn.addEventListener('click', function(){ window.location.href = 'live_mystrix+.html'; }, false);
  }

  function health(){ var base=apiBase(); return fetch(base+'/healthz').then(function(r){ var ok=r&&r.ok; var dot=$('#srv-status .status-dot'); var lab=$('#srv-status'); if(dot) dot.className='status-dot '+(ok?'dot-on':'dot-off'); if(lab) lab.innerHTML='API: <span class="status-dot '+(ok?'dot-on':'dot-off')+'"></span> ' + (ok?'Online':'Not running'); return ok; }).catch(function(){ return false; }); }

  var __product = 'mystrix';
  function gateProduct(p, opts){
    try{
      var key = (p || 'mystrix').toLowerCase();
      var isClick = (opts && opts.fromClick);
      if(key === 'mystrixplus'){
        localStorage.setItem('product', 'mystrixplus');
        // Redirect to concurrent lab ONLY on user click, not on pageload
        if(isClick){
          window.location.href = '/static/concurrent_lab.html';
        }
        __product = key;
        return;
      }
      __product = key;
      var htf=$('#htf-gate');
      var ult=$('#ultimate-panel');
      if(htf) htf.style.display = (key === 'mystrix') ? 'block' : 'none';
      if(ult) ult.style.display = (key === 'ultimate') ? 'block' : 'none';
      localStorage.setItem('product', key);
    }catch(_){}
  }
  function bindProduct(){
    $all('#product-switch [data-prod]').forEach(function(b){
      b.addEventListener('click', function(){
        gateProduct(b.getAttribute('data-prod'), {fromClick:true});
      }, false);
    });
    // Default to Mystrix on load; ignore stored mystrixplus to avoid auto-redirect
    var last = localStorage.getItem('product');
    if(!last || last === 'mystrixplus'){ last = 'mystrix'; }
    gateProduct(last);
  }

  function bindToggles(){ var L=$('#long-rsi'), S=$('#short-rsi'); var tl=$('#en-long'), ts=$('#en-short'); function apply(){ if(L&&tl) L.style.display=tl.checked?'block':'none'; if(S&&ts) S.style.display=ts.checked?'block':'none'; } if(tl) tl.addEventListener('change', apply, false); if(ts) ts.addEventListener('change', apply, false); apply(); }

  function get(id, def){ var el=document.getElementById(id); return el?el.value:def; }
  function on(id){ var el=document.getElementById(id); return !!(el&&el.checked); }

  function loadSymbols(){ fetch(apiBase()+'/symbols').then(function(r){ if(!r.ok) return null; return r.json(); }).then(function(data){ if(!data) return; var dl=$('#symbols-list'); if(!dl) return; dl.innerHTML=''; (data.symbols||[]).forEach(function(s){ var o=document.createElement('option'); o.value=s; dl.appendChild(o); }); }).catch(function(){}); }

  function runBacktest(){ var base=apiBase(); var out=$('#bt-out'); if(out) out.innerHTML=''; var syms=(get('bt-symbols','BTC/USDT').split(',').map(function(s){return s.trim();}).filter(Boolean)); var symbol=syms[0]||'BTC/USDT'; var tf=get('bt-tf','3m'); var start=get('bt-start',''); var end=get('bt-end',''); var enLong=on('en-long'); var enShort=on('en-short'); var engine=(enLong&&enShort)?'both':(enShort?'short':'long'); function ovLong(){ var pctStop=parseFloat(get('bt-pct-stop',1.8))/100; var rpct=parseFloat(get('bt-risk-pct',10))/100; var cd=on('bt-cooldown-en')?parseInt(get('bt-cooldown',15)):0; return { timeframe_hist: tf, rsi_length: parseInt(get('bt-rsi-length',14)), rsi_overbought: parseInt(get('bt-rsi-ob',79)), rsi_oversold: parseInt(get('bt-rsi-os',27)), lookbackLeft: parseInt(get('bt-lb-left',5)), lookbackRight: parseInt(get('bt-lb-right',5)), rangeLower: parseInt(get('bt-range-low',5)), rangeUpper: parseInt(get('bt-range-up',60)), use_pct_stop: pctStop, max_wait_bars: parseInt(get('bt-max-wait',25)), cooldownBars: cd, initial_capital: parseFloat(get('bt-initial',10000)), percent_risk: rpct }; } function ovShort(){ var pctStop=parseFloat(get('sb-pct-stop',1.8))/100; var rpct=parseFloat(get('sb-risk-pct',10))/100; var cd=on('sb-cooldown-en')?parseInt(get('sb-cooldown',15)):0; return { timeframe_hist: tf, rsi_length: parseInt(get('sb-rsi-length',14)), rsi_overbought: parseInt(get('sb-rsi-ob',79)), rsi_oversold: parseInt(get('sb-rsi-os',27)), lookbackLeft: parseInt(get('sb-lb-left',5)), lookbackRight: parseInt(get('sb-lb-right',5)), rangeLower: parseInt(get('sb-range-low',5)), rangeUpper: parseInt(get('sb-range-up',60)), use_pct_stop: pctStop, max_wait_bars: parseInt(get('sb-max-wait',25)), cooldownBars: cd, initial_capital: parseFloat(get('sb-initial',10000)), percent_risk: rpct }; }
    var statusEl=$('#bt-status'); if(statusEl) statusEl.textContent='Running...'; var btn=document.getElementById('run-backtest'); if(btn) btn.disabled=true;
    var payload={symbols:[symbol], start:start, end:end, overrides:(engine==='short'?ovShort():ovLong()), engine:engine};
    // If both, call hedge mode using long UI settings and map stop -> init_stop_pct (hedge expects percent)
    if(engine==='both'){
      var longOv = ovLong();
      var pctStopUi = parseFloat(get('bt-pct-stop',1.8));
      if(!isFinite(pctStopUi)) pctStopUi = 1.8;
      longOv.init_stop_pct = pctStopUi; // percent value expected by hedge engine
      payload.overrides = longOv;
    }
    fetch(base+'/backtest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(function(r){ return r.json().then(function(j){ return {ok:r.ok,data:j}; }); })
      .then(function(res){ if(!res.ok){ if(out) out.innerHTML='<p class="status">'+(res.data&&res.data.detail||'Backtest error')+'</p>'; if(statusEl) statusEl.textContent='Error'; if(btn) btn.disabled=false; return; } window.__lastBT={engine:engine,data:res.data, long: (engine!=='short')?ovLong():null, short: (engine!=='long')?ovShort():null}; renderBacktest(res.data, engine, out); if(statusEl) statusEl.textContent='Done'; if(btn) btn.disabled=false; var exbtn=document.getElementById('bt-export'); if(exbtn) exbtn.disabled=false; })
      .catch(function(e){ if(out) out.innerHTML='<p class="status">'+(e&&e.message||e)+'</p>'; if(statusEl) statusEl.textContent='Error'; if(btn) btn.disabled=false; });
  }

  function renderBacktest(data, engine, out){
    function table(obj){ var rows='', k; for(k in (obj||{})){ if(Object.prototype.hasOwnProperty.call(obj,k)){ rows+='<tr><td>'+k+'</td><td>'+obj[k]+'</td></tr>'; } } return '<table class="trades"><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>'+rows+'</tbody></table>'; }
    function drawAxes(ctx,W,H,p,lo,hi){ ctx.strokeStyle='rgba(150,150,150,0.35)'; ctx.lineWidth=1; ctx.strokeRect(p,p,W-2*p,H-2*p); ctx.fillStyle='rgba(200,200,200,0.7)'; ctx.font='12px monospace'; ctx.fillText(String(lo.toFixed?lo.toFixed(2):lo), 6, H-p+12); ctx.fillText(String(hi.toFixed?hi.toFixed(2):hi), 6, p+12); }
  function _ensureCanvasScale(c){ try{ var dpr = (window.devicePixelRatio||1); var cssW = c.clientWidth||c.width; var cssH = c.clientHeight||c.height; if(cssW<=0){ cssW = (c.parentElement? c.parentElement.clientWidth: c.width)||c.width; } if(cssH<=0){ cssH = c.height; } var targetW = Math.max(100, Math.floor(cssW * dpr)); var targetH = Math.max(100, Math.floor(cssH * dpr)); if(c.width !== targetW || c.height !== targetH){ c.width = targetW; c.height = targetH; } return {W:c.width,H:c.height}; }catch(_){ return {W:c.width,H:c.height}; } }
  function drawPrice(id, candles, markers, color){ var c=document.getElementById(id); if(!c) return; var ctx=c.getContext('2d'); var WH=_ensureCanvasScale(c); var W=WH.W,H=WH.H,p=36; var vals=candles||[]; if(!vals.length){ ctx.clearRect(0,0,W,H); return; } var hi=Math.max.apply(null, vals.map(function(k){return Number(k.h||k.high||0);})); var lo=Math.min.apply(null, vals.map(function(k){return Number(k.l||k.low||0);})); var useLog = lo>0 && (hi/Math.max(1e-9, lo) > 3.0); var loS = useLog? Math.log(lo): lo; var hiS = useLog? Math.log(hi): hi; var xMin=0,xMax=vals.length-1; function xs(i){ return p+(W-2*p)*((i-xMin)/Math.max(1,(xMax-xMin))); } function ys(v){ var vv = useLog? Math.log(v): v; return H-p-(H-2*p)*((vv-loS)/Math.max(1e-9,hiS-loS)); } ctx.clearRect(0,0,W,H); drawAxes(ctx,W,H,p,lo,hi); vals.forEach(function(k,i){ var X=xs(i); var o=Number(k.o||k.open),h=Number(k.h||k.high),l=Number(k.l||k.low),cl=Number(k.c||k.close); ctx.strokeStyle= cl>=o? '#59f39b':'#f66'; ctx.beginPath(); ctx.moveTo(X, ys(l)); ctx.lineTo(X, ys(h)); ctx.stroke(); ctx.lineWidth=3; ctx.beginPath(); ctx.moveTo(X-2, ys(o)); ctx.lineTo(X+2, ys(cl)); ctx.stroke(); ctx.lineWidth=1; }); (markers||[]).forEach(function(m){ var i=vals.findIndex(function(k){ return k.t===m.t; }); if(i<0) return; var X=xs(i), Y=ys(Number(m.price)); ctx.fillStyle=(m.side==='short')?'#f59e0b':'#22c55e'; if(String(m.type||'').startsWith('exit')) ctx.fillStyle=(m.side==='short')?'#fb923c':'#ef4444'; ctx.beginPath(); ctx.arc(X,Y,3,0,Math.PI*2); ctx.fill(); }); }
function drawLine(id, series, color){ var c=document.getElementById(id); if(!c) return; var ctx=c.getContext('2d'); var W=c.width,H=c.height,p=36; if(!series||!series.length){ ctx.clearRect(0,0,W,H); ctx.fillStyle='#aaa'; ctx.fillText('No data', 10, 16); return; } var ys=series.map(function(pt){return Number(pt[1]||pt.equity||0);}); var xs=series.map(function(pt){ var t=pt[0]||pt.t; return (new Date(t)).getTime? (new Date(t)).getTime(): t; }); var lo=Math.min.apply(null, ys), hi=Math.max.apply(null, ys), xmin=Math.min.apply(null, xs), xmax=Math.max.apply(null, xs); function X(x){ return p+(W-2*p)*((x-xmin)/Math.max(1,(xmax-xmin))); } function Y(y){ return H-p-(H-2*p)*((y-lo)/Math.max(1,(hi-lo))); } ctx.clearRect(0,0,W,H); drawAxes(ctx,W,H,p,lo,hi); ctx.strokeStyle=color||'#7c4dff'; ctx.lineWidth=2; ctx.shadowColor='rgba(124,77,255,0.6)'; ctx.shadowBlur=6; ctx.beginPath(); series.forEach(function(pt,i){ var x=X(xs[i]); var y=Y(ys[i]); if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y); }); ctx.stroke(); ctx.shadowBlur=0; }

  // Windowed price drawing with auto log-y for signal/price charts
  function drawPriceZoom(id, candles, markers, start, win, autoLog){
    var c=document.getElementById(id); if(!c) return; var ctx=c.getContext('2d'); var WH=_ensureCanvasScale(c); var W=WH.W,H=WH.H,p=36;
    var vals=candles||[]; if(!vals.length){ ctx.clearRect(0,0,W,H); return; }
    start = Math.max(0, parseInt(start||0)); win = Math.max(10, parseInt(win||Math.min(300, vals.length)));
    var end = Math.min(vals.length, start + win);
    var sub = vals.slice(start, end);
    var hi = Math.max.apply(null, sub.map(function(k){ return Number(k.h||k.high||0); }));
    var lo = Math.min.apply(null, sub.map(function(k){ return Number(k.l||k.low||0); }));
    var useLog = !!autoLog && lo>0 && (hi/Math.max(1e-9,lo) > 3.0);
    var loS = useLog? Math.log(lo): lo;
    var hiS = useLog? Math.log(hi): hi;
    function xs(i){ return p + (W-2*p) * ((i - start) / Math.max(1, (end - start - 1))); }
    function ys(v){ var vv = useLog? Math.log(v): v; return H - p - (H-2*p) * ((vv - loS) / Math.max(1e-9, (hiS - loS))); }
    ctx.clearRect(0,0,W,H);
    drawAxes(ctx,W,H,p,lo,hi);
    sub.forEach(function(k,idx){ var i = start + idx; var X=xs(i); var o=Number(k.o||k.open),h=Number(k.h||k.high),l=Number(k.l||k.low),cl=Number(k.c||k.close); ctx.strokeStyle= cl>=o? '#59f39b':'#f66'; ctx.beginPath(); ctx.moveTo(X, ys(l)); ctx.lineTo(X, ys(h)); ctx.stroke(); ctx.lineWidth=3; ctx.beginPath(); ctx.moveTo(X-2, ys(o)); ctx.lineTo(X+2, ys(cl)); ctx.stroke(); ctx.lineWidth=1; });
    (markers||[]).forEach(function(m){ var i = vals.findIndex(function(k){ return k.t===m.t; }); if(i<0 || i<start || i>=end) return; var X=xs(i), Y=ys(Number(m.price)); ctx.fillStyle=(m.side==='short')?'#f59e0b':'#22c55e'; if(String(m.type||'').startsWith('exit')) ctx.fillStyle=(m.side==='short')?'#fb923c':'#ef4444'; ctx.beginPath(); ctx.arc(X,Y,3,0,Math.PI*2); ctx.fill(); });
    try{ var ind=document.getElementById('sc-log-ind'); if(ind) ind.textContent = useLog? 'log':'lin'; }catch(_){ }
  }
    var content='';
    // Compute drawdowns from equity series when available
    function ddMetrics(eq, initial){ if(!eq||!eq.length){ return {}; } var peak=eq[0].equity||eq[0][1]; var maxDD=0; var minEquity=eq[0].equity||eq[0][1]; for(var i=0;i<eq.length;i++){ var v=eq[i].equity||eq[i][1]; if(v>peak) peak=v; var dd=(peak>0)? (1 - v/peak)*100 : 0; if(dd>maxDD) maxDD=dd; if(v<minEquity) minEquity=v; } var mddInit=(initial>0)? (1 - (minEquity/initial))*100 : 0; return { 'Max Drawdown (%)': Number(maxDD.toFixed(2)), 'Max DD from Initial (%)': Number(mddInit.toFixed(2)) }; }
    if(engine==='both'){
      var eq = (data.equity_series||[]).map(function(e){ return [e.t||e[0], e.equity||e[1]]; });
      var eqL= (data.equity_series_long||[]).map(function(e){ return [e.t||e[0], e.equity||e[1]]; });
      var eqS= (data.equity_series_short||[]).map(function(e){ return [e.t||e[0], e.equity||e[1]]; });
      var initial = (window.__lastBT && window.__lastBT.long && window.__lastBT.long.initial_capital) || 10000;
      var extra = ddMetrics(eq, initial);
      // Append DD metrics to table
      var m = data.metrics||{}; for(var k in extra){ m[k]=extra[k]; }
      content += table(m);
      content += '<div class="glass" style="padding:8px; margin-top:8px;"><h4 style="margin:4px 0;">Equity - Long</h4><div class="chart-wrap"><canvas id="eqL" width="980" height="200" style="max-width:100%"></canvas></div></div>';
      content += '<div class="glass" style="padding:8px; margin-top:8px;"><h4 style="margin:4px 0;">Equity - Short</h4><div class="chart-wrap"><canvas id="eqS" width="980" height="200" style="max-width:100%"></canvas></div></div>';
      content += '<div class="glass" style="padding:8px; margin-top:8px;"><h4 style="margin:4px 0;">Equity - Combined</h4><div class="chart-wrap"><canvas id="eqC" width="980" height="220" style="max-width:100%"></canvas></div></div>';
      var trades=data.trades||[]; var body=''; trades.forEach(function(t){ var pr=t.price, q=t.qty; try{ pr=Math.abs(Number(pr)); }catch(_){ } try{ q=Number(q); }catch(_){ } body+='<tr><td>'+(t.t||'')+'</td><td>'+(t.type||'')+'</td><td>'+(pr||'')+'</td><td>'+(q||'')+'</td><td>'+(t.pnl||'')+'</td><td>'+(t.side||'')+'</td></tr>'; });
      content += (trades.length? '<div class="results"><table class="trades"><thead><tr><th>t</th><th>type</th><th>price</th><th>qty</th><th>pnl</th><th>side</th></tr></thead><tbody>'+body+'</tbody></table></div>' : '<p class="status">No trades.</p>');
      out.innerHTML = content;
      setTimeout(function(){ drawLine('eqL', eqL, '#7c4dff'); drawLine('eqS', eqS, '#7c4dff'); drawLine('eqC', eq, '#7c4dff'); }, 0);
    } else {
      var chartId='bt-price-'+Math.random().toString(16).slice(2); var chart='<div class="chart-wrap" style="margin-top:8px;"><canvas id="'+chartId+'" width="980" height="320" style="max-width:100%"></canvas></div>'; var trades2=data.trades||[]; var body2=''; trades2.forEach(function(t){ var pr=t.price, q=t.qty; try{ pr=Math.abs(Number(pr)); }catch(_){ } try{ q=Number(q); }catch(_){ } body2+='<tr><td>'+(t.t||'')+'</td><td>'+(t.type||'')+'</td><td>'+(pr||'')+'</td><td>'+(q||'')+'</td><td>'+(t.pnl||'')+'</td><td>'+(t.side||engine)+'</td></tr>'; }); var tbl2 = trades2.length? '<div class="results"><table class="trades"><thead><tr><th>t</th><th>type</th><th>price</th><th>qty</th><th>pnl</th><th>side</th></tr></thead><tbody>'+body2+'</tbody></table></div>' : '<p class="status">No trades.</p>'; out.innerHTML = table(data.metrics||{}) + chart + tbl2; setTimeout(function(){ drawPrice(chartId, data.candles||[], data.markers||[], '#7c4dff'); }, 0);
    }
  }

  function scanSignals(){ var base=apiBase(); var symbols=get('ls-symbols','BTC/USDT,ETH/USDT'); var tf=get('ls-tf','3m'); var bars=500; var url=base+'/signals?symbols='+encodeURIComponent(symbols)+'&timeframe='+encodeURIComponent(tf)+'&bars='+bars; var out=$('#signals'); fetch(url).then(function(r){ return r.json().then(function(j){ return {ok:r.ok,data:j}; }); }).then(function(res){ if(!res.ok){ out.innerHTML='<p class="status">Error</p>'; return; } var rows=(res.data.signals||[]).map(function(s){ return '<tr><td>'+s.symbol+'</td><td>'+Number(s.price).toFixed(4)+'</td><td>'+Number(s.rsi).toFixed(2)+'</td><td>'+((s.signal||{}).action||'HOLD')+'</td></tr>'; }).join(''); out.innerHTML='<table class="signals"><thead><tr><th>Symbol</th><th>Price</th><th>RSI</th><th>Action</th></tr></thead><tbody>'+rows+'</tbody></table>'; var sel=$('#ls-symbol-list'); if(sel){ sel.innerHTML=(res.data.signals||[]).map(function(s){ return '<option value="'+s.symbol+'">'+s.symbol+'</option>'; }).join(''); } $('#ls-logs').innerHTML=''; }).catch(function(){ out.innerHTML='<p class="status">Scan error</p>'; }); }

  function fetchSignal(){ var base=apiBase(); var symbol=get('sc-symbol','BTC/USDT'); var timeframe=get('sc-tf','3m'); var bars=parseInt(get('sc-bars',400)); var url=base+'/pine/signal?symbol='+encodeURIComponent(symbol)+'&timeframe='+encodeURIComponent(timeframe)+'&bars='+bars; fetch(url).then(function(r){ return r.json(); }).then(function(j){ try{ var candles=(j.chart&&j.chart.candles)||j.candles||[]; var markers=(j.chart&&j.chart.markers)||j.markers||[]; window.__sigChart={ c: candles, m: markers }; var win=Math.min(candles.length, Math.max(60, Math.floor(bars*0.6))); var start=Math.max(0, candles.length - win); var sc=document.getElementById('sc-scroll'); if(sc){ sc.max = String(Math.max(0, candles.length - win)); sc.value = String(start); sc.oninput = function(){ try{ var s=parseInt(sc.value||'0'); var r=document.getElementById('sc-range'); if(r){ var a=Math.max(0,s), b=Math.min(candles.length, s+win); r.textContent=(a+'..'+b+' / '+candles.length); } drawPriceZoom('sig-canvas', candles, markers, s, win, true); }catch(_){ } }; } var r=document.getElementById('sc-range'); if(r){ r.textContent=(start+'..'+(start+win)+' / '+candles.length); } drawPriceZoom('sig-canvas', candles, markers, start, win, true); }catch(_){ } }).catch(function(){}); }

  function bindActions(){ var r=document.getElementById('recheck'); if(r) r.addEventListener('click', health, false); var b=document.getElementById('run-backtest'); if(b) b.addEventListener('click', runBacktest, false); var s=document.getElementById('ls-scan'); if(s) s.addEventListener('click', scanSignals, false); var f=document.getElementById('sc-fetch'); if(f) f.addEventListener('click', fetchSignal, false); var ex=document.getElementById('bt-export'); if(ex) ex.addEventListener('click', exportCSV, false); var sc=document.getElementById('sc-scroll'); if(sc && !sc.oninput){ sc.oninput=function(){ try{ var data=window.__sigChart||{}; var candles=data.c||[]; var markers=data.m||[]; var bars=parseInt(get('sc-bars',400)); var win=Math.min(candles.length, Math.max(60, Math.floor(bars*0.6))); var s=parseInt(sc.value||'0'); var rr=document.getElementById('sc-range'); if(rr){ var a=Math.max(0,s), b=Math.min(candles.length, s+win); rr.textContent=(a+'..'+b+' / '+candles.length); } drawPriceZoom('sig-canvas', candles, markers, s, win, true); }catch(_){ } }; } }
  // Presets: bull/bear/chop for both long & short
  var __presetSlot='bull';
  function currentSymbol(){ var v=get('bt-symbols','BTC/USDT'); return (v.split(',')[0]||'BTC/USDT').trim(); }
  function canon(sym){ return (sym||'').toUpperCase().replace(/\//g,''); }
  function slotKey(){ return 'presetSlot:'+(__product||'mystrix')+':'+canon(currentSymbol()); }
  function savePreset(){ try{ var params={ long: { timeframe_hist:get('bt-tf','3m'), rsi_length:parseInt(get('bt-rsi-length',14)), rsi_overbought:parseInt(get('bt-rsi-ob',79)), rsi_oversold:parseInt(get('bt-rsi-os',27)), lookbackLeft:parseInt(get('bt-lb-left',5)), lookbackRight:parseInt(get('bt-lb-right',5)), rangeLower:parseInt(get('bt-range-low',5)), rangeUpper:parseInt(get('bt-range-up',60)), use_pct_stop: parseFloat(get('bt-pct-stop',1.8))/100, max_wait_bars: parseInt(get('bt-max-wait',25)), cooldownBars: (on('bt-cooldown-en')?parseInt(get('bt-cooldown',15)):0), initial_capital: parseFloat(get('bt-initial',10000)), percent_risk: parseFloat(get('bt-risk-pct',10))/100 }, short: { timeframe_hist:get('bt-tf','3m'), rsi_length:parseInt(get('sb-rsi-length',14)), rsi_overbought:parseInt(get('sb-rsi-ob',79)), rsi_oversold:parseInt(get('sb-rsi-os',27)), lookbackLeft:parseInt(get('sb-lb-left',5)), lookbackRight:parseInt(get('sb-lb-right',5)), rangeLower:parseInt(get('sb-range-low',5)), rangeUpper:parseInt(get('sb-range-up',60)), use_pct_stop: parseFloat(get('sb-pct-stop',1.8))/100, max_wait_bars: parseInt(get('sb-max-wait',25)), cooldownBars: (on('sb-cooldown-en')?parseInt(get('sb-cooldown',15)):0), initial_capital: parseFloat(get('sb-initial',10000)), percent_risk: parseFloat(get('sb-risk-pct',10))/100 } }; var body={ product:'mystrix', symbol: currentSymbol(), slot: __presetSlot, params: params }; fetch(apiBase()+'/api/presets/save',{ method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) }).then(function(r){ return r.json().then(function(j){ return {ok:r.ok,data:j}; }); }).then(function(res){ var ps=document.getElementById('preset-status'); if(res.ok){ if(ps) ps.textContent='Saved'; if(window.notify) notify('Preset saved: '+__presetSlot,'info'); } else { if(ps) ps.textContent='Error'; if(window.notify) notify('Preset save failed','error'); } setTimeout(function(){ if(ps) ps.textContent=''; }, 1500); }).catch(function(){ var ps=document.getElementById('preset-status'); if(ps) ps.textContent='Error'; }); }catch(_){ }
  }
  function setActivePreset(slot){ var ids=['preset-bull','preset-bear','preset-chop']; for(var i=0;i<ids.length;i++){ var el=document.getElementById(ids[i]); if(el){ el.style.outline='none'; el.style.boxShadow=''; } } var sel = document.getElementById('preset-'+slot); if(sel){ sel.style.outline='2px solid var(--accent-strong)'; sel.style.boxShadow='0 0 12px rgba(124,77,255,0.6)'; }
    try{ localStorage.setItem(slotKey(), slot); }catch(_){ }
  }
  function applyParams(p){ try{ var L=p&&p.long||{}; var S=p&&p.short||{}; function set(id,val){ var el=document.getElementById(id); if(el&&val!==undefined&&val!==null){ el.value=String(val); } } function setChk(id, on){ var el=document.getElementById(id); if(el){ el.checked = !!on; } }
      set('bt-rsi-length',L.rsi_length); set('bt-rsi-ob',L.rsi_overbought); set('bt-rsi-os',L.rsi_oversold); set('bt-lb-left',L.lookbackLeft); set('bt-lb-right',L.lookbackRight); set('bt-range-low',L.rangeLower); set('bt-range-up',L.rangeUpper); if(L.use_pct_stop!=null){ set('bt-pct-stop', Number(L.use_pct_stop)*100); } else if(L.init_stop_pct!=null){ set('bt-pct-stop', Number(L.init_stop_pct)); } if(L.max_wait_bars!=null){ set('bt-max-wait', L.max_wait_bars); } if(L.cooldownBars!=null){ set('bt-cooldown', L.cooldownBars); setChk('bt-cooldown-en', (L.cooldownBars>0)); } if(L.initial_capital!=null){ set('bt-initial', L.initial_capital); } if(L.percent_risk!=null){ set('bt-risk-pct', Number(L.percent_risk)*100); }
      set('sb-rsi-length',S.rsi_length); set('sb-rsi-ob',S.rsi_overbought); set('sb-rsi-os',S.rsi_oversold); set('sb-lb-left',S.lookbackLeft); set('sb-lb-right',S.lookbackRight); set('sb-range-low',S.rangeLower); set('sb-range-up',S.rangeUpper); if(S.use_pct_stop!=null){ set('sb-pct-stop', Number(S.use_pct_stop)*100); } else if(S.init_stop_pct!=null){ set('sb-pct-stop', Number(S.init_stop_pct)); } if(S.max_wait_bars!=null){ set('sb-max-wait', S.max_wait_bars); } if(S.cooldownBars!=null){ set('sb-cooldown', S.cooldownBars); setChk('sb-cooldown-en', (S.cooldownBars>0)); } if(S.initial_capital!=null){ set('sb-initial', S.initial_capital); } if(S.percent_risk!=null){ set('sb-risk-pct', Number(S.percent_risk)*100); }
  }catch(_){ }
  }
  function loadPreset(slot){ var ps=document.getElementById('preset-status'); var sym=currentSymbol(); var url=apiBase()+'/api/presets/get?product=mystrix&symbol='+encodeURIComponent(sym); fetch(url).then(function(r){ return r.json(); }).then(function(j){ var p=(j&&j.presets&&j.presets[slot]&&j.presets[slot].params)||null; if(p){ applyParams(p); if(ps) ps.textContent='Loaded '+slot; if(window.notify) notify('Preset loaded: '+slot,'info'); } else { if(ps) ps.textContent='No '+slot+' preset'; if(window.notify) notify('No '+slot+' preset found','warn'); } setTimeout(function(){ if(ps) ps.textContent=''; },1500); }).catch(function(){ if(ps) ps.textContent='Error'; }); }
  function bindPresets(){ var b=document.getElementById('preset-bull'); var r=document.getElementById('preset-bear'); var c=document.getElementById('preset-chop'); function set(slot){ __presetSlot=slot; setActivePreset(slot); if(window.notify) notify('Preset slot: '+slot+' ('+currentSymbol()+')','info'); loadPreset(slot); } if(b) b.addEventListener('click', function(){ set('bull'); }, false); if(r) r.addEventListener('click', function(){ set('bear'); }, false); if(c) c.addEventListener('click', function(){ set('chop'); }, false); var s=document.getElementById('preset-save'); if(s) s.addEventListener('click', function(){ if(!__presetSlot){ if(window.notify) notify('Select a preset slot first','warn'); return; } savePreset(); }, false); var l=document.getElementById('preset-load'); if(l) l.addEventListener('click', function(){ if(!__presetSlot){ if(window.notify) notify('Select a preset slot first','warn'); return; } loadPreset(__presetSlot); }, false);
    // Restore last slot per asset
    try{ var last=localStorage.getItem(slotKey())||'bull'; __presetSlot=last; setActivePreset(last); loadPreset(last); }catch(_){ }
    // React to symbol edits and reload per-asset slot
    var symInput=document.getElementById('bt-symbols'); if(symInput){ var onSym=function(){ try{ var last2=localStorage.getItem(slotKey())||'bull'; __presetSlot=last2; setActivePreset(last2); loadPreset(last2); }catch(_){ } }; symInput.addEventListener('change', onSym, false); symInput.addEventListener('blur', onSym, false); }
  }

  // Export CSV for the last backtest
  function exportCSV(){ try{ if(!window.__lastBT || !window.__lastBT.data) return; var d=window.__lastBT.data; var eng=window.__lastBT.engine||''; var rows=['side,t,type,price,qty,pnl']; var tr=d.trades||[]; for(var i=0;i<tr.length;i++){ var t=tr[i]; rows.push([(t.side||eng||''),(t.t||''),(t.type||''),(t.price||''),(t.qty||''),(t.pnl||'')].join(',')); } var csv=rows.join('\n'); var blob=new Blob([csv], {type:'text/csv'}); var a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='backtest_report.csv'; document.body.appendChild(a); a.click(); setTimeout(function(){ URL.revokeObjectURL(a.href); document.body.removeChild(a); }, 0); }catch(_){ }
  }

  function initDates(){ var s=$('#bt-start'), e=$('#bt-end'); var today=new Date(); var past=new Date(); past.setMonth(today.getMonth()-1); if(s&&!s.value) s.value=past.toISOString().slice(0,10); if(e&&!e.value) e.value=today.toISOString().slice(0,10); }

  function init(){ bindProduct(); bindToggles(); initDates(); bindActions(); bindPresets(); loadSymbols(); health(); if(!document.getElementById('notif-rail')){ var rail=document.createElement('aside'); rail.id='notif-rail'; rail.style.cssText='position:fixed;right:14px;bottom:14px;max-height:50vh;width:min(92vw,380px);overflow:auto;background:rgba(0,0,0,0.6);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px;z-index:9999;'; document.body.appendChild(rail); window.notify=function(msg,level){ var ts=new Date().toLocaleTimeString(); var div=document.createElement('div'); var color=level==='error'?'#f87171':(level==='warn'?'#fde047':'#d1d5db'); div.style.cssText='font:12px monospace;margin:6px 2px;color:'+color; div.textContent='['+ts+'] '+msg; rail.appendChild(div); rail.scrollTop=rail.scrollHeight; }; }
    // Redraw charts on resize at device pixel ratio
    try{ window.addEventListener('resize', function(){ try{ var data=window.__sigChart||{}; if(data.c){ var sc=document.getElementById('sc-scroll'); var s = sc? parseInt(sc.value||'0'): 0; var bars=parseInt(get('sc-bars',400)); var win=Math.min((data.c||[]).length, Math.max(60, Math.floor(bars*0.6))); drawPriceZoom('sig-canvas', data.c||[], data.m||[], s, win, true); } }catch(_){ } }, false); }catch(_){ }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init, false); else init();
})();
