"""ML feature engineering service."""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.db import models
from app.ml.feature_engineering import FeatureEngineer


class FeatureService:
    """Service for building ML features for teams, players, and matches."""
    
    def __init__(self, db_session: Session):
        """Initialize feature service.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
        self.feature_engineer = FeatureEngineer()
    
    def build_team_features(
        self,
        team_id: int,
        competition: str = "sa20",
    ) -> Dict[str, float]:
        """Build team features for ML models.
        
        Args:
            team_id: Team ID
            competition: Competition name
            
        Returns:
            Dictionary of team features
        """
        team = self.db.get(models.Team, team_id)
        if not team:
            raise ValueError(f"Team {team_id} not found")
        
        # Get team matches
        matches = self.db.query(models.Match).filter(
            (models.Match.home_team_id == team_id) | (models.Match.away_team_id == team_id)
        ).all()
        
        # Get team performances
        players = self.db.query(models.Player).filter(
            models.Player.team_id == team_id
        ).all()
        
        # Build features
        features = {
            "team_batting_elo": self._calculate_batting_elo(team_id, matches),
            "team_bowling_elo": self._calculate_bowling_elo(team_id, matches),
            "team_recent_form": self._calculate_recent_form(team_id, matches),
            "team_venue_factor": self._calculate_venue_factor(team_id, matches),
        }
        
        return features
    
    def build_player_features(
        self,
        player_id: int,
        phase: Optional[str] = None,
    ) -> Dict[str, float]:
        """Build player features for ML models.
        
        Args:
            player_id: Player ID
            phase: Match phase ('powerplay', 'middle', 'death') (optional)
            
        Returns:
            Dictionary of player features
        """
        player = self.db.get(models.Player, player_id)
        if not player:
            raise ValueError(f"Player {player_id} not found")
        
        # Get player performances
        performances = self.db.query(models.PlayerPerformance).filter(
            models.PlayerPerformance.player_id == player_id
        ).all()
        
        if not performances:
            return self._get_default_player_features(player)
        
        # Convert to DataFrame for feature engineering
        perf_df = pd.DataFrame([
            {
                "player_id": p.player_id,
                "runs_scored": p.runs_scored,
                "balls_faced": p.balls_faced,
                "wickets_taken": p.wickets_taken,
                "overs_bowled": p.overs_bowled,
                "runs_conceded": p.runs_conceded,
                "strike_rate": p.strike_rate or 0.0,
                "economy_rate": p.economy_rate or 0.0,
            }
            for p in performances
        ])
        
        # Build features
        features = self.feature_engineer.create_player_features(player_id, perf_df)
        
        # Add phase-specific features if phase is specified
        if phase:
            features.update(self._get_phase_features(player_id, phase))
        
        return features
    
    def build_match_features(
        self,
        team1_id: int,
        team2_id: int,
        venue_id: int,
    ) -> Dict[str, float]:
        """Build match features for ML models.
        
        Args:
            team1_id: First team ID
            team2_id: Second team ID
            venue_id: Venue ID
            
        Returns:
            Dictionary of match features
        """
        team1_features = self.build_team_features(team1_id)
        team2_features = self.build_team_features(team2_id)
        
        venue = self.db.get(models.Venue, venue_id)
        if not venue:
            raise ValueError(f"Venue {venue_id} not found")
        
        # Build match-specific features
        features = {
            f"team1_{k}": v for k, v in team1_features.items()
        }
        features.update({
            f"team2_{k}": v for k, v in team2_features.items()
        })
        
        # Venue features
        features["venue_avg_score"] = venue.avg_first_innings_score or 160.0
        features["venue_altitude"] = venue.altitude_m or 0.0
        
        # Head-to-head features
        h2h = self._calculate_head_to_head(team1_id, team2_id)
        features.update(h2h)
        
        return features
    
    def _calculate_batting_elo(self, team_id: int, matches: List[models.Match]) -> float:
        """Calculate team batting Elo rating."""
        # Simplified Elo calculation
        # In production, this would use a proper Elo system
        return 1500.0  # Default Elo
    
    def _calculate_bowling_elo(self, team_id: int, matches: List[models.Match]) -> float:
        """Calculate team bowling Elo rating."""
        # Simplified Elo calculation
        return 1500.0  # Default Elo
    
    def _calculate_recent_form(self, team_id: int, matches: List[models.Match]) -> float:
        """Calculate recent form (win rate in last 5 matches)."""
        if not matches:
            return 0.5  # Default
        
        # Get recent matches (last 5)
        recent_matches = sorted(matches, key=lambda m: m.match_date, reverse=True)[:5]
        
        wins = sum(1 for m in recent_matches if m.winner_id == team_id)
        return wins / len(recent_matches) if recent_matches else 0.5
    
    def _calculate_venue_factor(self, team_id: int, matches: List[models.Match]) -> float:
        """Calculate venue factor (performance at venue)."""
        # Simplified: return default
        return 1.0
    
    def _calculate_head_to_head(self, team1_id: int, team2_id: int) -> Dict[str, float]:
        """Calculate head-to-head features."""
        matches = self.db.query(models.Match).filter(
            ((models.Match.home_team_id == team1_id) & (models.Match.away_team_id == team2_id)) |
            ((models.Match.home_team_id == team2_id) & (models.Match.away_team_id == team1_id))
        ).all()
        
        if not matches:
            return {
                "h2h_team1_wins": 0.0,
                "h2h_team2_wins": 0.0,
                "h2h_team1_win_rate": 0.5,
            }
        
        team1_wins = sum(1 for m in matches if m.winner_id == team1_id)
        team2_wins = sum(1 for m in matches if m.winner_id == team2_id)
        
        return {
            "h2h_team1_wins": float(team1_wins),
            "h2h_team2_wins": float(team2_wins),
            "h2h_team1_win_rate": team1_wins / len(matches) if matches else 0.5,
        }
    
    def _get_default_player_features(self, player: models.Player) -> Dict[str, float]:
        """Get default player features when no performance data exists."""
        return {
            "career_batting_avg": 20.0,
            "career_strike_rate": 120.0,
            "career_wickets": 0.0,
            "career_economy": 8.0,
        }
    
    def _get_phase_features(self, player_id: int, phase: str) -> Dict[str, float]:
        """Get phase-specific player features."""
        # Simplified: return default phase features
        # In production, this would query phase-specific performance data
        return {
            f"{phase}_strike_rate": 130.0,
            f"{phase}_dismissal_rate": 0.3,
        }

