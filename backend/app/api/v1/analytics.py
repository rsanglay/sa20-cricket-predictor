"""Analytics endpoints v1."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/batting-leaderboard")
async def batting_leaderboard(
    season: Optional[int] = Query(None, description="Season year"),
    competition: Optional[str] = Query(None, description="Competition name"),
    limit: int = Query(10, ge=1, le=100, description="Number of results to return"),
    db: Session = Depends(get_db),
):
    """Get batting leaderboard."""
    service = AnalyticsService()
    data = service.get_batting_leaderboard(competition=competition, season=str(season) if season else None, limit=limit)
    return data if data else []


@router.get("/bowling-leaderboard")
async def bowling_leaderboard(
    season: Optional[int] = Query(None, description="Season year"),
    competition: Optional[str] = Query(None, description="Competition name"),
    limit: int = Query(10, ge=1, le=100, description="Number of results to return"),
    db: Session = Depends(get_db),
):
    """Get bowling leaderboard."""
    service = AnalyticsService()
    data = service.get_bowling_leaderboard(competition=competition, season=str(season) if season else None, limit=limit)
    return data if data else []


@router.get("/head-to-head")
async def head_to_head(
    team_a: str = Query(..., description="First team name or ID"),
    team_b: str = Query(..., description="Second team name or ID"),
    competition: Optional[str] = Query(None, description="Competition name"),
    db: Session = Depends(get_db),
):
    """Get head-to-head statistics between two teams."""
    service = AnalyticsService()
    data = service.get_head_to_head(team_a, team_b, competition=competition)
    return data if data else {}


# Additional analytics endpoints for compatibility
@router.get("/team-stats")
async def team_stats(
    competition: Optional[str] = Query(None, description="Competition name"),
    season: Optional[str] = Query(None, description="Season"),
    db: Session = Depends(get_db),
):
    """Get team statistics."""
    service = AnalyticsService()
    data = service.get_team_stats(competition=competition, season=season)
    return data if data else []


@router.get("/player-stats")
async def player_stats(
    competition: Optional[str] = Query(None, description="Competition name"),
    season: Optional[str] = Query(None, description="Season"),
    team_name: Optional[str] = Query(None, description="Team name"),
    min_matches: Optional[int] = Query(None, description="Minimum matches"),
    limit: int = Query(100, ge=1, le=1000, description="Number of results to return"),
    db: Session = Depends(get_db),
):
    """Get player statistics."""
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
    competition: Optional[str] = Query(None, description="Competition name"),
    season: Optional[str] = Query(None, description="Season"),
    team_name: Optional[str] = Query(None, description="Team name"),
    limit: int = Query(50, ge=1, le=500, description="Number of results to return"),
    db: Session = Depends(get_db),
):
    """Get match scorecards."""
    service = AnalyticsService()
    data = service.get_match_scorecards(
        competition=competition,
        season=season,
        team_name=team_name,
        limit=limit,
    )
    return data if data else []


@router.get("/sa20-official-stats")
async def sa20_official_stats(
    stat_type: str = Query("batting", description="Stat type (batting/bowling)"),
    season: Optional[int] = Query(None, description="Season year"),
    limit: int = Query(50, ge=1, le=500, description="Number of results to return"),
    db: Session = Depends(get_db),
):
    """Get statistics scraped from SA20 official website."""
    service = AnalyticsService()
    data = service.get_sa20_official_stats(stat_type=stat_type, season=season, limit=limit)
    return data if data else []

