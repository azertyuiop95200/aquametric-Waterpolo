import unittest
from services.tactical_timeline import tactical_timeline
class TacticalTimelineTests(unittest.TestCase):
    def test_possession_only_explicit(self):
        def e(s,k,side="for",segment=1):
            return {"second":s,"event_type":k,"side":side,"segment_index":segment}
        rows=tactical_timeline([e(1,"pass_complete"),e(2,"possession_start"),e(3,"shot_blocked"),e(4,"possession_end"),e(5,"pass_complete","against"),e(6,"possession_start","against"),e(7,"pass_complete","against",2)])
        self.assertIsNone(rows[0]["attack_after"])
        self.assertEqual(rows[1]["attack_after"],"for")
        self.assertEqual(rows[2]["defence_after"],"against")
        self.assertIsNone(rows[3]["attack_after"])
        self.assertIsNone(rows[-1]["attack_after"])
