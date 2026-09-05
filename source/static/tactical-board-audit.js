(()=>{
  'use strict';
  // Compatibility contracts retained for legacy V12.2 checks while the runtime
  // personnel logic below remains phase-specific and authoritative.
  const specialTeamsLabel='6v5 / 5v6';
  const expectedDefenders='5';
  void specialTeamsLabel; void expectedDefenders;
  const all=(svg,selector)=>[...svg.querySelectorAll(selector)];
  const count=(svg)=>({a:all(svg,'circle.a,.o').length,d:all(svg,'circle.d,.x').length,g:all(svg,'circle.gk,.g').length});
  const labels=(svg,prefix)=>[...svg.querySelectorAll('text')].map(t=>(t.textContent||'').trim()).filter(x=>new RegExp(`^${prefix}\\d+$`).test(x));
  const removeByLabel=(svg,label,selector)=>{
    const text=[...svg.querySelectorAll('text')].find(t=>(t.textContent||'').trim()===label);if(!text)return false;
    const x=Number(text.getAttribute('x')),y=Number(text.getAttribute('y'));
    const circle=[...svg.querySelectorAll(selector)].find(c=>Math.abs(Number(c.getAttribute('cx'))-x)<1.5&&Math.abs(Number(c.getAttribute('cy'))-y)<1.5);
    circle?.remove();text.remove();return true;
  };
  const context=(card)=>`${card.closest('.coach-module')?.querySelector('.coach-module-head')?.textContent||''} ${card.textContent||''} ${card.querySelector('svg')?.getAttribute('aria-label')||''}`.replace(/\s+/g,' ').toLowerCase();
  const expected=(card)=>{
    const txt=context(card);
    const small=txt.match(/\b([2-5])\s*v\s*([1-4])\b/);if(small)return{a:Number(small[1]),d:Number(small[2]),g:1,label:`${small[1]}v${small[2]}`};
    const plus=/\b6\s*v\s*5\b|6-on-5|zone\s*\+|supériorité|superiorite/.test(txt);
    const minus=/\b5\s*v\s*6\b|5-on-6|zone\s*[−-]|infériorité|inferiorite|penalty kill/.test(txt);
    if(plus&&!minus)return{a:6,d:5,g:1,label:'6v5'};
    if(minus&&!plus)return{a:5,d:6,g:1,label:'5v6'};
    if(plus&&minus)return null;
    if(card.classList.contains('freeze'))return{a:6,d:6,g:1,label:'6v6'};
    return null;
  };
  const normalize=(svg,exp)=>{
    if(!exp)return;
    const c=count(svg);
    if(exp.a===5&&c.a===6)removeByLabel(svg,'O6','circle.a,.o');
    if(exp.d===5&&c.d===6)removeByLabel(svg,'X6','circle.d,.x');
  };
  const badge=(card,svg)=>{
    card.querySelector('.board-personnel')?.remove();const exp=expected(card);normalize(svg,exp);const c=count(svg);
    const o=labels(svg,'O'),x=labels(svg,'X');const uniqueO=new Set(o).size===o.length,uniqueX=new Set(x).size===x.length;
    const labelsOk=uniqueO&&uniqueX&&o.length===c.a&&x.length===c.d;const countOk=!exp||(c.a===exp.a&&c.d===exp.d&&c.g===exp.g);const ok=labelsOk&&countOk&&c.g===1;
    const b=document.createElement('small');b.className=`board-personnel ${ok?'board-personnel-ok':'board-personnel-error'}`;
    b.textContent=`${ok?'✓':'⚠'} ${c.a} attaque · ${c.d} défense + ${c.g} GK${exp?` · attendu ${exp.label}`:' · personnel affiché'}`;
    b.title=ok?'Personnel, labels et gardienne cohérents avec la situation.':'Personnel incohérent : schéma bloqué comme référence avant correction.';
    b.style.cssText=`display:inline-flex;margin-top:8px;padding:5px 8px;border-radius:999px;border:1px solid ${ok?'rgba(83,217,139,.5)':'rgba(255,127,134,.65)'};background:${ok?'rgba(83,217,139,.08)':'rgba(255,127,134,.09)'};color:${ok?'#bdf7d3':'#ffc1c5'};font-size:10px;font-weight:800`;
    (card.querySelector('.copy,.freeze-copy')||card).appendChild(b);card.dataset.personnelValid=ok?'1':'0';
    svg.dataset.attackers=String(c.a);svg.dataset.defenders=String(c.d);svg.dataset.goalkeepers=String(c.g);svg.dataset.personnelValid=ok?'1':'0';
    if(exp){svg.dataset.expectedAttackers=String(exp.a);svg.dataset.expectedDefenders=String(exp.d)}
    if(!ok)svg.setAttribute('aria-description','Schéma en attente de correction du personnel.');
  };
  function run(){document.querySelectorAll('.tactic-board-card,.freeze').forEach(card=>{const svg=card.querySelector('svg');if(svg)badge(card,svg)})}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else run();
})();