"""Powerplay strategy analysis."""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.db import models


class PowerplayAnalyzer:
    """Analyzes powerplay strategy and recommends intent level.
    
    Estimates aggressiveness frontier: runs vs wicket risk using historical
    PP trade-offs by lineup archetype.
    """
    
    def __init__(self, db_session: Session):
        """Initialize powerplay analyzer.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
    
    def analyze_powerplay_strategy(
        self,
        batting_team_id: int,
        bowling_team_id: int,
        venue_id: Optional[int] = None,
        wickets_down: int = 0,
        overs_completed: float = 0.0,
    ) -> Dict:
        """Analyze powerplay strategy and recommend intent level.
        
        Args:
            batting_team_id: Batting team ID
            bowling_team_id: Bowling team ID
            venue_id: Venue ID (optional)
            wickets_down: Wickets down
            overs_completed: Overs completed in powerplay
        
        Returns:
            Dictionary with powerplay analysis and recommendations
        """
        # Get teams
        batting_team = self.db.get(models.Team, batting_team_id)
        bowling_team = self.db.get(models.Team, bowling_team_id)
        
        if not batting_team or not bowling_team:
            raise ValueError("Invalid team ID")
        
        # Get venue stats
        venue = self.db.get(models.Venue, venue_id) if venue_id else None
        venue_avg = venue.avg_first_innings_score if venue else 160.0
        
        # Get historical powerplay performance
        pp_stats = self._get_powerplay_stats(batting_team_id, venue_id)
        
        # Calculate par score
        par_score = self._calculate_par_score(venue_avg, wickets_down, overs_completed)
        
        # Recommend intent level
        intent_level = self._recommend_intent_level(
            pp_stats, wickets_down, overs_completed, par_score
        )
        
        # Calculate aggressiveness frontier
        frontier = self._calculate_aggressiveness_frontier(pp_stats, wickets_down)
        
        return {
            "par_score_6_overs": par_score,
            "current_score_estimate": pp_stats.get("avg_runs", 45),
            "wickets_down": wickets_down,
            "overs_completed": overs_completed,
            "recommended_intent": intent_level,
            "aggressiveness_frontier": frontier,
            "reasoning": self._generate_reasoning(intent_level, par_score, wickets_down),
        }
    
    def _get_powerplay_stats(
        self,
        team_id: int,
        venue_id: Optional[int],
    ) -> Dict:
        """Get historical powerplay statistics.
        
        Args:
            team_id: Team ID
            venue_id: Venue ID (optional)
            
        Returns:
            Dictionary with powerplay stats
        """
        # Simplified: In production, this would query actual powerplay data
        # For now, return defaults based on team
        return {
            "avg_runs": 45.0,  # Average runs in powerplay
            "avg_wickets": 0.8,  # Average wickets in powerplay
            "avg_sr": 135.0,  # Average strike rate
            "risk_level": "moderate",
        }
    
    def _calculate_par_score(
        self,
        venue_avg: float,
        wickets_down: int,
        overs_completed: float,
    ) -> float:
        """Calculate par score for powerplay.
        
        Args:
            venue_avg: Venue average first innings score
            wickets_down: Wickets down
            overs_completed: Overs completed
        
        Returns:
            Par score for 6 overs
        """
        # Base par: ~28% of venue average in first 6 overs
        base_par = venue_avg * 0.28
        
        # Adjust for wickets
        if wickets_down == 0:
            par_multiplier = 1.0
        elif wickets_down == 1:
            par_multiplier = 0.95
        elif wickets_down == 2:
            par_multiplier = 0.85
        else:
            par_multiplier = 0.75
        
        # Adjust for overs completed
        if overs_completed > 0:
            # Scale down par based on overs completed
            remaining_overs = 6.0 - overs_completed
            par_multiplier *= (remaining_overs / 6.0)
        
        return base_par * par_multiplier
    
    def _recommend_intent_level(
        self,
        pp_stats: Dict,
        wickets_down: int,
        overs_completed: float,
        par_score: float,
    ) -> str:
        """Recommend powerplay intent level.
        
        Args:
            pp_stats: Powerplay statistics
            wickets_down: Wickets down
            overs_completed: Overs completed
            par_score: Par score
        
        Returns:
            Intent level: 'conservative', 'balanced', or 'aggressive'
        """
        current_estimate = pp_stats.get("avg_runs", 45.0)
        
        # Calculate required run rate
        remaining_overs = 6.0 - overs_completed
        if remaining_overs <= 0:
            return "balanced"
        
        required_runs = par_score - (current_estimate * (overs_completed / 6.0))
        required_rr = required_runs / remaining_overs
        
        # Adjust for wickets
        if wickets_down == 0:
            # Can be more aggressive
            if required_rr > 10:
                return "aggressive"
            elif required_rr > 8:
                return "balanced"
            else:
                return "conservative"
        elif wickets_down == 1:
            # Balance aggression and stability
            if required_rr > 9:
                return "aggressive"
            elif required_rr > 7:
                return "balanced"
            else:
                return "conservative"
        else:
            # Need to be more conservative
            if required_rr > 8:
                return "balanced"
            else:
                return "conservative"
    
    def _calculate_aggressiveness_frontier(
        self,
        pp_stats: Dict,
        wickets_down: int,
    ) -> Dict:
        """Calculate aggressiveness frontier (runs vs wicket risk).
        
        Args:
            pp_stats: Powerplay statistics
            wickets_down: Wickets down
        
        Returns:
            Dictionary with frontier data
        """
        # Simplified: Return frontier points
        return {
            "conservative": {
                "expected_runs": 40.0,
                "wicket_risk": 0.3,
            },
            "balanced": {
                "expected_runs": 50.0,
                "wicket_risk": 0.5,
            },
            "aggressive": {
                "expected_runs": 60.0,
                "wicket_risk": 0.7,
            },
        }
    
    def _generate_reasoning(
        self,
        intent_level: str,
        par_score: float,
        wickets_down: int,
    ) -> str:
        """Generate human-readable reasoning.
        
        Args:
            intent_level: Recommended intent level
            par_score: Par score
            wickets_down: Wickets down
        
        Returns:
            Reasoning string
        """
        if intent_level == "aggressive":
            return f"Recommend aggressive approach to reach par score of {par_score:.1f} with {wickets_down} wicket(s) down"
        elif intent_level == "balanced":
            return f"Recommend balanced approach to reach par score of {par_score:.1f} with {wickets_down} wicket(s) down"
        else:
            return f"Recommend conservative approach to preserve wickets while targeting par score of {par_score:.1f}"

