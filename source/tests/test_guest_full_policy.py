import unittest
from unittest.mock import patch
from types import SimpleNamespace
from services.guest_ultimate import full_guest, guest_match_limit, upload_byte_limit, prohibit_paid_analysis

class GuestFullPolicy(unittest.TestCase):
    def test_full_mode(self):
        request=SimpleNamespace(session={"web_demo":True,"user_id":42})
        with patch.dict("os.environ",{"AQUAMETRIC_GUEST_FULL":"1","AQUAMETRIC_GUEST_MATCH_LIMIT":"0","AQUAMETRIC_GUEST_UPLOAD_MB":"250"}):
            self.assertTrue(full_guest(request))
            self.assertEqual(guest_match_limit(),0)
            self.assertEqual(upload_byte_limit(request,1024**3),250*1024**2)
            with self.assertRaises(Exception):
                prohibit_paid_analysis(request)
    def test_default(self):
        request=SimpleNamespace(session={"web_demo":True})
        with patch.dict("os.environ",{"AQUAMETRIC_GUEST_FULL":"0"}):
            self.assertFalse(full_guest(request))
            self.assertEqual(guest_match_limit(),3)
            self.assertEqual(upload_byte_limit(request,1024**3),30*1024**2)
