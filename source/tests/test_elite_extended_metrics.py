import unittest
from services.elite_performance import reduce_side
class ExtendedMetrics(unittest.TestCase):
    def test_unknown_shot_and_duels(self):
        r=reduce_side([{"event_type":k} for k in ("goal","shot_unknown","duel_won","duel_lost","assist","key_pass","pass_complete","bad_pass","touch","centre_touch")])
        self.assertEqual(r["shots"],2)
        self.assertIsNone(r["shot_conversion"])
        self.assertEqual(r["duel_pct"],50)
        self.assertEqual(r["passes"],3)
        self.assertEqual(r["pass_accuracy"],75)
        self.assertEqual(r["touches"],2)
