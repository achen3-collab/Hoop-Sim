import sys
import unittest
import json
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import import_basketball_reference as bref


class BasketballReferenceParserTests(unittest.TestCase):
    def test_parses_comment_wrapped_player_table_and_calculates_eff(self):
        page = '''<!-- <table id="per_game_stats"><tbody><tr>
        <th data-stat="ranker">1</th>
        <td data-stat="name_display"><a href="/players/t/testpl01.html">Test Player</a></td>
        <td data-stat="pos">PG-SG</td><td data-stat="games">10</td>
        <td data-stat="fg_per_g">5</td><td data-stat="fga_per_g">10</td>
        <td data-stat="fg_pct">.500</td><td data-stat="fg3_per_g">2</td>
        <td data-stat="fg3a_per_g">5</td><td data-stat="fg3_pct">.400</td>
        <td data-stat="ft_per_g">3</td><td data-stat="fta_per_g">4</td>
        <td data-stat="ft_pct">.750</td><td data-stat="orb_per_g">1</td>
        <td data-stat="drb_per_g">3</td><td data-stat="trb_per_g">4</td>
        <td data-stat="ast_per_g">6</td><td data-stat="stl_per_g">1</td>
        <td data-stat="blk_per_g">0</td><td data-stat="tov_per_g">2</td>
        <td data-stat="pf_per_g">2</td><td data-stat="pts_per_g">15</td>
        <td data-stat="team_name_abbr">TST</td></tr></tbody></table> -->'''
        rows = bref.parse_table(page, "per_game_stats")

        self.assertEqual(len(rows), 1)
        rows[0]["__slug"] = bref.slug_from_href(rows[0]["__href"])
        player = bref.season_player(rows[0], "2024-25")
        self.assertEqual(player["id"], "testpl01")
        self.assertEqual(player["positions"], ["G"])
        self.assertEqual(player["stats"]["FG_PCT"], 0.5)
        self.assertEqual(player["stats"]["EFF"], 18)

    def test_parses_minutes_and_dates(self):
        self.assertEqual(bref.parse_minutes("32:30"), 32.5)
        self.assertEqual(bref.parse_date("Oct 22, 2024"), "2024-10-22")

    def test_collects_real_team_codes_for_aggregate_rows(self):
        rows = "".join(
            f'<tr><td data-stat="name_display"><a href="/players/t/testpl01.html">Test Player</a></td><td data-stat="games">{games}</td><td data-stat="team_name_abbr">{team}</td></tr>'
            for team, games in (("2TM", "82"), ("BOS", "40"), ("MIA", "42"))
        )
        page = f'<table id="per_game_stats"><tbody>{rows}</tbody></table>'
        with patch.object(bref, "request_html", return_value=page):
            player = bref.fetch_player_rows("2024-25")[0]

        self.assertEqual(player["team_name_abbr"], "2TM")
        self.assertEqual(player["__teams"], ["BOS", "MIA"])

    def test_current_roster_replaces_aggregate_team_for_schedule(self):
        players = [{"id": "testpl01", "team": "2TM", "teams": ["BOS", "MIA"], "positions": ["G"]}]
        bref.apply_roster_map(players, {"testpl01": {"team": "MIA", "positions": ["F"]}})

        self.assertEqual(players[0]["team"], "MIA")
        self.assertEqual(players[0]["teams"], ["MIA"])
        self.assertEqual(players[0]["positions"], ["F"])
        self.assertEqual(players[0]["rosterSeason"], "2026-27")

    def test_current_roster_adds_new_players_with_blank_stats(self):
        players = []
        bref.apply_roster_map(players, {"newpl01": {"name": "New Player", "team": "BOS", "positions": ["G"]}})

        self.assertEqual(len(players), 1)
        self.assertEqual(players[0]["name"], "New Player")
        self.assertEqual(players[0]["team"], "BOS")
        self.assertEqual(players[0]["stats"]["GP"], 0)

    def test_regular_season_filter_keeps_cup_games_only(self):
        cutoff = date(2025, 4, 13)
        self.assertTrue(bref.is_regular_season_game("2024-12-03", "NBA Cup", cutoff))
        self.assertFalse(bref.is_regular_season_game("2024-12-17", "NBA Cup", cutoff))
        self.assertFalse(bref.is_regular_season_game("2025-04-19", "Playoffs", cutoff))

    def test_live_pool_seeds_previous_players_and_blank_stat_rookies(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "players.json").write_text(json.dumps({"players": [{"id": "veteran", "name": "Veteran", "team": "BOS", "positions": ["PG"], "stats": {"PTS": 20}}]}), encoding="utf-8")
            (data / "draft-2026.json").write_text(json.dumps({"players": [{"id": "rookie", "name": "Rookie", "team": "BOS", "positions": [], "stats": {}}]}), encoding="utf-8")
            with patch.object(bref, "DATA", data):
                players = bref.seed_live_players([], "2026-27")

        by_id = {player["id"]: player for player in players}
        self.assertEqual(by_id["veteran"]["stats"]["PTS"], 0)
        self.assertEqual(by_id["veteran"]["positions"], ["PG"])
        self.assertEqual(by_id["rookie"]["stats"], {})


if __name__ == "__main__":
    unittest.main()
