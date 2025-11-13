"""Check progress of player stats scraping."""
import sys
from pathlib import Path

if Path("/app/app").exists():
    sys.path.insert(0, "/app")
else:
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

from app.db.session import SessionLocal
from app.db import models

def check_progress():
    """Check how many players have stats."""
    db = SessionLocal()
    
    try:
        total = db.query(models.Player).count()
        with_stats = db.query(models.Player).filter(
            models.Player.scraped_season_stats.isnot(None)
        ).count()
        without_stats = total - with_stats
        
        progress = (with_stats * 100) // total if total > 0 else 0
        
        print(f"=" * 60)
        print(f"Player Stats Scraping Progress")
        print(f"=" * 60)
        print(f"Total players: {total}")
        print(f"Players with stats: {with_stats} ({progress}%)")
        print(f"Players without stats: {without_stats} ({100 - progress}%)")
        print(f"=" * 60)
        
        # Show some players with stats
        players_with_stats = db.query(models.Player).filter(
            models.Player.scraped_season_stats.isnot(None)
        ).order_by(models.Player.name).limit(10).all()
        
        if players_with_stats:
            print(f"\nPlayers with stats (showing first 10):")
            for p in players_with_stats:
                stats_count = len(p.scraped_season_stats.get('season_stats', [])) if p.scraped_season_stats else 0
                print(f"  ✓ {p.name} ({stats_count} seasons)")
        
        # Show some players without stats
        players_without_stats = db.query(models.Player).filter(
            models.Player.scraped_season_stats.is_(None)
        ).order_by(models.Player.name).limit(10).all()
        
        if players_without_stats:
            print(f"\nPlayers without stats (showing first 10):")
            for p in players_without_stats:
                print(f"  ✗ {p.name}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_progress()

