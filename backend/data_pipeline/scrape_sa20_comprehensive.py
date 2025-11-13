"""Comprehensive scraper for all SA20 data using improved API scraper."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal
from data_pipeline.scrapers.sa20_api_scraper import SA20APIScraper

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def normalize_name(name: str) -> str:
    """Normalize name for matching."""
    return name.strip().lower().replace("'", "").replace(" ", "_").replace("-", "_")


def get_team_by_name(db: Session, name: str) -> Optional[models.Team]:
    """Get team from database by name."""
    team = db.query(models.Team).filter(models.Team.name == name).first()
    if team:
        return team
    
    normalized = normalize_name(name)
    all_teams = db.query(models.Team).all()
    for t in all_teams:
        if normalize_name(t.name) == normalized or normalize_name(t.short_name or "") == normalized:
            return t
    
    return None


def update_teams_and_players_comprehensive(db: Session) -> tuple[int, int]:
    """Comprehensively scrape and update teams and players."""
    logger.info("=" * 70)
    logger.info("Scraping SA20 Teams and Players")
    logger.info("=" * 70)
    
    scraper = SA20APIScraper()
    teams_data = scraper.scrape_teams()
    
    if not teams_data:
        logger.warning("No teams found")
        return 0, 0
    
    teams_updated = 0
    players_added = 0
    players_updated = 0
    
    for team_data in teams_data:
        team = get_team_by_name(db, team_data["name"])
        if not team:
            logger.warning(f"Team not found in database: {team_data['name']}")
            continue
        
        logger.info(f"\nProcessing team: {team.name}")
        teams_updated += 1
        
        # Scrape players for this team
        slug = team_data.get("slug")
        if slug:
            logger.info(f"  Scraping players from: {slug}")
            players_data = scraper.scrape_team_players(slug)
            
            for player_data in players_data:
                # Check if player exists
                existing = db.query(models.Player).filter(
                    models.Player.name == player_data["name"],
                    models.Player.team_id == team.id
                ).first()
                
                # Normalize role string
                role_map = {
                    "batsman": models.PlayerRole.BATSMAN,
                    "batter": models.PlayerRole.BATSMAN,
                    "bowler": models.PlayerRole.BOWLER,
                    "all-rounder": models.PlayerRole.ALL_ROUNDER,
                    "all_rounder": models.PlayerRole.ALL_ROUNDER,
                    "wicket-keeper": models.PlayerRole.WICKET_KEEPER,
                    "wicket_keeper": models.PlayerRole.WICKET_KEEPER,
                    "keeper": models.PlayerRole.WICKET_KEEPER,
                    "wk": models.PlayerRole.WICKET_KEEPER,
                }
                
                # Try to get role from scraped data
                role = models.PlayerRole.BATSMAN  # Default fallback
                if player_data.get("role"):
                    role_str = str(player_data["role"]).lower().strip()
                    role = role_map.get(role_str, models.PlayerRole.BATSMAN)
                
                if existing:
                    # Update existing player
                    updated = False
                    if existing.role != role:
                        existing.role = role
                        updated = True
                    
                    if player_data.get("image_url"):
                        existing.image_url = player_data["image_url"]
                        updated = True
                    
                    if player_data.get("country"):
                        existing.country = player_data["country"]
                        updated = True
                    
                    if updated:
                        players_updated += 1
                        logger.info(f"    ✓ Updated: {player_data['name']} (role: {role.value})")
                else:
                    # Create new player
                    player = models.Player(
                        name=player_data["name"],
                        role=role,
                        batting_style=models.BattingStyle.RIGHT_HAND,
                        team_id=team.id,
                        country=player_data.get("country", "South Africa"),
                        age=25,  # Default
                        image_url=player_data.get("image_url"),
                    )
                    db.add(player)
                    players_added += 1
                    logger.info(f"    + Added: {player_data['name']} ({role.value})")
            
            # Rate limiting
            import time
            time.sleep(2)
    
    db.commit()
    logger.info(f"\n{'=' * 70}")
    logger.info(f"✓ Updated {teams_updated} teams")
    logger.info(f"✓ Added {players_added} new players")
    logger.info(f"✓ Updated {players_updated} existing players")
    logger.info(f"{'=' * 70}")
    
    return teams_updated, players_added + players_updated


def scrape_and_save_stats(db: Session, season: Optional[int] = None) -> int:
    """Scrape and save statistics."""
    logger.info("\n" + "=" * 70)
    logger.info(f"Scraping SA20 Statistics{' for season ' + str(season) if season else ' (all-time)'}")
    logger.info("=" * 70)
    
    scraper = SA20APIScraper()
    
    # Scrape batting stats
    logger.info("\nScraping batting statistics...")
    batting_stats = scraper.scrape_stats("batting", season)
    logger.info(f"  Found {len(batting_stats)} batting records")
    
    # Scrape bowling stats
    logger.info("\nScraping bowling statistics...")
    bowling_stats = scraper.scrape_stats("bowling", season)
    logger.info(f"  Found {len(bowling_stats)} bowling records")
    
    # Save to CSV
    import pandas as pd
    output_dir = Path(__file__).parent.parent.parent / "data" / "raw" / "sa20_stats"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    season_str = str(season) if season else "alltime"
    
    if batting_stats:
        batting_df = pd.DataFrame(batting_stats)
        batting_path = output_dir / f"sa20_batting_stats_{season_str}.csv"
        batting_df.to_csv(batting_path, index=False)
        logger.info(f"  ✓ Saved to {batting_path}")
    
    if bowling_stats:
        bowling_df = pd.DataFrame(bowling_stats)
        bowling_path = output_dir / f"sa20_bowling_stats_{season_str}.csv"
        bowling_df.to_csv(bowling_path, index=False)
        logger.info(f"  ✓ Saved to {bowling_path}")
    
    return len(batting_stats) + len(bowling_stats)


def scrape_and_save_fixtures(db: Session, season: int = 2026) -> int:
    """Scrape and save fixtures."""
    logger.info("\n" + "=" * 70)
    logger.info(f"Scraping SA20 Fixtures for season {season}")
    logger.info("=" * 70)
    
    scraper = SA20APIScraper()
    fixtures = scraper.scrape_fixtures(season)
    
    logger.info(f"Found {len(fixtures)} fixtures")
    
    # Note: Fixtures would need more parsing to extract teams, dates, venues
    # For now, we'll use the generated schedule
    
    return len(fixtures)


def main():
    """Main scraping function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensively scrape SA20 data")
    parser.add_argument("--season", type=int, default=2026, help="Season year")
    parser.add_argument("--skip-teams", action="store_true", help="Skip teams/players")
    parser.add_argument("--skip-stats", action="store_true", help="Skip statistics")
    parser.add_argument("--skip-fixtures", action="store_true", help="Skip fixtures")
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        if not args.skip_teams:
            teams_updated, players_total = update_teams_and_players_comprehensive(db)
        
        if not args.skip_stats:
            # Scrape current season and all-time
            scrape_and_save_stats(db, season=args.season)
            scrape_and_save_stats(db, season=None)  # All-time
        
        if not args.skip_fixtures:
            scrape_and_save_fixtures(db, season=args.season)
        
        logger.info("\n" + "=" * 70)
        logger.info("✓ Comprehensive scraping completed!")
        logger.info("=" * 70)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

