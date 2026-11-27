"""Manually reviewed post-change sequences, bound to current local metric analysis."""
from .collective_review import context, num
from .defensive_recovery import analyze_recovery

LIMIT=4
MAX_S=15.


def validate(raw, ctx):
    if not isinstance(raw,dict):raise ValueError('Revue de repli invalide.')
    before,after,a,b=(raw.get(k) for k in ('before_s','after_s','start_s','end_s'))
    period=raw.get('period');side=raw.get('losing_side');goal=raw.get('own_goal_x')
    if not all(map(num,(before,after,a,b))) or not 0<=before<after<=a<b<=28800 or b-a>MAX_S or after-before>MAX_S:
        raise ValueError('Bornes de contrôle et fenêtre de repli invalides (15 s maximum chacune).')
    if type(period) is not int or not 1<=period<=8 or side not in ('for','against') or not num(goal) or goal not in (0,ctx['length_m']):
        raise ValueError('Période, équipe ou but défendu invalide.')
    flags=('unique_change_reviewed','continuous_play_reviewed','roster_reviewed','field_players_only')
    if any(raw.get(k) is not True for k in flags):
        raise ValueError('Contrôles opposés, changement unique, jeu continu et effectif de champ à confirmer.')
    ids=raw.get('defenders')
    if not isinstance(ids,list) or not 1<=len(ids)<=7 or any(not isinstance(i,str) or not i.startswith(side+':') for i in ids) or len(set(ids))!=len(ids) or not set(ids)<=set(ctx['ids']):
        raise ValueError('Effectif de champ revu invalide.')
    note=raw.get('evidence')
    if not isinstance(note,str) or not 3<=len(note.strip())<=300:raise ValueError('Justification visuelle requise (3–300 caractères).')
    return dict(before_s=before,after_s=after,start_s=a,end_s=b,period=period,losing_side=side,own_goal_x=goal,defenders=ids,evidence=note.strip(),**{k:True for k in flags})


def append(snapshot,raw):
    ctx=context(snapshot)
    if ctx is None or raw.get('binding')!=ctx:raise ValueError('Calibration ou identités modifiées. Actualiser le rapport.')
    saved=snapshot['automatic']['summary'].get('recovery_reviews') or {}
    windows=list(saved.get('windows',[])) if saved.get('binding')==ctx else []
    w=validate(raw,ctx)
    # Disjoint evidence-to-recovery intervals even across periods.
    if len(windows)>=LIMIT or any(w['before_s']<old['end_s'] and old['before_s']<w['end_s'] for old in windows):
        raise ValueError('Quatre revues de transition maximum, sans chevauchement.')
    return dict(binding=ctx,windows=windows+[w])


def build(snapshot, *, local_source):
    out=dict(status='unavailable',reports=[],context=None,reason='Calibration locale et identités revues nécessaires.')
    if not local_source:return out
    ctx=context(snapshot)
    if ctx is None:return out
    out.update(status='ready',context=ctx,reason='Aucun repli explicitement revu.')
    saved=snapshot['automatic']['summary'].get('recovery_reviews') or {}
    if saved.get('binding')!=ctx:
        if saved:out['reason']='Calibration ou identités modifiées : anciennes revues non réutilisées.'
        return out
    try:
        windows=saved.get('windows',[])
        if not isinstance(windows,list) or len(windows)>LIMIT:raise ValueError('Limite dépassée.')
        last=-1.
        for i,raw in enumerate(sorted(windows,key=lambda w:w['before_s']),1):
            w=validate(raw,ctx)
            if w['before_s']<last:raise ValueError('Chevauchement.')
            last=w['end_s']; ident='R'+str(i);side=w['losing_side']
            # This ID denotes a local coach review, not a confirmed sporting event.
            evidence=dict(id=ident,source=ctx['source'],period=w['period'],before=side,after='against' if side=='for' else 'for',start_s=w['before_s'],end_s=w['after_s'],status='opposite_endpoints',exact_count=1)
            report=dict(source=ctx['source'],period=w['period'],start_s=w['before_s'],end_s=w['end_s'],length_m=ctx['length_m'],width_m=ctx['width_m'],players=snapshot['advanced_motion']['players'])
            r=analyze_recovery(report,evidence,dict(w,source=ctx['source'],transition_id=ident,provenance='coach_review'))
            report.pop('players');report['transitions']=[dict(id=ident,recovery=r,evidence=w['evidence'],before_s=w['before_s'],after_s=w['after_s'],losing_side=side)]
            out['reports'].append(report)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        out.update(status='invalid',reports=[],reason='Revues périmées ou incohérentes.')
        return out
    if out['reports']:out.update(status='experimental_partial',reason='')
    return out
