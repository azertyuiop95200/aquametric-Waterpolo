"""Reviewed event-linked planar shot context, not a reconstruction of ball flight."""
from math import hypot, atan2, degrees
from .collective_review import context, num
from .possession_geometry import segment_distance
from .goalkeeper_geometry import snapshot as keeper_snapshot

SHOTS={'goal','shot_on_target','shot_off_target','shot_blocked','shot_unknown'}
LIMIT=12
TIME_TOL=.25


def primary_events(db,match,snapshot):
    """Only explicit primary-video positions; no cross-clip timestamp guessing."""
    from sqlalchemy import select
    from models import Event, EventPosition, MatchVideoSegment
    if match.video_source!='upload' or not match.video_path:return []
    primary=list(db.scalars(select(MatchVideoSegment).where(MatchVideoSegment.match_id==match.id,MatchVideoSegment.source_type=='upload',MatchVideoSegment.video_path==match.video_path)).all())
    if len(primary)>1:return []
    segment=primary[0].id if primary else None
    positions=db.scalars(select(EventPosition).join(Event,Event.id==EventPosition.event_id).where(Event.match_id==match.id)).all()
    pos={p.event_id:p for p in positions if p.segment_id==segment and p.provenance=='manual_verified'}
    ids={e['id']:e.get('review') or {} for e in snapshot.get('identity_analysis',{}).get('event_rows',[])}
    rows=[]
    for e in snapshot.get('verified_events',[]):
        p=pos.get(e['id']); a=ids.get(e['id'],{}); side=e.get('perspective')
        if not p or e.get('event_type') not in SHOTS|{'save'} or side not in ('for','against') or type(p.period) is not int or not 1<=p.period<=8 or not num(p.segment_second) or p.segment_second<0:continue
        if a.get('provenance') not in ('coach_review','confirmed_roster') or a.get('side')!=side or type(a.get('cap_number')) is not int:continue
        rows.append(dict(id=e['id'],kind=e['event_type'],second=p.segment_second,period=p.period,side=side,identity=f"{side}:{a['cap_number']}"))
    return rows


def available(snapshot):
    ctx=context(snapshot)
    if ctx is None:return None,[],[]
    s=snapshot['automatic']['summary']; raw=s['metric_field_map']; reviewed=(s.get('identity_reviews') or {}).get('shots',{})
    shots=[]
    for i,p in enumerate(raw.get('shots',[])):
        r=reviewed.get(str(i),{}); side,cap=r.get('side'),r.get('cap_number')
        x,y,t=p.get('x_m'),p.get('y_m'),p.get('second')
        if p.get('provenance')!='manual_review_candidate' or r.get('provenance')!='coach_review' or not r.get('evidence') or side not in ('for','against') or type(cap) is not int or not all(map(num,(x,y,t))) or not (0<=x<=ctx['length_m'] and -ctx['width_m']/2<=y<=ctx['width_m']/2 and 0<=t<=28800):continue
        shots.append(dict(index=i,second=t,origin=[x,y+ctx['width_m']/2],identity=f"{side}:{cap}",side=side))
    events=snapshot.get('primary_shot_events',[])
    return ctx,shots,events


def validate(raw,ctx,shots,events):
    if not isinstance(raw,dict) or raw.get('shot_link_reviewed') is not True or raw.get('roster_reviewed') is not True:raise ValueError('Lien tir-action et effectif défensif à revoir.')
    si,ei=raw.get('shot_index'),raw.get('event_id')
    if type(si) is not int or type(ei) is not int:raise ValueError('Choisir un tir et une action confirmée.')
    p=next((x for x in shots if x['index']==si),None);e=next((x for x in events if x['id']==ei and x['kind'] in SHOTS),None)
    if p is None or e is None or p['identity']!=e['identity'] or abs(p['second']-e['second'])>TIME_TOL:raise ValueError('Tir et action incompatibles : même vidéo, identité et instant requis (0,25 s).')
    goal=raw.get('goal_x'); width=raw.get('goal_width_m');D=raw.get('defenders');keeper=raw.get('keeper') or None;span=raw.get('assumed_lateral_span_m')
    other='against' if e['side']=='for' else 'for'
    if not num(goal) or goal not in (0,ctx['length_m']) or not num(width) or not 0<width<=ctx['width_m'] or abs(p['origin'][0]-goal)<1e-8:raise ValueError('But attaqué et largeur revus nécessaires.')
    if not isinstance(D,list) or not 1<=len(D)<=8 or any(not isinstance(i,str) or not i.startswith(other+':') for i in D) or len(set(D))!=len(D) or not set(D)<=set(ctx['ids']) or keeper is not None and keeper not in D:raise ValueError('Effectif défensif revu invalide.')
    if span is not None and (keeper is None or not num(span) or not 0<span<=3):raise ValueError('Envergure hypothétique invalide.')
    note=raw.get('evidence')
    if not isinstance(note,str) or not 3<=len(note.strip())<=300:raise ValueError('Justification visuelle requise.')
    save=None; sid=raw.get('save_event_id')
    if sid is not None:
        if type(sid) is not int:raise ValueError('Arrêt invalide.')
        save=next((x for x in events if x['id']==sid and x['kind']=='save'),None)
        if save is None or keeper is None or save['identity']!=keeper or save['period']!=e['period'] or save['side']!=other or not 0<=save['second']-p['second']<=1.5 or e['kind'] not in ('shot_on_target','shot_unknown'):raise ValueError('Arrêt incompatible avec le tir et la gardienne.')
    return dict(shot_index=si,event_id=ei,goal_x=goal,goal_width_m=width,defenders=D,keeper=keeper,assumed_lateral_span_m=span,save_event_id=sid,evidence=note.strip(),shot_link_reviewed=True,roster_reviewed=True),p,e,save


def point_at(player,t,L,W):
    """A point on accepted linear edges; reject conflicting boundaries."""
    hits=[]
    for seg in player.get('segments',[]):
        for a,b in zip(seg,seg[1:]):
            s,u=a['second'],b['second'];x,y=a['x_m'],a['y_m'];X,Y=b['x_m'],b['y_m']
            if not all(map(num,(s,u,x,y,X,Y))) or not 0<u-s<=.26 or not s<=t<=u or hypot(X-x,Y-y)/(u-s)>3.5:continue
            if not (0<=x<=L and 0<=X<=L and 0<=y<=W and 0<=Y<=W):continue
            f=(t-s)/(u-s);hits.append((x+(X-x)*f,y+(Y-y)*f))
    if not hits or any(hypot(p[0]-hits[0][0],p[1]-hits[0][1])>1e-6 for p in hits):return None
    return hits[0]


def describe(snapshot,ctx,w,p,e,save):
    L,W=ctx['length_m'],ctx['width_m'];o=p['origin'];g=(w['goal_x'],W/2);d=abs(g[0]-o[0]);half=w['goal_width_m']/2
    roster={f"{x['side']}:{x['cap_number']}":x for x in snapshot['advanced_motion']['players']}
    positions={i:point_at(roster[i],p['second'],L,W) for i in w['defenders'] if i in roster and roster[i].get('metrics')}
    visible={i:v for i,v in positions.items() if v is not None};complete=len(visible)==len(w['defenders'])
    near=[hypot(v[0]-o[0],v[1]-o[1]) for v in visible.values()]
    field=[v for i,v in visible.items() if i!=w['keeper']]
    k=visible.get(w['keeper'])
    return dict(event=e,save=save,shot=p,goal_x=g[0],goal_width_m=w['goal_width_m'],defenders=visible,expected_defenders=len(w['defenders']),complete_geometry=complete,keeper_id=w['keeper'],keeper=keeper_snapshot(o,k,g[0],L,W,w['goal_width_m'],w['assumed_lateral_span_m']) if k is not None else None,assumed_lateral_span_m=w['assumed_lateral_span_m'],distance_to_goal_m=hypot(d,o[1]-g[1]),goal_angle_deg=degrees(atan2(g[1]+half-o[1],d)-atan2(g[1]-half-o[1],d)),nearest_visible_defender_m=min(near) if near else None,centerline_field_gap_m=min(segment_distance(v,o,g) for v in field) if complete and w['keeper'] is not None and field else None,goal_probability=None,evidence=w['evidence'])


def append(snapshot,raw):
    ctx,shots,events=available(snapshot)
    if ctx is None or raw.get('binding')!=ctx:raise ValueError('Calibration ou identités modifiées.')
    old=snapshot['automatic']['summary'].get('shot_context_reviews') or {}
    rows=list(old.get('rows',[])) if old.get('binding')==ctx else []
    w,p,e,save=validate(raw,ctx,shots,events)
    if len(rows)>=LIMIT or any(r['shot_index']==w['shot_index'] or r['event_id']==w['event_id'] or w['save_event_id'] is not None and r.get('save_event_id')==w['save_event_id'] for r in rows):raise ValueError('Doublon ou limite de douze revues.')
    w['signature']=[p,e,save]
    return dict(binding=ctx,rows=rows+[w])


def build(snapshot, *, local_source):
    out=dict(status='unavailable',context=None,shots=[],events=[],rows=[],reason='Calibration locale et identités revues nécessaires.')
    if not local_source:return out
    ctx,shots,events=available(snapshot)
    if ctx is None:return out
    out.update(status='ready',context=ctx,shots=shots,events=events,length_m=ctx['length_m'],width_m=ctx['width_m'],reason='Aucun tir confirmé relié à une revue cartographique.')
    saved=snapshot['automatic']['summary'].get('shot_context_reviews') or {}
    if saved.get('binding')!=ctx:return out
    used_s=set();used_e=set();used_save=set()
    for raw in saved.get('rows',[])[:LIMIT]:
        try:
            w,p,e,save=validate(raw,ctx,shots,events)
            if raw.get('signature')!=[p,e,save] or p['index'] in used_s or e['id'] in used_e or save is not None and save['id'] in used_save:continue
            used_s.add(p['index']);used_e.add(e['id'])
            if save is not None:used_save.add(save['id'])
            out['rows'].append(describe(snapshot,ctx,w,p,e,save))
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):continue
    if out['rows']:out.update(status='experimental_partial',reason='')
    out['excluded_reviews']=max(0,len(saved.get('rows',[]))-len(out['rows']))
    return out
