"""Owner-scoped reviewed windows for one local calibrated video.
The server supplies the current analysis, calibration and identity context.
No possession or tactical role is inferred from coordinates.
"""
import hashlib
import json
from math import isfinite
from .possession_geometry import analyze_window

LIMIT=4
MAX_WINDOW_S=15.


def context(snapshot):
    m=snapshot.get('advanced_motion') or {}
    s=(snapshot.get('automatic') or {}).get('summary') or {}
    raw=s.get('metric_field_map') or {}
    if m.get('status')!='experimental_partial' or raw.get('calibration_provenance')!='manual_reviewed_anchors' or not raw.get('revision') or m.get('analysis_id') is None or s.get('analysis_outcome')=='source_unverified':
        return None
    ids=sorted(f"{p['side']}:{p['cap_number']}" for p in m['players'] if p.get('metrics') and p['metrics'].get('observed_s',0)>0)
    if len(set(ids))!=len(ids): return None
    review_hash=hashlib.sha256(json.dumps((s.get('identity_reviews') or {}).get('tracks',{}),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return dict(analysis_id=m['analysis_id'],revision=raw['revision'],identity_hash=review_hash,ids=ids,length_m=m['length_m'],width_m=m['width_m'],source='analysis:'+str(m['analysis_id']))


def num(v): return type(v) in (int,float) and isfinite(v)


def validate(raw, ctx):
    if not isinstance(raw,dict): raise ValueError('Fenêtre invalide.')
    a,b=raw.get('start_s'),raw.get('end_s'); period=raw.get('period');side=raw.get('attacking_side')
    if not all(map(num,(a,b))) or not 0<=a<b<=28800 or b-a>MAX_WINDOW_S or type(period) is not int or not 1<=period<=8 or side not in ('for','against'):
        raise ValueError('Période ou fenêtre vidéo invalide (15 s maximum).')
    if raw.get('control_reviewed') is not True or raw.get('roster_reviewed') is not True:
        raise ValueError('Porteuse constante et effectifs complets à confirmer.')
    A,D=raw.get('attackers'),raw.get('defenders'); carrier=raw.get('carrier')
    other='against' if side=='for' else 'for'
    if not isinstance(A,list) or not isinstance(D,list) or not 1<=len(A)<=8 or not 1<=len(D)<=8 or any(not isinstance(i,str) for i in A+D) or len(set(A+D))!=len(A+D) or not set(A+D)<=set(ctx['ids']) or any(not i.startswith(side+':') for i in A) or any(not i.startswith(other+':') for i in D) or carrier not in A:
        raise ValueError('Identités revues et effectifs distincts requis.')
    goal=raw.get('goal_x')
    if not num(goal) or goal not in (0,ctx['length_m']): raise ValueError('But attaqué à préciser.')
    note=raw.get('evidence')
    if not isinstance(note,str) or not 3<=len(note.strip())<=300: raise ValueError('Justification visuelle requise (3–300 caractères).')
    w=dict(start_s=a,end_s=b,period=period,source=ctx['source'],attacking_side=side,attackers=A,defenders=D,carrier=carrier,goal_x=goal,control_reviewed=True,roster_reviewed=True,evidence=note.strip())
    center=raw.get('center');marker=raw.get('marker');keeper=raw.get('keeper')
    if center or marker:
        if center not in A or marker not in D:raise ValueError('Pointe et défenseure désignée à renseigner ensemble.')
        w['center_review']=dict(center=center,marker=marker,provenance='coach_review')
    if keeper:
        width=raw.get('goal_width_m');span=raw.get('assumed_lateral_span_m')
        if keeper not in D or keeper==marker or not num(width) or not 0<width<=ctx['width_m'] or (span is not None and (not num(span) or not 0<span<=3)):raise ValueError('Gardienne, largeur de but ou envergure hypothétique invalide.')
        w['keeper_review']=dict(keeper=keeper,goal_width_m=width,assumed_lateral_span_m=span,provenance='coach_review')
    return w


def build(snapshot, *, local_source):
    out=dict(status='unavailable',reports=[],context=None,reason='Calibration locale et identités revues nécessaires.')
    if not local_source:return out
    ctx=context(snapshot)
    if ctx is None:return out
    out.update(status='ready',context=ctx,reason='Aucune séquence collective revue.')
    saved=((snapshot.get('automatic') or {}).get('summary') or {}).get('collective_reviews') or {}
    if saved.get('binding')!=ctx:
        if saved:out.update(reason='Calibration ou identités modifiées : anciennes séquences non réutilisées.')
        return out
    windows=saved.get('windows',[])
    if not isinstance(windows,list) or len(windows)>LIMIT:return out
    last=-1.
    for i,raw in enumerate(sorted(windows,key=lambda w:w['start_s']),1):
        try:
            w=validate(raw,ctx)
            if w['start_s']<last:raise ValueError('Chevauchement.')
            last=w['end_s'];w['id']='Séquence '+str(i)
            report=dict(source=ctx['source'],period=w['period'],start_s=w['start_s'],end_s=w['end_s'],length_m=ctx['length_m'],width_m=ctx['width_m'],players=snapshot['advanced_motion']['players'])
            result=analyze_window(report,w)
            result['evidence']=w['evidence']
            report['possession_geometry']=[result]; report.pop('players')
            out['reports'].append(report)
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
            out.update(status='invalid',reports=[],reason='Séquences périmées ou incohérentes : revue nécessaire.')
            return out
    if out['reports']:out.update(status='experimental_partial',reason='')
    return out


def append(snapshot,raw):
    ctx=context(snapshot)
    if ctx is None or raw.get('binding')!=ctx: raise ValueError('Calibration ou identités modifiées. Actualiser le rapport.')
    s=snapshot['automatic']['summary']; saved=s.get('collective_reviews') or {}
    windows=list(saved.get('windows',[])) if saved.get('binding')==ctx else []
    w=validate(raw,ctx)
    if len(windows)>=LIMIT or any(w['start_s']<old['end_s'] and old['start_s']<w['end_s'] for old in windows):
        raise ValueError('Quatre séquences maximum, sans chevauchement.')
    # Store only validated inputs; revalidate on every report.
    clean={k:v for k,v in raw.items() if k in ('start_s','end_s','period','attacking_side','attackers','defenders','carrier','goal_x','control_reviewed','roster_reviewed','evidence','center','marker','keeper','goal_width_m','assumed_lateral_span_m')}
    return dict(binding=ctx,windows=windows+[clean])
