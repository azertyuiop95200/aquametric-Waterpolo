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

TARGET_ZONE_LABELS = [
    ["upper left", "upper centre", "upper right"],
    ["middle left", "centre", "middle right"],
    ["low left", "low centre", "low right"],
]


def event_metric_summary(events, player_id):
    c=Counter()
    for e in events:
        if e.player_id != player_id: continue
        metric=EVENT_TO_METRIC.get(e.event_type)
        if metric: c[metric]+=1
        if e.event_type in {"shot_on_target","shot_off_target","shot_blocked","goal"}: c["shots"]+=1
    return dict(c)


def _target_preference(goal_bins):
    located=sum(sum(row) for row in goal_bins)
    if located < 3:
        return {"available":False,"label":None,"share":None,"located":located}
    best=(-1,0,0)
    for row_idx,row in enumerate(goal_bins):
        for col_idx,value in enumerate(row):
            if value > best[0]:
                best=(value,row_idx,col_idx)
    value,row_idx,col_idx=best
    return {
        "available":value > 0,
        "label":TARGET_ZONE_LABELS[row_idx][col_idx] if value > 0 else None,
        "share":round(value/located*100) if located else None,
        "located":located,
    }


def _side_preference(side):
    known={k:v for k,v in side.items() if k and k.lower() not in {"unknown","none","n/a"}}
    total=sum(known.values())
    if total < 3 or not known:
        return {"available":False,"label":None,"share":None,"located":total}
    label,value=max(known.items(),key=lambda item:item[1])
    return {"available":True,"label":label.replace('_',' '),"share":round(value/total*100),"located":total}


def shot_map_summary(db, profile_id):
    shots=db.scalars(select(PlayerShotObservation).where(PlayerShotObservation.profile_id==profile_id)).all()
    if not shots:
        return {"count":0,"pool_bins":[],"goal_bins":[],"side":{},"outcomes":{},"confidence":0.0,"demo":False,"preferences":{"target":{"available":False,"label":None,"share":None,"located":0},"side":{"available":False,"label":None,"share":None,"located":0}}}
    pool=[[0 for _ in range(6)] for __ in range(3)]
    goal=[[0 for _ in range(3)] for __ in range(3)]
    side=Counter(); outcomes=Counter(); conf=[]
    for s in shots:
        if s.pool_x is not None and s.pool_y is not None:
            cx=min(5,max(0,int(s.pool_x*6))); cy=min(2,max(0,int(s.pool_y*3))); pool[cy][cx]+=1
        if s.goal_x is not None and s.goal_y is not None:
            gx=min(2,max(0,int(s.goal_x*3))); gy=min(2,max(0,int(s.goal_y*3))); goal[gy][gx]+=1
        side[s.shooter_side or "unknown"]+=1; outcomes[s.outcome or "unknown"]+=1; conf.append(s.confidence_score or 0)
    demo=all((s.provenance or "") == "showcase_demo" for s in shots)
    preferences={"target":_target_preference(goal),"side":_side_preference(dict(side))}
    return {"count":len(shots),"pool_bins":pool,"goal_bins":goal,"side":dict(side),"outcomes":dict(outcomes),"confidence":sum(conf)/len(conf) if conf else 0.0,"demo":demo,"preferences":preferences}
