#!/usr/bin/env python3
"""Import Basketball-Reference per-game tables and optional player game logs."""
from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from import_nba_data import EXPECTED, normalize_positions

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE = "https://www.basketball-reference.com"
AGENT = "HoopSim local importer (Basketball-Reference season stats)"
REQUEST_DELAY = 3.2
LAST_REQUEST = 0.0
STAT_MAP = {
    "GP": "games", "MIN": "mp_per_g", "FGM": "fg_per_g", "FGA": "fga_per_g",
    "FG_PCT": "fg_pct", "FG3M": "fg3_per_g", "FG3A": "fg3a_per_g", "FG3_PCT": "fg3_pct",
    "FTM": "ft_per_g", "FTA": "fta_per_g", "FT_PCT": "ft_pct", "OREB": "orb_per_g",
    "DREB": "drb_per_g", "REB": "trb_per_g", "AST": "ast_per_g", "STL": "stl_per_g",
    "BLK": "blk_per_g", "TOV": "tov_per_g", "PF": "pf_per_g", "PTS": "pts_per_g",
}
LOG_MAP = {
    "FGM": "fg", "FGA": "fga", "FG_PCT": "fg_pct", "FG3M": "fg3", "FG3A": "fg3a",
    "FG3_PCT": "fg3_pct", "FTM": "ft", "FTA": "fta", "FT_PCT": "ft_pct", "OREB": "orb",
    "DREB": "drb", "REB": "trb", "AST": "ast", "STL": "stl", "BLK": "blk", "TOV": "tov",
    "PF": "pf", "PTS": "pts", "PLUS_MINUS": "plus_minus",
}


class TableParser(HTMLParser):
    def __init__(self, table_id: str):
        super().__init__(convert_charrefs=True)
        self.table_id = table_id
        self.in_table = False
        self.row = None
        self.stat = None
        self.cell = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and attrs.get("id") == self.table_id:
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.row = {}
        elif self.in_table and self.row is not None and tag in {"th", "td"}:
            self.stat = attrs.get("data-stat")
            self.cell = []
        elif self.in_table and self.row is not None and tag == "a" and self.stat:
            href = attrs.get("href", "")
            self.row[f"__href_{self.stat}"] = href
            if self.stat in {"player", "name_display"}:
                self.row["__href"] = href

    def handle_data(self, data):
        if self.in_table and self.stat:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if not self.in_table:
            return
        if tag in {"th", "td"} and self.stat:
            self.row[self.stat] = " ".join(" ".join(self.cell).split())
            self.stat = None
            self.cell = []
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            self.in_table = False


class CommentTableParser(HTMLParser):
    def __init__(self, table_id: str):
        super().__init__(convert_charrefs=True)
        self.table_id = table_id
        self.rows = []

    def handle_comment(self, data):
        if f'id="{self.table_id}"' not in data and f"id='{self.table_id}'" not in data:
            return
        parser = TableParser(self.table_id)
        parser.feed(data)
        self.rows = parser.rows


class ScheduleMonthLinks(HTMLParser):
    def __init__(self, season_end: int):
        super().__init__(convert_charrefs=True)
        self.prefix = f"/leagues/NBA_{season_end}_games-"
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        if href.startswith(self.prefix) and href.endswith(".html"):
            self.links.add(href)


def parse_table(page: str, table_id: str) -> list[dict]:
    parser = TableParser(table_id)
    parser.feed(page)
    if parser.rows:
        return parser.rows
    comments = CommentTableParser(table_id)
    comments.feed(page)
    return comments.rows


def is_regular_season_game(game_date: str, remarks: str, regular_season_end: date) -> bool:
    if not game_date or date.fromisoformat(game_date) > regular_season_end:
        return False
    note = remarks.strip().lower()
    if "playoff" in note or "play-in" in note or "play in" in note:
        return False
    cup_final = note == "nba cup" and game_date[5:7] == "12" and int(game_date[8:]) >= 15
    return not cup_final


def fetch_schedule(season: str) -> list[dict]:
    end_year = int(season[:4]) + 1
    april_first = date(end_year, 4, 1)
    first_sunday = april_first + timedelta(days=(6 - april_first.weekday()) % 7)
    regular_season_end = first_sunday + timedelta(days=7)
    base_url = f"{SITE}/leagues/NBA_{end_year}_games.html"
    try:
        page = request_html(base_url)
    except RuntimeError as error:
        print(f"Basketball-Reference schedule unavailable for {season}: {error}", file=sys.stderr)
        return []
    month_links = ScheduleMonthLinks(end_year)
    month_links.feed(page)
    pages = sorted(month_links.links) or [f"/leagues/NBA_{end_year}_games.html"]
    games = {}
    for path in pages:
        html = page if path.endswith("_games.html") else request_html(urljoin(SITE, path))
        for row in parse_table(html, "schedule"):
            game_date = parse_date(row.get("date_game", ""))
            remarks = row.get("game_remarks", "").strip().lower()
            visitor_href = row.get("__href_visitor_team_name", "")
            home_href = row.get("__href_home_team_name", "")
            visitor = visitor_href.split("/")[-2] if visitor_href else ""
            home = home_href.split("/")[-2] if home_href else ""
            if not is_regular_season_game(game_date, remarks, regular_season_end) or not visitor or not home:
                continue
            key = (game_date, *sorted((visitor, home)))
            games[key] = {"date": game_date, "teams": [visitor, home]}
    return sorted(games.values(), key=lambda game: (game["date"], game["teams"]))


def season_schedule(season: str) -> list[dict]:
    path = DATA / f"schedule-{season}.json"
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        synced = datetime.fromisoformat(cached.get("lastSyncedAt", "").replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - synced).total_seconds()
        if cached.get("source") == "Basketball-Reference" and cached.get("scheduleVersion") == 4 and age < 86400:
            return cached.get("games", [])
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    games = fetch_schedule(season)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    DATA.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"season": season, "lastSyncedAt": now, "source": "Basketball-Reference", "scheduleVersion": 4, "games": games}, separators=(",", ":")), encoding="utf-8")
    return games


def fetch_roster_map(season: str, schedule: list[dict]) -> dict[str, dict]:
    end_year = int(season[:4]) + 1
    teams = sorted({team for game in schedule for team in game.get("teams", [])})
    roster_map = {}
    for index, team in enumerate(teams, start=1):
        url = f"{SITE}/teams/{team}/{end_year}.html"
        try:
            rows = parse_table(request_html(url), "roster")
            for row in rows:
                slug = slug_from_href(row.get("__href_player", ""))
                if not slug or not row.get("player") or row["player"] == "Player":
                    continue
                name = row.get("player", "").removesuffix(" (TW)").strip()
                roster_map[slug] = {"name": name, "team": team, "positions": sorted(normalize_positions(row.get("pos", "")))}
        except RuntimeError as error:
            print(f"Could not load {team} roster for {season}: {error}", file=sys.stderr)
        if index < len(teams):
            time.sleep(REQUEST_DELAY)
        if index % 10 == 0:
            print(f"Loaded current rosters for {index}/{len(teams)} teams…")
    return roster_map


def current_roster_map(season: str, schedule: list[dict]) -> dict[str, dict]:
    path = DATA / f"rosters-{season}.json"
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
        synced = datetime.fromisoformat(cache.get("lastSyncedAt", "").replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - synced).total_seconds()
        if cache.get("source") == "Basketball-Reference" and cache.get("version") == 2 and age < 86400:
            return cache.get("players", {})
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    roster_map = fetch_roster_map(season, schedule)
    if roster_map:
        DATA.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"season": season, "source": "Basketball-Reference", "version": 2, "lastSyncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "players": roster_map}, separators=(",", ":")), encoding="utf-8")
    return roster_map


def apply_roster_map(players: list[dict], roster_map: dict[str, dict]) -> None:
    people = {str(person["id"]): person for person in players}
    for slug, roster in roster_map.items():
        person = people.get(slug)
        if person is None:
            stats = {key: 0 for key in STAT_MAP}
            stats["EFF"] = 0
            person = {"id": slug, "name": roster.get("name") or slug, "team": roster["team"], "teams": [roster["team"]], "rosterSeason": "2026-27", "positions": roster.get("positions", []), "season": "2026-27", "stats": stats, **stats, "gameLogs": []}
            players.append(person)
            people[slug] = person
            continue
        person["team"] = roster["team"]
        person["teams"] = [roster["team"]]
        person["rosterSeason"] = "2026-27"
        if roster.get("positions"):
            person["positions"] = roster["positions"]


def number(value) -> float:
    try:
        return float(str(value or "").replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def parse_date(value: str) -> str:
    value = value.strip()
    for pattern in ("%Y-%m-%d", "%b %d, %Y", "%a, %b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ""


def parse_minutes(value: str) -> float:
    value = value.strip()
    if ":" in value:
        try:
            minutes, seconds = value.split(":", 1)
            return round(float(minutes) + float(seconds) / 60, 3)
        except ValueError:
            return 0.0
    return number(value)


def request_html(url: str, retries: int = 4) -> str:
    global LAST_REQUEST
    for attempt in range(retries):
        wait = REQUEST_DELAY - (time.monotonic() - LAST_REQUEST)
        if wait > 0:
            time.sleep(wait)
        request = Request(url, headers={"User-Agent": AGENT, "Accept": "text/html"})
        try:
            with urlopen(request, timeout=45) as response:
                LAST_REQUEST = time.monotonic()
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as error:
            LAST_REQUEST = time.monotonic()
            if error.code in {403, 404}:
                raise RuntimeError(f"Basketball-Reference returned HTTP {error.code} for {url}") from error
            if attempt + 1 == retries:
                raise RuntimeError(f"Basketball-Reference request failed: {error}") from error
            time.sleep(min(60, 5 * 2**attempt))
        except Exception as error:
            LAST_REQUEST = time.monotonic()
            if attempt + 1 == retries:
                raise RuntimeError(f"Basketball-Reference request failed: {error}") from error
            delay = min(60, 5 * 2**attempt)
            print(f"Request failed ({error}); retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
    raise RuntimeError(f"No response from {url}")


def slug_from_href(href: str) -> str:
    return Path(urlsplit(href).path).stem


def fetch_player_rows(season: str) -> list[dict]:
    end_year = int(season[:4]) + 1
    url = f"{SITE}/leagues/NBA_{end_year}_per_game.html"
    page = request_html(url)
    rows = parse_table(page, "per_game_stats")
    players = {}
    for row in rows:
        href = row.get("__href", "")
        slug = slug_from_href(href)
        name = row.get("name_display", "").strip()
        if not slug or not name or name.lower() in {"league average", "player"}:
            continue
        previous = players.get(slug)
        team_codes = set(previous.get("__teams", [])) if previous else set()
        team_code = row.get("team_name_abbr", "")
        if team_code and team_code not in {"TOT", "2TM", "3TM", "4TM"}:
            team_codes.add(team_code)
        if previous is None or number(row.get("games")) > number(previous.get("games")):
            row["__slug"] = slug
            row["__teams"] = sorted(team_codes)
            players[slug] = row
        elif team_codes:
            previous["__teams"] = sorted(team_codes)
    if not players and season != "2026-27":
        raise RuntimeError(f"No player rows found in Basketball-Reference table {url}")
    return list(players.values())


def fetch_player_logs(row: dict, season: str) -> list[dict]:
    end_year = int(season[:4]) + 1
    href = row.get("__href", "")
    player_path = urlsplit(href).path.removesuffix(".html")
    url = urljoin(SITE, f"{player_path}/gamelog/{end_year}/")
    raw_rows = parse_table(request_html(url), "player_game_log_reg")
    player_logs = []
    for game in raw_rows:
        game_date = parse_date(game.get("date", ""))
        minutes = parse_minutes(game.get("mp", ""))
        if not game_date or minutes <= 0:
            continue
        team = game.get("team_name_abbr", "")
        opponent = game.get("opp_name_abbr", "")
        pair = ":".join(sorted((team, opponent)))
        log = {"gameId": f"{game_date}:{pair}", "date": game_date, "team": team, "opponent": opponent, "MIN": minutes}
        for key, source in LOG_MAP.items():
            log[key] = number(game.get(source, ""))
        player_logs.append(log)
    return player_logs


def season_player(row: dict, season: str, logs: list[dict] | None = None) -> dict:
    stats = {key: number(row.get(source, "")) for key, source in STAT_MAP.items()}
    stats["GP"] = int(stats.get("GP", 0))
    stats["EFF"] = round(stats.get("PTS", 0) + stats.get("REB", 0) + stats.get("AST", 0) + stats.get("STL", 0) + stats.get("BLK", 0) - (stats.get("FGA", 0) - stats.get("FGM", 0)) - (stats.get("FTA", 0) - stats.get("FTM", 0)) - stats.get("TOV", 0), 2)
    team = row.get("team_name_abbr", "FA")
    if logs:
        team = logs[-1].get("team") or team
    return {
        "id": row["__slug"], "name": row.get("name_display", "").strip(), "team": team,
        "teams": row.get("__teams", []),
        "positions": sorted(normalize_positions(row.get("pos", ""))), "season": season,
        "stats": stats, **stats, "gameLogs": logs or [],
    }


def seed_live_players(players: list[dict], season: str) -> list[dict]:
    if season != "2026-27":
        return sorted(players, key=lambda person: person["name"])
    seeded = {}
    for pool_path in (DATA / "players.json", DATA / "players-2024-25.json"):
        try:
            previous = json.loads(pool_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for old in previous.get("players", []):
            stats = {key: 0 for key in STAT_MAP}
            stats["EFF"] = 0
            seeded[str(old["id"])] = {
                "id": old["id"], "name": old["name"], "team": old.get("team", "FA"),
                "teams": old.get("teams", []),
                "positions": old.get("positions", []), "season": season,
                "stats": stats, **stats, "gameLogs": [],
            }
    for person in players:
        seeded[str(person["id"])] = person
    try:
        draft = json.loads((DATA / "draft-2026.json").read_text(encoding="utf-8"))
        for person in draft.get("players", []):
            seeded.setdefault(str(person["id"]), person)
    except (OSError, json.JSONDecodeError):
        pass
    return sorted(seeded.values(), key=lambda person: person["name"])


def import_season(season: str, include_logs: bool = False, delay: float = REQUEST_DELAY) -> dict:
    global REQUEST_DELAY
    REQUEST_DELAY = max(3.1, delay)
    print(f"Fetching Basketball-Reference {season} per-game stats…")
    try:
        rows = fetch_player_rows(season)
    except RuntimeError as error:
        if season != "2026-27" or "HTTP 404" not in str(error):
            raise
        print("The 2026–27 player table is not published yet; writing an empty live pool.")
        rows = []
    log_dir = DATA / "bref_game_logs" / season
    players = []
    raw_logs = []
    for index, row in enumerate(rows, start=1):
        logs = []
        cache = log_dir / f"{row['__slug']}.jsonl"
        if include_logs:
            if cache.exists():
                logs = [json.loads(line) for line in cache.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                logs = fetch_player_logs(row, season)
                log_dir.mkdir(parents=True, exist_ok=True)
                cache.write_text("".join(json.dumps(game, separators=(",", ":")) + "\n" for game in logs), encoding="utf-8")
            for game in logs:
                raw_logs.append({"PLAYER_ID": row["__slug"], "PLAYER_NAME": row.get("name_display", ""), "TEAM_ABBREVIATION": game["team"], "GAME_ID": game["gameId"], "GAME_DATE": game["date"], **game})
            if index % 25 == 0:
                print(f"Fetched game logs for {index}/{len(rows)} players…")
        players.append(season_player(row, season, logs))
    if include_logs:
        (DATA / "game_logs").mkdir(parents=True, exist_ok=True)
        (DATA / "game_logs" / f"{season}.jsonl").write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in raw_logs), encoding="utf-8")
    schedule = season_schedule(season)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    DATA.mkdir(parents=True, exist_ok=True)
    players = seed_live_players(players, season)
    if season == "2026-27":
        apply_roster_map(players, current_roster_map(season, schedule))
    unique_games = {log["gameId"] for player in players for log in player["gameLogs"]}
    game_count = len(unique_games) or len(schedule) or None
    line_count = len(raw_logs) if include_logs else None
    expected = EXPECTED.get(season)
    matches = (game_count, line_count, len(players)) == expected if expected and line_count is not None else None
    pool = {
        "season": season, "defaultSeason": "2025-26", "lastSyncedAt": now,
        "source": "Basketball-Reference · Per Game", "playerCount": len(players),
        "playerGameLines": line_count, "gameCount": game_count, "matchesExpected": matches,
        "expected": {"gameCount": expected[0], "playerGameLines": expected[1], "playerCount": expected[2]} if expected else None,
        "players": players,
    }
    output = DATA / ("players.json" if season == "2025-26" else f"players-{season}.json")
    output.write_text(json.dumps(pool, separators=(",", ":")), encoding="utf-8")
    with (DATA / "sync_history.jsonl").open("a", encoding="utf-8") as history:
        history.write(json.dumps({"source": "Basketball-Reference", "season": season, "syncedAt": now, "gameCount": game_count, "playerGameLines": line_count, "playerCount": len(players), "matchesExpected": matches}, separators=(",", ":")) + "\n")
    game_count_label = f"{game_count:,} games" if game_count is not None else "game count unavailable"
    print(f"{season}: {len(players):,} players, {game_count_label}" + (f", {line_count:,} player-game lines" if line_count is not None else ", player-game logs not requested"))
    if expected and line_count is not None and not matches:
        print(f"Expected {expected[0]:,} games / {expected[1]:,} player lines / {expected[2]:,} players; inspect import totals.", file=sys.stderr)
    print(f"Wrote {output.relative_to(ROOT)}; synced {now}.")
    return pool


def import_draft_class(year: int) -> None:
    page = request_html(f"{SITE}/draft/NBA_{year}.html")
    rows = parse_table(page, "stats")
    rookies = []
    for row in rows:
        name = row.get("player", row.get("name_display", "")).strip()
        slug = slug_from_href(row.get("__href", ""))
        if not name or not slug:
            continue
        rookies.append({"id": slug, "name": name, "team": row.get("team_id", "Rookie"), "positions": [], "season": f"{year}-{str(year + 1)[-2:]}", "GP": 0, "EFF": 0, "stats": {}, "gameLogs": []})
    result = {"year": year, "lastSyncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": "Basketball-Reference · Draft History", "players": rookies}
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / f"draft-{year}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    pool_path = DATA / "players-2026-27.json"
    if year == 2026 and pool_path.exists():
        pool = json.loads(pool_path.read_text(encoding="utf-8"))
        existing = {str(person["id"]) for person in pool.get("players", [])}
        pool["players"].extend(person for person in rookies if str(person["id"]) not in existing)
        pool["players"].sort(key=lambda person: person["name"])
        pool["playerCount"] = len(pool["players"])
        pool_path.write_text(json.dumps(pool, separators=(",", ":")), encoding="utf-8")
    print(f"Draft class {year}: {len(rookies)} players with blank stats.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", action="append", help="Season such as 2025-26; repeat to import multiple.")
    parser.add_argument("--game-logs", action="store_true", help="Fetch each player's game log (polite 3.2s delay; slow, cacheable).")
    parser.add_argument("--skip-game-logs", action="store_true", help="Import only the full-season per-game table.")
    parser.add_argument("--draft-year", type=int, default=2026)
    parser.add_argument("--skip-draft", action="store_true")
    parser.add_argument("--draft-only", action="store_true")
    parser.add_argument("--watch", action="store_true", help="Repeat one season's aggregate import on an interval.")
    parser.add_argument("--interval", type=int, default=3600)
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY)
    args = parser.parse_args()
    if args.draft_only:
        import_draft_class(args.draft_year)
        return
    seasons = args.season or ["2024-25", "2025-26", "2026-27"]
    if args.watch and (len(seasons) != 1 or args.game_logs):
        parser.error("--watch requires one --season and cannot be combined with --game-logs")
    include_logs = args.game_logs or (args.season is None and not args.skip_game_logs and not args.watch)
    if args.watch:
        try:
            while True:
                try:
                    import_season(seasons[0], include_logs=False, delay=args.delay)
                except RuntimeError as error:
                    print(f"Live import failed: {error}", file=sys.stderr)
                time.sleep(max(300, args.interval))
        except KeyboardInterrupt:
            print("Live Basketball-Reference sync stopped.")
        return
    for index, season in enumerate(seasons):
        import_season(season, include_logs=include_logs, delay=args.delay)
        if index + 1 < len(seasons):
            time.sleep(max(REQUEST_DELAY, args.delay))
    if not args.skip_draft:
        import_draft_class(args.draft_year)


if __name__ == "__main__":
    main()
