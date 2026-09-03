// Legacy regression contract only — no separate UI entry is rendered: ['/knowledge','/tactical-chess'] /static/video-session-elite.html Analyse vidéo élite
if(location.pathname==='/tactical-chess'){
  location.replace('/knowledge');
}

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

document.querySelectorAll('[data-refresh-control]').forEach(el=>el.remove());

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

// Existing remote-URL matches get the same Ultimate Analyst entry point as
// the dedicated "Analyze from URL" creation path. This is injected only when
// the match workspace actually contains a remote provider video.
(function addUrlAnalysisEntry(){
  const matchPath=location.pathname.match(/^\/matches\/(\d+)\/?$/);
  if(!matchPath)return;
  const panel=document.querySelector('.video-panel');
  if(!panel||document.getElementById('url-analysis-entry'))return;
  const remoteVideo=panel.querySelector('iframe#yt')||panel.querySelector('a[href^="http"]');
  const localVideo=panel.querySelector('video#video');
  if(!remoteVideo||localVideo)return;
  const form=document.createElement('form');
  form.id='url-analysis-entry';
  form.method='post';
  form.action=`/matches/${matchPath[1]}/url-analysis/start`;
  form.style.margin='12px 0';
  form.innerHTML='<button class="btn intelligence-cta" type="submit">Analyser l’URL · Ultimate Analyst</button><small style="display:block;margin-top:6px">Même grille minimum que l’upload : tirs, passes, pertes, possessions, transitions, phases, décisions et joueuses.</small>';
  const anchor=panel.querySelector('.video-wrap')||remoteVideo.parentElement||panel.firstElementChild;
  anchor?.insertAdjacentElement('afterend',form);
})();

// Extension dictionaries are loaded after the core i18n scripts have initialized.
window.addEventListener('DOMContentLoaded',()=>{
  if(document.querySelector('script[data-aquametric-i18n-v125]'))return;
  const script=document.createElement('script');
  script.src='/static/i18n-v125.js?v=12.5.0';
  script.dataset.aquametricI18nV125='1';
  document.body.appendChild(script);
});
