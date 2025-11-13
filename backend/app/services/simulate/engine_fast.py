"""Fast score distribution-based simulation engine."""
from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Tuple

from app.db import models


class FastSimulationEngine:
    """Fast simulation engine using score distribution approach.
    
    Predicts μ/σ scores conditioned on batting/bowling power, venue, toss;
    samples scores and decides winner; allocates player contributions statistically.
    """
    
    def __init__(self, match_predictor):
        """Initialize the fast simulation engine.
        
        Args:
            match_predictor: MatchPredictor instance for win probabilities
        """
        self.match_predictor = match_predictor
    
    def simulate_match(
        self,
        team1_id: int,
        team2_id: int,
        venue_id: int,
        toss_winner_id: Optional[int] = None,
        toss_decision: Optional[str] = None,
        db_session = None,
    ) -> Dict:
        """Simulate a single match using score distribution.
        
        Args:
            team1_id: First team ID
            team2_id: Second team ID
            venue_id: Venue ID
            toss_winner_id: Toss winner ID (optional)
            toss_decision: Toss decision ('bat' or 'bowl') (optional)
            db_session: Database session
            
        Returns:
            Dictionary with match simulation results
        """
        if db_session is None:
            raise ValueError("Database session required")
        
        team1 = db_session.get(models.Team, team1_id)
        team2 = db_session.get(models.Team, team2_id)
        venue = db_session.get(models.Venue, venue_id)
        
        if not team1 or not team2 or not venue:
            raise ValueError("Invalid team or venue ID")
        
        # Get venue average score
        venue_avg = venue.avg_first_innings_score or 160.0
        
        # Estimate batting/bowling strengths (simplified - can be enhanced)
        team1_batting_power = self._estimate_batting_power(team1_id, db_session)
        team1_bowling_power = self._estimate_bowling_power(team1_id, db_session)
        team2_batting_power = self._estimate_batting_power(team2_id, db_session)
        team2_bowling_power = self._estimate_bowling_power(team2_id, db_session)
        
        # Determine batting order from toss
        if toss_winner_id == team1_id:
            batting_first_id = team1_id
            bowling_first_id = team2_id
            batting_first_power = team1_batting_power
            bowling_first_power = team2_bowling_power
        elif toss_winner_id == team2_id:
            batting_first_id = team2_id
            bowling_first_id = team1_id
            batting_first_power = team2_batting_power
            bowling_first_power = team1_bowling_power
        else:
            # Default: team1 bats first
            batting_first_id = team1_id
            bowling_first_id = team2_id
            batting_first_power = team1_batting_power
            bowling_first_power = team2_bowling_power
        
        # Calculate expected scores
        first_innings_score = self._sample_score(
            venue_avg, batting_first_power, bowling_first_power
        )
        second_innings_score = self._sample_score(
            venue_avg, team2_batting_power if batting_first_id == team1_id else team1_batting_power,
            team1_bowling_power if batting_first_id == team1_id else team2_bowling_power,
            target=first_innings_score + 1,
        )
        
        # Determine winner
        if first_innings_score > second_innings_score:
            winner_id = batting_first_id
            margin = first_innings_score - second_innings_score
            margin_text = f"{margin} runs"
        else:
            winner_id = bowling_first_id
            wickets_remaining = max(0, 10 - int(np.random.poisson(3)))  # Simplified
            margin = 10 - wickets_remaining
            margin_text = f"{margin} wickets"
        
        # Allocate player contributions (simplified statistical allocation)
        player_contributions = self._allocate_player_contributions(
            batting_first_id, first_innings_score, db_session
        )
        player_contributions.extend(
            self._allocate_player_contributions(
                bowling_first_id, second_innings_score, db_session
            )
        )
        
        return {
            "team1_id": team1_id,
            "team2_id": team2_id,
            "batting_first_id": batting_first_id,
            "first_innings_score": int(first_innings_score),
            "second_innings_score": int(second_innings_score),
            "winner_id": winner_id,
            "margin": margin_text,
            "player_contributions": player_contributions,
        }
    
    def _estimate_batting_power(self, team_id: int, db_session) -> float:
        """Estimate team batting power (0-1 scale)."""
        # Simplified: can be enhanced with actual player stats
        players = db_session.query(models.Player).filter(
            models.Player.team_id == team_id
        ).all()
        
        if not players:
            return 0.5  # Default
        
        # Simple heuristic: count batsmen/all-rounders
        batting_players = [p for p in players if p.role in [
            models.PlayerRole.BATSMAN,
            models.PlayerRole.ALL_ROUNDER,
            models.PlayerRole.WICKET_KEEPER,
        ]]
        
        return min(1.0, len(batting_players) / 7.0)
    
    def _estimate_bowling_power(self, team_id: int, db_session) -> float:
        """Estimate team bowling power (0-1 scale)."""
        # Simplified: can be enhanced with actual player stats
        players = db_session.query(models.Player).filter(
            models.Player.team_id == team_id
        ).all()
        
        if not players:
            return 0.5  # Default
        
        # Simple heuristic: count bowlers/all-rounders
        bowling_players = [p for p in players if p.role in [
            models.PlayerRole.BOWLER,
            models.PlayerRole.ALL_ROUNDER,
        ]]
        
        return min(1.0, len(bowling_players) / 5.0)
    
    def _sample_score(
        self,
        venue_avg: float,
        batting_power: float,
        bowling_power: float,
        target: Optional[float] = None,
    ) -> float:
        """Sample a team score from distribution.
        
        Args:
            venue_avg: Average score at venue
            batting_power: Batting team power (0-1)
            bowling_power: Bowling team power (0-1)
            target: Target score (for second innings, optional)
            
        Returns:
            Sampled score
        """
        # Base score adjusted by power difference
        power_diff = batting_power - bowling_power
        mean_score = venue_avg * (1.0 + power_diff * 0.2)
        
        # Add some randomness
        std_dev = venue_avg * 0.15
        score = np.random.normal(mean_score, std_dev)
        
        # Clamp to reasonable bounds
        score = max(80, min(250, score))
        
        # If target exists (second innings), adjust for chase scenarios
        if target is not None:
            # Teams often score slightly less when chasing, or more if aggressive
            chase_factor = np.random.uniform(0.95, 1.05)
            score = score * chase_factor
        
        return score
    
    def _allocate_player_contributions(
        self,
        team_id: int,
        total_score: int,
        db_session,
    ) -> List[Dict]:
        """Allocate score contributions to players (simplified).
        
        Args:
            team_id: Team ID
            total_score: Total team score
            db_session: Database session
            
        Returns:
            List of player contribution dictionaries
        """
        players = db_session.query(models.Player).filter(
            models.Player.team_id == team_id
        ).limit(11).all()
        
        if not players:
            return []
        
        # Simplified allocation: distribute score among top 6-7 batsmen
        batting_players = [p for p in players if p.role in [
            models.PlayerRole.BATSMAN,
            models.PlayerRole.ALL_ROUNDER,
            models.PlayerRole.WICKET_KEEPER,
        ]][:7]
        
        contributions = []
        remaining_score = total_score
        
        # Allocate runs to players (simplified distribution)
        for i, player in enumerate(batting_players):
            if i == len(batting_players) - 1:
                # Last player gets remaining runs
                runs = remaining_score
            else:
                # Allocate proportionally (top order gets more)
                proportion = (len(batting_players) - i) / sum(range(1, len(batting_players) + 1))
                runs = int(total_score * proportion * np.random.uniform(0.8, 1.2))
                runs = min(runs, remaining_score)
                remaining_score -= runs
            
            contributions.append({
                "player_id": player.id,
                "runs": max(0, runs),
                "balls": int(runs * np.random.uniform(0.8, 1.5)),  # Simplified
                "wickets": 0,
            })
        
        # Allocate wickets to bowlers (simplified)
        bowling_players = [p for p in players if p.role in [
            models.PlayerRole.BOWLER,
            models.PlayerRole.ALL_ROUNDER,
        ]][:5]
        
        total_wickets = min(10, len(batting_players))
        for i, player in enumerate(bowling_players):
            if i < total_wickets:
                # Distribute wickets
                wickets = 1 if i < total_wickets else 0
                contributions.append({
                    "player_id": player.id,
                    "runs": 0,
                    "balls": 0,
                    "wickets": wickets,
                    "overs": np.random.uniform(3.0, 4.0),
                    "runs_conceded": int(np.random.uniform(20, 40)),
                })
        
        return contributions

