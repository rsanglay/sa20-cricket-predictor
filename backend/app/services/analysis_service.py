"""Analytical service utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from sqlalchemy.orm import Session

from app.db import models
from app.ml.models.squad_optimizer import SquadOptimizer


@dataclass
class AnalysisService:
    db: Session

    def analyze_squad_gaps(self, team_id: int) -> Dict:
        squad = (
            self.db.query(models.Player)
            .filter(models.Player.team_id == team_id)
            .all()
        )
        role_counts: Dict[str, int] = {}
        for player in squad:
            role = player.role.value if hasattr(player.role, "value") else player.role
            role_counts[role] = role_counts.get(role, 0) + 1
        gaps: List[Dict[str, int]] = []
        if role_counts.get("batsman", 0) < 5:
            gaps.append({"role": "batsman", "needed": 5 - role_counts.get("batsman", 0)})
        if role_counts.get("bowler", 0) < 5:
            gaps.append({"role": "bowler", "needed": 5 - role_counts.get("bowler", 0)})
        if role_counts.get("all_rounder", 0) < 2:
            gaps.append({"role": "all_rounder", "needed": 2 - role_counts.get("all_rounder", 0)})
        return {
            "team_id": team_id,
            "gaps": gaps,
            "recommendations": [f"Recruit {gap['needed']} {gap['role']}" for gap in gaps],
        }

    def generate_optimal_xi(self, team_id: int, opponent_id: int, venue_id: int) -> Dict:
        squad = (
            self.db.query(models.Player)
            .filter(models.Player.team_id == team_id)
            .all()
        )
        squad_ids = [player.id for player in squad][:11]
        return {
            "team_id": team_id,
            "opponent_id": opponent_id,
            "venue_id": venue_id,
            "players": squad_ids,
        }

    def get_player_matchup(self, batsman_id: int, bowler_id: int) -> Dict:
        performances = (
            self.db.query(models.PlayerPerformance)
            .filter(models.PlayerPerformance.player_id == batsman_id)
            .all()
        )
        return {
            "batsman_id": batsman_id,
            "bowler_id": bowler_id,
            "matches": len(performances),
            "runs": sum(p.runs_scored for p in performances),
            "wickets": sum(p.wickets_taken for p in performances if p.player_id == bowler_id),
            "batting_average": 0.0,
        }

    def optimize_fantasy_team(
        self, budget: float, required_positions: Dict[str, int], available_players: List[int]
    ) -> Dict:
        players = [self.db.get(models.Player, pid) for pid in available_players]
        player_dicts = [
            {
                "player_id": player.id,
                "role": player.role.value if hasattr(player.role, "value") else player.role,
                "auction_price": player.auction_price or 0,
                "country": player.country,
                "batting_impact": 0,
                "bowling_impact": 0,
                "international_caps": player.international_caps,
                "age": player.age,
            }
            for player in players
            if player
        ]
        optimizer = SquadOptimizer(budget=budget)
        return optimizer.optimize_squad(player_dicts)
