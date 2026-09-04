(()=>{
  const NS='http://www.w3.org/2000/svg';
  const labelFor=(svg)=>{
    const a=svg.querySelectorAll('circle.a,.o').length;
    const d=svg.querySelectorAll('circle.d,.x').length;
    const g=svg.querySelectorAll('circle.gk,.g').length;
    return {a,d,g,text:`${a} attaque${a>1?'s':''} · ${d} défense${d>1?'s':''}${g?` + ${g} gardienne`:''}`};
  };
  const removeDefender=(svg,label)=>{
    const texts=[...svg.querySelectorAll('text')].filter(t=>t.textContent.trim()===label);
    texts.forEach(t=>t.remove());
    const defenders=[...svg.querySelectorAll('circle.d')];
    if(defenders.length>5) defenders.slice(5).forEach(x=>x.remove());
  };
  const addBadge=(card,svg)=>{
    if(card.querySelector('.board-personnel')) return;
    const c=labelFor(svg);
    const badge=document.createElement('small');
    badge.className='board-personnel';
    badge.textContent=c.text;
    badge.style.cssText='display:inline-flex;margin-top:8px;padding:4px 7px;border-radius:999px;border:1px solid rgba(255,255,255,.22);font-size:10px;opacity:.82';
    const target=card.querySelector('.copy,.freeze-copy')||card;
    target.appendChild(badge);
    svg.dataset.attackers=String(c.a);svg.dataset.defenders=String(c.d);svg.dataset.goalkeepers=String(c.g);
  };
  function run(){
    document.querySelectorAll('.coach-module').forEach(module=>{
      const txt=module.querySelector('.coach-module-head')?.textContent||'';
      if(/6v5\s*\/\s*5v6|Special teams/i.test(txt)){
        module.querySelectorAll('.freeze svg').forEach(svg=>{
          removeDefender(svg,'X6');
          svg.dataset.expectedDefenders='5';
        });
      }
    });
    document.querySelectorAll('.tactic-board-card,.freeze').forEach(card=>{
      const svg=card.querySelector('svg'); if(svg) addBadge(card,svg);
    });
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',run); else run();
})();
