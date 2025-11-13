"""Prediction schema definitions."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class MatchPredictionRequest(BaseModel):
    home_team_id: int
    away_team_id: int
    venue_id: int
    overwrite_venue_avg_score: Optional[float] = None
    home_lineup_player_ids: Optional[List[int]] = None
    away_lineup_player_ids: Optional[List[int]] = None


class PlayerPerformancePrediction(BaseModel):
    player_id: int
    player_name: str
    predicted_runs: Optional[float] = None
    predicted_wickets: Optional[float] = None


class PredictedScores(BaseModel):
    home_score: int
    home_wickets: int
    away_score: int
    away_wickets: int
    first_innings_score: int
    first_innings_wickets: int
    second_innings_score: int
    second_innings_wickets: int
    first_team: str
    second_team: str


class MatchResult(BaseModel):
    winner: str
    result_type: str
    result_text: str
    margin: int


class TopRunScorer(BaseModel):
    player_id: int
    player_name: str
    predicted_runs: float


class TopWicketTaker(BaseModel):
    player_id: int
    player_name: str
    predicted_wickets: float


class ManOfTheMatch(BaseModel):
    player_id: int
    player_name: str
    team: str
    team_name: str
    predicted_runs: float
    predicted_wickets: float


class Top3RunScorer(BaseModel):
    player_id: int
    player_name: str
    predicted_runs: float


class Top3WicketTaker(BaseModel):
    player_id: int
    player_name: str
    predicted_wickets: float


class StartingXIPlayer(BaseModel):
    player_id: int
    player_name: str
    role: Optional[str] = None
    team_name: Optional[str] = None
    predicted_runs: float
    predicted_wickets: float


class MatchPredictionResponse(BaseModel):
    home_team: str
    away_team: str
    venue: str
    home_win_probability: float
    away_win_probability: float
    predicted_winner: str
    confidence: float
    key_factors: List[List[str | float]]
    toss_winner: str
    bat_first: str
    predicted_scores: PredictedScores
    match_result: MatchResult
    top_run_scorers: Dict[str, Optional[TopRunScorer]]
    top_3_run_scorers: Dict[str, List[Top3RunScorer]]
    top_wicket_takers: Dict[str, Optional[TopWicketTaker]]
    top_3_wicket_takers: Dict[str, List[Top3WicketTaker]]
    man_of_the_match: Optional[ManOfTheMatch] = None
    predicted_starting_xi: Dict[str, List[StartingXIPlayer]]


class Standing(BaseModel):
    team_id: int
    avg_position: float
    avg_points: float
    position_std: float
    playoff_probability: float
    championship_probability: float


class OrangeCap(BaseModel):
    player_id: int
    player_name: str
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    avg_runs: float
    total_runs_range: List[float]


class PurpleCap(BaseModel):
    player_id: int
    player_name: str
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    avg_wickets: float
    total_wickets_range: List[float]


class Champion(BaseModel):
    team_id: int
    team_name: Optional[str] = None
    win_probability: float


class MVP(BaseModel):
    player_id: int
    player_name: str
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    avg_runs: float
    avg_wickets: float
    mvp_score: float


class TeamOfTournamentPlayer(BaseModel):
    player_id: int
    player_name: str
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    role: str
    avg_runs: float
    avg_wickets: float
    performance_score: float


class UpsetTracker(BaseModel):
    team_id: int
    team_name: str
    expected_position: float
    actual_avg_position: float
    improvement: float


class SeasonPrediction(BaseModel):
    predicted_standings: List[Standing]
    playoff_probabilities: Dict[int, float]
    championship_probabilities: Dict[int, float]
    num_simulations: int
    orange_cap: Optional[OrangeCap] = None
    purple_cap: Optional[PurpleCap] = None
    champion: Optional[Champion] = None
    mvp: Optional[MVP] = None
    team_of_tournament: List[TeamOfTournamentPlayer] = []
    upset_tracker: List[UpsetTracker] = []


class SeasonSimulationRequest(BaseModel):
    num_simulations: int = 1000
    custom_xis: Optional[Dict[int, List[int]]] = None
