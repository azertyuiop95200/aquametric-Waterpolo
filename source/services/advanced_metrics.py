from collections import Counter
from sqlalchemy import select
from models import PlayerShotObservation

METRIC_GROUPS = {
    "Creation": ["action_created","assists","key_passes","passes_complete","touches","centre_touches","exclusions_earned"],
    "Finishing": ["goals","shots","shot_efficiency","shots_on_target","blocked_shots","penalties_earned","penalties_scored"],
    "Duels & centre play": ["duels_won","duels_lost","centre_touches","centre_entries_received","exclusions_earned","turnovers_under_pressure"],
    "Defence": ["steals","blocks","rebounds","fouls","exclusions_committed","duels_won_defence","shot_contests"],
    "Transition": ["sprints","fast_recovery","late_recovery","transition_involvement","distance_m","avg_swim_speed","max_swim_speed"],
    "Goalkeeper": ["saves","save_efficiency","shots_on_goal_received","distribution_complete","distribution_lost","restart_time"],
}

EVENT_TO_METRIC = {
    "goal":"goals","assist":"assists","key_pass":"key_passes","action_created":"action_created","touch":"touches","centre_touch":"centre_touches",
    "duel_won":"duels_won","duel_lost":"duels_lost","pass_complete":"passes_complete","shot_on_target":"shots_on_target","shot_off_target":"shots_off_target",
    "shot_blocked":"blocked_shots","block":"blocks","interception":"steals","recovery":"recoveries","save":"saves","bad_pass":"bad_passes","turnover":"turnovers",
    "exclusion_earned":"exclusions_earned","exclusion_committed":"exclusions_committed","fast_recovery":"fast_recovery","late_recovery":"late_recovery"
}


def event_metric_summary(events, player_id):
    c=Counter()
    for e in events:
        if e.player_id != player_id: continue
        metric=EVENT_TO_METRIC.get(e.event_type)
        if metric: c[metric]+=1
        if e.event_type in {"shot_on_target","shot_off_target","shot_blocked","goal"}: c["shots"]+=1
    return dict(c)


def shot_map_summary(db, profile_id):
    shots=db.scalars(select(PlayerShotObservation).where(PlayerShotObservation.profile_id==profile_id)).all()
    if not shots:
        return {"count":0,"pool_bins":[],"goal_bins":[],"side":{},"outcomes":{},"confidence":0.0,"demo":False}
    pool=[[0 for _ in range(6)] for __ in range(3)]
    goal=[[0 for _ in range(3)] for __ in range(3)]
    side=Counter(); outcomes=Counter(); conf=[]
    for s in shots:
        if s.pool_x is not None and s.pool_y is not None:
            cx=min(5,max(0,int(s.pool_x*6))); cy=min(2,max(0,int(s.pool_y*3))); pool[cy][cx]+=1
        if s.goal_x is not None and s.goal_y is not None:
            gx=min(2,max(0,int(s.goal_x*3))); gy=min(2,max(0,int(s.goal_y*3))); goal[gy][gx]+=1
        side[s.shooter_side or "unknown"]+=1; outcomes[s.outcome or "unknown"]+=1; conf.append(s.confidence_score or 0)
    return {"count":len(shots),"pool_bins":pool,"goal_bins":goal,"side":dict(side),"outcomes":dict(outcomes),"confidence":sum(conf)/len(conf) if conf else 0.0,"demo":all((s.provenance or "") == "showcase_demo" for s in shots)}
