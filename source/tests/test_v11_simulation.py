from services.simulation import simulate_matchup

def test_cross_level_reality_gate_granville_france():
    r=simulate_matchup('Granville Water Polo','France — Women Senior',n=12000,seed=1)
    assert r['avg_b'] - r['avg_a'] >= 7.0
    assert r['win_b'] >= 96.0
    assert r['cross_level'] is True

def test_tactics_cannot_reverse_huge_class_gap():
    r=simulate_matchup('Granville Water Polo','France — Women Senior',tactic_a='transition',tactic_b='defence_first',n=9000,seed=2,form_a=70,form_b=30,venue='team_a_home')
    assert r['win_b'] >= 90.0
    assert r['avg_b'] > r['avg_a'] + 5.0

def test_peer_club_match_is_not_forced_to_extreme():
    r=simulate_matchup('Granville Water Polo','Lille UC Métropole Water-Polo',n=9000,seed=3)
    assert 2.0 < r['win_a'] < 55.0
    assert 45.0 < r['win_b'] < 95.0
    assert abs(r['avg_a']-r['avg_b']) < 5.0

def test_world_elite_beats_lower_senior_prior_more_often():
    r=simulate_matchup('France — Women Senior','Spain — Women Senior',n=9000,seed=4)
    assert r['win_b'] > r['win_a']
    assert r['avg_b'] > r['avg_a']

def test_historical_and_recruitment_factors_are_exposed():
    r=simulate_matchup('Granville Water Polo','Lille UC Métropole Water-Polo',n=2000,seed=9,venue='team_a_home')
    labels=[row[0] for row in r['factor_rows']]
    assert 'Historical results prior' in labels
    assert 'Recruitment / selection impact' in labels
    assert 'Roster continuity' in labels
    assert 'Home/away history' in labels
    assert 'recruitment_note_a' in r

def test_team_specific_home_history_changes_projection():
    neutral=simulate_matchup('Granville Water Polo','Lille UC Métropole Water-Polo',n=6000,seed=10,venue='neutral')
    home=simulate_matchup('Granville Water Polo','Lille UC Métropole Water-Polo',n=6000,seed=10,venue='team_a_home')
    assert home['avg_a'] >= neutral['avg_a'] - 0.2
    assert home['win_a'] >= neutral['win_a'] - 1.0
