"""General-purpose Cricsheet ingestion utility."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

from data_pipeline.scrapers.cricsheet_api import CricsheetAPI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "cricsheet"
PROCESSED_DIR = DATA_DIR / "processed"


@dataclass(frozen=True)
class CompetitionConfig:
    mode: str  # "competition" or "team_slugs"
    sources: List[str]


DEFAULT_COMPETITIONS: Dict[str, CompetitionConfig] = {
    "sa20": CompetitionConfig(
        mode="team_slugs",
        sources=[
            "mi_cape_town",
            "paarl_royals",
            "pretoria_capitals",
            "durban%27s_super_giants",
            "joburg_super_kings",
            "sunrisers_eastern_cape",
        ],
    ),
    "ipl": CompetitionConfig(mode="competition", sources=["ipl"]),
    "bbl": CompetitionConfig(mode="competition", sources=["bbl"]),
    "it20s": CompetitionConfig(mode="competition", sources=["it20s_male"]),
}


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def ingest_competitions(
    competitions: Iterable[str],
    overwrite: bool = False,
) -> Dict[str, pd.DataFrame]:
    """Download, extract, and parse deliveries for the requested competitions."""
    ensure_dirs()
    api = CricsheetAPI()

    deliveries_frames: List[pd.DataFrame] = []
    roster_records: List[Dict] = []
    player_tracker: Dict[str, Dict] = {}
    processed_matches: set[tuple[str, str]] = set()

    for key in competitions:
        config = DEFAULT_COMPETITIONS.get(key)
        if config is None:
            raise ValueError(f"Unknown competition '{key}'. Configure it in DEFAULT_COMPETITIONS.")

        print(f"=== Processing {key} ({config.mode}) ===")
        for source in config.sources:
            match_files = download_and_extract(api, key, source, config.mode, overwrite)
            print(f"  • {source}: {len(match_files)} files")
            for path in match_files:
                match_key = (key, path.stem)
                if match_key in processed_matches:
                    continue
                deliveries, roster, player_meta = parse_match(path, api, key, source)
                if not deliveries.empty:
                    deliveries_frames.append(deliveries)
                roster_records.extend(roster)
                update_player_tracker(player_tracker, player_meta)
                processed_matches.add(match_key)

    if not deliveries_frames:
        print("No deliveries parsed.")
        return {}

    deliveries_df = pd.concat(deliveries_frames, ignore_index=True)
    roster_df = pd.DataFrame(roster_records).drop_duplicates()
    players_df = build_players_df(player_tracker)

    write_outputs(deliveries_df, roster_df, players_df)
    return {
        "deliveries": deliveries_df,
        "rosters": roster_df,
        "players": players_df,
    }


def download_and_extract(
    api: CricsheetAPI,
    competition_key: str,
    source: str,
    mode: str,
    overwrite: bool,
) -> List[Path]:
    safe_source = source.replace("%", "")
    if mode == "competition":
        zip_path = RAW_DIR / competition_key / f"{safe_source}_json.zip"
        extract_dir = RAW_DIR / competition_key
    else:
        zip_path = RAW_DIR / competition_key / f"{safe_source}_json.zip"
        extract_dir = RAW_DIR / competition_key / safe_source

    extract_dir.mkdir(parents=True, exist_ok=True)
    print(f"    - downloading {source} -> {zip_path.name}")
    api.download_competition_zip(source, zip_path, force=overwrite)

    print(f"    - extracting to {extract_dir}")
    return api.extract_zip(zip_path, extract_dir, overwrite=overwrite)


def parse_match(
    path: Path,
    api: CricsheetAPI,
    competition: str,
    source: str,
) -> tuple[pd.DataFrame, List[Dict], Dict[str, Dict]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    deliveries = api.parse_match_json(data)
    if deliveries.empty:
        return deliveries, [], {}

    info = data.get("info", {})
    match_id = info.get("registry", {}).get("fixtures", {}).get("match", path.stem)
    if match_id is None:
        match_id = path.stem
    season = info.get("season")
    dates = info.get("dates", [])
    match_date = None
    if dates:
        try:
            match_date = datetime.fromisoformat(dates[0])
        except ValueError:
            match_date = None

    deliveries["match_id"] = match_id
    deliveries["season"] = season
    deliveries["competition"] = competition
    deliveries["source_slug"] = source
    if match_date:
        deliveries["match_date"] = match_date.date().isoformat()

    roster_records = build_roster_records(info, competition, season, match_id, match_date)
    player_meta = build_player_meta(roster_records, match_date)

    return deliveries, roster_records, player_meta


def build_roster_records(
    info: Dict,
    competition: str,
    season: str | None,
    match_id: str,
    match_date: datetime | None,
) -> List[Dict]:
    records: List[Dict] = []
    players_by_team = info.get("players", {})
    registry = info.get("registry", {}).get("people", {})

    for team_name, players in players_by_team.items():
        for player in players:
            player_id = registry.get(player)
            records.append(
                {
                    "competition": competition,
                    "season": season,
                    "match_id": match_id,
                    "team_name": team_name,
                    "player_name": player,
                    "player_id": player_id,
                    "match_date": match_date.date().isoformat() if match_date else None,
                }
            )
    return records


def build_player_meta(roster_records: List[Dict], match_date: datetime | None) -> Dict[str, Dict]:
    meta: Dict[str, Dict] = {}
    for record in roster_records:
        key = record.get("player_id") or record["player_name"]
        if key not in meta:
            meta[key] = {
                "player_id": record.get("player_id"),
                "player_name": record["player_name"],
                "first_seen": record.get("match_date"),
                "last_seen": record.get("match_date"),
                "competitions": {record["competition"]},
            }
        else:
            if record.get("match_date"):
                existing_first = meta[key]["first_seen"]
                existing_last = meta[key]["last_seen"]
                date_value = record["match_date"]
                if existing_first is None or (date_value and date_value < existing_first):
                    meta[key]["first_seen"] = date_value
                if existing_last is None or (date_value and date_value > existing_last):
                    meta[key]["last_seen"] = date_value
            meta[key]["competitions"].add(record["competition"])
    return meta


def update_player_tracker(tracker: Dict[str, Dict], player_meta: Dict[str, Dict]) -> None:
    for key, meta in player_meta.items():
        if key not in tracker:
            tracker[key] = meta
        else:
            if meta.get("first_seen"):
                existing_first = tracker[key].get("first_seen")
                if existing_first is None or meta["first_seen"] < existing_first:
                    tracker[key]["first_seen"] = meta["first_seen"]
            if meta.get("last_seen"):
                existing_last = tracker[key].get("last_seen")
                if existing_last is None or meta["last_seen"] > existing_last:
                    tracker[key]["last_seen"] = meta["last_seen"]
            tracker[key]["competitions"].update(meta.get("competitions", set()))


def build_players_df(player_tracker: Dict[str, Dict]) -> pd.DataFrame:
    records: List[Dict] = []
    for meta in player_tracker.values():
        competitions = sorted(meta.get("competitions", []))
        records.append(
            {
                "player_id": meta.get("player_id"),
                "player_name": meta.get("player_name"),
                "first_seen": meta.get("first_seen"),
                "last_seen": meta.get("last_seen"),
                "competitions": ",".join(competitions),
            }
        )
    return pd.DataFrame(records)


def write_outputs(deliveries: pd.DataFrame, rosters: pd.DataFrame, players: pd.DataFrame) -> None:
    combined_path = PROCESSED_DIR / "cricsheet_deliveries.csv"
    print(f"Writing combined deliveries -> {combined_path}")
    deliveries.to_csv(combined_path, index=False)

    roster_path = PROCESSED_DIR / "cricsheet_team_rosters.csv"
    print(f"Writing team rosters -> {roster_path}")
    rosters.to_csv(roster_path, index=False)

    players_path = PROCESSED_DIR / "cricsheet_players.csv"
    print(f"Writing player master -> {players_path}")
    players.to_csv(players_path, index=False)

    for competition, frame in deliveries.groupby("competition"):
        output = PROCESSED_DIR / f"{competition}_deliveries.csv"
        print(f"Writing {competition} deliveries -> {output}")
        frame.to_csv(output, index=False)

    for competition, frame in rosters.groupby("competition"):
        output = PROCESSED_DIR / f"{competition}_team_rosters.csv"
        print(f"Writing {competition} rosters -> {output}")
        frame.to_csv(output, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Cricsheet competitions")
    parser.add_argument(
        "--competitions",
        default="sa20",
        help="Comma-separated list of competition keys (default: sa20)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Force re-download and re-extract archives",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    comps = [c.strip() for c in args.competitions.split(",") if c.strip()]
    ingest_competitions(comps, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
