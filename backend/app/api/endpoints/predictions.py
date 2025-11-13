"""Prediction endpoints."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.schemas.prediction import (
    MatchPredictionRequest, 
    MatchPredictionResponse, 
    SeasonPrediction,
    SeasonSimulationRequest,
)
from app.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/match", response_model=MatchPredictionResponse)
async def predict_match(
    request: MatchPredictionRequest, db: Session = Depends(get_db)
) -> MatchPredictionResponse:
    service = PredictionService(db)
    try:
        return service.predict_match(
            home_team_id=request.home_team_id,
            away_team_id=request.away_team_id,
            venue_id=request.venue_id,
            overwrite_venue_avg_score=request.overwrite_venue_avg_score,
            home_lineup=request.home_lineup_player_ids,
            away_lineup=request.away_lineup_player_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"Model files not found: {str(exc)}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(exc)}") from exc


@router.post("/season", response_model=SeasonPrediction)
async def simulate_season(
    request: SeasonSimulationRequest,
):
    """Simulate season with Monte Carlo method and optional custom XIs.
    
    This endpoint runs the simulation in a thread pool to avoid blocking other requests.
    The simulation is optimized to pre-load all data before running, minimizing database queries.
    
    Note: We don't use Depends(get_db) here to avoid holding onto a database connection
    while the simulation runs. The simulation creates its own session.
    """
    # OPTIMIZATION: Run simulation in thread pool to avoid blocking event loop
    # This allows other requests to be processed while simulation runs
    def run_simulation():
        """Run simulation in a separate thread with its own database session.
        
        Creates an isolated database session that's completely separate from
        the request lifecycle, preventing any connection blocking.
        """
        # Import here to avoid circular imports
        from app.db.session import engine
        from sqlalchemy.orm import sessionmaker
        
        # Create a new sessionmaker for this thread (not scoped_session)
        # This ensures the session is completely independent
        ThreadSession = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,  # Don't expire objects on commit (we're not committing)
        )
        thread_db = ThreadSession()
        
        try:
            logger.info(f"Starting simulation with {request.num_simulations} simulations")
            service = PredictionService(thread_db)
            result = service.simulate_season(request.num_simulations, request.custom_xis)
            logger.info("Simulation completed successfully")
            return result
        except Exception as e:
            # Rollback on error (though we shouldn't have any transactions)
            thread_db.rollback()
            logger.error(f"Simulation error: {e}", exc_info=True)
            raise
        finally:
            # Always close the database session when done to release the connection
            # This is critical - it releases the connection back to the pool
            thread_db.close()
            logger.info("Database session closed, connection released")
    
    try:
        # Run the blocking simulation in a thread pool
        # This allows other requests to be processed concurrently
        result = await asyncio.to_thread(run_simulation)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Model files not found: {str(exc)}") from exc
    except Exception as exc:
        logger.error(f"Simulation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(exc)}") from exc


@router.get("/standings")
async def get_standings(db: Session = Depends(get_db)):
    service = PredictionService(db)
    return service.get_predicted_standings()


@router.get("/top-run-scorer")
async def predict_top_run_scorer(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    """Predict top run scorers for the upcoming season."""
    service = PredictionService(db)
    try:
        return service.predict_top_run_scorers(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(exc)}") from exc


@router.get("/top-wicket-taker")
async def predict_top_wicket_taker(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    """Predict top wicket takers for the upcoming season."""
    service = PredictionService(db)
    try:
        return service.predict_top_wicket_takers(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(exc)}") from exc
