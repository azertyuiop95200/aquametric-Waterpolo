"""One reviewed video source/period: timeline and map, consuming existing 3D reviews.
Call only with owner-scoped data and one calibrated coordinate system.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from math import floor, ceil, hypot, isfinite
try:
    from services.advanced_tracking import reviewed_motion
    from services.spatial_report_detail import map_scale, spatial_options, pass_network
except ModuleNotFoundError as e:
    if e.name != 'services': raise
    from advanced_tracking import reviewed_motion
    from spatial_report_detail import map_scale, spatial_options, pass_network

KINDS={'goal':'shot','shot_on_target':'shot','shot_off_target':'shot','shot_blocked':'shot',
       'pass_complete':'pass','bad_pass':'pass','key_pass':'pass','assist':'pass'}


def _num(x):
    return type(x) in (float,int) and isfinite(x)


def _xy(p, length, width):
    return isinstance(p,(list,tuple)) and len(p)>=2 and all(map(_num,p[:2])) and 0<=p[0]<=length and 0<=p[1]<=width


def occupancy(segments, length, width, cell, start, end, gap=.26, speed=3.5):
    """Split each accepted straight segment at grid boundaries; exact time allocation."""
    cells=defaultdict(float); observed=0.; last=-1.
    for seg in segments:
        for a,b in zip(seg,seg[1:]):
            t,u=a['second'],b['second']; p=(a['x_m'],a['y_m']); q=(b['x_m'],b['y_m'])
            if not all(map(_num,(t,u))) or t<last or u<=t: raise ValueError('overlap or invalid time')
            last=u; dt=u-t
            if t<start or u>end or dt>gap or not _xy(p,length,width) or not _xy(q,length,width): continue
            dx,dy=q[0]-p[0],q[1]-p[1]
            if hypot(dx,dy)/dt>speed: continue
            cuts={0.,1.}
            for v,d,extent in ((p[0],dx,length),(p[1],dy,width)):
                if d:
                    cuts.update(f for k in range(1,ceil(extent/cell)) if 0<(f:=(k*cell-v)/d)<1)
            cuts=sorted(cuts)
            for a0,b0 in zip(cuts,cuts[1:]):
                f=(a0+b0)/2; x=p[0]+dx*f; y=p[1]+dy*f
                key=(min(ceil(length/cell)-1,floor(x/cell)),min(ceil(width/cell)-1,floor(y/cell)))
                cells[key]+=dt*(b0-a0)
            observed+=dt
    return {'observed_s':observed,'cells':[{'x':i*cell,'y':j*cell,'w':min(cell,length-i*cell),'h':min(cell,width-j*cell),'seconds':v,'share':v/observed} for (i,j),v in sorted(cells.items())]}


def adapt_metric(raw, *, source, period, reference_goal_x, lateral_sign):
    """metric_field.build_map uses goal-relative x and signed lateral y.
    Caller must confirm reference goal and lateral orientation in the 3D frame.
    Split on out-of-pool points rather than clipping or bridging them.
    """
    length,width=raw.get('length_m'),raw.get('width_m')
    if raw.get('goal_relative') is not True or raw.get('status')!='estimated' or not all(map(_num,(length,width))) or reference_goal_x not in (0,length) or lateral_sign not in (-1,1): raise ValueError('explicit coordinate alignment required')
    out=deepcopy(raw)
    for tr in out.get('tracks',[]):
        segments=[]
        for seg in tr.get('segments',[]):
            current=[]
            for p in seg:
                x,y=p.get('x_m'),p.get('y_m')
                if _num(x) and _num(y):
                    q=(x if reference_goal_x==0 else length-x,width/2+lateral_sign*y)
                    if _xy(q,length,width):
                        current.append(dict(p,x_m=q[0],y_m=q[1])); continue
                if current: segments.append(current); current=[]
            if current: segments.append(current)
        tr['segments']=segments
    out.update(coordinate_system='pool_metric_2d',source=source,period=period,reference_goal_x=reference_goal_x,lateral_sign=lateral_sign)
    return out


def build_report(*, source, period, start, end, length, width, metric, identity, events, spatial_reviews, sprint_mps, min_sprint_s, bucket_s=60, cell_m=2, pass_summary=None, pass_links=None, team_to_side=None):
    """events are explicit source/period-scoped confirmed event records, not candidates.
    spatial_reviews is saved_reviews() output, already owner/match filtered.
    No 3D model duplicated; joins use event ID + time + kind, not nearest time.
    """
    if not isinstance(source,str) or not source or type(period)!=int or not 1<=period<=8: raise ValueError('source/period required')
    if not all(map(_num,(start,end,length,width,bucket_s,cell_m))) or not 0<=start<end<=86400 or not 15<=length<=40 or not 10<=width<=25 or not 5<=bucket_s<=600 or not .5<=cell_m<=5: raise ValueError('invalid report bounds')
    if metric.get('coordinate_system')!='pool_metric_2d' or metric.get('source')!=source or metric.get('period')!=period: raise ValueError('reviewed metric source and period required')
    if ('length_m' in metric and metric['length_m']!=length) or ('width_m' in metric and metric['width_m']!=width): raise ValueError('calibration dimensions mismatch')
    tracks={str(t['id']):t for t in metric.get('tracks',[])}
    # Reject out-of-window tracks rather than silently mixing periods.
    for tr in metric.get('tracks',[]):
        for seg in tr.get('segments',[]):
            if any(not _num(p['second']) or not start<=p['second']<=end or not _xy((p['x_m'],p['y_m']),length,width) for p in seg): raise ValueError('track outside report scope')
    players=reviewed_motion(metric,identity,sprint_mps=sprint_mps,min_sprint_s=min_sprint_s)
    for p in players:
        if p['metrics'] is not None:
            p['map']=occupancy(p['segments'],length,width,cell_m,start,end)
        else: p['map']=None
    rows=[]; seen=set(); excluded=0
    for e in events:
        if e.get('source')!=source or e.get('period')!=period or str(e.get('confidence','')).upper() not in {'CONFIRMED','VERIFIED'}: continue
        t=e.get('second'); ident=str(e['id']) if e.get('id') is not None else ''
        if not ident or not _num(t) or not start<=t<end: continue
        if ident in seen: raise ValueError('duplicate verified event ID')
        seen.add(ident); kind=e.get('event_type'); row={'id':ident,'second':t,'kind':kind,'player_id':e.get('player_id'),'side':e.get('perspective'),'spatial':None}
        review=spatial_reviews.get(ident,spatial_reviews.get(e['id']))
        if review and kind in KINDS:
            r=review.get('result',{}); chosen=[o for o in r.get('options',[]) if o.get('id')==r.get('chosen')]
            d=r.get('decision_second'); origin=r.get('start')
            # Legacy 3D records have no verified segment association; withhold if not explicitly scoped.
            if (review.get('video_source')==source and review.get('period')==period and _num(d) and max(start,t-10)<=d<=t and r.get('length_m')==length and r.get('width_m')==width and len(chosen)==1 and chosen[0].get('kind')==KINDS[kind] and _xy(origin,length,width) and _xy(chosen[0].get('target'),length,width)):
                o=chosen[0]; row['spatial']={'origin':list(origin[:2]),'target':list(o['target'][:2]),'decision_second':d,'model_version':r.get('model_version'),'status':o.get('status') if r.get('complete_defence') else 'unknown','clearance_m':o.get('clearance_m') if r.get('complete_defence') else None,'goal_angles':r.get('goal_angles'),'alternative_count':len(r['options'])-1,'probability':None,'options':spatial_options(r,length,width)}
            else: excluded+=1
        rows.append(row)
    rows.sort(key=lambda r:(r['second'],r['id']))
    timeline=[]; cumulative=Counter()
    for i in range(ceil((end-start)/bucket_s)):
        a=start+i*bucket_s; b=min(end,a+bucket_s); selected=[r for r in rows if a<=r['second']<b]; counts=Counter(r['kind'] for r in selected); cumulative.update(counts)
        timeline.append({'start_s':a,'end_s':b,'event_ids':[r['id'] for r in selected],'confirmed_counts':dict(counts),'cumulative_confirmed_counts':dict(cumulative),'complete_event_coverage':None})
    report={'schema_version':'1.1','cell_m':cell_m,'source':source,'period':period,'start_s':start,'end_s':end,'length_m':length,'width_m':width,'players':players,'actions':rows,'timeline':timeline,'spatial_excluded':excluded,'scope':'partial_reviewed_video','metric_status':metric.get('status','unspecified'),'game_duration_s':None,'event_coverage':None}
    report['map_scale']=map_scale(report)
    report['pass_network']=pass_network(report,pass_summary,pass_links or {},team_to_side=team_to_side or {})
    return report
