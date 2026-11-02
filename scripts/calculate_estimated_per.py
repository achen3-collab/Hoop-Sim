#!/usr/bin/env python3
"""Calculate a league-normalized EFF-per-minute estimate for player pools."""
from __future__ import annotations

import json
import math
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SEASON_POOLS = {
    "2024-25": ("players-2024-25.json",),
    "2025-26": ("players.json",),
    "2026-27": ("players-2026-27.json", "live-players-2026-27.json"),
}
STAT_FIELDS = ("PTS", "REB", "AST", "STL", "BLK", "FGM", "FGA", "FTM", "FTA", "TOV")
METHOD = "15 × player EFF per minute ÷ league-average EFF per minute. EFF = PTS + REB + AST + STL + BLK − missed FGs − missed FTs − TOV. This is an estimate, not Hollinger PER."


def normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if char.isalnum()).casefold()


def numeric_stat(player: dict, key: str) -> float | None:
    stats = player.get("stats")
    value = stats.get(key) if isinstance(stats, dict) and key in stats else player.get(key)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def impact_per_game(player: dict) -> tuple[float, float, float] | None:
    gp = numeric_stat(player, "GP")
    minutes = numeric_stat(player, "MIN")
    values = {key: numeric_stat(player, key) for key in STAT_FIELDS}
    if gp is None or minutes is None or gp <= 0 or minutes <= 0 or any(value is None for value in values.values()):
        return None
    stats = {key: value for key, value in values.items() if value is not None}
    impact = (
        stats["PTS"] + stats["REB"] + stats["AST"] + stats["STL"] + stats["BLK"]
        - (stats["FGA"] - stats["FGM"]) - (stats["FTA"] - stats["FTM"]) - stats["TOV"]
    )
    return impact, minutes, gp


def write_json(path: Path, payload: dict) -> None:
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


def load_pool(path: Path) -> dict:
    try:
        pool = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read player pool {path}: {error}") from error
    if not isinstance(pool, dict) or not isinstance(pool.get("players"), list):
        raise ValueError(f"Player pool {path} does not contain a players list.")
    return pool


def league_average(players: list[dict]) -> float:
    total_impact = 0.0
    total_minutes = 0.0
    for player in players:
        impact = impact_per_game(player)
        if impact is None:
            continue
        per_game_impact, minutes, games = impact
        total_impact += per_game_impact * games
        total_minutes += minutes * games
    if total_minutes <= 0 or total_impact <= 0:
        raise ValueError("Cannot calculate estimated PER without positive league minutes and box-score impact.")
    return total_impact / total_minutes


def apply_estimated_per(
    data_dir: Path = DATA,
    season_pools: dict[str, tuple[str, ...]] = SEASON_POOLS,
) -> dict[str, int]:
    loaded = {
        filename: load_pool(data_dir / filename)
        for filenames in season_pools.values()
        for filename in filenames
    }
    results = {}
    for season, filenames in season_pools.items():
        reference_by_name = {}
        for filename in filenames:
            for player in loaded[filename]["players"]:
                name = normalized_name(str(player.get("name", "")))
                if name:
                    reference_by_name.setdefault(name, player)
        average_impact = league_average(list(reference_by_name.values()))
        for filename in filenames:
            pool = loaded[filename]
            calculated = 0
            for player in pool["players"]:
                impact = impact_per_game(player)
                estimate = None
                if impact is not None:
                    per_game_impact, minutes, _ = impact
                    estimate = round(15 * (per_game_impact / minutes) / average_impact, 2)
                    calculated += 1
                stats = player.get("stats")
                if not isinstance(stats, dict):
                    stats = {}
                    player["stats"] = stats
                stats["estimatedPER"] = estimate
                player["estimatedPER"] = estimate
            pool["estimatedPERMethod"] = METHOD
            pool["estimatedPERLeagueAverageImpactPerMinute"] = round(average_impact, 8)
            write_json(data_dir / filename, pool)
            results[filename] = calculated
    return results


def main() -> None:
    results = apply_estimated_per()
    for filename, calculated in results.items():
        print(f"Calculated estimated PER for {calculated} players in {filename}.")


if __name__ == "__main__":
    main()
