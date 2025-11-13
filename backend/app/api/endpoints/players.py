"""Player endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.player import Player, PlayerDetail, PlayerStats
from app.services.player_service import PlayerService

router = APIRouter()


@router.get("/", response_model=List[Player])
async def list_players(
    role: Optional[str] = None,
    team_id: Optional[int] = None,
    country: Optional[str] = None,
    only_with_projection: bool = False,
    only_with_images: bool = False,
    response: Response = Response(),
    db: Session = Depends(get_db),
) -> List[Player]:
    """Get players. Results are cached for 30 minutes when no filters are applied.
    
    When team_id is provided, only returns players with valid images (current squad).
    """
    service = PlayerService(db)
    # Automatically filter by images when team_id is provided
    filter_by_images = only_with_images or (team_id is not None)
    players = service.get_players(
        role=role, 
        team_id=team_id, 
        country=country,
        only_with_images=filter_by_images,
        only_with_projection=only_with_projection,
    )
    # Add cache headers (shorter cache for filtered results)
    cache_time = 1800 if not (role or team_id or country) else 300
    response.headers["Cache-Control"] = f"public, max-age={cache_time}"
    return players


@router.get("/{player_id}", response_model=PlayerDetail)
async def get_player(
    player_id: int,
    response: Response,
    db: Session = Depends(get_db)
) -> PlayerDetail:
    """Get player details. Results are cached for 30 minutes."""
    service = PlayerService(db)
    player = service.get_player_detail(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    # Add cache headers
    response.headers["Cache-Control"] = "public, max-age=1800"  # 30 minutes
    return player


@router.get("/{player_id}/stats", response_model=PlayerStats)
async def get_player_stats(
    player_id: int, season: Optional[int] = None, db: Session = Depends(get_db)
) -> PlayerStats:
    service = PlayerService(db)
    stats = service.get_player_stats(player_id, season)
    if not stats:
        raise HTTPException(status_code=404, detail="Player not found")
    return stats


@router.get("/{player_id}/projection")
async def predict_player_performance(player_id: int, db: Session = Depends(get_db)):
    service = PlayerService(db)
    if not service.projection_service:
        raise HTTPException(
            status_code=503, 
            detail="Player projection models not available. Please train the models first."
        )
    projection = service.predict_performance(player_id)
    if not projection:
        raise HTTPException(
            status_code=404, 
            detail="Projection unavailable for this player. Player may not be in the training dataset."
        )
    return projection
