import unittest
from unittest.mock import patch
import cv2,numpy as np
from services.head_flow_tracking import _flow,scan_head_flow

M='services.head_flow_tracking'
def image(x=300):
    f=np.full((720,1280,3),120,np.uint8)
    cv2.rectangle(f,(x-8,292),(x+8,308),(20,20,20),-1)
    cv2.line(f,(x-7,294),(x+7,306),(210,210,210),2)
    return f

def det(x=300,colour='cap_dark'):
    return dict(kind='head',colour=colour,x=x/1280,y=300/720,bbox=[(x-8)/1280,292/720,(x+8)/1280,308/720],ranking_score=.8,status='candidate')

def seq(ds,fs=None,flow=None,limit=2):
    fs=fs or [(i*.04,image(300+i*3)) for i in range(len(ds))]
    with patch(M+'.detect',side_effect=ds):
        if flow is None:return scan_head_flow(fs,max_flow_only=limit)
        with patch(M+'._flow',side_effect=flow):return scan_head_flow(fs,max_flow_only=limit)

class HeadFlowTests(unittest.TestCase):
    def test_real_flow(self):
        a,b=[cv2.cvtColor(image(x),cv2.COLOR_BGR2GRAY) for x in (300,308)]
        p=_flow(a,b,[(300,300)])[0];self.assertIsNotNone(p);self.assertAlmostEqual(p[0],308,delta=1)
    def test_flat_patch(self):
        a=np.full((720,1280),120,np.uint8);self.assertEqual(_flow(a,a,[(300,300)]),[None])
    def test_detect_association(self):
        r=seq([[det()],[det(303)]],flow=[[(303,300)]]);a,b=r['frames'];self.assertEqual(a['detections'][0]['track_id'],b['detections'][0]['track_id']);self.assertEqual(b['detections'][0]['point_source'],'detector')
    def test_fallback(self):
        r=seq([[det()],[det(303)]],flow=[[None]]);self.assertEqual(r['tracklets_total'],1)
    def test_flow_limit(self):
        r=seq([[det()],[],[],[],[det(312)]],flow=[[(303,300)],[(306,300)],[(309,300)]]);self.assertEqual(r['flow_only_points'],2);self.assertEqual(r['frames'][3]['detections'],[]);self.assertEqual(r['tracklets_total'],2);self.assertFalse(r['identity_verified'])
    def test_flow_is_not_detection(self):
        r=seq([[det()],[]],flow=[[(303,300)]]);d=r['frames'][1]['detections'][0];self.assertEqual(d['point_source'],'optical_flow');self.assertEqual(d['status'],'flow_candidate_not_detection');self.assertIsNone(d['bbox'])
    def test_conflicting_colour(self):
        r=seq([[det()],[det(303,'cap_light')]],flow=[[(303,300)]]);self.assertEqual(r['flow_only_points'],0);self.assertEqual(r['tracklets_total'],2)
    def test_ambiguity(self):
        r=seq([[det()],[det(301),det(305)]],flow=[[(303,300)]]);self.assertEqual(r['tracklets_total'],3);self.assertEqual(r['flow_only_points'],0)
    def test_cut(self):
        r=seq([[det()],[det()]],fs=[(0,image()),(.04,np.full((720,1280,3),255,np.uint8))]);self.assertEqual(r['resets'],1);self.assertEqual(r['tracklets_total'],2)
    def test_gap(self):
        r=seq([[det()],[det()]],fs=[(0,image()),(.2,image())]);self.assertEqual(r['resets'],1);self.assertEqual(r['tracklets_total'],2)
    def test_invalid_time(self):
        with self.assertRaises(ValueError):seq([[det()],[det()]],fs=[(0,image()),(0,image())])
    def test_invalid_limit(self):
        with self.assertRaises(ValueError):scan_head_flow([],3)
    def test_empty(self):
        r=scan_head_flow([]);self.assertEqual(r['tracklets_total'],0);self.assertFalse(r['metrics_validated'])


class SupportedFlowTests(unittest.TestCase):
    def run_supported(self, ds, flow):
        fs=[(i*.04,image(300+i*3)) for i in range(len(ds))]
        with patch(M+'.detect',side_effect=ds),patch(M+'._flow',side_effect=flow):
            return scan_head_flow(fs,min_detector_support=2)

    def test_single_candidate_does_not_seed_propagation(self):
        r=self.run_supported([[det()],[],[]], [[(303,300)]])
        self.assertEqual(r['flow_only_points'],0)
        self.assertEqual(r['flow_support_withheld'],1)
        self.assertEqual(r['frames'][0]['detections'][0]['point_source'],'detector')

    def test_two_independent_observations_seed_short_gap(self):
        r=self.run_supported([[det()],[det(303)],[],[],[]],
                             [[(303,300)],[(306,300)],[(309,300)],[(312,300)]])
        self.assertEqual(r['flow_only_points'],2)
        self.assertEqual(r['frames'][2]['detections'][0]['detector_support'],2)
        self.assertEqual(r['frames'][4]['detections'],[])
        self.assertFalse(r['identity_verified'])

    def test_red_cap_independent_candidate_preserved(self):
        r=self.run_supported([[det(colour='cap_red')],[]],[[(303,300)]])
        self.assertEqual(r['frames'][0]['detections'][0]['colour'],'cap_red')
        self.assertEqual(r['flow_only_points'],0)

    def test_support_restarts_after_gap(self):
        r=self.run_supported([[det()],[det(303)],[],[det(309)],[]],
                             [[(303,300)],[(306,300)],[(309,300)],[(312,300)]])
        self.assertEqual(r['flow_only_points'],1)
        self.assertEqual(r['frames'][3]['detections'][0]['detector_support'],1)
        self.assertEqual(r['flow_support_withheld'],1)

    def test_historical_replay_keeps_raw_points_and_rejects_chain(self):
        from services.head_flow_tracking import audit_flow_support
        r=seq([[det()],[],[],[det(309)],[det(312)],[]],
              flow=[[(303,300)],[(306,300)],[(309,300)],[(312,300)],[(315,300)]])
        import copy
        old=copy.deepcopy(r)
        a=audit_flow_support(r['frames'])
        self.assertEqual((a['detector_points'],a['flow_retained'],a['flow_withheld']),(3,1,2))
        self.assertIsNone(a['precision'])
        self.assertEqual(r,old)
