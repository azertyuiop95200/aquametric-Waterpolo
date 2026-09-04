(()=>{
  document.documentElement.dataset.aquametricProductRelease='2026-09-04-premium-v1';
  const hostLabel=(href)=>{try{const u=new URL(href,location.href);return u.hostname.replace(/^www\./,'')}catch{return 'source'}};
  document.querySelectorAll('a[href^="http"]').forEach(a=>{
    const text=(a.textContent||'').trim();
    if((text===a.href||text.length>62)&&!a.classList.contains('btn')){
      a.textContent=`${hostLabel(a.href)} ↗`;
      a.title=a.href;
      a.classList.add('aq-source-link');
    }
    if(a.target==='_blank') a.rel='noopener noreferrer';
  });
  document.querySelectorAll('iframe').forEach(el=>{if(!el.loading)el.loading='lazy'});
  document.querySelectorAll('img').forEach(el=>{if(!el.loading)el.loading='lazy'});
  document.querySelectorAll('table').forEach(table=>{
    if(table.closest('.aq-table-wrap,.wide,.table-scroll,.table-wrap')) return;
    const wrap=document.createElement('div'); wrap.className='aq-table-wrap'; table.parentNode.insertBefore(wrap,table); wrap.appendChild(table); table.classList.add('aq-table');
  });
  const result=document.querySelector('.result-shell');
  if(result&&!document.getElementById('aq-result-nav')){
    const panels=[...result.querySelectorAll('.result-panel')];
    const nav=document.createElement('nav'); nav.id='aq-result-nav'; nav.className='aq-nav-pills'; nav.setAttribute('aria-label','Navigation du dossier');
    panels.forEach((panel,i)=>{
      if(!panel.id) panel.id=`analysis-section-${i+1}`;
      const h=panel.querySelector('h2'); if(!h)return;
      const a=document.createElement('a');a.href=`#${panel.id}`;a.textContent=h.textContent.trim().slice(0,42);nav.appendChild(a);
    });
    if(nav.children.length) result.insertBefore(nav,result.children[1]||null);
  }
  document.querySelectorAll('.aq-kpi,.result-kpi,.mini,.ea-kpi').forEach(card=>{
    const t=(card.textContent||'').toLowerCase();
    if(t.includes('—')||t.includes('non mesur')) card.title='Donnée non prouvée ou couverture insuffisante : AquaMetric ne fabrique pas de valeur.';
  });
})();