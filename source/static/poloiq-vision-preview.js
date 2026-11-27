/* PoloIQ detection preview; only raw object candidates, never scored sports events. */
(() => {
  const id=name=>document.getElementById(name);
  const form=id('poloiqFrameForm');
  if(!form)return;
  const state=id('poloiqState'),explain=id('poloiqExplain'),button=id('poloiqTestBtn');
  const picker=id('poloiqFrame'),result=id('poloiqResult'),canvas=id('poloiqPreview');
  const ctx=canvas.getContext('2d');
  let available=false,bitmap=null;
  let currentDetections=[];
  const colors={ball:'#f97316',goal:'#22c55e',goalie_red:'#ef4444',player_dark:'#2563eb',player_white:'#f8fafc'};
  const label={ball:'Ballon',goal:'Cage',goalie_red:'Gardienne rouge',
               player_dark:'Joueuse foncée',player_white:'Joueuse blanche'};
  function paint(){
    if(!bitmap){ctx.clearRect(0,0,canvas.width,canvas.height);return;}
    const max=1200,scale=Math.min(1,max/Math.max(bitmap.width,bitmap.height));
    canvas.width=Math.round(bitmap.width*scale);
    canvas.height=Math.round(bitmap.height*scale);
    ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);
    const px=canvas.width,py=canvas.height;
    for(const item of currentDetections){
      const [x1,y1,x2,y2]=item.bbox_normalized;
      const color=colors[item.class]||'#facc15';
      ctx.strokeStyle=color;ctx.lineWidth=Math.max(2,px/450);
      ctx.strokeRect(x1*px,y1*py,(x2-x1)*px,(y2-y1)*py);
      const txt=(label[item.class]||item.class)+' '+Math.round(item.confidence*100)+' %';
      ctx.font=Math.max(12,px/65)+'px system-ui';
      const width=ctx.measureText(txt).width+12;
      const bottom=Math.max(18,y1*py);
      ctx.fillStyle='#082134';
      ctx.fillRect(x1*px,bottom-19,width,19);
      ctx.fillStyle='#f8fafc';
      ctx.fillText(txt,x1*px+6,bottom-5);
    }
  }
  picker.addEventListener('change', async()=>{
    currentDetections=[];
    bitmap=null;
    const file=picker.files?.[0];
    if(!file){paint();return;}
    if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>6*1024*1024){
      result.textContent='Image JPG/PNG/WebP de 6 Mo maximum obligatoire.';paint();return;
    }
    try{
      bitmap=await createImageBitmap(file);
      paint();
      result.textContent='Image chargée. Aucun objet mesuré tant que tu n’as pas lancé le détecteur.';
    }catch(e){result.textContent="L'image ne peut pas être affichée.";}
  });
  fetch('/api/poloiq/readiness',{cache:'no-store'}).then(async r=>{
    if(!r.ok)throw Error('HTTP '+r.status);return r.json();
  }).then(data=>{
    available=!!data.configured;
    state.textContent=available?'Modèle de détection connecté':'Modèle à entraîner';
    explain.textContent=available?
      'Modèle connecté. Les résultats sont des boîtes d’objets à vérifier, pas des statistiques de match.' :
      (data.reason||'Le modèle n’est pas configuré sur ce serveur.');
    button.disabled=!available;
  }).catch(()=>{
    state.textContent='État inconnu';
    explain.textContent='Service de vision indisponible. Les cartes de tirs vérifiés restent utilisables.';
  });
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    const file=picker.files?.[0];
    if(!available||!file||file.size>6*1024*1024)return;
    button.disabled=true;
    result.textContent='Analyse d’une seule image en cours…';
    try{
      const body=new FormData();
      body.append('image',file);
      const response=await fetch('/api/matches/'+form.dataset.matchId+'/poloiq/frame',{
        method:'POST',body,credentials:'same-origin'});
      const payload=await response.json();
      if(!response.ok)throw Error(typeof payload.detail==='string'?payload.detail:('HTTP '+response.status));
      currentDetections=payload.detections||[];
      paint();
      result.textContent=currentDetections.length+' objet(s) détecté(s) et à vérifier ; aucun tir, but, exclusion ou résultat de match ajouté automatiquement.';
    }catch(e){
      currentDetections=[];paint();result.textContent='Test de détection impossible : '+e.message;
    }finally{button.disabled=!available;}
  });
})();
