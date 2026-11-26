"""Conservative candidate links across short gaps, never roster re-identification.
No imputation: measured observations remain unchanged. Candidate links require review.
"""
import gzip,json,math
from collections import defaultdict

def load_tracks(path):
    tracks={}; cuts=[]; last=-1; prev_t=-1.
    with gzip.open(path,'rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line); i=r['frame']; t=float(r['second'])
            if i!=last+1 or not math.isfinite(t) or t<=prev_t: raise ValueError('Non-contiguous frame ledger')
            last=i;prev_t=t
            if r.get('cut'):cuts.append(i)
            seen=set()
            for k,x,y,c in r.get('tracks',[]):
                if k in seen:raise ValueError('Duplicate track in frame')
                seen.add(k)
                if not all(math.isfinite(v) and 0<=v<=1 for v in (x,y)):raise ValueError('Invalid position')
                tr=tracks.setdefault(k,{'id':k,'colour':c,'points':[]})
                if tr['colour']!=c or (tr['points'] and tr['points'][-1][0]!=i-1):raise ValueError('Track reused after gap/colour change')
                tr['points'].append((i,t,x,y))
    return tracks,cuts,last+1

def propose_links(tracks,cuts,*,max_gap_s=.24,min_points=5,aspect=16/9,gate=.018,margin=.006):
    """Motion in normalized image coordinates; engineering defaults, not metres."""
    from bisect import bisect_right
    cuts=sorted(cuts); starts=defaultdict(list); ends=defaultdict(list)
    for k,tr in tracks.items():
        p=tr['points']
        if len(p)<min_points or tr['colour'] not in ('dark','light','red'):continue
        starts[bisect_right(cuts,p[0][0])].append(tr)
        ends[bisect_right(cuts,p[-1][0])].append(tr)
    def vel(p):
        a,b=p[0],p[-1]; dt=b[1]-a[1]
        return ((b[2]-a[2])/dt,(b[3]-a[3])/dt) if dt>0 else (0.,0.)
    def norm(x,y):return math.hypot(x,y/aspect)
    forward=defaultdict(list); reverse=defaultdict(list)
    for scene,rr in starts.items():
        ss=sorted(rr,key=lambda r:r['points'][0][1]); ee=sorted(ends[scene],key=lambda r:r['points'][-1][1]); left=0
        for b in ss:
            q=b['points']; t=q[0][1]
            while left<len(ee) and ee[left]['points'][-1][1]<t-max_gap_s: left+=1
            j=left
            while j<len(ee) and ee[j]['points'][-1][1]<t:
                a=ee[j];j+=1;p=a['points'];dt=t-p[-1][1]
                if dt>max_gap_s+1e-8 or a['colour']!=b['colour']:continue
                vx,vy=vel(p[-5:]);wx,wy=vel(q[:5]);dx=q[0][2]-p[-1][2];dy=q[0][3]-p[-1][3]
                raw=norm(dx,dy)
                if raw>gate+dt*.04:continue
                err=max(norm(dx-dt*vx,dy-dt*vy),norm(dx-dt*wx,dy-dt*wy))
                if err>gate:continue
                score=err+.25*raw+.01*dt
                r={'from':a['id'],'to':b['id'],'end_frame':p[-1][0],'start_frame':q[0][0],'end_s':p[-1][1],'start_s':t,'gap_s':round(dt,4),'missing_frames':q[0][0]-p[-1][0]-1,'colour':a['colour'],'error':round(err,6),'score':score,'status':'candidate_only'}
                forward[a['id']].append(r);reverse[b['id']].append(r)
    def unique(rows):
        rows=sorted(rows,key=lambda r:(r['score'],r['from'],r['to']))
        return rows[0] if len(rows)==1 or rows[1]['score']-rows[0]['score']>=margin else None
    result=[]
    for k,rows in forward.items():
        r=unique(rows)
        if r is not None and unique(reverse[r['to']]) is r:result.append(r)
    return sorted(result,key=lambda r:r['start_frame'])

def summarize(tracks,links,frames):
    parent={k:k for k in tracks}
    for r in links:parent[r['to']]=r['from']
    def root(k):
        while parent[k]!=k:k=parent[k]
        return k
    chains=defaultdict(list)
    for k,tr in tracks.items():chains[root(k)].append(tr)
    before=[len(t['points']) for t in tracks.values()]; after=[sum(len(t['points']) for t in rr) for rr in chains.values()]
    return {'processed_frames':frames,'raw_tracklets':len(before),'candidate_chains':len(after),'proposed_links':len(links),'observations_before':sum(before),'observations_after':sum(after),'longest_raw_observations':max(before,default=0),'longest_chain_observations':max(after,default=0),'missing_frames_not_filled':sum(r['missing_frames'] for r in links),'scope':'unverified_candidate_chains_not_player_identities','links':links}

def analyze(path):
    tracks,cuts,n=load_tracks(path);return summarize(tracks,propose_links(tracks,cuts),n)

if __name__=='__main__':
    import sys
    result=analyze(sys.argv[1]);open(sys.argv[2],'w',encoding='utf8').write(json.dumps(result,indent=2));print({k:v for k,v in result.items() if k!='links'})
