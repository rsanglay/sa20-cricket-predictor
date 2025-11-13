"""Fantasy differential picks service."""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.fantasy.projections import FantasyProjectionService


class DifferentialService:
    """Service for identifying low-ownership, high-expected-value fantasy picks."""
    
    def __init__(self, db_session: Session):
        """Initialize differential service.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
        self.projection_service = FantasyProjectionService(db_session)
        # In production, this would accept external ownership data
        self.ownership_data: Dict[int, float] = {}  # player_id -> ownership %
    
    def get_differentials(
        self,
        matchday: str,
        max_ownership: float = 0.20,  # 20% ownership threshold
        min_expected_points: float = 30.0,
        limit: int = 10,
    ) -> List[Dict]:
        """Get differential picks (low ownership, high expected value).
        
        Args:
            matchday: Matchday identifier
            max_ownership: Maximum ownership percentage
            min_expected_points: Minimum expected points
            limit: Maximum number of picks to return
            
        Returns:
            List of differential picks
        """
        # Get player projections
        projections = self.projection_service.get_player_projections(matchday)
        
        # Filter by ownership and expected points
        differentials = []
        for projection in projections:
            player_id = projection["player_id"]
            ownership = self._get_ownership(player_id)
            expected_points = projection["expected_points"]
            
            if ownership <= max_ownership and expected_points >= min_expected_points:
                # Calculate value (expected points / ownership)
                value = expected_points / max(ownership, 0.01)
                
                differentials.append({
                    **projection,
                    "ownership": ownership,
                    "value": value,
                })
        
        # Sort by value (descending)
        differentials.sort(key=lambda x: x["value"], reverse=True)
        
        return differentials[:limit]
    
    def _get_ownership(self, player_id: int) -> float:
        """Get player ownership percentage.
        
        Args:
            player_id: Player ID
            
        Returns:
            Ownership percentage (0-1)
        """
        # In production, this would query external ownership data
        # For now, return simulated ownership
        if player_id in self.ownership_data:
            return self.ownership_data[player_id]
        else:
            # Simulate ownership (lower for less popular players)
            return random.uniform(0.05, 0.40)  # 5-40% ownership
    
    def update_ownership(self, player_id: int, ownership: float) -> None:
        """Update player ownership data.
        
        Args:
            player_id: Player ID
            ownership: Ownership percentage (0-1)
        """
        self.ownership_data[player_id] = max(0.0, min(1.0, ownership))

