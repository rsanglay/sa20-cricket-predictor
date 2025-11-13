"""Health check endpoints."""
from fastapi import APIRouter
from app.core.cache import redis_client

router = APIRouter()


@router.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "redis": "connected" if redis_client else "disconnected",
    }


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint (basic implementation)."""
    # TODO: Implement proper Prometheus metrics
    # For now, return basic metrics
    return {
        "status": "ok",
        "metrics": {
            "redis_connected": redis_client is not None,
        },
    }


@router.get("/version")
async def version():
    """Version endpoint."""
    return {
        "version": "0.1.0",
        "api_version": "v1",
    }

