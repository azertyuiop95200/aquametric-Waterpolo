import unittest
from services.review_coverage import coverage
from test_pass_review import sample
from test_review_reference_import import read
from services.review_reference_import import summarize
from jinja2 import Environment, FileSystemLoader

def w(id,a,b,step=5,view='full_frame'):
    return dict(id=id,first_frame=a,last_frame=b,step_frames=step,view=view,sample_count=(b-a)//step+1,sheets=[dict(path=f'preuves/{id}.jpg',sha256='a'*64,bytes=100)])
def review(*rows):
    return dict(fps=25,review_windows=list(rows))
class ReviewCoverageTests(unittest.TestCase):
    def test_legacy(self):self.assertIsNone(coverage(dict(fps=25),8))
    def test_empty(self):
        c=coverage(review(),8);self.assertEqual(c['remaining_unregistered_span_s'],8);self.assertEqual(c['distinct_full_frame_samples'],0)
    def test_overlap(self):
        c=coverage(review(w('A',0,50),w('B',25,75)),8)
        self.assertEqual(c['distinct_full_frame_samples'],16);self.assertEqual(c['declared_samples'],22);self.assertEqual(c['registered_full_frame_span_s'],3.04)
    def test_crop_not_full(self):
        c=coverage(review(w('A',0,10),w('B',10,20,1,'crop')),8)
        self.assertEqual(c['distinct_full_frame_samples'],3);self.assertEqual(c['distinct_crop_samples'],11);self.assertEqual(c['distinct_any_samples'],13)
        self.assertEqual(c['registered_full_frame_span_s'],.44)
    def test_gaps(self):
        c=coverage(review(w('A',5,15),w('B',25,35)),2)
        self.assertEqual([(x['first_frame'],x['end_frame_exclusive']) for x in c['gaps']],[(0,5),(16,25),(36,50)])
        self.assertEqual(c['largest_gap']['first_frame'],36)
    def test_complete_frame_span_not_complete_annotation(self):
        c=coverage(review(w('A',0,49,1)),2)
        self.assertEqual(c['registered_full_frame_span_pct'],100);self.assertFalse(c['complete_annotation']);self.assertFalse(c['files_verified_on_server'])
    def test_invalid_bounds(self):
        with self.assertRaises(ValueError):coverage(review(w('A',0,50)),2)
    def test_stride_alignment(self):
        with self.assertRaises(ValueError):coverage(review(w('A',0,9)),2)
    def test_count(self):
        x=w('A',0,10);x['sample_count']=99
        with self.assertRaises(ValueError):coverage(review(x),2)
    def test_duplicate(self):
        with self.assertRaises(ValueError):coverage(review(w('A',0,10),w('A',0,10)),2)
    def test_bad_path(self):
        x=w('A',0,10);x['sheets'][0]['path']='preuves/../a.jpg'
        with self.assertRaises(ValueError):coverage(review(x),2)
    def test_conflicting_path(self):
        x,y=w('A',0,10),w('B',0,10);y['sheets'][0].update(path='preuves/A.jpg',sha256='b'*64)
        with self.assertRaises(ValueError):coverage(review(x,y),2)
    def test_integration(self):
        p=sample();p['reference']['pass_review']['review_windows']=[w('A',0,50)]
        s=summarize(read(p)[0],'bleus')['pass_review'];self.assertEqual(s['review_coverage']['distinct_full_frame_samples'],11)
        h=Environment(loader=FileSystemLoader('source/templates')).get_template('pass_review_report.html').render(p={'pass_review':s,'home_color':'bleus'},ref={'period':1})
        self.assertIn('Intervalles non inscrits',h);self.assertIn('11 / 200',h)
