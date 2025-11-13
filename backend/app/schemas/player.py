"""Player schema definitions."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class Player(BaseModel):
    id: int
    team_id: Optional[int] = None
    name: str
    role: str
    batting_style: Optional[str] = None
    bowling_style: Optional[str] = None
    country: str
    age: int
    birth_date: Optional[str] = None
    auction_price: Optional[float] = None
    image_url: Optional[str] = None
    has_projection: Optional[bool] = None

    class Config:
        orm_mode = True


class MatchPerformance(BaseModel):
    match_id: int
    date: str
    opponent: str
    runs: int
    balls_faced: int
    wickets: int


class CareerStats(BaseModel):
    matches_played: int
    runs_scored: int
    batting_average: float
    strike_rate: float
    highest_score: int
    fours: int
    sixes: int
    fifties: int
    hundreds: int
    wickets_taken: int
    bowling_average: Optional[float] = None
    economy_rate: Optional[float] = None
    best_bowling_figures: Optional[str] = None
    five_wickets: int


class RecentForm(BaseModel):
    last_5_matches: List[MatchPerformance]
    trend: str


class SeasonBattingStats(BaseModel):
    matches: int
    runs: int
    highest_score: int
    average: float
    strike_rate: float
    balls_faced: int
    fours: int
    sixes: int


class SeasonBowlingStats(BaseModel):
    matches: int
    balls: int
    runs: int
    wickets: int
    average: float
    economy: float
    strike_rate: float
    best_figures: Optional[str] = None
    five_wickets: int


class SeasonStats(BaseModel):
    season: int
    team: str
    batting: SeasonBattingStats
    bowling: SeasonBowlingStats


class PlayerDetail(Player):
    international_caps: int
    career_stats: CareerStats
    season_stats: List[SeasonStats]
    recent_form: RecentForm


class PlayerStats(BaseModel):
    player_id: int
    season: Optional[int] = None
    batting: dict
    bowling: Optional[dict]
