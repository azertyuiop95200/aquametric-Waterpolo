(() => {
"use strict";
const $=id=>document.getElementById("sp-"+id);
const data=JSON.parse($("data").textContent), reviews=data.reviews;
let active=null, result=null;
const canvas=$("canvas"), ctx=canvas.getContext("2d");
const num=id=>Number($(id).value);
const text=(tag,value,parent)=>{const el=document.createElement(tag);el.textContent=value;parent.append(el);return el};
const fmt=(x,n=2)=>Number.isFinite(x)?x.toFixed(n):"non mesuré";
function draw(){
 ctx.clearRect(0,0,canvas.width,canvas.height);
 if(!result){ctx.fillStyle="#c9e2ef";ctx.font="17px sans-serif";ctx.fillText("Aucune scène métrique disponible",30,45);return}
 const a=num("rotate")*Math.PI/180,b=num("tilt")*Math.PI/180, L=result.length_m,W=result.width_m;
 const scale=Math.min(560/Math.hypot(L,W),320/Math.hypot(L,W));
 function project(p){const x=p[0]-L/2,y=p[1]-W/2,u=x*Math.cos(a)-y*Math.sin(a),v=x*Math.sin(a)+y*Math.cos(a);return [360+u*scale,235+v*Math.sin(b)*scale-p[2]*Math.cos(b)*scale]}
 function line(points,color,width=2,fill=null){ctx.beginPath();points.forEach((p,i)=>{const q=project(p);i?ctx.lineTo(...q):ctx.moveTo(...q)});if(fill){ctx.closePath();ctx.fillStyle=fill;ctx.fill()}ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke()}
 function dot(p,color,r,label){const q=project(p);ctx.beginPath();ctx.arc(...q,r,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();if(label){ctx.fillStyle="#fff";ctx.font="13px sans-serif";ctx.fillText(label,q[0]+r+3,q[1]-4)}}
 line([[0,0,0],[L,0,0],[L,W,0],[0,W,0]],"#80cde5",2,"#174d68");
 for(let x=2;x<L;x+=2)line([[x,0,0],[x,W,0]],"#39738a",.7);
 for(let y=2;y<W;y+=2)line([[0,y,0],[L,y,0]],"#39738a",.7);
 const g=result.goal_x,c=W/2;
 line([[g,c-1.5,0],[g,c-1.5,.9],[g,c+1.5,.9],[g,c+1.5,0]],"#ffffff",4);
 const t=num("time")/100;
 for(const d of result.defenders){
 const p=d.position.map((v,i)=>v+d.velocity[i]*t);
 const circle=Array.from({length:37},(_,i)=>[p[0]+d.radius*Math.cos(i*Math.PI/18),p[1]+d.radius*Math.sin(i*Math.PI/18),p[2]]);
 line(circle,"#ff7777",1);line([[p[0],p[1],0],p],"#e88181",1);dot(p,"#e85a66",6,d.id);
 }
 for(const o of result.options){
 const color=o.id===result.chosen?"#5bbcff":"#55e4a5";
 line(o.path.map(p=>p.xyz_m),color,o.id===result.chosen?3:2);
 const idx=Math.min(o.path.length-1,Math.round(t/o.flight_s*(o.path.length-1)));
 dot(o.path[idx].xyz_m,color,4,o.id);
 }
 dot(result.start,"#ffd36a",6,"Ballon");
 ctx.fillStyle="#c9e2ef";ctx.font="13px sans-serif";ctx.fillText("t = "+t.toFixed(2)+" s · projection métrique des hypothèses",16,24);
}
function display(){
 $("results").replaceChildren();
 if(!result){$("summary").textContent="Aucune relecture calculée pour cette action.";draw();return}
 const angles=result.goal_angles;
 $("summary").textContent=angles?"Distance horizontale au but : "+fmt(angles.distance_m)+" m · angle horizontal : "+fmt(angles.horizontal_deg,1)+"° · angle vertical au centre : "+fmt(angles.vertical_center_deg,1)+"°":"Angle non mesurable.";
 const status={unknown:"Couverture défensive insuffisante",clear_in_model:"Trajectoire dégagée dans le modèle",potential_obstruction:"Obstruction possible",uncertain:"Observation incertaine"};
 const choices=[...result.options].sort((a,b)=>(b.clearance_m??-Infinity)-(a.clearance_m??-Infinity));
 for(const o of choices){
 const el=text("article","",$("results"));
 text("h3",(o.id===result.chosen?"Geste réel · ":"Alternative · ")+o.id,el);
 text("p",status[o.status]||o.status,el);
 text("p","Marge de sécurité conservatrice : "+fmt(o.clearance_m)+" m · vol "+fmt(o.flight_s)+" s · vitesse initiale "+fmt(o.launch_speed_m_s)+" m/s · hauteur max. "+fmt(o.peak_height_m)+" m",el);
 if(o.kind==="shot")text("p",o.target_in_goal?"Cible située dans le cadre.":"Cible hors cadre ou trajectoire interrompue.",el);
 if(o.closest_defender)text("p","Défenseure la plus proche : "+o.closest_defender+" à "+fmt(o.closest_time_s)+" s (instant échantillonné).",el);
 text("p",o.clearance_frequency===null?"Fréquence de dégagement non calculable.":"Fréquence de dégagement conditionnelle : "+fmt(100*o.clearance_frequency,1)+" % (intervalle Monte-Carlo : "+o.simulation_interval.map(v=>fmt(v*100,1)).join("–")+" %).",el);
 text("p","Probabilité de but / de passe réussie : non calibrée.",el);
 }
 draw();
}
function load(){
 active=data.events.find(e=>String(e.id)===$("event")?.value)||null;
 const saved=active&&reviews[active.id];
 result=saved?.result||null;
 if($("form")){
 $("form").reset();$("status").textContent="";$("decision").value=active?.second??"";
 if(saved){const v=saved.observations;
 $("decision").value=v.decision_second??active.second;$("length").value=v.length_m;$("width").value=v.width_m;$("goal").value=v.goal_x===0?"zero":"end";
 ["x","y","z"].forEach((id,i)=>{$(id).value=v.start[i]});
 $("sigma").value=v.sigma_m;$("def").value=JSON.stringify(v.defenders,null,2);$("opt").value=JSON.stringify(v.options,null,2);
 $("chosen").value=v.chosen;$("complete").checked=v.complete_defence;
 }}
 $("time").value=0;display();
}
$("event")?.addEventListener("change",load);
for(const id of ["rotate","tilt","time"])$(id).addEventListener("input",draw);
$("seek").addEventListener("click",()=>{
 if(!active)return;const t=Math.max(0,active.second-3);
 if($("video")){$("video").currentTime=t;$("video").pause()}
 else if($("yt")&&data.embed){const u=new URL(data.embed);u.searchParams.set("start",String(Math.floor(t)));$("yt").src=u.href}
});
$("form")?.addEventListener("submit",async e=>{
 e.preventDefault();if(!active)return;const id=active.id;
 const button=e.target.querySelector("button[type=submit]");button.disabled=true;
 try{
 const observation={source:"manual_video",decision_second:num("decision"),length_m:num("length"),width_m:num("width"),goal_x:$("goal").value==="zero"?0:num("length"),
 start:[num("x"),num("y"),num("z")],sigma_m:num("sigma"),defenders:JSON.parse($("def").value),options:JSON.parse($("opt").value),
 chosen:$("chosen").value,complete_defence:$("complete").checked};
 $("status").textContent="Calcul en cours…";
 const response=await fetch("/matches/"+data.match+"/spatial/"+id,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(observation)});
 const json=await response.json();if(!response.ok)throw Error(typeof json.detail==="string"?json.detail:"Calcul impossible");
 reviews[id]={observations:observation,result:json};
 if(active?.id===id){result=json;display();$("status").textContent="Relecture enregistrée."}
 }catch(err){$("status").textContent="Impossible de calculer : "+err.message}
 finally{button.disabled=false}
});
load();
})();
