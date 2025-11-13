"""Batting order optimizer for in-match strategy."""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.db import models


class BattingOrderOptimizer:
    """Optimizes batting order to maximize expected runs wicket-by-wicket.
    
    Uses per-pair outcomes and phase-aware SR/dismissal rates to compute
    E[runs] for positions 3-7 under fall-of-wickets states.
    """
    
    def __init__(self, db_session: Session):
        """Initialize batting order optimizer.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
    
    def optimize_batting_order(
        self,
        xi_player_ids: List[int],
        wickets_fallen: int,
        overs_left: float,
        striker_id: Optional[int] = None,
        non_striker_id: Optional[int] = None,
        venue_id: Optional[int] = None,
    ) -> Dict:
        """Suggest optimal batting order for remaining wickets.
        
        Args:
            xi_player_ids: List of player IDs in the XI
            wickets_fallen: Number of wickets fallen
            overs_left: Overs remaining in the innings
            striker_id: Current striker ID (optional)
            non_striker_id: Current non-striker ID (optional)
            venue_id: Venue ID (optional)
            
        Returns:
            Dictionary with recommended batting order and expected runs
        """
        # Get players
        players = self.db.query(models.Player).filter(
            models.Player.id.in_(xi_player_ids)
        ).all()
        
        if len(players) < 2:
            raise ValueError("Need at least 2 players in XI")
        
        # Determine phase
        phase = self._get_phase(overs_left)
        
        # Get player stats by phase
        player_stats = self._get_player_phase_stats(players, phase)
        
        # Current batsmen
        current_batsmen = []
        if striker_id:
            current_batsmen.append(striker_id)
        if non_striker_id and non_striker_id != striker_id:
            current_batsmen.append(non_striker_id)
        
        # Remaining positions to fill
        remaining_positions = 11 - wickets_fallen - len(current_batsmen)
        
        # Optimize order for remaining positions
        recommended_order = self._compute_optimal_order(
            players, player_stats, current_batsmen, remaining_positions, phase
        )
        
        # Calculate expected runs
        expected_runs = self._estimate_expected_runs(
            recommended_order, player_stats, overs_left, phase
        )
        
        return {
            "recommended_order": recommended_order,
            "expected_runs": expected_runs,
            "phase": phase,
            "reasoning": self._generate_reasoning(recommended_order, phase),
        }
    
    def _get_phase(self, overs_left: float) -> str:
        """Get match phase based on overs left.
        
        Args:
            overs_left: Overs remaining
            
        Returns:
            Phase name: 'powerplay', 'middle', or 'death'
        """
        if overs_left >= 14:  # First 6 overs
            return "powerplay"
        elif overs_left >= 4:  # Overs 7-16
            return "middle"
        else:  # Overs 17-20
            return "death"
    
    def _get_player_phase_stats(
        self,
        players: List[models.Player],
        phase: str,
    ) -> Dict[int, Dict]:
        """Get player statistics by phase.
        
        Args:
            players: List of players
            phase: Match phase
            
        Returns:
            Dictionary mapping player_id to phase stats
        """
        stats = {}
        
        for player in players:
            # Simplified: use player role and historical performance
            # In production, this would query actual phase-specific stats
            performances = self.db.query(models.PlayerPerformance).filter(
                models.PlayerPerformance.player_id == player.id
            ).all()
            
            if performances:
                avg_runs = sum(p.runs_scored for p in performances) / len(performances)
                avg_sr = sum(p.strike_rate or 120 for p in performances) / len(performances) if performances else 120.0
                dismissal_rate = len([p for p in performances if p.runs_scored == 0]) / len(performances)
            else:
                # Defaults based on role
                if player.role == models.PlayerRole.BATSMAN:
                    avg_runs = 25.0
                    avg_sr = 130.0
                    dismissal_rate = 0.3
                elif player.role == models.PlayerRole.ALL_ROUNDER:
                    avg_runs = 20.0
                    avg_sr = 140.0
                    dismissal_rate = 0.35
                else:
                    avg_runs = 15.0
                    avg_sr = 150.0
                    dismissal_rate = 0.4
            
            # Adjust for phase
            if phase == "powerplay":
                sr_multiplier = 0.9  # Slightly conservative
                dismissal_multiplier = 1.1
            elif phase == "death":
                sr_multiplier = 1.2  # More aggressive
                dismissal_multiplier = 1.2
            else:
                sr_multiplier = 1.0
                dismissal_multiplier = 1.0
            
            stats[player.id] = {
                "player_id": player.id,
                "name": player.name,
                "role": player.role.value,
                "avg_runs": avg_runs,
                "strike_rate": avg_sr * sr_multiplier,
                "dismissal_rate": dismissal_rate * dismissal_multiplier,
                "handedness": player.batting_style.value,
            }
        
        return stats
    
    def _compute_optimal_order(
        self,
        players: List[models.Player],
        player_stats: Dict[int, Dict],
        current_batsmen: List[int],
        remaining_positions: int,
        phase: str,
    ) -> List[Dict]:
        """Compute optimal batting order.
        
        Args:
            players: List of players
            player_stats: Player statistics by phase
            current_batsmen: Current batsmen IDs
            remaining_positions: Number of positions to fill
            phase: Match phase
            
        Returns:
            List of recommended batting order entries
        """
        # Sort players by expected value (runs * SR / dismissal_rate)
        available_players = [p for p in players if p.id not in current_batsmen]
        
        player_values = []
        for player in available_players:
            stats = player_stats.get(player.id, {})
            expected_value = (
                stats.get("avg_runs", 20) *
                stats.get("strike_rate", 120) /
                max(stats.get("dismissal_rate", 0.3), 0.1)
            )
            player_values.append((player.id, expected_value, stats))
        
        # Sort by expected value (descending)
        player_values.sort(key=lambda x: x[1], reverse=True)
        
        # Recommend order
        recommended = []
        for i, (player_id, value, stats) in enumerate(player_values[:remaining_positions]):
            recommended.append({
                "position": len(current_batsmen) + i + 1,
                "player_id": player_id,
                "player_name": stats.get("name", ""),
                "expected_value": value,
                "reason": self._get_recommendation_reason(stats, phase),
            })
        
        return recommended
    
    def _estimate_expected_runs(
        self,
        order: List[Dict],
        player_stats: Dict[int, Dict],
        overs_left: float,
        phase: str,
    ) -> float:
        """Estimate expected runs from recommended order.
        
        Args:
            order: Recommended batting order
            player_stats: Player statistics
            overs_left: Overs remaining
            phase: Match phase
            
        Returns:
            Expected runs
        """
        total_expected = 0.0
        balls_remaining = int(overs_left * 6)
        
        for entry in order:
            player_id = entry["player_id"]
            stats = player_stats.get(player_id, {})
            
            # Estimate runs per ball
            sr = stats.get("strike_rate", 120) / 100.0
            dismissal_rate = stats.get("dismissal_rate", 0.3)
            
            # Expected balls faced before dismissal
            expected_balls = 1.0 / max(dismissal_rate, 0.01)
            expected_balls = min(expected_balls, balls_remaining)
            
            # Expected runs
            expected_runs = expected_balls * sr
            total_expected += expected_runs
            
            balls_remaining -= int(expected_balls)
            if balls_remaining <= 0:
                break
        
        return total_expected
    
    def _get_recommendation_reason(self, stats: Dict, phase: str) -> str:
        """Get reasoning for recommendation.
        
        Args:
            stats: Player statistics
            phase: Match phase
            
        Returns:
            Reasoning string
        """
        role = stats.get("role", "")
        sr = stats.get("strike_rate", 120)
        
        if phase == "death" and sr > 150:
            return "High strike rate suitable for death overs"
        elif phase == "powerplay" and role == "batsman":
            return "Stable batsman for powerplay"
        else:
            return "Balanced option for middle overs"
    
    def _generate_reasoning(self, order: List[Dict], phase: str) -> str:
        """Generate human-readable reasoning.
        
        Args:
            order: Recommended batting order
            phase: Match phase
            
        Returns:
            Reasoning string
        """
        if phase == "death":
            return "Focusing on high strike rate players for aggressive scoring in death overs"
        elif phase == "powerplay":
            return "Prioritizing stable batsmen to build foundation in powerplay"
        else:
            return "Balancing aggression and stability for middle overs"

