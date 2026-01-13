(function(){
  function $(s){ return document.querySelector(s); }
  function txt(id){ return document.getElementById(id).value; }
  function setv(id,val){ var el=document.getElementById(id); if(el && val!==undefined && val!==null) el.value=String(val); }
  function api(){ try{ return window.API_BASE || location.origin || 'http://127.0.0.1:8000'; }catch(_){ return 'http://127.0.0.1:8000'; } }
  function canon(s){ return (s||'').toUpperCase().replace(/\//g,''); }
  function keySlot(prod,sym){ return 'pm:lastSlot:'+prod+':'+canon(sym); }

  function toParams(){ return {
    long: { timeframe_hist: '3m', rsi_length: parseInt(txt('pl-rsi-len')||'14'), rsi_overbought: parseInt(txt('pl-rsi-ob')||'79'), rsi_oversold: parseInt(txt('pl-rsi-os')||'27'), lookbackLeft: parseInt(txt('pl-lb-l')||'5'), lookbackRight: parseInt(txt('pl-lb-r')||'5'), rangeLower: parseInt(txt('pl-range-low')||'5'), rangeUpper: parseInt(txt('pl-range-up')||'60') },
    short: { timeframe_hist: '3m', rsi_length: parseInt(txt('ps-rsi-len')||'14'), rsi_overbought: parseInt(txt('ps-rsi-ob')||'79'), rsi_oversold: parseInt(txt('ps-rsi-os')||'27'), lookbackLeft: parseInt(txt('ps-lb-l')||'5'), lookbackRight: parseInt(txt('ps-lb-r')||'5'), rangeLower: parseInt(txt('ps-range-low')||'5'), rangeUpper: parseInt(txt('ps-range-up')||'60') }
  }; }
  function fromParams(p){ if(!p) return; var L=p.long||{}, S=p.short||{};
    setv('pl-rsi-len',L.rsi_length); setv('pl-rsi-ob',L.rsi_overbought); setv('pl-rsi-os',L.rsi_oversold); setv('pl-lb-l',L.lookbackLeft); setv('pl-lb-r',L.lookbackRight); setv('pl-range-low',L.rangeLower); setv('pl-range-up',L.rangeUpper);
    setv('ps-rsi-len',S.rsi_length); setv('ps-rsi-ob',S.rsi_overbought); setv('ps-rsi-os',S.rsi_oversold); setv('ps-lb-l',S.lookbackLeft); setv('ps-lb-r',S.lookbackRight); setv('ps-range-low',S.rangeLower); setv('ps-range-up',S.rangeUpper);
  }

  function listSlots(){ var prod=txt('pm-product')||'mystrix'; var sym=txt('pm-symbol'); var url=api()+'/api/presets/get?product='+encodeURIComponent(prod)+'&symbol='+encodeURIComponent(sym); var box=$('#pm-status'); box.textContent='Loading...'; fetch(url).then(function(r){ return r.json(); }).then(function(j){ var div=$('#pm-list'); var presets=j.presets||{}; var keys=Object.keys(presets); var html=''; if(keys.length===0){ html='<p class="status">No presets yet.</p>'; } else { html='<table class="trades"><thead><tr><th>Slot</th><th>Updated</th></tr></thead><tbody>'; keys.forEach(function(k){ var it=presets[k]; if(it&&it.params){ var dt = it.updatedAt ? new Date(it.updatedAt).toLocaleString() : ''; html+='<tr data-slot="'+k+'"><td>'+k+'</td><td>'+dt+'</td></tr>'; } }); html+='</tbody></table>'; }
    div.innerHTML=html; box.textContent='';
    var rows=document.querySelectorAll('#pm-list tr[data-slot]'); Array.prototype.forEach.call(rows, function(tr){ tr.style.cursor='pointer'; tr.addEventListener('click', function(){ document.getElementById('pm-slot').value = tr.getAttribute('data-slot'); loadSlot(); }); });
  }).catch(function(){ $('#pm-status').textContent='Error'; }); }

  function loadSlot(){ var prod=txt('pm-product')||'mystrix'; var sym=txt('pm-symbol'); var slot=(txt('pm-slot')||'').trim(); if(!slot){ $('#pm-status').textContent='Enter slot'; return; } var url=api()+'/api/presets/get?product='+encodeURIComponent(prod)+'&symbol='+encodeURIComponent(sym); $('#pm-status').textContent='Loading...'; fetch(url).then(function(r){ return r.json(); }).then(function(j){ var p=j&&j.presets&&j.presets[slot]&&j.presets[slot].params; if(p){ fromParams(p); $('#pm-status').textContent='Loaded'; try{ localStorage.setItem(keySlot(prod,sym), slot);}catch(_){ } } else { $('#pm-status').textContent='Not found'; }
    setTimeout(function(){ $('#pm-status').textContent=''; }, 1200);
  }).catch(function(){ $('#pm-status').textContent='Error'; }); }

  function saveSlot(){ var prod=txt('pm-product')||'mystrix'; var sym=txt('pm-symbol'); var slot=(txt('pm-slot')||'').trim(); if(!slot){ $('#pm-status').textContent='Enter slot'; return; } var body={ product: prod, symbol: sym, slot: slot, params: toParams() }; $('#pm-status').textContent='Saving...'; fetch(api()+'/api/presets/save', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) }).then(function(r){ return r.json().then(function(j){ return {ok:r.ok,data:j}; }); }).then(function(res){ $('#pm-status').textContent = res.ok? 'Saved' : 'Error'; listSlots(); try{ localStorage.setItem(keySlot(prod,sym), slot);}catch(_){ } setTimeout(function(){ $('#pm-status').textContent=''; }, 1200); }).catch(function(){ $('#pm-status').textContent='Error'; }); }

  function deleteSlot(){ var prod=txt('pm-product')||'mystrix'; var sym=txt('pm-symbol'); var slot=(txt('pm-slot')||'').trim(); if(!slot){ $('#pm-status').textContent='Enter slot'; return; } $('#pm-status').textContent='Deleting...'; fetch(api()+'/api/presets/delete', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({product:prod, symbol:sym, slot:slot}) }).then(function(r){ return r.json().then(function(j){ return {ok:r.ok,data:j}; }); }).then(function(res){ $('#pm-status').textContent = res.ok? 'Deleted' : 'Error'; listSlots(); setTimeout(function(){ $('#pm-status').textContent=''; }, 1200); }).catch(function(){ $('#pm-status').textContent='Error'; }); }

  function init(){
    document.getElementById('pm-load-list').addEventListener('click', listSlots, false);
    document.getElementById('pm-load-slot').addEventListener('click', loadSlot, false);
    document.getElementById('pm-save-slot').addEventListener('click', saveSlot, false);
    document.getElementById('pm-delete-slot').addEventListener('click', deleteSlot, false);
    // restore last slot per asset
    try{ var prod=txt('pm-product')||'mystrix'; var sym=txt('pm-symbol'); var last=localStorage.getItem(keySlot(prod,sym)); if(last){ document.getElementById('pm-slot').value=last; } }catch(_){ }
    listSlots();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init, false); else init();
})();

