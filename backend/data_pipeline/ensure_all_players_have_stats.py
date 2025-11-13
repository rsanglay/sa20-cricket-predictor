"""Ensure all players have stats by scraping and generating from deliveries."""
import sys
import logging
import asyncio
from pathlib import Path
from typing import Optional

# Add app directory to path
if Path("/app/app").exists():
    sys.path.insert(0, "/app")
else:
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

from app.db.session import SessionLocal
from app.db import models
from data_pipeline.scrape_player_profiles import scrape_all_players
from data_pipeline.generate_stats_from_deliveries import generate_stats_from_deliveries

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def ensure_all_players_have_stats(skip_scraping: bool = False):
    """Ensure all players have stats by scraping first, then generating from deliveries."""
    db = SessionLocal()
    
    try:
        # Step 1: Check current status
        total_players = db.query(models.Player).count()
        players_with_stats = db.query(models.Player).filter(
            models.Player.scraped_season_stats.isnot(None)
        ).count()
        
        logger.info("=" * 60)
        logger.info("Ensuring All Players Have Stats")
        logger.info("=" * 60)
        logger.info(f"Total players: {total_players}")
        logger.info(f"Players with stats: {players_with_stats} ({players_with_stats * 100 // total_players if total_players > 0 else 0}%)")
        logger.info(f"Players without stats: {total_players - players_with_stats}")
        logger.info("=" * 60)
        
        # Step 2: Scrape all players (if not skipped)
        if not skip_scraping:
            logger.info("\nStep 1: Scraping player profiles from SA20 website...")
            await scrape_all_players(limit=None, update_existing=True)
            
            # Refresh session after scraping
            db.commit()
            
            # Step 3: Check status after scraping
            players_with_stats_after_scrape = db.query(models.Player).filter(
                models.Player.scraped_season_stats.isnot(None)
            ).count()
            
            logger.info(f"\nAfter scraping: {players_with_stats_after_scrape}/{total_players} players have stats")
        else:
            logger.info("\nSkipping scraping (already in progress or completed)")
            players_with_stats_after_scrape = players_with_stats
        
        # Step 4: Generate stats from deliveries for remaining players
        players_without_stats = total_players - players_with_stats_after_scrape
        if players_without_stats > 0:
            logger.info(f"\nStep 2: Generating stats from deliveries data for {players_without_stats} players...")
            result = generate_stats_from_deliveries(db, limit=None)
            
            logger.info(f"Generated stats for {result['success']} players")
            logger.info(f"Skipped {result['skipped']} players (no match data)")
            logger.info(f"Failed {result['failed']} players")
        else:
            logger.info("\nAll players already have stats from scraping!")
        
        # Step 5: Final status
        final_players_with_stats = db.query(models.Player).filter(
            models.Player.scraped_season_stats.isnot(None)
        ).count()
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("Final Status")
        logger.info("=" * 60)
        logger.info(f"Total players: {total_players}")
        logger.info(f"Players with stats: {final_players_with_stats} ({final_players_with_stats * 100 // total_players if total_players > 0 else 0}%)")
        logger.info(f"Players without stats: {total_players - final_players_with_stats}")
        logger.info("=" * 60)
        
        if final_players_with_stats == total_players:
            logger.info("✅ SUCCESS: All players now have stats!")
        else:
            logger.warning(f"⚠️  WARNING: {total_players - final_players_with_stats} players still don't have stats")
            logger.warning("These players may not have played any matches or may not be in the deliveries data.")
            
            # List players without stats
            players_without = db.query(models.Player).filter(
                models.Player.scraped_season_stats.is_(None)
            ).all()
            logger.info("\nPlayers without stats:")
            for p in players_without:
                logger.info(f"  - {p.name}")
        
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Ensure all players have stats")
    parser.add_argument("--skip-scraping", action="store_true", help="Skip scraping and only generate from deliveries")
    args = parser.parse_args()
    
    asyncio.run(ensure_all_players_have_stats(skip_scraping=args.skip_scraping))

