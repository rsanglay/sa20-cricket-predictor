"""Match endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.match import HeadToHead, Match, MatchDetail
from app.services.match_service import MatchService

router = APIRouter()


@router.get("/", response_model=List[Match])
async def list_matches(
    season: Optional[int] = None,
    team_id: Optional[int] = None,
    venue_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> List[Match]:
    service = MatchService(db)
    return service.get_matches(season=season, team_id=team_id, venue_id=venue_id)


@router.get("/upcoming")
async def get_upcoming_matches(
    season: int = 2026,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> List[Match]:
    """Get upcoming matches for the season."""
    service = MatchService(db)
    matches = service.get_upcoming_matches(season=season, limit=limit)
    return matches


@router.get("/head-to-head/{team1_id}/{team2_id}", response_model=HeadToHead)
async def head_to_head(team1_id: int, team2_id: int, db: Session = Depends(get_db)) -> HeadToHead:
    service = MatchService(db)
    return service.get_head_to_head(team1_id, team2_id)


@router.get("/{match_id}", response_model=MatchDetail)
async def get_match(match_id: int, db: Session = Depends(get_db)) -> MatchDetail:
    service = MatchService(db)
    return service.get_match_detail(match_id)
