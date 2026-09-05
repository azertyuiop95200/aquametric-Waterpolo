(()=>{
  // Executive Coach Brief · V12.2 premium match surface.
  document.documentElement.dataset.aquametricProductRelease='V12.2-ultimate-match-video-intelligence';
  const directMatch=location.pathname.match(/^\/matches\/(\d+)\/?$/);
  if(directMatch&&!new URLSearchParams(location.search).has('workspace')){
    fetch(`/api/premium/matches/${directMatch[1]}/status`,{credentials:'same-origin'}).then(r=>r.ok?r.json():null).then(d=>{
      if(d&&d.analysis_flow&&d.result_url) location.replace(d.result_url);
    }).catch(()=>{});
  }
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const hostLabel=(href)=>{try{const u=new URL(href,location.href);return u.hostname.replace(/^www\./,'')}catch{return 'source'}};
  const val=(v,suffix='')=>v===null||v===undefined||v===''?'—':`${v}${suffix}`;
  const metric=(v,suffix='')=>v===null||v===undefined?'—':`${v}${suffix}`;
  const refreshKnowledgeLinks=()=>{
    const lab=document.getElementById('elite-analyst-cta');
    if(lab){lab.href='/analysis-library';lab.innerHTML='<strong>▶ Salle vidéo & Analyse Ultimate</strong><span>Résultats, vidéos, séquences, habitudes, joueuses, tendances et preuves reliées au match.</span>'}
    const atlas=document.getElementById('elite-video-atlas-cta');
    if(atlas){atlas.href='/analysis-library#filmroom';atlas.innerHTML='<strong>▶ Film Room élite · vidéos directement lisibles</strong><span>Références internationales + dossiers data. Les anciens croquis génériques ne sont plus utilisés comme preuves.</span>'}
  };
  refreshKnowledgeLinks();
  setTimeout(refreshKnowledgeLinks,0);
  document.querySelectorAll('a[href^="http"]').forEach(a=>{
    const text=(a.textContent||'').trim();
    if((text===a.href||text.length>62)&&!a.classList.contains('btn')){a.textContent=`${hostLabel(a.href)} ↗`;a.title=a.href;a.classList.add('aq-source-link')}
    if(a.target==='_blank') a.rel='noopener noreferrer';
  });
  document.querySelectorAll('iframe').forEach(el=>{if(!el.loading)el.loading='lazy'});
  document.querySelectorAll('img').forEach(el=>{if(!el.loading)el.loading='lazy'});
  document.querySelectorAll('table').forEach(table=>{
    if(table.closest('.aq-table-wrap,.wide,.table-scroll,.table-wrap')) return;
    const wrap=document.createElement('div');wrap.className='aq-table-wrap';table.parentNode.insertBefore(wrap,table);wrap.appendChild(table);table.classList.add('aq-table');
  });
  const result=document.querySelector('.result-shell');
  if(result&&!document.getElementById('aq-result-nav')){
    const panels=[...result.querySelectorAll('.result-panel')];const nav=document.createElement('nav');nav.id='aq-result-nav';nav.className='aq-nav-pills';nav.setAttribute('aria-label','Navigation du dossier');
    panels.forEach((panel,i)=>{if(!panel.id)panel.id=`analysis-section-${i+1}`;const h=panel.querySelector('h2');if(!h)return;const a=document.createElement('a');a.href=`#${panel.id}`;a.textContent=h.textContent.trim().slice(0,42);nav.appendChild(a)});
    if(nav.children.length) result.insertBefore(nav,result.children[1]||null);
  }
  const habit=(h,tone)=>`<article class="aq-habit ${tone}"><b>${esc(h.title)}</b><span>${esc(h.text)}</span><small>${esc(h.evidence||'')} ${h.strength?`· ${esc(h.strength)}`:''}</small></article>`;
  const kpi=(label,value,detail='')=>`<div class="aq-kpi"><span>${esc(label)}</span><b>${esc(value)}</b>${detail?`<small>${esc(detail)}</small>`:''}</div>`;
  const matchId=(()=>{const m=location.pathname.match(/^\/matches\/(\d+)\/analysis\/result\/?$/);return m?m[1]:null})();

  const playerEvidenceCard=e=>{
    let media='';
    if(e.clip_url) media=`<video controls preload="metadata" src="${esc(e.clip_url)}"></video>`;
    else if(e.local_segment_url) media=`<video controls preload="metadata" src="${esc(e.local_segment_url)}"></video>`;
    else if(e.segment_embed) media=`<iframe loading="lazy" src="${esc(e.segment_embed)}" title="${esc(e.title||'Séquence')}" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>`;
    else if((e.screenshot_urls||[])[0]) media=`<img loading="lazy" src="${esc(e.screenshot_urls[0])}" alt="${esc(e.title||'Preuve image')}">`;
    if(!media)return '';
    const sec=Number(e.second||0);const t=`${Math.floor(sec/60)}:${String(Math.floor(sec%60)).padStart(2,'0')}`;
    return `<article class="aq-card"><div class="aq-media">${media}</div><div class="aq-card-body"><div class="aq-tags"><span class="aq-tag">${esc(t)}</span><span class="aq-tag">${esc(e.kind||'preuve')}</span>${e.confidence_label?`<span class="aq-tag">${esc(e.confidence_label)}</span>`:''}</div><b>${esc(e.title||'Séquence')}</b>${e.summary?`<p>${esc(e.summary)}</p>`:''}${(e.screenshot_urls||[]).length>1?`<div class="aq-tags">${e.screenshot_urls.slice(0,3).map((u,i)=>`<a class="aq-tag" href="${esc(u)}" target="_blank" rel="noopener">Image ${i+1}</a>`).join('')}</div>`:''}</div></article>`;
  };

  const playerTable=players=>{
    if(!players.length)return '<div class="aq-empty">Aucune action attribuée à une joueuse.</div>';
    const rows=players.map(p=>{const s=p.statboard||{},ph=p.physical||{};return `<tr><td><b>${esc(p.name)}</b><br><small>#${esc(p.cap??'—')} · ${esc(p.role||'poste à confirmer')}</small></td><td>${esc(ph.playing_time?.text||'—')}</td><td>${esc(s.ball_touches??0)}</td><td>${esc(s.centre_touches??0)}</td><td>${esc(s.passes_completed??0)}</td><td>${esc(s.passes_failed??0)}</td><td>${metric(s.pass_completion_pct,'%')}</td><td>${esc(s.shots??0)}</td><td>${esc(s.goals??0)}</td><td>${metric(s.shot_accuracy_pct,'%')}</td><td>${esc(s.duels_won??0)} / ${esc(s.duels_lost??0)}</td><td>${esc(s.turnovers??0)}</td><td>${esc(s.interceptions??0)}</td><td>${esc(s.recoveries??0)}</td><td>${esc(s.exclusions_earned??0)} / ${esc(s.exclusions_committed??0)}</td><td>${metric(ph.distance_m,' m')}</td><td>${metric(ph.max_swim_speed_mps,' m/s')}</td><td>${metric(ph.shot_speed_kmh,' km/h')}</td></tr>`}).join('');
    return `<div class="aq-table-wrap"><table class="aq-table"><thead><tr><th>Joueuse</th><th>Temps jeu</th><th>Touches</th><th>Touches centre</th><th>Passes OK</th><th>Passes ratées</th><th>% passes</th><th>Tirs</th><th>Buts</th><th>% cadrage</th><th>Duels G/P</th><th>Pertes</th><th>Interceptions</th><th>Récup.</th><th>Excl. +/−</th><th>Distance</th><th>Vitesse max</th><th>Vitesse tir</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  };

  const playerCard=p=>{
    const s=p.statboard||{},tr=p.transition||{},ph=p.physical||{};
    const losses=(p.losses?.rows||[]).slice(0,4).map(x=>`${x.label} ${x.count} (${metric(x.share,'%')})`).join(' · ');
    const proof=(p.evidence||[]).slice(0,4).map(playerEvidenceCard).filter(Boolean).join('');
    return `<article class="aq-card"><div class="aq-card-body"><div class="aq-tags"><span class="aq-tag">#${esc(p.cap??'—')}</span><span class="aq-tag">${esc(p.role||'poste à confirmer')}</span><span class="aq-tag">${esc(p.event_count)} événements attribués</span><span class="aq-tag ${ph.calibrated?'good':'warn'}">${ph.calibrated?'physique calibré':'physique non calibré'}</span></div><h3>${esc(p.name)}</h3><div class="aq-kpi-row">${kpi('Temps de jeu',ph.playing_time?.text||'—',ph.playing_time?'mesuré/tagué':'non mesuré')}${kpi('Touches de balle',s.ball_touches??0,`${s.centre_touches??0} au centre`)}${kpi('Passes',`${s.passes_completed??0}/${s.pass_attempts_tagged??0}`,`${metric(s.pass_completion_pct,'%')} · ${s.passes_failed??0} ratées`)}${kpi('Buts / tirs',`${s.goals??0}/${s.shots??0}`,`${metric(s.scoring_efficiency_pct,'%')} efficacité · ${metric(s.shot_accuracy_pct,'%')} cadrage`)}${kpi('Duels',`${s.duels_won??0}/${s.duels_total??0}`,`${s.duels_lost??0} perdus`)}${kpi('Pertes',s.turnovers??0,losses||'cause à documenter')}${kpi('Création',`${s.assists??0} A · ${s.key_passes??0} KP`,`${s.actions_created??0} actions créées`)}${kpi('Défense',`${s.interceptions??0} INT · ${s.recoveries??0} REC`,`${s.blocks??0} blocs · ${s.saves??0} arrêts`)}${kpi('Exclusions +/−',`${s.exclusions_earned??0}/${s.exclusions_committed??0}`,`${s.penalties_earned??0} pen. provoqué(s)`)}${kpi('D→A 1re passe',val(tr.defence_to_attack_first_pass_s,' s'))}${kpi('A→D structure',val(tr.attack_to_defence_shape_s,' s'))}${kpi('Distance',metric(ph.distance_m,' m'),ph.distance_m!==null&&ph.distance_m!==undefined?'calibrée':'non mesurée')}${kpi('Vitesse nage max',metric(ph.max_swim_speed_mps,' m/s'),ph.max_swim_speed_mps!==null&&ph.max_swim_speed_mps!==undefined?'mesurée':'non mesurée')}${kpi('Vitesse tir',metric(ph.shot_speed_kmh,' km/h'),ph.shot_speed_kmh!==null&&ph.shot_speed_kmh!==undefined?'mesurée':'non mesurée')}${kpi('Release',metric(ph.release_time_s,' s'),ph.release_time_s!==null&&ph.release_time_s!==undefined?'mesuré':'non mesuré')}</div><details><summary>Lecture poste · pertes · phases</summary><div class="aq-habits">${(p.checklist||[]).map(x=>`<div class="aq-habit"><span>${esc(x)}</span></div>`).join('')}</div>${losses?`<p><b>Causes pertes :</b> ${esc(losses)}</p>`:''}<p class="aq-subtle">Contrat mesure : temps ${esc(p.measurement_contract?.playing_time||'NON MESURÉ')} · distance ${esc(p.measurement_contract?.distance||'NON MESURÉ')} · vitesse ${esc(p.measurement_contract?.absolute_speed||'NON MESURÉ')}</p></details>${proof?`<details open><summary>Preuves vidéo / images de ${esc(p.name)}</summary><div class="aq-grid" style="margin-top:10px">${proof}</div></details>`:'<p class="aq-subtle">Aucune preuve média attribuée directement à cette joueuse pour le moment.</p>'}</div></article>`;
  };

  async function addPremiumBrief(){
    if(!result||!matchId||document.getElementById('aq-premium-brief'))return;
    try{
      const r=await fetch(`/api/premium/matches/${matchId}/brief`,{credentials:'same-origin'});if(!r.ok)return;const d=await r.json();
      const scoring=(d.phase_scoring||[]).map(x=>`<div class="aq-kpi"><span>${esc(x.label)}</span><b>${esc(x.goals||0)} but${x.goals===1?'':'s'}</b><small>${val(x.goal_share_pct,'%')} des buts · ${val(x.conversion_pct,'%')} conversion · ${esc(x.shots||0)} tirs</small></div>`).join('');
      const routes=(d.repeated_routes||[]).map(x=>`<div class="aq-habit"><b>${esc(x.signature)}</b><span>${esc(x.count)} répétition(s)</span><small>${val(x.share_pct,'%')} des buts observés</small></div>`).join('');
      const playerRows=d.players||[];
      const players=playerRows.map(playerCard).join('');
      const qualitative=(d.qualitative||[]).map(f=>habit({title:f.title,text:f.text,evidence:f.evidence},f.tone==='positive'?'good':f.tone==='warning'?'bad':'')).join('');
      const panel=document.createElement('section');panel.id='aq-premium-brief';panel.className='aq-section';panel.innerHTML=`<div class="aq-section-head"><div><span class="aq-eyebrow">EXECUTIVE COACH BRIEF · V12.2</span><h2>Ce que le match dit réellement</h2></div><p>Mesures, faits vérifiés, phases, pertes, tirs, passes, joueuses et preuves média. Une valeur physique absolue n’apparaît que si elle est réellement mesurée/calibrée.</p></div><div class="aq-kpi-row">${kpi('Couverture',val(d.coverage?.score,'%'),d.coverage?.readiness||'')}${kpi('Buts',d.basic?.goals||0)}${kpi('Tirs',d.basic?.shots||0,`${val(d.basic?.scoring_efficiency_pct,'%')} efficacité`)}${kpi('Passes',val(d.basic?.pass_completion_pct,'%'))}${kpi('Pertes',d.basic?.turnovers||0)}${kpi('Décisions taguées',d.decisions?.total||0,`${val(d.decisions?.poor_pct,'%')} pauvres`)}${kpi('Séquences',d.sequence_summary?.total||0,`${d.sequence_summary?.downloadable_clips||0} clips téléchargeables`)}</div><div class="aq-split" style="margin-top:14px"><div><h3>Habitudes positives</h3><div class="aq-habits">${(d.positive_habits||[]).map(h=>habit(h,'good')).join('')||'<div class="aq-empty">Pas assez de preuves pour une habitude positive forte.</div>'}</div></div><div><h3>Risques / habitudes négatives</h3><div class="aq-habits">${(d.negative_habits||[]).map(h=>habit(h,'bad')).join('')||'<div class="aq-empty">Pas assez de preuves pour un risque récurrent.</div>'}</div></div></div>${(d.tendencies||[]).length?`<h3>Tendances</h3><div class="aq-habits">${d.tendencies.map(h=>habit(h,'')).join('')}</div>`:''}${qualitative?`<h3>Diagnostic qualité</h3><div class="aq-habits">${qualitative}</div>`:''}<div class="aq-section-head" style="margin-top:20px"><div><span class="aq-eyebrow">COMMENT L’ÉQUIPE MARQUE</span><h2>Phases et routes de but</h2></div></div><div class="aq-kpi-row">${scoring||'<div class="aq-empty">Les buts doivent être tagués par phase pour obtenir la distribution.</div>'}</div>${routes?`<h3>Enchaînements répétés avant but</h3><div class="aq-habits">${routes}</div>`:''}<div class="aq-section-head" style="margin-top:22px"><div><span class="aq-eyebrow">MATRICE JOUEUSES · TOUTES LES MESURES</span><h2>Une ligne par joueuse, aucune donnée cachée</h2></div><p>Temps de jeu, touches, centre, passes, tirs, duels, pertes, défense, exclusions et physique calibré.</p></div>${playerTable(playerRows)}<div class="aq-section-head" style="margin-top:22px"><div><span class="aq-eyebrow">DOSSIER INDIVIDUEL + PREUVES</span><h2>Joueuse par joueuse</h2></div><p>Chaque fiche relie les métriques à ses clips/images quand des événements attribués possèdent une preuve média.</p></div><div class="aq-grid">${players||'<div class="aq-empty">Aucune action attribuée à une joueuse. Attribue/valide les événements pour obtenir l’analyse individuelle.</div>'}</div>`;
      const hero=result.querySelector('.result-hero');hero?.insertAdjacentElement('afterend',panel);
      const nav=document.getElementById('aq-result-nav');if(nav){const a=document.createElement('a');a.href='#aq-premium-brief';a.textContent='Toutes les métriques joueuses';nav.insertBefore(a,nav.firstChild)}
    }catch(e){console.warn('AquaMetric premium brief unavailable',e)}
  }
  addPremiumBrief();
  document.querySelectorAll('.aq-kpi,.result-kpi,.mini,.ea-kpi').forEach(card=>{const t=(card.textContent||'').toLowerCase();if(t.includes('—')||t.includes('non mesur'))card.title='Donnée non prouvée ou couverture insuffisante : AquaMetric ne fabrique pas de valeur.'});
})();