import unittest
from unittest.mock import patch
import cv2,numpy as np
from services.learned_head import hog,detect_heads,review_disagreements

def p(x,y=.5):return dict(kind='head',x=x,y=y,status='candidate',ranking_score=.3)
class LearnedHeadTests(unittest.TestCase):
 def test_unavailable_hog(self):
  with patch('services.learned_head.cv2',new=object()):
   with self.assertRaisesRegex(ValueError,'HOG indisponible'):hog()
 def test_valid_hog(self):
  f=np.full((240,320,3),100,np.uint8);v=[0.]*hog().getDescriptorSize();self.assertEqual(detect_heads(f,v,-1),[])
 def test_bad_model(self):
  f=np.zeros((240,320,3),np.uint8)
  for w,b in [([],0),([float('nan')]*hog().getDescriptorSize(),0),([0.]*hog().getDescriptorSize(),True),([0.]*hog().getDescriptorSize(),float('inf'))]:
   with self.assertRaises(ValueError):detect_heads(f,w,b)
 def test_bad_frame(self):
  with self.assertRaises(ValueError):detect_heads(np.zeros((128,2000,3),np.uint8),[],0)
 def test_invalid_budget(self):
  with self.assertRaises(ValueError):detect_heads(np.zeros((240,320,3),np.uint8),[0.]*hog().getDescriptorSize(),0,limit=25)
 def test_no_duplicate(self):
  r=review_disagreements([p(.1)],[p(.101),p(.5),p(.501),p(.8)],1280,720);self.assertEqual(len(r['additional_review_candidates']),2);self.assertEqual(r['total_review_candidates'],3)
 def test_bounded(self):
  r=review_disagreements([], [p(i/20) for i in range(1,21)],1280,720);self.assertEqual(len(r['additional_review_candidates']),6)
 def test_baseline_preserved(self):
  b=[p(.2)];r=review_disagreements(b,[p(.6)],1280,720);self.assertEqual(b,r['baseline']);self.assertIsNot(b[0],r['baseline'][0]);self.assertFalse(r['statistical_use_allowed']);self.assertFalse(r['identity_verified']);self.assertFalse(r['metrics_validated'])
 def test_zero_budget(self):
  self.assertEqual(review_disagreements([], [p(.5)],1280,720,extra_limit=0)['total_review_candidates'],0)
 def test_invalid_inputs(self):
  for a,b,w,h in [([p(2)],[],1280,720),([],[],1,1),([dict(kind='ball',x=.3,y=.4)],[],1280,720),([p(.4)]*25,[],1280,720)]:
   with self.assertRaises(ValueError):review_disagreements(a,b,w,h)
if __name__=='__main__':unittest.main()
