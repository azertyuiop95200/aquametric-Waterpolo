from services.shot_reference_summary import summarize_shots


def shot(uid,start,end,**kw):
    return dict(dict(event_id=uid,video_start_s=start,video_end_s=end,source_kind='shot',source_review_state='reference_single_review',team_before='bleus',cause='goal',cause_verified=False),**kw)


def test_unverified_goal_not_promoted():
    r=summarize_shots([shot('a',1,2),shot('b',3,4,source_kind='shot_candidate')]);s=r['teams']['bleus']
    assert (s['reviewed'],s['candidates'],s['goal_indications'],s['unknown_outcomes'],s['declared_verified_goals'])==(1,1,1,1,0)
    assert r['match_goals'] is None and r['match_conversion_pct'] is None


def test_overlapping_windows_excluded():
    r=summarize_shots([shot('a',1,2),shot('b',1.8,3)])
    assert r['teams']['bleus']['reviewed']==0 and r['conflict_ids']==['a','b']
