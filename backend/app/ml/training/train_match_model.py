"""Train an XGBoost classifier for match outcome prediction."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from joblib import dump

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "data" / "models"

FEATURE_FILE = MODELS_DIR / "match_predictor_features.json"
MODEL_FILE = MODELS_DIR / "match_predictor.pkl"
TEAM_FEATURE_SNAPSHOT = PROCESSED_DIR / "team_feature_snapshot.csv"


def normalise_team_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


@dataclass
class TeamHistory:
    matches: int = 0
    wins: int = 0
    runs_for: float = 0.0
    overs_for: float = 0.0
    runs_against: float = 0.0
    overs_against: float = 0.0

    def record_match(self, runs_for: float, overs_for: float, won: bool, runs_against: float, overs_against: float) -> None:
        self.matches += 1
        if won:
            self.wins += 1
        self.runs_for += runs_for
        self.overs_for += overs_for
        self.runs_against += runs_against
        self.overs_against += overs_against

    def features(self) -> dict[str, float]:
        win_pct = self.wins / self.matches if self.matches else 0.0
        run_rate = self.runs_for / self.overs_for if self.overs_for else 0.0
        conceded_rate = self.runs_against / self.overs_against if self.overs_against else 0.0
        net_run_rate = run_rate - conceded_rate
        avg_runs_for = self.runs_for / self.matches if self.matches else 0.0
        avg_runs_against = self.runs_against / self.matches if self.matches else 0.0
        return {
            "matches_played": float(self.matches),
            "win_pct": float(win_pct),
            "run_rate": float(run_rate),
            "net_run_rate": float(net_run_rate),
            "avg_runs_for": float(avg_runs_for),
            "avg_runs_against": float(avg_runs_against),
        }


FEATURE_NAMES = [
    "team_win_pct",
    "opp_win_pct",
    "delta_win_pct",
    "team_run_rate",
    "opp_run_rate",
    "delta_run_rate",
    "team_net_run_rate",
    "opp_net_run_rate",
    "delta_net_run_rate",
    "team_avg_runs_for",
    "opp_avg_runs_for",
    "delta_avg_runs_for",
    "team_avg_runs_against",
    "opp_avg_runs_against",
    "delta_avg_runs_against",
    "team_matches",
    "opp_matches",
    "delta_matches",
]


def load_scorecards(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "match_date" in df.columns:
        df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")
    else:
        df["match_date"] = pd.NaT
    return df.sort_values("match_date")


def build_training_dataset(scorecards: pd.DataFrame) -> tuple[pd.DataFrame, dict[tuple[str, str], TeamHistory]]:
    dataset_rows: list[dict[str, float]] = []
    team_history: dict[tuple[str, str], TeamHistory] = defaultdict(TeamHistory)

    for _, group in scorecards.groupby(["competition", "season", "match_id", "match_date"], sort=False):
        if len(group) != 2:
            continue

        rows = group.sort_values("innings_team").to_dict("records")
        team_a = rows[0]
        team_b = rows[1]

        comp = team_a["competition"]
        key_a = (comp, team_a["innings_team"])
        key_b = (comp, team_b["innings_team"])
        history_a = team_history[key_a]
        history_b = team_history[key_b]

        if history_a.matches == 0 and history_b.matches == 0:
            update_team_history(history_a, history_b, team_a, team_b)
            continue

        feats_a = history_a.features()
        feats_b = history_b.features()
        record = {
            "competition": comp,
            "season": team_a.get("season"),
            "match_id": team_a.get("match_id"),
            "match_date": team_a.get("match_date"),
            "team_name": team_a.get("innings_team"),
            "opp_name": team_b.get("innings_team"),
            "label": 1 if team_a.get("winning_team") == team_a.get("innings_team") else 0,
        }
        record.update(feature_vector_from_histories(feats_a, feats_b))
        dataset_rows.append(record)

        update_team_history(history_a, history_b, team_a, team_b)

    dataset = pd.DataFrame(dataset_rows)
    return dataset, team_history


def feature_vector_from_histories(team: dict[str, float], opp: dict[str, float]) -> dict[str, float]:
    return {
        "team_win_pct": team["win_pct"],
        "opp_win_pct": opp["win_pct"],
        "delta_win_pct": team["win_pct"] - opp["win_pct"],
        "team_run_rate": team["run_rate"],
        "opp_run_rate": opp["run_rate"],
        "delta_run_rate": team["run_rate"] - opp["run_rate"],
        "team_net_run_rate": team["net_run_rate"],
        "opp_net_run_rate": opp["net_run_rate"],
        "delta_net_run_rate": team["net_run_rate"] - opp["net_run_rate"],
        "team_avg_runs_for": team["avg_runs_for"],
        "opp_avg_runs_for": opp["avg_runs_for"],
        "delta_avg_runs_for": team["avg_runs_for"] - opp["avg_runs_for"],
        "team_avg_runs_against": team["avg_runs_against"],
        "opp_avg_runs_against": opp["avg_runs_against"],
        "delta_avg_runs_against": team["avg_runs_against"] - opp["avg_runs_against"],
        "team_matches": team["matches_played"],
        "opp_matches": opp["matches_played"],
        "delta_matches": team["matches_played"] - opp["matches_played"],
    }


def update_team_history(stats_a: TeamHistory, stats_b: TeamHistory, row_a: dict, row_b: dict) -> None:
    stats_a.record_match(
        runs_for=row_a["runs_scored"],
        overs_for=row_a["overs_float"],
        won=row_a.get("winning_team") == row_a.get("innings_team"),
        runs_against=row_b["runs_scored"],
        overs_against=row_b["overs_float"],
    )
    stats_b.record_match(
        runs_for=row_b["runs_scored"],
        overs_for=row_b["overs_float"],
        won=row_b.get("winning_team") == row_b.get("innings_team"),
        runs_against=row_a["runs_scored"],
        overs_against=row_a["overs_float"],
    )


def train_model(features: pd.DataFrame, labels: pd.Series) -> GradientBoostingClassifier:
    model = GradientBoostingClassifier(
        n_estimators=400,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.9,
        random_state=42,
    )
    model.fit(features, labels)
    return model


def chronological_split(df: pd.DataFrame, test_ratio: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values("match_date")
    split_idx = int(len(df) * (1 - test_ratio))
    split_idx = max(min(split_idx, len(df) - 1), 1)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    return train_df, test_df


def save_artifacts(model: GradientBoostingClassifier, feature_names: list[str], snapshot: pd.DataFrame) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    dump(model, MODEL_FILE)
    with FEATURE_FILE.open("w", encoding="utf-8") as fh:
        json.dump({"feature_names": feature_names}, fh, indent=2)

    snapshot.to_csv(TEAM_FEATURE_SNAPSHOT, index=False)


def build_team_feature_snapshot(team_history: dict[tuple[str, str], TeamHistory]) -> pd.DataFrame:
    rows = []
    for (competition, team_name), history in team_history.items():
        feats = history.features()
        rows.append(
            {
                "competition": competition,
                "team_name": team_name,
                "team_key": normalise_team_name(team_name),
                "matches_played": history.matches,
                "wins": history.wins,
                "runs_for": history.runs_for,
                "overs_for": history.overs_for,
                "runs_against": history.runs_against,
                "overs_against": history.overs_against,
                "win_pct": feats["win_pct"],
                "run_rate": feats["run_rate"],
                "net_run_rate": feats["net_run_rate"],
                "avg_runs_for": feats["avg_runs_for"],
                "avg_runs_against": feats["avg_runs_against"],
            }
        )
    return pd.DataFrame(rows)


def evaluate(model: GradientBoostingClassifier, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, float]:
    probas = model.predict_proba(X_test)[:, 1]
    preds = (probas >= 0.5).astype(int)
    return {
        "accuracy": float(accuracy_score(y_test, preds)),
        "roc_auc": float(roc_auc_score(y_test, probas)) if len(y_test.unique()) > 1 else float("nan"),
    }


def main() -> None:
    scorecard_path = PROCESSED_DIR / "match_scorecards.csv"
    scorecards = load_scorecards(scorecard_path)
    dataset, team_history = build_training_dataset(scorecards)
    if dataset.empty:
        raise RuntimeError("No training data available. Ensure aggregates are built first.")

    train_df, test_df = chronological_split(dataset)
    X_train = train_df[FEATURE_NAMES]
    y_train = train_df["label"]
    X_test = test_df[FEATURE_NAMES]
    y_test = test_df["label"]

    model = train_model(X_train, y_train)
    metrics = evaluate(model, X_test, y_test)

    print("Training rows:", len(X_train))
    print("Test rows:", len(X_test))
    print("Metrics:", metrics)

    snapshot = build_team_feature_snapshot(team_history)
    save_artifacts(model, FEATURE_NAMES, snapshot)


if __name__ == "__main__":
    main()
