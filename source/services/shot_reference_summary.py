"""Counts of reviewed shot windows, never full-period or automatic statistics."""


def summarize_shots(events):
    groups = {c: dict(reviewed=0, candidates=0, goal_indications=0,
                      declared_verified_goals=0, unknown_outcomes=0)
              for c in ('blancs', 'bleus', 'unknown')}
    shots = [e for e in events if e['source_kind'] in ('shot','shot_candidate')
             and e['source_review_state'] != 'not_shot_example']
    # Overlapping windows are potentially the same action: exclude both from counts.
    conflicts = set()
    for i, a in enumerate(shots):
        for b in shots[i+1:]:
            if max(a['video_start_s'], b['video_start_s']) <= min(a['video_end_s'], b['video_end_s']):
                conflicts.update((a['event_id'], b['event_id']))
    for e in shots:
        if e['event_id'] in conflicts:
            continue
        row = groups[e.get('team_before') or 'unknown']
        if e['source_kind'] != 'shot' or e['source_review_state'] != 'reference_single_review':
            row['candidates'] += 1
            continue
        row['reviewed'] += 1
        if e['cause'] == 'goal':
            row['goal_indications'] += 1
            if e['cause_verified'] is True:
                row['declared_verified_goals'] += 1
        if not e['cause_verified'] or e['cause'] in ('unknown','shot_unknown'):
            row['unknown_outcomes'] += 1
    return dict(teams=groups, conflict_ids=sorted(conflicts), scope='partial_single_review',
                match_shots=None, match_goals=None, match_conversion_pct=None,
                note='Fenêtres de tirs revues, non statistiques du quart-temps. Les indices de but non vérifiés font aussi partie des issues non résolues. Aucun événement automatique créé.')
