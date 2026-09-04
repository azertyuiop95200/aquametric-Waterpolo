(()=>{
  document.documentElement.dataset.aquametricProductRelease='2026-09-04-premium-v4';
  const directMatch=location.pathname.match(/^\/matches\/(\d+)\/?$/);
  if(directMatch&&!new URLSearchParams(location.search).has('workspace')){
    fetch(`/api/premium/matches/${directMatch[1]}/status`,{credentials:'same-origin'}).then(r=>r.ok?r.json():null).then(d=>{
      if(d&&d.analysis_flow&&d.result_url) location.replace(d.result_url);
    }).catch(()=>{});
  }
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const hostLabel=(href)=>{try{const u=new URL(href,location.href);return u.hostname.replace(/^www\./,'')}catch{return 'source'}};
  const val=(v,suffix='')=>v===null||v===undefined||v===''?'—':`${v}${suffix}`;
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
  async function addPremiumBrief(){
    if(!result||!matchId||document.getElementById('aq-premium-brief'))return;
    try{
      const r=await fetch(`/api/premium/matches/${matchId}/brief`,{credentials:'same-origin'});if(!r.ok)return;const d=await r.json();
      const scoring=(d.phase_scoring||[]).map(x=>`<div class="aq-kpi"><span>${esc(x.label)}</span><b>${esc(x.goals||0)} but${x.goals===1?'':'s'}</b><small>${val(x.goal_share_pct,'%')} des buts · ${val(x.conversion_pct,'%')} conversion · ${esc(x.shots||0)} tirs</small></div>`).join('');
      const routes=(d.repeated_routes||[]).map(x=>`<div class="aq-habit"><b>${esc(x.signature)}</b><span>${esc(x.count)} répétition(s)</span><small>${val(x.share_pct,'%')} des buts observés</small></div>`).join('');
      const players=(d.players||[]).map(p=>{const s=p.statboard||{},tr=p.transition||{};const losses=(p.losses?.rows||[]).slice(0,2).map(x=>`${x.label} ${x.share}%`).join(' · ');return `<article class="aq-card"><div class="aq-card-body"><div class="aq-tags"><span class="aq-tag">#${esc(p.cap??'—')}</span><span class="aq-tag">${esc(p.role||'poste à confirmer')}</span><span class="aq-tag">${esc(p.event_count)} événements</span></div><h3>${esc(p.name)}</h3><div class="aq-kpi-row">${kpi('Buts / tirs',`${s.goals||0}/${s.shots||0}`,`${val(s.scoring_efficiency_pct,'%')} efficacité`)}${kpi('Cadrage',val(s.shot_accuracy_pct,'%'))}${kpi('Passes',val(s.pass_completion_pct,'%'),`${s.passes_completed||0}/${s.pass_attempts_tagged||0}`)}${kpi('Pertes',s.turnovers||0,losses||'cause à documenter')}${kpi('D→A 1re passe',val(tr.defence_to_attack_first_pass_s,' s'))}${kpi('A→D structure',val(tr.attack_to_defence_shape_s,' s'))}</div><details><summary>Checklist ${esc(p.position_family||'poste')}</summary><div class="aq-habits">${(p.checklist||[]).map(x=>`<div class="aq-habit"><span>${esc(x)}</span></div>`).join('')}</div></details></div></article>`}).join('');
      const qualitative=(d.qualitative||[]).map(f=>habit({title:f.title,text:f.text,evidence:f.evidence},f.tone==='positive'?'good':f.tone==='warning'?'bad':'')).join('');
      const panel=document.createElement('section');panel.id='aq-premium-brief';panel.className='aq-section';panel.innerHTML=`<div class="aq-section-head"><div><span class="aq-eyebrow">EXECUTIVE COACH BRIEF · PREMIUM</span><h2>Ce que le match dit réellement</h2></div><p>Résumé calculé à partir des faits vérifiés, du contexte de phase, des causes de pertes, des tirs, des séquences et de l’attribution joueuse. Les champs non prouvés restent vides.</p></div><div class="aq-kpi-row">${kpi('Couverture',val(d.coverage?.score,'%'),d.coverage?.readiness||'')}${kpi('Buts',d.basic?.goals||0)}${kpi('Tirs',d.basic?.shots||0,`${val(d.basic?.scoring_efficiency_pct,'%')} efficacité`)}${kpi('Passes',val(d.basic?.pass_completion_pct,'%'))}${kpi('Pertes',d.basic?.turnovers||0)}${kpi('Décisions taguées',d.decisions?.total||0,`${val(d.decisions?.poor_pct,'%')} pauvres`)}</div><div class="aq-split" style="margin-top:14px"><div><h3>Habitudes positives</h3><div class="aq-habits">${(d.positive_habits||[]).map(h=>habit(h,'good')).join('')||'<div class="aq-empty">Pas assez de preuves pour une habitude positive forte.</div>'}</div></div><div><h3>Risques / habitudes négatives</h3><div class="aq-habits">${(d.negative_habits||[]).map(h=>habit(h,'bad')).join('')||'<div class="aq-empty">Pas assez de preuves pour un risque récurrent.</div>'}</div></div></div>${(d.tendencies||[]).length?`<h3>Tendances</h3><div class="aq-habits">${d.tendencies.map(h=>habit(h,'')).join('')}</div>`:''}${qualitative?`<h3>Diagnostic qualité</h3><div class="aq-habits">${qualitative}</div>`:''}<div class="aq-section-head" style="margin-top:20px"><div><span class="aq-eyebrow">COMMENT L’ÉQUIPE MARQUE</span><h2>Phases et routes de but</h2></div></div><div class="aq-kpi-row">${scoring||'<div class="aq-empty">Les buts doivent être tagués par phase pour obtenir la distribution.</div>'}</div>${routes?`<h3>Enchaînements répétés avant but</h3><div class="aq-habits">${routes}</div>`:''}<div class="aq-section-head" style="margin-top:20px"><div><span class="aq-eyebrow">ANALYSE INDIVIDUELLE PAR POSTE</span><h2>Joueuse par joueuse</h2></div><p>Statistiques + transition + causes de pertes + grille qualitative adaptée au poste.</p></div><div class="aq-grid">${players||'<div class="aq-empty">Aucune action attribuée à une joueuse. Attribue les événements pour obtenir l’analyse individuelle.</div>'}</div>`;
      const hero=result.querySelector('.result-hero');hero?.insertAdjacentElement('afterend',panel);
      const nav=document.getElementById('aq-result-nav');if(nav){const a=document.createElement('a');a.href='#aq-premium-brief';a.textContent='Executive Coach Brief';nav.insertBefore(a,nav.firstChild)}
    }catch(e){console.warn('AquaMetric premium brief unavailable',e)}
  }
  addPremiumBrief();
  document.querySelectorAll('.aq-kpi,.result-kpi,.mini,.ea-kpi').forEach(card=>{const t=(card.textContent||'').toLowerCase();if(t.includes('—')||t.includes('non mesur'))card.title='Donnée non prouvée ou couverture insuffisante : AquaMetric ne fabrique pas de valeur.'});
})();