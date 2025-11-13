"""Build aggregated datasets for players, teams, and matches."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def read_deliveries(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Deliveries file not found: {path}")
    deliveries = pd.read_csv(path)
    numeric_cols = ["runs_batter", "runs_extras", "runs_total", "wicket"]
    for col in numeric_cols:
        if col in deliveries.columns:
            deliveries[col] = deliveries[col].fillna(0).astype(float)
    deliveries["over"] = deliveries["over"].fillna(0).astype(int)
    return deliveries


def read_rosters(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Roster file not found: {path}")
    rosters = pd.read_csv(path)
    return rosters


def build_match_scorecards(deliveries: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        deliveries.groupby([
            "competition",
            "season",
            "match_id",
            "innings_team",
        ])
        .agg(
            runs_scored=("runs_total", "sum"),
            wickets_lost=("wicket", "sum"),
            deliveries_faced=("runs_total", "count"),
            match_date=("match_date", "first"),
        )
        .reset_index()
    )
    grouped["overs_float"] = grouped["deliveries_faced"].apply(deliveries_to_overs)

    winners = determine_winners(grouped)
    grouped = grouped.merge(winners, on=["competition", "season", "match_id"], how="left")
    return grouped


def deliveries_to_overs(deliveries: float) -> float:
    deliveries = int(deliveries)
    whole_overs, balls = divmod(deliveries, 6)
    return whole_overs + balls / 10


def determine_winners(scorecards: pd.DataFrame) -> pd.DataFrame:
    def winner_for_match(df: pd.DataFrame) -> pd.Series:
        if df.empty:
            return pd.Series({"winning_team": None, "winning_margin_runs": np.nan})
        df = df.sort_values("runs_scored", ascending=False)
        top = df.iloc[0]
        if len(df) == 1:
            margin = top["runs_scored"]
        else:
            margin = top["runs_scored"] - df.iloc[1]["runs_scored"]
        return pd.Series({"winning_team": top["innings_team"], "winning_margin_runs": margin})

    winners = scorecards.groupby(
        ["competition", "season", "match_id"]
    ).apply(
        winner_for_match,
        include_groups=False,
    ).reset_index()
    return winners


def build_team_aggregates(scorecards: pd.DataFrame) -> pd.DataFrame:
    team_stats = (
        scorecards.groupby(["competition", "season", "innings_team"])
        .agg(
            matches_played=("match_id", "nunique"),
            total_runs=("runs_scored", "sum"),
            total_wickets=("wickets_lost", "sum"),
            total_overs=("overs_float", "sum"),
        )
        .reset_index()
        .rename(columns={"innings_team": "team_name"})
    )

    wins = scorecards[scorecards["innings_team"] == scorecards["winning_team"]]
    wins = wins.groupby(["competition", "season", "innings_team"]).agg(wins=("match_id", "nunique"))
    team_stats = team_stats.merge(
        wins,
        left_on=["competition", "season", "team_name"],
        right_index=True,
        how="left",
    )
    team_stats["wins"] = team_stats["wins"].fillna(0).astype(int)
    team_stats["win_percentage"] = team_stats["wins"] / team_stats["matches_played"].clip(lower=1)
    team_stats["run_rate"] = team_stats["total_runs"] / team_stats["total_overs"].replace(0, np.nan)
    return team_stats


def build_player_aggregates(deliveries: pd.DataFrame, rosters: pd.DataFrame) -> pd.DataFrame:
    roster_lookup = rosters[[
        "competition",
        "season",
        "match_id",
        "player_name",
        "player_id",
        "team_name",
    ]].drop_duplicates()

    batting = (
        deliveries.groupby([
            "competition",
            "season",
            "match_id",
            "innings_team",
            "batter",
        ])
        .agg(
            runs=("runs_batter", "sum"),
            balls=("runs_batter", "count"),
            boundaries_4=("runs_batter", lambda x: np.sum(x == 4)),
            boundaries_6=("runs_batter", lambda x: np.sum(x == 6)),
        )
        .reset_index()
        .rename(columns={"batter": "player_name", "innings_team": "team_name"})
    )

    bowling = (
        deliveries.groupby([
            "competition",
            "season",
            "match_id",
            "bowler",
        ])
        .agg(
            wickets=("wicket", "sum"),
            runs_conceded=("runs_total", "sum"),
            deliveries_bowled=("runs_total", "count"),
        )
        .reset_index()
        .rename(columns={"bowler": "player_name"})
    )

    batting = batting.merge(
        roster_lookup,
        on=["competition", "season", "match_id", "player_name", "team_name"],
        how="left",
    )

    bowling = bowling.merge(
        roster_lookup,
        on=["competition", "season", "match_id", "player_name"],
        how="left",
    )

    grouped_batting = (
        batting.groupby(["competition", "season", "player_id", "player_name", "team_name"]).agg(
            matches_batted=("match_id", "nunique"),
            innings=("match_id", "count"),
            runs=("runs", "sum"),
            balls=("balls", "sum"),
            fours=("boundaries_4", "sum"),
            sixes=("boundaries_6", "sum"),
        )
    ).reset_index()

    grouped_bowling = (
        bowling.groupby(["competition", "season", "player_id", "player_name", "team_name"]).agg(
            matches_bowled=("match_id", "nunique"),
            wickets=("wickets", "sum"),
            runs_conceded=("runs_conceded", "sum"),
            deliveries=("deliveries_bowled", "sum"),
        )
    ).reset_index()

    player_stats = pd.merge(
        grouped_batting,
        grouped_bowling,
        on=["competition", "season", "player_id", "player_name", "team_name"],
        how="outer",
        suffixes=("_bat", "_bowl"),
    ).fillna(0)

    player_stats["strike_rate"] = player_stats.apply(
        lambda row: (row["runs"] / row["balls"]) * 100 if row["balls"] > 0 else 0,
        axis=1,
    )
    player_stats["economy_rate"] = player_stats.apply(
        lambda row: (row["runs_conceded"] / row["deliveries"]) * 6 if row["deliveries"] > 0 else 0,
        axis=1,
    )

    player_stats["matches_played"] = player_stats[["matches_batted", "matches_bowled"]].max(axis=1)
    return player_stats


def write_output_frames(frames: Dict[str, pd.DataFrame]) -> None:
    for name, df in frames.items():
        output_path = PROCESSED_DIR / name
        print(f"Writing {name} -> {output_path}")
        df.to_csv(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build aggregated cricket datasets")
    parser.add_argument(
        "--deliveries",
        default=str(PROCESSED_DIR / "cricsheet_deliveries.csv"),
        help="Path to combined deliveries CSV",
    )
    parser.add_argument(
        "--rosters",
        default=str(PROCESSED_DIR / "cricsheet_team_rosters.csv"),
        help="Path to team roster CSV",
    )
    args = parser.parse_args()

    deliveries = read_deliveries(Path(args.deliveries))
    rosters = read_rosters(Path(args.rosters))

    scorecards = build_match_scorecards(deliveries)
    team_stats = build_team_aggregates(scorecards)
    player_stats = build_player_aggregates(deliveries, rosters)

    write_output_frames(
        {
            "match_scorecards.csv": scorecards,
            "team_season_stats.csv": team_stats,
            "player_season_stats.csv": player_stats,
        }
    )


if __name__ == "__main__":
    main()
