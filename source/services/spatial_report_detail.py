"""Report-only geometry and verified pass links; no second 3D model."""
from collections import Counter, defaultdict
from math import hypot, isfinite


def number(v):
    return type(v) in (int, float) and isfinite(v)


def map_scale(report):
    """Fixed density scale: fraction of observed time per square metre.
    Edge cells may be smaller; area normalization prevents misleading intensity.
    """
    for p in report['players']:
        m=p.get('map')
        if m is None:
            continue
        for c in m['cells']:
            c['density_per_m2']=c['share']/(c['w']*c['h'])
            c['opacity']=min(1., c['density_per_m2']/.25)
        p['video_coverage']=m['observed_s']/(report['end_s']-report['start_s'])
    return {'unit':'fraction_of_observed_time_per_m2','legend_max':.25,'scale_bar_m':5.,'cell_m':report.get('cell_m',2.)}


def spatial_options(result, length, width):
    """Reuse replay-1 outputs. Keep modeled alternatives distinct from actual events."""
    if result.get('model_version')!='replay-1':
        return []
    start=result.get('start'); chosen=result.get('chosen'); options=result.get('options',[])
    def valid(p):
        return isinstance(p,(tuple,list)) and len(p)==3 and all(map(number,p)) and 0<=p[0]<=length and 0<=p[1]<=width and 0<=p[2]<=3
    if not valid(start) or not isinstance(options,list):
        return []
    if any(not isinstance(o,dict) or not isinstance(o.get('id'),str) for o in options):
        return []
    ids=[o['id'] for o in options]
    if len(set(ids))!=len(ids) or chosen not in ids:
        return []
    rows=[]
    for o in options:
        target=o.get('target')
        if not valid(target) or o.get('kind') not in ('pass','shot'):
            continue
        known=result.get('complete_defence') is True and o.get('status') in ('clear_in_model','potential_obstruction')
        margin=o.get('clearance_m'); freq=o.get('clearance_frequency')
        rows.append({'id':o['id'],'kind':o['kind'],'chosen':o['id']==chosen,'target':list(target),
                     'planar_length_m':hypot(target[0]-start[0],target[1]-start[1]),
                     'clearance_m':margin if known and number(margin) else None,
                     'clearance_frequency':freq if known and number(freq) and 0<=freq<=1 else None,
                     'status':o['status'] if known else 'unknown','sport_probability':None})
    return rows if any(r['chosen'] for r in rows) else []


def pass_network(report, pass_summary, reviewed_links, *, team_to_side):
    """Consume validated pass_review summary, not raw candidates.
    reviewed_links: pass ID -> explicit same-action reviewed player identities.
    No inferred receiver from nearest track, no key-pass/assist double counting.
    Caller scopes pass summary and link provenance to the same owner/source/period.
    """
    if pass_summary is None:
        return None
    if set(team_to_side.values())!={'for','against'} or len(team_to_side)!=2:
        raise ValueError('explicit team mapping required')
    if pass_summary.get('source')!=report['source'] or pass_summary.get('period')!=report['period']:
        raise ValueError('pass summary source/period mismatch')
    if pass_summary.get('coverage_complete') is not False:
        raise ValueError('expected validated partial pass summary')
    actions={a['id']:a for a in report['actions']}
    edges=defaultdict(list); seen=set(); eligible=0; linked=0; excluded=Counter()
    for p in pass_summary.get('actions',[]):
        ident=p['id']
        if ident in seen: raise ValueError('duplicate pass ID')
        seen.add(ident)
        if p.get('state')!='observed_pass' or p.get('outcome')!='completed': continue
        t=p.get('release_first_free_s'); u=p.get('control_s')
        if not number(t) or not number(u) or not report['start_s']<=t<=u<report['end_s']: continue
        eligible+=1
        link=reviewed_links.get(ident)
        if not link or link.get('provenance')!='coach_review' or link.get('source')!=report['source'] or link.get('period')!=report['period']:
            excluded['identity_or_scope_missing']+=1; continue
        side=team_to_side.get(p.get('team')); a=link.get('sender_id'); b=link.get('receiver_id')
        if side is None or link.get('side')!=side or not all(isinstance(v,str) and v for v in (a,b)) or a==b:
            excluded['identity_conflict']+=1; continue
        event=actions.get(str(p.get('related_event_id')))
        if p.get('event_relation')=='same_action' and (not event or event.get('side')!=side or event.get('kind') not in ('pass_complete','key_pass','assist') or abs(event['second']-t)>.25):
            excluded['event_conflict']+=1; continue
        linked+=1; edges[(side,a,b)].append({'pass_id':ident,'second':t})
    return {'eligible_completed':eligible,'linked_completed':linked,'identity_coverage':linked/eligible if eligible else None,
            'edges':[{'side':s,'sender':a,'receiver':b,'count':len(items),'passes':items} for (s,a,b),items in sorted(edges.items())],
            'excluded':dict(excluded),'match_completion_rate':None,'scope':'reviewed_partial_passes'}
