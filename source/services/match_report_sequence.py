"""Assemble nonoverlapping source/period reports; keep sources non-additive."""
from collections import Counter, defaultdict
from math import hypot
try:
    from services.advanced_tracking import motion, transition
    from services.match_tactical_report import build_report, _num
    from services.possession_geometry import analyze_window
    from services.defensive_recovery import analyze_recovery
except ModuleNotFoundError as e:
    if e.name != 'services': raise
    from advanced_tracking import motion, transition
    from match_tactical_report import build_report, _num
    from possession_geometry import analyze_window
    from defensive_recovery import analyze_recovery


def _clip(segments, start, end):
    """Clip eligible metric edges to a window without repairing gaps."""
    for seg in segments:
        for p,q in zip(seg,seg[1:]):
            t,u=p['second'],q['second']; dt=u-t
            if not 0<dt<=.26 or hypot(q['x_m']-p['x_m'],q['y_m']-p['y_m'])/dt>3.5: continue
            a,b=max(start,t),min(end,u)
            if b<=a: continue
            def at(s):
                f=(s-t)/dt
                return {'second':s,'x_m':p['x_m']+f*(q['x_m']-p['x_m']),'y_m':p['y_m']+f*(q['y_m']-p['y_m'])}
            yield [at(a),at(b)]


def build_match_sequence(inputs):
    """Input is a list of build_report kwargs plus optional transition_records.
    Caller must provide one owner-scoped match; no aggregate across source IDs.
    Each transition record supplies reviewed metric endpoints and attack axis.
    """
    ordered=sorted(inputs,key=lambda x:(x['source'],x['period'],x['start']))
    reports=[]; previous={}; cumulative=defaultdict(Counter); event_ids=set()
    for raw in ordered:
        args=dict(raw); transitions=args.pop('transition_records',[]); windows=args.pop('possession_windows',[])
        key=(args['source'],args['period']); start,end=args['start'],args['end']
        if key in previous and start<previous[key]: raise ValueError('overlapping report windows')
        previous[key]=end
        report=build_report(**args)
        tracks={str(t['id']):t for t in args['metric'].get('tracks',[])}
        for row in report['actions']:
            if row['id'] in event_ids: raise ValueError('event repeated between source windows')
            event_ids.add(row['id'])
        for w in report['timeline']:
            cumulative[key].update(w['confirmed_counts']); w['source_period_cumulative']=dict(cumulative[key]); w['movement']=[]
            for p in report['players']:
                m=None
                if p['metrics'] is not None:
                    clipped=list(_clip(p['segments'],w['start_s'],w['end_s']))
                    # No sprint/acceleration across bucket cuts; full-window values stay in player report.
                    result=motion(clipped,sprint_mps=args['sprint_mps'],min_sprint_s=args['min_sprint_s'])
                    m={k:result[k] for k in ('observed_s','distance_m','mean_speed_mps')}
                    m['coverage']=m['observed_s']/(w['end_s']-w['start_s'])
                w['movement'].append({'side':p['side'],'cap_number':p['cap_number'],'metrics':m})
        seen=set(); report['transitions']=[]
        for record in transitions:
            evidence=record['evidence']; ident=evidence.get('id'); a,b=evidence.get('start_s'),evidence.get('end_s')
            if ident is None or ident in seen or evidence.get('source')!=key[0] or evidence.get('period')!=key[1] or not all(map(_num,(a,b))) or not start<=a<b<=end: continue
            seen.add(ident)
            if record.get('metric_endpoints_reviewed') is not True: continue
            value=transition(evidence,record['ball_start'],record['ball_end'],record['attack_axis'])
            recovery=None
            if record.get('recovery_review') is not None:
                recovery=analyze_recovery(report,evidence,record['recovery_review'])
            report['transitions'].append({'id':ident,'start_s':a,'end_s':b,**value,'recovery':recovery})
        report['possession_geometry']=[]; last=start; ids=set()
        for w in sorted(windows,key=lambda w:w['start_s']):
            if not isinstance(w.get('id'),str) or not w['id'] or w['id'] in ids or w['start_s']<last:
                raise ValueError('duplicate or overlapping possession subwindows')
            report['possession_geometry'].append(analyze_window(report,w))
            last=w['end_s']; ids.add(w['id'])
        reports.append(report)
    return {'scope':'source_period_reports_not_full_match_totals','reports':reports,'global_totals':None,'game_duration_s':None}
