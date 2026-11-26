import unittest
from services.recognition_quality import temporal_score_rows, audit, evaluate
from services.autonomous_engine import infer_candidates

def row(t,h,a):
    return {"second":t,"home_score":h,"away_score":a,"period":1,"clock_seconds":480-int(t),"ocr_confidence":.95}

class QualityTests(unittest.TestCase):
    def test_simultaneous_crops_cannot_confirm_a_goal(self):
        rows=[row(0,0,0),row(10,1,0),row(10,1,0)]
        self.assertEqual(len(temporal_score_rows(rows)),2)
        self.assertFalse(any(c.event_type.startswith("goal_candidate") for c in infer_candidates(rows,[])))
    def test_conflicting_crops(self):
        self.assertEqual(temporal_score_rows([row(10,1,0),row(10,0,0)]),[])
    def test_reference_matching_is_one_to_one(self):
        ref=[{"second":10,"event_type":"goal","side":"for"},{"second":13,"event_type":"goal","side":"for"}]
        pred=[{"second":11,"event_type":"goal","side":"for"},{"second":9,"event_type":"goal","side":"for"},{"second":10,"event_type":"goal","side":"against"}]
        m=evaluate(ref,pred)
        self.assertEqual((m["tp"],m["fp"],m["fn"]),(2,1,0))
        self.assertAlmostEqual(m["f1"],.8)
    def test_unmapped_sources_not_compared(self):
        a={"candidates":[{"event_type":"goal_candidate_home","evidence":{"bracket_start_second":8,"bracket_end_second":12}}]}
        b={"events":[{"event_type":"goal","counted":True,"second":10,"side":"for","cap_number":3}]}
        self.assertIsNone(audit(a,b)["time_matches"])
        a["same_source_timeline"]=True
        self.assertEqual(audit(a,b)["time_matches"],1)
        b["events"].append(dict(b["events"][0],second=11))
        self.assertEqual(audit(a,b)["time_matches"],0)
