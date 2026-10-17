import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_csv_stats as publisher


CSV = """PLAYER_ID,PLAYER_NAME,TEAM_ABBREVIATION,GAME_ID,GAME_DATE,MATCHUP,FGM,FGA,FG3M,FG3A,FTM,FTA,OREB,DREB,REB,AST,STL,BLK,TOV,PF,PTS,PLUS_MINUS,MIN,PER
42,Test Player,TST,1,10/20/2026,TST vs. OPP,7,15,2,6,4,5,1,4,5,4,1,0,3,2,20,1,35:00,17
42,Test Player,TST,2,10/22/2026,TST @ OPP,4,10,1,3,2,2,0,3,3,2,0,1,1,1,10,-2,28:30,19
"""


class PublishCsvStatsTests(unittest.TestCase):
    def test_csv_updates_both_published_pools(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            csv_path = data / "stats.csv"
            csv_path.write_text(CSV, encoding="utf-8")
            draft_path = data / "players-2026-27.json"
            draft_path.write_text(json.dumps({
                "season": "2026-27",
                "players": [
                    {"id": "bref-test01", "name": "Test Player", "positions": ["G"], "stats": {"PTS": 0}},
                    {"id": "other01", "name": "Another Player", "positions": ["F"], "stats": {}},
                ],
            }), encoding="utf-8")

            player_count, updated, unmatched = publisher.publish_csv(csv_path, "2026-27", data)

            live = json.loads((data / "live-players-2026-27.json").read_text(encoding="utf-8"))
            draft = json.loads(draft_path.read_text(encoding="utf-8"))

        self.assertEqual((player_count, updated, unmatched), (1, 1, 0))
        player = live["players"][0]
        self.assertEqual(player["id"], "42")
        self.assertEqual(player["stats"]["GP"], 2)
        self.assertEqual(player["stats"]["PTS"], 15)
        self.assertEqual(player["stats"]["MIN"], 31.75)
        self.assertEqual(player["stats"]["FG_PCT"], 0.44)
        self.assertEqual(player["stats"]["FT_PCT"], 0.8571)
        self.assertEqual(player["stats"]["PER"], 18)
        self.assertEqual(live["gameCount"], 2)
        self.assertEqual(draft["players"][0]["id"], "bref-test01")
        self.assertEqual(draft["players"][0]["positions"], ["G"])
        self.assertEqual(draft["players"][0]["stats"]["PTS"], 15)
        self.assertEqual(draft["players"][0]["statsSeason"], "2026-27")
        self.assertEqual(len(draft["players"][0]["gameLogs"]), 2)
        self.assertEqual(draft["players"][1]["stats"], {})

    def test_dry_run_validates_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            csv_path = data / "stats.csv"
            csv_path.write_text(CSV, encoding="utf-8")
            draft_path = data / "players.json"
            original = json.dumps({"players": [{"name": "Test Player", "stats": {}}]})
            draft_path.write_text(original, encoding="utf-8")

            result = publisher.publish_csv(csv_path, "2025-26", data, dry_run=True)

            self.assertEqual(result, (1, 1, 0))
            self.assertFalse((data / "live-players-2025-26.json").exists())
            self.assertEqual(draft_path.read_text(encoding="utf-8"), original)

    def test_ambiguous_names_are_not_written_to_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            csv_path = data / "stats.csv"
            csv_path.write_text(CSV, encoding="utf-8")
            (data / "players.json").write_text(json.dumps({
                "players": [
                    {"name": "Test Player", "stats": {}},
                    {"name": "Test-Player", "stats": {}},
                ],
            }), encoding="utf-8")

            result = publisher.publish_csv(csv_path, "2025-26", data)
            draft = json.loads((data / "players.json").read_text(encoding="utf-8"))
            live = json.loads((data / "live-players-2025-26.json").read_text(encoding="utf-8"))

        self.assertEqual(result, (1, 0, 1))
        self.assertEqual(draft["players"][0]["stats"], {})
        self.assertEqual(draft["players"][1]["stats"], {})
        self.assertEqual(live["playerCount"], 1)

    def test_rejects_missing_required_columns_and_invalid_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "stats.csv"
            csv_path.write_text("NAME,PTS\nTest Player,10\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "date columns"):
                publisher.read_csv_pool(csv_path, "2025-26")

            csv_path.write_text("NAME,DATE,PTS\nTest Player,2026-10-20,nan\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid number"):
                publisher.read_csv_pool(csv_path, "2025-26")


if __name__ == "__main__":
    unittest.main()
