"""Ball-by-ball simulation engine."""
from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Tuple

from app.db import models


class BallByBallEngine:
    """Ball-by-ball simulation engine.
    
    Samples outcomes {0,1,2,3,4,6,W,extras} based on batter/bowler/phase context.
    """
    
    # Outcome probabilities by phase (simplified - can be enhanced with ML)
    OUTCOME_PROBS = {
        "powerplay": {
            0: 0.35, 1: 0.20, 2: 0.15, 3: 0.02, 4: 0.15, 6: 0.08, "W": 0.05
        },
        "middle": {
            0: 0.30, 1: 0.25, 2: 0.18, 3: 0.02, 4: 0.12, 6: 0.08, "W": 0.05
        },
        "death": {
            0: 0.25, 1: 0.20, 2: 0.12, 3: 0.01, 4: 0.18, 6: 0.20, "W": 0.04
        },
    }
    
    def __init__(self):
        """Initialize the ball-by-ball engine."""
        pass
    
    def simulate_innings(
        self,
        batting_team_id: int,
        bowling_team_id: int,
        target: Optional[int] = None,
        db_session = None,
    ) -> Dict:
        """Simulate an innings ball-by-ball.
        
        Args:
            batting_team_id: Batting team ID
            bowling_team_id: Bowling team ID
            target: Target score (for second innings, optional)
            db_session: Database session
            
        Returns:
            Dictionary with innings results
        """
        if db_session is None:
            raise ValueError("Database session required")
        
        total_runs = 0
        wickets = 0
        balls_bowled = 0
        overs = 0
        deliveries = []
        
        # Get team players
        batting_players = db_session.query(models.Player).filter(
            models.Player.team_id == batting_team_id
        ).limit(11).all()
        
        bowling_players = db_session.query(models.Player).filter(
            models.Player.team_id == bowling_team_id
        ).limit(11).all()
        
        if not batting_players or not bowling_players:
            raise ValueError("Insufficient players for simulation")
        
        # Current batsmen (simplified: use first two)
        striker_idx = 0
        non_striker_idx = 1
        current_bowler_idx = 0
        
        # Simulate 20 overs (120 balls)
        max_balls = 120
        max_wickets = 10
        
        for ball in range(max_balls):
            if wickets >= max_wickets:
                break
            
            if target and total_runs >= target:
                break
            
            # Determine phase
            phase = self._get_phase(balls_bowled)
            
            # Sample outcome
            outcome = self._sample_outcome(phase)
            
            # Process outcome
            if outcome == "W":
                wickets += 1
                runs_this_ball = 0
                # Next batsman comes in
                if striker_idx < len(batting_players) - 1:
                    striker_idx = max(striker_idx, non_striker_idx) + 1
            else:
                runs_this_ball = outcome
                total_runs += runs_this_ball
            
            # Update balls/overs
            balls_bowled += 1
            if balls_bowled % 6 == 0:
                overs += 1
                # Swap striker/non-striker
                striker_idx, non_striker_idx = non_striker_idx, striker_idx
                # Change bowler every over (simplified)
                if overs % 1 == 0 and current_bowler_idx < len(bowling_players) - 1:
                    current_bowler_idx = (current_bowler_idx + 1) % len(bowling_players)
            
            deliveries.append({
                "over": overs,
                "ball": (balls_bowled - 1) % 6 + 1,
                "batsman_id": batting_players[striker_idx].id if striker_idx < len(batting_players) else None,
                "bowler_id": bowling_players[current_bowler_idx].id if current_bowler_idx < len(bowling_players) else None,
                "runs": runs_this_ball,
                "wicket": outcome == "W",
                "phase": phase,
            })
        
        return {
            "total_runs": total_runs,
            "wickets": wickets,
            "overs": overs + (balls_bowled % 6) / 6.0,
            "balls_bowled": balls_bowled,
            "deliveries": deliveries,
            "target_reached": target is not None and total_runs >= target,
        }
    
    def _get_phase(self, balls_bowled: int) -> str:
        """Get match phase based on balls bowled.
        
        Args:
            balls_bowled: Number of balls bowled
            
        Returns:
            Phase name: 'powerplay', 'middle', or 'death'
        """
        if balls_bowled < 36:  # First 6 overs
            return "powerplay"
        elif balls_bowled < 96:  # Overs 7-16
            return "middle"
        else:  # Overs 17-20
            return "death"
    
    def _sample_outcome(self, phase: str) -> int | str:
        """Sample a ball outcome based on phase.
        
        Args:
            phase: Match phase
            
        Returns:
            Outcome: 0, 1, 2, 3, 4, 6, or "W"
        """
        probs = self.OUTCOME_PROBS[phase]
        outcomes = list(probs.keys())
        probabilities = list(probs.values())
        
        # Normalize probabilities
        total = sum(probabilities)
        probabilities = [p / total for p in probabilities]
        
        return np.random.choice(outcomes, p=probabilities)
    
    def simulate_match(
        self,
        team1_id: int,
        team2_id: int,
        venue_id: int,
        toss_winner_id: Optional[int] = None,
        toss_decision: Optional[str] = None,
        db_session = None,
    ) -> Dict:
        """Simulate a match ball-by-ball.
        
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
        
        # Determine batting order
        if toss_winner_id == team1_id:
            batting_first_id = team1_id
            bowling_first_id = team2_id
        elif toss_winner_id == team2_id:
            batting_first_id = team2_id
            bowling_first_id = team1_id
        else:
            # Default: team1 bats first
            batting_first_id = team1_id
            bowling_first_id = team2_id
        
        # Simulate first innings
        first_innings = self.simulate_innings(
            batting_first_id, bowling_first_id, target=None, db_session=db_session
        )
        
        # Simulate second innings
        target = first_innings["total_runs"] + 1
        second_innings = self.simulate_innings(
            bowling_first_id, batting_first_id, target=target, db_session=db_session
        )
        
        # Determine winner
        if first_innings["total_runs"] > second_innings["total_runs"]:
            winner_id = batting_first_id
            margin = first_innings["total_runs"] - second_innings["total_runs"]
            margin_text = f"{margin} runs"
        else:
            winner_id = bowling_first_id
            margin = 10 - second_innings["wickets"]
            margin_text = f"{margin} wickets"
        
        return {
            "team1_id": team1_id,
            "team2_id": team2_id,
            "batting_first_id": batting_first_id,
            "first_innings": first_innings,
            "second_innings": second_innings,
            "winner_id": winner_id,
            "margin": margin_text,
        }

