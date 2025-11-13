"""Advanced analysis endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.analysis_service import AnalysisService

router = APIRouter()


@router.post("/squad-gaps")
async def analyze_squad_gaps(team_id: int, db: Session = Depends(get_db)):
    service = AnalysisService(db)
    return service.analyze_squad_gaps(team_id)


@router.post("/optimal-xi")
async def generate_optimal_xi(team_id: int, opponent_id: int, venue_id: int, db: Session = Depends(get_db)):
    service = AnalysisService(db)
    return service.generate_optimal_xi(team_id, opponent_id, venue_id)


@router.get("/matchups")
async def get_matchups(batsman_id: int, bowler_id: int, db: Session = Depends(get_db)):
    service = AnalysisService(db)
    return service.get_player_matchup(batsman_id, bowler_id)
