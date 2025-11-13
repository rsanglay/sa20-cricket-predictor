"""Team service layer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy.orm import Session, selectinload

from app.db import models
from app.core.cache import cache_result


@dataclass
class TeamService:
    db: Session

    @cache_result(expire=3600, key_prefix="teams")  # Cache for 1 hour
    def get_all_teams(self) -> List[Dict]:
        # Optimized query - no relationships needed for list view
        teams = self.db.query(models.Team).order_by(models.Team.name).all()
        return [self._to_dict(team) for team in teams]

    @cache_result(expire=1800, key_prefix="team_detail")  # Cache for 30 minutes
    def get_team_detail(self, team_id: int) -> Optional[Dict]:
        team = self.db.get(models.Team, team_id)
        if not team:
            return None
        
        # Optimized query with aggregation in database
        from sqlalchemy import func
        squad_stats = self.db.query(
            func.count(models.Player.id).label('squad_size'),
            func.coalesce(func.sum(models.Player.auction_price), 0).label('squad_value'),
            func.avg(models.Player.age).label('avg_age'),
            func.count(models.Player.id).filter(models.Player.country != "South Africa").label('international_players'),
        ).filter(models.Player.team_id == team_id).first()
        
        # Get role distribution in a single query
        role_dist = self.db.query(
            models.Player.role,
            func.count(models.Player.id).label('count')
        ).filter(models.Player.team_id == team_id).group_by(models.Player.role).all()
        
        role_distribution = {
            (role.value if hasattr(role, "value") else str(role)): count
            for role, count in role_dist
        }
        
        return {
            **self._to_dict(team),
            "squad_size": squad_stats.squad_size or 0,
            "squad_value": float(squad_stats.squad_value or 0),
            "avg_age": float(squad_stats.avg_age or 0),
            "international_players": squad_stats.international_players or 0,
            "role_distribution": role_distribution,
        }

    def compare_teams(self, team_ids: List[int]) -> Dict:
        teams = [self.get_team_detail(team_id) for team_id in team_ids if self.get_team_detail(team_id)]
        return {
            "teams": teams,
            "comparison": {
                "avg_squad_value": [team["squad_value"] for team in teams],
                "avg_age": [team["avg_age"] for team in teams],
                "international_players": [team["international_players"] for team in teams],
            },
        }

    def _role_distribution(self, players: List[models.Player]) -> Dict[str, int]:
        distribution: Dict[str, int] = {}
        for player in players:
            role = player.role.value if hasattr(player.role, "value") else player.role
            distribution[role] = distribution.get(role, 0) + 1
        return distribution

    def _to_dict(self, team: models.Team) -> Dict:
        return {
            "id": team.id,
            "name": team.name,
            "short_name": team.short_name,
            "city": team.city,  # Changed from home_venue to city
            "home_venue": team.city,  # Keep for backward compatibility
            "founded_year": team.founded_year,
        }
