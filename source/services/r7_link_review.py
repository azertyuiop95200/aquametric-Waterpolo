"""Conservative candidate links between R7 fragments. Never merge sports observations."""
from collections import defaultdict
from math import hypot
import cv2
from services.head_flow_tracking import _flow, scan_head_flow

VERSION='r7-fragment-links-v1'

def unique(rows,margin):
    rows=sorted(rows)
    return rows[0] if rows and (len(rows)==1 or rows[1][0]-rows[0][0]>margin) else None

def propose(result, images):
    """Images are the exact chronological BGR samples of the original scan.
    Look across at most two missing samples, no invented points; inspect all
    competing observations. Return link proposals, not new tracks or identities.
    """
    frames=result['frames']; tracks=result['tracks']
    if len(frames)!=len(images) or not 1<=len(frames)<=75:raise ValueError('Fenêtre incohérente.')
    if len({t['id'] for t in tracks})!=len(tracks):raise ValueError('Pistes dupliquées.')
    times={f['second']:i for i,f in enumerate(frames)}
    if len(times)!=len(frames):raise ValueError('Temps dupliqués.')
    gray=[cv2.cvtColor(f,cv2.COLOR_BGR2GRAY) for f in images]
    h,w=gray[0].shape;scale=h/720
    if any(f.shape!=(h,w) for f in gray):raise ValueError('Dimensions variables.')
    starts=defaultdict(set);ends=defaultdict(list)
    for t in tracks:
        pts=t['points']
        if t['kind']!='head' or not pts:continue
        starts[times[pts[0]['second']]].add(t['id'])
        ends[times[pts[-1]['second']]].append((t['id'],pts[-1]))
    # Only genuine terminal fragments can be sources; future data only ranks retrospective reviews.
    edges=[];used_end=set();used_start=set()
    for j in range(1,len(frames)):
        if not starts[j]:continue
        ds=[d for d in frames[j]['detections'] if d['kind']=='head']
        if not ds:continue
        prior=[]
        for i in range(max(0,j-3),j):
            if frames[j]['second']-frames[i]['second']>.24+1e-6 or any(frames[k]['scene_reset'] for k in range(i+1,j+1)):continue
            es=[(tid,p) for tid,p in ends[i] if tid not in used_end]
            points=[(p['x']*w,p['y']*h) for _,p in es]
            for k in range(i+1,j+1):
                valid=[a for a,p in enumerate(points) if p is not None]
                vals=_flow(gray[k-1],gray[k],[points[a] for a in valid])
                points=[None]*len(points)
                for a,p in zip(valid,vals):
                    # No path through another observed head in a missing sample.
                    if p is not None and (k==j or not any(hypot(p[0]-d['x']*w,p[1]-d['y']*h)<12*scale for d in frames[k]['detections'] if d['kind']=='head')):points[a]=p
            prior.extend((tid,i,pt,p) for (tid,pt),p in zip(es,points) if p is not None)
        reverse=defaultdict(list);forward={}
        for k,(tid,i,pt,p) in enumerate(prior):
            choices=[]
            for q,d in enumerate(ds):
                err=hypot(p[0]-d['x']*w,p[1]-d['y']*h)
                if err<=12*scale:choices.append((err,q));reverse[q].append((err,k))
            best=unique(choices,6*scale)
            if best:forward[k]=best
        for k,(err,q) in forward.items():
            tid,i,pt,p=prior[k];target=ds[q]['track_id']
            best=unique(reverse[q],6*scale)
            if best is None or best[1]!=k or target not in starts[j] or target in used_start:continue
            # Reverse from the actual new observation, not the predicted endpoint.
            b=(ds[q]['x']*w,ds[q]['y']*h)
            for a in range(j,i,-1):
                b=_flow(gray[a],gray[a-1],[b])[0] if b is not None else None
            if b is None:continue
            residual=hypot(b[0]-pt['x']*w,b[1]-pt['y']*h)
            if residual>12*scale:continue
            edges.append(dict(from_track_id=tid,to_track_id=target,from_second=frames[i]['second'],to_second=frames[j]['second'],missing_samples=j-i-1,forward_error_px=round(err,3),reverse_error_px=round(residual,3),status='review_candidate_not_verified'))
            used_end.add(tid);used_start.add(target)
    return dict(engine=VERSION,links=edges,identity_verified=False,statistical_use_allowed=False,note='Liens rétrospectifs à revoir, aucune piste fusionnée ni point interpolé.')

def scan_head_flow_with_links(frames):
    pairs=[];size=0
    for t,f in frames:
        size+=f.nbytes
        if len(pairs)>=75 or size>128*1024*1024:raise ValueError('Fenêtre de revue trop volumineuse ; réduire le nombre d’images.')
        pairs.append((t,f))
    result=scan_head_flow(iter(pairs))
    result['fragment_link_review']=propose(result,[f for _,f in pairs])
    return result
