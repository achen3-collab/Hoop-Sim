# Hoop Sim

A local-first NBA fantasy basketball draft room and nine-category weekly matchup simulator.

## Run it

Requires Python 3.10+; the app server and importer use only the Python standard library.

```bash
python3 server.py
```

Open http://localhost:8000. The default stat season is 2025–26. Drafts, lineups, team names, and roster sizes are saved in browser local storage.

## Publish on GitHub Pages

The `Deploy to GitHub Pages` workflow publishes the static site and its JSON data whenever a commit is pushed to `main`. In the repository's **Settings → Pages**, set the build and deployment source to **GitHub Actions**. After the workflow completes, GitHub Pages will show the public site URL in the Pages settings and in the workflow run.

GitHub Pages serves only static files: the **Catch up now** and **Update live stats** actions need the Python server and are not available on Pages. To publish refreshed data, update the JSON files in `data/` and push the changes to `main`. CSV uploads and browser-saved drafts and lineups remain local to each visitor's browser. All published files, including player and schedule data, are publicly accessible.

### Publish CSV stats to both Draft and Data

To publish a complete per-game CSV as shared stats, use a local copy of this repository with Python 3.10 or later. The CSV must have one row per player per game and include player name, game date, and at least one supported stat column. NBA Stats LeagueGameLog CSV headers are supported.

First preview the update, replacing the path and season with your own:

```bash
python3 scripts/publish_csv_stats.py /path/to/game-logs.csv --season 2026-27 --dry-run
```

If the preview is correct, run the command again without `--dry-run`. It writes `data/live-players-<season>.json` for the Data tab and updates the matching `data/players[-<season>].json` Draft pool for players whose names match unambiguously. Unmatched players stay in the Data pool but are not added to Draft, because their roster and position details cannot be inferred safely. The CSV must contain the complete game log for the season; it replaces the published Data pool for that season.

Review the changed JSON files, then commit and push them to `main`. GitHub Actions will redeploy the site, and the shared Draft and Data stats will update for visitors. These JSON files are public. The website's **Upload CSV** button remains a browser-only upload and does not publish files.

## Publish on PythonAnywhere

The site can run as a public, read-only WSGI app. Create a PythonAnywhere web app using Python 3.10 or later, upload the project to `/home/<username>/Hoop-Sim`, and configure its WSGI file to import the project entry point:

```python
import sys

project = "/home/<username>/Hoop-Sim"
if project not in sys.path:
    sys.path.insert(0, project)

from wsgi import application
```

Replace `<username>` with the PythonAnywhere account name, then reload the web app. Do not add static-file mappings; `wsgi.py` serves the site assets and JSON data itself. The WSGI app intentionally disables the public sync endpoints so visitors cannot trigger imports that write to the server or consume its resources. To refresh hosted stats, run the importer as a private PythonAnywhere scheduled task, for example:

```bash
python /home/<username>/Hoop-Sim/scripts/import_nba_data.py --season 2026-27 --live-only
```

Use an interval allowed by the account plan. The browser reads the updated JSON files on its next refresh. Deploy updated player pools and schedules by uploading the new files from `data/`. Keep the PythonAnywhere account private; never publish credentials in the repository.

## Import NBA data

```bash
python3 scripts/import_basketball_reference.py
```

The importer uses Basketball-Reference's per-game tables for 2024–25, 2025–26, and 2026–27, its 2026 draft table, and the NBA schedule when available. Season aggregates and positions are fetched from one BRef page per season. The default full import also fetches each player's game log with a 3.2-second minimum delay; responses cache per player and can take about an hour across the two completed seasons. To import aggregates quickly, use `--skip-game-logs`. To import game logs for just one season, use `--season 2025-26 --game-logs`.

The importer writes raw player-game rows to `data/game_logs/<season>.jsonl`, per-player log caches to `data/bref_game_logs/`, aggregates to `data/players[-<season>].json`, schedules to `data/schedule-<season>.json`, current team assignments to `data/rosters-<season>.json` (cached for 24 hours), rookies to `data/draft-2026.json`, and every sync timestamp/count to `data/sync_history.jsonl`. The 2025–26 pool is `data/players.json`; the 2026–27 pool includes returning players, current roster-only players, and blank-stat rookies before current-season stats arrive. EFF is `(PTS + REB + AST + STL + BLK - missed FG - missed FT - TO) / GP`.

Use the in-app **Catch up now** action to refresh the selected season's BRef aggregates. To keep 2026–27 updating hourly in a local terminal, run:

```bash
python3 scripts/import_basketball_reference.py --season 2026-27 --skip-game-logs --skip-draft --watch --interval 3600
```

Use `--draft-only` to retry draft metadata without refetching season stats.

Basketball-Reference may rate-limit or change its HTML. The importer spaces requests, caches player logs, reports imported counts, and timestamps every sync. With `--game-logs`, it checks completed seasons against 1,230 games, 26,306 / 26,627 player-game lines, and 569 / 582 players. The per-game-only mode does not claim those player-game-line totals.

## Live player data

Open the **Data** tab and choose **Update live stats** to fetch completed NBA player game logs for the selected season. The tracker shows season averages and every completed box score, newest first. It uses the NBA Stats LeagueGameLog feed and stores its results separately in `data/live-players-<season>.json`, so live updates do not replace the draft-room season pools. The page reloads the saved live data every five minutes; click the update button after games finish to fetch the latest box scores.

Use **Upload CSV** to import your own per-game box scores, including on static hosting where the sync API is unavailable. The CSV needs one row per player per game, a player-name column (`PLAYER_NAME` or `NAME`), a date column (`GAME_DATE` or `DATE`), and at least one stat column such as `PTS`, `REB`, `AST`, or `MIN`. NBA Stats LeagueGameLog CSV headers are supported; player ID, team, matchup, shooting attempts/makes, percentages, and PER are optional. The import calculates season averages and weighted shooting percentages from game rows. It replaces the uploaded CSV data for that season in this browser; upload the complete set of game rows when replacing it. Choose **Use synced data** to remove the browser's CSV override and return to the hosted JSON pool. CSV imports are saved only in that browser and do not update the site's files for other visitors.

The Data tab also includes a 2026–27 roster pool made from the active team rosters plus the 2026 draft class, including drafted players not yet listed on a team roster. It shows per-game minutes, shooting percentages, points, rebounds, assists, steals, blocks, turnovers, and NBA Player Efficiency Rating (PER). PER is a rating, not a percentage; stats remain blank until a player has appeared in a game. The live importer fetches PER from NBA advanced player stats.

## Fantasy model

Roster formats are 13–15 players: PG, SG, G, SF, PF, F, C, C, Util, Util, BN, BN, BN, with extra roster spots added to the bench. Player labels normalize PG/SG to G and SF/PF to F; G players can fill PG, SG, or G slots, and F players can fill SF, PF, or F slots. Up to 20 editable teams are supported. Slot-aware drag and drop enforces NBA position eligibility. My team saves daily lineup assignments. Matchups compare Monday–Sunday projections and exclude bench players. Percentages are weighted by attempts; turnovers are inverse-scored. When game rows for a selected week are unavailable, the simulator uses an estimate of 3.5 games per starter.

The My Team view shows roster games Monday through Sunday for the week containing the selected lineup date. **Auto-set lineup** prioritizes rostered players with a scheduled game that day and assigns players to eligible non-bench slots; the active starter count excludes bench slots.

In Matchups, the independent **My team auto-set** and **Opponent auto-set** switches generate eligible, game-aware starting lineups for each day of the selected week. When a switch is off, projections use that team's saved daily or default lineup; generated assumptions are retained separately and never overwrite actual lineups. The sidebar shows day-to-day lineup changes and, while auto-set is on, each generated lineup's difference from the saved lineup.

Projections are derived from NBA season averages, not Yahoo's proprietary projections. Access to Yahoo's official fantasy pool/projections requires a separately configured Yahoo OAuth application and is not included. The draft endpoint may not publish future draft information immediately; rookies retain blank stat lines until NBA game data exists.