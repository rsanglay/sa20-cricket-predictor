"""DRS review probability model."""
from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.db import models


class DRSModel:
    """Predicts DRS overturn probability and net win% impact.
    
    Binary classifier predicting overturn probability given delivery type,
    line/length, batter stance, impact zone, umpire bias, and game context.
    """
    
    def __init__(self, db_session: Session):
        """Initialize DRS model.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
        # Simplified: In production, this would load a trained model
        self.overturn_threshold = 0.33  # Default threshold
    
    def predict_overturn_probability(
        self,
        delivery_type: str,
        line: str,
        length: str,
        batter_id: int,
        bowler_id: int,
        match_id: int,
        phase: Optional[str] = None,
        umpire_id: Optional[int] = None,
    ) -> Dict:
        """Predict DRS overturn probability.
        
        Args:
            delivery_type: Delivery type ('pace' or 'spin')
            line: Line of delivery ('off', 'middle', 'leg')
            length: Length of delivery ('full', 'good', 'short')
            batter_id: Batter ID
            bowler_id: Bowler ID
            match_id: Match ID
            phase: Match phase (optional)
            umpire_id: Umpire ID (optional)
            
        Returns:
            Dictionary with overturn probability and recommendation
        """
        # Get batter and bowler
        batter = self.db.get(models.Player, batter_id)
        bowler = self.db.get(models.Player, bowler_id)
        
        if not batter or not bowler:
            raise ValueError("Invalid batter or bowler ID")
        
        # Simplified model: calculate probability based on factors
        base_prob = 0.25  # Base overturn probability
        
        # Adjust for delivery type
        if delivery_type == "spin":
            base_prob += 0.05  # Spin reviews more likely to be overturned
        elif delivery_type == "pace":
            base_prob += 0.02
        
        # Adjust for line/length
        if line == "middle" and length == "full":
            base_prob += 0.10  # LBW appeals more likely to be overturned
        elif line == "leg" and length == "good":
            base_prob += 0.08
        
        # Adjust for batter stance
        if batter.batting_style == models.BattingStyle.LEFT_HAND:
            base_prob += 0.03  # Left-handers have different angles
        
        # Adjust for phase
        if phase == "death":
            base_prob += 0.05  # More reviews in death overs
        elif phase == "powerplay":
            base_prob -= 0.02  # Fewer reviews in powerplay
        
        # Adjust for bowler type
        if bowler.bowling_style:
            if "spin" in bowler.bowling_style.value:
                base_prob += 0.03
        
        # Clamp probability
        overturn_prob = max(0.0, min(1.0, base_prob))
        
        # Calculate net win% impact
        win_prob_impact = self._calculate_win_prob_impact(
            overturn_prob, match_id, batter_id, phase
        )
        
        # Recommendation
        should_review = overturn_prob > self.overturn_threshold
        
        return {
            "overturn_probability": overturn_prob,
            "should_review": should_review,
            "win_prob_impact": win_prob_impact,
            "threshold": self.overturn_threshold,
            "reasoning": self._generate_reasoning(overturn_prob, delivery_type, phase),
        }
    
    def _calculate_win_prob_impact(
        self,
        overturn_prob: float,
        match_id: int,
        batter_id: int,
        phase: Optional[str],
    ) -> float:
        """Calculate net win probability impact of review.
        
        Args:
            overturn_prob: Overturn probability
            match_id: Match ID
            batter_id: Batter ID
            phase: Match phase
            
        Returns:
            Win probability impact (percentage points)
        """
        # Simplified: Impact depends on phase and overturn probability
        if phase == "death":
            # Wicket in death overs is very valuable
            impact = overturn_prob * 8.0  # Up to 8% win prob increase
        elif phase == "powerplay":
            # Wicket in powerplay is valuable
            impact = overturn_prob * 5.0  # Up to 5% win prob increase
        else:
            # Wicket in middle overs is moderately valuable
            impact = overturn_prob * 3.0  # Up to 3% win prob increase
        
        # Adjust for review cost (losing a review)
        review_cost = 0.5  # Losing a review costs ~0.5% win probability
        
        net_impact = impact - (1 - overturn_prob) * review_cost
        
        return net_impact
    
    def _generate_reasoning(
        self,
        overturn_prob: float,
        delivery_type: str,
        phase: Optional[str],
    ) -> str:
        """Generate human-readable reasoning.
        
        Args:
            overturn_prob: Overturn probability
            delivery_type: Delivery type
            phase: Match phase
            
        Returns:
            Reasoning string
        """
        if overturn_prob > 0.5:
            return f"High probability of overturn ({overturn_prob:.1%}). Strongly recommend review."
        elif overturn_prob > self.overturn_threshold:
            return f"Moderate probability of overturn ({overturn_prob:.1%}). Recommend review."
        else:
            return f"Low probability of overturn ({overturn_prob:.1%}). Not recommended to review."
    
    def set_threshold(self, threshold: float) -> None:
        """Set review threshold.
        
        Args:
            threshold: New threshold (0-1)
        """
        self.overturn_threshold = max(0.0, min(1.0, threshold))

