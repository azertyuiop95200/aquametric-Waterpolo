import unittest
from services.execution_timing import execution_report

def m(n):
    return {"status":"corroborated","match":{"side":"for","cap_number":n}}
def e(key,t,n=8,kind="goal",receiver=None,u=None):
    return dict(key=key,counted=True,side="for",cap_number=n,event_type=kind,actor_position={"second":t},receiver_cap_number=receiver,receiver_position={"second":u},spatial_attribution={"actor":m(n),"receiver":m(receiver) if receiver else {}})
def span(a,b,n=8,status="identified"):
    return dict(start_second=a,end_second=b,side="for",cap_number=n,status=status)
class TimingTests(unittest.TestCase):
    def report(self,events,spans,rev="x"):
        return execution_report(events,{"intervals":spans,"source_revision":rev},source_revision="x")
    def test_receipt_to_shot(self):
        r=self.report([e("p",.5,2,"pass_complete",8,1),e("s",3)],[span(1,3)])["rows"][0]
        self.assertEqual((r["visible_control_before_release_s"],r["reception_to_release_s"]),(2,2))
    def test_no_receipt_is_not_full_control(self):
        r=self.report([e("s",3)],[span(1,3)])["rows"][0]
        self.assertIsNone(r["reception_to_release_s"])
    def test_missing_control_gap(self):
        self.assertFalse(self.report([e("s",3)],[span(1,2)])["rows"])
    def test_wrong_controller(self):
        self.assertFalse(self.report([e("s",3)],[span(1,3,2)])["rows"])
    def test_intervening_release(self):
        self.assertFalse(self.report([e("a",2),e("b",3)],[span(1,3)])["rows"])
    def test_duplicate_receipts(self):
        r=self.report([e("a",.3,2,"pass_complete",8,1),e("b",.4,3,"pass_complete",8,1.05),e("s",3)],[span(1,3)])["rows"][0]
        self.assertIsNone(r["reception_to_release_s"])
    def test_source_mismatch(self):
        self.assertEqual(self.report([],[],"y")["scope"],"source_unmatched")
    def test_conflict(self):
        self.assertEqual(self.report([],[span(1,3),span(2,4,2)])["scope"],"conflicting_control")
    def test_next_span_at_release(self):
        r=self.report([e("s",3)],[span(1,3),span(3,4,2)])["rows"][0]
        self.assertEqual(r["visible_control_before_release_s"],2)
