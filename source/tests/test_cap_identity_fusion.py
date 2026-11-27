import unittest
from services.cap_identity_fusion import fuse, enforce_unique_candidates

R = {"A": {1, 4, 7}, "B": {1, 4, 7}}

def r(f, s="A", c=4, p=.95):
    return {"frame": f, "side": s, "cap": c, "score": p}

def t(track_id, start, end, side="A", cap=4, support=5, share=.9):
    return {
        "track_id": track_id,
        "start_second": start,
        "end_second": end,
        "candidate": (side, cap),
        "support": support,
        "share": share,
        "status": "review_candidate",
    }

class FusionTests(unittest.TestCase):
    def test_consensus(self):
        self.assertEqual(fuse([r(1), r(2), r(3), r(4), r(5, c=7)], R)["candidate"], ("A", 4))

    def test_duplicate(self):
        self.assertIsNone(fuse([r(1)] * 20, R)["candidate"])

    def test_teams(self):
        self.assertIsNone(fuse([r(1), r(2), r(3, "B"), r(4, "B")], R)["candidate"])

    def test_conflict(self):
        self.assertIsNone(fuse([r(1), r(1, c=7), r(2), r(3)], R)["candidate"])

    def test_low(self):
        self.assertIsNone(fuse([r(i, p=.3) for i in range(10)], R)["candidate"])

    def test_unknown(self):
        self.assertIsNone(fuse([r(i, c=99) for i in range(10)], R)["candidate"])

    def test_empty(self):
        self.assertIsNone(fuse([], R)["share"])

    def test_red_unknown_team(self):
        self.assertIsNone(fuse([r(i, "red", 1) for i in range(5)], R)["candidate"])

    def test_no_confirmation(self):
        self.assertEqual(fuse([r(i) for i in range(3)], R)["status"], "review_candidate")

    def test_invalid(self):
        self.assertRaises(ValueError, fuse, [r(1, p=float("nan"))], R)

class UniquenessTests(unittest.TestCase):
    def test_stronger_overlapping_track_wins(self):
        out = enforce_unique_candidates([t("strong", 0, 2, support=7, share=.95), t("weak", 1, 3, support=4, share=.90)])
        by = {x["track_id"]: x for x in out["tracks"]}
        self.assertEqual(by["strong"]["candidate"], ("A", 4))
        self.assertIsNone(by["weak"]["candidate"])
        self.assertEqual(out["conflict_pairs"], 1)
        self.assertEqual(out["rejected_tracks"], 1)

    def test_tie_rejects_both(self):
        out = enforce_unique_candidates([t("x", 0, 2), t("y", 1, 3)])
        self.assertTrue(all(x["candidate"] is None for x in out["tracks"]))
        self.assertEqual(out["rejected_tracks"], 2)

    def test_nonoverlap_can_reuse_identity(self):
        out = enforce_unique_candidates([t("x", 0, 1), t("y", 1, 2)])
        self.assertEqual(out["remaining_candidates"], 2)
        self.assertEqual(out["conflict_pairs"], 0)

    def test_same_cap_opposing_teams_is_not_collision(self):
        out = enforce_unique_candidates([t("x", 0, 2, side="A", cap=4), t("y", 1, 3, side="B", cap=4)])
        self.assertEqual(out["remaining_candidates"], 2)

    def test_chain_keeps_two_nonoverlapping_strong_tracks(self):
        rows = [
            t("left", 0, 1.5, support=8, share=.95),
            t("middle", 1, 3, support=4, share=.80),
            t("right", 2.5, 4, support=8, share=.95),
        ]
        out = enforce_unique_candidates(rows)
        by = {x["track_id"]: x for x in out["tracks"]}
        self.assertIsNotNone(by["left"]["candidate"])
        self.assertIsNone(by["middle"]["candidate"])
        self.assertIsNotNone(by["right"]["candidate"])
        self.assertEqual(out["conflict_pairs"], 2)

    def test_share_margin_can_break_support_tie(self):
        out = enforce_unique_candidates([t("clear", 0, 2, support=5, share=.96), t("noisy", 1, 3, support=5, share=.82)])
        by = {x["track_id"]: x for x in out["tracks"]}
        self.assertIsNotNone(by["clear"]["candidate"])
        self.assertIsNone(by["noisy"]["candidate"])

    def test_input_not_mutated(self):
        rows = [t("x", 0, 2), t("y", 1, 3)]
        original = [dict(x) for x in rows]
        enforce_unique_candidates(rows)
        self.assertEqual(rows, original)

    def test_duplicate_track_id_invalid(self):
        self.assertRaises(ValueError, enforce_unique_candidates, [t("x", 0, 1), t("x", 2, 3)])

    def test_bad_interval_invalid(self):
        self.assertRaises(ValueError, enforce_unique_candidates, [t("x", 2, 1)])

    def test_unresolved_track_does_not_conflict(self):
        a = t("x", 0, 2)
        b = t("y", 1, 3)
        b["candidate"] = None
        b["share"] = None
        b["support"] = 0
        out = enforce_unique_candidates([a, b])
        self.assertEqual(out["remaining_candidates"], 1)
        self.assertEqual(out["conflict_pairs"], 0)

if __name__ == "__main__":
    unittest.main()
