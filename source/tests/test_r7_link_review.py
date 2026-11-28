"""Test link proposal logic separately from the optical-flow engine."""
import copy,unittest
from unittest.mock import patch
import numpy as np
from services.r7_link_review import propose, scan_head_flow_with_links

def fixture(end=.16,cut=False,competing=False,intermediate=False):
    a=dict(second=0.,x=.4,y=.5)
    b=dict(second=end,x=.4,y=.5)
    def det(i,p):return dict(kind='head',track_id=i,x=p['x'],y=p['y'])
    t=[dict(id=1,kind='head',points=[a]),dict(id=2,kind='head',points=[b])]
    frames=[dict(second=0.,scene_reset=False,detections=[det(1,a)]),
            dict(second=.08,scene_reset=cut,detections=[]),
            dict(second=end,scene_reset=False,detections=[det(2,b)])]
    if competing:
        q=dict(b,x=.402)
        t.append(dict(id=3,kind='head',points=[q]));frames[2]['detections'].append(det(3,q))
    if intermediate:
        q=dict(a,second=.08)
        t.append(dict(id=3,kind='head',points=[q]));frames[1]['detections'].append(det(3,q))
    return dict(tracks=t,frames=frames),[np.zeros((128,128,3),np.uint8) for _ in frames]

class LinkReviewTests(unittest.TestCase):
    def setUp(self):
        p=patch('services.r7_link_review._flow',side_effect=lambda a,b,points:list(points));p.start();self.addCleanup(p.stop)
    def test_candidate_not_merge(self):
        result,images=fixture();old=copy.deepcopy(result)
        r=propose(result,images);self.assertEqual(result,old)
        self.assertEqual(len(r['links']),1)
        self.assertEqual((r['links'][0]['from_track_id'],r['links'][0]['to_track_id'],r['links'][0]['missing_samples']),(1,2,1))
        self.assertFalse(r['identity_verified']);self.assertFalse(r['statistical_use_allowed'])
    def test_cut(self):
        self.assertEqual(propose(*fixture(cut=True))['links'],[])
    def test_long_gap(self):
        self.assertEqual(propose(*fixture(end=.32))['links'],[])
    def test_ambiguous_endpoint(self):
        self.assertEqual(propose(*fixture(competing=True))['links'],[])
    def test_intermediate_competitor(self):
        r=propose(*fixture(intermediate=True))
        self.assertNotIn((1,2),[(e['from_track_id'],e['to_track_id']) for e in r['links']])
    def test_reverse_failure(self):
        with patch('services.r7_link_review._flow',side_effect=[[(51.2,64.)],[(51.2,64.)],[],[None]]):
            self.assertEqual(propose(*fixture())['links'],[])
    def test_memory_limit(self):
        f=np.zeros((2160,3840,3),np.uint8)
        with self.assertRaises(ValueError):scan_head_flow_with_links((i/25,f) for i in range(10))
    def test_mismatched_images(self):
        r,images=fixture()
        with self.assertRaises(ValueError):propose(r,images[:-1])
