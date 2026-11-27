"""Partial pass evidence on an explicitly constant-rate, normalized video timeline.
A completed transfer is not a possession change. No player or full-match rate is inferred.
"""
from collections import Counter
from math import isfinite
import re

TEAMS = {'blancs', 'bleus'}
OUTCOMES = {'completed', 'intercepted', 'out_of_play', 'deflected_retained', 'unknown'}
STATES = {'observed_pass', 'candidate', 'not_pass', 'arrival_only'}

def check(ok, message):
    if not ok:
        raise ValueError(message)

def frame(value, limit):
    return type(value) is int and 0 <= value < limit

def validate_pass_review(reference, duration):
    review = reference.get('pass_review')
    if review is None:
        return None
    check(isinstance(review, dict) and type(review.get('version')) is int and review['version'] == 1 and review.get('coverage_complete') is False, 'Référence passes invalide ou non partielle.')
    fps = review.get('fps')
    check(type(fps) is int and 1 <= fps <= 240 and isinstance(duration, (int,float)) and isfinite(duration), 'Cadence vidéo invalide.')
    limit = round(duration * fps)
    check(abs(limit-duration*fps)<1e-5 and limit>0, 'Durée incompatible avec la cadence déclarée.')
    rows=review.get('actions')
    check(isinstance(rows,list) and len(rows)<=2000, 'Registre de passes invalide.')
    events={e['event_id']:e for e in reference.get('events',[])}
    intervals={e['interval_id']:e for e in reference.get('possession_review_intervals',[])}
    ids=set(); releases=[]; same_action_ids=set(); shot_links=set()
    for r in rows:
        check(isinstance(r,dict), 'Action de passe invalide.')
        uid=r.get('id');state=r.get('state');outcome=r.get('outcome');team=r.get('team');receiver=r.get('control_team')
        check(isinstance(uid,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,60}',uid) and uid not in ids, 'Identifiant passe invalide ou dupliqué.');ids.add(uid)
        check(state in STATES and outcome in OUTCOMES and team in TEAMS|{None} and receiver in TEAMS|{None}, 'État ou équipe de passe invalide.')
        a,b=r.get('window_start_frame'),r.get('window_end_frame')
        check(frame(a,limit) and frame(b,limit) and a<b,'Fenêtre de preuve invalide.')
        lo,hi,c,k=(r.get(x) for x in ('release_last_held_frame','release_first_free_frame','contact_frame','control_frame'))
        arrival=r.get('arrival_first_frame')
        for v in (lo,hi,c,k,arrival):check(v is None or frame(v,limit) and a<=v<=b,'Image hors fenêtre de preuve.')
        check((lo is None)==(hi is None) and (lo is None or lo<hi),'Bornes de libération incompatibles.')
        if state=='arrival_only':
            check(arrival is not None and lo is None and team is None and outcome=='unknown' and r.get('sender_role')=='unknown' and r.get('delivery')!='not_applicable' and r.get('direct_sequence') is not True and r.get('distinct_receiver') is not True,'Arrivée seule : départ, lanceuse et issue non établis.')
            anchor=arrival
        else:
            check(arrival is None,'Repère arrivée seule incompatible avec cet état.')
            anchor=hi
        check(c is None or anchor is not None and c>=anchor,'Contact avant libération/arrivée.')
        check(k is None or anchor is not None and k>=anchor and (c is None or k>=c),'Maîtrise avant libération/arrivée/contact.')
        check((k is None)==(receiver is None),'Maîtrise et équipe de contrôle indissociables.')
        check(r.get('contact_state') in {'observed','apparent','unknown'} and ((c is None)==(r['contact_state']=='unknown')),'Contact et niveau de preuve incompatibles.')
        water=r.get('water_seen_frame')
        check(water is None or frame(water,limit) and a<=water<=b and (state!='arrival_only' or water>=arrival),'Image de ballon à la surface invalide.')
        for f in ('distinct_receiver','direct_sequence','deflection_observed'):
            check(r.get(f) is None or type(r[f]) is bool,'Drapeau de preuve invalide.')
        check(r.get('delivery') in {'air','water','unknown','not_applicable'},'Mode de réception invalide.')
        check(r.get('sender_role') in {'field','goalkeeper','unknown'},'Rôle lanceur invalide.')
        check(r.get('pressure') in {'observed','not_observed','unknown'},'Pression invalide.')
        check(isinstance(r.get('observation'),str) and 0<len(r['observation'].strip())<=4000,'Observation requise.')
        proof=r.get('evidence')
        check(isinstance(proof,list) and 1<=len(proof)<=12 and all(isinstance(x,str) and re.fullmatch(r'preuves/[A-Za-z0-9_.-]+\.jpg',x) for x in proof),'Référence preuve invalide.')
        if state=='observed_pass':
            check(team in TEAMS and lo is not None and r['delivery']!='not_applicable','Passe observée : départ et équipe requis.')
            releases.append((lo,hi,k if r.get('direct_sequence') is True else None,uid))
        elif state!='arrival_only':
            check(outcome=='unknown' and k is None,'Candidat ou contre-exemple : aucun résultat attribuable.')
        if state=='not_pass':check(lo is None and c is None and r['delivery']=='not_applicable','Contre-exemple incompatible avec un lancer observé.')
        if outcome=='completed':
            check(receiver==team and k is not None and r.get('distinct_receiver') is True and r.get('direct_sequence') is True and r.get('deflection_observed') is not True,'Réception réussie non démontrée.')
        elif outcome=='intercepted':
            check(receiver in TEAMS and receiver!=team and k is not None and r.get('direct_sequence') is True,'Interception directe non démontrée.')
        elif outcome=='deflected_retained':
            check(receiver==team and k is not None and r.get('direct_sequence') is True and r.get('deflection_observed') is True,'Conservation après déviation non démontrée.')
        elif outcome=='out_of_play':check(k is None and r.get('direct_sequence') is True,'Sortie directe non démontrée.')
        # Optional independent quality dimensions; legacy rows remain unknown.
        for field, allowed in (
            ('accuracy', {'accurate','inaccurate','unknown'}),
            ('defensive_intervention', {'blocked','deflected','none_observed','unknown'}),
            ('reception_quality', {'clean','adjusted','multiple_contacts','failed','unknown'}),
        ):
            value=r.get(field,'unknown')
            check(isinstance(value,str) and value in allowed,'Qualité de passe invalide.')
            check(state=='observed_pass' or value=='unknown','Qualité sans passe observée.')
        quality=r.get('reception_quality','unknown')
        if quality in {'clean','adjusted','multiple_contacts'}:
            check(outcome=='completed' and c is not None and r['contact_state']=='observed','Réception non démontrée.')
        if quality=='clean':
            check(c==k,'Maîtrise au premier contact non démontrée.')
        if quality=='failed':
            check(outcome in {'intercepted','out_of_play'} and c is not None and r['contact_state']=='observed','Échec de réception non démontré.')
        if r.get('defensive_intervention')=='deflected':
            check(r.get('deflection_observed') is True,'Déviation non démontrée.')
        ev=r.get('related_event_id');relation=r.get('event_relation');iv=r.get('related_interval_id')
        check((ev is None and relation is None) or ev in events and relation in {'same_action','precedes_shot'},'Lien événement invalide.')
        if relation=='precedes_shot':
            check(ev not in shot_links,'Plusieurs passes directement liées au même tir.')
            shot_links.add(ev)
            check(outcome=='completed' and k/fps<=events[ev]['video_start_s'] and events[ev]['source_kind']=='shot' and events[ev]['team_before']==team,'Lien passe-tir incompatible.')
        if relation=='same_action':
            check(ev not in same_action_ids and lo is not None and events[ev]['team_before']==team and events[ev]['video_start_s']-0.25<=hi/fps<=events[ev]['video_end_s']+0.25,'Lien temporel action incompatible ou dupliqué.')
            same_action_ids.add(ev)
        if iv is not None:
            check(iv in intervals and a/fps<=intervals[iv]['end_s'] and b/fps>=intervals[iv]['start_s'],'Lien fenêtre de possession incompatible.')
    releases.sort()
    for prev,cur in zip(releases,releases[1:]):
        check(prev[1]<cur[0],'Départs de passe chevauchants : doublon potentiel.')
        check(prev[2] is None or prev[2]<=cur[0],'Nouveau départ avant la maîtrise directe précédente.')
    return review

def summarize_pass_review(reference,duration):
    review=validate_pass_review(reference,duration)
    if review is None:return None
    fps=review['fps']; rows=review['actions']; output=[]; teams={}
    for r in rows:
        d=dict(r)
        for field in ('accuracy','defensive_intervention','reception_quality'):
            d.setdefault(field,'unknown')
        for f in ('window_start_frame','window_end_frame','release_last_held_frame','release_first_free_frame','contact_frame','control_frame','water_seen_frame','arrival_first_frame'):
            d[f.replace('_frame','_s')]=None if r.get(f) is None else round(r[f]/fps,6)
        if r.get('control_frame') is not None and r.get('direct_sequence') is True:
            d['release_to_control_evidence_s']=[round((r['control_frame']-r['release_first_free_frame'])/fps,6),round((r['control_frame']-r['release_last_held_frame'])/fps,6)]
        else:d['release_to_control_evidence_s']=None
        # Temporal association alone does not establish uninterrupted possession.
        d['shot_link_status']='temporal_only' if r.get('event_relation')=='precedes_shot' else None
        # A proven opponent control inside the gap contradicts continuity.
        if d['shot_link_status']=='temporal_only':
            start=r['control_frame']/fps
            end=next(e['video_start_s'] for e in reference['events'] if e['event_id']==r['related_event_id'])
            opponent=next(t for t in TEAMS if t!=r['team'])
            conflicts=[]
            for iv in reference.get('possession_review_intervals',[]):
                for edge, time_key in (('before','start_s'),('after','end_s')):
                    if iv.get(edge+'_state')=='observed' and iv.get(edge+'_team')==opponent and start<=iv[time_key]<=end:
                        conflicts.append(iv['interval_id'])
            d['shot_link_conflict_ids']=sorted(set(conflicts))
            if conflicts:d['shot_link_status']='opponent_control_observed'
        else:d['shot_link_conflict_ids']=[]
        d['arrival_to_control_evidence_s']=round((r['control_frame']-r['arrival_first_frame'])/fps,6) if r['state']=='arrival_only' and r.get('control_frame') is not None else None
        d['key_pass_verified']=False
        d['assist_verified']=False
        output.append(d)
    for team in sorted(TEAMS):
        actions=[r for r in rows if r['state']=='observed_pass' and r['team']==team];counts=Counter(r['outcome'] for r in actions)
        teams[team]=dict(observed_attempts=len(actions),completed=counts['completed'],unknown_outcomes=counts['unknown'],intercepted=counts['intercepted'],out_of_play=counts['out_of_play'],deflected_retained=counts['deflected_retained'],match_completion_pct=None,match_turnover_count=None)
        summary=teams[team]
        summary['confirmed_failed']=counts['intercepted']+counts['out_of_play']
        summary['unclassified_completion']=counts['unknown']+counts['deflected_retained']
        summary['resolved_completion_denominator']=counts['completed']+summary['confirmed_failed']
        n=summary['resolved_completion_denominator']
        summary['observed_resolved_completion_pct']=round(100*counts['completed']/n,2) if n else None
        for field in ('accuracy','defensive_intervention','reception_quality'):
            summary[field+'_counts']=dict(Counter(r.get(field,'unknown') for r in actions))
    return dict(actions=output,teams=teams,states=dict(Counter(r['state'] for r in rows)),fps=fps,coverage_complete=False,note='Revue partielle. Durée jusqu’à une image de maîtrise, non temps de vol exact. Aucun taux global ni attribution individuelle.')
