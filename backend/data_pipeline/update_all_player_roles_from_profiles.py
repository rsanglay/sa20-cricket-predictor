"""Update all player roles by scraping individual player profile pages from sa20.co.za/player/."""
from __future__ import annotations

import asyncio
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal
from data_pipeline.scrapers.sa20_playwright_scraper import SA20PlaywrightScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def normalize_role_to_enum(role_str: str | None) -> models.PlayerRole | None:
    """Convert normalized role string to PlayerRole enum."""
    if not role_str:
        return None
    
    role_map = {
        "batsman": models.PlayerRole.BATSMAN,
        "bowler": models.PlayerRole.BOWLER,
        "all_rounder": models.PlayerRole.ALL_ROUNDER,
        "wicket_keeper": models.PlayerRole.WICKET_KEEPER,
    }
    
    return role_map.get(role_str)


async def update_all_player_roles(dry_run: bool = False, limit: int | None = None) -> dict:
    """Update all player roles by scraping individual player profile pages."""
    logger.info("=" * 70)
    logger.info("Updating Player Roles from Individual Player Profile Pages")
    logger.info("=" * 70)
    
    db: Session = SessionLocal()
    scraper = SA20PlaywrightScraper()
    
    try:
        # Get all players from database
        query = db.query(models.Player)
        players = query.all()
        
        if limit:
            players = players[:limit]
            logger.info(f"Limiting to first {limit} players")
        
        logger.info(f"Found {len(players)} players to update")
        
        stats = {
            "total_players": len(players),
            "updated": 0,
            "unchanged": 0,
            "failed": 0,
            "no_role": 0,
            "changes": [],
        }
        
        # Scrape each player's profile
        for i, player in enumerate(players, 1):
            logger.info(f"\n[{i}/{len(players)}] Processing {player.name}...")
            
            try:
                # Scrape player profile
                scraped_data = await scraper.scrape_player_profile(player.name)
                
                if not scraped_data:
                    logger.warning(f"  ✗ Failed to scrape profile for {player.name}")
                    stats["failed"] += 1
                    continue
                
                # Get role from scraped data
                role_str = scraped_data.get("role")
                
                if not role_str:
                    logger.warning(f"  - No role found in scraped data for {player.name}")
                    stats["no_role"] += 1
                    continue
                
                # Convert to enum
                new_role = normalize_role_to_enum(role_str)
                
                if not new_role:
                    logger.warning(f"  - Could not normalize role '{role_str}' for {player.name}")
                    stats["no_role"] += 1
                    continue
                
                # Check if role needs updating
                if player.role != new_role:
                    old_role_str = player.role.value if hasattr(player.role, "value") else str(player.role)
                    new_role_str = new_role.value if hasattr(new_role, "value") else str(new_role)
                    
                    stats["changes"].append({
                        "player_id": player.id,
                        "name": player.name,
                        "old_role": old_role_str,
                        "new_role": new_role_str,
                    })
                    
                    if not dry_run:
                        player.role = new_role
                        db.commit()
                        logger.info(f"  ✓ Updated role: {old_role_str} → {new_role_str}")
                        stats["updated"] += 1
                    else:
                        logger.info(f"  [DRY RUN] Would update role: {old_role_str} → {new_role_str}")
                        stats["updated"] += 1
                else:
                    logger.info(f"  - Role already correct: {player.role.value}")
                    stats["unchanged"] += 1
                
                # Rate limiting - be respectful to the server
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"  ✗ Error processing {player.name}: {e}", exc_info=True)
                stats["failed"] += 1
                db.rollback()
                continue
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("Summary:")
        logger.info(f"  Total players: {stats['total_players']}")
        logger.info(f"  Updated: {stats['updated']}")
        logger.info(f"  Unchanged: {stats['unchanged']}")
        logger.info(f"  Failed: {stats['failed']}")
        logger.info(f"  No role data: {stats['no_role']}")
        
        if stats["changes"]:
            logger.info(f"\nFirst 20 changes:")
            for change in stats["changes"][:20]:
                logger.info(
                    f"  {change['name']}: {change['old_role']} → {change['new_role']}"
                )
        
        return stats
        
    except Exception as e:
        logger.error(f"Error in update_all_player_roles: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Update all player roles by scraping individual player profile pages"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without actually updating the database",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of players to process (for testing)",
    )
    args = parser.parse_args()
    
    if args.dry_run:
        print("\n" + "=" * 70)
        print("DRY RUN MODE - No changes will be made to the database")
        print("=" * 70 + "\n")
    
    asyncio.run(update_all_player_roles(dry_run=args.dry_run, limit=args.limit))
    
    if args.dry_run:
        print("\n" + "=" * 70)
        print("DRY RUN COMPLETE - No changes were made")
        print("Run without --dry-run to apply changes")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("✓ Player roles updated successfully!")
        print("=" * 70)


if __name__ == "__main__":
    main()

