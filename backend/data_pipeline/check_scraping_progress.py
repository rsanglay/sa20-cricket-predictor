"""Quick script to check scraping progress."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.db import models

db = SessionLocal()

total = db.query(models.Player).count()
with_birth_date = db.query(models.Player).filter(models.Player.birth_date.isnot(None)).count()
with_batting_style = db.query(models.Player).filter(
    models.Player.batting_style.isnot(None)
).count()
with_bowling_style = db.query(models.Player).filter(
    models.Player.bowling_style.isnot(None)
).count()

print(f"Total players: {total}")
print(f"Players with birth_date: {with_birth_date} ({with_birth_date/total*100:.1f}%)")
print(f"Players with batting_style: {with_batting_style} ({with_batting_style/total*100:.1f}%)")
print(f"Players with bowling_style: {with_bowling_style} ({with_bowling_style/total*100:.1f}%)")
print(f"\nProgress: {with_birth_date}/{total} players scraped")

db.close()

