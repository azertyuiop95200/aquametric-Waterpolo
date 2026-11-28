"""Short, review-seeded ball hypotheses; no event or metric certification."""
from math import hypot
from services.ball_motion_review import propose
from services.local_object_tracking import detect

VERSION = 'assisted-colour-motion-v1'


def fuse(previous, current, following, *, frame_index, seeds):
    """Use the existing motion safety gate; rank actual colour/motion evidence.

    Never emit the extrapolated point itself. At most three spatially distinct
    proposals; an empty result is a legitimate abstention. The scores are not
    calibrated probabilities. Both seeds must have been reviewed by the caller.
    """
    motion = propose(previous, current, following, frame_index=frame_index, seeds=seeds)
    out = dict(motion, engine=VERSION, candidates=[], statistical_use_allowed=False,
               seed_review_verified_by_server=False, motion_candidate_count=len(motion['candidates']))
    if motion['status'] in ('scene_motion_refused', 'prediction_outside_frame'):
        return out
    h, w = current.shape[:2]
    px, py = motion['prediction_xy']
    radius = motion['radius_px']
    candidates = [(p, 'colour') for p in detect(current) if p['kind'] == 'ball']
    candidates += [(p, 'motion') for p in motion['candidates']]
    ranked = []
    for p, source in candidates:
        distance = hypot((p['x']-px)*w, (p['y']-py)*h)
        if distance > radius:
            continue
        score = 1-distance/radius + .1*float(p['ranking_score'])
        ranked.append(dict(p, evidence_source=source, distance_to_prediction_px=round(distance,3),
                           fusion_score=round(score,6), status='assisted_candidate_not_verified'))
    ranked.sort(key=lambda p: -p['fusion_score'])
    distinct = []
    for p in ranked:
        if any(hypot((p['x']-q['x'])*w,(p['y']-q['y'])*h) < 9*h/720 for q in distinct):
            continue
        distinct.append(p)
    out.update(status='candidates' if distinct else 'no_supported_candidate',
               candidates=distinct[:3], gated_candidate_count=len(distinct))
    return out
