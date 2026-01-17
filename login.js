const API = (typeof location !== 'undefined' && location.origin.startsWith('http')) ? location.origin : 'http://127.0.0.1:8000';
const $ = (s)=>document.querySelector(s);

async function checkStatus(){
  const el = $('#srv-status');
  const dot = el?.querySelector('.status-dot');
  try{
    const r = await fetch(API + '/healthz');
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

async function login(email, password){
  const msg = $('#lg-msg');
  msg.textContent = 'Signing in...';
  try{
    const r = await fetch(API + '/auth/login', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      credentials: 'include',
      body: JSON.stringify({email, password}),
    });
    if(!r.ok) throw new Error(await r.text());
    msg.textContent = 'Welcome back.';
    location.href = 'user.html';
  }catch(e){
    msg.textContent = String(e);
  }
}

async function signup(email, password, name){
  const msg = $('#su-msg');
  msg.textContent = 'Creating account...';
  try{
    const r = await fetch(API + '/auth/signup', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({email, password, name}),
    });
    if(!r.ok) throw new Error(await r.text());
    msg.textContent = 'Account created. Sign in on the left.';
  }catch(e){
    msg.textContent = String(e);
  }
}

$('#lg-login')?.addEventListener('click', ()=>{
  const email = ($('#lg-email').value || '').trim();
  const pass = $('#lg-pass').value || '';
  if(!email || !pass){
    $('#lg-msg').textContent = 'Enter username and password.';
    return;
  }
  login(email, pass);
});

$('#su-submit')?.addEventListener('click', ()=>{
  const email = ($('#su-email').value || '').trim();
  const name = ($('#su-name').value || '').trim();
  const pass = $('#su-pass').value || '';
  if(!email || !pass){
    $('#su-msg').textContent = 'Email and password are required.';
    return;
  }
  signup(email, pass, name);
});

checkStatus();
setInterval(checkStatus, 4000);
