"""Database session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings

# Optimize connection pooling for better performance
# Increased pool size to handle concurrent requests during long-running simulations
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    poolclass=QueuePool,
    pool_size=20,  # Increased from 10 to handle more concurrent requests
    max_overflow=40,  # Increased from 20 to allow more overflow connections
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_reset_on_return='commit',  # Reset connections on return
    echo=False,  # Set to True for SQL query logging
    future=True,
)
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
)


def get_db():
    """Dependency that provides a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
