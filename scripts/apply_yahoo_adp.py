#!/usr/bin/env python3
"""Sort 2026-27 player pools by the saved Yahoo ADP snapshot."""
from __future__ import annotations

import json
import math
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RANKINGS = DATA / "yahoo-adp-2026-27.json"
POOL_FILES = ("players-2026-27.json", "live-players-2026-27.json")


def normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if char.isalnum()).casefold()


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


def load_adp(path: Path) -> tuple[dict, dict[str, float]]:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read Yahoo ADP snapshot {path}: {error}") from error
    if (
        snapshot.get("season") != "2026-27"
        or not isinstance(snapshot.get("updatedAt"), str)
        or not isinstance(snapshot.get("source"), str)
        or not isinstance(snapshot.get("players"), list)
    ):
        raise ValueError(f"Yahoo ADP snapshot {path} must contain 2026-27 players.")

    adp_by_name = {}
    for player in snapshot["players"]:
        name = str(player.get("name", "")).strip()
        try:
            adp = float(player["adp"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid Yahoo ADP entry for {name or 'unnamed player'}.") from error
        key = normalized_name(name)
        if not key or not math.isfinite(adp) or adp <= 0 or key in adp_by_name:
            raise ValueError(f"Invalid or duplicate Yahoo ADP entry for {name or 'unnamed player'}.")
        adp_by_name[key] = adp
    if not adp_by_name:
        raise ValueError(f"Yahoo ADP snapshot {path} contains no rankings.")
    return snapshot, adp_by_name


def apply_yahoo_adp(data_dir: Path = DATA, rankings_path: Path = RANKINGS) -> dict[str, tuple[int, int]]:
    snapshot, adp_by_name = load_adp(rankings_path)
    results = {}
    for filename in POOL_FILES:
        path = data_dir / filename
        try:
            pool = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Could not read player pool {path}: {error}") from error
        players = pool.get("players")
        if not isinstance(players, list):
            raise ValueError(f"Player pool {path} does not contain a players list.")

        matched = 0
        for player in players:
            adp = adp_by_name.get(normalized_name(str(player.get("name", ""))))
            if adp is None:
                player.pop("yahooAdp", None)
            else:
                player["yahooAdp"] = adp
                matched += 1
        players.sort(key=lambda player: (
            player.get("yahooAdp") is None,
            player.get("yahooAdp", math.inf),
            str(player.get("name", "")).casefold(),
        ))
        pool["yahooAdpUpdatedAt"] = snapshot["updatedAt"]
        pool["yahooAdpSource"] = snapshot["source"]
        write_json(path, pool)
        results[filename] = (matched, len(players) - matched)
    return results

def main() -> None:
    results = apply_yahoo_adp()
    for filename, (matched, unranked) in results.items():
        print(f"Sorted {filename}: {matched} Yahoo ADP matches; {unranked} unranked players follow alphabetically.")


if __name__ == "__main__":
    main()
