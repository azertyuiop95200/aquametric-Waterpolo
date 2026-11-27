"""Retrospective decisions based on reviewed downstream actions, not calibrated probabilities."""
from collections import Counter

TEAMS={'blancs','bleus'}
INDICES={'observed','not_observed','unknown'}

def require(ok,msg):
    if not ok: raise ValueError(msg)

def retrospective(reference, fps, rows):
    """Keep the original outcome immutable; produce a separate tactical interpretation."""
    by_id={r['id']:r for r in rows}
    result={}
    for r in rows:
        follow=r.get('retrospective')
        if follow is None:continue
        require(isinstance(follow,dict) and r['state'] in {'observed_pass','arrival_only'} and r['outcome']=='unknown','Revue rétrospective réservée à une issue inconnue.')
        k=r.get('control_frame')
        f=follow.get('next_frame');team=follow.get('next_team')
        require(type(k) is int and type(f) is int and k<f<=r['window_end_frame'] and team==r['control_team'] and team in TEAMS,'Action suivante et maîtrise incompatibles.')
        kind=follow.get('next_kind')
        require(kind in {'control','carry','pass','shot','restart'},'Nature de la suite invalide.')
        for key in ('path_consistent','distinct_receiver'):
            require(follow.get(key) is None or type(follow[key]) is bool,'Indice logique invalide.')
        for key in ('intervening_control','intervening_restart'):
            require(isinstance(follow.get(key),str) and follow[key] in INDICES,'Indice intermédiaire invalide.')
        for key in ('reason','alternative'):
            require(isinstance(follow.get(key),str) and 0<len(follow[key].strip())<=2000,'Justification et alternative requises.')
        evidence=follow.get('evidence')
        require(isinstance(evidence,list) and 1<=len(evidence)<=12 and all(isinstance(p,str) and p in r['evidence'] for p in evidence),'Preuves rétrospectives non rattachées.')
        linked=follow.get('next_pass_id')
        if linked is not None:
            require(isinstance(linked,str) and linked!=r['id'] and linked in by_id and kind=='pass','Lien de passe suivante invalide.')
            nxt=by_id[linked]
            require(nxt['state']=='observed_pass' and nxt['team']==team and nxt['release_last_held_frame']<=f<=nxt['release_first_free_frame'],'Chronologie de passe suivante incompatible.')
        origin=r.get('release_first_free_frame') if r['state']=='observed_pass' else r.get('arrival_first_frame')
        conflicts=set()
        # A contrary observed control in the gap cannot be ignored.
        for iv in reference.get('possession_review_intervals',[]):
            for edge,key in (('before','start_s'),('after','end_s')):
                if iv.get(edge+'_state')=='observed' and iv.get(edge+'_team') in TEAMS and iv[edge+'_team']!=team and origin/fps<iv[key]<=f/fps:
                    conflicts.add(iv['interval_id'])
        for other in rows:
            if other['id']==r['id']:continue
            o=other.get('control_frame')
            if o is not None and origin<o<=f and other.get('control_team') in TEAMS and other['control_team']!=team:conflicts.add(other['id'])
        for e in reference.get('events',[]):
            if e.get('source_kind')=='shot' and e.get('source_review_state')=='reference_single_review' and e.get('team_before') in TEAMS and e['team_before']!=team and origin/fps<e['video_start_s']<=f/fps:conflicts.add(e['event_id'])
        status='later_control_only';pass_decision='undetermined'
        if conflicts or follow['intervening_control']=='observed' or follow['intervening_restart']=='observed' or kind=='restart':
            status='continuity_not_supported'
        elif (r['state']=='observed_pass' and follow.get('path_consistent') is True
              and follow['intervening_control']==follow['intervening_restart']=='not_observed'):
            if r['team']==team:
                status='probable_retained'
                if follow.get('distinct_receiver') is True:pass_decision='probable_completed'
            else:status='probable_changed'
        result[r['id']]=dict(status=status,pass_decision=pass_decision,control_team=team,
            control_s=round(k/fps,6),next_s=round(f/fps,6),next_kind=kind,next_pass_id=linked,
            reason=follow['reason'],alternative=follow['alternative'],evidence=evidence,
            conflict_ids=sorted(conflicts),confirmed=False,
            note='Interprétation rétrospective qualitative, sans probabilité calibrée. Ne modifie pas les statistiques confirmées.')
    return result

def retrospective_summary(rows, decisions):
    observed=[r for r in rows if r['state']=='observed_pass' and r['outcome']=='unknown']
    statuses=Counter(decisions.get(r['id'],{}).get('status','unreviewed') for r in observed)
    return dict(observed_unknown_passes=len(observed),reviewed_unknown_passes=sum(r['id'] in decisions for r in observed),
                probable_retained=statuses['probable_retained'],probable_changed=statuses['probable_changed'],
                probable_completed=sum(decisions.get(r['id'],{}).get('pass_decision')=='probable_completed' for r in observed),
                without_tactical_decision=len(observed)-statuses['probable_retained']-statuses['probable_changed'],
                statuses=dict(statuses),arrival_contexts=sum(r['state']=='arrival_only' and r['id'] in decisions for r in rows),
                note='Les conclusions probables constituent une couche tactique séparée ; les issues directes restent inchangées.')
