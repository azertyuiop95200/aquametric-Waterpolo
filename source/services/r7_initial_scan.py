"""Initial experimental R7 scan after a local analysis, independently of its metrics."""
import logging
import cv2
from services.local_clip_scan import scan_clip
from services.vision_scan_evidence import save_scan

def initial_scan(db,match,path):
    try:
        try:
            result=scan_clip(path,0,25,tracking_mode="head_flow")
            result["scan_status"]="completed"
        except (ValueError,OSError,cv2.error):
            result=dict(engine="local-head-flow",tracking_mode="head_flow",scan_status="failed",
                        first_frame=0,frames=[],identity_verified=False,metrics_validated=False,
                        statistical_use_allowed=False,pts_validated=False)
        return save_scan(db,match,None,"tracklets",result,path)
    except Exception:
        # Keep the already committed rapid analysis; never invent successful evidence.
        db.rollback()
        logging.getLogger(__name__).exception("R7 initial scan could not be saved")
        return None
