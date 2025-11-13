"""Comprehensive scraper using Playwright to handle JavaScript rendering."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal
from data_pipeline.scrapers.sa20_robust_scraper import RobustSA20Scraper

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def normalize_name(name: str) -> str:
    """Normalize name for matching."""
    return name.strip().lower().replace("'", "").replace(" ", "_").replace("-", "_")


def get_team_by_name(db: Session, name: str) -> models.Team | None:
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


async def scrape_and_update_all(db: Session, season: int = 2026) -> dict:
    """Scrape all SA20 data using Playwright."""
    logger.info("=" * 70)
    logger.info("SA20 Comprehensive Scraping with Playwright")
    logger.info("=" * 70)
    
    scraper = RobustSA20Scraper()
    
    results = {
        "teams_updated": 0,
        "players_added": 0,
        "players_updated": 0,
        "stats_scraped": 0,
        "fixtures_scraped": 0,
    }
    
    # 1. Scrape teams
    logger.info("\n[1/4] Scraping teams...")
    teams_data = await scraper.scrape_teams()
    logger.info(f"  Found {len(teams_data)} teams")
    results["teams_updated"] = len(teams_data)
    
    # 2. Scrape players for each team
    logger.info("\n[2/4] Scraping players from team pages...")
    for team_data in teams_data:
        team = get_team_by_name(db, team_data["name"])
        if not team:
            logger.warning(f"  Team not found: {team_data['name']}")
            continue
        
        logger.info(f"  Processing: {team.name}")
        slug = team_data.get("slug")
        if slug:
            players_data = await scraper.scrape_team_players(slug)
            logger.info(f"    Players from scraper: {len(players_data)}")
            if len(players_data) > 0:
                logger.info(f"    Sample names: {[p.get('name') for p in players_data[:3]]}")
                # Show source breakdown
                sources = {}
                for p in players_data:
                    source = p.get('source', 'unknown')
                    sources[source] = sources.get(source, 0) + 1
                logger.info(f"    Sources: {sources}")
            
            for player_data in players_data:
                # Try exact match first
                existing = db.query(models.Player).filter(
                    models.Player.name == player_data["name"],
                    models.Player.team_id == team.id
                ).first()
                
                # If no exact match, try fuzzy matching (check if names are similar)
                if not existing:
                    # Try matching by last name or initials
                    all_team_players = db.query(models.Player).filter(
                        models.Player.team_id == team.id
                    ).all()
                    
                    scraped_name = player_data["name"].lower()
                    for p in all_team_players:
                        db_name = p.name.lower()
                        # Check if last names match or if one is contained in the other
                        scraped_words = scraped_name.split()
                        db_words = db_name.split()
                        if scraped_words and db_words:
                            # Match by last name (most reliable)
                            if scraped_words[-1] == db_words[-1]:
                                existing = p
                                logger.info(f"    Matched '{player_data['name']}' to existing '{p.name}' by last name")
                                # Update the name to the full name from scraper
                                if p.name != player_data["name"]:
                                    p.name = player_data["name"]
                                    logger.info(f"    Updated name from '{p.name}' to '{player_data['name']}'")
                                break
                            # Or match if one name contains the other (for initials like "D Brevis" vs "Dewald Brevis")
                            if len(scraped_words) >= 2 and len(db_words) >= 2:
                                if scraped_words[-1] == db_words[-1] and (scraped_words[0][0] == db_words[0][0] or db_words[0][0] == scraped_words[0][0]):
                                    existing = p
                                    logger.info(f"    Matched '{player_data['name']}' to existing '{p.name}' by last name + initial")
                                    # Update the name to the full name from scraper
                                    if p.name != player_data["name"]:
                                        p.name = player_data["name"]
                                        logger.info(f"    Updated name from '{p.name}' to '{player_data['name']}'")
                                    break
                
                # Map role string to enum
                role_str = player_data.get("role", "batsman")
                role_map = {
                    "batsman": models.PlayerRole.BATSMAN,
                    "batter": models.PlayerRole.BATSMAN,
                    "bowler": models.PlayerRole.BOWLER,
                    "all_rounder": models.PlayerRole.ALL_ROUNDER,
                    "all-rounder": models.PlayerRole.ALL_ROUNDER,
                    "wicket_keeper": models.PlayerRole.WICKET_KEEPER,
                    "keeper": models.PlayerRole.WICKET_KEEPER,
                }
                role = role_map.get(role_str.lower(), models.PlayerRole.BATSMAN)
                
                if existing:
                    updated = False
                    if existing.role != role:
                        existing.role = role
                        updated = True
                    
                    # Always update image_url if we have one (even if existing is None)
                    if player_data.get("image_url"):
                        if existing.image_url != player_data["image_url"]:
                            existing.image_url = player_data["image_url"]
                            updated = True
                            logger.info(f"    📷 Updated image for: {player_data['name']}")
                    
                    if player_data.get("country") and existing.country != player_data["country"]:
                        existing.country = player_data["country"]
                        updated = True
                    
                    if updated:
                        results["players_updated"] += 1
                        logger.info(f"    ✓ Updated: {player_data['name']} ({role.value})")
                else:
                    player = models.Player(
                        name=player_data["name"],
                        role=role,
                        batting_style=models.BattingStyle.RIGHT_HAND,
                        team_id=team.id,
                        country=player_data.get("country", "South Africa"),
                        age=25,
                        image_url=player_data.get("image_url"),
                    )
                    db.add(player)
                    results["players_added"] += 1
                    logger.info(f"    + Added: {player_data['name']} ({role.value})")
        
        await asyncio.sleep(2)  # Rate limiting
    
    db.commit()
    
    # Note: Stats and fixtures scraping can be done separately
    # For now, we focus on player data
    logger.info("\n[3/3] Player scraping complete!")
    
    return results


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape SA20 data with Playwright")
    parser.add_argument("--season", type=int, default=2026, help="Season year")
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        results = asyncio.run(scrape_and_update_all(db, season=args.season))
        
        logger.info("\n" + "=" * 70)
        logger.info("✓ Scraping completed!")
        logger.info("=" * 70)
        logger.info(f"  Teams updated: {results['teams_updated']}")
        logger.info(f"  Players added: {results['players_added']}")
        logger.info(f"  Players updated: {results['players_updated']}")
        logger.info(f"  Stats scraped: {results['stats_scraped']}")
        logger.info(f"  Fixtures scraped: {results['fixtures_scraped']}")
        logger.info("=" * 70)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

