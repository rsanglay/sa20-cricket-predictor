"""Transformation logic for SA20 datasets."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DataTransformer:
    def clean_match_data(self, matches: pd.DataFrame) -> pd.DataFrame:
        matches = matches.drop_duplicates(subset=["match_id"])
        matches["match_date"] = pd.to_datetime(matches["match_date"], errors="coerce")
        return matches.dropna(subset=["match_date"])

    def calculate_player_stats(self, performances: pd.DataFrame) -> pd.DataFrame:
        grouped = (
            performances.groupby("player_id")
            .agg(
                runs=("runs_scored", "sum"),
                wickets=("wickets_taken", "sum"),
                balls=("balls_faced", "sum"),
                overs=("overs_bowled", "sum"),
                runs_conceded=("runs_conceded", "sum"),
            )
            .reset_index()
        )
        grouped["batting_average"] = grouped["runs"] / grouped["balls"].replace(0, np.nan)
        grouped["economy_rate"] = grouped["runs_conceded"] / grouped["overs"].replace(0, np.nan)
        return grouped.fillna(0)

    def calculate_recent_form(self, performances: pd.DataFrame, window: int = 5) -> pd.DataFrame:
        performances = performances.sort_values("match_date")
        recent = performances.groupby("player_id").tail(window)
        return self.calculate_player_stats(recent)
