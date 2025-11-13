"""Analysis output schemas."""
from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel


class SquadGap(BaseModel):
    role: str
    needed: int


class SquadGaps(BaseModel):
    team_id: int
    gaps: List[SquadGap]
    recommendations: List[str]


class OptimalXI(BaseModel):
    team_id: int
    opponent_id: int
    venue_id: int
    players: List[int]


class PlayerMatchup(BaseModel):
    batsman_id: int
    bowler_id: int
    matches: int
    runs: int
    wickets: int
    batting_average: float
