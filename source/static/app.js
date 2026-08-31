function seekMatchVideo(seconds){
  const localVideo=document.getElementById('video');
  if(localVideo){localVideo.currentTime=seconds;localVideo.play().catch(()=>{});return;}
  const youtube=document.getElementById('yt');
  if(youtube && youtube.contentWindow){
    youtube.contentWindow.postMessage(JSON.stringify({event:'command',func:'seekTo',args:[seconds,true]}),'*');
    youtube.contentWindow.postMessage(JSON.stringify({event:'command',func:'playVideo',args:[]}),'*');
  }
}
document.querySelectorAll('.timeline').forEach(btn=>btn.addEventListener('click',()=>{const sec=parseFloat(btn.dataset.second||0);seekMatchVideo(sec);const evidenceSecond=document.getElementById('evidence-second');if(evidenceSecond)evidenceSecond.value=sec;const evidenceEvent=document.getElementById('evidence-event');if(evidenceEvent&&btn.dataset.eventId)evidenceEvent.value=btn.dataset.eventId;}));
const hashMatch=location.hash.match(/^#t=(\d+(?:\.\d+)?)$/);if(hashMatch){setTimeout(()=>seekMatchVideo(parseFloat(hashMatch[1])),400);}

// V12.1 mobile navigation. Opening/closing never changes the URL or page state.
const sidebar=document.getElementById('sidebar');
const menuToggle=document.querySelector('[data-menu-toggle]');
const menuBackdrop=document.querySelector('[data-menu-backdrop]');
const menuClose=document.querySelector('[data-menu-close]');
function setMenu(open){
  if(!sidebar)return;
  const shouldOpen=!!open;
  sidebar.classList.toggle('open',shouldOpen);
  sidebar.setAttribute('aria-hidden',shouldOpen?'false':'true');
  document.body.classList.toggle('menu-open',shouldOpen);
  if(menuToggle)menuToggle.setAttribute('aria-expanded',shouldOpen?'true':'false');
  if(menuBackdrop)menuBackdrop.classList.toggle('open',shouldOpen);
}
function toggleMenu(e){if(e){e.preventDefault();e.stopPropagation();}setMenu(!sidebar?.classList.contains('open'));}
// Use one activation event only. iOS synthesizes click after touch; registering both caused an immediate open/close double toggle.
if(menuToggle)menuToggle.addEventListener('click',toggleMenu,{passive:false});
if(menuClose)menuClose.addEventListener('click',()=>setMenu(false));
if(menuBackdrop)menuBackdrop.addEventListener('click',()=>setMenu(false));
document.addEventListener('pointerdown',e=>{
  if(!sidebar?.classList.contains('open'))return;
  if(sidebar.contains(e.target)||menuToggle?.contains(e.target))return;
  setMenu(false);
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')setMenu(false);});
window.addEventListener('resize',()=>{if(window.innerWidth>900)setMenu(false);});
document.querySelectorAll('.side-nav a').forEach(a=>a.addEventListener('click',()=>setMenu(false)));

// Lightweight tab system used by team and match intelligence pages.
document.querySelectorAll('[data-tabs]').forEach(group => {
  const buttons = group.querySelectorAll('[data-tab]');
  const scope = group.parentElement || document;
  buttons.forEach(btn => btn.addEventListener('click', () => {
    buttons.forEach(x => x.classList.remove('active'));
    scope.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
    btn.classList.add('active');
    const panel = scope.querySelector(`[data-panel="${btn.dataset.tab}"]`);
    if (panel) panel.classList.add('active');
  }));
});

// Remove legacy manual refresh controls. Pages display their current cached/automatic data immediately.
document.querySelectorAll('[data-refresh-control]').forEach(el=>el.remove());

// Native touch scrolling + mouse/pen drag for wide tables, ribbons and tab bars.
const dragSelectors='.table-wrap,.transfer-table,.roster-table,.coverage-table,.metric-ribbon,.factor-table,.section-tabs,[data-drag-scroll]';
document.querySelectorAll(dragSelectors).forEach(el=>{
  el.classList.add('drag-scroll');
  let active=false,startX=0,startScroll=0;
  el.addEventListener('pointerdown',e=>{
    if(e.pointerType==='touch'||e.button!==0||el.scrollWidth<=el.clientWidth)return;
    active=true;startX=e.clientX;startScroll=el.scrollLeft;el.classList.add('dragging');el.setPointerCapture?.(e.pointerId);
  });
  el.addEventListener('pointermove',e=>{if(active){el.scrollLeft=startScroll-(e.clientX-startX);e.preventDefault();}});
  const end=e=>{if(!active)return;active=false;el.classList.remove('dragging');try{el.releasePointerCapture?.(e.pointerId);}catch(_){}};
  el.addEventListener('pointerup',end);el.addEventListener('pointercancel',end);el.addEventListener('lostpointercapture',()=>{active=false;el.classList.remove('dragging');});
});

// Premium video-analysis entry point: keep it visible where coaches are most likely to look for tactics.
if(['/knowledge','/tactical-chess'].includes(location.pathname)){
  const elite=document.createElement('a');
  elite.href='/static/video-session-elite.html';
  elite.className='elite-video-quick-access';
  elite.innerHTML='<span aria-hidden="true">▶</span><strong>Analyse vidéo élite</strong><small>matchs + schémas + lecture</small>';
  elite.setAttribute('aria-label','Ouvrir Analyse vidéo élite');
  Object.assign(elite.style,{position:'fixed',right:'18px',bottom:'18px',zIndex:'9999',display:'grid',gridTemplateColumns:'32px auto',columnGap:'10px',alignItems:'center',padding:'12px 16px',borderRadius:'16px',border:'1px solid rgba(99,210,237,.55)',background:'rgba(5,24,34,.96)',boxShadow:'0 14px 42px rgba(0,0,0,.35)',color:'#e8faff',textDecoration:'none',backdropFilter:'blur(12px)',maxWidth:'260px'});
  elite.querySelector('span').style.cssText='grid-row:1/3;width:32px;height:32px;display:grid;place-items:center;border-radius:50%;background:#39c6e6;color:#04202a;font-size:14px';
  elite.querySelector('strong').style.cssText='font-size:14px;line-height:1.15';
  elite.querySelector('small').style.cssText='font-size:11px;color:#9ec8d3;line-height:1.2;margin-top:3px';
  document.body.appendChild(elite);
}
