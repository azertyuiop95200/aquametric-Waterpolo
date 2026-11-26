import unittest
from services.elite_performance import elite_report, shot_clock_reset

def event(typ, note="", phase="even_attack", side="for", confidence="CONFIRMED", pid=11, i=0):
    return {"event_type":typ,"note":note,"phase":phase,"perspective":side,
            "confidence":confidence,"player_id":pid,"player":"Test","id":i}

class EliteTests(unittest.TestCase):
    def test_shots_and_possessions(self):
        r=elite_report([event("goal"),event("shot_on_target"),event("shot_off_target"),
            event("possession_end","outcome=goal"),event("possession_end","outcome=steal"),
            event("possession_end"),event("goal",confidence="LOW")])["team"]
        self.assertEqual(r["shots"],3)
        self.assertEqual(r["shot_accuracy"],66.7)
        self.assertEqual(r["shot_conversion"],33.3)
        self.assertEqual(r["attack_conversion"],50)
        self.assertEqual(r["possession_ends"],3)
    def test_time_distance_and_rules(self):
        r=elite_report([event("player_in","period=1 game_clock_s=480",i=1),
            event("player_out","period=1 game_clock_s=300",i=2),
            event("player_in","period=2 game_clock_s=480",i=3),
            event("distance_sample","distance_m=25"),event("distance_sample","distance_m=nan")])["players"][0]
        self.assertEqual(r["playing_seconds"],180)
        self.assertEqual(r["unpaired_markers"],1)
        self.assertEqual(r["distance_m"],25)
        self.assertEqual(shot_clock_reset("new_possession"),28)
        self.assertEqual(shot_clock_reset("exclusion",24),24)
        self.assertEqual(shot_clock_reset("exclusion",5),18)
    def test_special_teams_and_missing(self):
        r=elite_report([event("power_play_end","outcome=goal"),event("power_play_end","outcome=no_goal"),
            event("penalty_kill_end","outcome=no_goal"),event("goal",phase="penalty")])["team"]
        self.assertEqual(r["power_play_conversion"],50)
        self.assertEqual(r["penalty_kill_success"],100)
        self.assertEqual(r["penalty_conversion"],100)
        self.assertIsNone(r["distance_m"])
        self.assertIsNone(elite_report([])["team"]["attack_conversion"])

if __name__ == "__main__":
    unittest.main()
