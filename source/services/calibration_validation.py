"""Independent planar calibration check. A successful fit is not a metric validation."""
import math
import numpy as np
from services.metric_field import calibrate, project

def check_calibration(anchors, width, length, checks, *, dimensions_verified=False, mean_limit_m=.30, max_limit_m=.60):
    """Check withheld, surveyed, water-plane landmarks; never use training residual as accuracy.
    The caller must attest independent measurements. This function cannot verify their provenance.
    """
    if type(dimensions_verified) is not bool:
        raise ValueError("dimensions_verified must be boolean")
    if not all(math.isfinite(v) and v>0 for v in (mean_limit_m,max_limit_m)) or mean_limit_m>max_limit_m:
        raise ValueError("Invalid error limits")
    cal=calibrate(anchors,width,length)
    fit=np.asarray(anchors,dtype=float)
    results=[]
    used=set()
    world=[]
    for row in checks:
        rid=row["id"]
        if not isinstance(rid,str) or not rid.strip() or rid in used:
            raise ValueError("Duplicate or missing independent landmark")
        used.add(rid)
        xy=np.asarray(row["image"],dtype=float)
        target=np.asarray(row["metric"],dtype=float)
        if xy.shape!=(2,) or target.shape!=(2,) or not np.isfinite(xy).all() or not np.isfinite(target).all() or (xy<0).any() or (xy>1).any():
            raise ValueError("Invalid landmark")
        if not 0<=target[0]<=cal["length"] or abs(target[1])>cal["width"]/2:
            raise ValueError("Landmark outside field")
        if min(np.linalg.norm(fit-xy,axis=1))<.002 or any(np.linalg.norm(v-target)<.05 for v in world):
            raise ValueError("Landmark not independent")
        world.append(target)
        pred=project(cal,*xy)
        results.append({"id":rid,"expected_m":target.tolist(),"predicted_m":list(pred) if pred is not None else None,"error_m":float(np.linalg.norm(np.asarray(pred)-target)) if pred is not None else None})
    errors=[r["error_m"] for r in results if r["error_m"] is not None]
    span=bool(len(world)>=4 and np.ptp(np.asarray(world),axis=0).min()>=3 and np.linalg.matrix_rank(np.asarray(world)-np.mean(world,axis=0))==2)
    mean=float(np.mean(errors)) if errors else None
    worst=max(errors) if errors else None
    reasons=[]
    if not dimensions_verified: reasons.append("dimensions_unverified")
    if not span: reasons.append("insufficient_independent_spatial_coverage")
    if len(errors)!=len(results) or not errors: reasons.append("unprojectable_landmarks")
    if mean is not None and (mean>mean_limit_m or worst>max_limit_m): reasons.append("error_threshold_exceeded")
    return {"status":"passed_declared_landmarks" if not reasons else "not_validated","reasons":reasons,"dimensions_verified_declared":dimensions_verified,"fit_error_normalized":cal["fit_error_normalized"],"mean_error_m":mean,"max_error_m":worst,"mean_limit_m":mean_limit_m,"max_limit_m":max_limit_m,"independent_landmarks":results,"scope":"single_frame_water_plane_only; no camera-motion or player-identity validation"}
