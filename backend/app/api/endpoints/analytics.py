"""Analytics endpoints exposing aggregated datasets."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/team-stats")
async def team_stats(
    competition: Optional[str] = None,
    season: Optional[str] = None,
    db: Session = Depends(get_db_session),
):
    service = AnalyticsService()
    data = service.get_team_stats(competition=competition, season=season)
    return data if data else []


@router.get("/player-stats")
async def player_stats(
    competition: Optional[str] = None,
    season: Optional[str] = None,
    team_name: Optional[str] = None,
    min_matches: Optional[int] = None,
    limit: Optional[int] = 100,
    db: Session = Depends(get_db_session),
):
    service = AnalyticsService()
    data = service.get_player_stats(
        competition=competition,
        season=season,
        team_name=team_name,
        min_matches=min_matches,
        limit=limit,
    )
    return data if data else []


@router.get("/match-scorecards")
async def match_scorecards(
    competition: Optional[str] = None,
    season: Optional[str] = None,
    team_name: Optional[str] = None,
    limit: Optional[int] = 50,
    db: Session = Depends(get_db_session),
):
    service = AnalyticsService()
    data = service.get_match_scorecards(
        competition=competition,
        season=season,
        team_name=team_name,
        limit=limit,
    )
    return data if data else []


@router.get("/leaderboards/batting")
async def batting_leaderboard(
    competition: Optional[str] = None,
    season: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db_session),
):
    service = AnalyticsService()
    data = service.get_batting_leaderboard(competition=competition, season=season, limit=limit)
    return data if data else []


@router.get("/leaderboards/bowling")
async def bowling_leaderboard(
    competition: Optional[str] = None,
    season: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db_session),
):
    service = AnalyticsService()
    data = service.get_bowling_leaderboard(competition=competition, season=season, limit=limit)
    return data if data else []


@router.get("/head-to-head")
async def head_to_head(
    team_a: str,
    team_b: str,
    competition: Optional[str] = None,
    db: Session = Depends(get_db_session),
):
    service = AnalyticsService()
    data = service.get_head_to_head(team_a, team_b, competition=competition)
    return data if data else {}


@router.get("/sa20-official-stats")
async def sa20_official_stats(
    stat_type: str = "batting",
    season: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db_session),
):
    """Get statistics scraped from SA20 official website."""
    service = AnalyticsService()
    data = service.get_sa20_official_stats(stat_type=stat_type, season=season, limit=limit)
    return data if data else []
