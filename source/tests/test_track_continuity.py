import unittest,gzip,json,tempfile
from services.track_continuity import propose_links,summarize,load_tracks
def tr(k,start,x=.3,colour='light'):
    return {'id':k,'colour':colour,'points':[(i,i*.04,x+.001*i,.5) for i in range(start,start+8)]}
class Tests(unittest.TestCase):
    def test_short_gap_and_no_imputation(self):
        t={1:tr(1,0),2:tr(2,10)};l=propose_links(t,[])
        self.assertEqual(len(l),1);r=summarize(t,l,18)
        self.assertEqual(r['candidate_chains'],1);self.assertEqual(r['observations_after'],16);self.assertEqual(r['missing_frames_not_filled'],2)
    def test_cut(self):self.assertEqual(propose_links({1:tr(1,0),2:tr(2,10)},[9]),[])
    def test_colour(self):self.assertEqual(propose_links({1:tr(1,0),2:tr(2,10,colour='dark')},[]),[])
    def test_ambiguity(self):self.assertEqual(propose_links({1:tr(1,0),2:tr(2,10),3:tr(3,10,x=.301)},[]),[])
    def test_overlap(self):self.assertEqual(propose_links({1:tr(1,0),2:tr(2,5)},[]),[])
    def test_long_gap(self):self.assertEqual(propose_links({1:tr(1,0),2:tr(2,20)},[]),[])
    def test_reverse_ambiguity(self):self.assertEqual(propose_links({1:tr(1,0),2:tr(2,0,x=.301),3:tr(3,10)},[]),[])
    def test_wrong_motion(self):self.assertEqual(propose_links({1:tr(1,0),2:tr(2,10,x=.36)},[]),[])
    def test_missing_frame(self):
        with tempfile.TemporaryDirectory() as d:
            p=d+'/a.gz'
            with gzip.open(p,'wt') as f:f.write(json.dumps({'frame':1,'second':.04})+'\n')
            with self.assertRaises(ValueError):load_tracks(p)
