"""Audit segment metadata without assuming a verified source clock."""
from math import isfinite

def audit(manifest, tolerance_s=0.04):
    if not isfinite(tolerance_s) or tolerance_s < 0: raise ValueError('tolerance')
    def number(x):
        if isinstance(x,bool) or not isinstance(x,(int,float)) or not isfinite(x) or x<0: raise ValueError('invalid time')
        return x
    duration=number(manifest['source_duration_s']); prev=0; seen=set(); issues=[]; rows=[]
    for c in manifest['clips']:
        name=c['file']; start=number(c['source_start_s']); end=number(c['source_end_s']); actual=number(c['duration_s'])
        if name in seen or end<=start or actual<=0: raise ValueError('duplicate or empty clip')
        seen.add(name)
        gap=start-prev; delta=end-start-actual
        for key,value in [('boundary_gap_s',gap),('duration_delta_s',delta)]:
            if abs(value)>tolerance_s: issues.append({'clip':name,'kind':key,'seconds':value})
        rows.append({'clip':name,'declared_start_s':start,'declared_end_s':end,'duration_delta_s':delta})
        prev=end
    if not rows: raise ValueError('empty clips')
    if abs(prev-duration)>tolerance_s: issues.append({'kind':'source_end_delta_s','seconds':prev-duration})
    return {'clips':rows,'issues':issues,'offsets_verified':False,'status':'metadata_only','tolerance_s':tolerance_s}
