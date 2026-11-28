import unittest
from services.candidate_review import make_packet,validate_response,digest

def p(x):return dict(kind='head',x=x,y=.5)
def packet():return make_packet('a'*64,2,'b'*64,1280,720,[p(.1)],[p(.1),p(.5),p(.8)])
class CandidateReviewTests(unittest.TestCase):
 def test_binding(self):
  a=packet();self.assertEqual(a,packet());self.assertEqual(len(a['candidates']),2);self.assertFalse(a['statistical_use_allowed'])
 def test_hash_changes(self):
  a=packet();b=make_packet('a'*64,3,'b'*64,1280,720,[p(.1)],[p(.1),p(.5),p(.8)]);self.assertNotEqual(a['packet_sha256'],b['packet_sha256'])
 def test_partial(self):
  a=packet();r=validate_response(a,dict(packet_sha256=a['packet_sha256'],decisions=[dict(candidate_id='C01',label='uncertain')]))
  self.assertEqual(r['unreviewed'],1);self.assertFalse(r['complete']);self.assertFalse(r['statistical_use_allowed']);self.assertTrue(r['training_labels_require_verification'])
 def test_complete(self):
  a=packet();r=validate_response(a,dict(packet_sha256=a['packet_sha256'],decisions=[dict(candidate_id='C01',label='head_present'),dict(candidate_id='C02',label='not_head')]))
  self.assertTrue(r['complete']);self.assertEqual(r['counts']['head_present'],1);self.assertEqual(r['counts']['not_head'],1)
 def test_modified_packet(self):
  a=packet();a['source_frame_index']=4
  with self.assertRaises(ValueError):validate_response(a,dict(packet_sha256=a['packet_sha256'],decisions=[]))
 def test_wrong_digest(self):
  a=packet()
  with self.assertRaises(ValueError):validate_response(a,dict(packet_sha256='0'*64,decisions=[]))
 def test_invalid_decisions(self):
  a=packet()
  for ds in ([dict(candidate_id='C99',label='not_head')],[dict(candidate_id='C01',label='goal')],[dict(candidate_id='C01',label='not_head')]*2):
   with self.assertRaises(ValueError):validate_response(a,dict(packet_sha256=a['packet_sha256'],decisions=ds))
 def test_invalid_source(self):
  for s,i in [('x',0),('a'*64,True),('a'*64,-1)]:
   with self.assertRaises(ValueError):make_packet(s,i,'b'*64,1280,720,[],[])
 def test_budget(self):
  a=make_packet('a'*64,2,'b'*64,1280,720,[],[p(.1),p(.5)],budget=1);self.assertEqual(len(a['candidates']),1)

 def test_malformed_rehashed_packet(self):
  for key,value in [('width',1),('source_frame_index',True),('budget',0),('candidates',[{'candidate_id':'C01','x':2,'y':0,'origin':'learned_only'}])]:
   a=packet();a[key]=value;a['packet_sha256']=digest({k:v for k,v in a.items() if k!='packet_sha256'})
   with self.assertRaises(ValueError):validate_response(a,dict(packet_sha256=a['packet_sha256'],decisions=[]))
