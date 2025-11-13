"""Team endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.team import Team, TeamComparison, TeamDetail
from app.services.team_service import TeamService

router = APIRouter()


@router.get("/", response_model=List[Team])
async def list_teams(
    response: Response,
    db: Session = Depends(get_db)
) -> List[Team]:
    """Get all teams. Results are cached for 1 hour."""
    service = TeamService(db)
    teams = service.get_all_teams()
    # Add cache headers for client-side caching
    response.headers["Cache-Control"] = "public, max-age=3600"  # 1 hour
    return teams


@router.get("/{team_id}", response_model=TeamDetail)
async def get_team(
    team_id: int,
    response: Response,
    db: Session = Depends(get_db)
) -> TeamDetail:
    """Get team details. Results are cached for 30 minutes."""
    service = TeamService(db)
    team = service.get_team_detail(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    # Add cache headers for client-side caching
    response.headers["Cache-Control"] = "public, max-age=1800"  # 30 minutes
    return team


@router.post("/compare", response_model=TeamComparison)
async def compare_teams(team_ids: List[int], db: Session = Depends(get_db)) -> TeamComparison:
    if len(team_ids) < 2:
        raise HTTPException(status_code=400, detail="At least two teams are required")
    service = TeamService(db)
    return service.compare_teams(team_ids)
