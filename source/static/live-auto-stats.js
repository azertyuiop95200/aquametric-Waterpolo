/* Progressive AI sports estimates: DOM text only, no markup from models.
   Updates during video playback without pausing or reloading the report. */
(() => {
  const panel = document.getElementById('liveAutomaticStats');
  if (!panel) return;
  const $=id=>document.getElementById(id);
  const names={for:'Équipe suivie',against:'Adversaire',unknown:'Équipe indéterminée'};
  let revision=null,delay=3500,stopped=false,failures=0;
  const update=(node,text)=>{if(node)node.textContent=String(text)};
  const row=(parent,content)=>{
    const div=document.createElement('div');
    div.className='event-row';
    const main=document.createElement('span');
    main.textContent=content;
    div.appendChild(main);
    parent.appendChild(div);
  };
  function display(data){
    if (data.revision === revision && data.status !== 'unavailable') return;
    revision=data.revision;
    update($('liveAutoStatus'),{
      unavailable:'Moteur IA non configuré',
      awaiting_video:'En attente de vidéo',
      processing:'Détections en cours',
      ready:'Traitement terminé · à vérifier',
      partial:'Traitement incomplet',
    }[data.status]||data.status||'État inconnu');
    update($('liveAutoMessage'),data.message||'Analyse indisponible.');
    update($('liveAutoProgress'),data.completed+' / '+data.total+' séquences traitées');
    update($('liveAutoDetected'),data.counted_events
      ? data.counted_events+' action(s) retenue(s) automatiquement · '+data.excluded_events+' exclue(s)'
      : 'Aucune action sportive retenue');
    panel.querySelectorAll('[data-auto-side][data-auto-field]').forEach(cell=>{
      const side=cell.dataset.autoSide,key=cell.dataset.autoField;
      const group=data.sides?.[side]||{};
      // No observations of this team means "unmeasured", not a true 0.
      const value=group.actions>0?group[key]:null;
      cell.textContent=value==null?'—':key==='efficiency_pct'?value+' %':String(value);
      cell.classList.toggle('unmeasured',value==null);
    });
    const sources=$('liveAutoSources');sources.replaceChildren();
    for(const info of data.sources||[]){
      row(sources,'Vidéo '+info.part+' · '+info.completed+'/'+info.total+
        ' séquences · '+info.coverage_percent+' % de durée couverte · '+info.detected+
        ' détection(s) · '+(info.message||info.status));
    }
    if(!(data.sources||[]).length)row(sources,'Aucune analyse vidéo démarrée.');
    const timeline=$('liveAutoTimeline');timeline.replaceChildren();
    for(const item of data.recent_events||[]){
      const n=Math.floor(item.second);
      row(timeline,'Vidéo '+item.video_part+' · '+String(Math.floor(n/60)).padStart(2,'0')+
        ':'+String(n%60).padStart(2,'0')+' · '+item.label+' · '+
        (names[item.side]||'Équipe inconnue')+' · confiance '+Math.round(item.confidence*100)+' %'+
        (item.cap_number?' · bonnet candidat '+item.cap_number:''));
    }
    if(!(data.recent_events||[]).length)row(timeline,'Aucun événement automatique identifié dans les séquences traitées.');
    const start=$('liveAutoStartAction');
    if(start){
      const initialLocal=start.dataset.source==='upload' && data.status==='awaiting_video';
      const retry=data.status==='partial'||data.status==='failed';
      start.hidden=!(data.configured && !data.active && (initialLocal||retry) && start.querySelector('form'));
    }
    update($('liveAutoPrivacyNote'),data.configured
      ? 'Les chiffres IA sont provisoires ; seules les annotations vérifiées servent au rapport officiel et aux points du bassin.'
      : 'Analyse des actions indisponible tant que la clé du modèle vidéo manque. Aucune donnée n’est simulée.');
  }
  const schedule=()=>{if(!stopped)setTimeout(refresh,delay)};
  async function refresh(){
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),10000);
    try{
      const response=await fetch(panel.dataset.url,{cache:'no-store',credentials:'same-origin',signal:controller.signal});
      if(response.status===401||response.status===404){
        stopped=true;
        update($('liveAutoMessage'),'Session expirée. Reconnecte-toi pour consulter les résultats du match.');
        return;
      }
      if(!response.ok)throw Error('HTTP '+response.status);
      const data=await response.json();
      failures=0;
      display(data);
      delay=data.active?2500:(data.status==='awaiting_video'?5000:10000);
    }catch(e){
      failures++;
      delay=Math.min(30000,3000*failures);
      update($('liveAutoMessage'),'Rafraîchissement temporairement indisponible ; nouvelle vérification automatique.');
    }finally{clearTimeout(timer);schedule();}
  }
  refresh();
})();
