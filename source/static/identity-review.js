(() => {
 const root=document.getElementById('identityReview');if(!root)return;
 const save=document.getElementById('identitySave'),status=document.getElementById('identityStatus'),video=document.getElementById('identityVideo');
 root.querySelectorAll('.identity-seek').forEach(btn=>btn.onclick=()=>{if(video){video.currentTime=Number(btn.dataset.second);video.pause();video.scrollIntoView({block:'nearest'});}});
 save.onclick=async()=>{const reviews={tracks:{},shots:{},events:{}};for(const row of root.querySelectorAll('.identity-row')){
 const side=row.querySelector('.identity-side').value,cap=row.querySelector('.identity-cap').value,colour=row.querySelector('.identity-colour').value,evidence=row.querySelector('.identity-evidence').value.trim();
 if(!side)continue;if(!evidence){status.textContent='Ajouter une preuve visuelle pour la référence '+row.dataset.id;return;}
 if(cap&&(!Number.isInteger(Number(cap))||Number(cap)<1||Number(cap)>30)){status.textContent='Numéro invalide.';return;}
 reviews[row.dataset.kind][row.dataset.id]={side,cap_number:cap?Number(cap):null,colour,evidence};
 }
 save.disabled=true;status.textContent='Recalcul des statistiques…';
 try{const res=await fetch(root.dataset.url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({analysis_id:Number(root.dataset.analysis),calibration_revision:root.dataset.revision,reviews})});const body=await res.json();if(!res.ok)throw new Error(typeof body.detail==='string'?body.detail:'Attribution refusée');location.reload()}catch(e){status.textContent=e.message;save.disabled=false;}
 };
})();