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

// Mobile menu: opening/closing never changes the current URL or page state.
const sidebar=document.getElementById('sidebar');
const menuToggle=document.querySelector('[data-menu-toggle]');
const menuBackdrop=document.querySelector('[data-menu-backdrop]');
function setMenu(open){
  if(!sidebar)return;
  sidebar.classList.toggle('open',open);
  document.body.classList.toggle('menu-open',open);
  if(menuToggle)menuToggle.setAttribute('aria-expanded',open?'true':'false');
  if(menuBackdrop)menuBackdrop.classList.toggle('open',open);
}
if(menuToggle){menuToggle.addEventListener('click',e=>{e.stopPropagation();setMenu(!sidebar?.classList.contains('open'));});}
if(menuBackdrop){menuBackdrop.addEventListener('click',()=>setMenu(false));}
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
