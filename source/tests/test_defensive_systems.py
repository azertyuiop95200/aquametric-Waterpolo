import unittest
from services.defensive_systems import classify_frame,classify_window,local_features
def fixture():
    a=[{"id":i,"role":i,"x":x,"y":y} for i,(x,y) in enumerate([(3,-6),(6,-3),(7,0),(6,3),(3,6),(2,0)],1)]
    d=[dict(p,id=p["id"]+10,x=p["x"]-.6) for p in a]
    return a,d
class TacticTests(unittest.TestCase):
    def test_press_and_partial(self):
        a,d=fixture()
        self.assertEqual(classify_frame(a,d,True)["system"],"press")
        self.assertEqual(classify_frame(a,d[:-1],True)["system"],"unknown")
        self.assertEqual(classify_frame(a,d)["system"],"unknown")
    def test_m_and_zone(self):
        a,d=fixture();d[2].update(x=3,y=0);d[1].update(x=6,y=-1.2);d[3].update(x=6,y=1.2)
        self.assertEqual(classify_frame(a,d,True)["system"],"zone_m")
        d[1].update(x=2,y=-1);d[3].update(x=2,y=1)
        self.assertEqual(classify_frame(a,d,True)["system"],"zone_234")
    def test_persistence(self):
        a,d=fixture();f=[{"second":i*.5,"attack":a,"defence":d,"even_verified":True,"possession_id":1} for i in range(5)]
        self.assertEqual(classify_window(f)["system"],"press")
        f[-1]["possession_id"]=2
        self.assertEqual(classify_window(f)["system"],"unknown")
