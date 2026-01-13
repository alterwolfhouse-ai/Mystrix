// Shared Preset Client for Admin/Magic pages
// Drop-in usage:
//   <script src="/static/presets_client.js"></script>
//   Presets.save('mystrix','BTC/USDT','bull', params)
//   const presets = await Presets.load('mystrix','BTC/USDT')

window.Presets = (function(){
  const KEY = 'mystrix.presets.v1';
  const norm = s => (s || '').toUpperCase().replace('/', '');

  async function save(product, symbol, slot, params){
    // server
    await fetch('/api/presets/save',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({product, symbol, slot, params})
    });
    // local cache
    const sym = norm(symbol);
    const store = JSON.parse(localStorage.getItem(KEY) || '{}');
    store[sym] = store[sym] || { bull:{}, bear:{}, chop:{} };
    store[sym][slot] = { params, updatedAt: Date.now() };
    localStorage.setItem(KEY, JSON.stringify(store));
  }

  async function load(product, symbol){
    const res = await fetch(`/api/presets/get?product=${encodeURIComponent(product)}&symbol=${encodeURIComponent(symbol)}`);
    if(!res.ok) throw new Error(await res.text());
    const data = await res.json();
    // also refresh local cache
    const sym = norm(symbol);
    const store = JSON.parse(localStorage.getItem(KEY) || '{}');
    store[sym] = data.presets || { bull:{}, bear:{}, chop:{} };
    localStorage.setItem(KEY, JSON.stringify(store));
    return data.presets;
  }

  function getLocal(symbol, slot){
    const sym = norm(symbol);
    const store = JSON.parse(localStorage.getItem(KEY) || '{}');
    return (store[sym] && store[sym][slot] && store[sym][slot].params) || null;
  }

  return { save, load, getLocal, KEY };
})();

