"""
Import scraped player profiles from players.json into the database.

This script:
1. Reads players.json
2. Converts the data format to match database schema
3. Updates players in the database with scraped stats
"""
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import SessionLocal
from app.db.models import Player, BattingStyle, BowlingStyle

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def normalize_player_name(name: str) -> str:
    """Normalize player name for matching."""
    return name.strip()


def find_player_by_name(db: Session, player_name: str) -> Optional[Player]:
    """Find player in database by name (case-insensitive, flexible matching)."""
    normalized_search = normalize_player_name(player_name).lower()
    
    # Try exact match first
    player = db.query(Player).filter(
        func.lower(Player.name) == normalized_search
    ).first()
    
    if player:
        return player
    
    # Try partial match
    players = db.query(Player).filter(
        func.lower(Player.name).contains(normalized_search)
    ).all()
    
    if len(players) == 1:
        return players[0]
    
    # Try reverse (search name in player name)
    if len(players) > 1:
        for p in players:
            if normalized_search in p.name.lower():
                return p
    
    return None


def parse_date_of_birth(dob_str: str) -> Optional[datetime]:
    """Parse date of birth from string (DD/MM/YYYY format)."""
    if not dob_str:
        return None
    
    try:
        # SA20 uses DD/MM/YYYY format
        parts = dob_str.split('/')
        if len(parts) == 3:
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            return datetime(year, month, day)
    except Exception as e:
        logger.debug(f"Could not parse date {dob_str}: {e}")
    
    return None


def map_batting_style(style_str: str) -> Optional[BattingStyle]:
    """Map batting style string to enum."""
    if not style_str:
        return None
    
    style_lower = style_str.lower()
    if 'right' in style_lower and 'hand' in style_lower:
        return BattingStyle.RIGHT_HAND
    elif 'left' in style_lower and 'hand' in style_lower:
        return BattingStyle.LEFT_HAND
    elif 'right' in style_lower:
        return BattingStyle.RIGHT_HAND
    elif 'left' in style_lower:
        return BattingStyle.LEFT_HAND
    
    return None


def map_bowling_style(style_str: str) -> Optional[BowlingStyle]:
    """Map bowling style string to enum."""
    if not style_str:
        return None
    
    style_lower = style_str.lower()
    if 'right arm fast' in style_lower or 'right-arm fast' in style_lower:
        return BowlingStyle.RIGHT_ARM_FAST
    elif 'left arm fast' in style_lower or 'left-arm fast' in style_lower:
        return BowlingStyle.LEFT_ARM_FAST
    elif 'right arm medium' in style_lower or 'right-arm medium' in style_lower or ('right' in style_lower and 'medium' in style_lower):
        return BowlingStyle.RIGHT_ARM_MEDIUM
    elif 'left arm medium' in style_lower or 'left-arm medium' in style_lower or ('left' in style_lower and 'medium' in style_lower):
        return BowlingStyle.LEFT_ARM_MEDIUM
    elif 'right arm spin' in style_lower or 'right-arm spin' in style_lower or ('right' in style_lower and 'spin' in style_lower):
        return BowlingStyle.RIGHT_ARM_SPIN
    elif 'left arm spin' in style_lower or 'left-arm spin' in style_lower or ('left' in style_lower and 'spin' in style_lower):
        return BowlingStyle.LEFT_ARM_SPIN
    
    return None


def convert_to_season_stats(player_data: Dict) -> List[Dict]:
    """Convert player data format to season_stats format for database."""
    batting_stats = player_data.get('batting_fielding_stats', [])
    bowling_stats = player_data.get('bowling_stats', [])
    
    # Merge stats by season and team
    stats_by_season = {}
    
    # Process batting stats
    for stat in batting_stats:
        year = int(stat.get('year', 0))
        team = stat.get('team', '')
        key = (year, team)
        
        if key not in stats_by_season:
            stats_by_season[key] = {
                'season': year,
                'team': team,
                'batting': {},
                'bowling': {}
            }
        
        stats_by_season[key]['batting'] = {
            'matches': parse_int(stat.get('mat', '0')),
            'runs': parse_int(stat.get('runs', '0')),
            'highest_score': parse_int(stat.get('hs', '0')),
            'average': parse_float(stat.get('avg', '0')),
            'strike_rate': parse_float(stat.get('sr', '0')),
            'balls': parse_int(stat.get('bf', '0')),  # balls_faced
            'fours': parse_int(stat.get('4s', '0')),
            'sixes': parse_int(stat.get('6s', '0')),
            'fifties': parse_int(stat.get('50', '0')),
            'hundreds': parse_int(stat.get('100', '0')),
        }
    
    # Process bowling stats
    for stat in bowling_stats:
        year = int(stat.get('year', 0))
        team = stat.get('team', '')
        key = (year, team)
        
        if key not in stats_by_season:
            stats_by_season[key] = {
                'season': year,
                'team': team,
                'batting': {},
                'bowling': {}
            }
        
        best_figures = stat.get('bbm', '-')
        if best_figures in ['—', '-', '', '0', '–']:
            best_figures = None
        
        stats_by_season[key]['bowling'] = {
            'matches': parse_int(stat.get('mat', '0')),
            'balls': parse_int(stat.get('balls', '0')),
            'runs': parse_int(stat.get('runs', '0')),
            'wickets': parse_int(stat.get('wkts', '0')),
            'average': parse_float(stat.get('ave', '0')),
            'economy': parse_float(stat.get('econ', '0')),
            'strike_rate': parse_float(stat.get('sr', '0')),
            'best_figures': best_figures,
            'five_wickets': parse_int(stat.get('5w', '0')),
        }
    
    # Convert to list and sort by season
    season_stats = list(stats_by_season.values())
    season_stats.sort(key=lambda x: x['season'], reverse=True)
    
    return season_stats


def parse_int(value: str) -> int:
    """Parse integer value, handling dashes and empty strings."""
    if isinstance(value, int):
        return value
    value = str(value).strip()
    if not value or value == "—" or value == "-" or value == "":
        return 0
    value = re.sub(r'[^\d]', '', value)
    try:
        return int(value) if value else 0
    except ValueError:
        return 0


def parse_float(value: str) -> float:
    """Parse float value, handling dashes and empty strings."""
    if isinstance(value, (int, float)):
        return float(value)
    value = str(value).strip()
    if not value or value == "—" or value == "-" or value == "":
        return 0.0
    value = value.replace(',', '')
    try:
        return float(value) if value else 0.0
    except ValueError:
        return 0.0


def update_player_from_scraped_data(db: Session, player: Player, scraped_data: Dict) -> bool:
    """Update player record with scraped data."""
    updated = False
    
    try:
        # Update birth_date
        personal_details = scraped_data.get('personal_details', {})
        dob_str = personal_details.get('date_of_birth')
        if dob_str and not player.birth_date:
            birth_date = parse_date_of_birth(dob_str)
            if birth_date:
                player.birth_date = birth_date
                updated = True
                logger.info(f"  Updated birth_date: {birth_date}")
        
        # Update country if available
        nationality = personal_details.get('nationality')
        if nationality and not player.country:
            player.country = nationality
            updated = True
            logger.info(f"  Updated country: {nationality}")
        
        # Update batting_style
        batting_style_str = personal_details.get('batting_style')
        if batting_style_str:
            new_style = map_batting_style(batting_style_str)
            if new_style and player.batting_style != new_style:
                player.batting_style = new_style
                updated = True
                logger.info(f"  Updated batting_style: {new_style.value}")
        
        # Update bowling_style
        bowling_style_str = personal_details.get('bowling_style')
        if bowling_style_str:
            new_style = map_bowling_style(bowling_style_str)
            if new_style and player.bowling_style != new_style:
                player.bowling_style = new_style
                updated = True
                logger.info(f"  Updated bowling_style: {new_style.value}")
        
        # Store season stats in JSONB field
        season_stats = convert_to_season_stats(scraped_data)
        if season_stats:
            player.scraped_season_stats = {"season_stats": season_stats}
            updated = True
            logger.info(f"  Stored {len(season_stats)} season stats records")
        
        if updated:
            db.commit()
            logger.info(f"  ✓ Successfully updated player {player.name}")
        else:
            logger.info(f"  - No updates needed for player {player.name}")
        
        return updated
    except Exception as e:
        logger.error(f"  ✗ Error updating player {player.name}: {e}", exc_info=True)
        db.rollback()
        return False


def import_player_profiles(json_file: str = "players.json") -> Dict:
    """Import player profiles from JSON file into database."""
    # Determine file path
    json_path = Path(json_file)
    if not json_path.is_absolute():
        # Try project root
        project_root = Path(__file__).parent.parent.parent
        json_path = project_root / json_file
    
    if not json_path.exists():
        logger.error(f"JSON file not found: {json_path}")
        return {"success": 0, "failed": 0, "not_found": 0, "skipped": 0}
    
    logger.info(f"Loading player data from {json_path}")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            players_data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON file: {e}")
        return {"success": 0, "failed": 0, "not_found": 0, "skipped": 0}
    
    logger.info(f"Loaded {len(players_data)} players from JSON")
    
    db = SessionLocal()
    success = 0
    failed = 0
    not_found = 0
    skipped = 0
    
    try:
        for i, player_data in enumerate(players_data, 1):
            player_name = player_data.get('player_name', '')
            logger.info(f"[{i}/{len(players_data)}] Processing {player_name}...")
            
            # Find player in database
            player = find_player_by_name(db, player_name)
            
            if not player:
                logger.warning(f"  ✗ Player not found in database: {player_name}")
                not_found += 1
                continue
            
            # Update player with scraped data
            if update_player_from_scraped_data(db, player, player_data):
                success += 1
            else:
                skipped += 1
        
        logger.info(f"\n=== Import Summary ===")
        logger.info(f"Total players in JSON: {len(players_data)}")
        logger.info(f"Successfully updated: {success}")
        logger.info(f"Skipped (no changes): {skipped}")
        logger.info(f"Not found in database: {not_found}")
        logger.info(f"Failed: {failed}")
        
        return {
            "success": success,
            "failed": failed,
            "not_found": not_found,
            "skipped": skipped,
            "total": len(players_data)
        }
    
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Import player profiles from JSON into database")
    parser.add_argument("--file", type=str, default="players.json", help="Path to players.json file")
    
    args = parser.parse_args()
    
    result = import_player_profiles(args.file)
    
    if result["success"] > 0:
        logger.info(f"\n✓ Successfully imported {result['success']} players")
    else:
        logger.warning(f"\n⚠ No players were updated")


if __name__ == "__main__":
    main()

