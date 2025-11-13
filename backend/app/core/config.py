"""Application configuration using pydantic settings."""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Configuration values for the platform."""

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/sa20_predictor"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MODEL_PATH: str = "./data/models"

    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
