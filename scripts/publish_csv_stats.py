#!/usr/bin/env python3
"""Build shared Draft and Data player pools from a complete game-log CSV."""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SEASONS = {"2024-25", "2025-26", "2026-27"}
COUNTING = (
    "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB",
    "REB", "AST", "STL", "BLK", "TOV", "PF", "PTS", "PLUS_MINUS", "MIN",
)
PERCENTAGES = ("FG_PCT", "FT_PCT", "FG3_PCT")
ALIASES = {
    "id": ("PLAYERID", "PERSONID", "ID"),
    "name": ("PLAYERNAME", "PLAYER", "NAME"),
    "team": ("TEAMABBREVIATION", "TEAM", "TEAMCODE"),
    "gameId": ("GAMEID",),
    "date": ("GAMEDATE", "DATE"),
    "matchup": ("MATCHUP", "OPPONENT"),
    "FGM": ("FGM", "FIELDGOALSMADE"),
    "FGA": ("FGA", "FIELDGOALSATTEMPTED"),
    "FG3M": ("FG3M", "3PM", "THREESMADE"),
    "FG3A": ("FG3A", "3PA", "THREESATTEMPTED"),
    "FTM": ("FTM", "FREETHROWSMADE"),
    "FTA": ("FTA", "FREETHROWSATTEMPTED"),
    "OREB": ("OREB", "OFFENSIVEREBOUNDS"),
    "DREB": ("DREB", "DEFENSIVEREBOUNDS"),
    "REB": ("REB", "REBOUNDS"),
    "AST": ("AST", "ASSISTS"),
    "STL": ("STL", "STEALS"),
    "BLK": ("BLK", "BLOCKS"),
    "TOV": ("TOV", "TO", "TURNOVERS"),
    "PF": ("PF", "FOULS"),
    "PTS": ("PTS", "POINTS"),
    "PLUS_MINUS": ("PLUSMINUS", "PLUSMINUSPOINTS"),
    "MIN": ("MIN", "MINUTESPLAYED", "MINPLAYED"),
    "FG_PCT": ("FGPCT", "FG", "FIELDGOALPERCENTAGE"),
    "FT_PCT": ("FTPCT", "FT", "FREETHROWPERCENTAGE"),
    "FG3_PCT": ("FG3PCT", "3PPCT", "3PTFG", "THREEPOINTFGPCT", "THREEPOINTPERCENTAGE"),
    "PER": ("PER", "PLAYEREFFICIENCYRATING"),
}


def header_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.lstrip("\ufeff").strip().upper())


def normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if char.isalnum()).lower()


def parse_date(value: str, row_number: int) -> str:
    raw = value.strip()
    formats = ("%m/%d/%Y", "%b %d, %Y", "%B %d, %Y")
    for date_format in formats:
        try:
            return datetime.strptime(raw.title(), date_format).date().isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError as error:
        raise ValueError(f'Invalid game date "{raw}" on CSV row {row_number}.') from error


def parse_number(value: str, field: str, row_number: int) -> float:
    raw = value.strip()
    if not raw or raw in {"–", "-"}:
        return 0.0
    if field == "MIN" and ":" in raw:
        try:
            minutes, seconds = raw.split(":", 1)
            return float(minutes) + float(seconds) / 60
        except ValueError:
            pass
    try:
        parsed = float(raw.replace(",", "").removesuffix("%"))
    except ValueError as error:
        raise ValueError(f'Invalid number "{raw}" in {field} on CSV row {row_number}.') from error
    if not math.isfinite(parsed):
        raise ValueError(f'Invalid number "{raw}" in {field} on CSV row {row_number}.')
    if raw.endswith("%") or (field in PERCENTAGES and abs(parsed) > 1):
        parsed /= 100
    return parsed


def read_csv_pool(csv_path: Path, season: str) -> dict:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, strict=True)
        try:
            headers = [header_key(value) for value in next(reader)]
        except StopIteration as error:
            raise ValueError("CSV must include a header and at least one game row.") from error
        columns = {
            key: next((headers.index(alias) for alias in aliases if alias in headers), -1)
            for key, aliases in ALIASES.items()
        }
        if columns["name"] < 0 or columns["date"] < 0:
            raise ValueError("CSV needs player name and game date columns (for example PLAYER_NAME and GAME_DATE).")
        if not any(columns[key] >= 0 for key in ("PTS", "FGM", "FGA", "REB", "AST", "MIN")):
            raise ValueError("CSV needs at least one stats column, such as PTS, REB, AST, or MIN.")

        people: dict[str, dict] = {}
        games: set[str] = set()
        lines = 0
        for row_number, cells in enumerate(reader, start=2):
            if not any(cell.strip() for cell in cells):
                continue
            if len(cells) != len(headers):
                raise ValueError(f"CSV row {row_number} has {len(cells)} fields; expected {len(headers)}.")

            def value(key: str) -> str:
                index = columns[key]
                return cells[index].strip() if index >= 0 else ""

            name = value("name")
            if not name:
                raise ValueError(f"Missing player name on CSV row {row_number}.")
            date = parse_date(value("date"), row_number)
            team = value("team").upper()
            supplied_id = value("id")
            identity = supplied_id or normalized_name(name)
            person = people.setdefault(identity, {
                "id": supplied_id or f"csv-{identity}",
                "name": name,
                "team": team or "NBA",
                "gameLogs": [],
                "totals": dict.fromkeys(COUNTING, 0.0),
                "percentageTotals": dict.fromkeys(PERCENTAGES, 0.0),
                "perTotal": 0.0,
                "perCount": 0,
            })
            if team:
                person["team"] = team

            game = {
                "gameId": value("gameId"),
                "date": date,
                "team": team or person["team"],
                "matchup": value("matchup"),
            }
            for field in (*COUNTING, *PERCENTAGES, "PER"):
                index = columns[field]
                raw = cells[index] if index >= 0 else ""
                game[field] = parse_number(raw, field, row_number)
            if not game["FG_PCT"] and game["FGA"]:
                game["FG_PCT"] = game["FGM"] / game["FGA"]
            if not game["FT_PCT"] and game["FTA"]:
                game["FT_PCT"] = game["FTM"] / game["FTA"]
            if not game["FG3_PCT"] and game["FG3A"]:
                game["FG3_PCT"] = game["FG3M"] / game["FG3A"]
            person["gameLogs"].append(game)
            for field in COUNTING:
                person["totals"][field] += game[field]
            for field in PERCENTAGES:
                person["percentageTotals"][field] += game[field]
            if game["PER"]:
                person["perTotal"] += game["PER"]
                person["perCount"] += 1
            games.add(game["gameId"] or f"{date}|{team}|{game['matchup']}|{'' if team or game['matchup'] else row_number}")
            lines += 1

    if not lines:
        raise ValueError("CSV must include at least one game row.")

    players = []
    for person in people.values():
        totals = person["totals"]
        games_played = len(person["gameLogs"])
        stats = {key: round(value / games_played, 3) for key, value in totals.items()}
        stats.update({
            "GP": games_played,
            "PER": round(person["perTotal"] / person["perCount"], 2) if person["perCount"] else 0,
            "FG_PCT": round(totals["FGM"] / totals["FGA"], 4) if totals["FGA"] else round(person["percentageTotals"]["FG_PCT"] / games_played, 4),
            "FT_PCT": round(totals["FTM"] / totals["FTA"], 4) if totals["FTA"] else round(person["percentageTotals"]["FT_PCT"] / games_played, 4),
            "FG3_PCT": round(totals["FG3M"] / totals["FG3A"], 4) if totals["FG3A"] else round(person["percentageTotals"]["FG3_PCT"] / games_played, 4),
        })
        stats["EFF"] = round((
            totals["PTS"] + totals["REB"] + totals["AST"] + totals["STL"] + totals["BLK"]
            - (totals["FGA"] - totals["FGM"]) - (totals["FTA"] - totals["FTM"]) - totals["TOV"]
        ) / games_played, 2)
        players.append({
            "id": person["id"],
            "name": person["name"],
            "team": person["team"],
            "season": season,
            "stats": stats,
            **stats,
            "gameLogs": person["gameLogs"],
        })

    players.sort(key=lambda player: player["name"].casefold())
    synced = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "season": season,
        "lastSyncedAt": synced,
        "source": "CSV upload",
        "playerCount": len(players),
        "playerGameLines": lines,
        "gameCount": len(games),
        "players": players,
    }


def draft_pool_path(data_dir: Path, season: str) -> Path:
    return data_dir / ("players.json" if season == "2025-26" else f"players-{season}.json")


def merge_draft_stats(pool: dict, live_pool: dict) -> tuple[int, int]:
    by_name: dict[str, list[dict]] = {}
    for player in pool.get("players", []):
        by_name.setdefault(normalized_name(player.get("name", "")), []).append(player)

    updated = 0
    unmatched = 0
    for live_player in live_pool["players"]:
        matches = by_name.get(normalized_name(live_player["name"]), [])
        if len(matches) != 1:
            unmatched += 1
            continue
        draft_player = matches[0]
        draft_player["stats"] = live_player["stats"]
        draft_player.update(live_player["stats"])
        draft_player["statsSeason"] = live_pool["season"]
        draft_player["gameLogs"] = live_player["gameLogs"]
        updated += 1
    pool["lastSyncedAt"] = live_pool["lastSyncedAt"]
    pool["statsSource"] = "CSV upload"
    return updated, unmatched


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temp_name = handle.name
            json.dump(payload, handle, separators=(",", ":"), ensure_ascii=False)
            handle.write("\n")
        Path(temp_name).replace(path)
    finally:
        if temp_name and Path(temp_name).exists():
            Path(temp_name).unlink()


def publish_csv(csv_path: Path, season: str, data_dir: Path = DATA, dry_run: bool = False) -> tuple[int, int, int]:
    live_pool = read_csv_pool(csv_path, season)
    draft_path = draft_pool_path(data_dir, season)
    try:
        draft_pool = json.loads(draft_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read Draft pool {draft_path}: {error}") from error
    updated, unmatched = merge_draft_stats(draft_pool, live_pool)
    live_path = data_dir / f"live-players-{season}.json"
    if not dry_run:
        write_json(live_path, live_pool)
        write_json(draft_path, draft_pool)
    return live_pool["playerCount"], updated, unmatched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="Complete per-game CSV file")
    parser.add_argument("--season", required=True, choices=sorted(SEASONS), help="Season represented by the CSV")
    parser.add_argument("--dry-run", action="store_true", help="Validate the CSV and show how many Draft players match without writing files")
    args = parser.parse_args()
    try:
        player_count, updated, unmatched = publish_csv(args.csv_file, args.season, dry_run=args.dry_run)
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))
    action = "Would update" if args.dry_run else "Updated"
    print(f"{action} the {args.season} Data pool ({player_count} players) and Draft pool ({updated} matched players).")
    if unmatched:
        print(f"Note: {unmatched} CSV players did not match exactly one Draft player and were not added to Draft.", file=sys.stderr)
    if not args.dry_run:
        print(f"Review and publish data/live-players-{args.season}.json and {draft_pool_path(DATA, args.season).relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
