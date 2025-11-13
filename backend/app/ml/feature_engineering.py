"""Feature engineering utilities for players, teams, and matches."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass
class FeatureEngineer:
    """Construct derived features for machine learning models."""

    def clean_match_data(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.drop_duplicates()
        df = df.dropna(subset=["match_date", "home_team_id", "away_team_id"])
        df["match_date"] = pd.to_datetime(df["match_date"])
        return df

    def calculate_player_stats(self, performances: pd.DataFrame) -> pd.DataFrame:
        stats = (
            performances.groupby("player_id")
            .agg(
                runs_scored_sum=("runs_scored", "sum"),
                runs_scored_mean=("runs_scored", "mean"),
                balls_faced_sum=("balls_faced", "sum"),
                wickets_taken_sum=("wickets_taken", "sum"),
                wickets_taken_mean=("wickets_taken", "mean"),
                overs_bowled_sum=("overs_bowled", "sum"),
                runs_conceded_sum=("runs_conceded", "sum"),
            )
            .reset_index()
        )
        stats["batting_average"] = stats["runs_scored_sum"].clip(lower=0) / stats[
            "balls_faced_sum"
        ].replace(0, np.nan)
        stats["economy_rate"] = stats["runs_conceded_sum"] / stats["overs_bowled_sum"].replace(
            0, np.nan
        )
        return stats

    def create_player_features(self, player_id: int, performances: pd.DataFrame) -> Dict[str, float]:
        player_data = performances[performances["player_id"] == player_id].copy()
        if player_data.empty:
            return {}

        features: Dict[str, float] = {}
        features["career_batting_avg"] = player_data["runs_scored"].mean()
        features["career_strike_rate"] = (
            player_data["runs_scored"].sum() / player_data["balls_faced"].replace(0, np.nan).sum()
        ) * 100
        features["career_wickets"] = player_data["wickets_taken"].sum()
        features["career_economy"] = (
            player_data["runs_conceded"].sum()
            / player_data["overs_bowled"].replace(0, np.nan).sum()
        )

        recent = player_data.sort_values("match_date").tail(5)
        features["recent_batting_avg"] = recent["runs_scored"].mean()
        features["recent_strike_rate"] = (
            recent["runs_scored"].sum()
            / recent["balls_faced"].replace(0, np.nan).sum()
        ) * 100
        features["recent_wickets"] = recent["wickets_taken"].mean()

        features["batting_consistency"] = player_data["runs_scored"].std(ddof=0)
        features["bowling_consistency"] = player_data["wickets_taken"].std(ddof=0)

        return {k: float(v) if pd.notna(v) else 0.0 for k, v in features.items()}

    def create_team_features(
        self,
        team_id: int,
        matches: pd.DataFrame,
        player_features: pd.DataFrame,
    ) -> Dict[str, float]:
        team_matches = matches[
            (matches["home_team_id"] == team_id) | (matches["away_team_id"] == team_id)
        ].copy()
        if team_matches.empty:
            return {}

        features: Dict[str, float] = {}
        features["win_rate"] = (
            (team_matches["winner_id"] == team_id).sum() / len(team_matches)
        )

        recent = team_matches.sort_values("match_date").tail(5)
        features["recent_form"] = (
            (recent["winner_id"] == team_id).sum() / recent.shape[0]
        )

        home_matches = team_matches[team_matches["home_team_id"] == team_id]
        if not home_matches.empty:
            features["home_win_rate"] = (
                (home_matches["winner_id"] == team_id).sum() / home_matches.shape[0]
            )
        else:
            features["home_win_rate"] = 0.0

        player_subset = player_features[player_features["team_id"] == team_id]
        if not player_subset.empty:
            features["avg_player_impact"] = player_subset["career_batting_avg"].mean()
            features["bowling_strength"] = player_subset["career_wickets"].sum()
            features["num_batsmen"] = (player_subset["role"] == "batsman").sum()
            features["num_bowlers"] = (player_subset["role"] == "bowler").sum()
            features["num_all_rounders"] = (player_subset["role"] == "all_rounder").sum()
        else:
            features.update({
                "avg_player_impact": 0.0,
                "bowling_strength": 0.0,
                "num_batsmen": 0.0,
                "num_bowlers": 0.0,
                "num_all_rounders": 0.0,
            })

        return {k: float(v) if pd.notna(v) else 0.0 for k, v in features.items()}

    def create_match_features(
        self,
        home_team_id: int,
        away_team_id: int,
        venue_id: int,
        team_features: pd.DataFrame,
        venue_data: pd.DataFrame,
    ) -> Dict[str, float]:
        home = team_features[team_features["team_id"] == home_team_id]
        away = team_features[team_features["team_id"] == away_team_id]
        venue = venue_data[venue_data["id"] == venue_id]
        if home.empty or away.empty or venue.empty:
            return {}

        home_row = home.iloc[0]
        away_row = away.iloc[0]
        venue_row = venue.iloc[0]

        features = {
            "win_rate_diff": float(home_row.get("win_rate", 0) - away_row.get("win_rate", 0)),
            "form_diff": float(home_row.get("recent_form", 0) - away_row.get("recent_form", 0)),
            "venue_avg_score": float(venue_row.get("avg_first_innings_score", 0)),
            "home_venue_advantage": float(
                1
                if venue_row.get("name") and home_row.get("home_venue")
                and venue_row.get("name") == home_row.get("home_venue")
                else 0
            ),
        }

        return features
