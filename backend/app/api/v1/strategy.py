"""Strategy endpoints for in-match decision making."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.simulate.xi_optimizer import BattingOrderOptimizer
from app.services.simulate.bowling_advisor import BowlingAdvisor
from app.services.simulate.drs_model import DRSModel
from app.services.simulate.powerplay import PowerplayAnalyzer

router = APIRouter()


# Request models
class BattingOrderRequest(BaseModel):
    xi_player_ids: List[int]
    wickets_fallen: int
    overs_left: float
    striker_id: Optional[int] = None
    non_striker_id: Optional[int] = None
    venue_id: Optional[int] = None


class BowlingChangeRequest(BaseModel):
    available_bowlers: List[int]
    remaining_overs: float
    wickets_down: int
    striker_id: Optional[int] = None
    non_striker_id: Optional[int] = None
    current_bowler_id: Optional[int] = None
    phase: Optional[str] = None
    overs_ahead: int = 3


class DRSRequest(BaseModel):
    delivery_type: str  # 'pace' or 'spin'
    line: str  # 'off', 'middle', 'leg'
    length: str  # 'full', 'good', 'short'
    batter_id: int
    bowler_id: int
    match_id: int
    phase: Optional[str] = None
    umpire_id: Optional[int] = None


class PowerplayRequest(BaseModel):
    batting_team_id: int
    bowling_team_id: int
    venue_id: Optional[int] = None
    wickets_down: int = 0
    overs_completed: float = 0.0


@router.post("/batting-order")
async def suggest_batting_order(
    request: BattingOrderRequest,
    db: Session = Depends(get_db),
):
    """Suggest optimal batting order for remaining wickets."""
    try:
        optimizer = BattingOrderOptimizer(db)
        result = optimizer.optimize_batting_order(
            xi_player_ids=request.xi_player_ids,
            wickets_fallen=request.wickets_fallen,
            overs_left=request.overs_left,
            striker_id=request.striker_id,
            non_striker_id=request.non_striker_id,
            venue_id=request.venue_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error optimizing batting order: {str(e)}")


@router.post("/bowling-change")
async def recommend_bowling_change(
    request: BowlingChangeRequest,
    db: Session = Depends(get_db),
):
    """Recommend next over bowler and sequence for next K overs."""
    try:
        advisor = BowlingAdvisor(db)
        result = advisor.recommend_bowling_change(
            available_bowlers=request.available_bowlers,
            remaining_overs=request.remaining_overs,
            wickets_down=request.wickets_down,
            striker_id=request.striker_id,
            non_striker_id=request.non_striker_id,
            current_bowler_id=request.current_bowler_id,
            phase=request.phase,
            overs_ahead=request.overs_ahead,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recommending bowling change: {str(e)}")


@router.post("/drs")
async def drs_review_advice(
    request: DRSRequest,
    db: Session = Depends(get_db),
):
    """Return DRS overturn probability and net win% impact."""
    try:
        drs_model = DRSModel(db)
        result = drs_model.predict_overturn_probability(
            delivery_type=request.delivery_type,
            line=request.line,
            length=request.length,
            batter_id=request.batter_id,
            bowler_id=request.bowler_id,
            match_id=request.match_id,
            phase=request.phase,
            umpire_id=request.umpire_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error predicting DRS outcome: {str(e)}")


@router.post("/powerplay")
async def powerplay_strategy(
    request: PowerplayRequest,
    db: Session = Depends(get_db),
):
    """Recommend powerplay intent level and par targets."""
    try:
        analyzer = PowerplayAnalyzer(db)
        result = analyzer.analyze_powerplay_strategy(
            batting_team_id=request.batting_team_id,
            bowling_team_id=request.bowling_team_id,
            venue_id=request.venue_id,
            wickets_down=request.wickets_down,
            overs_completed=request.overs_completed,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing powerplay strategy: {str(e)}")


# Note: WebSocket endpoint for live strategy updates would be implemented separately
# using FastAPI's WebSocket support. This would require additional setup for real-time
# match state updates.

