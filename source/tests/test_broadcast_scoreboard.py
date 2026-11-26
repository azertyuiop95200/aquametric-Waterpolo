import unittest
import cv2
import numpy as np
from services.broadcast_scoreboard import read_broadcast_scoreboard, clock_changes

class BroadcastScoreboardTests(unittest.TestCase):
    def fixture(self):
        f=np.zeros((1078,1918,3),np.uint8)
        cv2.putText(f,"2",(289,78),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,220,0),2)
        cv2.putText(f,"18",(344,78),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,220,220),2)
        return f
    def test_layout_and_invalid_fields(self):
        values={"home":"0","away":"6","clock":"06:53","period":"2","shot":"18"}
        result=read_broadcast_scoreboard(self.fixture(),lambda im,k:(values[k],.9))
        self.assertEqual((result["home_score"],result["away_score"],result["period"],result["shot_clock_seconds"]),(0,6,2,18))
        values["home"]="166"
        self.assertEqual(read_broadcast_scoreboard(self.fixture(),lambda im,k:(values[k],.9)),{})
        self.assertIsNone(read_broadcast_scoreboard(np.full((1078,1918,3),255,np.uint8),lambda im,k:("",0)))
    def test_reset_unknown_cause(self):
        rows=[{"second":10.8,"period":2,"clock_seconds":404,"shot_clock_seconds":8},{"second":12.6,"period":2,"clock_seconds":404,"shot_clock_seconds":28}]
        result=clock_changes(rows)
        self.assertEqual(result[0]["reason"],"unknown")
        self.assertEqual(result[0]["after"],28)
        self.assertEqual(clock_changes([rows[0],dict(rows[1],is_replay=True)]),[])
    def test_tight_crop_retries_unreadable_digit(self):
        image=self.fixture()
        cv2.putText(image,"0",(240,61),cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),2)
        values={"home":"0","away":"6","clock":"06:49","period":"2","shot":"14"}
        seen=[]
        def read(img,key):
            if key=="home":
                seen.append(img.shape)
                if len(seen)==1:
                    return "",0.0
            return values[key],.95
        result=read_broadcast_scoreboard(image,read)
        self.assertEqual(result["home_score"],0)
        self.assertEqual(len(seen),2)
        self.assertNotEqual(seen[0],seen[1])
