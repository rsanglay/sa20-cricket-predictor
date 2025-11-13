"""Fantasy team optimizer service."""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.db import models
from app.services.fantasy.projections import FantasyProjectionService

try:
    import pulp
    PULP_AVAILABLE = True
except ImportError:
    PULP_AVAILABLE = False


class FantasyOptimizer:
    """Optimizes fantasy team selection under budget and constraint constraints."""
    
    def __init__(self, db_session: Session):
        """Initialize fantasy optimizer.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
        self.projection_service = FantasyProjectionService(db_session)
    
    def optimize_team(
        self,
        matchday: str,
        budget: float = 100.0,
        max_per_team: int = 7,
        min_batsmen: int = 3,
        min_bowlers: int = 3,
        min_all_rounders: int = 1,
        min_wicket_keepers: int = 1,
    ) -> Dict:
        """Optimize fantasy team selection.
        
        Args:
            matchday: Matchday identifier
            budget: Budget/credits available
            max_per_team: Maximum players from a single team
            min_batsmen: Minimum batsmen required
            min_bowlers: Minimum bowlers required
            min_all_rounders: Minimum all-rounders required
            min_wicket_keepers: Minimum wicket keepers required
            
        Returns:
            Dictionary with optimized team and projected points
        """
        # Get player projections
        projections = self.projection_service.get_player_projections(matchday)
        
        if not projections:
            raise ValueError(f"No players found for matchday {matchday}")
        
        # Use ILP optimization if available, otherwise fall back to greedy
        if PULP_AVAILABLE:
            return self._optimize_with_ilp(
                projections, budget, max_per_team, min_batsmen, min_bowlers, 
                min_all_rounders, min_wicket_keepers
            )
        else:
            return self._optimize_greedy(
                projections, budget, max_per_team, min_batsmen, min_bowlers,
                min_all_rounders, min_wicket_keepers
            )
    
    def _optimize_with_ilp(
        self,
        projections: List[Dict],
        budget: float,
        max_per_team: int,
        min_batsmen: int,
        min_bowlers: int,
        min_all_rounders: int,
        min_wicket_keepers: int,
    ) -> Dict:
        """Optimize using Integer Linear Programming."""
        # Create problem
        prob = pulp.LpProblem("FantasyTeamOptimization", pulp.LpMaximize)
        
        # Decision variables: x[i] = 1 if player i is selected, 0 otherwise
        n = len(projections)
        x = [pulp.LpVariable(f"x_{i}", cat='Binary') for i in range(n)]
        
        # Objective: maximize total expected points
        prob += pulp.lpSum([projections[i]["expected_points"] * x[i] for i in range(n)])
        
        # Constraints
        # 1. Budget constraint
        costs = [self._get_player_cost(projections[i]["player_id"]) for i in range(n)]
        prob += pulp.lpSum([costs[i] * x[i] for i in range(n)]) <= budget
        
        # 2. Exactly 11 players
        prob += pulp.lpSum([x[i] for i in range(n)]) == 11
        
        # 3. Role constraints
        batsmen_indices = [i for i in range(n) if projections[i]["role"] == "batsman"]
        bowlers_indices = [i for i in range(n) if projections[i]["role"] == "bowler"]
        all_rounders_indices = [i for i in range(n) if projections[i]["role"] == "all_rounder"]
        wicket_keepers_indices = [i for i in range(n) if projections[i]["role"] == "wicket_keeper"]
        
        if batsmen_indices:
            prob += pulp.lpSum([x[i] for i in batsmen_indices]) >= min_batsmen
        if bowlers_indices:
            prob += pulp.lpSum([x[i] for i in bowlers_indices]) >= min_bowlers
        if all_rounders_indices:
            prob += pulp.lpSum([x[i] for i in all_rounders_indices]) >= min_all_rounders
        if wicket_keepers_indices:
            prob += pulp.lpSum([x[i] for i in wicket_keepers_indices]) >= min_wicket_keepers
        
        # 4. Max players per team
        team_ids = set(projections[i]["team_id"] for i in range(n))
        for team_id in team_ids:
            team_indices = [i for i in range(n) if projections[i]["team_id"] == team_id]
            if team_indices:
                prob += pulp.lpSum([x[i] for i in team_indices]) <= max_per_team
        
        # Solve
        prob.solve(pulp.PULP_CBC_CMD(msg=0))  # Suppress solver output
        
        # Extract solution
        selected_indices = [i for i in range(n) if x[i].varValue == 1]
        selected_team = [projections[i] for i in selected_indices]
        
        total_cost = sum(costs[i] for i in selected_indices)
        total_points = sum(projections[i]["expected_points"] for i in selected_indices)
        
        # Calculate role and team counts
        role_counts = {
            "batsman": sum(1 for i in selected_indices if projections[i]["role"] == "batsman"),
            "bowler": sum(1 for i in selected_indices if projections[i]["role"] == "bowler"),
            "all_rounder": sum(1 for i in selected_indices if projections[i]["role"] == "all_rounder"),
            "wicket_keeper": sum(1 for i in selected_indices if projections[i]["role"] == "wicket_keeper"),
        }
        
        team_counts = {}
        for i in selected_indices:
            team_id = projections[i]["team_id"]
            team_counts[team_id] = team_counts.get(team_id, 0) + 1
        
        # Select captain and vice-captain
        selected_team.sort(key=lambda x: x["expected_points"], reverse=True)
        captain = selected_team[0] if selected_team else None
        vice_captain = selected_team[1] if len(selected_team) > 1 else None
        
        # Captain gets 2x points, vice-captain gets 1.5x
        if captain:
            total_points += captain["expected_points"]
        if vice_captain:
            total_points += vice_captain["expected_points"] * 0.5
        
        return {
            "team": selected_team,
            "captain": captain,
            "vice_captain": vice_captain,
            "total_points": total_points,
            "total_cost": total_cost,
            "budget_used": total_cost,
            "budget_remaining": budget - total_cost,
            "role_counts": role_counts,
            "team_counts": team_counts,
            "optimization_method": "ILP",
        }
    
    def _optimize_greedy(
        self,
        projections: List[Dict],
        budget: float,
        max_per_team: int,
        min_batsmen: int,
        min_bowlers: int,
        min_all_rounders: int,
        min_wicket_keepers: int,
    ) -> Dict:
        """Fallback greedy optimization."""
        selected_team = []
        total_cost = 0.0
        total_points = 0.0
        team_counts = {}
        role_counts = {
            "batsman": 0,
            "bowler": 0,
            "all_rounder": 0,
            "wicket_keeper": 0,
        }
        
        # Sort by points per cost (efficiency)
        projections.sort(
            key=lambda x: x["expected_points"] / max(self._get_player_cost(x["player_id"]), 1.0),
            reverse=True
        )
        
        # Select players
        for projection in projections:
            player_id = projection["player_id"]
            team_id = projection["team_id"]
            role = projection["role"]
            cost = self._get_player_cost(player_id)
            
            # Check constraints
            if total_cost + cost > budget:
                continue
            
            if team_counts.get(team_id, 0) >= max_per_team:
                continue
            
            if role == "batsman" and role_counts["batsman"] >= 6:
                continue
            if role == "bowler" and role_counts["bowler"] >= 6:
                continue
            if role == "all_rounder" and role_counts["all_rounder"] >= 4:
                continue
            if role == "wicket_keeper" and role_counts["wicket_keeper"] >= 2:
                continue
            
            # Add player
            selected_team.append(projection)
            total_cost += cost
            total_points += projection["expected_points"]
            team_counts[team_id] = team_counts.get(team_id, 0) + 1
            role_counts[role] = role_counts.get(role, 0) + 1
            
            # Check if we have enough players
            if len(selected_team) >= 11:
                break
        
        # Check if constraints are met
        if role_counts["batsman"] < min_batsmen:
            raise ValueError(f"Insufficient batsmen: {role_counts['batsman']} < {min_batsmen}")
        if role_counts["bowler"] < min_bowlers:
            raise ValueError(f"Insufficient bowlers: {role_counts['bowler']} < {min_bowlers}")
        if role_counts["all_rounder"] < min_all_rounders:
            raise ValueError(f"Insufficient all-rounders: {role_counts['all_rounder']} < {min_all_rounders}")
        if role_counts["wicket_keeper"] < min_wicket_keepers:
            raise ValueError(f"Insufficient wicket keepers: {role_counts['wicket_keeper']} < {min_wicket_keepers}")
        
        # Select captain and vice-captain (highest point players)
        selected_team.sort(key=lambda x: x["expected_points"], reverse=True)
        captain = selected_team[0] if selected_team else None
        vice_captain = selected_team[1] if len(selected_team) > 1 else None
        
        # Captain gets 2x points, vice-captain gets 1.5x
        if captain:
            total_points += captain["expected_points"]  # Already counted, add bonus
        if vice_captain:
            total_points += vice_captain["expected_points"] * 0.5  # 1.5x total
        
        return {
            "team": selected_team,
            "captain": captain,
            "vice_captain": vice_captain,
            "total_points": total_points,
            "total_cost": total_cost,
            "budget_used": total_cost,
            "budget_remaining": budget - total_cost,
            "role_counts": role_counts,
            "team_counts": team_counts,
            "optimization_method": "greedy",
        }
    
    def _get_player_cost(self, player_id: int) -> float:
        """Get player cost/credits.
        
        Args:
            player_id: Player ID
            
        Returns:
            Player cost
        """
        player = self.db.get(models.Player, player_id)
        if player and player.auction_price:
            # Convert auction price to credits (simplified)
            return player.auction_price / 1000000.0  # Scale down
        else:
            # Default cost based on role
            return 8.0  # Default credit cost

