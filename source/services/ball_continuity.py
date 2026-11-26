"""Full-ledger ball candidate association. No athlete, ball or event is certified.
Coordinates are normalized image pixels, not metres. Thresholds are experimental.
"""
import gzip
import json
from math import hypot, isfinite
from collections import Counter, defaultdict


def associate(rows, *, aspect=16/9, max_gap_s=.12, gate=.025, margin=.003, max_speed=1.5):
    if not all(isfinite(x) and x>0 for x in (aspect,max_gap_s,gate,margin,max_speed)):
        raise ValueError('Invalid association parameters')
    active={}; finished=[]; next_id=1; last_i=-1; last_t=-1.; counts=Counter(); bins=defaultdict(Counter)
    def distance(x,y):return hypot(x,y/aspect)
    def close(k):finished.append(active.pop(k))
    def unique(options):
        options=sorted(options)
        return options[0][1] if options and (len(options)==1 or options[1][0]-options[0][0]>=margin) else None
    for row in rows:
        i=row['frame']; t=float(row['second'])
        if type(i) is not int or i!=last_i+1 or not isfinite(t) or t<0 or t<=last_t:raise ValueError('Invalid sequential frame ledger')
        b=bins[int(t//10)]; b['frames']+=1; counts['frames']+=1
        candidates=[]
        for x,y,c in row.get('ball_candidates',[]):
            x,y=float(x),float(y)
            if not (isfinite(x) and isfinite(y) and 0<=x<=1 and 0<=y<=1):raise ValueError('Invalid ball coordinates')
            candidates.append((x,y,c))
        for k in list(active):
            if row.get('cut') or t-active[k]['points'][-1][1]>max_gap_s+1e-8:close(k)
        fwd=defaultdict(list); rev=defaultdict(list)
        for k,tr in active.items():
            p=tr['points']; a=p[-1]; dt=t-a[1]; vx=vy=0.
            if len(p)>=2:
                z=p[-2]; d=a[1]-z[1]; vx=(a[2]-z[2])/d;vy=(a[3]-z[3])/d
            for j,(x,y,c) in enumerate(candidates):
                dx=x-a[2];dy=y-a[3];raw=distance(dx,dy)
                if raw>max_speed*dt+gate:continue
                residual=distance(dx-vx*dt,dy-vy*dt)
                if len(p)>=2 and residual>gate:continue
                # Colour is weak evidence: red/white visibility can change in flight.
                score=(residual if len(p)>=2 else raw)+.2*raw+(.006 if c!=tr['colour'] else 0)
                fwd[k].append((score,j));rev[j].append((score,k))
        used=set(); accepted=set()
        for k,options in fwd.items():
            j=unique(options)
            if j is None or unique(rev[j])!=k:continue
            x,y,c=candidates[j];active[k]['points'].append((i,t,x,y,c));active[k]['colour']=c;used.add(j);accepted.add(k)
        # Never bridge an ambiguous association: terminate competing fragments.
        for k in list(fwd):
            if k not in accepted:close(k)
        for j,(x,y,c) in enumerate(candidates):
            if j in used:continue
            active[next_id]={'id':next_id,'colour':c,'points':[(i,t,x,y,c)]};next_id+=1
        for key,val in [('candidate_frames',bool(candidates)),('associated_frames',bool(accepted)),('ambiguous_frames',any(len(v)>1 for v in fwd.values()) or any(len(v)>1 for v in rev.values())),('observations',len(candidates)),('links',len(accepted))]:
            counts[key]+=int(val);b[key]+=int(val)
        last_i,last_t=i,t
    for k in list(active):close(k)
    # Stability is a diagnostic only: a float or cap may also remain visible.
    support=set(); multi=Counter(); qualified=[]
    for tr in finished:
        p=tr['points'];n=len(p);duration=p[-1][1]-p[0][1]
        if n<4 or duration<.12-1e-8:continue
        qualified.append({'id':tr['id'],'start_s':p[0][1],'end_s':p[-1][1],'observations':n,'missing_frames':p[-1][0]-p[0][0]+1-n,'image_displacement':round(distance(p[-1][2]-p[0][2],p[-1][3]-p[0][3]),5)})
        for q in p:support.add(q[0]);multi[q[0]]+=1
    counts['persistent_candidate_frames']=len(support);counts['unique_persistent_candidate_frames']=sum(v==1 for v in multi.values())
    # All observations are preserved; never count a missing frame as a detection.
    if sum(len(r['points']) for r in finished)!=counts['observations']:raise RuntimeError('Ball observation reconciliation failed')
    return {'scope':'ball_candidates_not_verified','counts':dict(counts),'tracklets':len(finished),'persistent_tracklets':len(qualified),'bins':[{'start_s':k*10,**v} for k,v in sorted(bins.items())],'tracks':finished,'review_examples':sorted(qualified,key=lambda r:-r['observations'])[:20]}


def analyze(path):
    with gzip.open(path,'rt',encoding='utf8') as f:return associate(json.loads(line) for line in f)
