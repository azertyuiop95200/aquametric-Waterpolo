"""Read-only first release: reviewed motion in the original calibration frame."""
from math import isfinite
from .advanced_tracking import reviewed_motion
from .occupancy_grid import occupancy, density, observed_timeline


def build(snapshot):
    out={'status':'unavailable','players':[],'scope':'partial_calibrated_video','playing_seconds':None}
    auto=snapshot.get('automatic') or {}; summary=auto.get('summary') or {}
    raw=summary.get('metric_field_map') or {}; identity=snapshot.get('identity_analysis') or {}
    if summary.get('analysis_outcome')=='source_unverified' or raw.get('status')!='estimated' or raw.get('goal_relative') is not True:
        return out
    if not raw.get('revision') or identity.get('calibration_revision')!=raw['revision'] or identity.get('analysis_id') is None:
        return out
    L,W=raw.get('length_m'),raw.get('width_m')
    def finite(v): return type(v) in (float,int) and isfinite(v)
    if not finite(L) or not finite(W) or not 15<=L<=30 or not 12.5<=W<=20: return out
    tracks=[]; ids=set(); reviews=(summary.get('identity_reviews') or {}).get('tracks') or {}
    for tr in raw.get('tracks',[]):
        k=str(tr['id'])
        if k in ids: return out
        ids.add(k)
        segments=[]
        for seg in tr.get('segments',[]):
            run=[]
            for p in seg:
                t,x,y=(p.get(k) for k in ('second','x_m','y_m'))
                if all(map(finite,(t,x,y))) and t>=0 and 0<=x<=L and -W/2<=y<=W/2:
                    run.append({'second':t,'x_m':x,'y_m':y+W/2})
                else:
                    if run: segments.append(run); run=[]
            if run: segments.append(run)
        tracks.append({'id':tr['id'],'segments':segments})
    people=[]
    for p in identity.get('players',[]):
        side,cap=p.get('side'),p.get('cap_number')
        if side not in ('for','against') or type(cap) is not int or not 1<=cap<=30: continue
        keys=[]
        for k in p.get('track_ids',[]):
            r=reviews.get(str(k),{})
            if r.get('provenance')=='coach_review' and r.get('side')==side and r.get('cap_number')==cap and r.get('evidence'):
                keys.append(k)
        if keys: people.append({'side':side,'cap_number':cap,'track_ids':keys})
    if len({(p['side'],p['cap_number']) for p in people})!=len(people): return out
    try:
        rows=reviewed_motion({'tracks':tracks},{'players':people},sprint_mps=1.5,min_sprint_s=.35)
    except (ValueError,TypeError,KeyError,OverflowError):
        return out
    for row in rows:
        row['occupation']=None; row['movement_timeline']=None
        if row['metrics'] and row['metrics']['observed_s']:
            segments=row['segments']
            row['occupation']=density(occupancy(segments,L,W,2.,0.,86400.))
            row['movement_timeline']=observed_timeline(segments)
    return dict(out,status='experimental_partial' if any(r['metrics'] and r['metrics']['observed_s'] for r in rows) else 'unavailable',players=rows,length_m=L,width_m=W,analysis_id=identity['analysis_id'],sprint_mps=1.5,min_sprint_s=.35,coordinate_system='reference_goal_relative_shifted_lateral')
