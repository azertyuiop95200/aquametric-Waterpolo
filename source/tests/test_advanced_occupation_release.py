import unittest
from services.advanced_motion_report import build
from services.occupancy_grid import occupancy,density,observed_timeline
from test_advanced_motion_release import fixture

def points(a,b,t=0,u=.2):
    return [{'second':t,'x_m':a[0],'y_m':a[1]},{'second':u,'x_m':b[0],'y_m':b[1]}]

class OccupancyReleaseTests(unittest.TestCase):
    def test_partition(self):
        m=occupancy([points((1.8,1),(2.2,1))],25,20,2,0,1)
        self.assertAlmostEqual(sum(c['seconds'] for c in m['cells']),.2)
        self.assertAlmostEqual(m['cells'][0]['seconds'],.1)
        self.assertAlmostEqual(sum(c['share'] for c in m['cells']),1)
    def test_partial_cell(self):
        m=density(occupancy([points((24.5,19),(24.5,19))],25,20,2,0,1));c=m['cells'][0]
        self.assertEqual(c['w'],1);self.assertEqual(c['density_per_m2'],.5);self.assertEqual(c['opacity'],1)
    def test_time_split(self):
        r=observed_timeline([points((1,1),(1.4,1),59.9,60.1)])
        self.assertEqual([x['start_s'] for x in r],[0,60]);self.assertAlmostEqual(r[0]['distance_m'],.2);self.assertAlmostEqual(sum(x['observed_s'] for x in r),.2)
    def test_gap(self):
        r=observed_timeline([points((1,1),(1.4,1),0,.2),points((1,1),(1.4,1),120,120.2)])
        self.assertEqual([x['start_s'] for x in r],[0,120])
    def test_empty(self):
        self.assertEqual(observed_timeline([]),[]);self.assertEqual(occupancy([],25,20,2,0,1)['cells'],[])
    def test_invalid_bounds(self):
        with self.assertRaises(ValueError): occupancy([],25,20,0,0,1)
    def test_release(self):
        p=build(fixture())['players'][0];m=p['metrics'];self.assertAlmostEqual(p['occupation']['observed_s'],m['observed_s']);self.assertAlmostEqual(sum(x['distance_m'] for x in p['movement_timeline']),m['distance_m'])
    def test_overlap(self):
        a=points((1,1),(1.4,1));self.assertRaises(ValueError,observed_timeline,[a,a])
if __name__=='__main__':unittest.main()
