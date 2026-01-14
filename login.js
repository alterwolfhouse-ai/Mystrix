const API = (typeof location !== 'undefined' && location.origin.startsWith('http')) ? location.origin : 'http://127.0.0.1:8000';
const $ = (s)=>document.querySelector(s);
const isLocalHost = (() => {
  try {
    const host = location.hostname || '';
    return host === 'localhost' || host === '127.0.0.1' || host === '[::1]';
  } catch (_) {
    return false;
  }
})();

async function checkStatus(){ const el=$('#srv-status'); const dot=el?.querySelector('.status-dot'); try{ const r=await fetch(API+'/healthz'); const ok=r.ok; if(dot){ dot.classList.toggle('dot-on',ok); dot.classList.toggle('dot-off',!ok); el.innerHTML=`Server: <span class=\"status-dot ${ok?'dot-on':'dot-off'}\"></span> ${ok?'Online':'Offline'}`; } }catch(_){ if(dot){ dot.classList.add('dot-off'); dot.classList.remove('dot-on'); el.innerHTML='Server: <span class=\"status-dot dot-off\"></span> Offline'; } } }

async function login(email, password){ const msg=$('#lg-msg'); try{ const r=await fetch(API+'/auth/login',{method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body:JSON.stringify({email,password})}); if(!r.ok) throw new Error(await r.text()); msg.textContent='Logged in'; location.href='user.html'; }catch(e){ msg.textContent=String(e); }}

document.getElementById('lg-login')?.addEventListener('click', ()=>{ const e=$('#lg-email').value.trim(); const p=$('#lg-pass').value; login(e,p); });
const adminBtn = document.getElementById('lg-admin');
const demoBtn = document.getElementById('lg-demo');
if (!isLocalHost) {
  adminBtn?.remove();
  demoBtn?.remove();
} else {
  adminBtn?.addEventListener('click', ()=>{ login('fantum','wolfhouse'); });
  demoBtn?.addEventListener('click', ()=>{ login('era','Bubble@26'); });
}

checkStatus(); setInterval(checkStatus, 4000);
