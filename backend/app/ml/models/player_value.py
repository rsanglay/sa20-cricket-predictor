"""Player performance and value prediction models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import mlflow
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


@dataclass
class PlayerValuePredictor:
    """Collection of regressors for player performance estimation."""

    runs_model: RandomForestRegressor | None = None
    wickets_model: GradientBoostingRegressor | None = None
    value_model: RandomForestRegressor | None = None

    def train_performance_models(
        self, player_features: pd.DataFrame, performances: pd.DataFrame
    ) -> None:
        batsmen = player_features[player_features["role"].isin(["batsman", "all_rounder"])]
        batsmen_perfs = performances[performances["player_id"].isin(batsmen["player_id"])]
        batting_cols = [
            "career_batting_avg",
            "recent_batting_avg",
            "career_strike_rate",
            "recent_strike_rate",
        ]
        X_batting = batsmen_perfs[batting_cols]
        y_runs = batsmen_perfs["runs_scored"]
        X_train, X_test, y_train, y_test = train_test_split(
            X_batting, y_runs, test_size=0.2, random_state=42
        )
        self.runs_model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42)
        self.runs_model.fit(X_train, y_train)
        y_pred = self.runs_model.predict(X_test)
        self._log_metrics("runs_model", y_test, y_pred)

        bowlers = player_features[player_features["role"].isin(["bowler", "all_rounder"])]
        bowlers_perfs = performances[performances["player_id"].isin(bowlers["player_id"])]
        bowling_cols = [
            "career_wickets",
            "recent_wickets",
            "career_economy",
        ]
        X_bowling = bowlers_perfs[bowling_cols]
        y_wickets = bowlers_perfs["wickets_taken"]
        X_train, X_test, y_train, y_test = train_test_split(
            X_bowling, y_wickets, test_size=0.2, random_state=42
        )
        self.wickets_model = GradientBoostingRegressor(random_state=42)
        self.wickets_model.fit(X_train, y_train)
        y_pred = self.wickets_model.predict(X_test)
        self._log_metrics("wickets_model", y_test, y_pred)

    def train_value_model(self, player_features: pd.DataFrame) -> None:
        feature_cols = [
            "career_batting_avg",
            "career_strike_rate",
            "career_wickets",
            "career_economy",
            "age",
            "international_caps",
            "recent_batting_avg",
        ]
        X = player_features[feature_cols]
        y = player_features["auction_price"].fillna(0)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        self.value_model = RandomForestRegressor(n_estimators=300, max_depth=12, random_state=42)
        self.value_model.fit(X_train, y_train)
        y_pred = self.value_model.predict(X_test)
        self._log_metrics("value_model", y_test, y_pred)

    def predict_performance(self, player_features: pd.DataFrame) -> Dict[str, float]:
        predictions: Dict[str, float] = {}
        if self.runs_model is not None:
            predictions["predicted_runs"] = float(self.runs_model.predict(player_features)[0])
        if self.wickets_model is not None:
            predictions["predicted_wickets"] = float(
                self.wickets_model.predict(player_features)[0]
            )
        return predictions

    def predict_value(self, player_features: pd.DataFrame) -> float:
        if self.value_model is None:
            raise ValueError("Value model not trained yet")
        return float(self.value_model.predict(player_features)[0])

    def identify_undervalued_players(
        self, players: pd.DataFrame, threshold: float = 0.2
    ) -> List[Dict[str, float]]:
        undervalued: List[Dict[str, float]] = []
        if self.value_model is None:
            return undervalued
        for _, row in players.iterrows():
            features = row[[
                "career_batting_avg",
                "career_strike_rate",
                "career_wickets",
                "career_economy",
                "age",
                "international_caps",
                "recent_batting_avg",
            ]].to_frame().T
            predicted = self.predict_value(features)
            actual = row.get("auction_price", 0) or 0
            if predicted > actual * (1 + threshold):
                undervalued.append(
                    {
                        "player_id": int(row["player_id"]),
                        "name": row.get("name", "Unknown"),
                        "actual_value": float(actual),
                        "predicted_value": float(predicted),
                        "value_gap": float(predicted - actual),
                    }
                )
        return sorted(undervalued, key=lambda item: item["value_gap"], reverse=True)

    def _log_metrics(self, model_name: str, y_true: pd.Series, y_pred: np.ndarray) -> None:
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        r2 = float(r2_score(y_true, y_pred))
        mae = float(mean_absolute_error(y_true, y_pred))
        mlflow.set_experiment("player_value_predictor")
        with mlflow.start_run(run_name=model_name):
            mlflow.log_metric("rmse", rmse)
            mlflow.log_metric("r2", r2)
            mlflow.log_metric("mae", mae)
