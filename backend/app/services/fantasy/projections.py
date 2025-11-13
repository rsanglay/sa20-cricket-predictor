"""Fantasy cricket player projections service."""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.db import models


class FantasyProjectionService:
    """Service for generating fantasy cricket player projections."""
    
    def __init__(self, db_session: Session):
        """Initialize fantasy projection service.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
    
    def get_player_projections(
        self,
        matchday: str,
        player_ids: Optional[List[int]] = None,
    ) -> List[Dict]:
        """Get fantasy projections for players for a matchday.
        
        Args:
            matchday: Matchday identifier (e.g., "2026-01-15")
            player_ids: Optional list of player IDs to filter
            
        Returns:
            List of player projections
        """
        # Get matches for matchday
        matches = self.db.query(models.Match).filter(
            models.Match.match_date.like(f"{matchday}%")
        ).all()
        
        if not matches:
            return []
        
        # Get players
        if player_ids:
            players = self.db.query(models.Player).filter(
                models.Player.id.in_(player_ids)
            ).all()
        else:
            # Get all players from teams playing on this matchday
            team_ids = set()
            for match in matches:
                team_ids.add(match.home_team_id)
                team_ids.add(match.away_team_id)
            
            players = self.db.query(models.Player).filter(
                models.Player.team_id.in_(team_ids)
            ).all()
        
        projections = []
        for player in players:
            projection = self._calculate_projection(player, matches)
            projections.append(projection)
        
        # Sort by expected points
        projections.sort(key=lambda x: x["expected_points"], reverse=True)
        
        return projections
    
    def _calculate_projection(
        self,
        player: models.Player,
        matches: List[models.Match],
    ) -> Dict:
        """Calculate fantasy projection for a player.
        
        Args:
            player: Player model
            matches: List of matches for matchday
            
        Returns:
            Dictionary with projection data
        """
        # Get historical performance
        performances = self.db.query(models.PlayerPerformance).filter(
            models.PlayerPerformance.player_id == player.id
        ).all()
        
        # Calculate expected points
        if performances:
            avg_runs = sum(p.runs_scored for p in performances) / len(performances)
            avg_wickets = sum(p.wickets_taken for p in performances) / len(performances)
            avg_catches = sum(p.catches for p in performances) / len(performances)
        else:
            # Defaults based on role
            if player.role == models.PlayerRole.BATSMAN:
                avg_runs = 25.0
                avg_wickets = 0.0
                avg_catches = 0.5
            elif player.role == models.PlayerRole.BOWLER:
                avg_runs = 5.0
                avg_wickets = 1.5
                avg_catches = 0.3
            elif player.role == models.PlayerRole.ALL_ROUNDER:
                avg_runs = 20.0
                avg_wickets = 1.0
                avg_catches = 0.4
            else:
                avg_runs = 15.0
                avg_wickets = 0.0
                avg_catches = 0.6
        
        # Calculate fantasy points (simplified scoring system)
        # Runs: 1 point per run
        # Wickets: 20 points per wicket
        # Catches: 10 points per catch
        expected_points = (
            avg_runs * 1.0 +
            avg_wickets * 20.0 +
            avg_catches * 10.0
        )
        
        # Calculate percentiles (simplified)
        p10 = expected_points * 0.7
        p50 = expected_points
        p90 = expected_points * 1.3
        
        return {
            "player_id": player.id,
            "player_name": player.name,
            "team_id": player.team_id,
            "role": player.role.value,
            "expected_points": expected_points,
            "p10": p10,
            "p50": p50,
            "p90": p90,
            "avg_runs": avg_runs,
            "avg_wickets": avg_wickets,
            "avg_catches": avg_catches,
        }

