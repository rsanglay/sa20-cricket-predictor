"""Script to scrape and seed SA20 fixtures from official website."""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal
from data_pipeline.scrapers.sa20_playwright_scraper import SA20PlaywrightScraper
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    return name.strip().lower().replace("'", "").replace(" ", "_")


def get_team_by_name(db: Session, name: str) -> models.Team | None:
    """Get team from database by name (with fuzzy matching)."""
    normalized = normalize_team_name(name)
    
    # Try exact match first
    team = db.query(models.Team).filter(models.Team.name == name).first()
    if team:
        return team
    
    # Try short name
    team = db.query(models.Team).filter(models.Team.short_name == name).first()
    if team:
        return team
    
    # Try normalized match
    all_teams = db.query(models.Team).all()
    for t in all_teams:
        if normalize_team_name(t.name) == normalized or normalize_team_name(t.short_name or "") == normalized:
            return t
    
    return None


def get_venue_by_name(db: Session, name: str) -> models.Venue | None:
    """Get venue from database by name."""
    if not name:
        return None
    
    name_clean = name.strip()
    
    # Try exact match first
    venue = db.query(models.Venue).filter(models.Venue.name == name_clean).first()
    if venue:
        return venue
    
    # Try case-insensitive match
    all_venues = db.query(models.Venue).all()
    for v in all_venues:
        if v.name.lower() == name_clean.lower():
            return v
    
    # Try fuzzy match (partial match)
    for v in all_venues:
        v_name_lower = v.name.lower()
        name_lower = name_clean.lower()
        # Check if names are similar
        if name_lower in v_name_lower or v_name_lower in name_lower:
            return v
        # Check for common variations
        if 'super sport' in name_lower and 'supersport' in v_name_lower:
            return v
        if 'st george' in name_lower and "st george's" in v_name_lower:
            return v
    
    # Venue name mappings for common variations
    venue_mappings = {
        'SuperSport Park': 'Centurion',  # SuperSport Park is also known as Centurion
        'Centurion Park': 'Centurion',
        'Centurion': 'Centurion',
    }
    
    if name_clean in venue_mappings:
        mapped_name = venue_mappings[name_clean]
        venue = db.query(models.Venue).filter(models.Venue.name == mapped_name).first()
        if venue:
            return venue
    
    return None


async def seed_fixtures_from_scraper_async(db: Session, season: int = 2026) -> int:
    """Scrape fixtures from SA20 website and seed database (async version)."""
    logger.info(f"Scraping SA20 {season} fixtures from official website...")
    
    scraper = SA20PlaywrightScraper()
    fixtures = await scraper.scrape_fixtures(season=season)
    
    if not fixtures:
        logger.warning("No fixtures found from scraper.")
        return 0
    
    logger.info(f"Found {len(fixtures)} fixtures from website")
    
    # Clear existing fixtures for this season (only if we have new ones)
    if fixtures:
        deleted = db.query(models.Match).filter(models.Match.season == season).delete()
        logger.info(f"Cleared {deleted} existing fixtures for season {season}")
        db.commit()
    
    matches_added = 0
    matches_skipped = 0
    
    for fixture in fixtures:
        try:
            # Handle both raw_text format and parsed format
            if "raw_text" in fixture:
                logger.warning(f"Skipping fixture with only raw_text: {fixture.get('raw_text')[:50]}")
                matches_skipped += 1
                continue
            
            home_team_name = fixture.get("home_team")
            away_team_name = fixture.get("away_team")
            
            if not home_team_name or not away_team_name:
                logger.warning(f"Skipping fixture with missing team names: {fixture}")
                matches_skipped += 1
                continue
            
            home_team = get_team_by_name(db, home_team_name)
            away_team = get_team_by_name(db, away_team_name)
            
            if not home_team or not away_team:
                logger.warning(
                    f"Skipping fixture: {home_team_name} vs {away_team_name} "
                    f"(teams not found in database)"
                )
                matches_skipped += 1
                continue
            
            # Get venue - use home team's city to find venue as fallback
            venue = get_venue_by_name(db, fixture.get("venue"))
            if not venue:
                # Use home team's city to find venue
                if hasattr(home_team, 'city') and home_team.city:
                    # Map city to venue
                    city_to_venue = {
                        "Cape Town": "Newlands",
                        "Johannesburg": "Wanderers",
                        "Paarl": "Boland Park",
                        "Pretoria": "Centurion",
                        "Durban": "Kingsmead",
                        "Gqeberha": "St George's Park",
                    }
                    venue_name = city_to_venue.get(home_team.city)
                    if venue_name:
                        venue = get_venue_by_name(db, venue_name)
            
            if not venue:
                logger.warning(f"Venue not found for fixture, using first available venue")
                venue = db.query(models.Venue).first()
            
            if not venue:
                logger.error("No venues in database!")
                matches_skipped += 1
                continue
            
            match_date = fixture.get("match_date")
            if not match_date:
                logger.warning(f"Skipping fixture with no date: {home_team.name} vs {away_team.name}")
                matches_skipped += 1
                continue
            
            # Filter by season - for 2026 season, include Dec 2025 fixtures (group stage starts Dec 26)
            # Group stage: Dec 26, 2025 - Jan 19, 2026
            # Playoffs: Jan 21-23, 2026
            # Final: Jan 25, 2026
            if season == 2026:
                # Include fixtures from Dec 26, 2025 onwards through Jan 25, 2026
                from datetime import datetime
                season_start = datetime(2025, 12, 26)
                season_end = datetime(2026, 1, 25)
                if match_date < season_start or match_date > season_end:
                    logger.debug(f"Skipping fixture outside 2026 season range: {home_team.name} vs {away_team.name} on {match_date}")
                    matches_skipped += 1
                    continue
            elif match_date.year != season:
                logger.debug(f"Skipping fixture from {match_date.year} (requested season: {season}): {home_team.name} vs {away_team.name}")
                matches_skipped += 1
                continue
            
            # Check if match already exists
            existing = db.query(models.Match).filter(
                models.Match.home_team_id == home_team.id,
                models.Match.away_team_id == away_team.id,
                models.Match.season == season,
                models.Match.match_date == match_date,
            ).first()
            
            if existing:
                continue
            
            match = models.Match(
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                venue_id=venue.id,
                match_date=match_date,
                season=season,
                match_no=fixture.get("match_number"),  # Use match_no instead of match_number
            )
            db.add(match)
            matches_added += 1
            logger.info(f"  + Added: {home_team.name} vs {away_team.name} on {match_date}")
            
        except Exception as e:
            logger.error(f"Error processing fixture: {e}", exc_info=True)
            matches_skipped += 1
            continue
    
    db.commit()
    logger.info(f"✓ Seeded {matches_added} fixtures ({matches_skipped} skipped)")
    return matches_added


def seed_fixtures_from_scraper(db: Session, season: int = 2026) -> int:
    """Synchronous wrapper for async scraper."""
    return asyncio.run(seed_fixtures_from_scraper_async(db, season=season))


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape and seed SA20 fixtures from official website")
    parser.add_argument("--season", type=int, default=2026, help="Season year")
    args = parser.parse_args()
    
    db: Session = SessionLocal()
    try:
        matches_added = seed_fixtures_from_scraper(db, season=args.season)
        if matches_added == 0:
            logger.warning("No fixtures were added. The scraper may need to be updated for the current website structure.")
            logger.info("Falling back to generated schedule...")
            # Import and run the regular seed function as fallback
            from data_pipeline.seed_database import seed_matches, seed_teams, seed_venues
            team_map = {t.name: t for t in db.query(models.Team).all()}
            venue_map = {v.name: v for v in db.query(models.Venue).all()}
            if team_map and venue_map:
                # Fix: Use city instead of home_venue
                for team in team_map.values():
                    if hasattr(team, 'city') and team.city:
                        city_to_venue = {
                            "Cape Town": "Newlands",
                            "Johannesburg": "Wanderers",
                            "Paarl": "Boland Park",
                            "Pretoria": "Centurion",
                            "Durban": "Kingsmead",
                            "Gqeberha": "St George's Park",
                        }
                        # Update team object to have home_venue attribute for compatibility
                        if team.city in city_to_venue:
                            team.home_venue = city_to_venue[team.city]
                seed_matches(db, team_map, venue_map)
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding fixtures: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

