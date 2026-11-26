import unittest
from services.cap_reading import select_reading_frames,reviewed_identity
class DeferredCapTests(unittest.TestCase):
    def test_best_frames_spaced(self):
        rows=[{"second":t,"sharpness":v} for t,v in [(0,10),(.1,15),(.8,7),(1.6,20)]]
        self.assertEqual([r["second"] for r in select_reading_frames(rows)], [.1,.8,1.6])
    def test_need_distinct_readings(self):
        v={"reviewed":True,"side":"for","cap_number":8,"second":10,"colour":"blue"}
        self.assertIsNone(reviewed_identity([v,v]))
        self.assertEqual(reviewed_identity([v,dict(v,second=11)])["cap_number"],8)
        self.assertIsNone(reviewed_identity([v,dict(v,second=11,cap_number=3)]))
        self.assertIsNone(reviewed_identity([v,dict(v,second=11,side="against")]))
    def test_unreviewed_not_identity(self):
        v={"reviewed":False,"side":"for","cap_number":8,"second":10}
        self.assertIsNone(reviewed_identity([v,dict(v,second=11)]))
