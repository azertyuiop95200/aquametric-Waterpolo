"""Nearest-player geometry, not a model of control or interception probability.
All coordinates are in the common metric pool plane. No assumptions about speed,
reach, reaction, or legal availability. Explicit position error is a bound, not SD.
"""
from math import ceil, hypot, isfinite


def number(v):
    return type(v) in (int, float) and isfinite(v)


class SpaceAccumulator:
    def __init__(self, length, width, attackers, defenders, *, cell_m=2., local_radius_m=3., position_error_m=None):
        if not all(number(v) and v > 0 for v in (length, width, cell_m, local_radius_m)) or not .5 <= cell_m <= 5 or not 15 <= length <= 40 or not 10 <= width <= 25:
            raise ValueError('invalid metric dimensions or spatial thresholds')
        if position_error_m is not None and (not number(position_error_m) or position_error_m < 0):
            raise ValueError('position error must be an explicit nonnegative bound or null')
        self.A, self.D = tuple(attackers), tuple(defenders)
        if not self.A or not self.D or len(set(self.A+self.D)) != len(self.A+self.D):
            raise ValueError('distinct fixed rosters required')
        self.error, self.radius, self.cell = position_error_m, local_radius_m, cell_m
        self.observed = 0.
        self.cells = []
        for i in range(ceil(length/cell_m)):
            for j in range(ceil(width/cell_m)):
                x,y=i*cell_m,j*cell_m
                w,h=min(cell_m,length-x),min(cell_m,width-y)
                self.cells.append(dict(x=x,y=y,w=w,h=h,nominal=[0.,0.,0.],robust=[0.,0.,0.]))
        self.local={i:dict(nominal=[0.,0.,0.],robust=[0.,0.,0.],attack_count=0.,defence_count=0.) for i in self.A}
        self.snapshot=None

    @staticmethod
    def _index(a,b,tol=1e-9):
        return 0 if a>b+tol else 1 if b>a+tol else 2

    def add(self, edges, start, end):
        # Called only by the shared possession loop on fully observed intervals.
        if not number(start) or not number(end) or end<=start or set(edges)!=set(self.A+self.D):
            raise ValueError('invalid complete interval')
        dt=end-start
        mid={i:tuple((p+q)/2 for p,q in zip(*v)) for i,v in edges.items()}
        drift={i:hypot(v[0][0]-v[1][0],v[0][1]-v[1][1])/2 for i,v in edges.items()}
        self.observed+=dt
        for c in self.cells:
            x,y=c['x']+c['w']/2,c['y']+c['h']/2
            d={i:hypot(x-p[0],y-p[1]) for i,p in mid.items()}
            k=self._index(min(d[i] for i in self.D),min(d[i] for i in self.A))
            c['nominal'][k]+=dt
            if self.error is not None:
                # Triangle inequality: bound distance over whole cell and interval.
                half=hypot(c['w'],c['h'])/2
                err={i:half+drift[i]+self.error for i in d}
                lo=lambda ids:min(max(0.,d[i]-err[i]) for i in ids)
                hi=lambda ids:min(d[i]+err[i] for i in ids)
                k=0 if hi(self.A)<lo(self.D) else 1 if hi(self.D)<lo(self.A) else 2
                c['robust'][k]+=dt
        counts={}
        for i,row in self.local.items():
            d={j:hypot(mid[i][0]-mid[j][0],mid[i][1]-mid[j][1]) for j in mid if j!=i}
            # Include the focal attacker in the local count, always exactly once.
            a=1+sum(d[j]<=self.radius for j in self.A if j!=i)
            b=sum(d[j]<=self.radius for j in self.D)
            row['attack_count']+=dt*a; row['defence_count']+=dt*b
            row['nominal'][self._index(a,b)]+=dt
            counts[i]={'attackers':a,'defenders':b}
            if self.error is not None:
                err={j:drift[i]+drift[j]+2*self.error for j in d}
                lower=lambda ids:sum(d[j]+err[j]<=self.radius for j in ids if j!=i)
                upper=lambda ids:sum(max(0.,d[j]-err[j])<=self.radius for j in ids if j!=i)
                a0,a1=1+lower(self.A),1+upper(self.A); b0,b1=lower(self.D),upper(self.D)
                k=0 if a0>b1 else 1 if b0>a1 else 2
                row['robust'][k]+=dt
        if self.snapshot is None:
            self.snapshot={'second':(start+end)/2,'local_counts':counts}

    def result(self):
        t=self.observed
        names=('attack','defence','neutral_or_unresolved')
        nominal={k:0. for k in names}; robust={k:0. for k in names}
        cells=[]
        for c in self.cells:
            row={k:c[k] for k in ('x','y','w','h')}; area=c['w']*c['h']
            for label,totals in (('nominal',nominal),('robust',robust)):
                available=t>0 and (label=='nominal' or self.error is not None)
                row[label]={k:v/t for k,v in zip(names,c[label])} if available else None
                if available:
                    for k,v in row[label].items(): totals[k]+=area*v
            cells.append(row)
        local=[]
        for i,r in self.local.items():
            local.append(dict(id=i,mean_attackers=r['attack_count']/t if t else None,
                              mean_defenders=r['defence_count']/t if t else None,
                              nominal_s=dict(zip(names,r['nominal'])) if t else None,
                              robust_s=dict(zip(names,r['robust'])) if t and self.error is not None else None))
        return dict(observed_s=t,cell_m=self.cell,local_radius_m=self.radius,position_error_bound_m=self.error,
                    nominal_mean_area_m2=nominal if t else None,
                    robust_mean_area_m2=robust if t and self.error is not None else None,
                    cells=cells,local=local,snapshot=self.snapshot,scope='nearest_distance_proxy_not_control')
