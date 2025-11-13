#!/usr/bin/env python3
"""Helper script to create initial Alembic migration."""
import os
import sys
from pathlib import Path

# Add parent directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Set environment variables if not set
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5435/sa20_predictor")

print("Setting up Alembic migration...")
print(f"Database URL: {os.environ.get('DATABASE_URL')}")

# Check if models can be imported
try:
    from app.db.models import *
    from app.db.base import Base
    print("✓ Models imported successfully")
except Exception as e:
    print(f"✗ Error importing models: {e}")
    sys.exit(1)

# Check if Alembic is available
try:
    import alembic
    print("✓ Alembic is available")
except ImportError:
    print("✗ Alembic not found. Install with: pip install alembic")
    sys.exit(1)

print("\nNext steps:")
print("1. Make sure PostgreSQL is running (docker-compose up -d postgres)")
print("2. Run: alembic revision --autogenerate -m 'Initial migration'")
print("3. Run: alembic upgrade head")

