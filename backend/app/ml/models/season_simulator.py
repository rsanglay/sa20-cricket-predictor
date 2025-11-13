"""Monte Carlo simulation for SA20 seasons."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

from app.ml.models.match_predictor import MatchPredictor


@dataclass
class SeasonSimulator:
    """Run Monte Carlo simulations to produce standings and probabilities."""

    match_predictor: MatchPredictor

    def simulate_season(self, fixtures: pd.DataFrame, num_simulations: int = 1000) -> Dict:
        teams = sorted(
            set(fixtures["home_team_id"].unique()).union(fixtures["away_team_id"].unique())
        )
        playoff_counts = {team: 0 for team in teams}
        champion_counts = {team: 0 for team in teams}
        standings: List[pd.DataFrame] = []

        for _ in range(num_simulations):
            season_results = self._simulate_single_season(fixtures)
            table = self._calculate_standings(season_results, teams)
            standings.append(table)
            playoff = table.head(4)["team_id"].tolist()
            for team in playoff:
                playoff_counts[team] += 1
            champion = self._simulate_playoffs(playoff)
            champion_counts[champion] += 1

        return self._aggregate_results(standings, playoff_counts, champion_counts, teams, num_simulations)

    def _simulate_single_season(self, fixtures: pd.DataFrame) -> pd.DataFrame:
        outcomes = []
        for _, match in fixtures.iterrows():
            feature_vector = {name: 0.0 for name in getattr(self.match_predictor, "feature_names", [])}
            prediction = self.match_predictor.predict_from_vector(feature_vector)
            home_win = np.random.random() < prediction["home_win_probability"]
            outcomes.append(
                {
                    "match_id": match["match_id"],
                    "home_team_id": match["home_team_id"],
                    "away_team_id": match["away_team_id"],
                    "winner_id": match["home_team_id"] if home_win else match["away_team_id"],
                }
            )
        return pd.DataFrame(outcomes)

    def _calculate_standings(self, results: pd.DataFrame, teams: List[int]) -> pd.DataFrame:
        rows = []
        for team in teams:
            played = ((results["home_team_id"] == team) | (results["away_team_id"] == team)).sum()
            wins = (results["winner_id"] == team).sum()
            losses = played - wins
            rows.append(
                {
                    "team_id": team,
                    "matches_played": played,
                    "wins": wins,
                    "losses": losses,
                    "points": wins * 2,
                    "win_rate": wins / played if played else 0,
                }
            )
        table = pd.DataFrame(rows).sort_values(["points", "win_rate"], ascending=False)
        table["position"] = range(1, len(table) + 1)
        return table

    def _simulate_playoffs(self, teams: List[int]) -> int:
        """Simulate SA20 playoff structure: Qualifier 1, Eliminator, Qualifier 2, Final."""
        if len(teams) < 4:
            # Fallback if not enough teams
            return teams[0] if teams else -1
        
        # Qualifier 1: 1st vs 2nd
        q1_winner = self._simulate_match(teams[0], teams[1])
        q1_loser = teams[1] if q1_winner == teams[0] else teams[0]
        
        # Eliminator: 3rd vs 4th
        elim_winner = self._simulate_match(teams[2], teams[3])
        
        # Qualifier 2: Loser Q1 vs Winner Eliminator
        q2_winner = self._simulate_match(q1_loser, elim_winner)
        
        # Final: Winner Q1 vs Winner Q2
        champion = self._simulate_match(q1_winner, q2_winner)
        
        return champion
    
    def _simulate_match(self, team1: int, team2: int) -> int:
        """Simulate a single match between two teams."""
        # Use a simple 50/50 for playoff matches (could be enhanced with actual team strengths)
        # For now, use random but could use match_predictor if we had team features
        rng = np.random.default_rng()
        return team1 if rng.random() < 0.5 else team2

    def _aggregate_results(
        self,
        standings: List[pd.DataFrame],
        playoff_counts: Dict[int, int],
        champion_counts: Dict[int, int],
        teams: List[int],
        num_simulations: int,
    ) -> Dict:
        aggregated = []
        for team in teams:
            positions = [table.loc[table["team_id"] == team, "position"].iloc[0] for table in standings]
            points = [table.loc[table["team_id"] == team, "points"].iloc[0] for table in standings]
            aggregated.append(
                {
                    "team_id": team,
                    "avg_position": float(np.mean(positions)),
                    "avg_points": float(np.mean(points)),
                    "position_std": float(np.std(positions)),
                    "playoff_probability": playoff_counts[team] / num_simulations * 100,
                    "championship_probability": champion_counts[team] / num_simulations * 100,
                }
            )
        aggregated_df = pd.DataFrame(aggregated).sort_values("avg_points", ascending=False)
        return {
            "predicted_standings": aggregated_df.to_dict("records"),
            "playoff_probabilities": {
                team: playoff_counts[team] / num_simulations * 100 for team in teams
            },
            "championship_probabilities": {
                team: champion_counts[team] / num_simulations * 100 for team in teams
            },
            "num_simulations": num_simulations,
        }
