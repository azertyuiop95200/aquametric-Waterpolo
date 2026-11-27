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


class PersistedScanBenchmarkTests(unittest.TestCase):
    def evidence(self, mode, frames=None, **changes):
        import hashlib, json
        r=dict(tracking_mode=mode,coordinate_system="image_normalized",
               object_scope="heads_only" if mode=="head_flow" else "heads_and_ball_candidates",
               time_basis="nominal_frame_index_divided_by_reported_fps",
               source_fps_reported=25.,source_frame_count_reported=100,
               first_frame=10,end_frame_exclusive=14,sample_stride=2,
               frames=frames if frames is not None else [
                   dict(source_frame_index=i,second=i/25,detections=[]) for i in (10,12)])
        payload=dict(schema="vision-scan-v1",kind="tracklets",source_binding="fixture",
                     source_file_size=123,source_file_mtime_ns=456,source_bytes_verified=False,result=r)
        payload.update(changes)
        raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)
        return dict(payload,digest=hashlib.sha256(raw.encode()).hexdigest(),id=1,segment_id=1)

    def ref(self, i=10, **changes):
        r=dict(source_binding="fixture",image_width=1000,image_height=500,
               source_frame_index=i,completeness="complete",reference={"A":[100,100]})
        r.update(changes)
        return r

    def run_pair(self,a,b,refs):
        from services.detection_evaluation import compare_scan_windows
        return compare_scan_windows(a,b,refs,5,width=1000,height=500)

    def test_flow_provenance_and_ball_exclusion(self):
        def frame(i,points):return dict(source_frame_index=i,second=i/25,detections=points)
        head=dict(kind="head",x=.1,y=.2)
        ball=dict(kind="ball",x=.1,y=.2)
        a=self.evidence("baseline",[frame(10,[ball]),frame(12,[])])
        b=self.evidence("head_flow",[frame(10,[dict(head,point_source="optical_flow")]),frame(12,[])])
        r=self.run_pair(a,b,[self.ref(),self.ref(99)])
        self.assertEqual(r["candidate_counts"],dict(baseline_heads=0,head_flow_detector_heads=0,head_flow_propagated_heads=1))
        self.assertEqual(r["reference_frames_outside_window"],1)
        self.assertEqual(r["all_candidates"]["methods"]["head_flow"]["recall_complete"],1)
        self.assertEqual(r["detector_only"]["methods"]["head_flow"]["recall_complete"],0)
        self.assertFalse(r["statistical_use_allowed"])

    def test_no_annotations_and_tampered_digest(self):
        a,b=self.evidence("baseline"),self.evidence("head_flow")
        r=self.run_pair(a,b,[])
        self.assertEqual(r["sampled_frames"],2)
        self.assertEqual(r["all_candidates"]["state"],"not_measured")
        b["result"]["frames"][0]["second"]=0
        with self.assertRaisesRegex(ValueError,"digest"):self.run_pair(a,b,[])

    def test_different_source_and_dimensions(self):
        a=self.evidence("baseline")
        with self.assertRaisesRegex(ValueError,"source bindings"):
            self.run_pair(a,self.evidence("head_flow",source_binding="other"),[])
        with self.assertRaisesRegex(ValueError,"dimensions"):
            self.run_pair(a,self.evidence("head_flow"),[self.ref(image_width=500)])

    def test_missing_frame_and_unknown_flow_provenance(self):
        a=self.evidence("baseline")
        with self.assertRaisesRegex(ValueError,"scan frames"):
            self.run_pair(a,self.evidence("head_flow",[]),[])
        b=self.evidence("head_flow",[
            dict(source_frame_index=10,second=.4,detections=[dict(kind="head",x=.1,y=.2)]),
            dict(source_frame_index=12,second=.48,detections=[])])
        with self.assertRaisesRegex(ValueError,"provenance"):self.run_pair(a,b,[])
