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

const menuToggle=document.querySelector('[data-menu-toggle]');
if(menuToggle){menuToggle.addEventListener('click',()=>document.getElementById('sidebar')?.classList.toggle('open'));}
document.querySelectorAll('.side-nav a').forEach(a=>a.addEventListener('click',()=>document.getElementById('sidebar')?.classList.remove('open')));


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
