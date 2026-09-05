(()=>{
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const val=(v,s='')=>v===null||v===undefined||v===''?'—':`${v}${s}`;
const pct=v=>v===null||v===undefined?'—':`${v}%`;
const secLabel=s=>{if(s===null||s===undefined)return'—';const m=Math.floor(Number(s)/60),r=Math.round(Number(s)%60);return`${m}:${String(r).padStart(2,'0')}`};
const mini=(l,v)=>`<div class="aqpm-mini"><small>${esc(l)}</small><b>${esc(v)}</b></div>`;
const status=(ok,label)=>`<span class="aqpm-status ${ok?'ok':'missing'}">${esc(label)}</span>`;
function mediaCard(x){
 const imgs=(x.screenshot_urls||[]).slice(0,3).map((u,i)=>`<img loading="lazy" src="${esc(u)}" alt="${esc(x.title)} image ${i+1}">`).join('');
 let media='';
 if(x.clip_url)media=`<video controls preload="metadata" src="${esc(x.clip_url)}"></video>`;
 else if(x.segment_embed)media=`<iframe loading="lazy" src="${esc(x.segment_embed)}" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>`;
 else if(imgs)media=imgs;
 if(!media)return'';
 return `<article class="aqpm-media-card">${media}<div class="aqpm-media-copy"><b>${esc(x.title||'Séquence')}</b><small>${secLabel(x.second)} · ${esc(x.kind||'preuve')}</small></div></article>`;
}
function playerCard(p){
 const ph=p.physical||{};
 const media=(p.media||[]).map(mediaCard).join('');
 const cov=p.coverage_groups||{};
 return `<details class="aqpm-player"><summary><span><b>#${esc(p.cap??'—')} · ${esc(p.name)}</b><br><small>${esc(p.role||'poste à confirmer')} · ${esc(p.event_count||0)} événements attribués</small></span><span>${status(p.coverage_score>=50,`${p.coverage_score}% couvert`)}</span></summary><div class="aqpm-player-body">
 <div class="aqpm-coverage"><i style="width:${Math.max(0,Math.min(100,p.coverage_score||0))}%"></i></div>
 <div class="aqpm-metric-grid">
 ${mini('Temps de jeu',val(p.playing_time_min,' min'))}${mini('Ballons touchés',p.touches||0)}${mini('Touches centre',p.centre_touches||0)}
 ${mini('Passes réussies',p.passes_completed||0)}${mini('Passes ratées',p.passes_failed||0)}${mini('% passes',pct(p.pass_completion_pct))}
 ${mini('Buts / tirs',`${p.goals||0}/${p.shots||0}`)}${mini('Cadrage',pct(p.shot_accuracy_pct))}${mini('Efficacité tir',pct(p.scoring_efficiency_pct))}
 ${mini('Duels G/P',`${p.duels_won||0}/${p.duels_lost||0}`)}${mini('% duels gagnés',pct(p.duel_success_pct))}${mini('Pertes',p.turnovers||0)}
 ${mini('Interceptions',p.interceptions||0)}${mini('Récupérations',p.recoveries||0)}${mini('Blocs',p.blocks||0)}
 ${mini('Exclusions provoquées',p.exclusions_earned||0)}${mini('Exclusions concédées',p.exclusions_committed||0)}${mini('Passes clés',p.key_passes||0)}
 ${mini('Assists',p.assists||0)}${mini('Actions créées',p.actions_created||0)}${mini('Actions ballon/min',val(p.ball_actions_per_min))}
 ${mini('Distance parcourue',val(ph.distance_m,' m'))}${mini('Vitesse nage max',val(ph.max_swim_speed_mps,' m/s'))}${mini('Sprint 10 m',val(ph.sprint_10m_s_best,' s'))}
 ${mini('Vitesse tir moy.',val(ph.shot_speed_kmh_avg,' km/h'))}${mini('Distance tir moy.',val(ph.shot_distance_m_avg,' m'))}${mini('Release moyen',val(ph.release_time_s_avg,' s'))}
 </div>
 <div class="aqpm-truth"><b>Qualité de mesure.</b> Temps de jeu, distance et vitesses restent « — » sans tag/calibration explicite. Les touches sont uniquement les événements <code>touch</code>/<code>centre_touch</code> attribués à cette joueuse.</div>
 ${media?`<div><b>Preuves vidéo / images liées à la joueuse</b><div class="aqpm-media">${media}</div></div>`:'<div class="aqpm-truth">Aucune séquence média n’est encore directement attribuée à cette joueuse.</div>'}
 </div></details>`;
}
function teamSequence(x){return mediaCard(x)}
async function render(){
 const m=location.pathname.match(/^\/matches\/(\d+)\/analysis\/result\/?$/);if(!m)return;
 const anchor=document.querySelector('.result-shell');if(!anchor||document.getElementById('aq-player-matrix'))return;
 try{
  const r=await fetch(`/api/v122/matches/${m[1]}/player-metrics`,{credentials:'same-origin'});if(!r.ok)return;
  const d=await r.json(),t=d.totals||{},a=d.attribution||{},media=d.media||{};
  const rows=(d.players||[]).map(p=>`<tr><td>#${esc(p.cap??'—')}</td><td><b>${esc(p.name)}</b><br><small>${esc(p.role||'')}</small></td><td>${val(p.playing_time_min,' min')}</td><td>${p.touches||0}</td><td>${p.centre_touches||0}</td><td>${p.passes_completed||0}/${p.pass_attempts||0}</td><td>${pct(p.pass_completion_pct)}</td><td>${p.goals||0}/${p.shots||0}</td><td>${pct(p.shot_accuracy_pct)}</td><td>${p.duels_won||0}/${p.duels||0}</td><td>${pct(p.duel_success_pct)}</td><td>${p.turnovers||0}</td><td>${p.interceptions||0}</td><td>${p.exclusions_earned||0}</td><td>${val(p.physical?.distance_m,' m')}</td><td>${val(p.physical?.max_swim_speed_mps,' m/s')}</td><td>${p.coverage_score}%</td></tr>`).join('');
  const sequences=(d.sequences||[]).map(teamSequence).filter(Boolean);
  const visible=sequences.slice(0,24).join(''),more=sequences.slice(24).join('');
  const panel=document.createElement('section');panel.id='aq-player-matrix';panel.className='aq-section';panel.innerHTML=`
   <div class="aqpm-head"><div><span class="aq-eyebrow">PLAYER PERFORMANCE MATRIX · V12.2</span><h2>Toutes les joueuses · toutes les mesures attribuées</h2><p class="aq-subtle">Temps de jeu, touches, passes, tirs, duels, pertes, création, défense, distance/vitesse calibrées et preuves vidéo. Aucun dénominateur absent n’est transformé en pourcentage.</p></div><div>${status((a.assigned_pct||0)>=70,`Attribution ${pct(a.assigned_pct)}`)}</div></div>
   <div class="aqpm-summary">
    ${mini('Événements attribués',`${a.events_assigned||0}/${a.events_total||0}`)}${mini('Ballons touchés',t.touches||0)}${mini('Passes réussies',t.passes_completed||0)}${mini('% passes',pct(t.pass_completion_pct))}${mini('Buts / tirs',`${t.goals||0}/${t.shots||0}`)}${mini('% cadrage',pct(t.shot_accuracy_pct))}${mini('Duels gagnés',`${t.duels_won||0}/${t.duels||0}`)}${mini('Pertes',t.turnovers||0)}${mini('Temps de jeu renseigné',`${t.players_with_playing_time||0}/${(d.players||[]).length}`)}${mini('Distance renseignée',`${t.players_with_distance||0}/${(d.players||[]).length}`)}${mini('Séquences',media.total||0)}${mini('Clips / images',`${media.downloadable_clips||0} / ${media.with_images||0}`)}
   </div>
   <div class="aqpm-table-wrap"><table class="aqpm-table"><thead><tr><th>#</th><th>Joueuse</th><th>Temps</th><th>Touches</th><th>Centre</th><th>Passes</th><th>% passe</th><th>Buts/Tirs</th><th>% cadrage</th><th>Duels G/T</th><th>% duel</th><th>Pertes</th><th>Interceptions</th><th>Excl. +</th><th>Distance</th><th>Vmax</th><th>Couverture</th></tr></thead><tbody>${rows||'<tr><td colspan="17">Aucune joueuse dans l’effectif.</td></tr>'}</tbody></table></div>
   <div class="aqpm-player-grid">${(d.players||[]).map(playerCard).join('')}</div>
   <div class="aq-section-head" style="margin-top:20px"><div><span class="aq-eyebrow">EVIDENCE ROOM</span><h2>Jusqu’à 72 séquences vidéo / image</h2></div><p>${media.downloadable_clips||0} clips locaux · ${media.with_images||0} séquences avec images · ${media.external_segments||0} segments externes.</p></div>
   <div class="aqpm-media">${visible||'<div class="aqpm-truth">Aucune preuve média matérialisée pour le moment.</div>'}</div>
   ${more?`<details style="margin-top:12px"><summary class="btn secondary">Afficher les autres séquences (${sequences.length-24})</summary><div class="aqpm-media" style="margin-top:12px">${more}</div></details>`:''}
   <div class="aqpm-truth" style="margin-top:14px"><b>Règle scientifique V12.2.</b> Distance, temps de jeu, vitesse de nage, vitesse de tir et temps de release ne deviennent des valeurs que lorsqu’une mesure ou calibration explicite existe. Les signaux de mouvement vidéo seuls ne sont jamais convertis en mètres ou km/h.</div>`;
  const hero=anchor.querySelector('.result-hero');
  const brief=document.getElementById('aq-premium-brief');
  (brief||hero)?.insertAdjacentElement('afterend',panel);
  const nav=document.getElementById('aq-result-nav');if(nav){const n=document.createElement('a');n.href='#aq-player-matrix';n.textContent='Joueuses & métriques';nav.insertBefore(n,nav.children[1]||null)}
 }catch(e){console.warn('AquaMetric player matrix unavailable',e)}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',render);else render();
})();