import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import calculate_estimated_per as estimator


def player(name, points, minutes, games=1):
    return {
        "name": name,
        "stats": {
            "GP": games,
            "MIN": minutes,
            "PTS": points,
            "REB": 0,
            "AST": 0,
            "STL": 0,
            "BLK": 0,
            "FGM": 0,
            "FGA": 0,
            "FTM": 0,
            "FTA": 0,
            "TOV": 0,
        },
    }


class CalculateEstimatedPerTests(unittest.TestCase):
    def test_normalizes_player_efficiency_to_league_average_of_15(self):
        test_player = player("Test Player", 20, 20)
        lower = player("Lower", 10, 20)
        higher = player("Higher", 30, 20)
        average = estimator.league_average([test_player, lower, higher])

        self.assertEqual(round(15 * (20 / 20) / average, 2), 15)
        self.assertIsNone(estimator.impact_per_game(player("No Games", 20, 20, games=0)))

    def test_applies_same_season_baseline_to_draft_and_data_pools(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            player_a = player("Player A", 10, 10)
            player_a["stats"]["PER"] = 18.25
            pools = {
                "players-2024-25.json": [player("Old Season", 15, 20)],
                "players.json": [player("Prior Season", 15, 20)],
                "players-2026-27.json": [
                    player_a,
                    player("Player B", 30, 10),
                    player("Zero Games", 0, 0, games=0),
                ],
                "live-players-2026-27.json": [
                    player("Player A", 10, 10),
                    player("Player C", 20, 10),
                ],
            }
            for filename, players in pools.items():
                (data / filename).write_text(json.dumps({"season": "2026-27", "players": players}), encoding="utf-8")

            results = estimator.apply_estimated_per(data)

            saved = {
                filename: json.loads((data / filename).read_text(encoding="utf-8"))
                for filename in pools
            }

        self.assertEqual(results, {
            "players-2024-25.json": 1,
            "players.json": 1,
            "players-2026-27.json": 2,
            "live-players-2026-27.json": 2,
        })
        draft_by_name = {item["name"]: item for item in saved["players-2026-27.json"]["players"]}
        live_by_name = {item["name"]: item for item in saved["live-players-2026-27.json"]["players"]}
        self.assertEqual(draft_by_name["Player A"]["estimatedPER"], live_by_name["Player A"]["estimatedPER"])
        self.assertEqual(draft_by_name["Player A"]["estimatedPER"], 7.5)
        self.assertEqual(draft_by_name["Player A"]["stats"]["PER"], 18.25)
        self.assertEqual(draft_by_name["Player B"]["estimatedPER"], 22.5)
        self.assertIsNone(draft_by_name["Zero Games"]["estimatedPER"])
        self.assertIsNone(draft_by_name["Zero Games"]["stats"]["estimatedPER"])
        self.assertEqual(saved["players-2026-27.json"]["estimatedPERMethod"], estimator.METHOD)


if __name__ == "__main__":
    unittest.main()
