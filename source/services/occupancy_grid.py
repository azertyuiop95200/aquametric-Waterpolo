"""Shared metric grid and observed movement timeline; no match-time extrapolation."""
from collections import defaultdict
from math import floor, ceil, hypot, isfinite

def _num(x):
    return type(x) in (float,int) and isfinite(x)

def _xy(p,length,width):
    return len(p)==2 and all(map(_num,p)) and 0<=p[0]<=length and 0<=p[1]<=width

def occupancy(segments, length, width, cell, start, end, gap=.26, speed=3.5):
    """Split each accepted straight segment at grid boundaries; exact time allocation."""
    if not all(map(_num,(length,width,cell,start,end,gap,speed))) or not 15<=length<=40 or not 10<=width<=25 or not .5<=cell<=5 or not 0<=start<end<=86400 or gap<=0 or speed<=0: raise ValueError("invalid map bounds")
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


def density(m):
    """Fixed legend; fraction of observed time per square metre."""
    for c in m['cells']:
        c['density_per_m2']=c['share']/(c['w']*c['h'])
        c['opacity']=min(1.,c['density_per_m2']/.25)
    return m


def observed_timeline(segments, *, bucket_s=60):
    """Only bins with accepted observations; absence is not zero movement.
    Caller supplies the same merged segments used for motion and occupancy.
    """
    if not _num(bucket_s) or not 5<=bucket_s<=600: raise ValueError('invalid bucket size')
    rows=defaultdict(lambda:[0.,0.]); last=-1.
    for seg in segments:
        for p,q in zip(seg,seg[1:]):
            t,u=p['second'],q['second']; dt=u-t
            if not all(map(_num,(t,u,p['x_m'],p['y_m'],q['x_m'],q['y_m']))) or not 0<=t<u<=86400 or t<last: raise ValueError('invalid timeline edge')
            last=u
            d=hypot(q['x_m']-p['x_m'],q['y_m']-p['y_m'])
            if dt>.26 or d/dt>3.5: continue
            for i in range(floor(t/bucket_s),ceil(u/bucket_s)):
                part=min(u,(i+1)*bucket_s)-max(t,i*bucket_s)
                if part>0:
                    rows[i][0]+=part; rows[i][1]+=d*part/dt
    return [{'start_s':i*bucket_s,'end_s':(i+1)*bucket_s,'observed_s':t,'distance_m':d,'mean_speed_mps':d/t} for i,(t,d) in sorted(rows.items())]
