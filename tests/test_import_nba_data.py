import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import import_nba_data as importer


class ImportAggregationTests(unittest.TestCase):
    def test_aggregate_computes_weighted_percentages_and_eff(self):
        base = {
            "PLAYER_ID": 42,
            "PLAYER_NAME": "Test Player",
            "TEAM_ABBREVIATION": "TST",
            "GAME_ID": "1",
            "GAME_DATE": "2026-10-20T00:00:00",
        }
        first = {**base, "FGM": 7, "FGA": 15, "FTM": 4, "FTA": 5, "FG3M": 2, "FG3A": 6, "OREB": 1, "DREB": 4, "REB": 5, "AST": 4, "STL": 1, "BLK": 0, "TOV": 3, "PF": 2, "PTS": 20, "PLUS_MINUS": 1, "MIN": 35}
        second = {**base, "GAME_ID": "2", "FGM": 4, "FGA": 10, "FTM": 2, "FTA": 2, "FG3M": 1, "FG3A": 3, "OREB": 0, "DREB": 3, "REB": 3, "AST": 2, "STL": 0, "BLK": 1, "TOV": 1, "PF": 1, "PTS": 10, "PLUS_MINUS": -2, "MIN": 28}

        pool = importer.build_pool("2026-27", [first, second], "2026-10-21T00:00:00+00:00", {42: {"PG"}}, {"42": 17.25})
        player = pool["players"][0]

        self.assertEqual(pool["gameCount"], 2)
        self.assertEqual(pool["playerGameLines"], 2)
        self.assertEqual(player["GP"], 2)
        self.assertEqual(player["FG_PCT"], 0.44)
        self.assertEqual(player["FT_PCT"], 0.8571)
        self.assertEqual(player["EFF"], 13.5)
        self.assertEqual(player["PER"], 17.25)
        self.assertEqual(player["positions"], ["PG"])
        self.assertEqual(player["gameLogs"][0]["matchup"], "")

    def test_live_import_writes_separate_game_log_pool(self):
        game = {
            "PLAYER_ID": 42,
            "PLAYER_NAME": "Test Player",
            "TEAM_ABBREVIATION": "TST",
            "GAME_ID": "1",
            "GAME_DATE": "2026-10-20",
            "MATCHUP": "TST vs. OPP",
            "FGM": 7,
            "FGA": 15,
            "FTM": 4,
            "FTA": 5,
            "FG3M": 2,
            "FG3A": 6,
            "OREB": 1,
            "DREB": 4,
            "REB": 5,
            "AST": 4,
            "STL": 1,
            "BLK": 0,
            "TOV": 3,
            "PF": 2,
            "PTS": 20,
            "PLUS_MINUS": 1,
            "MIN": 35,
        }
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            with patch.object(importer, "DATA", data), patch.object(importer, "fetch_logs", return_value=[game]), patch.object(importer, "fetch_player_per", return_value={"42": 15.5}):
                pool = importer.import_live_season("2026-27")

            saved = json.loads((data / "live-players-2026-27.json").read_text(encoding="utf-8"))

        self.assertEqual(saved["playerCount"], 1)
        self.assertEqual(saved["players"][0]["gameLogs"][0]["matchup"], "TST vs. OPP")
        self.assertEqual(saved["players"][0]["stats"]["PTS"], 20)
        self.assertEqual(saved["players"][0]["stats"]["PER"], 15.5)
        self.assertEqual(pool["gameCount"], 1)

    def test_fetch_player_per_uses_advanced_stats_rows(self):
        with patch.object(importer, "api", return_value={
            "resultSets": [{
                "headers": ["PLAYER_ID", "PER"],
                "rowSet": [[42, 18.25], [73, None]],
            }],
        }) as request:
            self.assertEqual(importer.fetch_player_per("2026-27"), {"42": 18.25})

        self.assertEqual(request.call_args.args[0], "leaguedashplayerstats")
        self.assertEqual(request.call_args.args[1]["MeasureType"], "Advanced")
        self.assertEqual(request.call_args.args[1]["Season"], "2026-27")

    def test_normalizes_combined_roster_positions(self):
        self.assertEqual(importer.normalize_positions("G-F"), {"G", "F"})
        self.assertEqual(importer.normalize_positions("F-C"), {"F", "C"})
        self.assertEqual(importer.normalize_positions("PG/SG"), {"G"})

    def test_normalizes_nba_game_log_date(self):
        self.assertEqual(importer.game_date("OCT 20, 2026"), "2026-10-20")
        self.assertEqual(importer.game_date("2026-10-20T00:00:00"), "2026-10-20")


if __name__ == "__main__":
    unittest.main()
