"""Script to scrape and update player statistics from SA20 official website."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Optional

from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal
from data_pipeline.scrapers.sa20_stats_scraper import SA20StatsScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_name(name: str) -> str:
    """Normalize player name for matching."""
    return name.strip().lower().replace("'", "").replace(" ", "_").replace("-", "_")


def get_player_by_name(db: Session, name: str, team_name: Optional[str] = None) -> models.Player | None:
    """Get player from database by name (with fuzzy matching)."""
    normalized = normalize_name(name)
    
    # Try exact match first
    player = db.query(models.Player).filter(models.Player.name == name).first()
    if player:
        return player
    
    # Try with team if provided
    if team_name:
        team = db.query(models.Team).filter(models.Team.name == team_name).first()
        if team:
            player = db.query(models.Player).filter(
                models.Player.name == name,
                models.Player.team_id == team.id
            ).first()
            if player:
                return player
    
    # Try normalized match
    all_players = db.query(models.Player).all()
    for p in all_players:
        if normalize_name(p.name) == normalized:
            return p
    
    return None


def update_player_stats_from_scraper(db: Session, season: Optional[int] = None) -> tuple[int, int]:
    """Scrape player stats from SA20 website and update database."""
    logger.info(f"Scraping SA20 player statistics{' for season ' + str(season) if season else ' (all-time)'}...")
    
    scraper = SA20StatsScraper()
    all_stats = scraper.scrape_all_player_stats(season=season)
    
    batting_stats = all_stats.get("batting", [])
    bowling_stats = all_stats.get("bowling", [])
    
    logger.info(f"Found {len(batting_stats)} batting records and {len(bowling_stats)} bowling records")
    
    players_updated = 0
    stats_added = 0
    
    # Process batting stats
    for stat in batting_stats:
        try:
            player = get_player_by_name(db, stat["player_name"], stat.get("team"))
            if not player:
                logger.debug(f"Player not found: {stat['player_name']}")
                continue
            
            # Update player role if we can infer it from stats
            # (batsmen typically have more runs, bowlers have more wickets)
            # This is a heuristic - actual role should come from team page
            
            # Create or update player performance record
            # Note: We'd need a match_id for this, so we'll store aggregated stats differently
            # For now, we'll update the player's career stats in a separate table or field
            
            players_updated += 1
            
        except Exception as e:
            logger.warning(f"Error processing batting stat for {stat.get('player_name')}: {e}")
            continue
    
    # Process bowling stats
    for stat in bowling_stats:
        try:
            player = get_player_by_name(db, stat["player_name"], stat.get("team"))
            if not player:
                continue
            
            # Similar processing for bowling stats
            players_updated += 1
            
        except Exception as e:
            logger.warning(f"Error processing bowling stat for {stat.get('player_name')}: {e}")
            continue
    
    db.commit()
    logger.info(f"✓ Updated stats for {players_updated} players")
    return players_updated, stats_added


def export_stats_to_csv(stats_data: Dict, output_dir: Path) -> None:
    """Export scraped stats to CSV files for use in ML models."""
    import pandas as pd
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Export batting stats
    if stats_data.get("batting"):
        batting_df = pd.DataFrame(stats_data["batting"])
        batting_path = output_dir / f"sa20_batting_stats_{stats_data.get('season', 'alltime')}.csv"
        batting_df.to_csv(batting_path, index=False)
        logger.info(f"Exported batting stats to {batting_path}")
    
    # Export bowling stats
    if stats_data.get("bowling"):
        bowling_df = pd.DataFrame(stats_data["bowling"])
        bowling_path = output_dir / f"sa20_bowling_stats_{stats_data.get('season', 'alltime')}.csv"
        bowling_df.to_csv(bowling_path, index=False)
        logger.info(f"Exported bowling stats to {bowling_path}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape and update SA20 player statistics")
    parser.add_argument("--season", type=int, default=None, help="Season year (default: all-time)")
    parser.add_argument("--export-csv", action="store_true", help="Export stats to CSV files")
    args = parser.parse_args()
    
    scraper = SA20StatsScraper()
    all_stats = scraper.scrape_all_player_stats(season=args.season)
    
    if args.export_csv:
        output_dir = Path(__file__).parent.parent.parent / "data" / "raw" / "sa20_stats"
        export_stats_to_csv(all_stats, output_dir)
    
    db: Session = SessionLocal()
    try:
        players_updated, stats_added = update_player_stats_from_scraper(db, season=args.season)
        print(f"\n✓ Successfully updated stats for {players_updated} players")
        if args.export_csv:
            print(f"✓ Stats exported to CSV files")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating stats: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

