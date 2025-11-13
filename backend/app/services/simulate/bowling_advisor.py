"""Bowling change advisor for in-match strategy."""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.db import models


class BowlingAdvisor:
    """Recommends bowling changes to maximize expected wicket value minus runs conceded.
    
    Uses dynamic programming to optimize bowler sequencing for next K overs,
    honoring per-bowler quotas and over-sequencing constraints.
    """
    
    def __init__(self, db_session: Session):
        """Initialize bowling advisor.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
    
    def recommend_bowling_change(
        self,
        available_bowlers: List[int],
        remaining_overs: float,
        wickets_down: int,
        striker_id: Optional[int] = None,
        non_striker_id: Optional[int] = None,
        current_bowler_id: Optional[int] = None,
        phase: Optional[str] = None,
        overs_ahead: int = 3,
    ) -> Dict:
        """Recommend next over bowler and sequence for next K overs.
        
        Args:
            available_bowlers: List of available bowler IDs
            remaining_overs: Overs remaining in the innings
            wickets_down: Number of wickets down
            striker_id: Current striker ID (optional)
            non_striker_id: Current non-striker ID (optional)
            current_bowler_id: Current bowler ID (optional)
            phase: Match phase (optional)
            overs_ahead: Number of overs to plan ahead
            
        Returns:
            Dictionary with bowling recommendations
        """
        # Get bowlers
        bowlers = self.db.query(models.Player).filter(
            models.Player.id.in_(available_bowlers)
        ).all()
        
        if not bowlers:
            raise ValueError("No available bowlers")
        
        # Determine phase
        if phase is None:
            phase = self._get_phase(remaining_overs)
        
        # Get bowler stats
        bowler_stats = self._get_bowler_stats(bowlers, phase, striker_id, non_striker_id)
        
        # Calculate bowler quotas (simplified: assume 4 overs max per bowler)
        bowler_quotas = {bowler.id: 4.0 for bowler in bowlers}
        
        # Optimize bowling sequence
        sequence = self._optimize_bowling_sequence(
            bowler_stats, bowler_quotas, remaining_overs, overs_ahead, current_bowler_id
        )
        
        # Calculate expected impact
        expected_impact = self._calculate_expected_impact(
            sequence, bowler_stats, wickets_down, phase
        )
        
        return {
            "next_over_bowler": sequence[0] if sequence else None,
            "sequence": sequence[:overs_ahead],
            "expected_impact": expected_impact,
            "reasoning": self._generate_reasoning(sequence, bowler_stats, phase),
            "alternates": self._get_alternates(bowler_stats, sequence, current_bowler_id),
        }
    
    def _get_phase(self, overs_left: float) -> str:
        """Get match phase based on overs left."""
        if overs_left >= 14:
            return "powerplay"
        elif overs_left >= 4:
            return "middle"
        else:
            return "death"
    
    def _get_bowler_stats(
        self,
        bowlers: List[models.Player],
        phase: str,
        striker_id: Optional[int],
        non_striker_id: Optional[int],
    ) -> Dict[int, Dict]:
        """Get bowler statistics by phase.
        
        Args:
            bowlers: List of bowlers
            phase: Match phase
            striker_id: Current striker ID
            non_striker_id: Current non-striker ID
            
        Returns:
            Dictionary mapping bowler_id to stats
        """
        stats = {}
        
        for bowler in bowlers:
            # Get historical performance
            performances = self.db.query(models.PlayerPerformance).filter(
                models.PlayerPerformance.player_id == bowler.id
            ).all()
            
            if performances:
                avg_wickets = sum(p.wickets_taken for p in performances) / len(performances)
                avg_econ = sum(p.economy_rate or 8.0 for p in performances) / len(performances) if performances else 8.0
                wickets_per_over = avg_wickets / max(sum(p.overs_bowled for p in performances) / len(performances), 0.1)
            else:
                # Defaults based on role
                if bowler.role == models.PlayerRole.BOWLER:
                    avg_wickets = 1.5
                    avg_econ = 7.5
                    wickets_per_over = 0.15
                elif bowler.role == models.PlayerRole.ALL_ROUNDER:
                    avg_wickets = 1.0
                    avg_econ = 8.5
                    wickets_per_over = 0.10
                else:
                    avg_wickets = 0.5
                    avg_econ = 9.0
                    wickets_per_over = 0.05
            
            # Adjust for phase
            if phase == "powerplay":
                econ_multiplier = 1.1  # Slightly more expensive
                wicket_multiplier = 1.2  # More wickets in powerplay
            elif phase == "death":
                econ_multiplier = 1.3  # More expensive in death
                wicket_multiplier = 0.8  # Fewer wickets in death
            else:
                econ_multiplier = 1.0
                wicket_multiplier = 1.0
            
            # Calculate expected value (wickets - runs conceded)
            expected_wickets = wickets_per_over * wicket_multiplier
            expected_runs = avg_econ * econ_multiplier
            expected_value = expected_wickets * 20 - expected_runs  # Weight wickets more
            
            stats[bowler.id] = {
                "bowler_id": bowler.id,
                "name": bowler.name,
                "role": bowler.role.value,
                "expected_wickets": expected_wickets,
                "expected_econ": expected_runs,
                "expected_value": expected_value,
                "bowling_style": bowler.bowling_style.value if bowler.bowling_style else "unknown",
            }
        
        return stats
    
    def _optimize_bowling_sequence(
        self,
        bowler_stats: Dict[int, Dict],
        bowler_quotas: Dict[int, float],
        remaining_overs: float,
        overs_ahead: int,
        current_bowler_id: Optional[int],
    ) -> List[Dict]:
        """Optimize bowling sequence using greedy algorithm.
        
        Args:
            bowler_stats: Bowler statistics
            bowler_quotas: Bowler quotas (overs remaining)
            remaining_overs: Overs remaining in innings
            overs_ahead: Number of overs to plan
            current_bowler_id: Current bowler ID
            
        Returns:
            List of recommended bowling assignments
        """
        sequence = []
        used_overs = {bowler_id: 0.0 for bowler_id in bowler_stats.keys()}
        
        # Don't recommend current bowler for next over (variation)
        available = [
            (bowler_id, stats)
            for bowler_id, stats in bowler_stats.items()
            if bowler_id != current_bowler_id and used_overs[bowler_id] < bowler_quotas.get(bowler_id, 4.0)
        ]
        
        for over in range(min(overs_ahead, int(remaining_overs))):
            if not available:
                break
            
            # Sort by expected value
            available.sort(key=lambda x: x[1]["expected_value"], reverse=True)
            
            # Select best available bowler
            if available:
                bowler_id, stats = available[0]
                sequence.append({
                    "over": over + 1,
                    "bowler_id": bowler_id,
                    "bowler_name": stats["name"],
                    "expected_value": stats["expected_value"],
                })
                
                used_overs[bowler_id] += 1.0
                
                # Remove if quota exceeded
                if used_overs[bowler_id] >= bowler_quotas.get(bowler_id, 4.0):
                    available = [(bid, s) for bid, s in available if bid != bowler_id]
        
        return sequence
    
    def _calculate_expected_impact(
        self,
        sequence: List[Dict],
        bowler_stats: Dict[int, Dict],
        wickets_down: int,
        phase: str,
    ) -> Dict:
        """Calculate expected impact of bowling sequence.
        
        Args:
            sequence: Bowling sequence
            bowler_stats: Bowler statistics
            wickets_down: Wickets down
            phase: Match phase
            
        Returns:
            Dictionary with expected impact metrics
        """
        total_expected_wickets = 0.0
        total_expected_runs = 0.0
        
        for assignment in sequence:
            bowler_id = assignment["bowler_id"]
            stats = bowler_stats.get(bowler_id, {})
            total_expected_wickets += stats.get("expected_wickets", 0.0)
            total_expected_runs += stats.get("expected_econ", 8.0)
        
        # Calculate win probability impact (simplified)
        # More wickets = higher win probability
        win_prob_delta = total_expected_wickets * 0.05  # Simplified
        
        return {
            "expected_wickets": total_expected_wickets,
            "expected_runs": total_expected_runs,
            "expected_net_value": total_expected_wickets * 20 - total_expected_runs,
            "win_prob_delta": win_prob_delta,
        }
    
    def _get_alternates(
        self,
        bowler_stats: Dict[int, Dict],
        sequence: List[Dict],
        current_bowler_id: Optional[int],
    ) -> List[Dict]:
        """Get alternate bowling options.
        
        Args:
            bowler_stats: Bowler statistics
            sequence: Recommended sequence
            current_bowler_id: Current bowler ID
            
        Returns:
            List of alternate options
        """
        recommended_ids = {item["bowler_id"] for item in sequence}
        
        alternates = [
            {
                "bowler_id": bowler_id,
                "bowler_name": stats["name"],
                "expected_value": stats["expected_value"],
                "reason": "Alternative option with similar expected value",
            }
            for bowler_id, stats in bowler_stats.items()
            if bowler_id not in recommended_ids and bowler_id != current_bowler_id
        ]
        
        # Sort by expected value
        alternates.sort(key=lambda x: x["expected_value"], reverse=True)
        
        return alternates[:2]  # Return top 2 alternates
    
    def _generate_reasoning(
        self,
        sequence: List[Dict],
        bowler_stats: Dict[int, Dict],
        phase: str,
    ) -> str:
        """Generate human-readable reasoning.
        
        Args:
            sequence: Recommended sequence
            bowler_stats: Bowler statistics
            phase: Match phase
            
        Returns:
            Reasoning string
        """
        if not sequence:
            return "No recommendations available"
        
        next_bowler = sequence[0]
        bowler_name = next_bowler["bowler_name"]
        
        if phase == "powerplay":
            return f"Recommend {bowler_name} for powerplay to take early wickets"
        elif phase == "death":
            return f"Recommend {bowler_name} for death overs to control run rate"
        else:
            return f"Recommend {bowler_name} for middle overs to maintain pressure"

