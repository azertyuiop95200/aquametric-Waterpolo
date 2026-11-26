(() => {
"use strict";
const $=id=>document.getElementById("sbx-"+id);
const data=JSON.parse($("data").textContent), base=data.baseline.observations, reference=data.baseline.result;
const clone=x=>JSON.parse(JSON.stringify(x)), L=base.length_m,W=base.width_m;
const canvas=$("canvas"),ctx=canvas.getContext("2d");
const initial=()=>({start:clone(base.start),carrier_velocity:[0,0,0],defenders:clone(base.defenders),
 options:base.options.map(o=>({...clone(o),receiver_velocity:[0,0,0]})),delay_s:0,ball_speed_m_s:12,suggest:true});
let edit=initial(), result=null, resultInput=null, history=[], selected="carrier", drag=null, timer=null, revision=0, busy=false, pending=false, refineNext=false, animation=0;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)), fmt=(v,n=2)=>Number.isFinite(v)?v.toFixed(n):"—";
const num=id=>$(id).valueAsNumber;
const add=(el,tag,txt)=>{const a=document.createElement(tag);a.textContent=txt;el.append(a);return a};
function entities(){
 return [{key:"carrier",label:"Ballon / porteuse",p:edit.start,v:edit.carrier_velocity,color:"#ffd36a"},
 ...edit.defenders.map((d,i)=>({key:"d"+i,label:"Défense · "+d.id,p:d.position,v:d.velocity,color:"#ff727c"})),
 ...edit.options.map((o,i)=>({key:"o"+i,label:(o.kind==="pass"?"Cible de passe · ":"Cible de tir · ")+o.id,p:o.target,
 v:o.kind==="pass"?o.receiver_velocity:null,option:o,color:o.kind==="pass"?"#61ddff":"#73e9a7"}))];
}
function selectedEntity(){return entities().find(e=>e.key===selected)||entities()[0]}
function sync(){
 const e=selectedEntity(); selected=e.key;$("entity").value=selected;
 ["x","y","z"].forEach((id,i)=>{$(id).value=fmt(e.p[i]);$(id).disabled=!!e.option&&e.option.kind==="shot"&&e.option.id!==base.chosen&&i===0});
 ["vx","vy","vz"].forEach((id,i)=>{$(id).disabled=!e.v;$(id).value=e.v?fmt(e.v[i]):""});
 $("flight").disabled=!e.option;$("flight").value=e.option?e.option.duration_s:"";
 $("delay").value=edit.delay_s;$("delay-value").value=fmt(edit.delay_s,1)+" s";$("speed").value=edit.ball_speed_m_s;$("suggest").checked=edit.suggest;
}
function remember(){history.push(clone(edit));if(history.length>40)history.shift();$("undo").disabled=false}
function limit(e,p){
 const q=[clamp(p[0],0,L),clamp(p[1],0,W),clamp(p[2],0,3)];
 if(e.option?.kind==="shot"&&e.option.id!==base.chosen){q[0]=base.goal_x;q[1]=clamp(q[1],W/2-1.5,W/2+1.5);q[2]=clamp(q[2],0,.9)}
 return q;
}
function setPoint(e,p){e.p.splice(0,3,...limit(e,p))}
function projection(){
 const a=num("rotation")*Math.PI/180,b=num("tilt")*Math.PI/180,k=390/Math.hypot(L,W);
 return {project(p){const x=p[0]-L/2,y=p[1]-W/2;return [380+k*(x*Math.cos(a)-y*Math.sin(a)),235+k*((x*Math.sin(a)+y*Math.cos(a))*Math.sin(b)-p[2]*Math.cos(b))]},
 inverse(q,z){const u=(q[0]-380)/k,v=((q[1]-235)/k+z*Math.cos(b))/Math.sin(b);return [L/2+u*Math.cos(a)+v*Math.sin(a),W/2-u*Math.sin(a)+v*Math.cos(a),z]}};
}
function draw(){
 const {project}=projection();ctx.clearRect(0,0,760,470);
 function line(ps,color,width=1,fill=null,dashed=false){ctx.beginPath();ps.forEach((p,i)=>{const q=project(p);i?ctx.lineTo(...q):ctx.moveTo(...q)});ctx.setLineDash(dashed?[5,4]:[]);if(fill){ctx.closePath();ctx.fillStyle=fill;ctx.fill()}ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();ctx.setLineDash([])}
 function dot(p,color,r,name,outline=false){const [x,y]=project(p);ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.strokeStyle=color;ctx.lineWidth=2;ctx.fillStyle=color;if(outline)ctx.stroke();else ctx.fill();if(name){ctx.font="12px sans-serif";ctx.fillStyle="#fff";ctx.fillText(name,x+r+3,y-5)}}
 line([[0,0,0],[L,0,0],[L,W,0],[0,W,0]],"#80cde5",2,"#174d68");
 for(let x=2;x<L;x+=2)line([[x,0,0],[x,W,0]],"#39738a");
 for(let y=2;y<W;y+=2)line([[0,y,0],[L,y,0]],"#39738a");
 const g=base.goal_x,c=W/2;line([[g,c-1.5,0],[g,c-1.5,.9],[g,c+1.5,.9],[g,c+1.5,0]],"#fff",3);
 const old=[base.start,...base.defenders.map(d=>d.position),...base.options.map(o=>o.target)];
 old.forEach(p=>dot(p,"#c0d3de",5,null,true));
 if(result&&resultInput===JSON.stringify(edit)){
  const t=num("playtime");
  for(const d of result.defenders){const p=d.position.map((x,i)=>x+d.velocity[i]*t);dot(p,"#ff727c",4,null,true)}
  for(const o of result.options){const color=o.id===base.chosen?"#5bbcff":o.generated?"#73e9a7":"#61ddff";line(o.path.map(p=>p.xyz_m),color,2,null,true);const i=Math.min(o.path.length-1,Math.round(t/o.flight_s*(o.path.length-1)));if(t<=o.flight_s)dot(o.path[i].xyz_m,color,3,null)}
 }
 for(const e of entities()){
  line([[e.p[0],e.p[1],0],e.p],e.color,1,null,true);
  dot(e.p,e.color,e.key===selected?9:6,e.label);
  if(e.v)line([e.p,e.p.map((p,i)=>p+e.v[i]*edit.delay_s)],e.color,2,null,true);
 }
 ctx.fillStyle="#c9e2ef";ctx.font="14px sans-serif";ctx.fillText("HYPOTHÈSE COACH · t avant geste = "+fmt(edit.delay_s,1)+" s",15,23);
}
function display(){
 $("rows").replaceChildren();
 if(!result||resultInput!==JSON.stringify(edit)){$("summary").textContent="Scène modifiée : résultats en attente de recalcul.";return}
 const options=[...result.options].sort((a,b)=>(b.clearance_m??-Infinity)-(a.clearance_m??-Infinity));
 $("summary").textContent=result.trials+" simulations / option · "+result.proposed_ids.length+" cibles de tir générées · "+(result.complete_defence?"couverture défensive déclarée complète":"couverture défensive insuffisante");
 for(const o of options){const tr=document.createElement("tr");$("rows").append(tr);
 const original=reference.options.find(x=>x.id===o.id);
 const delta=Number.isFinite(o.clearance_frequency)&&Number.isFinite(original?.clearance_frequency)?100*(o.clearance_frequency-original.clearance_frequency):null;
 add(tr,"td",o.id+(o.generated?" · proposé":" · variante"));
 add(tr,"td",fmt(o.clearance_m));
 add(tr,"td",o.clearance_frequency===null?"Non mesuré":fmt(o.clearance_frequency*100,1)+" % ["+o.simulation_interval.map(v=>fmt(v*100,1)).join("–")+"]");
 add(tr,"td",delta===null?"—":(delta>=0?"+":"")+fmt(delta,1)+" pts"+(result.trials!==reference.trials?" (aperçu)":""));
 add(tr,"td",o.clearance_m===null?"Données insuffisantes":(o.clearance_m>0?"Couloir dégagé dans le modèle":"Obstruction possible")+(o.closest_defender?" · "+o.closest_defender+" à "+fmt(o.closest_time_s)+" s":"")+" · vol "+fmt(o.flight_s)+" s · vitesse "+fmt(o.launch_speed_m_s)+" m/s");
 }
}
function changed(refine=false){
 revision++;pending=true;refineNext=refine;resultInput=null;$("export").disabled=true;
 $("status").textContent="Recalcul en attente…";display();draw();clearTimeout(timer);timer=setTimeout(calculate,220);
}
async function calculate(){
 if(busy||!pending)return;busy=true;pending=false;
 const token=revision,payload=clone(edit),key=JSON.stringify(payload);payload.refine=refineNext;
 $("status").textContent=payload.refine?"Calcul affiné…":"Recalcul interactif…";
 try{const res=await fetch("/matches/"+data.match+"/spatial/"+data.event+"/sandbox",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
 const json=await res.json();if(!res.ok)throw Error(typeof json.detail==="string"?json.detail:"Calcul impossible");
 if(token===revision){result=json;resultInput=key;$("status").textContent="Hypothèse recalculée (aucune observation modifiée).";$("export").disabled=false;display();draw()}
 }catch(e){if(token===revision){result=null;resultInput=null;$("status").textContent=e.message;display();draw()}}
 finally{busy=false;if(pending){clearTimeout(timer);timer=setTimeout(calculate,100)}}
}
const select=$("entity");for(const e of entities()){const o=add(select,"option",e.label);o.value=e.key}
select.addEventListener("change",()=>{selected=select.value;sync();draw()});
for(const id of ["x","y","z","vx","vy","vz","flight"])$(id).addEventListener("change",()=>{
 const value=num(id);if(!Number.isFinite(value)){sync();return}const e=selectedEntity();remember();
 if(["x","y","z"].includes(id)){const p=[...e.p];p[["x","y","z"].indexOf(id)]=value;setPoint(e,p)}
 else if(id==="flight"&&e.option)e.option.duration_s=clamp(value,.15,2);
 else if(e.v)e.v[["vx","vy","vz"].indexOf(id)]=clamp(value,-3,3);
 sync();changed();
});
for(const id of ["delay","speed","suggest"])$(id).addEventListener(id==="delay"?"input":"change",()=>{
 if(id==="delay"){edit.delay_s=num(id);$("delay-value").value=fmt(edit.delay_s,1)+" s"}
 if(id==="speed"){if(!Number.isFinite(num(id)))return;remember();edit.ball_speed_m_s=clamp(num(id),2,30);sync()}
 if(id==="suggest"){remember();edit.suggest=$(id).checked}changed();
});
function pointer(e){const r=canvas.getBoundingClientRect();return [(e.clientX-r.left)*760/r.width,(e.clientY-r.top)*470/r.height]}
canvas.addEventListener("pointerdown",e=>{
 const q=pointer(e),{project}=projection();
 const nearest=entities().map(x=>({x,d:Math.hypot(...project(x.p).map((v,i)=>v-q[i]))})).sort((a,b)=>a.d-b.d)[0];
 if(nearest.d>18)return;remember();selected=nearest.x.key;const p=project(nearest.x.p);drag={id:e.pointerId,offset:[q[0]-p[0],q[1]-p[1]]};canvas.setPointerCapture(e.pointerId);sync();draw();
});
canvas.addEventListener("pointermove",e=>{if(!drag||drag.id!==e.pointerId)return;const q=pointer(e),ent=selectedEntity();setPoint(ent,projection().inverse(q.map((v,i)=>v-drag.offset[i]),ent.p[2]));sync();changed()});
for(const event of ["pointerup","pointercancel","lostpointercapture"])canvas.addEventListener(event,()=>{drag=null});
for(const id of ["rotation","tilt","playtime"])$(id).addEventListener("input",draw);
$("reset").addEventListener("click",()=>{remember();edit=initial();sync();changed()});
$("undo").addEventListener("click",()=>{if(history.length){edit=history.pop();$("undo").disabled=!history.length;sync();changed()}});
$("refine").addEventListener("click",()=>changed(true));
$("play").addEventListener("click",()=>{cancelAnimationFrame(animation);const start=performance.now();function frame(now){$("playtime").value=Math.min(2,(now-start)/1000);draw();if(now-start<2000)animation=requestAnimationFrame(frame)}animation=requestAnimationFrame(frame)});
$("export").addEventListener("click",()=>{if(!result||resultInput!==JSON.stringify(edit))return;const url=URL.createObjectURL(new Blob([JSON.stringify({mode:"coach_hypothesis",match:data.match,event:data.event,reference,edits:edit,result},null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download="scenario-"+data.event+".json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});
$("undo").disabled=true;sync();changed();
})();
