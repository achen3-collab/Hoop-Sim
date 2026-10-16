#!/usr/bin/env python3
"""Fetch NBA regular-season player game logs and build local fantasy player pools."""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BASE = "https://stats.nba.com/stats/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
    "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
}
COUNTING = ("FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PTS", "PLUS_MINUS", "MIN")
EXPECTED = {"2024-25": (1230, 26306, 569), "2025-26": (1230, 26627, 582)}


def api(endpoint: str, params: dict, retries: int = 5) -> dict:
    request = Request(BASE + endpoint + "?" + urlencode(params), headers=HEADERS)
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except Exception as error:
            if attempt + 1 == retries:
                raise RuntimeError(f"{endpoint} request failed: {error}") from error
            delay = min(90, 4 * 2**attempt)
            print(f"NBA Stats temporarily unavailable ({error}); retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
    raise RuntimeError(f"No response from {endpoint}")


def rows_from(payload: dict) -> list[dict]:
    result = payload.get("resultSets", payload.get("resultSet"))
    if isinstance(result, list):
        result = result[0]
    if not result:
        return []
    return [dict(zip(result["headers"], row, strict=True)) for row in result["rowSet"]]


def number(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def game_date(value) -> str:
    raw = str(value or "").strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        try:
            return datetime.strptime(raw.title(), "%b %d, %Y").date().isoformat()
        except ValueError:
            return raw[:10] if len(raw) >= 10 else ""


def normalize_positions(value) -> set[str]:
    raw = str(value or "").upper().replace(" ", "")
    positions = set()
    parts = raw.replace("-", "/").split("/")
    for part in parts:
        if part in {"PG", "SG", "G", "GUARD"}:
            positions.add("G")
        elif part in {"SF", "PF", "F", "FORWARD"}:
            positions.add("F")
        elif part == "C":
            positions.add("C")
        elif part in {"CENTER", "C-F", "F-C"}:
            positions.add("C")
    return positions


def fetch_logs(season: str) -> list[dict]:
    payload = api("leaguegamelog", {
        "Counter": "0", "Direction": "DESC", "LeagueID": "00", "PlayerOrTeam": "P",
        "Season": season, "SeasonType": "Regular Season", "Sorter": "DATE",
    })
    return rows_from(payload)


def fetch_player_per(season: str) -> dict[str, float]:
    rows = rows_from(api("leaguedashplayerstats", {
        "College": "", "Conference": "", "Country": "", "DateFrom": "", "DateTo": "",
        "Division": "", "DraftPick": "", "DraftYear": "", "GameScope": "", "GameSegment": "",
        "Height": "", "LastNGames": 0, "LeagueID": "00", "Location": "",
        "MeasureType": "Advanced", "Month": 0, "OpponentTeamID": 0, "Outcome": "",
        "PORound": 0, "PaceAdjust": "N", "PerMode": "PerGame", "Period": 0,
        "PlayerExperience": "", "PlayerPosition": "", "PlusMinus": "N", "Rank": "N",
        "Season": season, "SeasonSegment": "", "SeasonType": "Regular Season",
        "ShotClockRange": "", "StarterBench": "", "TeamID": 0, "TwoWay": "0",
        "VsConference": "", "VsDivision": "", "Weight": "",
    }))
    return {
        str(row["PLAYER_ID"]): number(row.get("PER"))
        for row in rows
        if row.get("PLAYER_ID") is not None and row.get("PER") is not None
    }


def fetch_schedule(season: str) -> list[dict]:
    request = Request(
        "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json",
        headers=HEADERS,
    )
    try:
        with urlopen(request, timeout=30) as response:
            league = json.load(response).get("leagueSchedule", {})
        if not str(league.get("seasonYear", "")).startswith(season[:4]):
            return []
        games = []
        for day in league.get("gameDates", []):
            raw_date = str(day.get("gameDate", ""))
            try:
                game_date = datetime.strptime(raw_date, "%m/%d/%Y %I:%M:%S %p").date().isoformat()
            except ValueError:
                continue
            for game in day.get("games", []):
                if not str(game.get("gameId", "")).startswith("002"):
                    continue
                teams = [game.get(side, {}).get("teamTricode") for side in ("homeTeam", "awayTeam")]
                games.append({"date": game_date, "teams": [value for value in teams if value]})
        return games
    except Exception as error:
        print(f"Schedule unavailable for {season}: {error}", file=sys.stderr)
        return []


def fetch_positions(season: str, logs: list[dict]) -> dict[int, set[str]]:
    teams = {int(row["TEAM_ID"]) for row in logs if row.get("TEAM_ID")}
    positions: dict[int, set[str]] = {}
    for index, team_id in enumerate(sorted(teams), start=1):
        try:
            roster = rows_from(api("commonteamroster", {"LeagueID": "00", "Season": season, "TeamID": team_id}))
            for row in roster:
                if row.get("PLAYER_ID") and row.get("POSITION"):
                    positions.setdefault(int(row["PLAYER_ID"]), set()).update(normalize_positions(row["POSITION"]))
        except RuntimeError as error:
            print(f"Could not load positions for team {team_id}: {error}", file=sys.stderr)
        if index < len(teams):
            time.sleep(float(os.getenv("NBA_API_DELAY", "1.5")))
    print(f"Loaded position info from {len(teams)} NBA team rosters.")
    return positions


def build_pool(
    season: str,
    logs: list[dict],
    synced: str,
    positions: dict[int, set[str]],
    player_per: dict[str, float] | None = None,
) -> dict:
    player_per = player_per or {}
    people: dict[int, dict] = {}
    for row in logs:
        pid = int(row["PLAYER_ID"])
        person = people.setdefault(pid, {"id": pid, "name": row["PLAYER_NAME"], "team": row.get("TEAM_ABBREVIATION", "FA"), "gameLogs": [], "totals": {key: 0.0 for key in COUNTING}})
        game = {
            "gameId": row.get("GAME_ID"),
            "date": game_date(row.get("GAME_DATE")),
            "team": row.get("TEAM_ABBREVIATION", ""),
            "matchup": row.get("MATCHUP", ""),
        }
        for key in COUNTING + ("FG_PCT", "FT_PCT", "FG3_PCT"):
            game[key] = number(row.get(key))
        person["gameLogs"].append(game)
        for key in COUNTING:
            person["totals"][key] += number(row.get(key))

    result = []
    for pid, person in people.items():
        totals, games = person.pop("totals"), person["gameLogs"]
        gp = len(games)
        if not gp:
            continue
        averages = {key: round(totals[key] / gp, 3) for key in COUNTING}
        averages.update({
            "GP": gp,
            "PER": round(player_per.get(str(pid), 0), 2),
            "FG_PCT": round(totals["FGM"] / totals["FGA"], 4) if totals["FGA"] else 0,
            "FT_PCT": round(totals["FTM"] / totals["FTA"], 4) if totals["FTA"] else 0,
            "FG3_PCT": round(totals["FG3M"] / totals["FG3A"], 4) if totals["FG3A"] else 0,
            "EFF": round((totals["PTS"] + totals["REB"] + totals["AST"] + totals["STL"] + totals["BLK"] - (totals["FGA"] - totals["FGM"]) - (totals["FTA"] - totals["FTM"]) - totals["TOV"]) / gp, 2),
        })
        person.update({
            "positions": sorted(positions.get(pid, set())),
            "season": season, "stats": averages, **averages,
        })
        result.append(person)
    result.sort(key=lambda player: player["name"])
    game_count = len({row.get("GAME_ID") for row in logs})
    expected = EXPECTED.get(season)
    matches_expected = not expected or (game_count, len(logs), len(result)) == expected
    return {"season": season, "defaultSeason": "2025-26", "lastSyncedAt": synced, "source": "NBA Stats API · LeagueGameLog", "playerCount": len(result), "playerGameLines": len(logs), "gameCount": game_count, "matchesExpected": matches_expected, "expected": {"gameCount": expected[0], "playerGameLines": expected[1], "playerCount": expected[2]} if expected else None, "players": result}


def import_live_season(season: str) -> dict:
    print(f"Fetching {season} completed player game logs…")
    logs = fetch_logs(season)
    player_per = fetch_player_per(season)
    synced = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pool = build_pool(season, logs, synced, {}, player_per)
    DATA.mkdir(parents=True, exist_ok=True)
    output = DATA / f"live-players-{season}.json"
    output.write_text(json.dumps(pool, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {output.name}: {pool['gameCount']:,} games, {len(logs):,} player-game lines.")
    return pool


def import_season(season: str) -> tuple[int, int]:
    print(f"Fetching {season} regular-season player game logs…")
    logs = fetch_logs(season)
    positions = fetch_positions(season, logs)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / f"positions-{season}.json").write_text(json.dumps({str(key): sorted(value) for key, value in positions.items()}), encoding="utf-8")
    schedule = fetch_schedule(season)
    schedule_payload = {"season": season, "lastSyncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "games": schedule}
    (DATA / f"schedule-{season}.json").write_text(json.dumps(schedule_payload, separators=(",", ":")), encoding="utf-8")
    print(f"{season}: saved {len(schedule):,} regular-season schedule games.")
    synced = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (DATA / "game_logs").mkdir(parents=True, exist_ok=True)
    with (DATA / "game_logs" / f"{season}.jsonl").open("w", encoding="utf-8") as handle:
        for row in logs:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    pool = build_pool(season, logs, synced, positions)
    out = DATA / ("players.json" if season == "2025-26" else f"players-{season}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pool, separators=(",", ":")), encoding="utf-8")
    with (DATA / "sync_history.jsonl").open("a", encoding="utf-8") as history:
        history.write(json.dumps({"season": season, "syncedAt": synced, "gameCount": pool["gameCount"], "playerGameLines": len(logs), "playerCount": len(pool["players"]), "matchesExpected": pool["matchesExpected"]}, separators=(",", ":")) + "\n")
    print(f"{season}: {pool['gameCount']:,} games, {len(logs):,} player-game lines, {len(pool['players']):,} players")
    if not pool["matchesExpected"]:
        expected = pool["expected"]
        print(f"WARNING: expected {expected['gameCount']:,} games, {expected['playerGameLines']:,} lines, {expected['playerCount']:,} players; import totals differ.", file=sys.stderr)
    print(f"Wrote {out.relative_to(ROOT)} and data/game_logs/{season}.jsonl (sync {synced})")
    return pool["gameCount"], len(logs)


def import_draft_class(year: int) -> None:
    try:
        rows = rows_from(api("commondrafthistory", {"LeagueID": "00", "SeasonYear": str(year)}))
        try:
            position_map = json.loads((DATA / "positions-2026-27.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            position_map = {}
        rookies = [{"id": row.get("PERSON_ID"), "name": row.get("PLAYER_NAME"), "team": row.get("TEAM_ABBREVIATION", "Rookie"), "positions": position_map.get(str(row.get("PERSON_ID")), []), "season": f"{year}-{str(year + 1)[-2:]}", "GP": 0, "EFF": 0, "stats": {}} for row in rows if row.get("PERSON_ID")]
        result = {"year": year, "lastSyncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": "NBA Stats API · CommonDraftHistory", "players": rookies}
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / f"draft-{year}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        pool_path = DATA / "players-2026-27.json"
        if pool_path.exists():
            pool = json.loads(pool_path.read_text(encoding="utf-8"))
            existing = {str(person["id"]) for person in pool.get("players", [])}
            pool["players"].extend(person for person in rookies if str(person["id"]) not in existing)
            pool["players"].sort(key=lambda person: person["name"])
            pool["playerCount"] = len(pool["players"])
            pool_path.write_text(json.dumps(pool, separators=(",", ":")), encoding="utf-8")
        print(f"Draft class {year}: saved {len(rookies)} rookies with blank stats.")
    except RuntimeError as error:
        print(f"Draft history unavailable: {error}. Writing empty draft list.", file=sys.stderr)
        (DATA / f"draft-{year}.json").write_text(json.dumps({"year": year, "players": [], "note": "NBA Stats draft endpoint unavailable; retry importer."}, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", action="append", help="Season such as 2025-26; repeat for multiple seasons.")
    parser.add_argument("--draft-year", type=int, default=2026)
    parser.add_argument("--skip-draft", action="store_true")
    parser.add_argument("--watch", action="store_true", help="Repeat the selected season import on an interval.")
    parser.add_argument("--interval", type=int, default=3600, help="Watch interval in seconds (default: 3600).")
    parser.add_argument("--draft-only", action="store_true", help="Fetch only the NBA draft class metadata.")
    parser.add_argument("--live-only", action="store_true", help="Update the separate completed-game log pool.")
    args = parser.parse_args()
    seasons = args.season or ["2024-25", "2025-26", "2026-27"]
    if args.draft_only:
        import_draft_class(args.draft_year)
        return
    if args.live_only:
        if len(seasons) != 1:
            parser.error("--live-only requires exactly one --season")
        import_live_season(seasons[0])
        return
    if args.watch and len(seasons) != 1:
        parser.error("--watch requires exactly one --season")
    if args.watch:
        if not args.skip_draft:
            import_draft_class(args.draft_year)
        try:
            while True:
                try:
                    import_season(seasons[0])
                except RuntimeError as error:
                    print(f"Live import failed: {error}", file=sys.stderr)
                time.sleep(max(60, args.interval))
        except KeyboardInterrupt:
            print("Live sync stopped.")
    else:
        for i, season in enumerate(seasons):
            import_season(season)
            if i + 1 < len(seasons):
                time.sleep(float(os.getenv("NBA_API_DELAY", "1.5")))
        if not args.skip_draft:
            import_draft_class(args.draft_year)


if __name__ == "__main__":
    main()
