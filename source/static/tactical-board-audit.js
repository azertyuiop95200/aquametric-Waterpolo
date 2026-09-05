(()=>{
  'use strict';
  const circles=(svg,cls)=>[...svg.querySelectorAll(`circle.${cls}`)];
  const labels=(svg,prefix)=>[...svg.querySelectorAll('text')].map(t=>(t.textContent||'').trim()).filter(x=>new RegExp(`^${prefix}\\d+$`).test(x));
  const removeDefender=(svg,label)=>{
    [...svg.querySelectorAll('text')].filter(t=>(t.textContent||'').trim()===label).forEach(t=>t.remove());
    const defs=circles(svg,'d'); if(defs.length>5) defs.slice(5).forEach(x=>x.remove());
  };
  const expected=(card,svg)=>{
    const text=`${card.textContent||''} ${svg.getAttribute('aria-label')||''}`.toLowerCase();
    const module=card.closest('.coach-module');
    const moduleText=(module?.querySelector('.coach-module-head')?.textContent||'').toLowerCase();
    if(/6v5\s*\/\s*5v6|special teams/.test(moduleText)) return {a:6,d:5,g:1,label:'6v5 / 5v6'};
    const m=text.match(/(\d)\s*v\s*(\d)/);
    if(m){
      const left=Number(m[1]),right=Number(m[2]);
      // Boards are drawn from attacking O perspective; when title is 5v6 defensive
      // reference, the six attackers remain O and the five excluded-side defenders X.
      if(left===5&&right===6&&/5v6|zone−|penalty kill/.test(text)) return {a:6,d:5,g:1,label:'5v6 défense'};
      return {a:left,d:right,g:1,label:`${left}v${right}`};
    }
    if(card.classList.contains('freeze')) return {a:6,d:6,g:1,label:'6v6'};
    return null;
  };
  const addBadge=(card,svg)=>{
    card.querySelector('.board-personnel')?.remove();
    const a=circles(svg,'a').length,d=circles(svg,'d').length,g=circles(svg,'gk').length;
    const exp=expected(card,svg);
    const oLabels=labels(svg,'O'),xLabels=labels(svg,'X');
    const uniqueO=new Set(oLabels).size===oLabels.length,uniqueX=new Set(xLabels).size===xLabels.length;
    const countOk=!exp||(a===exp.a&&d===exp.d&&g===exp.g);
    const labelsOk=uniqueO&&uniqueX&&oLabels.length===a&&xLabels.length===d;
    const ok=countOk&&labelsOk;
    const badge=document.createElement('small');badge.className=`board-personnel ${ok?'board-personnel-ok':'board-personnel-error'}`;
    badge.textContent=`${ok?'✓':'⚠'} ${a} O · ${d} X${g?` + ${g} GK`:''}${exp?` · attendu ${exp.a}/${exp.d}/${exp.g}`:''}`;
    badge.title=ok?'Personnel et labels cohérents avec la situation dessinée.':'Incohérence de personnel/labels : ce schéma ne doit pas être utilisé comme référence avant correction.';
    badge.style.cssText=`display:inline-flex;margin-top:8px;padding:5px 8px;border-radius:999px;border:1px solid ${ok?'rgba(83,217,139,.45)':'rgba(255,127,134,.55)'};font-size:10px;font-weight:800;color:${ok?'#bdf7d3':'#ffc1c5'};background:${ok?'rgba(83,217,139,.08)':'rgba(255,127,134,.08)'}`;
    const target=card.querySelector('.copy,.freeze-copy')||card;target.appendChild(badge);
    svg.dataset.attackers=String(a);svg.dataset.defenders=String(d);svg.dataset.goalkeepers=String(g);svg.dataset.personnelValid=ok?'1':'0';
    if(!ok){card.dataset.boardInvalid='1';svg.setAttribute('aria-description','Schéma tactique en attente de correction du personnel.');}
  };
  function run(){
    document.querySelectorAll('.coach-module').forEach(module=>{
      const txt=module.querySelector('.coach-module-head')?.textContent||'';
      if(/6v5\s*\/\s*5v6|Special teams/i.test(txt)) module.querySelectorAll('.freeze svg').forEach(svg=>removeDefender(svg,'X6'));
    });
    document.querySelectorAll('.tactic-board-card,.freeze').forEach(card=>{const svg=card.querySelector('svg');if(svg)addBadge(card,svg)});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else run();
})();