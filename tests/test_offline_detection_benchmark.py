import copy,unittest
from services.offline_detection_benchmark import manifest,evaluate,digest

def fixture():
    m=manifest([dict(source_sha256='a'*64,frame_index=0,height=720,width=1280,image_sha256='b'*64)])
    f=m['frames'][0];key=dict(frame_id=f['frame_id'],image_sha256=f['image_sha256'])
    r=dict(manifest_sha256=m['manifest_sha256'],frames=[dict(key,reference={'head_center':dict(completeness='partial',objects={'A':[.5,.5]}),'ball_center':dict(completeness='unknown',objects={})})])
    p=dict(manifest_sha256=m['manifest_sha256'],model_id='test',supported_geometries=['head_center','ball_center'],frames=[dict(key,predictions={'head_center':[[.5,.5],[.7,.7]],'ball_center':[[.5,.5]]})])
    return m,r,p

class OfflineTests(unittest.TestCase):
    def test_partial(self):
        a=evaluate(*fixture());r=a['summary']['head_center']['partial'];self.assertEqual((r['marked'],r['matched'],r['predictions']),(1,1,2));self.assertIsNone(r['precision']);self.assertFalse(a['statistical_use_allowed'])
    def test_complete(self):
        m,r,p=fixture();r['frames'][0]['reference']['head_center']['completeness']='complete';a=evaluate(m,r,p);self.assertEqual(a['summary']['head_center']['complete']['precision'],.5)
    def test_unknown(self):
        a=evaluate(*fixture());self.assertEqual(a['summary']['ball_center']['status_counts'],{'unknown_reference':1});self.assertIsNone(a['summary']['ball_center']['complete']['precision'])
    def test_missing_frame(self):
        m,r,p=fixture();p['frames']=[]
        with self.assertRaises(ValueError):evaluate(m,r,p)
    def test_wrong_image(self):
        m,r,p=fixture();p['frames'][0]['image_sha256']='c'*64
        with self.assertRaises(ValueError):evaluate(m,r,p)
    def test_changed_manifest(self):
        m,r,p=fixture();m['thresholds']['head_center']=100
        with self.assertRaises(ValueError):evaluate(m,r,p)
    def test_wrong_manifest(self):
        m,r,p=fixture();p['manifest_sha256']='0'*64
        with self.assertRaises(ValueError):evaluate(m,r,p)
    def test_duplicate_frame(self):
        m,r,p=fixture()
        with self.assertRaises(ValueError):manifest(m['frames']*2)
    def test_bad_geometry(self):
        for coords in ([.4,.4,.6,.6],[float('nan'),.5],[1.1,.5],[True,.5]):
            m,r,p=fixture();p['frames'][0]['predictions']['head_center']=[coords]
            with self.assertRaises(ValueError):evaluate(m,r,p)
    def test_incompatible_geometry(self):
        m,r,p=fixture();p['supported_geometries']=['player_box'];p['frames'][0]['predictions']={'player_box':[[.4,.4,.6,.6]]};a=evaluate(m,r,p);self.assertEqual(a['summary']['head_center']['status_counts'],{'unsupported_geometry':1});self.assertIsNone(a['summary']['head_center']['partial']['recall'])
    def test_box_iou(self):
        m,r,p=fixture();r['frames'][0]['reference']={'player_box':dict(completeness='complete',objects={'A':[.2,.2,.4,.4]})};p['supported_geometries']=['player_box'];p['frames'][0]['predictions']={'player_box':[[.2,.2,.4,.4],[.7,.7,.9,.9]]};a=evaluate(m,r,p);self.assertEqual(a['summary']['player_box']['complete']['precision'],.5)
    def test_box_degenerate(self):
        m,r,p=fixture();p['supported_geometries']=['player_box'];p['frames'][0]['predictions']={'player_box':[[.4,.3,.2,.7]]}
        with self.assertRaises(ValueError):evaluate(m,r,p)
    def test_ball_top1_separate_from_matching(self):
        m,r,p=fixture();r['frames'][0]['reference']['ball_center']=dict(completeness='complete',objects={'ball':[.5,.5]});p['frames'][0]['predictions']['ball_center']=[[.508,.5],[.5,.5]];a=evaluate(m,r,p);self.assertEqual(a['summary']['ball_center']['first_ball_candidate_matched'],1);self.assertEqual(a['summary']['ball_center']['complete']['matched'],1)
    def test_negative_complete(self):
        m,r,p=fixture();r['frames'][0]['reference']['ball_center']=dict(completeness='complete',objects={});a=evaluate(m,r,p);self.assertEqual(a['summary']['ball_center']['complete']['precision'],0);self.assertIsNone(a['summary']['ball_center']['complete']['recall'])
    def test_missing_declared_class(self):
        m,r,p=fixture();del p['frames'][0]['predictions']['ball_center']
        with self.assertRaises(ValueError):evaluate(m,r,p)
    def test_unknown_nonempty(self):
        m,r,p=fixture();r['frames'][0]['reference']['ball_center']['objects']={'ball':[.5,.5]}
        with self.assertRaises(ValueError):evaluate(m,r,p)
