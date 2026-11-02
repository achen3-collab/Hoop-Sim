import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import apply_yahoo_adp as adp_sorter


class ApplyYahooAdpTests(unittest.TestCase):
    def test_sorts_both_pools_and_places_unranked_players_last(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "yahoo-adp-2026-27.json").write_text(json.dumps({
                "season": "2026-27",
                "updatedAt": "2026-11-02",
                "source": "https://example.com/adp",
                "players": [
                    {"name": "B Player", "adp": 2.0},
                    {"name": "Alperen Şengün", "adp": 1.5},
                ],
            }), encoding="utf-8")
            for filename in adp_sorter.POOL_FILES:
                (data / filename).write_text(json.dumps({
                    "season": "2026-27",
                    "players": [
                        {"name": "Zoe Unranked"},
                        {"name": "Alperen Sengun"},
                        {"name": "B Player"},
                        {"name": "Alpha Unranked", "yahooAdp": 99},
                    ],
                }), encoding="utf-8")

            results = adp_sorter.apply_yahoo_adp(data, data / "yahoo-adp-2026-27.json")

            pools = {
                filename: json.loads((data / filename).read_text(encoding="utf-8"))
                for filename in adp_sorter.POOL_FILES
            }

        self.assertEqual(results, {
            "players-2026-27.json": (2, 2),
            "live-players-2026-27.json": (2, 2),
        })
        for pool in pools.values():
            players = pool["players"]
            self.assertEqual(
                [player["name"] for player in players],
                ["Alperen Sengun", "B Player", "Alpha Unranked", "Zoe Unranked"],
            )
            self.assertEqual(players[0]["yahooAdp"], 1.5)
            self.assertEqual(players[1]["yahooAdp"], 2.0)
            self.assertNotIn("yahooAdp", players[2])
            self.assertEqual(pool["yahooAdpUpdatedAt"], "2026-11-02")
            self.assertEqual(pool["yahooAdpSource"], "https://example.com/adp")

    def test_rejects_duplicate_normalized_rankings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rankings.json"
            path.write_text(json.dumps({
                "season": "2026-27",
                "updatedAt": "2026-11-02",
                "source": "https://example.com/adp",
                "players": [
                    {"name": "Test Player", "adp": 2},
                    {"name": "Test-Player", "adp": 3},
                ],
            }), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate"):
                adp_sorter.load_adp(path)


if __name__ == "__main__":
    unittest.main()
