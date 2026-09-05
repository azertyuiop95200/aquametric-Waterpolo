(()=>{
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const rows=x=>Array.isArray(x)?x:[];
const table=(heads,body,empty='Aucune mesure automatique disponible.')=>body.length?`<div class="aqm-table-wrap"><table class="aqm-table"><thead><tr>${heads.map(x=>`<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${body.join('')}</tbody></table></div>`:`<div class="aqm-empty">${esc(empty)}</div>`;
const kpi=(label,value,detail='')=>`<div class="aqm-kpi"><small>${esc(label)}</small><strong>${esc(value)}</strong><em>mesure automatique</em>${detail?`<span>${esc(detail)}</span>`:''}</div>`;
function matrix(data){
 const body=rows(data.measurement_matrix).map(r=>`<tr><td><b>${esc(r.family)}</b></td><td><span class="aqm-chip">${esc(r.status)}</span></td><td>${esc(r.source)}</td><td>${esc(r.detail)}</td></tr>`);
 return `<div class="aqm-panel" id="aqm-measurement-matrix"><div class="aqm-section-head"><div><h3>Matrice de mesure — ce qui est réellement disponible</h3><p>Chaque famille est explicitement classée : AUTO, CANDIDAT AUTO, TAGUÉ, CALIBRÉ ou NON MESURÉ.</p></div></div>${table(['Famille','Statut','Source','Couverture / détail'],body)}</div>`;
}
function vision(v){
 if(!v)return `<div class="aqm-panel"><h3>Mesures automatiques vidéo</h3><div class="aqm-note warn"><b>Aucun scan Vision disponible</b><div>La vidéo locale ou l’URL vidéo accessible doit d’abord passer par l’analyse Vision/OCR.</div></div></div>`;
 return `<div class="aqm-panel" id="aqm-auto-video"><h3>Mesures automatiques réellement extraites de la vidéo</h3><p>Ces valeurs viennent des images effectivement décodées par le moteur Vision. Elles restent distinctes des statistiques joueuses validées.</p><div class="aqm-kpis">${kpi('Durée analysée',`${v.duration_minutes} min`,`${v.duration_seconds} s réellement lus`)}${kpi('Cadence vidéo',`${v.fps} fps`,`${v.width}×${v.height}`)}${kpi('Images analysées',v.sample_count,`intervalle ≈ ${v.sample_interval_seconds} s`)}${kpi('Type vidéo',v.video_type,`confiance ${v.confidence}`)}${kpi('Activité estimée',`${v.active_minutes_estimate} min`,`${v.active_windows_count} fenêtres actives`)}${kpi('Motion moyenne',v.avg_motion_score,'score visuel relatif')}${kpi('Présence bassin',v.avg_pool_ratio,'ratio visuel moyen')}${kpi('Coupes scène',v.scene_cut_rate,'taux relatif')}${kpi('Moments intéressants',v.interesting_moments_count,'candidats visuels')}${kpi('Zones scoreboard',v.scoreboard_roi_candidates,'candidats ROI')}</div></div>`;
}
function autonomy(a){
 if(!a)return `<div class="aqm-panel"><h3>OCR, périodes et événements candidats</h3><div class="aqm-note warn"><b>Analyse autonome non disponible</b><div>Aucune observation scoreboard/OCR n’a encore été enregistrée pour ce match.</div></div></div>`;
 const counts=Object.entries(a.candidate_counts||{}).map(([type,n])=>`<tr><td>${esc(type)}</td><td>${esc(n)}</td></tr>`);
 const periods=rows(a.periods).map((p,i)=>`<tr><td>${esc(p.period||p.label||i+1)}</td><td>${esc(p.start_second??p.start??'—')}</td><td>${esc(p.end_second??p.end??'—')}</td><td>${esc(p.confidence||p.status||'inféré')}</td></tr>`);
 const score=rows(a.score_change_candidates).map(c=>`<tr><td>${esc(c.second)} s</td><td>${esc(c.type)}</td><td>${esc(c.confidence)} (${esc(c.confidence_score)})</td><td>${esc(c.summary)}</td></tr>`);
 const whistles=rows(a.whistle_candidates).map(c=>`<tr><td>${esc(c.second)} s</td><td>${esc(c.confidence)} (${esc(c.confidence_score)})</td><td>${esc(c.summary)}</td></tr>`);
 const observedPeriods=rows(a.periods).map(p=>p.period).filter(Boolean);
 const format=observedPeriods.length?`${observedPeriods.length} période${observedPeriods.length>1?'s':''} observée${observedPeriods.length>1?'s':''} (${observedPeriods.map(p=>`P${p}`).join(', ')})`:'format non déterminé';
 return `<div class="aqm-panel" id="aqm-auto-ocr"><h3>OCR, périodes, score et audio — sorties automatiques</h3><div class="aqm-note"><b>Format vidéo observé : ${esc(format)}</b><div>Une rencontre amicale en 3 périodes reste en 3 périodes : AquaMetric n’ajoute jamais artificiellement une quatrième période.</div></div><div class="aqm-kpis" style="margin-top:12px">${kpi('Observations scoreboard',a.scoreboard_observations,`OCR ${a.ocr_available?'disponible':'indisponible'}`)}${kpi('Périodes inférées',a.period_count,a.engine)}${kpi('Événements candidats',a.candidate_count,'non promus en stats joueuse sans validation')}${kpi('Variations score',rows(a.score_change_candidates).length,'fenêtres candidates')}${kpi('Sifflets candidats',rows(a.whistle_candidates).length,'analyse audio')}</div><div class="aqm-grid-2" style="margin-top:12px"><div><h4>Types de candidats</h4>${table(['Type','Nombre'],counts)}</div><div><h4>Périodes inférées</h4>${table(['Période','Début','Fin','Confiance'],periods)}</div></div><h4>Fenêtres de variation de score</h4>${table(['Temps','Type','Confiance','Preuve'],score,'Aucune variation de score candidate détectée.')}${whistles.length?`<h4>Sifflets candidats</h4>${table(['Temps','Confiance','Signal'],whistles)}`:''}</div>`;
}
function jobs(items){
 const body=rows(items).map(j=>`<tr><td>${esc(j.stage)}</td><td>${esc(j.status)}</td><td>${esc(j.progress)}%</td><td>${esc(j.message)}</td></tr>`);
 return `<div class="aqm-panel"><h3>Pipeline d’analyse exécuté</h3>${table(['Étape','Statut','Progression','Message'],body,'Aucun job d’analyse enregistré.')}</div>`;
}
function maskFalseZerosWhenNothingVerified(eventCount){
 if(Number(eventCount||0)>0)return;
 const labels=new Set(['Couverture','Buts','Tirs','Passes','Pertes','Décisions taguées']);
 const apply=()=>{
  const panel=document.getElementById('aq-premium-brief');
  if(!panel)return false;
  panel.querySelectorAll('.aq-kpi').forEach(card=>{
   const label=(card.querySelector('span')?.textContent||'').trim();
   if(!labels.has(label))return;
   const value=card.querySelector('b');if(value)value.textContent='—';
   let detail=card.querySelector('small');
   if(!detail){detail=document.createElement('small');card.appendChild(detail)}
   detail.textContent='non mesuré · aucune action vérifiée';
   card.title='Aucune action validée : zéro ne signifie pas zéro sportif.';
  });
  return true;
 };
 if(apply())return;
 const observer=new MutationObserver(()=>{if(apply())observer.disconnect()});
 observer.observe(document.documentElement,{childList:true,subtree:true});
 setTimeout(()=>observer.disconnect(),10000);
}
function installElapsedTimer(){
 const selector='form[action="/analysis/url/create"], form[action$="/analysis/start"], form[action$="/url-analysis/start"]';
 document.querySelectorAll(selector).forEach(form=>{
  if(form.dataset.aqTimerInstalled==='1')return;
  form.dataset.aqTimerInstalled='1';
  form.addEventListener('submit',()=>{
   const button=form.querySelector('button[type="submit"],input[type="submit"]');
   if(!button)return;
   button.disabled=true;
   const started=Date.now();
   const render=()=>{
    const elapsed=Math.max(0,Math.floor((Date.now()-started)/1000));
    const mm=String(Math.floor(elapsed/60)).padStart(2,'0');
    const ss=String(elapsed%60).padStart(2,'0');
    const label=`Analyse vidéo en cours · ${mm}:${ss}`;
    if(button.tagName==='INPUT')button.value=label;else button.textContent=label;
   };
   render();
   const timer=setInterval(render,1000);
   window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
  });
 });
}
async function init(){
 installElapsedTimer();
 const m=location.pathname.match(/^\/matches\/(\d+)\/analysis\/result\/?$/);if(!m)return;
 try{
  const r=await fetch(`/api/matches/${m[1]}/performance`,{credentials:'same-origin'});if(!r.ok)return;const d=await r.json();
  maskFalseZerosWhenNothingVerified(d.ultimate?.team?.coverage?.event_count);
  let host=document.getElementById('aq-measured-analysis');
  for(let i=0;i<30&&!host;i++){await new Promise(res=>setTimeout(res,100));host=document.getElementById('aq-measured-analysis');}
  if(!host||document.getElementById('aqm-measurement-matrix'))return;
  const auto=d.automatic_analysis||{};
  const fragment=document.createElement('div');fragment.className='aqm-shell';fragment.innerHTML=matrix(d)+vision(auto.vision)+autonomy(auto.autonomy)+jobs(auto.jobs);
  const firstPanel=host.querySelector('.aqm-panel');
  if(firstPanel)firstPanel.insertAdjacentElement('beforebegin',fragment);else host.appendChild(fragment);
 }catch(_e){}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();