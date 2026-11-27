import unittest
from services.detection_evaluation import evaluate_points, endpoint_continuity

class DetectionEvaluationTests(unittest.TestCase):
    def test_partial(self):
        r=evaluate_points({'A':[0,0]},[[1,0],[20,20]],3)
        self.assertEqual((r['matched'],r['missed'],r['unmatched_predictions']),(1,0,1))
        self.assertIsNone(r['precision']);self.assertEqual(r['recall'],1)
    def test_complete(self):
        r=evaluate_points({'A':[0,0],'B':[20,20]},[[1,0],[100,100]],3,completeness='complete')
        self.assertEqual((r['precision'],r['recall']),(.5,.5))
    def test_one_to_one(self):
        r=evaluate_points({'A':[0,0],'B':[1,0]},[[0,0]],3)
        self.assertEqual(r['matched'],1)
    def test_cardinality(self):
        r=evaluate_points({'A':[0,0],'B':[2,0]},[[1,0],[-2,0]],2)
        self.assertEqual(r['matched'],2)
    def test_duplicates(self):
        r=evaluate_points({'A':[0,0]},[[0,0],[0,0]],1,completeness='complete')
        self.assertEqual(r['precision'],.5)
    def test_unknown(self):
        r=evaluate_points({},[[0,0]],2,completeness='unknown')
        self.assertFalse(r['evaluated']);self.assertIsNone(r['unmatched_predictions'])
    def test_negative(self):
        r=evaluate_points({},[[0,0]],2,completeness='complete')
        self.assertEqual(r['precision'],0);self.assertIsNone(r['recall'])
    def test_empty(self):
        r=evaluate_points({'A':[0,0]},[],2,completeness='complete')
        self.assertEqual(r['recall'],0);self.assertIsNone(r['precision'])
    def test_invalid(self):
        for v in (0,-1,float('nan'),True):
            with self.assertRaises(ValueError):evaluate_points({},[],v)
        with self.assertRaises(ValueError):evaluate_points({'A':[float('inf'),0]},[],1)
        with self.assertRaises(ValueError):evaluate_points({'A':[0,0]},[],1,completeness='unknown')
    def test_continuity(self):
        ref={'A':[0,0],'B':[20,0],'C':[40,0]}
        a=[dict(point=[0,0],track_id=1),dict(point=[20,0],track_id=2)]
        b=[dict(point=[0,0],track_id=1),dict(point=[20,0],track_id=3),dict(point=[40,0],track_id=4)]
        r=endpoint_continuity(ref,ref,a,b,2)
        self.assertEqual((r['same_track_id'],r['different_track_id'],r['missing_endpoint']),(1,1,1))
        self.assertEqual(r['endpoint_retention'],.5)
    def test_contradiction(self):
        ref={'A':[0,0],'B':[20,0]}
        a=[dict(point=[0,0],track_id=1),dict(point=[20,0],track_id=2)]
        b=[dict(point=[0,0],track_id=2),dict(point=[20,0],track_id=1)]
        self.assertEqual(endpoint_continuity(ref,ref,a,b,2)['contradictory_endpoint_link'],2)
    def test_no_shared(self):
        r=endpoint_continuity({'A':[0,0]},{'B':[20,0]},[],[],2)
        self.assertIsNone(r['endpoint_retention']);self.assertEqual(r['shared_reference_ids'],0)
    def test_duplicate_track_ids(self):
        a=[dict(point=[0,0],track_id=1),dict(point=[20,0],track_id=1)]
        with self.assertRaises(ValueError):endpoint_continuity({}, {}, a, [], 2)


class PairedBenchmarkTests(unittest.TestCase):
    def test_paired_scope(self):
        from services.detection_evaluation import compare_frame_methods
        rows=[dict(frame_key="a",completeness="complete",reference={"A":[0,0]},
                   baseline=[[0,0],[20,20]],head_flow=[[0,0]]),
              dict(frame_key="b",completeness="partial",reference={"B":[0,0]},
                   baseline=[],head_flow=[[0,0],[30,30]]),
              dict(frame_key="c",completeness="complete",reference={"C":[0,0]},
                   baseline=None,head_flow=[[0,0]])]
        r=compare_frame_methods(rows,2)
        self.assertEqual(r["paired_frames"],2)
        self.assertEqual(r["excluded"]["missing_output"],1)
        self.assertEqual(r["methods"]["baseline"]["precision"],.5)
        self.assertEqual(r["methods"]["head_flow"]["precision"],1)
        self.assertEqual(r["methods"]["baseline"]["recall_reviewed"],.5)
        self.assertEqual(r["methods"]["head_flow"]["recall_reviewed"],1)
        self.assertAlmostEqual(r["methods"]["baseline"]["f1_complete"],2/3)
    def test_no_reference(self):
        from services.detection_evaluation import compare_frame_methods
        r=compare_frame_methods([dict(frame_key="a",completeness="unknown")],2)
        self.assertEqual(r["state"],"not_measured")
        self.assertIsNone(r["methods"]["baseline"]["f1_complete"])
    def test_duplicate_frame(self):
        from services.detection_evaluation import compare_frame_methods
        row=dict(frame_key="a",completeness="unknown")
        with self.assertRaises(ValueError):compare_frame_methods([row,row],2)
    def test_empty_detection_is_not_missing(self):
        from services.detection_evaluation import compare_frame_methods
        r=compare_frame_methods([dict(frame_key="a",completeness="complete",
            reference={"A":[0,0]},baseline=[],head_flow=[])],2)
        self.assertEqual(r["paired_frames"],1)
        self.assertEqual(r["methods"]["baseline"]["recall_complete"],0)
        self.assertEqual(r["methods"]["baseline"]["f1_complete"],0)
