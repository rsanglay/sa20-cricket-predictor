"""Script to scrape player profiles from SA20 website and update the database."""
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import Player, BattingStyle, BowlingStyle, PlayerRole
from data_pipeline.scrapers.sa20_playwright_scraper import SA20PlaywrightScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def normalize_player_name(name: str) -> str:
    """Normalize player name for matching."""
    return name.strip().lower()


def find_player_by_name(db: Session, player_name: str) -> Optional[Player]:
    """Find player in database by name (case-insensitive, flexible matching)."""
    normalized_search = normalize_player_name(player_name)
    
    # Try exact match first
    player = db.query(Player).filter(
        Player.name.ilike(player_name)
    ).first()
    
    if player:
        return player
    
    # Try normalized match
    players = db.query(Player).all()
    for p in players:
        if normalize_player_name(p.name) == normalized_search:
            return p
    
    # Try partial match (in case of middle names, etc.)
    name_parts = normalized_search.split()
    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = name_parts[-1]
        for p in players:
            p_normalized = normalize_player_name(p.name)
            p_parts = p_normalized.split()
            if len(p_parts) >= 2:
                if p_parts[0] == first_name and p_parts[-1] == last_name:
                    return p
    
    return None


def update_player_from_scraped_data(db: Session, player: Player, scraped_data: dict) -> bool:
    """Update player record with scraped data."""
    updated = False
    
    try:
        # Update role if scraped and different
        if scraped_data.get("role"):
            # Map normalized role string to PlayerRole enum
            # The role is already normalized by the scraper's _normalize_role method
            role_map = {
                "batsman": PlayerRole.BATSMAN,
                "bowler": PlayerRole.BOWLER,
                "all_rounder": PlayerRole.ALL_ROUNDER,
                "wicket_keeper": PlayerRole.WICKET_KEEPER,
            }
            role_str = scraped_data["role"]
            if role_str in role_map:
                new_role = role_map[role_str]
                if player.role != new_role:
                    player.role = new_role
                    updated = True
                    logger.info(f"  Updated role: {role_str}")
            else:
                logger.warning(f"  Unknown role format: {role_str}")
        
        # Update birth_date
        if scraped_data.get("birth_date") and not player.birth_date:
            player.birth_date = scraped_data["birth_date"]
            updated = True
            logger.info(f"  Updated birth_date: {scraped_data['birth_date']}")
        
        # Update batting_style if not set or different
        if scraped_data.get("batting_style"):
            # Map to enum
            batting_style_map = {
                "right_hand": BattingStyle.RIGHT_HAND,
                "left_hand": BattingStyle.LEFT_HAND,
            }
            if scraped_data["batting_style"] in batting_style_map:
                new_style = batting_style_map[scraped_data["batting_style"]]
                if player.batting_style != new_style:
                    player.batting_style = new_style
                    updated = True
                    logger.info(f"  Updated batting_style: {scraped_data['batting_style']}")
        
        # Update bowling_style if not set or different
        if scraped_data.get("bowling_style"):
            # Map to enum
            bowling_style_map = {
                "right_arm_fast": BowlingStyle.RIGHT_ARM_FAST,
                "left_arm_fast": BowlingStyle.LEFT_ARM_FAST,
                "right_arm_medium": BowlingStyle.RIGHT_ARM_MEDIUM,
                "left_arm_medium": BowlingStyle.LEFT_ARM_MEDIUM,
                "right_arm_spin": BowlingStyle.RIGHT_ARM_SPIN,
                "left_arm_spin": BowlingStyle.LEFT_ARM_SPIN,
            }
            if scraped_data["bowling_style"] in bowling_style_map:
                new_style = bowling_style_map[scraped_data["bowling_style"]]
                if player.bowling_style != new_style:
                    player.bowling_style = new_style
                    updated = True
                    logger.info(f"  Updated bowling_style: {scraped_data['bowling_style']}")
        
        # Store season stats in JSONB field
        if scraped_data.get("season_stats"):
            import json
            # Convert season_stats to JSON-serializable format
            season_stats_list = []
            for stat in scraped_data["season_stats"]:
                # Convert any datetime objects to strings
                stat_dict = {}
                for key, value in stat.items():
                    if hasattr(value, 'isoformat'):  # datetime objects
                        stat_dict[key] = value.isoformat()
                    else:
                        stat_dict[key] = value
                season_stats_list.append(stat_dict)
            
            player.scraped_season_stats = {"season_stats": season_stats_list}
            updated = True
            logger.info(f"  Stored {len(season_stats_list)} season stats records")
        
        if updated:
            db.commit()
            logger.info(f"  ✓ Successfully updated player {player.name}")
        else:
            logger.info(f"  - No updates needed for player {player.name}")
        
        return updated
    except Exception as e:
        logger.error(f"  ✗ Error updating player {player.name}: {e}")
        db.rollback()
        return False


async def scrape_player_profile(scraper: SA20PlaywrightScraper, player_name: str) -> Optional[dict]:
    """Scrape a single player profile."""
    try:
        data = await scraper.scrape_player_profile(player_name)
        return data
    except Exception as e:
        logger.error(f"Error scraping player {player_name}: {e}")
        return None


async def scrape_all_players(limit: Optional[int] = None, update_existing: bool = True):
    """Scrape all player profiles from SA20 website and update database."""
    db = SessionLocal()
    scraper = SA20PlaywrightScraper()
    
    try:
        # Get all players from database
        query = db.query(Player)
        if not update_existing:
            # Only get players without birth_date
            query = query.filter(Player.birth_date.is_(None))
        
        players = query.all()
        
        if limit:
            players = players[:limit]
        
        logger.info(f"Found {len(players)} players to scrape")
        
        # Scrape each player
        successful = 0
        failed = 0
        skipped = 0
        updated = 0
        
        for i, player in enumerate(players, 1):
            logger.info(f"[{i}/{len(players)}] Scraping {player.name}...")
            
            # Scrape player profile
            try:
                scraped_data = await scrape_player_profile(scraper, player.name)
            except Exception as e:
                logger.error(f"  ✗ Exception scraping {player.name}: {e}")
                failed += 1
                await asyncio.sleep(2)
                continue
            
            if not scraped_data:
                logger.warning(f"  ✗ Failed to scrape data for {player.name}")
                failed += 1
                # Add delay between requests
                await asyncio.sleep(2)
                continue
            
            # Log what was found
            if scraped_data.get("role"):
                logger.info(f"  Found role: {scraped_data['role']}")
            if scraped_data.get("birth_date"):
                logger.info(f"  Found birth_date: {scraped_data['birth_date']}")
            if scraped_data.get("birth_place"):
                logger.info(f"  Found birth_place: {scraped_data['birth_place']}")
            if scraped_data.get("batting_style"):
                logger.info(f"  Found batting_style: {scraped_data['batting_style']}")
            if scraped_data.get("bowling_style"):
                logger.info(f"  Found bowling_style: {scraped_data['bowling_style']}")
            if scraped_data.get("season_stats"):
                logger.info(f"  Found {len(scraped_data['season_stats'])} season stats records")
            
            # Update player in database
            if update_player_from_scraped_data(db, player, scraped_data):
                updated += 1
                successful += 1
            else:
                skipped += 1
                successful += 1
            
            # Add delay between requests to be respectful
            await asyncio.sleep(2)
        
        logger.info(f"\n=== Scraping Summary ===")
        logger.info(f"Total players: {len(players)}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Updated: {updated}")
        logger.info(f"Skipped: {skipped}")
        logger.info(f"Failed: {failed}")
        
    except Exception as e:
        logger.error(f"Error in scrape_all_players: {e}", exc_info=True)
    finally:
        db.close()


async def scrape_single_player(player_name: str):
    """Scrape a single player profile (for testing)."""
    db = SessionLocal()
    scraper = SA20PlaywrightScraper()
    
    try:
        # Find player in database
        player = find_player_by_name(db, player_name)
        
        if not player:
            logger.error(f"Player '{player_name}' not found in database")
            return
        
        logger.info(f"Scraping player profile for {player.name}...")
        
        # Scrape player profile
        scraped_data = await scrape_player_profile(scraper, player.name)
        
        if not scraped_data:
            logger.error(f"Failed to scrape data for {player.name}")
            return
        
        logger.info(f"Scraped data: {scraped_data}")
        
        # Update player in database
        update_player_from_scraped_data(db, player, scraped_data)
        
    except Exception as e:
        logger.error(f"Error in scrape_single_player: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape player profiles from SA20 website")
    parser.add_argument("--player", type=str, help="Scrape a single player by name")
    parser.add_argument("--limit", type=int, help="Limit number of players to scrape")
    parser.add_argument("--update-all", action="store_true", help="Update all players (including those with existing data)")
    
    args = parser.parse_args()
    
    if args.player:
        asyncio.run(scrape_single_player(args.player))
    else:
        asyncio.run(scrape_all_players(limit=args.limit, update_existing=args.update_all))

