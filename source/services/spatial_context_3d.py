"""Bridge reviewed shot context to the shared 3D engine.
Every trajectory, height, speed, posture and counterfactual is a hypothesis.
No future observation is used to infer a better decision.
"""
from math import hypot
from copy import deepcopy
from .collective_review import num, context
from .shot_context_review import point_at
from .spatial_replay import review,number

LIMIT=4
TRIALS=32


def available(snapshot):
    s=snapshot.get('shot_context') or {}
    ctx=s.get('context')
    if ctx is None or ctx!=context(snapshot):return None,[]
    rows=[r for r in s.get('rows',[]) if r.get('complete_geometry') is True and r.get('keeper_id') in r.get('defenders',{}) and num(r.get('goal_width_m')) and abs(r['goal_width_m']-3)<1e-6]
    return ctx,rows


def prepare(snapshot,raw):
    ctx,rows=available(snapshot)
    if ctx is None or raw.get('binding')!=ctx or raw.get('hypotheses_reviewed') is not True:raise ValueError('Contexte périmé ou hypothèses non confirmées.')
    eid=raw.get('event_id')
    a=next((x for x in rows if type(eid) is int and x['event']['id']==eid),None)
    if a is None:raise ValueError('Tir revu, gardienne, défense complète et but de 3 m requis.')
    L,W=ctx['length_m'],ctx['width_m'];g=a['goal_x'];o=a['shot']['origin'];t=a['shot']['second']
    z=number(raw.get('release_height_m'),0,3)
    h=number(raw.get('defender_height_m'),0,3)
    radius=number(raw.get('radius_m'),.15,1.8)
    speed=number(raw.get('horizontal_speed_mps'),2,30)
    sigma=number(raw.get('sigma_m'),0,2)
    if raw.get('motion_mode')!='stationary_hypothesis':raise ValueError('Hypothèse de défense immobile requise.')
    note=raw.get('evidence')
    if not isinstance(note,str) or not 3<=len(note.strip())<=300:raise ValueError('Justification des hypothèses requise.')
    # Positions x/y from existing reviewed context; vertical positions and radii supplied.
    # A stationary model does not assert that the athletes were stationary.
    defs=[dict(id=i,position=[*v,h],velocity=[0,0,0],radius=radius,confidence=1.) for i,v in sorted(a['defenders'].items())]
    poses=raw.get('reach_segments') or {}
    if not isinstance(poses,dict) or not set(poses)<=set(a['defenders']):raise ValueError('Postures hypothétiques invalides.')
    for d in defs:
        if d['id'] in poses:
            segments=poses[d['id']]
            if not isinstance(segments,list) or len(segments)>3:raise ValueError('Maximum trois segments de portée par défenseure.')
            d['reach_segments']=segments
    def option(i,kind,target):
        duration=hypot(target[0]-o[0],target[1]-o[1])/speed
        if not .15<=duration<=2:return None
        return dict(id=i,kind=kind,target=target,duration_s=duration)
    opts=[]
    for label,y in [('y-moins',W/2-1.0),('centre',W/2),('y-plus',W/2+1.0)]:
        for height_label,zz in [('bas',.2),('haut',.7)]:
            v=option(label+'-'+height_label,'shot',[g,y,zz])
            if v:opts.append(v)
    # Receivers must be explicitly selected and observed at the decision instant.
    receivers=raw.get('receivers') or []
    if not isinstance(receivers,list) or len(receivers)>3 or any(not isinstance(i,str) for i in receivers) or len(set(receivers))!=len(receivers):raise ValueError('Receveuses invalides.')
    roster={f"{p['side']}:{p['cap_number']}":p for p in snapshot['advanced_motion']['players']}
    receiver_z=number(raw.get('receiver_height_m'),0,3) if receivers else None
    for i in receivers:
        if i not in ctx['ids'] or i==a['shot']['identity'] or not i.startswith(a['event']['side']+':') or i not in roster:raise ValueError('Receveuse revue de la même équipe requise.')
        p=point_at(roster[i],t,L,W)
        if p is None:raise ValueError('Receveuse non suivie à cet instant.')
        v=option('passe-'+i,'pass',[*p,receiver_z])
        if v:opts.append(v)
    if not any(o['kind']=='shot' for o in opts):raise ValueError('Aucun tir dans la fenêtre de vol du modèle.')
    # The engine requires a reference ID. It is not the observed actual destination.
    data=dict(source='manual_video',decision_second=t,length_m=L,width_m=W,goal_x=g,start=[*o,z],sigma_m=sigma,complete_defence=True,chosen=opts[0]['id'],defenders=defs,options=opts)
    sequence=None
    if raw.get('reception_s') is not None:
        delay=number(raw['reception_s'],0,1.5)
        budget=number(raw['budget_s'],.15,8) if raw.get('budget_s') is not None else None
        sequence=dict(reception_s=delay,budget_s=budget,receiver_velocities={v['id']:[0,0,0] for v in opts if v['kind']=='pass'})
    result=review(data,trials=TRIALS,goal_map=dict(keeper_id=a['keeper_id'],speed=speed),sequence=sequence)
    signature=dict(event=a['event'],shot=a['shot'],goal_x=g,goal_width_m=a['goal_width_m'],defenders=a['defenders'],keeper_id=a['keeper_id'],receivers={i:point_at(roster[i],t,L,W) for i in receivers})
    result.update(event_id=eid,period=a['event']['period'],scope='hypothetical_from_reviewed_planar_context',actual_target=None,reference_is_hypothetical=True,nominal_horizontal_speed_mps=speed,evidence=note.strip(),calibration_error_m=None)
    # Store canonical JSON-compatible results; no repeated expensive evaluation on GET.
    import json
    return json.loads(json.dumps(signature,allow_nan=False)),json.loads(json.dumps(result,allow_nan=False))


def append(snapshot,raw):
    ctx,_=available(snapshot)
    signature,result=prepare(snapshot,raw)
    old=snapshot['automatic']['summary'].get('spatial_3d_reviews') or {}
    rows=list(old.get('rows',[])) if old.get('binding')==ctx else []
    rows=[r for r in rows if r.get('result',{}).get('event_id')!=result['event_id']]
    if len(rows)>=LIMIT:raise ValueError('Quatre simulations maximum.')
    return dict(binding=deepcopy(ctx),rows=rows+[dict(signature=signature,result=result)])


def build(snapshot, *, local_source):
    import json
    out=dict(status='unavailable',context=None,events=[],rows=[],reason='Tirs contextualisés et défense complète nécessaires.')
    if not local_source:return out
    ctx,available_rows=available(snapshot)
    if ctx is None:return out
    out.update(status='ready',context=ctx,events=[dict(id=a['event']['id'],second=a['shot']['second'],identity=a['shot']['identity'],period=a['event']['period']) for a in available_rows],reason='Aucune simulation 3D revue.')
    saved=snapshot['automatic']['summary'].get('spatial_3d_reviews') or {}
    if saved.get('binding')!=ctx:return out
    for r in saved.get('rows',[])[:LIMIT]:
        v=r.get('result',{});a=next((a for a in available_rows if a['event']['id']==v.get('event_id')),None)
        if a is None or v.get('model_version')!='replay-3':continue
        signature=dict(event=a['event'],shot=a['shot'],goal_x=a['goal_x'],goal_width_m=a['goal_width_m'],defenders=a['defenders'],keeper_id=a['keeper_id'])
        receiver_ids=(r.get('signature') or {}).get('receivers',{})
        roster={f"{p['side']}:{p['cap_number']}":p for p in snapshot['advanced_motion']['players']}
        signature['receivers']={i:point_at(roster[i],a['shot']['second'],ctx['length_m'],ctx['width_m']) if i in roster else None for i in receiver_ids}
        if r.get('signature')!=json.loads(json.dumps(signature)):continue
        out['rows'].append(v)
    if out['rows']:out.update(status='experimental_partial',reason='')
    return out
