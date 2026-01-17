function apiBase(){
  if (typeof window !== 'undefined' && window.API_BASE) return window.API_BASE;
  try{
    const q = new URLSearchParams(location.search);
    const api = q.get('api');
    if (api){
      window.API_BASE = api;
      return api;
    }
  }catch(_){}
  try{
    const host = location.hostname || '';
    if (!window.API_BASE && /(^|\.)mystrixwolf\.in$/i.test(host)) {
      window.API_BASE = 'https://api.mystrixwolf.in';
    }
    if (!window.API_BASE && /(^|\.)wolfmystrix\.in$/i.test(host)) {
      window.API_BASE = 'https://api.mystrixwolf.in';
    }
    if (!window.API_BASE && /(^|\.)github\.io$/i.test(host)) {
      window.API_BASE = 'https://api.mystrixwolf.in';
    }
    if (!window.API_BASE && (host === '127.0.0.1' || host === 'localhost')) {
      window.API_BASE = location.origin;
    }
  }catch(_){}
  try{
    if(location.protocol === 'file:' && !window.API_BASE){
      window.API_BASE = 'http://127.0.0.1:8000';
    }
  }catch(_){}
  return (window.API_BASE || ((typeof location !== 'undefined' && location.origin.startsWith('http'))
    ? location.origin
    : 'http://127.0.0.1:8000'));
}
const API = apiBase();
const $ = (s)=>document.querySelector(s);

async function fetchJSON(path, opts){
  const r = await fetch(API + path, {credentials:'include', ...opts});
  if(!r.ok) throw new Error(await r.text());
  return await r.json();
}

async function me(){
  try{
    const r = await fetch(API + '/me', {credentials:'include'});
    if(!r.ok) return null;
    return (await r.json()).user;
  }catch(_){
    return null;
  }
}

async function requireAdmin(){
  const user = await me();
  const overlay = $('#admin-auth');
  if(!user || !user.is_admin){
    overlay?.classList.add('active');
    return false;
  }
  overlay?.classList.remove('active');
  return true;
}

$('#admin-login')?.addEventListener('click', async ()=>{
  const u = ($('#admin-user').value || '').trim();
  const p = $('#admin-pass').value || '';
  const msg = $('#admin-auth-msg');
  msg.textContent = 'Checking...';
  try{
    const r = await fetch(API + '/auth/login', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      credentials:'include',
      body: JSON.stringify({email: u, password: p}),
    });
    if(!r.ok) throw new Error(await r.text());
    msg.textContent = 'Access granted.';
    const ok = await requireAdmin();
    if(ok) render();
  }catch(e){
    msg.textContent = String(e);
  }
});

const state = {
  users: [],
  suggestions: [],
  ledgerSummary: null,
  ledgerEvents: [],
  ledgerFilterUserId: null,
  auditFilterUserId: null,
  auditEvents: [],
};

function collectUserPayload(id){
  const table = $('#admin-users-table');
  if(!table) return null;
  const flags = {};
  table.querySelectorAll(`input[type="checkbox"][data-id="${id}"]`).forEach(cb=>{
    flags[cb.getAttribute('data-flag')] = cb.checked;
  });
  const planName = table.querySelector(`input[data-plan="plan_name"][data-id="${id}"]`)?.value || '';
  const planNote = table.querySelector(`input[data-plan="plan_note"][data-id="${id}"]`)?.value || '';
  const planDate = table.querySelector(`input[data-plan="plan_expires_at"][data-id="${id}"]`)?.value || '';
  const planExpires = planDate ? Math.floor(new Date(planDate).getTime() / 1000) : null;
  return {
    user_id: Number(id),
    has_mystrix_plus: !!flags.has_mystrix_plus,
    has_backtest: !!flags.has_backtest,
    has_autotrader: !!flags.has_autotrader,
    has_chat: !!flags.has_chat,
    is_active: !!flags.is_active,
    plan_expires_at: planExpires,
    plan_name: planName,
    plan_note: planNote,
  };
}

async function saveUser(id){
  const payload = collectUserPayload(id);
  if(!payload) return;
  try{
    await fetchJSON('/admin/users/update', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload),
    });
    $('#admin-msg').textContent = `User ${id} saved.`;
  }catch(e){
    $('#admin-msg').textContent = String(e);
  }
}

function fmtTime(ts){
  if(!ts) return '--';
  try{
    const d = new Date(ts * 1000);
    return d.toLocaleString();
  }catch(_){
    return '--';
  }
}

function fmtNum(val, digits=2){
  const num = Number(val || 0);
  return num.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fmtPct(val){
  const num = Number(val || 0) * 100;
  return `${num.toFixed(2)}%`;
}

function renderStats(){
  const users = state.users;
  const total = users.length;
  const active = users.filter(u=>u.is_active).length;
  const premium = users.filter(u=>u.has_mystrix_plus).length;
  const backtest = users.filter(u=>u.has_backtest).length;
  const autotrader = users.filter(u=>u.has_autotrader).length;
  const disabled = users.filter(u=>!u.is_active).length;

  const cards = [
    {label:'Total Users', value: total},
    {label:'Active', value: active},
    {label:'Disabled', value: disabled},
    {label:'MystriX+', value: premium},
    {label:'Backtest', value: backtest},
    {label:'AutoTrader', value: autotrader},
  ];
  $('#admin-stats').innerHTML = cards.map(c=>`
    <div class="stat-card">
      <div class="stat-label">${c.label}</div>
      <div class="stat-value">${c.value}</div>
    </div>
  `).join('');
}

function renderLedgerStats(){
  const box = $('#ledger-stats');
  if(!box) return;
  const s = state.ledgerSummary || {};
  const cards = [
    {label:'Pool Principal', value: fmtNum(s.total_principal)},
    {label:'Pool Profit', value: fmtNum(s.total_profit)},
    {label:'Total Deposits', value: fmtNum(s.total_deposits)},
    {label:'Total Withdrawals', value: fmtNum(s.total_withdrawals)},
    {label:'Profit Allocated', value: fmtNum(s.total_profit_allocated)},
    {label:'Profit Paid', value: fmtNum(s.total_profit_withdrawn)},
    {label:'Active Principals', value: s.active_principal_users || 0},
  ];
  box.innerHTML = cards.map(c=>`
    <div class="stat-card">
      <div class="stat-label">${c.label}</div>
      <div class="stat-value">${c.value}</div>
    </div>
  `).join('');

  const batch = $('#ledger-batch');
  if(batch){
    if(s.last_batch){
      batch.innerHTML = `
        <strong>Last Yield Batch</strong>
        <div>Amount: ${fmtNum(s.last_batch.amount)} | Principal Base: ${fmtNum(s.last_batch.total_principal)} | Users: ${s.last_batch.allocated_to}</div>
        <div>${s.last_batch.note ? `Note: ${s.last_batch.note} | ` : ''}${fmtTime(s.last_batch.created_at)}</div>
      `;
    }else{
      batch.textContent = 'No yield allocations yet.';
    }
  }
}

function applyFilters(){
  const query = ($('#user-search').value || '').trim().toLowerCase();
  const planFilter = $('#filter-plan').value;
  const activeFilter = $('#filter-active').value;

  return state.users.filter(u=>{
    const searchable = `${u.email||''} ${u.name||''} ${u.plan_name||''} ${u.plan_note||''}`.toLowerCase();
    if(query && !searchable.includes(query)) return false;
    if(planFilter === 'premium' && !u.has_mystrix_plus) return false;
    if(planFilter === 'free' && u.has_mystrix_plus) return false;
    if(activeFilter === 'active' && !u.is_active) return false;
    if(activeFilter === 'disabled' && u.is_active) return false;
    return true;
  });
}

function renderUsers(){
  const rows = applyFilters().map(u=>{
    const expiry = u.plan_expires_at ? new Date(u.plan_expires_at * 1000).toISOString().slice(0,10) : '';
    const principal = fmtNum(u.principal_balance);
    const profit = fmtNum(u.profit_balance);
    const net = fmtNum(u.net_balance);
    const ratio = fmtPct(u.principal_ratio);
    const deposits = fmtNum(u.total_deposits);
    const withdrawals = fmtNum(u.total_withdrawals);
    const profitAlloc = fmtNum(u.total_profit);
    const profitPaid = fmtNum(u.total_profit_withdrawn);
    const created = fmtTime(u.created_at);
    const apiUpdated = fmtTime(u.api_updated_at);
    const apiKeyMask = u.api_key_masked || '';
    const apiSecretMask = u.api_secret_masked || '';
    return `
      <tr>
        <td><input type="checkbox" class="bulk-select" data-id="${u.id}"/></td>
        <td>${u.id}</td>
        <td>${u.email}</td>
        <td>${u.name || ''}</td>
        <td>${principal}</td>
        <td>${profit}</td>
        <td>${net}</td>
        <td>${ratio}</td>
        <td>${deposits}</td>
        <td>${withdrawals}</td>
        <td>${profitAlloc}</td>
        <td>${profitPaid}</td>
        <td>${fmtTime(u.last_deposit_at)}</td>
        <td>${fmtTime(u.last_withdrawal_at)}</td>
        <td>${fmtTime(u.last_profit_at)}</td>
        <td>
          <label class="switch"><input type="checkbox" data-flag="is_active" data-id="${u.id}" ${u.is_active?'checked':''}/><span class="slider"></span></label>
        </td>
        <td>
          <label class="switch"><input type="checkbox" data-flag="has_mystrix_plus" data-id="${u.id}" ${u.has_mystrix_plus?'checked':''}/><span class="slider"></span></label>
        </td>
        <td>
          <label class="switch"><input type="checkbox" data-flag="has_backtest" data-id="${u.id}" ${u.has_backtest?'checked':''}/><span class="slider"></span></label>
        </td>
        <td>
          <label class="switch"><input type="checkbox" data-flag="has_autotrader" data-id="${u.id}" ${u.has_autotrader?'checked':''}/><span class="slider"></span></label>
        </td>
        <td>
          <label class="switch"><input type="checkbox" data-flag="has_chat" data-id="${u.id}" ${u.has_chat?'checked':''}/><span class="slider"></span></label>
        </td>
        <td><input type="text" data-plan="plan_name" data-id="${u.id}" value="${u.plan_name||''}" placeholder="Plan name"/></td>
        <td><input type="text" data-plan="plan_note" data-id="${u.id}" value="${u.plan_note||''}" placeholder="Plan note"/></td>
        <td><input type="date" data-plan="plan_expires_at" data-id="${u.id}" value="${expiry}"/></td>
        <td>${fmtTime(u.last_login)}</td>
        <td>${created}</td>
        <td><input type="text" data-api="label" data-id="${u.id}" value="${u.api_label||''}" placeholder="Label"/></td>
        <td><input type="text" data-api="key" data-id="${u.id}" placeholder="${apiKeyMask || 'Not set'}"/></td>
        <td><input type="password" data-api="secret" data-id="${u.id}" placeholder="${apiSecretMask || 'Not set'}"/></td>
        <td>${apiUpdated}</td>
        <td>
          <button class="cta save-user" data-id="${u.id}">Save</button>
          <button class="cta reset-pass" data-id="${u.id}">Reset</button>
          <button class="cta force-logout" data-id="${u.id}">Logout</button>
          <button class="cta ledger-user" data-id="${u.id}">Ledger</button>
          <button class="cta save-api" data-id="${u.id}">Save API</button>
          <button class="cta danger clear-api" data-id="${u.id}">Clear API</button>
          <button class="cta danger delete-user" data-id="${u.id}">Delete</button>
        </td>
      </tr>
    `;
  }).join('');

  $('#admin-users-table').innerHTML = `
    <table class="trades">
      <thead>
        <tr>
          <th>Select</th>
          <th>ID</th>
          <th>Email</th>
          <th>Name</th>
          <th>Principal</th>
          <th>Profit</th>
          <th>Net</th>
          <th>Ratio</th>
          <th>Deposits</th>
          <th>Withdrawals</th>
          <th>Profit Alloc</th>
          <th>Profit Paid</th>
          <th>Last Deposit</th>
          <th>Last Withdraw</th>
          <th>Last Profit</th>
          <th>Active</th>
          <th>MystriX+</th>
          <th>Backtest</th>
          <th>AutoTrader</th>
          <th>Chat</th>
          <th>Plan</th>
          <th>Note</th>
          <th>Expires</th>
          <th>Last Login</th>
          <th>Created</th>
          <th>API Label</th>
          <th>API Key</th>
          <th>API Secret</th>
          <th>API Updated</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>${rows || `<tr><td colspan="30">No users found.</td></tr>`}</tbody>
    </table>
  `;

  $('#admin-users-table').querySelectorAll('.save-user').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const id = Number(btn.getAttribute('data-id'));
      await saveUser(id);
      await loadUsers();
    });
  });

  $('#admin-users-table').querySelectorAll('.reset-pass').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const id = Number(btn.getAttribute('data-id'));
      const next = prompt('New password for user ' + id + '?');
      if(!next) return;
      try{
        await fetchJSON('/admin/users/reset_password', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({user_id: id, new_password: next}),
        });
        $('#admin-msg').textContent = `Password reset for user ${id}.`;
      }catch(e){
        $('#admin-msg').textContent = String(e);
      }
    });
  });

  $('#admin-users-table').querySelectorAll('.force-logout').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const id = Number(btn.getAttribute('data-id'));
      try{
        await fetchJSON('/admin/users/logout?user_id=' + id, {method:'POST'});
        $('#admin-msg').textContent = `Sessions cleared for user ${id}.`;
      }catch(e){
        $('#admin-msg').textContent = String(e);
      }
    });
  });

  $('#admin-users-table').querySelectorAll('.delete-user').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const id = Number(btn.getAttribute('data-id'));
      const ok = confirm(`Delete user ${id}? This cannot be undone.`);
      if(!ok) return;
      try{
        await fetchJSON('/admin/users/delete', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({user_id: id}),
        });
        $('#admin-msg').textContent = `User ${id} deleted.`;
        await loadUsers();
      }catch(e){
        $('#admin-msg').textContent = String(e);
      }
    });
  });

  $('#admin-users-table').querySelectorAll('input[type="checkbox"][data-id]').forEach(cb=>{
    cb.addEventListener('change', async ()=>{
      const id = Number(cb.getAttribute('data-id'));
      await saveUser(id);
    });
  });
  $('#admin-users-table').querySelectorAll('input[data-plan="plan_name"], input[data-plan="plan_note"]').forEach(inp=>{
    inp.addEventListener('blur', async ()=>{
      const id = Number(inp.getAttribute('data-id'));
      await saveUser(id);
    });
  });
  $('#admin-users-table').querySelectorAll('input[data-plan="plan_expires_at"]').forEach(inp=>{
    inp.addEventListener('change', async ()=>{
      const id = Number(inp.getAttribute('data-id'));
      await saveUser(id);
    });
  });

  $('#admin-users-table').querySelectorAll('.ledger-user').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const id = Number(btn.getAttribute('data-id'));
      state.ledgerFilterUserId = id;
      const filter = $('#ledger-filter-user');
      if(filter) filter.value = String(id);
      await loadLedgerEvents();
    });
  });

  $('#admin-users-table').querySelectorAll('.save-api').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const id = Number(btn.getAttribute('data-id'));
      const label = $('#admin-users-table').querySelector(`input[data-api="label"][data-id="${id}"]`)?.value || '';
      const key = $('#admin-users-table').querySelector(`input[data-api="key"][data-id="${id}"]`)?.value || '';
      const secret = $('#admin-users-table').querySelector(`input[data-api="secret"][data-id="${id}"]`)?.value || '';
      try{
        await fetchJSON('/admin/users/api', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({
            user_id: id,
            api_label: label,
            api_key: key || null,
            api_secret: secret || null,
          }),
        });
        $('#admin-msg').textContent = `API updated for user ${id}.`;
        await loadUsers();
      }catch(e){
        $('#admin-msg').textContent = String(e);
      }
    });
  });

  $('#admin-users-table').querySelectorAll('.clear-api').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const id = Number(btn.getAttribute('data-id'));
      const ok = confirm(`Clear API credentials for user ${id}?`);
      if(!ok) return;
      try{
        await fetchJSON('/admin/users/api', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({user_id: id, clear: true}),
        });
        $('#admin-msg').textContent = `API cleared for user ${id}.`;
        await loadUsers();
      }catch(e){
        $('#admin-msg').textContent = String(e);
      }
    });
  });

  const selectAll = $('#bulk-select-all');
  if(selectAll && selectAll.checked){
    $('#admin-users-table').querySelectorAll('.bulk-select').forEach(cb=>{ cb.checked = true; });
  }
}

function renderLedgerUserOptions(){
  const userSelects = [$('#ledger-user'), $('#ledger-profit-user')].filter(Boolean);
  const filterSelect = $('#ledger-filter-user');
  const auditSelect = $('#audit-filter-user');
  if(!userSelects.length && !filterSelect && !auditSelect) return;
  const options = state.users.map(u=>{
    const label = `${u.email || u.name || 'User'} (#${u.id})`;
    return `<option value="${u.id}">${label}</option>`;
  }).join('');
  userSelects.forEach(sel=>{
    const current = sel.value;
    sel.innerHTML = options;
    if(current){
      sel.value = current;
    }
  });
  if(filterSelect){
    const current = filterSelect.value;
    filterSelect.innerHTML = `<option value="">All users</option>` + options;
    filterSelect.value = current;
  }
  if(auditSelect){
    const current = auditSelect.value;
    auditSelect.innerHTML = `<option value="">All users</option>` + options;
    auditSelect.value = current;
  }
}

async function loadUsers(){
  const data = await fetchJSON('/admin/users');
  state.users = data.users || [];
  renderStats();
  renderUsers();
  renderLedgerUserOptions();
}

async function loadLedgerSummary(){
  state.ledgerSummary = await fetchJSON('/admin/ledger/summary');
  renderLedgerStats();
}

async function loadLedgerEvents(){
  const userId = state.ledgerFilterUserId;
  const query = userId ? `?limit=50&user_id=${encodeURIComponent(userId)}` : '?limit=50';
  const data = await fetchJSON('/admin/ledger/events' + query);
  state.ledgerEvents = data.events || [];
  const rows = state.ledgerEvents.map(e=>`
    <tr>
      <td>${e.id}</td>
      <td>${e.email || ''}</td>
      <td>${e.kind}</td>
      <td>${fmtNum(e.principal_delta)}</td>
      <td>${fmtNum(e.profit_delta)}</td>
      <td>${e.note || ''}</td>
      <td>${fmtTime(e.created_at)}</td>
      <td>${e.batch_id || ''}</td>
    </tr>
  `).join('');
  $('#ledger-events').innerHTML = `
    <table class="trades">
      <thead>
        <tr><th>ID</th><th>User</th><th>Kind</th><th>Principal Δ</th><th>Profit Δ</th><th>Note</th><th>When</th><th>Batch</th></tr>
      </thead>
      <tbody>${rows || `<tr><td colspan="8">No ledger activity yet.</td></tr>`}</tbody>
    </table>
  `;
}

async function loadAuditEvents(){
  const userId = state.auditFilterUserId;
  const query = userId ? `?limit=100&target_user_id=${encodeURIComponent(userId)}` : '?limit=100';
  const data = await fetchJSON('/admin/audit' + query);
  state.auditEvents = data.events || [];
  const rows = state.auditEvents.map(e=>{
    let payload = e.payload || '';
    if(payload && payload.length > 120){
      payload = payload.slice(0, 117) + '...';
    }
    return `
      <tr>
        <td>${e.id}</td>
        <td>${e.action}</td>
        <td>${e.admin_email || e.admin_name || ''}</td>
        <td>${e.user_email || e.user_name || ''}</td>
        <td>${payload}</td>
        <td>${fmtTime(e.created_at)}</td>
      </tr>
    `;
  }).join('');
  $('#audit-events').innerHTML = `
    <table class="trades">
      <thead>
        <tr><th>ID</th><th>Action</th><th>Admin</th><th>User</th><th>Payload</th><th>When</th></tr>
      </thead>
      <tbody>${rows || `<tr><td colspan="6">No audit events yet.</td></tr>`}</tbody>
    </table>
  `;
}

async function ledgerAction(path, payload, okMsg){
  const msg = $('#ledger-msg');
  if(msg) msg.textContent = 'Working...';
  try{
    await fetchJSON(path, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload),
    });
    if(msg) msg.textContent = okMsg;
    await render();
  }catch(e){
    if(msg) msg.textContent = String(e);
  }
}

async function loadSuggestions(){
  const data = await fetchJSON('/admin/suggestions');
  state.suggestions = data.suggestions || [];
  const rows = state.suggestions.map(s=>`
    <tr>
      <td>${s.id}</td>
      <td>${s.email || ''}</td>
      <td>${s.text}</td>
      <td>${fmtTime(s.created_at)}</td>
      <td>${s.resolved ? 'yes' : 'no'}</td>
      <td>${s.resolved ? '' : `<button class="cta resolve-sug" data-id="${s.id}">Resolve</button>`}</td>
    </tr>
  `).join('');
  $('#admin-suggestions').innerHTML = `
    <table class="trades">
      <thead>
        <tr><th>ID</th><th>User</th><th>Text</th><th>Created</th><th>Resolved</th><th></th></tr>
      </thead>
      <tbody>${rows || `<tr><td colspan="6">No suggestions.</td></tr>`}</tbody>
    </table>
  `;
  $('#admin-suggestions').querySelectorAll('.resolve-sug').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const id = btn.getAttribute('data-id');
      try{
        await fetchJSON('/admin/suggestions/resolve?id=' + id, {method:'POST'});
        await loadSuggestions();
      }catch(e){
        $('#admin-msg').textContent = String(e);
      }
    });
  });
}

async function render(){
  await loadUsers();
  await loadSuggestions();
  await loadLedgerSummary();
  await loadLedgerEvents();
  await loadAuditEvents();
}

$('#refresh-users')?.addEventListener('click', render);
$('#user-search')?.addEventListener('input', renderUsers);
$('#filter-plan')?.addEventListener('change', renderUsers);
$('#filter-active')?.addEventListener('change', renderUsers);

function selectedUserIds(){
  const list = [];
  document.querySelectorAll('.bulk-select').forEach(cb=>{
    if(cb.checked){
      const id = Number(cb.getAttribute('data-id'));
      if(id) list.push(id);
    }
  });
  return list;
}

async function bulkUpdate(payload, okMsg){
  const msg = $('#admin-msg');
  if(msg) msg.textContent = 'Working...';
  try{
    payload.user_ids = selectedUserIds();
    if(!payload.user_ids.length){
      if(msg) msg.textContent = 'Select at least one user.';
      return;
    }
    await fetchJSON('/admin/users/bulk_update', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload),
    });
    if(msg) msg.textContent = okMsg;
    await loadUsers();
  }catch(e){
    if(msg) msg.textContent = String(e);
  }
}

$('#bulk-select-all')?.addEventListener('change', (e)=>{
  const checked = e.target.checked;
  document.querySelectorAll('.bulk-select').forEach(cb=>{ cb.checked = checked; });
});

$('#bulk-enable-plus')?.addEventListener('click', ()=> bulkUpdate({has_mystrix_plus:true}, 'MystriX+ enabled.'));
$('#bulk-disable-plus')?.addEventListener('click', ()=> bulkUpdate({has_mystrix_plus:false}, 'MystriX+ disabled.'));
$('#bulk-enable-backtest')?.addEventListener('click', ()=> bulkUpdate({has_backtest:true}, 'Backtest enabled.'));
$('#bulk-disable-backtest')?.addEventListener('click', ()=> bulkUpdate({has_backtest:false}, 'Backtest disabled.'));
$('#bulk-enable-autotrader')?.addEventListener('click', ()=> bulkUpdate({has_autotrader:true}, 'AutoTrader enabled.'));
$('#bulk-disable-autotrader')?.addEventListener('click', ()=> bulkUpdate({has_autotrader:false}, 'AutoTrader disabled.'));
$('#bulk-enable-chat')?.addEventListener('click', ()=> bulkUpdate({has_chat:true}, 'Chat enabled.'));
$('#bulk-disable-chat')?.addEventListener('click', ()=> bulkUpdate({has_chat:false}, 'Chat disabled.'));
$('#bulk-activate')?.addEventListener('click', ()=> bulkUpdate({is_active:true}, 'Users activated.'));
$('#bulk-disable')?.addEventListener('click', ()=> bulkUpdate({is_active:false}, 'Users disabled.'));

$('#bulk-apply-plan')?.addEventListener('click', ()=>{
  const name = $('#bulk-plan-name')?.value || '';
  const note = $('#bulk-plan-note')?.value || '';
  const expires = $('#bulk-plan-expires')?.value || '';
  const expiresAt = expires ? Math.floor(new Date(expires).getTime() / 1000) : null;
  bulkUpdate({
    plan_name: name || null,
    plan_note: note || null,
    plan_expires_at: expiresAt,
  }, 'Plan details applied.');
});

$('#bulk-clear-expiry')?.addEventListener('click', ()=> bulkUpdate({clear_plan_expires:true}, 'Expiry cleared.'));

$('#ledger-filter-apply')?.addEventListener('click', async ()=>{
  const userId = Number($('#ledger-filter-user')?.value || 0);
  state.ledgerFilterUserId = userId || null;
  await loadLedgerEvents();
});

$('#ledger-filter-clear')?.addEventListener('click', async ()=>{
  state.ledgerFilterUserId = null;
  const filter = $('#ledger-filter-user');
  if(filter) filter.value = '';
  await loadLedgerEvents();
});

$('#ledger-export')?.addEventListener('click', ()=>{
  const userId = state.ledgerFilterUserId;
  const url = API + '/admin/ledger/export' + (userId ? `?user_id=${encodeURIComponent(userId)}` : '');
  window.open(url, '_blank');
});

$('#audit-filter-apply')?.addEventListener('click', async ()=>{
  const userId = Number($('#audit-filter-user')?.value || 0);
  state.auditFilterUserId = userId || null;
  await loadAuditEvents();
});

$('#audit-filter-clear')?.addEventListener('click', async ()=>{
  state.auditFilterUserId = null;
  const filter = $('#audit-filter-user');
  if(filter) filter.value = '';
  await loadAuditEvents();
});

$('#audit-export')?.addEventListener('click', ()=>{
  const userId = state.auditFilterUserId;
  const url = API + '/admin/audit/export' + (userId ? `?target_user_id=${encodeURIComponent(userId)}` : '');
  window.open(url, '_blank');
});

$('#ledger-deposit')?.addEventListener('click', async ()=>{
  const userId = Number($('#ledger-user')?.value || 0);
  const amount = Number($('#ledger-amount')?.value || 0);
  const note = $('#ledger-note')?.value || '';
  if(!userId) return;
  await ledgerAction('/admin/ledger/deposit', {user_id: userId, amount, note}, 'Deposit recorded.');
});

$('#ledger-withdraw')?.addEventListener('click', async ()=>{
  const userId = Number($('#ledger-user')?.value || 0);
  const amount = Number($('#ledger-amount')?.value || 0);
  const note = $('#ledger-note')?.value || '';
  if(!userId) return;
  await ledgerAction('/admin/ledger/withdraw', {user_id: userId, amount, note}, 'Principal withdrawn.');
});

$('#ledger-allocate')?.addEventListener('click', async ()=>{
  const amount = Number($('#ledger-yield')?.value || 0);
  const note = $('#ledger-yield-note')?.value || '';
  await ledgerAction('/admin/ledger/profit_allocate', {amount, note}, 'Profit allocated.');
});

$('#ledger-profit-withdraw')?.addEventListener('click', async ()=>{
  const userId = Number($('#ledger-profit-user')?.value || 0);
  const amount = Number($('#ledger-profit-amount')?.value || 0);
  const note = $('#ledger-profit-note')?.value || '';
  if(!userId) return;
  await ledgerAction('/admin/ledger/profit_withdraw', {user_id: userId, amount, note}, 'Profit withdrawal recorded.');
});

(async ()=>{
  if(await requireAdmin()){
    render();
  }
})();
