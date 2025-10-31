function attachOverlay(formId){
  const form = document.getElementById(formId);
  if(!form) return;
  form.addEventListener('submit', (e)=>{
    const ov = document.getElementById('overlay');
    if(ov){
      ov.hidden = false;
      startProgressHints();
    }
  });
}

function stopProgressHints(){
  if(hintTimer){ clearInterval(hintTimer); hintTimer = null; }
}

function setupAjaxSubmit(formId){
  const form = document.getElementById(formId);
  if(!form) return;
  form.addEventListener('submit', async (ev)=>{
    ev.preventDefault();
    const ov = document.getElementById('overlay');
    const icon = document.getElementById('overlay-icon');
    if(ov){
      ov.hidden = false; startProgressHints();
      if(icon){ icon.classList.remove('overlay-success','overlay-error'); icon.classList.add('overlay-running'); }
    }
    try{
      const fd = new FormData(form);
      const resp = await fetch(form.action || window.location.pathname, { method:'POST', body: fd });
      const ct = (resp.headers.get('content-type')||'').toLowerCase();
      const cd = resp.headers.get('content-disposition')||'';
      if(!resp.ok){
        const text = await resp.text();
        if(icon){ icon.classList.remove('overlay-running'); icon.classList.add('overlay-error'); }
        setOverlayMsg('Error ' + resp.status + ': ' + text.slice(0,140));
        // keep toast visible for a bit
        await sleep(4000);
      } else if (ct.includes('text/html')){
        const html = await resp.text();
        if(icon){ icon.classList.remove('overlay-running'); icon.classList.add('overlay-success'); }
        try{
          const successCount = (html.match(/<a href=\"\/download\//g) || []).length;
          const failCount = (html.match(/<div class=\"error\"/g) || []).length;
          const secs = Math.max(1, Math.round((Date.now()-started)/1000));
          if(typeof showToast === 'function'){
            showToast(Processed  OK,  failed in s);
          }
        } catch{}
        setOverlayMsg('Done ✓');
        await sleep(600);
        stopProgressHints(); if(ov){ ov.hidden = true; }
        document.open(); document.write(html); document.close();
        return; // done
      } else if (ct.startsWith('audio') || cd.toLowerCase().includes('attachment')){
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        // Try filename from content-disposition
        const m = /filename\s*=\s*"?([^";]+)"?/i.exec(cd);
        a.download = m ? m[1] : 'download';
        a.href = url; document.body.appendChild(a); a.click(); a.remove();
        setTimeout(()=>URL.revokeObjectURL(url), 5000);
        if(icon){ icon.classList.remove('overlay-running'); icon.classList.add('overlay-success'); }
        try{
          const successCount = (html.match(/<a href=\"\/download\//g) || []).length;
          const failCount = (html.match(/<div class=\"error\"/g) || []).length;
          const secs = Math.max(1, Math.round((Date.now()-started)/1000));
          if(typeof showToast === 'function'){
            showToast(Processed  OK,  failed in s);
          }
        } catch{}
        setOverlayMsg('Download started ✓');
        await sleep(1000);
      } else {
        // Fallback JSON or other types: navigate to history
        try{ const data = await resp.json(); console.log('Response', data); } catch{}
        if(icon){ icon.classList.remove('overlay-running'); icon.classList.add('overlay-success'); }
        try{
          const successCount = (html.match(/<a href=\"\/download\//g) || []).length;
          const failCount = (html.match(/<div class=\"error\"/g) || []).length;
          const secs = Math.max(1, Math.round((Date.now()-started)/1000));
          if(typeof showToast === 'function'){
            showToast(Processed  OK,  failed in s);
          }
        } catch{}
        setOverlayMsg('Done ✓');
        await sleep(600);
        window.location.href = '/history';
        return;
      }
    } catch(e){
      console.error(e);
      setOverlayMsg('Error: ' + e);
      const icon = document.getElementById('overlay-icon');
      if(icon){ icon.classList.remove('overlay-running'); icon.classList.add('overlay-error'); }
      await sleep(2500);
    } finally {
      stopProgressHints();
      if(ov){ ov.hidden = true; }
    }
  });
}

let hintTimer = null;
function startProgressHints(){
  const el = document.getElementById('overlay-msg');
  if(!el) return;
  const fast = !!document.querySelector('input[name="fast_mode"]:checked');
  const baseHints = fast ? [
    'Uploading…',
    'Fast chain: light denoise…',
    'Fast chain: de-ess…',
    'Fast chain: limiting…',
    'Saving output…',
  ] : [
    'Uploading…',
    'Applying denoise (afftdn)…',
    'De-essing…',
    'Filtering (high/low-pass)…',
    'Limiting and normalizing…',
    'Saving output…',
  ];
  let i = 0;
  el.textContent = baseHints[0];
  if(hintTimer) clearInterval(hintTimer);
  hintTimer = setInterval(()=>{
    i = (i + 1) % baseHints.length;
    el.textContent = baseHints[i];
  }, 2500);
}

function setOverlayMsg(t){
  const el = document.getElementById('overlay-msg');
  if(el){ el.textContent = String(t); }
}

function sleep(ms){ return new Promise(res => setTimeout(res, ms)); }

function applyPreset(values){
  const map = {
    noise_reduce: 'input[name="noise_reduce"]',
    noise_floor: 'input[name="noise_floor"]',
    deess_center: 'input[name="deess_center"]',
    deess_strength: 'input[name="deess_strength"]',
    highpass: 'input[name="highpass"]',
    lowpass: 'input[name="lowpass"]',
    limiter: 'input[name="limiter"]',
  };
  for(const k in values){
    const sel = map[k];
    const el = document.querySelector(sel);
    if(el){ el.value = values[k]; }
  }
}

function setupPresets(){
  const sel = document.getElementById('preset-select');
  if(!sel) return;
  sel.addEventListener('change', ()=>{
    const p = sel.value;
    if(p === 'music'){
      applyPreset({noise_reduce:12, noise_floor:-28, deess_center:0.25, deess_strength:1.0, highpass:30, lowpass:18000, limiter:0.98});
    } else if(p === 'podcast'){
      applyPreset({noise_reduce:14, noise_floor:-30, deess_center:0.22, deess_strength:1.4, highpass:80, lowpass:17000, limiter:0.96});
    } else if(p === 'aggressive'){
      applyPreset({noise_reduce:16, noise_floor:-32, deess_center:0.27, deess_strength:1.6, highpass:70, lowpass:16000, limiter:0.95});
    }
  });
}

document.addEventListener('DOMContentLoaded', ()=>{
  attachOverlay('clean-form');
  attachOverlay('separate-form');
  setupAjaxSubmit('clean-form');
  setupAjaxSubmit('separate-form');
  setupPresets();
  startVerseRotation();
  setupSettingsPanel();
  const closeBtn = document.querySelector('.overlay-close');
  if(closeBtn){ closeBtn.addEventListener('click', ()=>{ const ov=document.getElementById('overlay'); if(ov){ ov.hidden = true; } }); }
  const adviceBtn = document.getElementById('advice-btn');
  if(adviceBtn){
    adviceBtn.addEventListener('click', async ()=>{
      const ov = document.getElementById('overlay'); if(ov) ov.hidden=false;
      try{
        const fileInput = document.querySelector('input[name="files"]');
        const ctxSel = document.getElementById('context-select');
        const context = ctxSel ? ctxSel.value : 'clean';
        const fd = new FormData();
        if(fileInput && fileInput.files && fileInput.files[0]){
          fd.append('file', fileInput.files[0]);
        }
        fd.append('context', context);
        const resp = await fetch('/api/advice', { method:'POST', body: fd });
        const data = await resp.json();
        if(data && data.ok && data.params){
          applyPreset(data.params);
          alert(`Advice source: ${data.source}\n${data.notes||''}`);
        } else {
          alert('Advice failed.');
        }
      } catch(e){
        console.error(e); alert('Advice error.');
      } finally {
        if(ov) ov.hidden=true;
      }
    });
  }
});

// Rotate scripture verses endlessly in the banner
let verseQueue = [];
async function startVerseRotation(){
  const el = document.querySelector('.banner');
  const textEl = document.getElementById('verse-text');
  if(!el || !textEl) return;
  async function fetchConfig(){
    try{
      const r = await fetch('/ui-config.json', { cache: 'no-store' });
      const d = await r.json();
      const sec = (d && typeof d.verse_interval_sec === 'number') ? d.verse_interval_sec : 10;
      return Math.max(3, sec) * 1000;
    }catch{ return 10000; }
  }
  async function fetchVerses(){
    try{
      const resp = await fetch('/verses.json', { cache: 'no-store' });
      const data = await resp.json();
      const arr = (data && Array.isArray(data.verses)) ? data.verses : (data.verses ? Object.values(data.verses) : []);
      return arr.filter(v => typeof v === 'string' && v.trim().length > 0);
    }catch{
      return [];
    }
  }
  function shuffle(a){
    for(let i=a.length-1;i>0;i--){
      const j = Math.floor(Math.random()*(i+1));
      [a[i],a[j]]=[a[j],a[i]];
    }
    return a;
  }
  async function refillQueue(){
    const v = await fetchVerses();
    if(v.length === 0){
      verseQueue = [textEl.textContent || '“Let everything that has breath praise the LORD.” — Psalm 150:6'];
    } else {
      verseQueue = shuffle(v.slice());
    }
  }
  async function nextVerse(){
    if(verseQueue.length === 0){
      await refillQueue();
    }
    const n = verseQueue.shift();
    if(typeof n === 'string' && n.trim()){
      try{
        textEl.style.opacity = 0;
        setTimeout(()=>{ textEl.textContent = n; textEl.style.opacity = 1; }, 250);
      } catch { textEl.textContent = n; }
    }
  }
  await refillQueue();
  await nextVerse();
  const intervalMs = await fetchConfig();
  setInterval(nextVerse, intervalMs);
  // expose controls
  window.__ab = window.__ab || {};
  window.__ab.nextVerse = nextVerse;
  window.__ab.reloadVerses = async ()=>{ await refillQueue(); await nextVerse(); };
}

async function setupSettingsPanel(){
  try{
    const r = await fetch('/ui-config.json', { cache: 'no-store' });
    const d = await r.json();
    const sec = (d && typeof d.verse_interval_sec === 'number') ? d.verse_interval_sec : null;
    const span = document.getElementById('verse-interval');
    if(span && sec){ span.textContent = String(sec); }
  } catch {}
  const nextBtn = document.getElementById('next-verse-btn');
  if(nextBtn){ nextBtn.addEventListener('click', ()=>{ if(window.__ab && window.__ab.nextVerse){ window.__ab.nextVerse(); } }); }
  const reloadBtn = document.getElementById('reload-verses-btn');
  if(reloadBtn){ reloadBtn.addEventListener('click', async ()=>{ if(window.__ab && window.__ab.reloadVerses){ await window.__ab.reloadVerses(); } }); }
}

// Mini toast notification (bottom-left)
function showToast(msg, ms=3000){
  try{
    const t = document.getElementById('mini-toast');
    const span = document.getElementById('mini-toast-msg');
    if(!t || !span) return;
    span.textContent = String(msg);
    t.hidden = false;
    setTimeout(()=>{ t.hidden = true; }, ms);
  } catch{}
}

// Persist settings in localStorage
function loadSettings(){
  try{
    const raw = localStorage.getItem('AB_SETTINGS');
    if(!raw) return;
    const s = JSON.parse(raw);
    const fields = ['noise_reduce','noise_floor','deess_center','deess_strength','highpass','lowpass','limiter'];
    for(const f of fields){ const el = document.querySelector(`input[name="${f}"]`); if(el && s[f] != null){ el.value = s[f]; } }
    const ff = document.querySelector('input[name="fast_mode"]'); if(ff){ ff.checked = !!s.fast_mode; }
    const kf = document.querySelector('input[name="keep_float"]'); if(kf){ kf.checked = !!s.keep_float; }
    const ctx = document.getElementById('context-select'); if(ctx && s.context){ ctx.value = s.context; }
  } catch{}
}

function saveSettings(){
  try{
    const s = {};
    const fields = ['noise_reduce','noise_floor','deess_center','deess_strength','highpass','lowpass','limiter'];
    for(const f of fields){ const el = document.querySelector(`input[name="${f}"]`); if(el){ s[f] = el.value; } }
    const ff = document.querySelector('input[name="fast_mode"]'); if(ff){ s.fast_mode = !!ff.checked; }
    const kf = document.querySelector('input[name="keep_float"]'); if(kf){ s.keep_float = !!kf.checked; }
    const ctx = document.getElementById('context-select'); if(ctx){ s.context = ctx.value; }
    localStorage.setItem('AB_SETTINGS', JSON.stringify(s));
  } catch{}
}

document.addEventListener('DOMContentLoaded', ()=>{
  loadSettings();
  const sel = document.getElementById('context-select'); if(sel) sel.addEventListener('change', saveSettings);
  ['noise_reduce','noise_floor','deess_center','deess_strength','highpass','lowpass','limiter'].forEach(n=>{
    const el = document.querySelector(`input[name="${n}"]`); if(el) el.addEventListener('change', saveSettings);
  });
  const ff = document.querySelector('input[name="fast_mode"]'); if(ff) ff.addEventListener('change', saveSettings);
  const kf = document.querySelector('input[name="keep_float"]'); if(kf) kf.addEventListener('change', saveSettings);
});
