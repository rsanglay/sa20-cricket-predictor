"""Train regression models to predict player batting runs and bowling wickets."""
from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "data" / "models"

RUNS_MODEL_PATH = MODELS_DIR / "player_runs_regressor.pkl"
RUNS_FEATURES_PATH = MODELS_DIR / "player_runs_features.json"
WICKETS_MODEL_PATH = MODELS_DIR / "player_wickets_regressor.pkl"
WICKETS_FEATURES_PATH = MODELS_DIR / "player_wickets_features.json"
PLAYER_FEATURE_SNAPSHOT = PROCESSED_DIR / "player_feature_snapshot.csv"

RUN_FEATURES = [
    "matches_played",
    "career_avg_runs",
    "career_strike_rate",
    "recent_avg_runs",
    "recent_strike_rate",
    "recent_runs_variance",
]

WICKET_FEATURES = [
    "matches_bowled",
    "career_avg_wickets",
    "career_economy",
    "recent_avg_wickets",
    "recent_economy",
    "recent_wickets_variance",
]

@dataclass
class BattingHistory:
    runs: List[float]
    balls: List[float]

@dataclass
class BowlingHistory:
    wickets: List[float]
    runs_conceded: List[float]
    deliveries: List[float]


def load_deliveries() -> pd.DataFrame:
    deliveries_path = PROCESSED_DIR / "cricsheet_deliveries.csv"
    if not deliveries_path.exists():
        raise FileNotFoundError("cricsheet_deliveries.csv not found. Run ingestion first.")
    deliveries = pd.read_csv(deliveries_path)
    return deliveries


def load_match_dates() -> pd.DataFrame:
    scorecards_path = PROCESSED_DIR / "match_scorecards.csv"
    if not scorecards_path.exists():
        raise FileNotFoundError("match_scorecards.csv not found. Run build_aggregates first.")
    scorecards = pd.read_csv(scorecards_path)
    match_dates = scorecards[["competition", "season", "match_id", "match_date"]].drop_duplicates()
    match_dates["match_date"] = pd.to_datetime(match_dates["match_date"], errors="coerce")
    return match_dates


def build_batting_dataset(deliveries: pd.DataFrame, match_dates: pd.DataFrame) -> tuple[pd.DataFrame, Dict[str, BattingHistory]]:
    batting = (
        deliveries.groupby(["competition", "season", "match_id", "batter"], as_index=False)
        .agg(runs=("runs_batter", "sum"), balls=("runs_batter", "count"))
        .rename(columns={"batter": "player_name"})
    )
    batting = batting.merge(match_dates, on=["competition", "season", "match_id"], how="left")
    batting = batting.dropna(subset=["match_date"]).sort_values("match_date")

    records = []
    history: Dict[str, BattingHistory] = defaultdict(lambda: BattingHistory(runs=[], balls=[]))

    for row in batting.to_dict("records"):
        player = row["player_name"]
        hist = history[player]
        if hist.runs:
            feature_row = make_batting_features(hist)
            feature_row.update(
                {
                    "competition": row["competition"],
                    "season": row["season"],
                    "match_id": row["match_id"],
                    "match_date": row["match_date"],
                    "player_name": player,
                    "target_runs": row["runs"],
                }
            )
            records.append(feature_row)
        update_batting_history(hist, row["runs"], row["balls"])

    dataset = pd.DataFrame(records)
    return dataset, history


def build_bowling_dataset(deliveries: pd.DataFrame, match_dates: pd.DataFrame) -> tuple[pd.DataFrame, Dict[str, BowlingHistory]]:
    bowling = (
        deliveries.groupby(["competition", "season", "match_id", "bowler"], as_index=False)
        .agg(wickets=("wicket", "sum"), runs_conceded=("runs_total", "sum"), deliveries_bowled=("runs_total", "count"))
        .rename(columns={"bowler": "player_name"})
    )
    bowling = bowling.merge(match_dates, on=["competition", "season", "match_id"], how="left")
    bowling = bowling.dropna(subset=["match_date"]).sort_values("match_date")

    records = []
    history: Dict[str, BowlingHistory] = defaultdict(lambda: BowlingHistory(wickets=[], runs_conceded=[], deliveries=[]))

    for row in bowling.to_dict("records"):
        player = row["player_name"]
        hist = history[player]
        if hist.wickets:
            feature_row = make_bowling_features(hist)
            feature_row.update(
                {
                    "competition": row["competition"],
                    "season": row["season"],
                    "match_id": row["match_id"],
                    "match_date": row["match_date"],
                    "player_name": player,
                    "target_wickets": row["wickets"],
                }
            )
            records.append(feature_row)
        update_bowling_history(hist, row["wickets"], row["runs_conceded"], row["deliveries_bowled"])

    dataset = pd.DataFrame(records)
    return dataset, history


def make_batting_features(hist: BattingHistory) -> Dict[str, float]:
    runs = np.array(hist.runs)
    balls = np.array(hist.balls)
    matches_played = len(runs)
    career_avg_runs = runs.mean()
    career_strike_rate = (runs.sum() / balls.sum()) * 100 if balls.sum() > 0 else 0.0
    recent_runs = runs[-3:] if matches_played >= 3 else runs
    recent_balls = balls[-3:] if matches_played >= 3 else balls
    recent_avg_runs = recent_runs.mean() if recent_runs.size else 0.0
    recent_strike_rate = (recent_runs.sum() / recent_balls.sum()) * 100 if recent_balls.sum() > 0 else 0.0
    recent_variance = float(np.var(recent_runs)) if recent_runs.size else 0.0
    return {
        "matches_played": float(matches_played),
        "career_avg_runs": float(career_avg_runs),
        "career_strike_rate": float(career_strike_rate),
        "recent_avg_runs": float(recent_avg_runs),
        "recent_strike_rate": float(recent_strike_rate),
        "recent_runs_variance": recent_variance,
    }


def update_batting_history(hist: BattingHistory, runs: float, balls: float) -> None:
    hist.runs.append(runs)
    hist.balls.append(balls)


def make_bowling_features(hist: BowlingHistory) -> Dict[str, float]:
    wickets = np.array(hist.wickets)
    runs_conceded = np.array(hist.runs_conceded)
    deliveries = np.array(hist.deliveries)
    matches = len(wickets)
    career_avg_wickets = wickets.mean()
    career_economy = (runs_conceded.sum() / deliveries.sum()) * 6 if deliveries.sum() > 0 else 0.0
    recent_wickets = wickets[-3:] if matches >= 3 else wickets
    recent_runs = runs_conceded[-3:] if matches >= 3 else runs_conceded
    recent_deliveries = deliveries[-3:] if matches >= 3 else deliveries
    recent_avg_wickets = recent_wickets.mean() if recent_wickets.size else 0.0
    recent_economy = (recent_runs.sum() / recent_deliveries.sum()) * 6 if recent_deliveries.sum() > 0 else 0.0
    recent_variance = float(np.var(recent_wickets)) if recent_wickets.size else 0.0
    return {
        "matches_bowled": float(matches),
        "career_avg_wickets": float(career_avg_wickets),
        "career_economy": float(career_economy),
        "recent_avg_wickets": float(recent_avg_wickets),
        "recent_economy": float(recent_economy),
        "recent_wickets_variance": recent_variance,
    }


def update_bowling_history(hist: BowlingHistory, wickets: float, runs_conceded: float, deliveries: float) -> None:
    hist.wickets.append(wickets)
    hist.runs_conceded.append(runs_conceded)
    hist.deliveries.append(deliveries)


def train_regressor(features: pd.DataFrame, targets: pd.Series) -> GradientBoostingRegressor:
    model = GradientBoostingRegressor(
        n_estimators=400,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.8,
        random_state=42,
    )
    model.fit(features, targets)
    return model


def evaluate_regressor(model: GradientBoostingRegressor, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
    preds = model.predict(X)
    return {
        "rmse": float(np.sqrt(mean_squared_error(y, preds))),
        "mae": float(mean_absolute_error(y, preds)),
        "r2": float(r2_score(y, preds)) if len(y.unique()) > 1 else float("nan"),
    }


def chronological_split(df: pd.DataFrame, test_ratio: float = 0.2, date_col: str = "match_date") -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values(date_col)
    split_idx = int(len(df) * (1 - test_ratio))
    split_idx = max(min(split_idx, len(df) - 1), 1)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    return train_df, test_df


def save_artifacts(model: GradientBoostingRegressor, feature_names: List[str], model_path: Path, features_path: Path) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dump(model, model_path)
    with features_path.open("w", encoding="utf-8") as fh:
        json.dump({"feature_names": feature_names}, fh, indent=2)


def build_player_snapshot(
    batting_history: Dict[str, BattingHistory],
    bowling_history: Dict[str, BowlingHistory],
) -> pd.DataFrame:
    rows = []
    all_players = set(batting_history.keys()) | set(bowling_history.keys())
    for player in all_players:
        batting = batting_history.get(player)
        bowling = bowling_history.get(player)
        batting_feats = make_batting_features(batting) if batting and batting.runs else {key: 0.0 for key in RUN_FEATURES}
        bowling_feats = make_bowling_features(bowling) if bowling and bowling.wickets else {key: 0.0 for key in WICKET_FEATURES}
        rows.append(
            {
                "player_name": player,
                **batting_feats,
                **bowling_feats,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    deliveries = load_deliveries()
    match_dates = load_match_dates()

    batting_dataset, batting_history = build_batting_dataset(deliveries, match_dates)
    bowling_dataset, bowling_history = build_bowling_dataset(deliveries, match_dates)

    if batting_dataset.empty:
        raise RuntimeError("No batting records available for training")
    if bowling_dataset.empty:
        raise RuntimeError("No bowling records available for training")

    bat_train, bat_test = chronological_split(batting_dataset)
    bowl_train, bowl_test = chronological_split(bowling_dataset)

    runs_model = train_regressor(bat_train[RUN_FEATURES], bat_train["target_runs"])
    wickets_model = train_regressor(bowl_train[WICKET_FEATURES], bowl_train["target_wickets"])

    runs_metrics = evaluate_regressor(runs_model, bat_test[RUN_FEATURES], bat_test["target_runs"])
    wickets_metrics = evaluate_regressor(wickets_model, bowl_test[WICKET_FEATURES], bowl_test["target_wickets"])

    print("Runs model metrics:", runs_metrics)
    print("Wickets model metrics:", wickets_metrics)

    save_artifacts(runs_model, RUN_FEATURES, RUNS_MODEL_PATH, RUNS_FEATURES_PATH)
    save_artifacts(wickets_model, WICKET_FEATURES, WICKETS_MODEL_PATH, WICKETS_FEATURES_PATH)

    snapshot = build_player_snapshot(batting_history, bowling_history)
    snapshot.to_csv(PLAYER_FEATURE_SNAPSHOT, index=False)
    print("Saved player feature snapshot to", PLAYER_FEATURE_SNAPSHOT)


if __name__ == "__main__":
    main()
