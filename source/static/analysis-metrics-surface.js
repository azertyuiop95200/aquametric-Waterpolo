(()=>{
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=v=>v==null?'—':`${v}%`;
const val=(v,suffix='')=>v==null?'—':`${v}${suffix}`;
const safeRows=x=>Array.isArray(x)?x:[];
const table=(heads,rows,empty='Aucune donnée mesurée pour ce bloc.')=>rows.length?`<div class="aqm-table-wrap"><table class="aqm-table"><thead><tr>${heads.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`:`<div class="aqm-empty">${esc(empty)}</div>`;
const kpi=(label,value,source='événements validés',detail='')=>`<div class="aqm-kpi"><small>${esc(label)}</small><strong>${esc(value)}</strong><em>${esc(source)}</em>${detail?`<span>${esc(detail)}</span>`:''}</div>`;
const metricValue=(board,key,kind='num')=>{
  const v=board?.[key];
  if(kind==='pct') return pct(v);
  return v==null?'—':v;
};
function injectStyles(){
 if(document.getElementById('aqm-styles'))return;
 const s=document.createElement('style');s.id='aqm-styles';s.textContent=`
 #aq-measured-analysis{scroll-margin-top:20px}.aqm-shell{display:grid;gap:16px}.aqm-hero,.aqm-panel{border:1px solid rgba(99,210,237,.22);border-radius:20px;background:linear-gradient(145deg,rgba(8,30,41,.98),rgba(4,20,29,.98));padding:18px}.aqm-hero{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.aqm-hero h2,.aqm-panel h3{margin:.25rem 0 .5rem}.aqm-hero p,.aqm-panel p{opacity:.8}.aqm-badges{display:flex;gap:8px;flex-wrap:wrap}.aqm-badge{min-width:105px;padding:10px 12px;border:1px solid rgba(255,255,255,.1);border-radius:14px;background:rgba(255,255,255,.035)}.aqm-badge b,.aqm-badge small{display:block}.aqm-badge b{font-size:20px}.aqm-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:9px}.aqm-kpi{padding:12px;border:1px solid rgba(255,255,255,.085);border-radius:14px;background:rgba(255,255,255,.025);min-height:92px}.aqm-kpi small,.aqm-kpi em,.aqm-kpi span{display:block}.aqm-kpi strong{display:block;font-size:22px;margin:4px 0}.aqm-kpi em{font-style:normal;font-size:11px;opacity:.62}.aqm-kpi span{font-size:11px;opacity:.7;margin-top:4px}.aqm-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:12px}.aqm-table-wrap{overflow:auto;border:1px solid rgba(255,255,255,.07);border-radius:14px}.aqm-table{width:100%;border-collapse:collapse;min-width:620px}.aqm-table th,.aqm-table td{padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.07);text-align:left;vertical-align:top}.aqm-table th{font-size:12px;opacity:.72}.aqm-table td{font-size:13px}.aqm-empty{padding:12px;border:1px dashed rgba(255,255,255,.18);border-radius:12px;opacity:.7}.aqm-section-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px}.aqm-section-head small{opacity:.65}.aqm-loss{display:grid;grid-template-columns:minmax(130px,1.2fr) 70px 70px;gap:8px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.07)}.aqm-loss b:last-child{text-align:right}.aqm-player{border:1px solid rgba(255,255,255,.1);border-radius:16px;background:rgba(255,255,255,.025);overflow:hidden}.aqm-player summary{cursor:pointer;list-style:none;padding:14px;display:flex;justify-content:space-between;gap:10px;align-items:center}.aqm-player summary::-webkit-details-marker{display:none}.aqm-player[open] summary{border-bottom:1px solid rgba(255,255,255,.08)}.aqm-player-body{padding:14px;display:grid;gap:12px}.aqm-player-list{display:grid;gap:9px}.aqm-note{padding:11px 12px;border-left:3px solid #63d2ed;background:rgba(99,210,237,.06);border-radius:0 10px 10px 0}.aqm-note.warn{border-color:#fb923c;background:rgba(251,146,60,.07)}.aqm-chip{display:inline-block;padding:4px 8px;border:1px solid rgba(99,210,237,.25);border-radius:999px;font-size:11px}.aqm-nav{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.aqm-nav a{font-size:12px;text-decoration:none;padding:6px 9px;border-radius:999px;border:1px solid rgba(99,210,237,.25)}.aqm-policy{display:grid;gap:7px}.aqm-policy div{padding:9px 10px;border-radius:10px;background:rgba(255,255,255,.025)}
 @media(max-width:820px){.aqm-grid-2,.aqm-hero{grid-template-columns:1fr;display:grid}.aqm-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.aqm-player summary{align-items:flex-start;flex-direction:column}.aqm-table{min-width:560px}}@media(max-width:480px){.aqm-kpis{grid-template-columns:1fr 1fr}.aqm-kpi{min-height:84px}.aqm-kpi strong{font-size:19px}}
 `;document.head.appendChild(s);
}
function fullTeamKpis(s={}){
 const passAttempts=s.pass_attempts_tagged||0;
 const shotN=s.shots||0;
 return [
  ['Buts',s.goals,'événements validés'],['Tirs tagués',shotN,'échantillon tagué'],['Cadrés',s.shots_on_target,'échantillon tagué'],['Non cadrés',s.shots_off_target,'échantillon tagué'],['Bloqués',s.shots_blocked,'échantillon tagué'],
  ['Précision tir',shotN?pct(s.shot_accuracy_pct):'—','calculé avec dénominateur'],['Efficacité but',shotN?pct(s.scoring_efficiency_pct):'—','calculé avec dénominateur'],
  ['Passes tentées',passAttempts||'—','passes taguées'],['Passes réussies',passAttempts?s.passes_completed:'—','passes taguées'],['Passes ratées',passAttempts?s.passes_failed:'—','passes taguées'],['Réussite passe',passAttempts?pct(s.pass_completion_pct):'—','calculé avec dénominateur'],
  ['Pertes',s.turnovers,'événements validés'],['Pertes / 100 passes',passAttempts?val(s.turnovers_per_100_tagged_passes):'—','calculé sur passes taguées'],['Assists',s.assists,'événements validés'],['Passes clés',s.key_passes,'événements validés'],['Actions créées',s.actions_created,'événements validés'],
  ['Exclusions provoquées',s.exclusions_earned,'événements validés'],['Exclusions concédées',s.exclusions_committed,'événements validés'],['Interceptions',s.interceptions,'événements validés'],['Récupérations',s.recoveries,'événements validés'],['Blocs',s.blocks,'événements validés'],['Arrêts',s.saves,'événements validés'],['Duels gagnés',s.duels_won,'événements validés'],['Duels perdus',s.duels_lost,'événements validés']
 ].map(([a,b,c])=>kpi(a,b,c)).join('');
}
const measuredLabels={
 sprint_5m_s:['Sprint 5 m',' s'],sprint_10m_s:['Sprint 10 m',' s'],max_swim_speed_mps:['Vitesse nage max',' m/s'],shot_speed_kmh:['Vitesse de tir',' km/h'],release_time_s:['Temps de release',' s']
};
function measuredPhysical(measured={}){
 return Object.entries(measuredLabels).map(([key,[label,unit]])=>{
  const m=measured[key]||{};const avg=m.avg==null?'—':`${m.avg}${unit}`;const detail=m.samples?`max ${m.max}${unit} · ${m.samples} mesure(s)`:'aucune mesure calibrée';return kpi(label,avg,'mesuré / calibré',detail);
 }).join('');
}
function dims(report={}){
 const rows=safeRows(report.dimensions).map(d=>`<tr><td>${esc(d.label)}</td><td>${d.available?`${esc(d.score)}/100`:'—'}</td><td>${esc(d.evidence||'')}</td></tr>`);
 return table(['Dimension','Score','Preuve / dénominateur'],rows,'Aucune dimension suffisamment couverte.');
}
function counterTable(rows,label='Contexte'){
 return table([label,'Nombre','Part'],safeRows(rows).map(x=>`<tr><td>${esc(x.label||x.key)}</td><td>${esc(x.count)}</td><td>${pct(x.share)}</td></tr>`));
}
function renderLosses(uLoss={},simpleLoss={}){
 const reasons=safeRows(uLoss.reasons).length?uLoss.reasons:safeRows(simpleLoss.rows);
 return `<div class="aqm-grid-2"><div>${table(['Cause','Nombre','Part des pertes'],reasons.map(x=>`<tr><td>${esc(x.label)}</td><td>${esc(x.count)}</td><td>${pct(x.share)}</td></tr>`),'Aucune perte classée.')}</div><div>${counterTable(uLoss.zones,'Zone')}</div><div>${counterTable(uLoss.phases,'Phase')}</div><div>${counterTable(uLoss.pressures,'Pression')}</div><div>${counterTable(uLoss.decisions,'Décision')}</div></div>`;
}
function shotTables(shots={}){
 const row=x=>`<tr><td>${esc(x.label||x.key)}</td><td>${esc(x.shots)}</td><td>${esc(x.on_target)}</td><td>${pct(x.accuracy_pct)}</td><td>${esc(x.goals)}/${esc(x.shots)}</td><td>${pct(x.efficiency_pct)}</td></tr>`;
 return `<div class="aqm-kpis">${kpi('Tirs localisés',shots.total?pct(shots.located_pct):'—','zone tag')}${kpi('Distance moyenne',val(shots.distance_m_avg,' m'),'mesuré / tagué')}${kpi('Vitesse tir moyenne',val(shots.shot_speed_kmh_avg,' km/h'),'calibré',`${shots.calibrated_speed_samples||0} mesure(s)`)}${kpi('Vitesse tir max',val(shots.shot_speed_kmh_max,' km/h'),'calibré')}${kpi('Release moyen',val(shots.release_time_s_avg,' s'),'calibré',`${shots.release_samples||0} mesure(s)`)}</div><div class="aqm-grid-2" style="margin-top:10px"><div>${table(['Zone','Tirs','Cadrés','% cadrés','Buts','% efficacité'],safeRows(shots.zones).map(row),'Zones de tir non taguées.')}</div><div>${table(['Type de tir','Tirs','Cadrés','% cadrés','Buts','% efficacité'],safeRows(shots.types).map(row),'Types de tir non tagués.')}</div><div>${table(['Main','Tirs','Cadrés','% cadrés','Buts','% efficacité'],safeRows(shots.hands).map(row),'Main de tir non taguée.')}</div></div>`;
}
function passTables(passes={}){
 const row=x=>`<tr><td>${esc(x.label||x.key)}</td><td>${esc(x.completed)}/${esc(x.attempts)}</td><td>${esc(x.failed)}</td><td>${pct(x.completion_pct)}</td></tr>`;
 return `<div class="aqm-kpis">${kpi('Passes taguées',passes.total||'—','échantillon tagué')}${kpi('Types renseignés',passes.total?pct(passes.typed_pct):'—','couverture type de passe')}</div><div class="aqm-grid-2" style="margin-top:10px"><div>${table(['Type','Réussies/Tentées','Ratées','% réussite'],safeRows(passes.types).map(row),'Types de passe non tagués.')}</div><div>${table(['Zone','Réussies/Tentées','Ratées','% réussite'],safeRows(passes.zones).map(row),'Zones de passe non taguées.')}</div><div>${table(['Pression','Réussies/Tentées','Ratées','% réussite'],safeRows(passes.pressures).map(row),'Pression non taguée sur les passes.')}</div><div>${table(['Décision','Réussies/Tentées','Ratées','% réussite'],safeRows(passes.decisions).map(row),'Décision non taguée sur les passes.')}</div></div>`;
}
function possessionDecision(u={}){
 const p=u.possessions||{},d=u.decisions||{},pr=u.pressure||{};
 const poss=p.available?`<div class="aqm-kpis">${kpi('Possessions',p.possessions,'possession=ID')}${kpi('Buts / possession',pct(p.goals_per_possession_pct),'calculé')}${kpi('Possessions avec tir',pct(p.shot_possessions_pct),'calculé')}${kpi('Pertes / possession',pct(p.turnover_possessions_pct),'calculé')}${kpi('Avantage provoqué',pct(p.advantage_earned_pct),'calculé')}${kpi('Durée observée',val(p.avg_observed_duration_s,' s'),'timestamps')}${kpi('Passes / possession',val(p.avg_tagged_passes),'calculé')}</div>${counterTable(p.outcomes,'Issue')}`:`<div class="aqm-note warn"><b>Possession exacte non mesurée</b><div>${esc(p.note||'Taguer possession=ID pour activer les taux par possession.')}</div></div>`;
 const decisions=table(['Décision','Nombre','Part','Issue positive'],safeRows(d.rows).map(x=>`<tr><td>${esc(x.key)}</td><td>${esc(x.count)}</td><td>${pct(x.share)}</td><td>${pct(x.positive_outcome_pct)}</td></tr>`),'Décisions non taguées.');
 const pressure=table(['Pression','Événements','% passes','% efficacité tir','Pertes','% pertes'],safeRows(pr.rows).map(x=>`<tr><td>${esc(x.key)}</td><td>${esc(x.events)}</td><td>${pct(x.pass_completion_pct)}</td><td>${pct(x.shot_efficiency_pct)}</td><td>${esc(x.turnovers)}</td><td>${pct(x.turnover_event_pct)}</td></tr>`),'Pression non taguée.');
 return `<div class="aqm-grid-2"><div>${poss}</div><div>${decisions}${pressure}</div></div>`;
}
function periodPhase(u={}){
 const periods=u.periods||{},phases=u.phases||[];
 const pRows=safeRows(periods.rows).map(x=>`<tr><td>${esc(x.period)}</td><td>${esc(x.goals)}/${esc(x.shots)}</td><td>${pct(x.shot_accuracy_pct)}</td><td>${pct(x.scoring_efficiency_pct)}</td><td>${esc(x.passes_completed)}/${esc(x.pass_attempts)}</td><td>${pct(x.pass_completion_pct)}</td><td>${esc(x.turnovers)}</td><td>${esc(x.ball_wins)}</td></tr>`);
 const fRows=safeRows(phases).map(x=>`<tr><td>${esc(x.label)}</td><td>${esc(x.events)}</td><td>${esc(x.goals)}/${esc(x.shots)}</td><td>${pct(x.scoring_efficiency_pct)}</td><td>${pct(x.pass_completion_pct)}</td><td>${esc(x.turnovers)}</td><td>${esc(x.ball_wins)}</td></tr>`);
 return `<div class="aqm-grid-2"><div>${table(['Période','Buts/Tirs','% cadrés','% efficacité','Passes','% passes','Pertes','Gains'],pRows,'Périodes non taguées.')}</div><div>${table(['Phase','Événements','Buts/Tirs','% efficacité','% passes','Pertes','Gains'],fRows,'Phases non taguées.')}</div></div>`;
}
function findings(rows=[]){return safeRows(rows).map(x=>`<div class="aqm-note ${x.tone==='warning'?'warn':''}"><b>${esc(x.title)}</b><div>${esc(x.text)}</div><small>${esc(x.evidence)}</small></div>`).join('')||'<div class="aqm-empty">Aucun constat qualitatif suffisamment étayé.</div>';}
function playerCard(player){
 const b=player.breakdown||{},s=b.statboard||{},tt=b.transition_timing||{},u=player.ultimate||{},loss=u.losses||{},shots=u.shots||{},passes=u.passes||{};
 const metricGrid=fullTeamKpis(s);
 const transition=`<div class="aqm-kpis">${kpi('D→A 1re passe',val(tt.defence_to_attack_first_pass_s,' s'),'timestamps',`${tt.samples?.d2o_first_pass||0} séq.`)}${kpi('D→A tir',val(tt.defence_to_attack_shot_s,' s'),'timestamps',`${tt.samples?.d2o_shot||0} séq.`)}${kpi('A→D structure',val(tt.attack_to_defence_shape_s,' s'),'timestamps',`${tt.samples?.o2d_shape||0} séq.`)}${measuredPhysical(tt.measured||{})}</div>`;
 const dimRows=Object.entries(player.dimensions||{}).map(([key,v])=>`<tr><td>${esc(key)}</td><td>${esc(v)}/100</td></tr>`);
 const roleChecks=safeRows(b.qualitative_checklist).map(x=>`<div class="aqm-note">${esc(x)}</div>`).join('');
 return `<details class="aqm-player"><summary><div><b>#${esc(player.cap||'—')} ${esc(player.name)}</b><div><span class="aqm-chip">${esc(player.role||'Poste à confirmer')}</span> <span class="aqm-chip">confiance ${esc(player.confidence||'—')}</span> <span class="aqm-chip">couverture ${esc(u.coverage?.score||0)}%</span></div></div><div><b>${player.rating==null?'—':`${esc(player.rating)}/100`}</b></div></summary><div class="aqm-player-body"><div class="aqm-kpis">${metricGrid}</div><h4>Transitions & mesures physiques</h4>${transition}<div class="aqm-grid-2"><div><h4>Pertes par cause</h4>${renderLosses(loss,b.loss_breakdown||{})}</div><div><h4>Scores individuels</h4>${table(['Dimension','Score'],dimRows,'Pas de score individuel fiable.')}${player.strengths?.length?`<div class="aqm-note"><b>Forces</b><div>${esc(player.strengths.join(' · '))}</div></div>`:''}${player.improvements?.length?`<div class="aqm-note warn"><b>Axes de revue</b><div>${esc(player.improvements.join(' · '))}</div></div>`:''}</div></div><h4>Tir individuel</h4>${shotTables(shots)}<h4>Passe individuelle</h4>${passTables(passes)}<h4>Lecture qualitative par poste</h4><div class="aqm-player-list">${roleChecks||'<div class="aqm-empty">Poste non renseigné.</div>'}</div><h4>Constats reliés aux preuves</h4>${findings(u.qualitative)}${player.shot_preference?.available?`<div class="aqm-note"><b>Préférence de tir historique</b><div>${esc(player.shot_preference.origin)} · ${esc(player.shot_preference.target)}</div></div>`:''}<a class="btn secondary" href="${esc(player.profile_url)}">Ouvrir la fiche joueuse</a></div></details>`;
}
function comparison(d){
 const a=d.team_performance?.statboard||{},b=d.team_performance?.opponent_statboard||{};
 const keys=[['Buts','goals'],['Tirs','shots'],['Cadrés','shots_on_target'],['% cadrés','shot_accuracy_pct','pct'],['% efficacité','scoring_efficiency_pct','pct'],['Passes réussies','passes_completed'],['Passes ratées','passes_failed'],['% passes','pass_completion_pct','pct'],['Pertes','turnovers'],['Assists','assists'],['Passes clés','key_passes'],['Actions créées','actions_created'],['Exclusions provoquées','exclusions_earned'],['Exclusions concédées','exclusions_committed'],['Interceptions','interceptions'],['Récupérations','recoveries'],['Blocs','blocks'],['Arrêts','saves'],['Duels gagnés','duels_won'],['Duels perdus','duels_lost']];
 return table(['Mesure',d.match?.team||'Équipe',d.match?.opponent||'Adversaire'],keys.map(([label,key,kind])=>`<tr><td>${esc(label)}</td><td>${esc(metricValue(a,key,kind))}</td><td>${esc(metricValue(b,key,kind))}</td></tr>`));
}
function coverage(u={}){
 const c=u.coverage||{},labels={player_attribution_pct:'Attribution joueuse',period_pct:'Période',phase_pct:'Phase',shot_zone_pct:'Zone tir',shot_type_pct:'Type tir',pass_type_pct:'Type passe',loss_cause_pct:'Cause perte',pressure_pct:'Pression',decision_pct:'Décision',possession_pct:'Possession ID'};
 return `<div class="aqm-kpis">${Object.entries(c.components||{}).map(([key,v])=>kpi(labels[key]||key,pct(v),'couverture structurée')).join('')}</div>`;
}
function buildSurface(d){
 const t=d.team_performance||{},s=t.statboard||{},tt=t.transition_timing||{},u=d.ultimate?.team||{};
 const sec=document.createElement('section');sec.id='aq-measured-analysis';sec.className='result-panel aqm-shell';
 sec.innerHTML=`<div class="aqm-hero"><div><span class="eyebrow">DONNÉES MESURÉES & ANALYSÉES · COMPLET</span><h2>Toutes les mesures disponibles pour ce match</h2><p>Ce bloc expose les données réellement taguées, les calculs avec dénominateur connu et les analyses qualitatives reliées aux preuves. Une donnée non mesurée reste « — ».</p><div class="aqm-nav"><a href="#aqm-team">Équipe</a><a href="#aqm-losses">Pertes</a><a href="#aqm-shots">Tirs</a><a href="#aqm-passes">Passes</a><a href="#aqm-possession">Possession</a><a href="#aqm-periods">Périodes / phases</a><a href="#aqm-players">Joueuses</a></div></div><div class="aqm-badges"><div class="aqm-badge"><b>${esc(t.confidence_label||'—')}</b><small>confiance</small></div><div class="aqm-badge"><b>${esc(t.event_count||0)}</b><small>événements</small></div><div class="aqm-badge"><b>${esc(u.coverage?.score||0)}%</b><small>couverture</small></div><div class="aqm-badge"><b>${esc(u.coverage?.readiness||'—')}</b><small>readiness</small></div></div></div>
 <div class="aqm-panel" id="aqm-team"><div class="aqm-section-head"><div><h3>1. Mesures équipe — tableau complet</h3><p>Tir, passe, création, pertes, défense, discipline, gardienne et duels.</p></div></div><div class="aqm-kpis">${fullTeamKpis(s)}</div></div>
 <div class="aqm-panel"><div class="aqm-section-head"><div><h3>2. Transitions & mesures physiques calibrées</h3><p>Temps D→A / A→D issus des timestamps. Sprint et vitesse de tir uniquement si explicitement mesurés.</p></div></div><div class="aqm-kpis">${kpi('D→A → 1re passe',val(tt.defence_to_attack_first_pass_s,' s'),'timestamps',`${tt.samples?.d2o_first_pass||0} séquence(s)`)}${kpi('D→A → tir',val(tt.defence_to_attack_shot_s,' s'),'timestamps',`${tt.samples?.d2o_shot||0} séquence(s)`)}${kpi('A→D → structure',val(tt.attack_to_defence_shape_s,' s'),'timestamps',`${tt.samples?.o2d_shape||0} séquence(s)`)}${measuredPhysical(tt.measured||{})}</div></div>
 <div class="aqm-panel"><h3>3. Scores d’exécution et niveau de preuve</h3>${dims(t)}<div class="aqm-grid-2" style="margin-top:10px"><div><h4>Forces étayées</h4>${safeRows(t.strengths).map(x=>`<div class="aqm-note"><b>${esc(x.label)} · ${esc(x.score)}/100</b><div>${esc(x.evidence)}</div></div>`).join('')||'<div class="aqm-empty">Aucune force affirmée.</div>'}</div><div><h4>Axes prioritaires</h4>${safeRows(t.reviews).map(x=>`<div class="aqm-note warn"><b>${esc(x.label)} · ${esc(x.score)}/100</b><div>${esc(x.evidence)}</div></div>`).join('')||'<div class="aqm-empty">Aucun axe faible affirmé.</div>'}</div></div></div>
 <div class="aqm-panel"><h3>4. Couverture des données</h3><p>Ce qui a réellement été renseigné dans le match.</p>${coverage(u)}</div>
 <div class="aqm-panel" id="aqm-losses"><h3>5. Pertes de possession — cause, zone, phase, pression, décision</h3>${renderLosses(u.losses||{},t.loss_breakdown||{})}</div>
 <div class="aqm-panel" id="aqm-shots"><h3>6. Tirs — localisation, type, main, distance, vitesse, release</h3>${shotTables(u.shots||{})}</div>
 <div class="aqm-panel" id="aqm-passes"><h3>7. Passes — type, zone, pression, décision</h3>${passTables(u.passes||{})}</div>
 <div class="aqm-panel" id="aqm-possession"><h3>8. Possessions, décisions et résistance à la pression</h3>${possessionDecision(u)}</div>
 <div class="aqm-panel" id="aqm-periods"><h3>9. Splits par période et par phase tactique</h3>${periodPhase(u)}</div>
 <div class="aqm-panel"><h3>10. Comparaison brute équipe / adversaire</h3><p>Uniquement à partir des événements portant la perspective « for / against ».</p>${comparison(d)}</div>
 <div class="aqm-panel"><h3>11. Analyse qualitative reliée aux preuves</h3>${findings(u.qualitative)}</div>
 <div class="aqm-panel" id="aqm-players"><div class="aqm-section-head"><div><h3>12. Joueuse par joueuse — toutes les mesures</h3><p>Ouvrir chaque joueuse pour tirs, passes, pertes, transitions, mesures physiques, décisions, poste et constats.</p></div><span class="aqm-chip">${safeRows(d.players).length} joueuse(s)</span></div><div class="aqm-player-list">${safeRows(d.players).map(playerCard).join('')||'<div class="aqm-empty">Aucune joueuse attribuée aux événements.</div>'}</div></div>
 <div class="aqm-panel"><h3>13. Contrat de preuve</h3><div class="aqm-policy">${Object.entries(d.policy||{}).map(([k,v])=>`<div><b>${esc(k.replaceAll('_',' '))}</b><br><span>${esc(v)}</span></div>`).join('')}</div></div>`;
 return sec;
}
function rewriteRetiredAtlasLinks(){
 document.querySelectorAll('a[href="/static/elite-video-atlas.html"]').forEach(a=>{a.href='/analysis-library#filmroom';if(a.id==='elite-video-atlas-cta'||a.classList.contains('ea-lab-cta'))a.innerHTML='<strong>▶ Film Room · matchs et preuves</strong><span>Vidéos intégrées, dossiers réels, métriques mesurées et analyse reliée aux séquences.</span>';});
}
async function initResult(){
 const m=location.pathname.match(/^\/matches\/(\d+)\/analysis\/result\/?$/);if(!m)return;if(document.getElementById('aq-measured-analysis'))return;
 injectStyles();
 const hero=document.querySelector('.result-hero');if(!hero)return;
 const loading=document.createElement('section');loading.id='aq-measured-analysis-loading';loading.className='result-panel';loading.innerHTML='<span class="eyebrow">DONNÉES MESURÉES & ANALYSÉES</span><h2>Chargement de toutes les métriques…</h2><p>Équipe, joueuses, tirs, passes, pertes, transitions, possession et mesures calibrées.</p>';hero.insertAdjacentElement('afterend',loading);
 const actions=hero.querySelector('.result-actions');if(actions&&!actions.querySelector('[href="#aq-measured-analysis"]'))actions.insertAdjacentHTML('beforeend','<a class="btn secondary" href="#aq-measured-analysis">Toutes les données mesurées</a>');
 try{const r=await fetch(`/api/matches/${m[1]}/performance`,{credentials:'same-origin'});if(!r.ok)throw new Error(`HTTP ${r.status}`);const d=await r.json();loading.replaceWith(buildSurface(d));}
 catch(err){loading.innerHTML=`<span class="eyebrow">DONNÉES MESURÉES & ANALYSÉES</span><h2>Impossible de charger les métriques</h2><p>${esc(err.message)}. Le moteur ne remplace pas une donnée indisponible par une valeur inventée.</p>`;}
}
function init(){rewriteRetiredAtlasLinks();initResult();setTimeout(rewriteRetiredAtlasLinks,50);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();