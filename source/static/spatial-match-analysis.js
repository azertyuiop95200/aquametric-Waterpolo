/* AquaMetric reviewed-shot explorer. Original coordinates, not random pixels.
   Pool viewBox x=50..550, y=50..405 represents normalized attack half 0..100.
   The heat layer is merely a density visualization of the exact saved points. */
(() => {
  const $ = id => document.getElementById(id);
  const pitch=$('spatialPitch');
  if (!pitch) return;
  const dataset=$('spatialDataset'), segmentsJson=$('videoSegmentsDataset');
  let points=[], segments=[];
  try {points=JSON.parse(dataset.textContent);}catch(e) {points=[];}
  try {segments=JSON.parse(segmentsJson.textContent);}catch(e){segments=[];}
  const svgNS='http://www.w3.org/2000/svg';
  const glows=$('spatialGlows'),dots=$('spatialPoints'),selected=$('spatialSelected');
  const field={left:50,top:50,width:500,height:355};
  const shots=new Set(['goal','shot_on_target','shot_off_target','shot_blocked']);
  const colors={goal:'#f97316',shot_on_target:'#0e7490',save:'#0e7490',
    shot_off_target:'#d946ef',shot_blocked:'#e11d48',recovery:'#16a34a',
    turnover:'#b91c1c',pass_complete:'#38bdf8'};
  const label={goal:'But',shot_on_target:'Tir cadré',shot_off_target:'Tir manqué',
    shot_blocked:'Tir contré',save:'Arrêt',turnover:'Perte de balle',
    recovery:'Récupération',pass_complete:'Passe'};
  const selects=['mapSide','mapKind','mapPeriod','mapPlayer','mapMode'].map($);
  const evtUrl=point=>point.proof_url || '';
  const fmt=seconds=>{
    const n=Math.max(0,Number(seconds)||0);
    return String(Math.floor(n/60)).padStart(2,'0')+':'+String(Math.floor(n%60)).padStart(2,'0');
  };
  const pos=point=>({x:field.left+point.x*field.width/100,
                     y:field.top+point.y*field.height/100});
  const create=(parent,type,props)=>{
    const node=document.createElementNS(svgNS,type);
    Object.entries(props).forEach(([k,v])=>node.setAttribute(k,String(v)));
    parent.appendChild(node);return node;
  };
  function filtered(){
    const [side,kind,period,player]=selects.map(s=>s.value);
    return points.filter(p=>
      (side==='all'||p.side===side) &&
      (kind==='all'||(kind==='shots'?shots.has(p.event_type):p.event_type===kind)) &&
      (period==='all'||String(p.period)===period) &&
      (player==='all'||String(p.player_id||'')===player)
    );
  }
  function draw(){
    const data=filtered(),mode=$('mapMode').value;
    glows.replaceChildren();dots.replaceChildren();
    data.forEach(p=>{
      const xy=pos(p);
      if(mode!=='points'){
        const blob=create(glows,'circle',{cx:xy.x,cy:xy.y,r:43,
          fill:'url(#shotDensity)',opacity:.68});
        const hint=document.createElementNS(svgNS,'title');
        hint.textContent='Densité visuelle calculée à partir du point mesuré';
        blob.appendChild(hint);
      }
      if(mode!=='heat'){
        const dot=create(dots,'circle',{cx:xy.x,cy:xy.y,r:6,
          fill:colors[p.event_type]||'#f8fafc',
          stroke:p.side==='against'?'#1a2449':'#f8fafc', 'stroke-width':2});
        const title=document.createElementNS(svgNS,'title');
        title.textContent=`${label[p.event_type]||p.event_type}, Q${p.period}, ${fmt(p.second)} – ${p.player||'joueuse non attribuée'} – X ${p.x}, Y ${p.y}`;
        dot.appendChild(title);
      }
    });
    const selectedShots=data.filter(x=>shots.has(x.event_type));
    $('mapCount').textContent=selectedShots.length+' tir(s) localisé(s)';
    $('mapFilteredCount').textContent=data.length+' position(s) confirmée(s) visibles avec ces filtres.';
    const proof=$('spatialProofList');proof.replaceChildren();
    const title=document.createElement('h3');title.textContent='Points mesurés et liens vers les preuves';proof.appendChild(title);
    if(!data.length){
      const empty=document.createElement('p');empty.className='evidence-note';
      empty.textContent='Aucun point confirmé avec les filtres sélectionnés. Cela ne signifie pas que le match ne contient aucune action.';
      proof.appendChild(empty);return;
    }
    data.forEach(p=>{
      const row=document.createElement('div');row.className='event-row';
      const time=document.createElement('strong');time.textContent='Q'+p.period+' · '+fmt(p.second);row.appendChild(time);
      const detail=document.createElement('span');detail.textContent=(label[p.event_type]||p.event_type)+
        ' · '+(p.player||'Joueuse non attribuée')+' · ('+p.x+' %, '+p.y+' %) · '+(p.side==='for'?'équipe':'adversaire');
      row.appendChild(detail);
      if(evtUrl(p)){
        const a=document.createElement('a');a.href=evtUrl(p);a.textContent='Revoir';a.rel='noopener';
        if(/^https:\/\//.test(a.href))a.target='_blank';
        row.appendChild(a);
      }
      proof.appendChild(row);
    });
  }
  selects.forEach(sel=>sel.addEventListener('change',draw));
  draw();

  const xInput=$('coordX'),yInput=$('coordY');
  const hint=$('spatialPointMessage');
  const currentPoint=$('spatialSelected');
  const clickSurface=$('spatialClickSurface');
  if(clickSurface&&xInput&&yInput){
    clickSurface.addEventListener('click',event=>{
      const pt=pitch.createSVGPoint();pt.x=event.clientX;pt.y=event.clientY;
      const matrix=pitch.getScreenCTM();
      if(!matrix)return;
      const location=pt.matrixTransform(matrix.inverse());
      if(location.x<field.left||location.x>field.left+field.width||
         location.y<field.top||location.y>field.top+field.height)return;
      const x=Math.round((location.x-field.left)/field.width*10000)/100;
      const y=Math.round((location.y-field.top)/field.height*10000)/100;
      xInput.value=String(x);yInput.value=String(y);
      currentPoint.setAttribute('cx',String(location.x));
      currentPoint.setAttribute('cy',String(location.y));
      currentPoint.setAttribute('visibility','visible');
      hint.textContent='Position préparée : X '+x+' %, Y '+y+' % (0=près de la cage). Elle sera enregistrée seulement lorsque tu confirmeras une action ci-dessous.';
    });
    $('spatialClear')?.addEventListener('click',()=>{
      xInput.value='';yInput.value='';
      currentPoint.setAttribute('visibility','hidden');
      hint.textContent='Point effacé. Tu peux enregistrer une action sans coordonnées, mais elle ne figurera pas sur la carte.';
    });
  }

  const select=$('reviewSegmentSelect');
  const target=$('reviewSegmentPlayer');
  const segmentInput=$('reviewSegmentId');
  const periodInput=$('reviewPeriod');
  const timeInput=$('reviewSecond');
  const updateClock=()=>{
    const n=Math.max(0,Number(timeInput?.value)||0);
    const clock=$('reviewTimeText');
    if(clock)clock.textContent=fmt(n)+' · instant local de cette vidéo';
  };
  const desiredStart=()=>{
    const query=new URLSearchParams(window.location.search);
    const t=Number(query.get('t')||0);
    return Number.isFinite(t)&&t>=0&&t<12*3600?t:0;
  };
  function showSegment(){
    if(!select||!target||!segments.length)return;
    const ix=Number(select.value);
    const source=segments[ix];
    if(!source)return;
    const primary=source.id===null;
    if(segmentInput)segmentInput.value=primary?'':String(source.id);
    if(periodInput)periodInput.value=String(source.period||1);
    target.replaceChildren();
    const link=document.createElement('a');
    const starting=desiredStart();
    if(source.play_url){
      const video=document.createElement('video');
      video.id='reviewLocalVideo';video.controls=true;video.preload='metadata';
      video.playsInline=true;video.className='video-frame';
      video.src=source.play_url;
      video.addEventListener('loadedmetadata',()=>{if(starting)video.currentTime=starting;});
      video.addEventListener('timeupdate',()=>{
        if(document.activeElement!==timeInput){
          timeInput.value=String(Math.round(video.currentTime*10)/10);
          updateClock();
        }
      });
      target.appendChild(video);
    }else if(source.embed){
      const iframe=document.createElement('iframe');
      iframe.id='reviewVideo';iframe.className='video-frame';
      iframe.src=source.embed+'&rel=0'+(starting?'&start='+Math.floor(starting):'');
      iframe.title='Replay '+(source.label||'');
      iframe.allow='autoplay; encrypted-media; picture-in-picture';
      iframe.allowFullscreen=true;target.appendChild(iframe);
    }else{
      const message=document.createElement('p');
      message.textContent='Ce lien externe n’est pas intégrable ici. Ouvre-le pour relever les actions.';
      target.appendChild(message);
    }
    if(source.video_url){
      link.href=source.video_url;link.textContent='Ouvrir cette vidéo à la source';
      link.target='_blank';link.rel='noopener';target.appendChild(link);
    }
    updateClock();
  }
  if(select&&segments.length){
    const qs=new URLSearchParams(window.location.search),chosen=qs.get('segment');
    const ix=segments.findIndex(s=>String(s.id??'primary')===chosen);
    if(ix>=0)select.value=String(ix);
    select.addEventListener('change',showSegment);showSegment();
    window.addEventListener('message',event=>{
      const player=$('reviewVideo');
      if(!player||event.source!==player.contentWindow ||
         !/^https:\/\/(?:www\.)?youtube(?:-nocookie)?\.com$/.test(event.origin))return;
      let msg=event.data;
      if(typeof msg==='string'){try{msg=JSON.parse(msg);}catch(e){return;}}
      const seconds=Number(msg?.info?.currentTime);
      if(Number.isFinite(seconds)&&seconds>0 && document.activeElement!==timeInput){
        timeInput.value=String(Math.round(seconds*10)/10);updateClock();
      }
    });
  }
})();
