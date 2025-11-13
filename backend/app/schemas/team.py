"""Team schema definitions."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class Team(BaseModel):
    id: int
    name: str
    short_name: str
    city: Optional[str] = None  # Changed from home_venue to city
    home_venue: Optional[str] = None  # Keep for backward compatibility
    founded_year: Optional[int] = None

    class Config:
        orm_mode = True


class TeamDetail(Team):
    squad_size: int
    squad_value: float
    avg_age: float
    international_players: int
    role_distribution: Dict[str, int]


class TeamComparison(BaseModel):
    teams: List[TeamDetail]
    comparison: Dict[str, List[float]]
