// Universal Asset Picker (searchable dropdown, no paging)
(function(){
  const CSS = `
  .ap-overlay{position:absolute;z-index:99999;max-height:280px;overflow:auto;min-width:220px;
    background:rgba(10,10,16,0.96);border:1px solid rgba(255,255,255,0.08);border-radius:8px;
    box-shadow:0 8px 20px rgba(0,0,0,0.5)}
  .ap-item{padding:6px 10px;font:12px monospace;color:#ddd;cursor:pointer}
  .ap-item:hover,.ap-item.active{background:rgba(124,77,255,0.2)}
  `;
  function inject(){ if(document.getElementById('ap-style')) return; const st=document.createElement('style'); st.id='ap-style'; st.textContent=CSS; document.head.appendChild(st); }
  inject();

  let CACHE = null; let FETCHING = false; let BASE = null;
  async function getSymbols(){ if(CACHE) return CACHE; if(FETCHING) { await new Promise(r=>setTimeout(r,150)); return getSymbols(); }
    FETCHING=true; try{ BASE=(window.API_BASE||location.origin||''); let r=await fetch(BASE+'/symbols'); if(!r.ok) throw new Error(); let j=await r.json(); CACHE=(j.symbols||[]); }
    catch(_){ CACHE=["BTC/USDT","ETH/USDT","SOL/USDT"]; }
    finally{ FETCHING=false; }
    return CACHE; }

  function makeOverlay(){ const d=document.createElement('div'); d.className='ap-overlay'; d.style.display='none'; (document.body||document.documentElement).appendChild(d); return d; }
  let overlay = null; function ensureOverlay(){ if(!overlay){ if(!document.body){ document.addEventListener('DOMContentLoaded', ()=>{ if(!overlay) overlay = makeOverlay(); }, {once:true}); } else { overlay = makeOverlay(); } } return overlay; }
  let activeInput=null; let items=[]; let idx=-1;

  function positionOverlay(input){ const ov=ensureOverlay(); const r=input.getBoundingClientRect(); ov.style.left=window.scrollX+r.left+'px'; ov.style.top=window.scrollY+r.bottom+'px'; ov.style.minWidth=r.width+'px'; }
  function setItems(list){ const ov=ensureOverlay(); ov.innerHTML=''; items=list; idx = (list.length?0:-1); list.forEach((s,i)=>{ const div=document.createElement('div'); div.className='ap-item'+(i===idx?' active':''); div.textContent=s; div.addEventListener('mousedown', (ev)=>{ ev.preventDefault(); choose(s); }); ov.appendChild(div); }); }
  function filterSymbols(q){ q=(q||'').toUpperCase(); const all=items&&items.length?items:(CACHE||[]); return all.filter(s=> s.includes(q)); }
  function currentToken(val){ const i=val.lastIndexOf(','); return { prefix: i>=0? val.slice(0,i+1):'', token: i>=0? val.slice(i+1).trim(): val.trim() }; }
  function choose(sym){ if(!activeInput) return; if(activeInput.dataset.multi==='true'){ const {prefix}=currentToken(activeInput.value); activeInput.value = (prefix + sym).replace(/\s+/g,''); }
    else { activeInput.value = sym; } hide(); activeInput.dispatchEvent(new Event('change')); }
  function show(){ ensureOverlay().style.display='block'; }
  function hide(){ const ov=ensureOverlay(); ov.style.display='none'; idx=-1; }

  async function onInput(ev){ activeInput = ev.currentTarget; positionOverlay(activeInput); const raw = (await getSymbols()); items = raw; const val = activeInput.value; const token = (activeInput.dataset.multi==='true')? currentToken(val).token : val; const filtered = filterSymbols(token); setItems(filtered); show(); }
  function onKey(ev){ const ov=ensureOverlay(); if(ov.style.display==='none') return; if(ev.key==='ArrowDown'){ idx=Math.min(idx+1, ov.children.length-1); updateActive(); ev.preventDefault(); }
    else if(ev.key==='ArrowUp'){ idx=Math.max(idx-1, 0); updateActive(); ev.preventDefault(); }
    else if(ev.key==='Enter'){ const el = ov.children[idx]; if(el){ choose(el.textContent); ev.preventDefault(); } }
    else if(ev.key==='Escape'){ hide(); }
  }
  function updateActive(){ const ov=ensureOverlay(); Array.from(ov.children).forEach((c,i)=>{ c.classList.toggle('active', i===idx); }); }
  function onBlur(){ setTimeout(hide, 150); }

  function attach(sel, opts={}){ const input = (typeof sel==='string')? document.querySelector(sel): sel; if(!input) return; input.setAttribute('autocomplete','off'); if(opts.multi) input.dataset.multi='true'; input.addEventListener('input', onInput); input.addEventListener('keydown', onKey); input.addEventListener('focus', onInput); input.addEventListener('blur', onBlur); }

  function autoAttach(){ attach('#bt-symbols', {multi:true}); attach('#u-symbol'); var all=document.querySelectorAll('[data-asset-picker]'); if(all && all.forEach){ all.forEach(function(el){ attach(el, {multi: el.dataset && el.dataset.multi==='true'}); }); } }
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', autoAttach, {once:true}); } else { autoAttach(); }

  window.AssetPicker = { attach, getSymbols };
})();
