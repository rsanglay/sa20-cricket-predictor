"""Fantasy cricket endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.fantasy.projections import FantasyProjectionService
from app.services.fantasy.optimizer import FantasyOptimizer
from app.services.fantasy.differentials import DifferentialService

router = APIRouter()


class OptimizeTeamRequest(BaseModel):
    matchday: str
    budget: float = 100.0
    max_per_team: int = 7
    min_batsmen: int = 3
    min_bowlers: int = 3
    min_all_rounders: int = 1
    min_wicket_keepers: int = 1


@router.get("/projections")
async def get_fantasy_projections(
    matchday: str = Query(..., description="Matchday identifier (e.g., '2026-01-15')"),
    player_ids: Optional[List[int]] = Query(None, description="Optional list of player IDs to filter"),
    db: Session = Depends(get_db),
):
    """Get fantasy projections for players for a matchday."""
    try:
        service = FantasyProjectionService(db)
        projections = service.get_player_projections(matchday, player_ids)
        return projections
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting projections: {str(e)}")


@router.post("/optimize")
async def optimize_fantasy_team(
    request: OptimizeTeamRequest,
    db: Session = Depends(get_db),
):
    """Optimize fantasy team selection under budget and constraints."""
    try:
        optimizer = FantasyOptimizer(db)
        result = optimizer.optimize_team(
            matchday=request.matchday,
            budget=request.budget,
            max_per_team=request.max_per_team,
            min_batsmen=request.min_batsmen,
            min_bowlers=request.min_bowlers,
            min_all_rounders=request.min_all_rounders,
            min_wicket_keepers=request.min_wicket_keepers,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error optimizing team: {str(e)}")


@router.get("/differentials")
async def get_differentials(
    matchday: str = Query(..., description="Matchday identifier"),
    max_ownership: float = Query(0.20, ge=0.0, le=1.0, description="Maximum ownership percentage"),
    min_expected_points: float = Query(30.0, ge=0.0, description="Minimum expected points"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of picks"),
    db: Session = Depends(get_db),
):
    """Get differential picks (low ownership, high expected value)."""
    try:
        service = DifferentialService(db)
        differentials = service.get_differentials(
            matchday=matchday,
            max_ownership=max_ownership,
            min_expected_points=min_expected_points,
            limit=limit,
        )
        return differentials
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting differentials: {str(e)}")

