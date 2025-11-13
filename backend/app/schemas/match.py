"""Match schema definitions."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Match(BaseModel):
    id: int
    home_team_id: int
    away_team_id: int
    venue_id: int
    match_date: str
    season: Optional[int] = None
    winner_id: Optional[int] = None
    margin: Optional[str] = None
    match_number: Optional[int] = None
    home_team_name: Optional[str] = None
    away_team_name: Optional[str] = None
    venue_name: Optional[str] = None

    class Config:
        orm_mode = True


class MatchDetail(Match):
    season: int
    winner_id: Optional[int] = None
    margin: Optional[str] = None


class HeadToHead(BaseModel):
    team1_id: int
    team2_id: int
    total_matches: int
    team1_wins: int
    team2_wins: int
    ties: int
