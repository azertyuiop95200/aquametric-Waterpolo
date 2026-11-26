import unittest
import numpy as np
from services.physical_board import read_physical_board, consensus
class PhysicalBoardTests(unittest.TestCase):
    def test_actual_q1_regression(self):
        rows=[dict(second=t,white_score=0,blue_score=7,display_clock=c) for t,c in [(788.72,None),(789.72,'0:15'),(790.72,None),(791.02,'0:16')]]
        r=consensus(rows)
        self.assertEqual((r['white_score'],r['blue_score']),(0,7))
        self.assertEqual(r['observations'],4)
        self.assertEqual(r['display_clock_direction'],'unknown')
        self.assertEqual(r['scope'],'observed_score_not_event_total')
    def test_reject_single_or_duplicate_frame(self):
        r=dict(second=1,white_score=0,blue_score=7,display_clock='0:13')
        self.assertIsNone(consensus([r,r]))
    def test_clock_not_game_clock(self):
        r=consensus([dict(second=i,white_score=0,blue_score=7,display_clock=f'0:{10+i}') for i in range(3)])
        self.assertEqual(r['display_clock_direction'],'increasing')
        self.assertEqual(r['clock_kind'],'unresolved')
    def test_water_only(self):
        f=np.full((720,1280,3),(155,145,60),np.uint8)
        self.assertIsNone(read_physical_board(f,lambda im,k:'7'))
