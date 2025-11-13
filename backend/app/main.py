"""FastAPI application entrypoint for SA20 Pre-Season Intelligence Platform."""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1 import analytics, fantasy, health, matches, players, predictions, teams, strategy
from app.api.endpoints import analysis  # Keep analysis endpoint as-is for now
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import engine

# Configure logging
configure_logging(settings.ENVIRONMENT)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    logger.info("Starting SA20 Pre-Season Intelligence Platform API")
    # Use Alembic migrations instead of create_all in production
    # Base.metadata.create_all(bind=engine)
    yield
    logger.info("Shutting down SA20 Pre-Season Intelligence Platform API")


def create_application() -> FastAPI:
    """Instantiate the FastAPI application with middleware and routers."""
    app = FastAPI(
        title="SA20 Pre-Season Intelligence Platform API",
        description=(
            "Advanced analytics, predictions, and squad intelligence for the SA20 "
            "cricket league."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(GZipMiddleware, minimum_size=1_000)

    # Health and meta endpoints (not versioned)
    app.include_router(health.router, tags=["health"])

    # API v1 endpoints
    app.include_router(predictions.router, prefix="/api/v1/predictions", tags=["predictions"])
    app.include_router(teams.router, prefix="/api/v1/teams", tags=["teams"])
    app.include_router(players.router, prefix="/api/v1/players", tags=["players"])
    app.include_router(matches.router, prefix="/api/v1/matches", tags=["matches"])
    app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
    app.include_router(strategy.router, prefix="/api/v1/strategy", tags=["strategy"])
    app.include_router(fantasy.router, prefix="/api/v1/fantasy", tags=["fantasy"])

    # Legacy endpoints (keep for backward compatibility)
    app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "message": "SA20 Pre-Season Intelligence Platform API",
            "version": "0.1.0",
            "api_version": "v1",
            "docs": "/docs",
        }

    return app


app = create_application()
